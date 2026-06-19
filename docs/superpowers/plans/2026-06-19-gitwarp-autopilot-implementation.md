# GitWarp Autopilot Implementation Plan

> Status: Historical record. Superseded by `2026-06-20-gitwarp-ddd-architecture.md` and the repository README. Do not follow old `plugins/gitwarp` mirror instructions.

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitWarp feel automatic for Codex/Claude agents by adding an `enter` command, stronger board views, and startup hook context injection.

**Architecture:** Extend the existing stdlib Python CLI in `skills/gitwarp/scripts/gitwarp.py`. Keep JSON as the default automation contract, add prompt/table formats only behind explicit `--format`, and update hooks to call the installed CLI for current context.

**Tech Stack:** Python stdlib, Git CLI, unittest, shell hooks, Codex skill/plugin packaging.

---

## Chunk 1: Agent Entry Command

### Task 1: Write failing tests for `enter`

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add a test where `enter --cwd <main-repo>` returns JSON with `location: "main"`, `statusline`, and a recommended next command containing `gitwarp start`.
- [ ] Add a test where `enter --cwd <nested-worktree-dir>` returns JSON with `location: "worktree"`, dossier paths, latest progress/lesson, and file snippets from `task.md`, `progress.md`, and `lessons.md`.
- [ ] Add a prompt-format test where `enter --format prompt` emits readable text containing branch, task file, progress file, lessons file, and latest progress.
- [ ] Run unittest and confirm failure because `enter` is missing.

### Task 2: Implement `enter`

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add helpers to read short Markdown snippets safely.
- [ ] Add `build_enter_payload(ctx, cwd)` that reuses `context`/worktree lookup.
- [ ] Add `cmd_enter` with `--format json|prompt`, default `json`.
- [ ] Keep main checkout behavior non-destructive: recommend `start`, do not create worktrees automatically.
- [ ] Run unittest and confirm Chunk 1 passes.

## Chunk 2: Board Polishing

### Task 3: Write failing tests for board filters and verbose rows

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Create two dossier-backed worktrees with different statuses.
- [ ] Assert `board --status testing` returns only matching rows.
- [ ] Assert `board --stale 0` returns stale rows with `stale: true`.
- [ ] Assert `board --verbose` includes task/progress/lessons snippets.
- [ ] Assert table output still includes branch and latest progress.
- [ ] Run unittest and confirm failure.

### Task 4: Implement board filters

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add age/stale calculation from `updated_at` or `created_at`.
- [ ] Add `--status`, `--stale HOURS`, and `--verbose` to `board`.
- [ ] Include `stale`, `age_seconds`, and snippets when requested.
- [ ] Keep default board JSON compact and backward-compatible.
- [ ] Run unittest and confirm Chunk 2 passes.

## Chunk 3: Startup Hook And Docs

### Task 5: Update hooks and smoke checks

**Files:**
- Modify: `hooks/session-start`
- Modify: `hooks/session-start-codex`
- Modify: `scripts/verify-install.sh`
- Sync: `plugins/gitwarp/hooks/*`

- [ ] Change hook context to mention `start`, `enter`, `handoff`, `board`, and `finish`.
- [ ] Make hooks run `gitwarp enter --cwd "$PWD" --format prompt` when available and inject that into additional context.
- [ ] Keep hook failure non-blocking.
- [ ] Extend smoke checks to call `enter --format prompt`, `board --status`, and `board --verbose`.

### Task 6: Update skill and repo docs

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`
- Sync: `plugins/gitwarp/skills/gitwarp/*`

- [ ] Make `enter --cwd "$PWD"` the first command in recommended agent workflow.
- [ ] Document board filters and hook behavior.
- [ ] Clarify what is automatic in Codex: skill discovery and hook context yes, worktree creation no.

### Task 7: Final verification and integration

**Files:**
- All modified code, tests, docs, hooks, and mirrored plugin files.

- [ ] Run shell syntax checks.
- [ ] Run Python compile.
- [ ] Run unittest discovery.
- [ ] Run skill validator and plugin validator.
- [ ] Run install script from main after merge.
- [ ] Run smoke script and fresh Codex plugin availability check.
- [ ] Finish the GitWarp worktree and merge back into main.
