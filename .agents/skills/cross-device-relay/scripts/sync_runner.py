#!/usr/bin/env python3
"""Fast-forward a credential-free SSH runner with a verified Git bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile


SAFE_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SAFE_HOME_PATH = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")


class SyncError(RuntimeError):
    pass


def run(args: list[str], cwd: Path | None = None, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise SyncError(f"{' '.join(args)} failed: {detail}")
    return result


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], repo, check=check).stdout.strip()


def ssh(host: str, command: str, *, check: bool = True) -> str:
    return run(["ssh", "-o", "BatchMode=yes", host, command], check=check).stdout.strip()


def validate(args: argparse.Namespace) -> None:
    if not SAFE_HOST.fullmatch(args.host):
        raise SyncError("host must be an SSH alias without shell metacharacters")
    if not SAFE_HOME_PATH.fullmatch(args.remote_repo) or ".." in args.remote_repo.split("/"):
        raise SyncError("remote-repo must be a safe path relative to the remote home directory")


def remote_cd(path: str) -> str:
    return f'cd "$HOME/{path}"'


def local_gate(repo: Path) -> tuple[str, str, str]:
    branch = git(repo, "branch", "--show-current")
    if not branch or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
        raise SyncError("a normally named local branch is required")
    head = git(repo, "rev-parse", "HEAD")
    upstream = git(repo, "rev-parse", "--abbrev-ref", "@{upstream}")
    if upstream != f"origin/{branch}":
        raise SyncError(f"expected upstream origin/{branch}, found {upstream}")
    if git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}").split() != ["0", "0"]:
        raise SyncError("local HEAD must already be pushed and aligned with upstream")
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise SyncError("local tracked worktree is not clean")
    origin = git(repo, "remote", "get-url", "origin")
    if re.search(r"https?://[^/]+@", origin):
        raise SyncError("origin URL appears to contain credentials")
    return branch, head, origin


def inspect_remote(host: str, path: str) -> dict[str, str] | None:
    command = (
        f'if [ -d "$HOME/{path}/.git" ]; then {remote_cd(path)} && '
        'printf "branch=%s\\nhead=%s\\ntracked=%s\\n" '
        '"$(git branch --show-current)" "$(git rev-parse HEAD)" '
        '"$(git status --porcelain --untracked-files=no | wc -l)"; '
        'else printf "absent=1\\n"; fi'
    )
    output = ssh(host, command)
    values = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    return None if values.get("absent") == "1" else values


def transfer(host: str, local_bundle: Path, remote_bundle: str) -> None:
    run(["scp", str(local_bundle), f"{host}:{remote_bundle}"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--host", required=True, help="existing SSH host alias")
    parser.add_argument("--remote-repo", required=True, help="path relative to remote $HOME")
    parser.add_argument("--bootstrap", action="store_true", help="create an absent runner checkout")
    args = parser.parse_args()
    try:
        validate(args)
        requested = Path(args.repo).expanduser().resolve()
        repo = Path(git(requested, "rev-parse", "--show-toplevel"))
        branch, head, origin = local_gate(repo)
        state = inspect_remote(args.host, args.remote_repo)
        if state is None and not args.bootstrap:
            raise SyncError("runner checkout is absent; rerun with --bootstrap only after approval")
        if state is not None:
            if state.get("tracked") != "0":
                raise SyncError("runner tracked worktree is not clean")
            if state.get("branch") != branch:
                raise SyncError(f"runner branch {state.get('branch')} does not match {branch}")
            remote_head = state.get("head", "")
            if run(["git", "cat-file", "-e", f"{remote_head}^{{commit}}"], repo, check=False).returncode:
                raise SyncError("runner HEAD is unknown locally")
            if run(["git", "merge-base", "--is-ancestor", remote_head, head], repo, check=False).returncode:
                raise SyncError("runner HEAD is not an ancestor of local HEAD")
            if remote_head == head:
                print(f"already aligned at {head}")
                return 0

        remote_bundle = f"/tmp/agent-relay-{head}.bundle"
        with tempfile.TemporaryDirectory(prefix="runner-sync-") as name:
            bundle = Path(name) / "sync.bundle"
            revisions = [f"refs/heads/{branch}"]
            if state is not None:
                revisions.append(f"^{state['head']}")
            run(["git", "bundle", "create", str(bundle), *revisions], repo)
            run(["git", "bundle", "verify", str(bundle)], repo)
            transfer(args.host, bundle, remote_bundle)

        try:
            refspec = shlex.quote(f"refs/heads/{branch}:refs/remotes/origin/{branch}")
            remote_ref = shlex.quote(f"origin/{branch}")
            if state is None:
                command = (
                    f'mkdir -p "$HOME/{args.remote_repo}" && {remote_cd(args.remote_repo)} && '
                    f'git init -q && git bundle verify {shlex.quote(remote_bundle)} >/dev/null && '
                    f'git fetch --no-tags {shlex.quote(remote_bundle)} {refspec} && '
                    f'git checkout -q -b {shlex.quote(branch)} --track {remote_ref} && '
                    f'git remote add origin {shlex.quote(origin)}'
                )
            else:
                command = (
                    f'{remote_cd(args.remote_repo)} && '
                    'test -z "$(git status --porcelain --untracked-files=no)" && '
                    f'test "$(git rev-parse HEAD)" = {shlex.quote(state["head"])} && '
                    f'git bundle verify {shlex.quote(remote_bundle)} >/dev/null && '
                    f'git fetch --no-tags {shlex.quote(remote_bundle)} {refspec} && '
                    f'git merge --ff-only {remote_ref}'
                )
            ssh(args.host, command)
        finally:
            ssh(args.host, f"rm -f -- {shlex.quote(remote_bundle)}", check=False)

        final = inspect_remote(args.host, args.remote_repo)
        if final is None or final.get("head") != head or final.get("tracked") != "0":
            raise SyncError("final runner verification failed")
        print(f"runner aligned: branch={branch} head={head}")
        return 0
    except SyncError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
