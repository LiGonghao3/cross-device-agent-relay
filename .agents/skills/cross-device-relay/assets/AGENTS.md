# Shared agent relay

These rules apply to every coding agent in this checkout.

1. The user's current request and fresh environment evidence outrank this file, the relay ledger, and private agent memory.
2. Before editing, read `.relay/current.md`; verify repository root, branch, HEAD, upstream, ahead/behind, and worktree state; explain any mismatch.
3. Only the agent named as `holder` may make intentional changes. Claim the baton before editing and release it only after recording the real stop point.
4. Preserve unrelated work. Inspect adjacent code and tests. Make the smallest complete change and validate it proportionally.
5. Keep product facts in source, tests, durable docs, and Git history. Keep `.relay/current.md` short and limited to the current task, evidence, unfinished changes, risks, and next action.
6. Never record passwords, tokens, private keys, secret host configuration, personal paths, or secret data in agent files, logs, commits, or relay state.
7. Stage explicit paths, inspect the staged diff, and never force-push or rewrite history without explicit approval.
8. Remote runners receive committed product revisions only. They do not hold GitHub credentials or the local agent overlay, and they are not a second source-editing location.

Use the repository-scoped `cross-device-relay` skill for setup, cross-computer state exchange, runner delivery, handoff, or recovery.

