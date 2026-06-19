# GitWarp Agent Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe GitWarp orchestration layer that prepares Codex/Claude/custom agent worktrees, audits active work, and keeps ledger updates safe under parallel agent usage.

**Architecture:** Keep the existing single-file Python CLI for this iteration, but introduce focused helpers inside `skills/gitwarp/scripts/gitwarp.py` for ledger locking, agent config parsing, prompt rendering, dispatch, adoption, reconciliation, and doctor checks. Mirror all canonical skill/plugin files into `plugins/gitwarp/` after each behavior change.

**Tech Stack:** Python standard library, Git CLI, `unittest`, shell smoke tests, Codex plugin packaging.

---

## File Structure

- Modify `skills/gitwarp/scripts/gitwarp.py`: core implementation for locking, config, dispatch, adopt, reconcile, doctor, and parser commands.
- Modify `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`: exact mirror of the canonical CLI.
- Modify `tests/test_gitwarp.py`: regression coverage for new orchestration behavior, concurrency, and mirror checks.
- Modify `skills/gitwarp/SKILL.md`: document agent orchestration commands and first-version execute-mode boundary.
- Modify `plugins/gitwarp/skills/gitwarp/SKILL.md`: exact mirror of canonical skill docs.
- Modify `README.md`: add orchestration usage examples.
- Modify `AGENTS.md`: update verification expectations.
- Modify `scripts/verify-install.sh`: smoke-test `agents`, `dispatch --command-mode print`, `adopt`, `reconcile`, and `doctor`.
- Modify plugin metadata only if command descriptions or prompts need updates.

## Chunk 1: Ledger Safety Foundation

### Task 1: Write failing tests for concurrent-safe ledger writes

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add imports for `threading`, `time`, and any needed typing helpers.
- [ ] Add `test_parallel_handoffs_do_not_lose_ledger_updates`.
- [ ] In the test, create one worktree with `start`, then run a deterministic stress loop: for 10 rounds, start 8 parallel `handoff` subprocesses against that worktree with unique progress notes.
- [ ] Assert every subprocess exits zero and final `context` contains all unique notes from every round.
- [ ] Assert `.gitwarp/ledger.lock` does not remain after the commands complete.
- [ ] If the stress loop does not reliably fail before the fix, add a temporary test-only environment hook around ledger read/write to synchronize subprocesses at the vulnerable read-modify-write point, then remove or keep it guarded by an internal `GITWARP_TEST_*` variable.
- [ ] Run:

```bash
python3 -m unittest discover -s tests -p test_gitwarp.py -k test_parallel_handoffs_do_not_lose_ledger_updates
```

Expected: fail with lost notes on the current unlocked read-modify-write path.

### Task 2: Implement ledger locking and atomic writes

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add constants `LEDGER_LOCK_FILENAME = "ledger.lock"` and `LOCK_TIMEOUT_SECONDS = 10`.
- [ ] Add `ledger_lock_path(ctx)` or a `RepoContext.ledger_lock_path` property.
- [ ] Add a `ledger_write_lock(ctx, timeout=LOCK_TIMEOUT_SECONDS)` context manager using `os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY)` so lock creation is atomic.
- [ ] Write the current PID and timestamp into the lock file for diagnostics.
- [ ] On timeout, raise `GitWarpError("timed out waiting for ledger lock: <path>")`.
- [ ] Ensure the lock file is removed in `finally`.
- [ ] Change `write_ledger` to write JSON to a unique temp file in `.gitwarp/`, flush and fsync it, then `Path.replace(ctx.ledger_path)`.
- [ ] Add `mutate_ledger(ctx, callback)` helper that acquires the lock, reloads the latest ledger, applies a callback, writes atomically, and returns callback result.
- [ ] Update write commands gradually to use `mutate_ledger`: `sync_ledger(... persist=True)`, `cmd_summon`, `cmd_start`, `cmd_annotate`, `record_handoff` callers, `cmd_finish`, and `cmd_collapse`.
- [ ] Keep `enter` and `statusline` read-only with `persist=False`.
- [ ] Run the new concurrency test until it is stable.
- [ ] Run full tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all tests pass.

### Task 3: Commit ledger safety

