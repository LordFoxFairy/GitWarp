# GitWarp Init Doctor Onboarding Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe first-run `gitwarp init` command and strengthen `doctor` into a read-only onboarding diagnostic with concrete setup guidance.

**Architecture:** Keep the implementation inside the existing standard-library CLI module. Add small helper functions for ledger validation, ignore-rule management, runtime source-checkout detection, and doctor recommendations, then expose them through `cmd_init` and a refactored `cmd_doctor`. Existing mutating commands remain backward-compatible and do not require explicit init.

**Tech Stack:** Python standard library, Git CLI, unittest, Bash smoke script, Markdown skill/plugin documentation.

---

## File Structure

- Modify `skills/gitwarp/scripts/gitwarp.py`: add init command, ledger validation helpers, ignore helpers, source-checkout detection, reusable doctor checks, parser wiring.
- Modify `tests/test_gitwarp.py`: add TDD coverage for init, invalid ledger variants, doctor guidance, non-executing hook diagnostics, and write-gitignore promotion.
- Modify `scripts/verify-install.sh`: exercise `gitwarp init` in the real smoke flow and assert new doctor codes.
- Modify `README.md`: update quick start to install, init, doctor, then dispatch.
- Modify `skills/gitwarp/SKILL.md`: add init guidance and clarify that agents recommend init when setup is missing.
- Modify `skills/gitwarp/references/install.md`: document `.git/info/exclude` default and `--write-gitignore` team mode.
- Modify `hooks/session-start` and `hooks/session-start-codex`: update context text to mention `gitwarp init` without running it.
- Mirror canonical files into `plugins/gitwarp/...` after behavior/docs changes.

## Chunk 1: Init Tests And Implementation

### Task 1: Write failing init lifecycle tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_init_bootstraps_runtime_state_and_is_idempotent`.

Test shape:

```python
def test_init_bootstraps_runtime_state_and_is_idempotent(self) -> None:
    init = run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
    self.assertTrue((self.repo / ".gitwarp" / "ledger.json").exists())
    self.assertTrue((self.repo / ".gitwarp" / "worktrees").is_dir())
    self.assertTrue((self.repo / ".gitwarp" / "dossiers").is_dir())
    self.assertEqual(init["ignore_target"], str(self.repo / ".git" / "info" / "exclude"))
    self.assertTrue(init["created"]["ledger"])
    self.assertTrue(init["updated"]["ignore_rule"])
    self.assertIn("/.gitwarp/", (self.repo / ".git" / "info" / "exclude").read_text(encoding="utf-8"))

    first_ledger = (self.repo / ".gitwarp" / "ledger.json").read_bytes()
    second = run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
    second_ledger = (self.repo / ".gitwarp" / "ledger.json").read_bytes()
    self.assertEqual(first_ledger, second_ledger)
    self.assertFalse(second["created"]["ledger"])
    self.assertFalse(second["updated"]["ignore_rule"])
```

- [ ] Add `test_init_preserves_existing_ledger_entries`.

Seed `.gitwarp/ledger.json` with an entry plus an unknown top-level field, run init, assert entry and unknown field remain.

- [ ] Run targeted test and verify failure.

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: fails because `init` subcommand does not exist.

