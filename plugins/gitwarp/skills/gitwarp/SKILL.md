---
name: gitwarp
description: Use when concurrent Claude Code or Codex agents need isolated git worktrees, when branch collisions or index contamination must be avoided, or when an agent must scan, summon, collapse, or label temporary workspaces with persistent metadata.
---

# GitWarp

## Overview

GitWarp provides a deterministic helper around native `git worktree` so agents can claim, track, and destroy isolated sandboxes without reusing a branch or contaminating the main checkout index. It stores runtime state in the target repository under `.gitwarp/ledger.json`.

## Core Rule

When a task requires isolated concurrent writes, do not run `git switch`, `git checkout`, or direct `git worktree add` in the main repository. Use GitWarp to scan, summon, label, and collapse the workspace so branch ownership stays machine-readable.

## When To Use

Use this skill when any of the following are true:

1. Two or more agents will write to the same repository concurrently.
2. You need a dedicated workspace for a feature branch and must not check it out in the main repo.
3. You need a machine-readable inventory of active worktrees plus ownership metadata such as agent id and task purpose.
4. You need a prompt statusline banner that tells a model whether it is in the main repo or an isolated sandbox.

Do not use this skill for single-agent edits in the main checkout when no branch isolation is needed.

## Command Contract

1. `scan`, `summon`, and `collapse` emit deterministic single-line JSON.
2. `statusline` emits a raw unquoted prompt banner only.
3. All `--cwd`, returned workspace paths, ledger paths, and worktree roots must be treated as absolute paths.
4. If any JSON command returns nonzero or `"ok": false`, stop the workflow, report the `error` field, and do not keep editing from an assumed workspace.
5. Never edit `.gitwarp/ledger.json` by hand.

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

### 2. Scan before allocating or editing

Run:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/gitwarp.py scan --cwd /absolute/path/to/repo
```

Or with the installed CLI:

```bash
gitwarp scan --cwd /absolute/path/to/repo
```

This returns the repo root, ledger path, and live worktrees enriched with any tracked `agent_id` and `purpose`.

If the current process might already be inside a sandbox, also run:

```bash
gitwarp statusline --cwd "$PWD"
```

Continue in place only when the banner matches the intended agent and branch.

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
4. Do not edit in the public root after a sandbox has been summoned for the task.

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

## Failure Handling

- Branch collision: abort and ask for a different branch or collapse the existing workspace only with explicit user approval.
- Missing Git repository: run from a real repository or pass `--cwd /absolute/path/to/repo`.
- Invalid ledger: stop and report the ledger path; do not rewrite it manually unless the user asks for repair.
- Collapse target missing: run `scan`, verify the branch/path, then retry with the exact live path or branch.

## Expectations

1. Never reuse a branch name already attached to a live worktree.
2. Always prefer helper output over assumptions about where a worktree lives.
3. Prefer `gitwarp ...` commands over direct Python script paths once the CLI is installed.
4. Keep the helper script deterministic and machine-readable.
