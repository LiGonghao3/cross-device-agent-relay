#!/usr/bin/env python3
"""Manage a bounded handoff ledger in tracked or detached mode."""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


RELAY_BRANCH = "agent-relay"
MANAGED_EXCLUDES = (
    "/.relay/",
    "/AGENTS.md",
    "/CLAUDE.md",
    "/.agents/skills/cross-device-relay/",
)
TRACKED_RELAY_PATHS = (
    ".relay/current.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".agents/skills/cross-device-relay/SKILL.md",
)
SENSITIVE_PATTERNS = (
    ("private key material", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("secret assignment", re.compile(r"(?i)\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s`]+")),
    ("Windows user path", re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+")),
    ("Unix user path", re.compile(r"/(?:Users|home)/[^/\s]+")),
    ("machine-specific SSH setting", re.compile(r"(?mi)^\s*(?:HostName|IdentityFile)\s+\S+")),
)


class RelayError(RuntimeError):
    pass


def run(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RelayError(f"{' '.join(args)} failed: {detail}")
    return result


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], repo, check=check).stdout.strip()


def repo_root(value: str) -> Path:
    candidate = Path(value).expanduser().resolve()
    root = git(candidate, "rev-parse", "--show-toplevel")
    return Path(root).resolve()


def asset(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / name


def is_tracked(repo: Path, relative: str) -> bool:
    return run(
        ["git", "ls-files", "--error-unmatch", "--", relative], repo, check=False
    ).returncode == 0


def add_local_excludes(repo: Path) -> None:
    exclude = Path(git(repo, "rev-parse", "--git-path", "info/exclude"))
    if not exclude.is_absolute():
        exclude = repo / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    lines = existing.splitlines()
    additions = [item for item in MANAGED_EXCLUDES if item not in lines]
    if additions:
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        block = "# cross-device-relay local overlay\n" + "\n".join(additions) + "\n"
        exclude.write_text(existing + prefix + block, encoding="utf-8")


def remove_managed_excludes(repo: Path) -> None:
    exclude = Path(git(repo, "rev-parse", "--git-path", "info/exclude"))
    if not exclude.is_absolute():
        exclude = repo / exclude
    if not exclude.exists():
        return
    lines = exclude.read_text(encoding="utf-8").splitlines()
    blocked = set(MANAGED_EXCLUDES) | {"# cross-device-relay local overlay"}
    updated = "\n".join(line for line in lines if line not in blocked).rstrip()
    exclude.write_text(updated + ("\n" if updated else ""), encoding="utf-8")


def copy_if_safe(repo: Path, source: Path, relative: str) -> str:
    target = repo / relative
    if is_tracked(repo, relative):
        return f"preserved tracked {relative}"
    if target.exists():
        return f"preserved existing {relative}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return f"created {relative}"


def init_repo(repo: Path, install_skill: bool, tracked: bool = False) -> None:
    if tracked:
        remove_managed_excludes(repo)
    else:
        add_local_excludes(repo)
    messages = [
        copy_if_safe(repo, asset("current.md"), ".relay/current.md"),
        copy_if_safe(repo, asset("AGENTS.md"), "AGENTS.md"),
        copy_if_safe(repo, asset("CLAUDE.md"), "CLAUDE.md"),
    ]
    if install_skill:
        target = repo / ".agents" / "skills" / "cross-device-relay"
        if not target.exists():
            shutil.copytree(Path(__file__).resolve().parent.parent, target)
            messages.append("installed repository-scoped skill")
        else:
            messages.append("preserved existing repository-scoped skill")
    if tracked:
        messages.append("tracked mode prepared; review and commit the relay files on the product branch")
    print("\n".join(messages))


def ledger_path(repo: Path) -> Path:
    path = repo / ".relay" / "current.md"
    if not path.is_file():
        raise RelayError(".relay/current.md is missing; run init first")
    return path


def ensure_ledger_safe(text: str) -> None:
    findings = [label for label, pattern in SENSITIVE_PATTERNS if pattern.search(text)]
    if findings:
        raise RelayError("ledger contains blocked sensitive data: " + ", ".join(findings))


def header_value(text: str, key: str) -> str:
    match = re.search(
        rf'(?m)^{re.escape(key)}:\s*(?:"([^"]*)"|([^\n]*?))\s*$', text
    )
    if not match:
        raise RelayError(f"ledger header has no {key} field")
    value = match.group(1) if match.group(1) is not None else match.group(2)
    return value.strip()


def replace_header(text: str, key: str, value: str) -> str:
    pattern = rf'(?m)^({re.escape(key)}:)\s*.*$'
    updated, count = re.subn(pattern, rf'\1 "{value}"', text, count=1)
    if count != 1:
        raise RelayError(f"ledger header has no unique {key} field")
    return updated


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def update_identity(repo: Path, text: str) -> str:
    text = replace_header(text, "updated", now_utc())
    text = replace_header(text, "branch", git(repo, "branch", "--show-current"))
    return replace_header(text, "head", git(repo, "rev-parse", "HEAD"))


def verify_ledger_identity(repo: Path, text: str) -> None:
    recorded_branch = header_value(text, "branch")
    recorded_head = header_value(text, "head")
    current_branch = git(repo, "branch", "--show-current")
    current_head = git(repo, "rev-parse", "HEAD")
    if recorded_branch and recorded_branch != current_branch:
        raise RelayError(f"ledger branch {recorded_branch} does not match {current_branch}")
    if recorded_head:
        if is_tracked(repo, ".relay/current.md"):
            if run(
                ["git", "merge-base", "--is-ancestor", recorded_head, current_head],
                repo,
                check=False,
            ).returncode:
                raise RelayError(f"tracked ledger base {recorded_head} is not an ancestor of {current_head}")
        elif recorded_head != current_head:
            raise RelayError(f"ledger HEAD {recorded_head} does not match {current_head}")


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def claim(repo: Path, agent: str) -> None:
    path = ledger_path(repo)
    text = path.read_text(encoding="utf-8")
    ensure_ledger_safe(text)
    verify_ledger_identity(repo, text)
    holder = header_value(text, "holder")
    if holder not in {"NONE", agent}:
        raise RelayError(f"baton is held by {holder}")
    text = replace_header(text, "holder", agent)
    text = replace_header(text, "status", "WORKING")
    write_atomic(path, update_identity(repo, text))


def release(repo: Path) -> None:
    path = ledger_path(repo)
    text = path.read_text(encoding="utf-8")
    ensure_ledger_safe(text)
    verify_ledger_identity(repo, text)
    text = replace_header(text, "holder", "NONE")
    text = replace_header(text, "status", "READY_TO_HANDOFF")
    write_atomic(path, update_identity(repo, text))


def status(repo: Path) -> None:
    upstream = git(repo, "rev-parse", "--abbrev-ref", "@{upstream}", check=False) or "(none)"
    counts = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}", check=False) or "n/a"
    print(f"repo={repo}")
    print(f"branch={git(repo, 'branch', '--show-current')}")
    print(f"head={git(repo, 'rev-parse', 'HEAD')}")
    print(f"upstream={upstream}")
    print(f"ahead_behind={counts}")
    print("worktree:")
    print(git(repo, "status", "--short") or "(clean)")
    print("\nledger:\n" + ledger_path(repo).read_text(encoding="utf-8"))


def remote_url(repo: Path) -> str:
    url = git(repo, "remote", "get-url", "origin")
    if not url:
        raise RelayError("origin remote is missing")
    return url


def fetch_remote_state(repo: Path) -> str:
    git(repo, "fetch", "origin", RELAY_BRANCH)
    return git(repo, "show", "FETCH_HEAD:current.md") + "\n"


def fetch_tracked_state(repo: Path) -> str:
    branch = git(repo, "branch", "--show-current")
    git(repo, "fetch", "origin", branch)
    return git(repo, "show", f"origin/{branch}:.relay/current.md") + "\n"


def state_diff(local_text: str, remote_text: str, remote_label: str = "origin/agent-relay:current.md") -> str:
    return "".join(
        difflib.unified_diff(
            local_text.splitlines(keepends=True),
            remote_text.splitlines(keepends=True),
            fromfile="local/.relay/current.md",
            tofile=remote_label,
        )
    )


def preview_state(repo: Path) -> None:
    local_text = ledger_path(repo).read_text(encoding="utf-8")
    ensure_ledger_safe(local_text)
    tracked = is_tracked(repo, ".relay/current.md")
    remote_text = fetch_tracked_state(repo) if tracked else fetch_remote_state(repo)
    ensure_ledger_safe(remote_text)
    label = f"origin/{git(repo, 'branch', '--show-current')}:.relay/current.md" if tracked else "origin/agent-relay:current.md"
    print(state_diff(local_text, remote_text, label) or "relay state is identical")


def push_state(repo: Path) -> None:
    if is_tracked(repo, ".relay/current.md"):
        raise RelayError("tracked mode publishes the ledger with the product commit; commit and push the current branch")
    source = ledger_path(repo)
    text = source.read_text(encoding="utf-8")
    ensure_ledger_safe(text)
    if header_value(text, "holder") != "NONE":
        raise RelayError("release the baton before publishing relay state")
    with tempfile.TemporaryDirectory(prefix="agent-relay-") as name:
        temp = Path(name)
        git(temp, "init", "-q")
        git(temp, "config", "user.name", "Agent Relay")
        git(temp, "config", "user.email", "agent-relay@users.noreply.github.com")
        git(temp, "remote", "add", "origin", remote_url(repo))
        fetched = run(["git", "fetch", "-q", "origin", RELAY_BRANCH], temp, check=False)
        if fetched.returncode == 0:
            git(temp, "checkout", "-q", "-b", RELAY_BRANCH, "FETCH_HEAD")
        else:
            git(temp, "checkout", "-q", "--orphan", RELAY_BRANCH)
        (temp / "current.md").write_text(text, encoding="utf-8", newline="\n")
        git(temp, "add", "--", "current.md")
        changed = run(["git", "diff", "--cached", "--quiet"], temp, check=False).returncode != 0
        if changed:
            git(temp, "commit", "-q", "-m", f"Update relay state {now_utc()}")
        git(temp, "push", "origin", f"HEAD:refs/heads/{RELAY_BRANCH}")


def pull_state(repo: Path, accept: bool) -> None:
    if is_tracked(repo, ".relay/current.md"):
        raise RelayError("tracked mode receives the ledger with the product branch; use git pull --ff-only")
    local_text = ledger_path(repo).read_text(encoding="utf-8")
    ensure_ledger_safe(local_text)
    if header_value(local_text, "holder") != "NONE":
        raise RelayError("local baton is active; release it before pulling remote state")
    text = fetch_remote_state(repo)
    ensure_ledger_safe(text)
    if header_value(text, "holder") != "NONE":
        raise RelayError("remote relay state still has an active holder")
    diff = state_diff(local_text, text)
    if not diff:
        print("relay state is identical")
        return
    print(diff)
    if not accept:
        raise RelayError("remote state differs; inspect the diff and rerun pull-state with --accept")
    write_atomic(ledger_path(repo), text)


def doctor(repo: Path) -> None:
    text = ledger_path(repo).read_text(encoding="utf-8")
    ensure_ledger_safe(text)
    for key in ("protocol", "updated", "holder", "status", "branch", "head"):
        header_value(text, key)
    if header_value(text, "holder") not in {"NONE", "CODEX", "CLAUDE"}:
        raise RelayError("ledger holder is invalid")
    verify_ledger_identity(repo, text)
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise RelayError("tracked worktree is not clean")
    if is_tracked(repo, ".relay/current.md"):
        missing = [path for path in TRACKED_RELAY_PATHS if not is_tracked(repo, path)]
        if missing:
            raise RelayError("tracked relay files are missing from Git: " + ", ".join(missing))
        print("doctor: ok (tracked mode)")
    else:
        missing = [
            path
            for path in MANAGED_EXCLUDES
            if run(["git", "check-ignore", "-q", "--", path.lstrip("/")], repo, check=False).returncode
        ]
        if missing:
            raise RelayError("local overlay exclusions are missing: " + ", ".join(missing))
        print("doctor: ok (detached mode)")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "doctor", "release", "push-state", "preview-state", "pull-state"):
        item = sub.add_parser(name)
        item.add_argument("--repo", default=".")
        if name == "init":
            item.add_argument("--no-install-skill", action="store_true")
            item.add_argument("--tracked", action="store_true")
        if name == "pull-state":
            item.add_argument("--accept", action="store_true")
    item = sub.add_parser("claim")
    item.add_argument("--repo", default=".")
    item.add_argument("--agent", choices=("CODEX", "CLAUDE"), required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        repo = repo_root(args.repo)
        if args.command == "init":
            init_repo(repo, not args.no_install_skill, args.tracked)
        elif args.command == "status":
            status(repo)
        elif args.command == "doctor":
            doctor(repo)
        elif args.command == "claim":
            claim(repo, args.agent)
        elif args.command == "release":
            release(repo)
        elif args.command == "push-state":
            push_state(repo)
        elif args.command == "preview-state":
            preview_state(repo)
        elif args.command == "pull-state":
            pull_state(repo, args.accept)
    except RelayError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