### Task 2: Implement init helpers and command

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`

- [ ] Add `RepoContext.git_info_exclude_path` property returning `ctx.common_dir / "info" / "exclude"`.
- [ ] Add `RepoContext.gitignore_path` property returning `ctx.repo_root / ".gitignore"`.
- [ ] Add `default_ledger(ctx)` returning `{"version": 1, "repo_root": str(ctx.repo_root), "entries": []}`.
- [ ] Add `normalize_ledger_schema(data, ctx)`:
  - Require root dict.
  - Require `entries` list.
  - Allow missing `version`; reject present non-integer or non-`1`.
  - Allow missing/string `repo_root`; reject present non-string.
  - Preserve unknown fields.
  - Normalize `version` and `repo_root`.
- [ ] Update `load_ledger` to call `normalize_ledger_schema` instead of only checking `entries`.
- [ ] Add ignore helpers:
  - `ignore_target_for_init(ctx, write_gitignore)`.
  - `git_ignores_gitwarp(ctx)` using `git check-ignore -q .gitwarp/` and fallback `.gitwarp` so directory-style rules such as `/.gitwarp/` are detected before the directory exists.
  - `target_contains_gitwarp_rule(path)`.
  - `append_gitwarp_ignore_rule(path)`.
- [ ] Add `preflight_init(ctx, write_gitignore)` returning selected ignore target and needed writes or raising `GitWarpError`.
- [ ] Add `cmd_init(args)`:
  - Discover repo.
  - Preflight.
  - Create dirs.
  - Create or normalize ledger via atomic `write_ledger`.
  - Append ignore rule when needed.
  - Emit JSON with `created`, `updated`, `ignore_target`, paths, and `recommended_next`.
- [ ] Wire parser:

```python
init = subparsers.add_parser("init", help="Initialize GitWarp runtime state for this repository")
init.add_argument("--cwd")
init.add_argument("--write-gitignore", action="store_true")
init.set_defaults(func=cmd_init)
```

- [ ] Run targeted tests and verify pass.

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

- [ ] Commit.

```bash
git add tests/test_gitwarp.py skills/gitwarp/scripts/gitwarp.py
git commit -m "feat: add gitwarp init"
```

## Chunk 2: Init Edge Cases

### Task 3: Add failing edge-case tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_init_refuses_invalid_existing_state`.
  - Subtests for `.gitwarp` as file, `.gitwarp/worktrees` as file, `.gitwarp/dossiers` as file.
  - Assert `expect_ok=False`, path-specific error, no ledger overwrite.

- [ ] Add table-driven invalid ledger variants:

```python
cases = [
    "[]",
    {"version": 1},
    {"version": 1, "entries": {}},
    {"version": "1", "entries": []},
    {"version": 2, "entries": []},
    {"version": None, "entries": []},
    {"version": 1, "repo_root": [], "entries": []},
]
```

Write each to `.gitwarp/ledger.json`, run init with `expect_ok=False`, assert error mentions ledger.

- [ ] Add `test_init_write_gitignore_and_deduplicates_ignore_rules`.
  - Run default init and assert exclude updated.
  - Run default init again and assert no duplicate.
  - In a fresh repo with `.gitignore` already containing `/.gitwarp/`, run default init and assert exclude not changed.
  - In a fresh repo with exclude containing `/.gitwarp/`, run `init --write-gitignore` and assert `.gitignore` gets one `/.gitwarp/`.
  - Run `--write-gitignore` again and assert no duplicate.

- [ ] Add `test_init_reports_ignore_target_write_failure`.
  - Create `.gitignore` as a directory.
  - Run `gitwarp init --write-gitignore` with `expect_ok=False`.
  - Assert error mentions `.gitignore`.

- [ ] Run tests and verify failures if implementation is incomplete.

### Task 4: Finish init edge behavior

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`

- [ ] Ensure preflight checks selected ignore target directory collision before any writes.
- [ ] Ensure default mode skips writing exclude when Git already ignores `.gitwarp` from `.gitignore`.
- [ ] Ensure team mode checks `.gitignore` specifically and promotes from exclude to gitignore when needed.
- [ ] Ensure init output has deterministic booleans in both `created` and `updated`.
- [ ] Run full unittest.

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

- [ ] Commit.

```bash
git add tests/test_gitwarp.py skills/gitwarp/scripts/gitwarp.py
git commit -m "test: cover gitwarp init edge cases"
```

## Chunk 3: Safe Doctor Refactor

### Task 5: Add failing doctor tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_doctor_reports_setup_guidance_without_mutation`.
  - On a fresh repo before init, run doctor.
  - Assert `ok` true, exit 0, `gitwarp_initialized`, `ledger_schema`, `gitwarp_ignored`, `agent_config`.
  - Assert `recommended_next` contains `gitwarp init --cwd`.
  - Assert no `.gitwarp/ledger.json` was created.
  - Run init, snapshot ledger bytes, run doctor again, assert bytes unchanged.

