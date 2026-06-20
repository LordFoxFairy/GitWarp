# GitWarp Dossiers Implementation Plan

> Status: Historical record. Superseded by `2026-06-20-gitwarp-ddd-architecture.md` and the repository README. Do not follow old `plugins/gitwarp` mirror instructions.

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement dossier-backed GitWarp workflows so every managed worktree can expose `task.md`, `progress.md`, and `lessons.md` through high-level agent commands.

**Architecture:** Extend the existing stdlib Python CLI in `skills/gitwarp/scripts/gitwarp.py`. Reuse the ledger as the source of truth, store Markdown dossiers under `.gitwarp/dossiers/<workspace-id>/`, and keep package mirrors synchronized under `plugins/gitwarp/`.

**Tech Stack:** Python stdlib, Git CLI, unittest, shell smoke checks, Codex skill/plugin packaging.

---

## Chunk 1: Start And Dossier Context

### Task 1: Write failing tests for `start` and dossier-aware `context`

**Files:**
- Modify: `tests/test_gitwarp.py`

- [x] Add a test that runs `gitwarp start --agent-id codex-dossier --branch feature/dossier --purpose "Build dossier workflow"`.
- [x] Assert the returned JSON includes `path`, `dossier_path`, `task_md`, `progress_md`, and `lessons_md`.
- [x] Assert all three Markdown files exist under `.gitwarp/dossiers/`.
- [x] Assert `context --cwd <nested-worktree-dir>` returns the same dossier paths.
- [x] Run `python3 -m unittest discover -s tests -p 'test_*.py' -v` and confirm failure because `start` is missing.

### Task 2: Implement minimal dossier creation

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [x] Add constants for `DOSSIER_DIRNAME`, `TASK_FILENAME`, `PROGRESS_FILENAME`, and `LESSONS_FILENAME`.
- [x] Add helper functions to build deterministic workspace IDs and dossier paths.
- [x] Add helper to create Markdown templates atomically enough for this CLI.
- [x] Add `cmd_start` that uses the same collision and worktree creation logic as `cmd_summon`, then creates dossier files and ledger fields.
- [x] Extend ledger enrichment so `scan` and `context` include dossier paths.
- [x] Run tests and confirm Chunk 1 passes.

## Chunk 2: Handoff, Board, And Finish

### Task 3: Write failing tests for workflow commands

**Files:**
- Modify: `tests/test_gitwarp.py`

- [x] After `start`, run `handoff --status testing --progress "Parser done" --lesson "Use context before edits"`.
- [x] Assert `progress.md`, `lessons.md`, and ledger status are updated.
- [x] Assert `board --format json` includes branch, agent, status, purpose, latest progress, latest lesson, and dossier paths.
- [x] Historical implementation used `finish --status pushed --progress "Verified and pushed" --lesson "Keep dossier after collapse" --collapse`.
- [x] Superseded lifecycle rule: `remove`, `collapse`, and `finish --collapse` now remove the matching dossier directory with the worktree and ledger row while preserving the Git branch.
- [x] Run unittest and confirm failure because `handoff`, `board`, and `finish` are missing.

### Task 4: Implement workflow commands

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [x] Add append helpers for progress and lessons.
- [x] Add latest-entry extraction helpers for board summaries.
- [x] Add `cmd_handoff` that refuses main repo, repairs missing dossier files when safe, appends Markdown, and updates ledger.
- [x] Add `cmd_board` with default JSON output and `--format table` human output.
- [x] Add `cmd_finish` that calls handoff behavior and only collapses when `--collapse` is passed; collapse now purges the matching active-sandbox dossier.
- [x] Run tests and confirm Chunk 2 passes.

## Chunk 3: Documentation, Smoke Checks, And Packaging

### Task 5: Update user-facing docs and smoke checks

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`
- Modify: `scripts/verify-install.sh`
- Sync: `plugins/gitwarp/skills/gitwarp/*`

- [x] Document `start`, `board`, `handoff`, and `finish` as recommended commands.
- [x] Keep low-level command docs concise and available.
- [x] Update install smoke script to use `start -> context -> handoff -> board -> finish --collapse`.
- [x] Run `bash -n scripts/verify-install.sh`.
- [x] Run skill validator, plugin validator, unittest discovery, install script, smoke script, and fresh Codex plugin availability check.

### Task 6: Commit and integrate

**Files:**
- All modified implementation, test, docs, and mirrored plugin files.

- [x] Commit the feature branch with `feat: add gitwarp dossier workflows`.
- [x] Merge back into `main` with a non-destructive fast-forward or normal merge after verification.
- [x] Collapse the implementation worktree only after the merged state is verified.