**Files:**
- Stage: `tests/test_gitwarp.py`, `skills/gitwarp/scripts/gitwarp.py`, `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Run `git diff --check`.
- [ ] Commit:

```bash
git add tests/test_gitwarp.py skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git commit -m "feat: add safe gitwarp ledger writes"
```

## Chunk 2: Agent Config And Dispatch Print Mode

### Task 4: Write failing tests for `agents` config loading

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_agents_lists_builtin_templates_without_config`.
- [ ] Assert `gitwarp agents --cwd <repo>` returns `ok:true`, `config_path` ending in `.gitwarp/agents.json`, and built-in entries for `codex` and `claude` with `configured:false`.
- [ ] Add `test_agents_loads_json_config_and_validates_templates`.
- [ ] Write `.gitwarp/agents.json` with one custom agent command like `["python3", "-c", "{prompt}", "{worktree}"]`.
- [ ] Assert configured agent is returned with `configured:true`, command array, and `available:true` for `python3`.
- [ ] Add negative cases for malformed JSON, `version != 1`, missing `{worktree}`, missing `{prompt}`, and unknown template variable.
- [ ] Run targeted tests and confirm failure because `agents` does not exist.

### Task 5: Implement agent config helpers and `gitwarp agents`

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add `AGENTS_FILENAME = "agents.json"`.
- [ ] Add built-in templates for `codex` and `claude`; use command arrays, not shell strings.
- [ ] Add `load_agent_config(ctx)` that reads `.gitwarp/agents.json` if present, validates schema, and merges with built-ins.
- [ ] Add `validate_command_template(command)` that requires `{worktree}` and `{prompt}`, rejects unknown `{...}` variables, and requires a non-empty list of strings.
- [ ] Add `command_available(command)` using `shutil.which(command[0])`.
- [ ] Add `cmd_agents` that emits strict JSON with config path, parse status, and agent rows.
- [ ] Add parser command:

```python
agents = subparsers.add_parser("agents", help="List configured agent launch templates")
agents.add_argument("--cwd")
agents.set_defaults(func=cmd_agents)
```

- [ ] Run targeted tests and full unit tests.

### Task 6: Write failing tests for `dispatch --command-mode print`

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_dispatch_print_creates_worktree_and_renders_launch_command`.
- [ ] Use a configured local agent command containing `{worktree}` and `{prompt}`.
- [ ] Run `gitwarp dispatch --agent local --branch feature/dispatch-print --purpose "Implement dispatch print"`.
- [ ] Assert output includes `mode:"print"`, `agent:"local"`, `status:"dispatched"`, absolute `path`, dossier paths, `launch_command`, and `launch_preview`.
- [ ] Assert the launch command contains the exact worktree path and a prompt mentioning `gitwarp enter`, `handoff`, and the purpose.
- [ ] Assert no process side effect occurred beyond worktree/dossier creation.
- [ ] Add `test_dispatch_execute_is_rejected_before_mutation`.
- [ ] Run `dispatch --command-mode execute` and assert `ok:false`, no branch exists, no worktree path exists, and ledger has no entry for the branch.
- [ ] Run targeted tests and confirm failure because `dispatch` does not exist.

### Task 7: Implement `dispatch` print mode

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add `render_agent_prompt(purpose)` with the short assignment prompt from the spec.
- [ ] Add `render_command(command_template, values)` returning a list of rendered args.
- [ ] Add `shell_preview(args)` using `shlex.join`.
- [ ] Add `build_agent_id(agent_name, branch)` that defaults to `<agent>-<sanitized-branch>` unless `--agent-id` is passed.
- [ ] Implement `cmd_dispatch`.
- [ ] If `--agent` is omitted, use `default_agent` from `.gitwarp/agents.json`; if there is no config, use built-in `codex`.
- [ ] Validate mode, agent, config, required template variables, and branch collision before creating a worktree.
- [ ] Reject `--command-mode execute` before any mutation.
- [ ] Reuse the same allocation/dossier behavior as `start`, but store status `dispatched` and a `dispatch` object in the ledger entry.
- [ ] Return strict JSON with all fields from the spec.
- [ ] Add parser command:

```python
dispatch = subparsers.add_parser("dispatch", help="Create a worktree and render an agent launch command")
dispatch.add_argument("--cwd")
dispatch.add_argument("--agent")
dispatch.add_argument("--agent-id")
dispatch.add_argument("--branch", required=True)
dispatch.add_argument("--purpose", required=True)
dispatch.add_argument("--command-mode", choices=["print", "execute"], default="print")
dispatch.set_defaults(func=cmd_dispatch)
```

- [ ] Run targeted dispatch tests and full unit tests.

### Task 8: Commit config and dispatch

**Files:**
- Stage: `tests/test_gitwarp.py`, `skills/gitwarp/scripts/gitwarp.py`, `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Run `git diff --check`.
- [ ] Commit:

