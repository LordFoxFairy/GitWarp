---
name: gitwarp
description: Use when concurrent Claude Code or Codex agents need isolated git worktrees, branch collision prevention, workspace context, task dossiers, prompt statusline banners, or persistent handoff records.
---

# GitWarp

## Overview

GitWarp is the worktree isolation protocol for coding agents. It creates task sandboxes with native `git worktree`, records ownership in `.gitwarp/ledger.json`, and gives each sandbox a dossier: `task.md`, `progress.md`, and `lessons.md`.

Dossiers live in the root repository control plane under `.gitwarp/dossiers/`. They are not copied into business source trees. Agents read them through `gitwarp enter`, `gitwarp context`, `gitwarp board`, or the Web Console Metadata tab.

Managed worktree directories follow Git branch hierarchy: `feature/my-task` maps to `.gitwarp/worktrees/feature/my-task`. Older flat paths remain readable because Git live worktrees are the source of truth.

## Core Rule

Do not use `git switch`, `git checkout`, or direct `git worktree add` in the main checkout for agent task work. Use GitWarp commands so branch collisions, ledger state, and dossier files stay consistent.

## Primary Commands

| Command | Use |
| --- | --- |
| `gitwarp task create` | Preferred intake for new user work; creates a task worktree and richer dossier from title, description, acceptance, and verification notes. |
| `gitwarp create` | Lower-level creation for explicit base worktrees or manually specified task sandboxes. |
| `gitwarp switch` | Locate an existing worktree and print its absolute path or `cd` command. |
| `gitwarp remove` | Destroy a sandbox and its dossier when explicitly requested; add `--force` only for dirty targets. |
| `gitwarp matrix` | Read-only control-plane view across Git refs, live worktrees, ledger rows, and dossiers. |
| `gitwarp next` | Read-only prioritized action queue derived from matrix categories; shows safety and recommended commands. |
| `gitwarp branches` | List local branch refs with cleanup safety metadata. |
| `gitwarp prune-branch` | Delete only a safe merged local branch ref after explicit selection. |
| `gitwarp handoff` | Record progress and optional lessons during work. |
| `gitwarp statusline` | Print a raw prompt banner such as `GITWARP[main-repo]`. |
| `gitwarp enter` | Return hook/session context and dossier snippets; not the main workflow command. |
| `gitwarp board` | List active sandboxes. |
| `gitwarp reconcile` | Read-only audit for dirty, stale, missing, merged, or drifted worktrees. |
| `gitwarp doctor` | Check install, hook, plugin, and runtime health. |
| `gitwarp web` | Open a local Web Console with Code, Metadata, and Health tabs. |

`start`, `summon`, `collapse`, and `dispatch` remain lower-level commands. Prefer `task create` for new work, `create --role base` for long-lived user feature branches, and `switch` or `remove` for existing sandboxes unless you specifically need a rendered launch command from `dispatch`.

The Web Console is for human supervision: open a project, choose a base branch, choose a task worktree under that base, browse tracked files in Code, inspect task/progress/lessons and next actions in Metadata, review Git refs/live worktrees/ledger rows/dossiers in Refs & Worktrees, and review doctor/reconcile findings in Health.

## Control Plane Matrix

Use `gitwarp matrix` when onboarding an existing repository or when `.git` and `.gitwarp` appear inconsistent. It reads Git branch refs, live Git worktrees, GitWarp ledger rows, and dossier directories without mutating any of them.

Use `gitwarp next` after `matrix` when you need a short prioritized queue. It returns actions such as `merged_task`, `merged_ref`, `untracked_worktree`, `stale_ledger`, and `orphan_dossier` with `safety`, `priority`, and `command` fields. It never removes, prunes, merges, or adopts by itself.

Important matrix categories:

- `untracked_worktree`: a live Git worktree exists outside the ledger. Ask before adopting it, then use the printed `gitwarp adopt ...` command.
- `stale_ledger`: a ledger row points to a worktree Git no longer reports. This is GitWarp metadata repair, not Git branch deletion. Use the printed `gitwarp init` only when the user wants stale metadata cleaned.
- `orphan_dossier`: a dossier directory is no longer referenced by the ledger. Treat it as legacy metadata; do not delete manually unless the user asks.
- `merged_ref`: a local branch ref is merged and safe according to GitWarp blockers. It is marked `deprecated`; delete only after explicit user selection with `gitwarp prune-branch`.
- `merged_task`: a live task worktree has already been merged into its parent base. It is a cleanup candidate, but `finish --collapse-merged` must still be explicitly run and will refuse dirty worktrees.

If multiple rows share the same branch, use `row_id` to distinguish branch refs, live worktrees, stale ledger rows, and dossier-only legacy records.

## Branch Roles

GitWarp tracks two workspace roles:

- `base`: long-lived coordination branch. `main` is always base. User-requested feature branches are usually base branches. Base branches do not have task dossiers and must not be auto-collapsed.
- `task`: short-lived agent branch under a `base_branch`. Task branches have dossiers and may be removed after they are merged into their parent base.

For a new user feature, prefer:

```bash
gitwarp create --role base --branch feature/user-request \
  --purpose "Coordinate user-request work"

gitwarp task create --base feature/user-request \
  --title "Implement user-request task" \
  --branch agent/user-request-impl \
  --description "Implement the requested feature in an agent task worktree"
```

## Agent Workflow

From any repository path:

```bash
gitwarp init
gitwarp statusline
gitwarp matrix
gitwarp next
gitwarp enter
```

Use `statusline` for automatic prompt hooks. Use `matrix` when the agent needs to understand historical Git state before creating or removing anything. Use `next` when the agent needs the safest prioritized maintenance action. Use `enter` manually when full dossier context is needed; do not wire full `enter` output into every session start.

If work requires edits and you are in the main checkout:

```bash
gitwarp task create --title "Implement isolated task" \
  --description "Build the requested change in an isolated worktree" \
  --acceptance "Tests cover the new behavior" \
  --verify "python3 -m unittest discover -s tests -p 'test_*.py' -v"
```

If the user asked for a dedicated feature branch, create that branch as `--role base` first, then run `gitwarp task create --base <feature-branch> ...` for implementation work.

Move into the returned `path`. When returning to a known branch later, print a shell navigation command:

```bash
gitwarp switch --branch agent/user-request-impl
gitwarp switch --branch agent/user-request-impl --format shell
```

Inside the sandbox, read the returned dossier files before editing. Record milestones:

```bash
gitwarp handoff --status implementing \
  --progress "Short, factual milestone"
```

If blocked:

```bash
gitwarp pause --reason "Waiting for credentials"
gitwarp resume --progress "Credentials configured; continuing"
```

When verified, record the outcome and leave the sandbox for user review unless cleanup was explicitly requested:

```bash
gitwarp finish --status pushed \
  --progress "Verified and pushed"
```

When a task branch has already been merged into its parent base and the worktree is clean, collapse the task sandbox:

```bash
gitwarp finish --status merged \
  --progress "Merged into parent base" \
  --collapse-merged
```

`--collapse-merged` refuses base worktrees, dirty worktrees, and task branches whose HEAD is not merged into `base_branch`.

When the user explicitly wants the sandbox destroyed regardless of merge state:

```bash
gitwarp finish --status pushed \
  --progress "Verified and pushed" \
  --collapse
```

Use `gitwarp remove` inside a sandbox only when it should be destroyed without a final handoff. From the main checkout, target one explicitly with `gitwarp remove --branch <branch>`. If the target has uncommitted or untracked files, `remove` refuses to proceed until you rerun with `--force`.

`remove`, `collapse`, `finish --collapse`, and `finish --collapse-merged` delete the worktree, its ledger row, and the matching `.gitwarp/dossiers/...` directory. They do not merge, push, or delete the Git branch. If the user assigns an existing worktree, finish the requested work there and stop after verification unless the user explicitly asks for push, merge, remove, or collapse.

For local branch cleanup, use the separate ref commands:

```bash
gitwarp matrix
gitwarp next
gitwarp branches
gitwarp prune-branch --branch feature/old-merged-task
```

`matrix` marks legacy and merged candidates but does not clean them. `next` turns those candidates into an ordered action queue. `prune-branch` refuses the default branch, base branches, branches checked out in any worktree, branches still tracked in the GitWarp ledger, and branches whose HEAD is not merged into the selected base. It deletes only the local Git ref; it does not delete worktrees or dossiers.

## Instructions

Local instruction files are not mounted automatically. Pass them explicitly when creating a sandbox:

```bash
gitwarp task create --title "Implement isolated task" \
  --branch agent/isolated-task \
  --instruction AGENTS.md \
  --instruction CLAUDE.md=docs/claude-code.md
```

Repeatable instruction stacks live in `.gitwarp/instruction_profiles.json` and are selected with `--instruction-profile <name>`. Instructions are copied by default; use `--instruction-mode symlink` only when live rule edits are intended.

## Output Contract

Automation commands print deterministic single-line JSON. `statusline`, `enter --format prompt`, `board --format table`, and `switch --format shell` intentionally print raw text. If a JSON command returns nonzero or `"ok": false`, stop and report the `error` field.

`--cwd /absolute/path` is optional. Use it from hooks, Web/API handlers, scripts, or when controlling a repository from another directory. For normal terminal use inside the target repo or sandbox, omit it.

## Installation Notes

Use `gitwarp` from `PATH`. The skill `scripts/` directory contains bootstrap helpers only, primarily `scripts/install_cli.py`; it does not contain product runtime code. Runtime changes belong in `src/gitwarp/`.

Read `references/install.md` only when installing, packaging, or troubleshooting plugin discovery.
