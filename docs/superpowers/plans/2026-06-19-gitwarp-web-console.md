# GitWarp Web Console Implementation Plan

> Status: Historical record. Superseded by `2026-06-20-gitwarp-ddd-architecture.md` and the repository README. Do not follow old `plugins/gitwarp` mirror instructions.

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local browser-based GitWarp management console with read-only state, safe mutations, and deterministic test coverage.

**Architecture:** First split the current single-file CLI into a small importable package under `skills/gitwarp/scripts/gitwarp_core/`, keeping `gitwarp.py` as a thin entrypoint. Then build a Python standard-library `ThreadingHTTPServer` around service payload builders. Keep `/api/state` non-mutating, protect mutation endpoints with Host allowlisting and CSRF, and gate destructive actions behind a fresh confirmation challenge.

**Tech Stack:** Python standard library (`http.server`, `urllib`, `threading`, `secrets`, `hmac`, `socket`, `webbrowser`), Git CLI, unittest, Bash smoke script, embedded HTML/CSS/JS.

---

## File Structure

- Modify `skills/gitwarp/scripts/gitwarp.py`: thin compatibility entrypoint only.
- Create `skills/gitwarp/scripts/gitwarp_core/__init__.py`: package marker and version export.
- Create `skills/gitwarp/scripts/gitwarp_core/models.py`: constants, `RepoContext`, `GitWarpError`.
- Create `skills/gitwarp/scripts/gitwarp_core/git_ops.py`: Git command execution, repo discovery, worktree parsing, branch/worktree helpers.
- Create `skills/gitwarp/scripts/gitwarp_core/ledger.py`: ledger loading, schema validation, locking, mutation, init helpers.
- Create `skills/gitwarp/scripts/gitwarp_core/agents.py`: agent registry, template validation, launch command rendering.
- Create `skills/gitwarp/scripts/gitwarp_core/dossiers.py`: dossier paths, markdown creation, snippet reading, handoff recording.
- Create `skills/gitwarp/scripts/gitwarp_core/services.py`: payload builders for CLI and Web APIs.
- Create `skills/gitwarp/scripts/gitwarp_core/cli.py`: argparse parser and command handlers.
- Create `skills/gitwarp/scripts/gitwarp_core/web.py`: local HTTP server, API routing, embedded UI, web safety helpers.
- Modify `tests/test_gitwarp.py`: parser/API/server tests using temporary repos and localhost requests.
- Modify `scripts/verify-install.sh`: installed CLI smoke for `gitwarp web --no-open --port 0`.
- Modify `README.md`: Web Console quick start and safety model.
- Modify `skills/gitwarp/SKILL.md`: command contract and workflow guidance for `web`.
- Modify `skills/gitwarp/references/install.md`: local web console install/verify note.
- Mirror canonical files into `plugins/gitwarp/...`.

## Chunk 0: Split The CLI Into A Package

### Task 0: Extract modules without behavior changes

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/__init__.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/models.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/git_ops.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/ledger.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/agents.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/dossiers.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/services.py`
- Create: `skills/gitwarp/scripts/gitwarp_core/cli.py`

- [ ] Move constants, `GitWarpError`, and `RepoContext` into `models.py`.
- [ ] Move Git subprocess/repo/worktree helpers into `git_ops.py`.
- [ ] Move ledger/init helpers into `ledger.py`.
- [ ] Move agent registry/template helpers into `agents.py`.
- [ ] Move dossier/handoff helpers into `dossiers.py`.
- [ ] Move existing payload-style helpers into `services.py`.
- [ ] Move argparse and `cmd_*` handlers into `cli.py`.
- [ ] Replace `gitwarp.py` with:

```python
#!/usr/bin/env python3
from gitwarp_core.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] Run full unittest and py_compile.

```bash
python3 -m py_compile skills/gitwarp/scripts/gitwarp.py skills/gitwarp/scripts/gitwarp_core/*.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] Sync plugin mirror including the new package.
- [ ] Commit.

```bash
cp -R skills/gitwarp/scripts/gitwarp_core plugins/gitwarp/skills/gitwarp/scripts/
cp skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git add skills/gitwarp/scripts plugins/gitwarp/skills/gitwarp/scripts tests/test_gitwarp.py
git commit -m "refactor: split gitwarp cli into modules"
```

## Chunk 1: Service Builders And Non-Mutating State

### Task 1: Add failing state/service tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_web_state_does_not_create_or_rewrite_ledger`.
  - Create a fresh temp repo with no `.gitwarp/ledger.json`.
  - Import the script module via `importlib.util.spec_from_file_location`.
  - Call `build_web_state_payload(repo, readonly=True)`.
  - Assert `payload["ok"] is True`, `payload["readonly"] is True`, and no ledger file exists.
  - Seed a malformed ledger, call state again, assert the bytes are unchanged and `doctor` reports ledger error.

