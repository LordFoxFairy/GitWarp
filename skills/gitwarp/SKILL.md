---
name: gitwarp
description: Use when concurrent Claude Code or Codex agents need isolated git worktrees, branch collision prevention, workspace context, task dossiers, prompt statusline banners, or persistent handoff records.
---

# GitWarp

## Overview

GitWarp is the worktree isolation protocol for coding agents. It wraps native `git worktree`, stores ownership metadata in `.gitwarp/ledger.json`, and creates `task.md`, `progress.md`, and `lessons.md` dossiers for each isolated branch.

## Core Rules

1. Run `gitwarp init --cwd "$PWD"` once per target repository when GitWarp runtime state is missing or `doctor` recommends it.
2. Run `gitwarp enter --cwd "$PWD"` before repository work unless a session hook already provided GitWarp Context.
3. For concurrent or isolated writes, do not run `git switch`, `git checkout`, or direct `git worktree add` in the main checkout.
4. Use only absolute paths returned by GitWarp. The default sandbox root is `<repo>/.gitwarp/worktrees/`.
5. Read `task.md`, `progress.md`, and `lessons.md` before editing inside a sandbox.
6. Record milestones with `gitwarp handoff` so later agents can recover context.
7. Never edit `.gitwarp/ledger.json` or `.gitwarp/agents.json` by hand while GitWarp commands may be running.

## Command Contract

| Command | Use |
| --- | --- |
| `init` | Create `.gitwarp/`, runtime subdirectories, ledger, and ignore rule safely. |
| `enter` | Get current main/worktree context and dossier pointers. JSON by default; `--format prompt` for hooks. |
| `dispatch` | Create a dossier-backed worktree and print a ready-to-run agent launch command. |
| `start` | Create a dossier-backed worktree for manual coordination. |
| `adopt` | Bind an existing non-main, non-detached worktree into the ledger. |
| `handoff` | Append progress and optional lessons to the dossier and ledger. |
| `board` | List active worktrees; use `--format table` for humans. |
| `reconcile` | Non-mutating audit for stale ledger rows, dirty worktrees, missing dossiers, and merged branches. |
| `doctor` | Check local GitWarp, plugin, hook, ignored runtime state, and agent launch readiness. |
| `finish` | Record final progress and optionally collapse the worktree. |
| `statusline` | Print only a raw banner such as `GITWARP[main-repo]`. |

All automation commands emit deterministic single-line JSON except `statusline`, `enter --format prompt`, and `board --format table`. If any JSON command returns nonzero or `"ok": false`, stop and report the `error` field.

## Standard Workflow

From any repository path:

```bash
gitwarp init --cwd "$PWD"
gitwarp doctor --cwd "$PWD"
gitwarp enter --cwd "$PWD"
```

If `doctor` reports missing runtime state, run or recommend `gitwarp init --cwd "$PWD"` before starting new isolated work. By default it writes `/.gitwarp/` to `.git/info/exclude`; use `--write-gitignore` only when the project wants a committed team ignore rule.

If `location` is `main` and isolated work is needed, prefer dispatch:

```bash
gitwarp dispatch --cwd /absolute/path/to/repo \
  --agent codex \
  --branch feature/my-task \
  --purpose "Implement isolated task"
```

Run the returned `launch_command` yourself. `dispatch --command-mode execute` is intentionally unsupported and fails before creating anything.

Inside the returned worktree:

```bash
gitwarp enter --cwd "$PWD"
gitwarp handoff --cwd "$PWD" --status implementing --progress "Short milestone"
gitwarp statusline --cwd "$PWD"
```

When verified:

```bash
gitwarp finish --cwd "$PWD" \
  --status pushed \
  --progress "Verified and pushed" \
  --collapse
```

## Coordination Commands

Use these from the main checkout before spawning more agents or cleaning up old work:

```bash
gitwarp board --cwd /absolute/path/to/repo --format table
gitwarp reconcile --cwd /absolute/path/to/repo --stale 4
gitwarp doctor --cwd /absolute/path/to/repo
gitwarp agents --cwd /absolute/path/to/repo
```

Agent launch templates come from built-ins plus optional `.gitwarp/agents.json`. Template variables include `{repo}`, `{worktree}`, `{branch}`, `{agent_id}`, `{purpose}`, `{task_md}`, `{progress_md}`, `{lessons_md}`, and `{prompt}`.

## Existing Worktrees

If a worktree already exists, adopt it instead of recreating it:

```bash
gitwarp adopt --cwd /absolute/path/to/repo \
  --path /absolute/path/to/existing-worktree \
  --agent-id claude-existing \
  --purpose "Continue existing sandbox"
```

GitWarp refuses main and detached worktrees.

## Resources

- CLI script: `scripts/gitwarp.py`
- CLI installer: `scripts/install_cli.py`
- Install and distribution notes: read `references/install.md` when installing, packaging, or troubleshooting host discovery.

Use `gitwarp` from `PATH` when installed. If it is unavailable, run the bundled script with `python3 /absolute/path/to/skills/gitwarp/scripts/gitwarp.py`.

## Common Failures

- Branch collision: choose a different branch or explicitly collapse the existing worktree.
- Main checkout handoff refused: start, dispatch, or adopt a non-main worktree first.
- Missing dossier: run `adopt` for existing worktrees or `reconcile` to audit.
- Stale prompt context: rerun `gitwarp enter --cwd "$PWD"` and trust the returned statusline.