```bash
git add tests/test_gitwarp.py skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git commit -m "feat: add gitwarp agent dispatch"
```

## Chunk 3: Adopt, Reconcile, And Doctor

### Task 9: Write failing tests for `adopt`

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_adopt_binds_existing_worktree_and_repairs_dossier`.
- [ ] Create a normal Git worktree manually with `git worktree add`.
- [ ] Run `gitwarp adopt --path <worktree> --agent-id claude-existing --purpose "Continue existing work"`.
- [ ] Assert status `adopted`, branch/head preserved, dossier files created, and `outside_guarded_root` accurately reflects path placement.
- [ ] Add negative tests: refusing main checkout, duplicate branch/path conflict, duplicate agent id conflict, and detached worktree refusal.
- [ ] Run targeted tests and confirm failure because `adopt` does not exist.

### Task 10: Implement `adopt`

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add helpers to find raw ledger entries by path, branch, and agent id.
- [ ] Implement collision rules from the spec.
- [ ] Reuse `ensure_dossier_for_entry` for dossier repair.
- [ ] Update or create one ledger entry with status `adopted`, `updated_at`, purpose, agent id, branch, path, and dossier paths.
- [ ] Return strict JSON including `outside_guarded_root`.
- [ ] Add parser command with `--cwd`, `--path`, `--agent-id`, and `--purpose`; do not add `--branch` because adoption must preserve live Git branch/HEAD.
- [ ] Run targeted adopt tests and full unit tests.

### Task 11: Write failing tests for `reconcile`

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_reconcile_reports_findings_without_mutating_ledger`.
- [ ] Create a ledger entry pointing to a missing path by editing `.gitwarp/ledger.json` directly inside the temp repo.
- [ ] Create a live worktree missing from the ledger.
- [ ] Remove one dossier file from a tracked worktree.
- [ ] Make one worktree dirty by writing an untracked file.
- [ ] Run `gitwarp reconcile --cwd <repo> --stale 0`.
- [ ] Assert findings include `stale_ledger_entry`, `untracked_worktree`, `missing_dossier_file`, `dirty_worktree`, status findings for `blocked`, `dispatch_failed`, and `merged`, and stale status where applicable.
- [ ] Create a branch already merged into `main` and assert reconcile reports `merged_head`.
- [ ] Assert ledger file bytes are unchanged before/after reconcile.
- [ ] Run targeted test and confirm failure because `reconcile` does not exist.

### Task 12: Implement `reconcile`

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add `load_raw_ledger(ctx)` that never prunes or writes.
- [ ] Add `worktree_dirty(path)` using `git status --porcelain`.
- [ ] Add finding builder with fields: `code`, `severity`, `path`, `branch`, `agent_id`, `message`.
- [ ] Compare raw ledger entries against live worktree paths.
- [ ] Compare live non-main worktrees against ledger entries.
- [ ] Check dossier path existence for tracked entries.
- [ ] Check dirty worktrees.
- [ ] Check stale age using `updated_at` or `created_at`.
- [ ] Report canonical attention statuses `blocked`, `dispatch_failed`, and `merged`.
- [ ] Report branches whose worktree HEAD is already merged into main with code `merged_head`.
- [ ] Return JSON with `findings` and `summary` counts by severity/code.
- [ ] Add parser command `reconcile --cwd --stale`.
- [ ] Run targeted reconcile tests and full unit tests.

