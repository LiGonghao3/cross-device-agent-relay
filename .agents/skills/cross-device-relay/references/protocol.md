# Relay protocol

## Startup gate

Before intentional edits:

1. Read the ledger and repository instructions.
2. Record path, branch, HEAD, upstream, ahead/behind, and worktree state from fresh commands.
3. Explain existing changes and compare them with the ledger.
4. Pull relay state when another authoring computer may have worked since this clone was last active.
5. Claim the baton only when the current holder is `NONE` or already the same agent.

Stop when the branch or HEAD is unexpected, tracked changes are unexplained, the remote ledger has diverged, or another holder is active.

## While working

- Keep a single active task.
- Update the ledger when the stop point, risk, or next action changes materially.
- Put code facts in code and Git; put stable decisions in durable project documentation.
- Do not turn the ledger into a diary. Replace stale facts instead of appending history.

## Handoff

1. Stop intentional edits.
2. Account for tracked and untracked changes.
3. Record actual commands and results, not expected outcomes.
4. Record each intentional unfinished file and its purpose.
5. State one precise next action and the conditions that would make it unsafe.
6. Release the baton, then push the relay state when another authoring computer needs it.

## Ledger budget

Keep the ledger under roughly 150 lines. It contains only:

- dynamic Git identity;
- one current task and non-goals;
- recent evidence relevant to continuation;
- intentional unfinished changes;
- open risks and stop conditions;
- one ordered next-action list.

Delete completed narrative once Git or durable documentation carries it.

## Recovery

If the ledger is missing or stale, reconstruct it from the checkout, diffs, recent commits, and reproducible commands. Private agent memory is a hint, never proof. If two ledgers disagree, preserve both copies outside the worktree, compare their Git identities, and ask for direction rather than silently choosing a winner.

