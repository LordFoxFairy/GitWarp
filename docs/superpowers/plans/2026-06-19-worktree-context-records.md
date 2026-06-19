# Worktree Context Records Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitWarp answer "which worktree am I in and what has this agent done here?" with machine-readable records.

**Architecture:** Extend the existing stdlib Python CLI without changing the ledger location. Add `context` for current-directory lookup and `annotate` for appending progress notes to a tracked worktree entry.

**Tech Stack:** Python stdlib, Git CLI, unittest, Codex skill/plugin packaging.

---

## Chunk 1: Context And Notes

### Task 1: Failing Tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [x] Add tests that summon a worktree, call `annotate`, then assert `context --cwd <worktree>` returns branch, agent, purpose, status, and notes.
- [x] Add a main-repo context assertion so agents can distinguish root checkout from isolated sandboxes.
- [x] Run `python3 -m unittest discover -s tests -p 'test_*.py' -v` and confirm the new tests fail because commands are missing.

### Task 2: Minimal CLI Implementation

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [x] Add helper lookup for matching CWD to live worktree plus ledger metadata.
- [x] Add `context --cwd <path>` with single-line JSON output.
- [x] Add `annotate --cwd/--path/--branch --status <value> --note <text>` with single-line JSON output.
- [x] Preserve existing `scan`, `summon`, `collapse`, and `statusline` behavior.

### Task 3: Documentation And Verification

**Files:**
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`
- Modify: `README.md`
- Modify: `scripts/verify-install.sh`
- Sync: `plugins/gitwarp/skills/gitwarp/*`

- [x] Document `context` and `annotate` as the agent memory layer.
- [x] Extend smoke verification to annotate a temp worktree and read it back with `context`.
- [x] Run skill validation, plugin validation, unittest discovery, install smoke check, and a fresh Codex plugin availability check.
- [x] Commit after verification.
