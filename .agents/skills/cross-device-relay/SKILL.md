---
name: cross-device-relay
description: Set up, operate, or recover a Git-based research workflow across multiple trusted authoring computers and credential-free remote runners, including concise Codex/Claude handoffs. Use for cross-device continuity, relay ledgers, private GitHub coordination, or safe bundle delivery to compute hosts; do not use for ordinary single-machine Git tasks.
---

# Cross-device Relay

Keep three kinds of state separate:

1. Product history belongs on normal Git branches.
2. The current handoff belongs in the bounded local `.relay/current.md` ledger and, when two authoring computers must share it, the private `agent-relay` branch.
3. Remote runners receive only committed product history. They do not receive the local overlay or GitHub credentials.

## Start every relay task

1. Locate the repository root and read `AGENTS.md`, `CLAUDE.md`, and `.relay/current.md` when present.
2. Inspect the current path, branch, HEAD, upstream, ahead/behind counts, tracked changes, untracked changes, and remotes.
3. Reconcile those facts with the ledger. Stop before writing when an unexplained mismatch or another active holder exists.
4. Identify the node role: trusted authoring computer or credential-free runner.
5. Keep the user's explicit goal and current command output above ledger claims or private agent memory.

For a new layout or an added machine, read [references/topology.md](references/topology.md). For a handoff or recovery, read [references/protocol.md](references/protocol.md).

## Set up a repository

Use `scripts/relay.py init --repo <path>` to create the local overlay without changing the product branch. It:

- creates a concise ledger;
- creates `AGENTS.md` and `CLAUDE.md` only when those files are absent and untracked;
- adds local-only paths to `.git/info/exclude`, not the shared `.gitignore`;
- can install this skill into the repository's `.agents/skills` folder.

If the repository already tracks an agent-instruction file, preserve it and integrate only the non-conflicting relay invariants. Never overwrite project rules automatically.

Use a versioned `.gitignore` for project-wide generated files that every clone should ignore. Use `.git/info/exclude` for the relay overlay that must remain clone-local. Neither mechanism is a security boundary; secrets must never enter the repository.

## Exchange the baton

- `scripts/relay.py status --repo <path>`: show current Git identity and the ledger.
- `scripts/relay.py claim --repo <path> --agent CODEX|CLAUDE`: claim the soft lock after verification.
- `scripts/relay.py release --repo <path>`: release the lock after recording the actual stop point.
- `scripts/relay.py push-state --repo <path>`: publish only the ledger to the private `agent-relay` branch without switching the product worktree.
- `scripts/relay.py pull-state --repo <path>`: retrieve that ledger on another trusted authoring computer.

Before pushing state, remove secrets, machine-specific host details, personal paths, raw logs, and stale narrative. The ledger should name one current task, completed evidence, intentional unfinished changes, risks, and the next executable action. Git already contains historical detail.

## Deliver to a remote runner

Use `scripts/sync_runner.py` only after the product commit is pushed and the local tracked worktree is clean. It sends a verified Git bundle over an existing SSH trust path and permits only a fast-forward update. An initial runner checkout requires the explicit `--bootstrap` flag.

Do not place GitHub tokens, deploy keys, personal SSH keys, or browser credentials on a shared runner. Do not edit source independently on the runner. Bring runner findings back as evidence, then make source changes on an authoring computer.

## Git and safety invariants

- Preserve unrelated work and explain every pre-existing change.
- Stage explicit paths and inspect the staged diff. Do not force-push or rewrite history.
- Never claim a push, runner update, test, or handoff without fresh output.
- A handoff is ready only when the ledger matches Git and the holder is `NONE`.
- A runner update is ready only when its HEAD equals the pushed product commit and its tracked worktree is clean.
- Ask before adding a new external destination, changing repository visibility, credentials, permissions, or destructive history.
