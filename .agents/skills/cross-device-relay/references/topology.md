# Topology and storage model

## Roles

| Role | Examples | May hold GitHub credentials | Writes source |
|---|---|---:|---:|
| Authoring node | desktop, laptop | yes | yes |
| Runner | laboratory GPU host, shared server | no | no |

An authoring node is trusted to edit, commit, and push. A runner executes and validates an already committed revision.

## Storage modes

```text
desktop  <--- private GitHub repository --->  laptop
   |                                                                        |
   +---- verified Git bundle over existing SSH ----> remote runner <--------+
                         (product commit only; no GitHub credential)
```

### Tracked mode

Source, tests, reproducible configuration, durable documentation, Agent rules, the Skill, and `.relay/current.md` share the normal product branch. This is the simplest choice for a private research repository operated serially by one person across computers.

### Detached mode

One small `current.md` file travels through the private `agent-relay` branch. The relay script updates this branch through a temporary repository, so the product worktree never switches branches and the file never appears in product history.

Use it only on a private remote. It must not contain secrets, personal paths, private host configuration, datasets, or raw logs. Anyone with access to the private repository may read it.

### Local overlay

`.relay/`, optional local `AGENTS.md`/`CLAUDE.md`, and a repository-scoped copy of the skill. Put these in `.git/info/exclude` when they must not be part of the product repository. Because this exclude file is clone-local, initialize the overlay once on every authoring node.

## Choose the smallest topology

- One authoring computer: local overlay only.
- Desktop and laptop in one private research repository: tracked mode is usually simplest.
- A product repository that must exclude agent state: detached mode plus the private `agent-relay` branch.
- Desktop/laptop plus runner: add bundle delivery; never add GitHub credentials merely for convenience.
- A runner that must contribute code is no longer a runner. Treat it as an authoring node and revisit its trust, credentials, and conflict model explicitly.

## `.gitignore` versus `.git/info/exclude`

- `.gitignore`: versioned, shared policy for generated outputs every clone should ignore.
- `.git/info/exclude`: local policy for machine- or workflow-specific files that must not alter the product branch.
- Both only reduce accidental staging. Already tracked files remain tracked, and secrets are still recoverable from history.
