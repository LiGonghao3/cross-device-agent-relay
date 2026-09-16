# Cross-device Agent Relay

A small, agent-readable workflow for continuing research work across a desktop, a laptop, and an optional remote compute host without pretending that chat memory is shared.

The core idea is separation:

- normal Git branches carry source, tests, and durable project facts;
- a private `agent-relay` branch carries one short handoff ledger between trusted authoring computers;
- a local overlay gives Codex and Claude Code the same operating rules without changing the product branch;
- remote runners receive verified Git bundles over existing SSH and keep no GitHub credentials.

This repository contains a Codex Skill built on the open Agent Skills layout. The templates and scripts are usable by other coding agents as ordinary repository instructions too.

## Why not put everything in one `AGENTS.md`?

Stable rules, live task state, product history, and machine credentials have different lifetimes. Mixing them creates stale instructions and accidental leaks. This workflow makes each channel explicit and keeps the live ledger bounded.

## Topologies

| Setup | Product sync | Handoff sync | Remote delivery |
|---|---|---|---|
| One computer | Git | local ledger | none |
| Desktop + laptop | private GitHub remote | private `agent-relay` branch | none |
| Desktop + laptop + runner | private GitHub remote | private `agent-relay` branch | verified bundle over SSH |

The runner is intentionally not a third editing location. It runs a known commit and returns evidence.

## Install the Skill

For repository-scoped use, copy `.agents/skills/cross-device-relay` into the same path in the target repository. Codex discovers repository skills from `.agents/skills`.

For personal use, copy the skill folder into your user skills directory. Then invoke it explicitly with `$cross-device-relay` or let Codex select it for matching cross-device collaboration tasks.

## Initialize a project

```bash
python .agents/skills/cross-device-relay/scripts/relay.py init --repo /path/to/project
```

The command creates a local `.relay/current.md`, compatible `AGENTS.md` and `CLAUDE.md` files when they are absent, and clone-local exclusions. Existing tracked instruction files are preserved.

Typical baton flow:

```bash
python .agents/skills/cross-device-relay/scripts/relay.py pull-state --repo .
python .agents/skills/cross-device-relay/scripts/relay.py claim --repo . --agent CODEX
# work, test, and update the ledger
python .agents/skills/cross-device-relay/scripts/relay.py release --repo .
python .agents/skills/cross-device-relay/scripts/relay.py push-state --repo .
```

The state commands use a separate `agent-relay` branch through a temporary checkout. They do not switch or add files to the product worktree. Use this branch only on a private remote and never put secrets in the ledger.

## Deliver a pushed commit to a runner

```bash
python .agents/skills/cross-device-relay/scripts/sync_runner.py \
  --repo . --host lab-runner --remote-repo projects/example --bootstrap
```

Later updates omit `--bootstrap`. The script requires an existing non-interactive SSH trust path, a clean tracked worktree, a pushed commit, and a fast-forward relationship. It does not install software, create credentials, or run project-specific tests.

## `.gitignore` is not the relay

Use the shared `.gitignore` for generated outputs that every clone should ignore. Use `.git/info/exclude` for the local relay overlay when it must not appear in product history. Neither prevents a secret from being recovered after it has been committed.

An example project `.gitignore` is included in the Skill assets.

## An anonymized research example

An image-enhancement project is edited on a desktop and a laptop. Both push product commits to a private GitHub repository and exchange a concise handoff through `agent-relay`. A laboratory GPU host has no GitHub token; it receives only the pushed commit through the bundle script, runs evaluation, and reports results. Local Agent instructions and the live ledger never enter the runner checkout.

## Safety properties

- No automatic force-push, reset, merge, deletion, credential creation, or package installation.
- No product delivery from an unpushed or dirty tracked worktree.
- No runner update when histories diverge.
- No overwrite of existing tracked Agent instructions during initialization.
- No claim that another machine is synchronized without verifying its commit.

## License

MIT. See [LICENSE](LICENSE).