- [ ] Add `test_web_state_includes_dispatch_metadata`.
  - Create a dispatched worktree via CLI.
  - Call `build_web_state_payload`.
  - Assert the dispatched row contains `dispatch.launch_command` and `dispatch.launch_preview`.

- [ ] Add `test_web_doctor_cache_marks_and_reuses_external_checks`.
  - Call `build_web_state_payload(repo, readonly=True, doctor_cache={})` twice quickly.
  - Assert `payload["doctor"]["cached"]` is `False` for the first call and `True` for the second call.
  - Assert the second payload includes integer `cache_age_seconds`.

- [ ] Run targeted tests and verify failure.

Run:

```bash
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_state_does_not_create_or_rewrite_ledger -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_state_includes_dispatch_metadata -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_doctor_cache_marks_and_reuses_external_checks -v
```

Expected: fail because service functions do not exist.

### Task 2: Implement state service builders

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/services.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/cli.py`

- [ ] Add `safe_load_ledger_for_web(ctx)`:
  - If ledger missing, return `default_ledger(ctx)` in memory only.
  - If ledger invalid, return default in memory plus error details.
  - Never write, normalize on disk, prune, or lock.

- [ ] Add `sync_ledger_for_web(ctx, live_worktrees)`:
  - Enrich live worktrees with metadata from in-memory ledger.
  - Preserve `dispatch` metadata from ledger entries.
  - Do not call `mutate_ledger`.

- [ ] Add `build_board_rows_payload(ctx, *, verbose, persist)`:
  - Existing board path calls with `persist=True`.
  - Web path calls with `persist=False`.

- [ ] Add `build_reconcile_payload(ctx)` and make `cmd_reconcile` emit it.

- [ ] Add `build_doctor_payload(ctx, *, web_safe=False, cache=None)`.
  - Keep CLI doctor behavior equivalent.
  - Web-safe mode caches external checks for at least 30 seconds.

- [ ] Add `build_web_state_payload(cwd, *, readonly, doctor_cache=None)`.
  - Include `ok`, `repo_root`, `readonly`, `statusline`, `worktrees`, `doctor`, `reconcile`, `recommended_next`.
  - Do not mutate ledger.

- [ ] Run full unittest.

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] Sync plugin mirror script.
- [ ] Commit.

```bash
cp -R skills/gitwarp/scripts/gitwarp_core plugins/gitwarp/skills/gitwarp/scripts/
cp skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git add tests/test_gitwarp.py skills/gitwarp/scripts plugins/gitwarp/skills/gitwarp/scripts
git commit -m "feat: add web state service"
```

## Chunk 2: Web Server Shell, Routing, And Security

### Task 3: Add failing server safety tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add helpers to start `gitwarp web --cwd <repo> --port 0 --no-open --readonly` as a subprocess.
  - Read first stdout line.
  - Parse readiness JSON.
  - Terminate process in cleanup.

- [ ] Add `test_web_server_readiness_json_and_state_endpoint`.
  - Assert readiness JSON has `ok`, `url`, `host`, `port`, `repo_root`, `readonly`.
  - Fetch `/api/state`; assert JSON shape.

- [ ] Add `test_web_parser_accepts_subcommand_and_global_alias`.
  - Start server with `gitwarp web --cwd <repo> --port 0 --no-open --readonly`; assert readiness JSON.
  - Start server with `gitwarp --web --cwd <repo> --port 0 --no-open --readonly`; assert readiness JSON.

- [ ] Add `test_web_rejects_bad_host_header`.
  - Fetch `/api/session` with mismatched `Host`.
  - Assert HTTP 403 JSON.

- [ ] Add `test_web_host_validation_rejects_non_loopback_without_unsafe`.
  - Run parser/server startup with `--host 0.0.0.0`.
  - Assert nonzero JSON error.

- [ ] Add `test_web_session_schema_and_readonly_mutation_rejection`.
  - Fetch `/api/session`; assert token string.
  - Fetch `/api/schema`; assert endpoints and mutability flags.
  - POST `/api/init` on readonly server with token; assert stable readonly error.

- [ ] Run targeted tests and verify failure.

Run:

```bash
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_server_readiness_json_and_state_endpoint -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_parser_accepts_subcommand_and_global_alias -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_rejects_bad_host_header -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_host_validation_rejects_non_loopback_without_unsafe -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_session_schema_and_readonly_mutation_rejection -v
```

Expected: fail because web server and parser alias do not exist.

### Task 4: Implement server shell

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/web.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/cli.py`

