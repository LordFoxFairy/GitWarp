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
| `gitwarp create` | Create a dossier-backed isolated worktree. |
| `gitwarp switch` | Locate an existing worktree and print its absolute path or `cd` command. |
| `gitwarp remove` | Remove a sandbox when it is no longer needed; add `--force` only for dirty targets. |
| `gitwarp handoff` | Record progress and optional lessons during work. |
| `gitwarp statusline` | Print a raw prompt banner such as `GITWARP[main-repo]`. |
| `gitwarp enter` | Return hook/session context and dossier snippets; not the main workflow command. |
| `gitwarp board` | List active sandboxes. |
| `gitwarp reconcile` | Read-only audit for dirty, stale, missing, merged, or drifted worktrees. |
| `gitwarp doctor` | Check install, hook, plugin, and runtime health. |
| `gitwarp web` | Open a local Web Console with Code, Metadata, and Health tabs. |

`start`, `summon`, `collapse`, and `dispatch` remain lower-level commands. Prefer `create`, `switch`, and `remove` unless you specifically need a rendered launch command from `dispatch`.

The Web Console is for human supervision: the Code tab browses tracked files at the selected worktree `HEAD`, the Metadata tab shows dossiers and agent actions, and the Health tab shows doctor/reconcile findings.

## Agent Workflow

From any repository path:

```bash
gitwarp init
gitwarp statusline
gitwarp enter
```

If work requires edits and you are in the main checkout:

```bash
gitwarp create --branch feature/my-task \
  --purpose "Implement isolated task"
```

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

When verified and pushed:

```bash
gitwarp finish --status pushed \
  --progress "Verified and pushed" \
  --collapse
```

Use `gitwarp remove` inside a sandbox only when it should be destroyed without a final handoff. From the main checkout, target one explicitly with `gitwarp remove --branch <branch>`. If the target has uncommitted or untracked files, `remove` refuses to proceed until you rerun with `--force`.

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
