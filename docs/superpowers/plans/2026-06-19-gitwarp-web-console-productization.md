# GitWarp Web Console Productization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the implemented GitWarp Web API into a usable local management console with documented launch paths and install-smoke coverage.

**Architecture:** Keep the CLI and API deterministic while moving browser UI code out of `web.py` into a focused `web_ui.py` module. Use standard-library HTML/JS only, call the existing `/api/*` endpoints, and require the existing confirmation challenge for destructive actions. Documentation and smoke tests should verify the same public workflows users and agents will run.

**Tech Stack:** Python standard library, embedded HTML/CSS/JS, Git CLI, Bash smoke script, `unittest`.

---

## File Structure

- Create: `skills/gitwarp/scripts/gitwarp_core/web_ui.py` for HTML rendering and browser-side JS/CSS payloads.
- Modify: `skills/gitwarp/scripts/gitwarp_core/web.py` to import `render_web_console_html()` and keep only server/security/API routing.
- Modify: `tests/test_gitwarp.py` for UI affordance and Web API smoke coverage.
- Modify: `README.md` with `gitwarp web` quick start, safety model, and human/operator workflow.
- Modify: `skills/gitwarp/SKILL.md` to expose `web` as a human oversight surface while keeping CLI JSON as the automation contract.
- Modify: `skills/gitwarp/references/install.md` with install verification and `--no-open` usage.
- Modify: `scripts/verify-install.sh` to start Web Console, fetch state, and exercise init/dispatch/handoff/finish through API.
- Mirror: `plugins/gitwarp/skills/gitwarp/...` and plugin docs/scripts after each behavior change.

## Parallel Work Strategy

- UI slice and docs/smoke slice are independent after endpoint contracts are fixed.
- If subagents are available, dispatch one worker for UI wiring and one worker for docs/smoke. The main session must re-run all tests and smoke checks before claiming completion.
- If subagents are unavailable, execute chunks sequentially with commits after each green checkpoint.

## Chunk 1: UI Module And Action Wiring

### Task 1: Write failing UI affordance tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_web_root_exposes_operator_controls`.
- [ ] Start `gitwarp web --cwd <repo> --port 0 --no-open`.
- [ ] Fetch `/` and assert the HTML includes `data-gitwarp-token`, `/api/state`, `/api/init`, `/api/dispatch`, `/api/start`, `/api/handoff`, `/api/confirmation`, `/api/finish`, `/api/collapse`.
- [ ] Assert action form/control ids exist: `dispatch-form`, `handoff-form`, `finish-form`, `collapse-button`, `confirmation-dialog`, `copy-launch-command`.
- [ ] Run:

```bash
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_root_exposes_operator_controls -v
```

- [ ] Expected: fail before the UI module exposes these controls.

### Task 2: Extract and implement browser UI

**Files:**
- Create: `skills/gitwarp/scripts/gitwarp_core/web_ui.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/web.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp_core/web_ui.py`
- Sync: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp_core/web.py`

- [ ] Move embedded HTML/CSS/JS out of `web.py`.
- [ ] Add `render_web_console_html(token: str) -> str`.
- [ ] Render a board with worktree rows, doctor/reconcile summary, selected dossier snippets, and raw JSON diagnostics collapsed by default.
- [ ] Add forms for init, dispatch, start, handoff, and finish.
- [ ] Add a destructive confirmation dialog that displays path, branch, HEAD, dirty count/sample, untracked count/sample, and expiry before calling finish-collapse or collapse.
- [ ] Disable mutation controls when `/api/schema` reports `readonly: true`.
- [ ] After any successful mutation, refresh `/api/state`; never optimistically mutate UI state.
- [ ] Keep CSS/JS self-contained and dependency-free.
- [ ] Run targeted UI tests and full Web tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v -k web_
```

- [ ] Commit:

```bash
git add tests/test_gitwarp.py skills/gitwarp/scripts/gitwarp_core plugins/gitwarp/skills/gitwarp/scripts/gitwarp_core
git commit -m "feat: wire web console operator controls"
```

## Chunk 2: Web API Smoke In Installer

### Task 3: Write failing install smoke expectations

**Files:**
- Modify: `scripts/verify-install.sh`

- [ ] Add a `start_web_console` helper that launches `gitwarp web --cwd "$tmpdir" --port 0 --no-open`.
- [ ] Read the first stdout line as readiness JSON and export `WEB_URL`.
- [ ] Fetch `/api/session` and `/api/state` with Python `urllib`.
- [ ] Assert `/api/state` does not create `.gitwarp/ledger.json` before `POST /api/init`.
- [ ] POST `/api/init`, `/api/dispatch`, `/api/handoff`, and `/api/finish` without collapse.
- [ ] Assert CLI `board --cwd "$tmpdir"` sees the Web-created worktree and progress.
- [ ] Always terminate the Web server in `cleanup`.

### Task 4: Implement smoke helper robustly

**Files:**
- Modify: `scripts/verify-install.sh`

- [ ] Use only Bash, Python stdlib, and existing `gitwarp`.
- [ ] Keep the Web server log separate from readiness stdout.
- [ ] Fail with useful stderr if readiness JSON is missing.
- [ ] Avoid destructive collapse in install smoke; endpoint collapse is already covered by unit tests.
- [ ] Run syntax and smoke:

```bash
bash -n scripts/verify-install.sh
scripts/verify-install.sh
```

- [ ] Commit:

```bash
git add scripts/verify-install.sh
git commit -m "test: smoke gitwarp web console"
```

## Chunk 3: Docs And Skill Guidance

### Task 5: Update public docs

**Files:**
- Modify: `README.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`
- Sync: `plugins/gitwarp/skills/gitwarp/SKILL.md`
- Sync: `plugins/gitwarp/skills/gitwarp/references/install.md`

- [ ] README quick start includes:

```bash
gitwarp web --cwd "$PWD"
gitwarp web --cwd "$PWD" --no-open
gitwarp web --cwd "$PWD" --readonly
```

- [ ] Explain that Web Console is for human oversight and local operations; automated agents should continue using CLI JSON.
- [ ] Document loopback binding, Host allowlist, CSRF token, and confirmation token behavior at a user level.
- [ ] Add a short Web workflow: init, dispatch/start, handoff, finish, collapse confirmation.
- [ ] Update SKILL command table with `web`.
- [ ] Install notes mention Web Console verification after installing the launcher.
- [ ] Commit:

```bash
git add README.md skills/gitwarp/SKILL.md skills/gitwarp/references/install.md plugins/gitwarp/skills/gitwarp/SKILL.md plugins/gitwarp/skills/gitwarp/references/install.md
git commit -m "docs: document gitwarp web console"
```

## Chunk 4: Final Verification And Release Prep

### Task 6: Full validation

**Files:**
- All changed files.

- [ ] Run:

```bash
bash -n scripts/verify-install.sh hooks/session-start hooks/session-start-codex scripts/install-codex-plugin.sh
python3 -m py_compile skills/gitwarp/scripts/gitwarp.py skills/gitwarp/scripts/gitwarp_core/*.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp_core/*.py
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/verify-install.sh
git diff --check
```

- [ ] If validator or smoke fails because external Codex/plugin state is unavailable, record the exact command and error before deciding whether to proceed.
- [ ] Final commit if validation required fixes.
- [ ] Write `gitwarp handoff` with commit hashes, test evidence, and remaining release notes.
