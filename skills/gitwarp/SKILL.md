---
name: gitwarp
description: Use when concurrent Claude Code or Codex agents need isolated git worktrees, branch collision prevention, workspace context, task dossiers, prompt statusline banners, or persistent handoff records.
---

# GitWarp

## Overview

GitWarp is the worktree isolation protocol for coding agents. It creates task sandboxes with native `git worktree`, records ownership in `.gitwarp/ledger.json`, and gives each sandbox a dossier: `task.md`, `progress.md`, and `lessons.md`.

## Core Rule

Do not use `git switch`, `git checkout`, or direct `git worktree add` in the main checkout for agent task work. Use GitWarp commands so branch collisions, ledger state, and dossier files stay consistent.

## Primary Commands

| Command | Use |
| --- | --- |
| `gitwarp create` | Create a base or task worktree. Task worktrees are dossier-backed. |
| `gitwarp switch` | Locate an existing worktree and print its absolute path or `cd` command. |
| `gitwarp remove` | Destroy a sandbox and its dossier when explicitly requested; add `--force` only for dirty targets. |
| `gitwarp handoff` | Record progress and optional lessons during work. |
| `gitwarp statusline` | Print a raw prompt banner such as `GITWARP[main-repo]`. |
| `gitwarp enter` | Return hook/session context and dossier snippets; not the main workflow command. |
| `gitwarp board` | List active sandboxes. |
| `gitwarp reconcile` | Read-only audit for dirty, stale, missing, merged, or drifted worktrees. |
| `gitwarp doctor` | Check install, hook, plugin, and runtime health. |
| `gitwarp web` | Open a local Web Console with Code, Metadata, and Health tabs. |

`start`, `summon`, `collapse`, and `dispatch` remain lower-level commands. Prefer `create`, `switch`, and `remove` unless you specifically need a rendered launch command from `dispatch`.

The Web Console is for human supervision: open a project, choose a base branch, choose a task worktree under that base, browse tracked files in Code, inspect task/progress/lessons in Metadata, and review doctor/reconcile findings in Health.

## Branch Roles

GitWarp tracks two workspace roles:

- `base`: long-lived coordination branch. `main` is always base. User-requested feature branches are usually base branches. Base branches do not have task dossiers and must not be auto-collapsed.
- `task`: short-lived agent branch under a `base_branch`. Task branches have dossiers and may be removed after they are merged into their parent base.

For a new user feature, prefer:

```bash
gitwarp create --role base --branch feature/user-request \
  --purpose "Coordinate user-request work"

gitwarp create --branch agent/user-request-impl \
  --base feature/user-request \
  --purpose "Implement user-request task"
```

## Agent Workflow

From any repository path:

```bash
gitwarp init
gitwarp statusline
gitwarp enter
```

Use `statusline` for automatic prompt hooks. Use `enter` manually when full dossier context is needed; do not wire full `enter` output into every session start.

If work requires edits and you are in the main checkout:

```bash
gitwarp create --branch feature/my-task \
  --purpose "Implement isolated task"
```

If the user asked for a dedicated feature branch, create that branch as `--role base` first, then create your implementation branch as a task with `--base <feature-branch>`.

Move into the returned `path`, or print a shell navigation command:

```bash
gitwarp switch --branch feature/my-task
gitwarp switch --branch feature/my-task --format shell
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

## Instructions

Local instruction files are not mounted automatically. Pass them explicitly when creating a sandbox:

```bash
gitwarp create --branch feature/my-task \
  --purpose "Implement isolated task" \
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
