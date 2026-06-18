---
name: gitwarp
description: Use when concurrent Claude Code or Codex agents need isolated git worktrees, when branch collisions or index contamination must be avoided, or when an agent must scan, summon, collapse, or label temporary workspaces with persistent metadata.
---

# GitWarp

## Overview

GitWarp provides a deterministic helper around native `git worktree` so agents can claim, track, and destroy isolated sandboxes without reusing a branch or contaminating the main checkout index. It stores runtime state in the target repository under `.gitwarp/ledger.json`.

## When To Use

Use this skill when any of the following are true:

1. Two or more agents will write to the same repository concurrently.
2. You need a dedicated workspace for a feature branch and must not check it out in the main repo.
3. You need a machine-readable inventory of active worktrees plus ownership metadata such as agent id and task purpose.
4. You need a prompt statusline banner that tells a model whether it is in the main repo or an isolated sandbox.

Do not use this skill for single-agent edits in the main checkout when no branch isolation is needed.

## Skill Resources

The helper lives next to this skill:

- Script: `scripts/gitwarp.py`
- CLI installer: `scripts/install_cli.py`
- Install notes: `references/install.md`

In Claude Code, you can reference the script with `${CLAUDE_SKILL_DIR}/scripts/gitwarp.py`.
In Codex, resolve `scripts/gitwarp.py` relative to this skill directory before running it.

If the `gitwarp` command is already installed in PATH, prefer that shorter command.

## Language Choice

The helper is Python because this skill needs structured Git parsing, JSON ledger updates, and cross-shell behavior without adding npm, uv, or package manager setup. Agents and users should treat Python as an implementation detail after the CLI is installed.

## Workflow

### 1. Resolve the helper

Use the bundled script, not ad-hoc `git worktree` commands, when workspace ownership matters.

Example:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/gitwarp.py scan
```

All command outputs other than `statusline` are single-line JSON.

To install the CLI command from this skill copy, run:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/install_cli.py
```

After installation, use:

```bash
gitwarp --help
```

### 2. Scan before allocating

Run:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/gitwarp.py scan --cwd /absolute/path/to/repo
```

Or with the installed CLI:

```bash
gitwarp scan --cwd /absolute/path/to/repo
```

This returns the repo root, ledger path, and live worktrees enriched with any tracked `agent_id` and `purpose`.

### 3. Summon an isolated workspace

Run:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/gitwarp.py summon \
  --cwd /absolute/path/to/repo \
  --agent-id codex-reviewer \
  --branch feature/gitwarp-statusline \
  --purpose "Implement prompt banner"
```

Rules:

1. Treat branch collisions as hard failures.
2. `cd` into the returned `path` before editing.
3. Assume the workspace path is absolute and stable for the lifetime of the task.

### 4. Collapse when the task is done

Run:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/gitwarp.py collapse \
  --cwd /absolute/path/to/repo \
  --branch feature/gitwarp-statusline
```

Use this only after verification and push, or when the user explicitly wants the sandbox destroyed.

### 5. Surface context in prompts

Run:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/gitwarp.py statusline --cwd "$PWD"
```

This prints a raw string such as `GITWARP[main-repo]` or `GITWARP[codex-reviewer@feature/gitwarp-statusline]`.

## Expectations

1. Never edit `.gitwarp/ledger.json` by hand.
2. Never reuse a branch name already attached to a live worktree.
3. Always prefer the helper output over assumptions about where a worktree lives.
4. Prefer `gitwarp ...` commands over direct Python script paths once the CLI is installed.
5. Keep the helper script deterministic and machine-readable.