### Task 13: Write failing tests for `doctor`

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_doctor_reports_environment_without_mutation`.
- [ ] Snapshot `.gitwarp/ledger.json` if present.
- [ ] Run `gitwarp doctor --cwd <repo>`.
- [ ] Assert findings include checks for `git`, `python3`, `.gitwarp_ignored`, and `gitwarp_launcher`.
- [ ] Assert findings include `codex_plugin_metadata` when `codex` is installed or a warning when unavailable.
- [ ] Assert findings include `session_hook_context` and that the hook check can produce a GitWarp Context block when hook files exist.
- [ ] Assert output has severity values only from `ok`, `warning`, and `error`.
- [ ] Assert ledger bytes are unchanged.
- [ ] Run targeted test and confirm failure because `doctor` does not exist.

### Task 14: Implement `doctor`

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Add `doctor_check` helper with `code`, `severity`, `message`, and optional details.
- [ ] Check `git` and `python3` via `shutil.which`.
- [ ] Check `gitwarp` launcher via `shutil.which("gitwarp")`; if present, verify path exists and optionally run `gitwarp --version` with a short timeout.
- [ ] Check `.gitwarp/` ignore state using `git check-ignore -q .gitwarp`.
- [ ] Load agent config and report configured binary availability.
- [ ] If `codex` is installed, inspect Codex plugin metadata through `codex plugin list --json` with a short timeout and report whether `gitwarp@gitwarp-dev` is present/enabled; if `codex` is not installed, report warning, not error.
- [ ] Invoke local hook script when present and executable; require its output to contain `GitWarp Context:` for an `ok` finding, otherwise report warning/error without mutating state.
- [ ] Return strict JSON without mutating state.
- [ ] Add parser command `doctor --cwd`.
- [ ] Run targeted doctor tests and full unit tests.

### Task 15: Commit management audits

**Files:**
- Stage: `tests/test_gitwarp.py`, `skills/gitwarp/scripts/gitwarp.py`, `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Run `git diff --check`.
- [ ] Commit:

```bash
git add tests/test_gitwarp.py skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git commit -m "feat: add gitwarp orchestration audits"
```

## Chunk 4: Docs, Skill, Smoke, And Packaging

### Task 16: Update docs and skill guidance

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/agents/openai.yaml`
- Modify: `skills/gitwarp/references/install.md`
- Sync: matching files under `plugins/gitwarp/`

- [ ] Document `.gitwarp/agents.json` and built-in fallback templates.
- [ ] Document `gitwarp agents`, `dispatch`, `adopt`, `reconcile`, and `doctor`.
- [ ] Explicitly state `dispatch --command-mode execute` is unsupported in this version and fails before mutation.
- [ ] Update AGENTS verification command description to include orchestration smoke coverage.
- [ ] Keep SKILL concise: workflow first, command reference short, defer details to `--help` and README.
- [ ] Sync all mirrored plugin files.

### Task 17: Extend install smoke

**Files:**
- Modify: `scripts/verify-install.sh`

- [ ] After temp repo initialization, run `gitwarp agents --cwd "$tmpdir"` and assert built-in `codex` and `claude` entries exist.
- [ ] Write a local `.gitwarp/agents.json` with a `local` command template using `python3`.
- [ ] Run `gitwarp dispatch --cwd "$tmpdir" --agent local --branch feature/verify-dispatch --purpose "Verify dispatch print"`.
- [ ] Assert JSON contains launch command, prompt text, status `dispatched`, and dossier paths.
- [ ] Run `gitwarp dispatch --command-mode execute` with another branch and assert `ok:false`; assert branch/worktree was not created.
- [ ] Create a manual worktree and run `gitwarp adopt`.
- [ ] Run `gitwarp reconcile --cwd "$tmpdir" --stale 0` and assert `ok:true`.
- [ ] Run `gitwarp doctor --cwd "$tmpdir"` and assert `ok:true` plus expected check codes.
- [ ] Keep existing enter/start/handoff/board/finish smoke coverage.

### Task 18: Final verification and integration

**Files:**
- All changed files.

- [ ] Run:

```bash
bash -n scripts/install-codex-plugin.sh scripts/verify-install.sh hooks/session-start hooks/session-start-codex
python3 -m py_compile skills/gitwarp/scripts/gitwarp.py skills/gitwarp/scripts/install_cli.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/install_cli.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
```

- [ ] After implementation branch is committed and verified, merge it to `main` from the main controller session.
- [ ] From `main`, install the merged plugin and run smoke:

```bash
scripts/install-codex-plugin.sh
scripts/verify-install.sh
```

- [ ] Run fresh Codex availability check:

```bash
codex --ask-for-approval never exec --sandbox read-only -C /Users/nako/WebstormProjects/github/thefoxfairy/GitWarp "Reply with exactly GITWARP_PLUGIN_SKILL=available if the gitwarp skill is listed in your available skills or session context; otherwise reply GITWARP_PLUGIN_SKILL=missing."
```

- [ ] Run main verification again after installation.
- [ ] `gitwarp finish --collapse` the implementation worktree after merge and verification.