- [ ] Add imports: `base64`, `hmac`, `ipaddress`, `socket`, `threading`, `urllib.parse`, `webbrowser`, `http.server`.

- [ ] Add `validate_web_host(host, unsafe)`:
  - Allow loopback addresses and hostnames resolving only to loopback.
  - Reject `0.0.0.0`, `::`, non-loopback without `unsafe`.

- [ ] Add `build_allowed_host_headers(host, port)`.

- [ ] Add `WebConsoleState` dataclass:
  - `ctx`, `readonly`, `token`, `doctor_cache`, `allowed_hosts`, `confirmation_secret`.

- [ ] Add `GitWarpWebHandler(BaseHTTPRequestHandler)`:
  - Enforce Host allowlist before route handling.
  - Return JSON errors with deterministic shape.
  - Serve `/`, `/api/session`, `/api/schema`, `/api/state`.
  - Reject unknown routes.

- [ ] Add `run_web_console(args)`:
  - Discover repo.
  - Validate host.
  - Bind `ThreadingHTTPServer`.
  - Emit readiness JSON to stdout and flush.
  - Open browser unless `--no-open`.
  - `serve_forever()`.

- [ ] Parser wiring:
  - Add canonical `web` subcommand.
  - Add global `--web` alias that maps to web when no subcommand is supplied.

- [ ] Run tests.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] Sync plugin mirror script and commit.

```bash
cp -R skills/gitwarp/scripts/gitwarp_core plugins/gitwarp/skills/gitwarp/scripts/
cp skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git add tests/test_gitwarp.py skills/gitwarp/scripts plugins/gitwarp/skills/gitwarp/scripts
git commit -m "feat: add gitwarp web server"
```

## Chunk 3: Read-Only UI And Dossier API

### Task 5: Add failing UI/dossier tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_web_root_serves_console_html`.
  - Fetch `/`.
  - Assert HTML includes `GitWarp Web Console`, `/api/state`, and `data-gitwarp-token`.

- [ ] Add `test_web_dossier_endpoint_allows_only_dossier_root`.
  - Create a worktree via `start`.
  - Fetch `/api/dossier?path=<task_md>`; assert markdown text.
  - Fetch `/api/dossier?path=<repo>/README.md`; assert 403 JSON.

- [ ] Run targeted tests and verify failure.

Run:

```bash
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_root_serves_console_html -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_dossier_endpoint_allows_only_dossier_root -v
```

Expected: fail because root HTML and dossier API are not implemented.

### Task 6: Implement embedded UI and dossier reads

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/web.py`

- [ ] Add `WEB_CONSOLE_HTML` with:
  - Distinctive lightweight UI.
  - Board table.
  - Health cards for doctor/reconcile.
  - Detail panel with dossier links/snippets.
  - Refresh button and optional auto-refresh toggle.
  - Basic forms for init/dispatch/handoff disabled when readonly.

- [ ] Add `/api/dossier` GET handler:
  - Require path under `ctx.dossier_root`.
  - Read UTF-8 with replacement.
  - Return `{"ok":true,"path": "...", "content": "..."}`.

- [ ] Run tests, sync mirror, commit.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
cp -R skills/gitwarp/scripts/gitwarp_core plugins/gitwarp/skills/gitwarp/scripts/
cp skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git add tests/test_gitwarp.py skills/gitwarp/scripts plugins/gitwarp/skills/gitwarp/scripts
git commit -m "feat: add gitwarp web console ui"
```

## Chunk 4: Mutations And Confirmation Flow

### Task 7: Add failing mutation tests

**Files:**
- Modify: `tests/test_gitwarp.py`