- [ ] Add `test_doctor_reports_invalid_ledger_error`.
  - Write malformed ledger.
  - Run doctor.
  - Assert `ok` true, `ledger_schema` error, process exit 0.

- [ ] Add `test_doctor_does_not_execute_repo_hook`.
  - Create a fake source-checkout-like temporary repo or use this repo's hook path pattern in temp repo.
  - Write executable `hooks/session-start-codex` that would create marker if executed and contains no required static text.
  - Run doctor.
  - Assert marker does not exist.
  - Assert `session_hook_context` is warning only when source-checkout predicate is true.

- [ ] Add `test_doctor_reports_agent_config_for_absent_valid_and_invalid_config`.
  - Fresh repo before `.gitwarp/agents.json`: doctor emits one `agent_config` finding with severity `ok`.
  - After valid config: doctor emits one `agent_config` finding with severity `ok` and still emits `agent_binary` rows.
  - After malformed config: doctor emits one `agent_config` finding with severity `error`, `ok:true`, exit 0, and `recommended_next` mentions `.gitwarp/agents.json`.

- [ ] Add `test_doctor_source_checkout_checks_are_scoped`.
  - In ordinary temporary repos, assert `standard_skill_links` and `session_hook_context` are absent.
  - In the GitWarp source checkout, assert both codes are present.
  - For a fake source checkout with a static hook that lacks `gitwarp enter --cwd`, assert `session_hook_context` warning and no hook marker file is created.

- [ ] Run tests and verify failures.

### Task 6: Refactor doctor into read-only checks

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`

- [ ] Add `is_gitwarp_source_checkout(ctx)`:
  - True only when `skills/gitwarp/SKILL.md`, `skills/gitwarp/scripts/gitwarp.py`, `.codex-plugin/plugin.json`, and `.agents/plugins/api_marketplace.json` exist.
- [ ] Add `runtime_state_check(ctx)`.
- [ ] Add `ledger_schema_check(ctx)` that catches JSON/schema errors without raising from `doctor`.
- [ ] Add `gitwarp_ignored_check(ctx)`.
- [ ] Add `standard_skill_links_check(ctx)` for source checkouts only.
- [ ] Add `agent_config_check(ctx)` always emitting one finding.
- [ ] Keep `agent_binary` findings for registry agents when registry is valid.
- [ ] Replace hook execution with static `session_hook_context` inspection for source checkouts only.
- [ ] Add `recommended_next_for_findings(ctx, findings)`.
- [ ] Keep `doctor` exit 0 / `ok:true` for diagnostic findings.
- [ ] Doctor finding JSON shape must remain:

```json
{"code":"agent_config","severity":"ok","message":"Agent config is valid or absent.","details":{"path":"/abs/repo/.gitwarp/agents.json","configured":false}}
```

Use `details` for paths, commands, booleans, and remediation context; do not add top-level per-finding fields besides `code`, `severity`, `message`, and `details`.

- [ ] Run full unittest.

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

- [ ] Commit.

```bash
git add tests/test_gitwarp.py skills/gitwarp/scripts/gitwarp.py
git commit -m "feat: make gitwarp doctor setup-aware"
```

## Chunk 4: Docs, Hooks, Smoke, Mirror

### Task 7: Update docs and hooks

**Files:**
- Modify: `README.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`
- Modify: `hooks/session-start`
- Modify: `hooks/session-start-codex`
- Modify: `.codex-plugin/plugin.json` if interface text needs init wording

- [ ] Red step: run existing structure/syntax checks before edits to establish baseline.

```bash
bash -n scripts/verify-install.sh hooks/session-start hooks/session-start-codex scripts/install-codex-plugin.sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] README install quick start becomes:

```bash
scripts/install-codex-plugin.sh
gitwarp init --cwd "$PWD"
gitwarp doctor --cwd "$PWD"
```