- [ ] Add `test_web_init_dispatch_handoff_flow`.
  - Start non-readonly server.
  - Fetch token.
  - POST `/api/init`; assert ledger exists.
  - POST `/api/dispatch`; assert worktree exists and response has launch command.
  - POST `/api/handoff`; assert progress is written.

- [ ] Add `test_web_mutations_require_csrf`.
  - POST mutation without token.
  - Assert 403 JSON.

- [ ] Add `test_web_mutations_require_json_content_type`.
  - POST `/api/init` with a valid CSRF token but no JSON `Content-Type`.
  - Assert 415 or 400 JSON error with stable code.

- [ ] Add `test_web_confirmation_rejects_stale_collapse`.
  - Start worktree.
  - POST `/api/confirmation` for collapse.
  - Dirty the worktree after challenge.
  - POST `/api/collapse`; assert stale confirmation error and worktree still exists.

- [ ] Add `test_web_confirmation_rejects_expired_token`.
  - Generate a confirmation token with a short test TTL.
  - Wait past expiry or monkeypatch the clock helper.
  - Assert collapse returns stale/expired confirmation error.

- [ ] Add `test_web_finish_collapse_requires_fresh_confirmation`.
  - Start worktree.
  - POST `/api/confirmation` for `finish-collapse`.
  - Change HEAD or dirty state after challenge.
  - POST `/api/finish` with `collapse: true`.
  - Assert stale confirmation error and worktree still exists.

- [ ] Run targeted tests and verify failure.

Run:

```bash
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_init_dispatch_handoff_flow -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_mutations_require_csrf -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_mutations_require_json_content_type -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_confirmation_rejects_stale_collapse -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_confirmation_rejects_expired_token -v
python3 -m unittest tests.test_gitwarp.GitWarpTests.test_web_finish_collapse_requires_fresh_confirmation -v
```

Expected: fail because mutation endpoints and confirmation flow are not implemented.

### Task 8: Implement mutation endpoints

**Files:**
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/services.py`
- Modify: `skills/gitwarp/scripts/gitwarp_core/web.py`

- [ ] Add JSON body parser with size limit.
- [ ] Add CSRF validation for POST routes.
- [ ] Enforce JSON `Content-Type` for mutation routes.
- [ ] Add service wrappers returning payloads for init, dispatch, start, handoff, finish, collapse.
- [ ] Add `/api/init`, `/api/dispatch`, `/api/start`, `/api/handoff`.
- [ ] Add `build_confirmation_challenge`.
- [ ] Add HMAC signed confirmation tokens with expiry.
- [ ] Add `/api/confirmation`, `/api/finish`, `/api/collapse`.
- [ ] Ensure stale target state rejects destructive action.
- [ ] Ensure expired confirmation tokens reject both collapse and finish-collapse.
- [ ] Run tests, sync mirror, commit.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
cp -R skills/gitwarp/scripts/gitwarp_core plugins/gitwarp/skills/gitwarp/scripts/
cp skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
git add tests/test_gitwarp.py skills/gitwarp/scripts plugins/gitwarp/skills/gitwarp/scripts
git commit -m "feat: add gitwarp web mutations"
```

## Chunk 5: Docs, Smoke, Validation, Release

### Task 9: Update docs and smoke

**Files:**
- Modify: `README.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`
- Modify: `scripts/verify-install.sh`
- Modify: `plugins/gitwarp/...`

- [ ] README quick start includes:

```bash
gitwarp web --cwd "$PWD"
```

- [ ] SKILL.md command table includes `web` and tells agents to use CLI JSON for automation, Web for human oversight.
- [ ] Install notes include `gitwarp web --cwd /abs/repo --no-open`.
- [ ] Smoke script starts web server with `--port 0 --no-open`, reads readiness JSON, fetches `/api/state`, asserts no ledger created before init, performs init/dispatch/handoff/finish through API, checks CLI `board` and `reconcile` agree with Web state, and terminates server.
- [ ] Mirror all canonical docs/scripts to plugin package.

### Task 10: Final validation and merge

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

- [ ] Commit docs/smoke:

```bash
git add README.md scripts/verify-install.sh skills/gitwarp plugins/gitwarp
git commit -m "docs: document gitwarp web console"
```

- [ ] Merge into main, reinstall CLI from main, re-run validation, push.
- [ ] Finish and collapse the GitWarp worktree.