- [ ] README runtime model explains default `.git/info/exclude` ignore mode and `--write-gitignore`.
- [ ] SKILL.md command contract includes `init`.
- [ ] SKILL.md standard workflow says run/recommend `gitwarp init` when doctor reports missing runtime.
- [ ] Install reference documents local vs team ignore modes.
- [ ] Hooks mention `gitwarp init` as user action but do not run it.

### Task 8: Update install smoke

**Files:**
- Modify: `scripts/verify-install.sh`

- [ ] After temp repo commit, run `gitwarp init --cwd "$tmpdir"`.
- [ ] Assert:
  - `ok` true.
  - `ledger_path`, `worktree_root`, `dossier_root`.
  - `created.ledger` true.
  - `updated.ignore_rule` true on first run.
  - `recommended_next` includes `gitwarp doctor`.
  - second init has `created.ledger` false and `updated.ignore_rule` false.
- [ ] Remove manual `mkdir -p "$tmpdir/.gitwarp"` before writing agents config if init already created it.
- [ ] Update expected doctor codes to include `gitwarp_initialized`, `ledger_schema`, `agent_config`.
- [ ] Assert doctor before init in a throwaway repo includes `recommended_next` with `gitwarp init`.
- [ ] Assert doctor after init has `gitwarp_initialized` and `ledger_schema` findings with severity `ok`.
- [ ] Update final smoke label to include `init`.

### Task 9: Mirror package and validate

**Files:**
- Modify: `plugins/gitwarp/...`

- [ ] Sync canonical skill and scripts into plugin mirror:

```bash
cp .codex-plugin/plugin.json plugins/gitwarp/.codex-plugin/plugin.json
cp .claude-plugin/plugin.json plugins/gitwarp/.claude-plugin/plugin.json
cp .claude-plugin/marketplace.json plugins/gitwarp/.claude-plugin/marketplace.json
cp hooks/hooks.json plugins/gitwarp/hooks/hooks.json
cp hooks/hooks-codex.json plugins/gitwarp/hooks/hooks-codex.json
cp hooks/run-hook.cmd plugins/gitwarp/hooks/run-hook.cmd
cp hooks/session-start plugins/gitwarp/hooks/session-start
cp hooks/session-start-codex plugins/gitwarp/hooks/session-start-codex
cp skills/gitwarp/SKILL.md plugins/gitwarp/skills/gitwarp/SKILL.md
cp skills/gitwarp/agents/openai.yaml plugins/gitwarp/skills/gitwarp/agents/openai.yaml
cp skills/gitwarp/references/install.md plugins/gitwarp/skills/gitwarp/references/install.md
cp skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
cp skills/gitwarp/scripts/install_cli.py plugins/gitwarp/skills/gitwarp/scripts/install_cli.py
```

- [ ] Run validation:

```bash
bash -n scripts/verify-install.sh hooks/session-start hooks/session-start-codex scripts/install-codex-plugin.sh
python3 -m py_compile skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/verify-install.sh
git diff --check
```

- [ ] Commit.

```bash
git add README.md .codex-plugin/plugin.json hooks/session-start hooks/session-start-codex scripts/verify-install.sh skills/gitwarp plugins/gitwarp
git commit -m "docs: document gitwarp init onboarding"
```

## Maintainer Release Checklist

This section is for the lead maintainer after implementation is complete and explicitly authorized for release. Generic workers should stop after passing verification and hand off.

- [ ] Install plugin from this worktree if needed:

```bash
scripts/install-codex-plugin.sh
```

- [ ] Run full validation again.
- [ ] Merge feature branch into main with `git merge --ff-only feature/gitwarp-init-doctor-onboarding`.
- [ ] Reinstall plugin from main.
- [ ] Run full validation from main.
- [ ] Push main to origin.
- [ ] Finish and collapse GitWarp worktree:

```bash
gitwarp finish --cwd /Users/nako/WebstormProjects/github/thefoxfairy/GitWarp/.gitwarp/worktrees/feature-gitwarp-init-doctor-onboarding \
  --status pushed \
  --progress "Implemented init/doctor onboarding, verified, merged, and pushed." \
  --collapse
```
