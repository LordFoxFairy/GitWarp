# GitWarp Web Console Design

## Goal

Add a local Web Console for GitWarp so humans can manage agent worktrees without memorizing CLI commands. The console should make the current worktree matrix, doctor findings, dossiers, and safe lifecycle actions visible from a browser while preserving GitWarp's existing CLI-first safety model.

## Non-Goals

- No hosted service, cloud sync, authentication server, database, or multi-user collaboration.
- No automatic agent execution in the first release.
- No replacement for deterministic CLI JSON streams; existing CLI commands remain the automation contract.
- No heavy runtime framework dependency unless a later design explicitly accepts it.

## Entry Points

Support both forms:

```bash
gitwarp web --cwd "$PWD"
gitwarp --web --cwd "$PWD"
```

`gitwarp web` is the canonical subcommand. `--web` is a convenience alias that maps to the same implementation before subcommand dispatch.

Options:

- `--cwd <path>`: target repository or nested worktree path, resolved to an absolute path.
- `--host 127.0.0.1`: default loopback-only binding.
- `--port 0`: default ephemeral port; print and open the selected URL.
- `--no-open`: start the server without opening a browser.
- `--readonly`: force read-only UI even if future releases enable mutations by default.
- `--unsafe-host`: allow binding to a non-loopback host after printing a warning.

## Architecture

Use Python standard library only:

- `http.server.ThreadingHTTPServer` for the local server.
- A small internal service layer that returns payload dictionaries for state, doctor, reconcile, dispatch, start, handoff, finish, and collapse operations.
- A single embedded HTML/CSS/JS page served by the CLI script.
- JSON endpoints under `/api/*`.

This keeps packaging simple for Codex and Claude skill/plugin installs. The Web Console must not shell out to `gitwarp`, but it also should not call the current stdout-oriented `cmd_*` functions directly. Implementation should first extract reusable payload builders from CLI commands, then have both CLI and Web call those builders. This preserves deterministic CLI JSON while giving Web endpoints testable return values.

The first service extraction must distinguish mutating and non-mutating builders. Existing `cmd_board` uses `sync_ledger(..., persist=True)`, so `/api/state` must not reuse that behavior. Web state should use a new non-mutating board builder based on `parse_worktrees` plus `load_ledger` only when the ledger already exists and is valid. It must not create, normalize, prune, lock, or rewrite ledger state.

## UI Model

The first screen is an operations board:

- Repository badge with resolved repo root, current GitWarp statusline, and active branch.
- Health strip showing `doctor` and `reconcile` totals.
- Worktree table with branch, agent, status, purpose, latest progress, stale marker, and dossier links.
- Detail panel for selected worktree showing task, progress, lessons snippets, absolute paths, and recommended next commands.
- Actions panel for safe lifecycle operations.

Initial read-only actions:

- Refresh board/doctor/reconcile.
- Copy launch command from existing dispatch metadata when present.
- Open worktree path/dossier path as text in the browser.

Mutation actions are phased in after the read-only console is verified:

- Create sandbox via `dispatch` or `start` once the read-only board is stable.
- Record handoff progress once CSRF protection is in place.
- Finish and optionally collapse a sandbox only after destructive confirmation is implemented and covered by tests.

Dangerous actions (`finish --collapse`, `collapse`) require explicit confirmation in the UI. The confirmation must show branch, path, HEAD, dirty summary, and untracked artifact summary.

## API Endpoints

All API responses are JSON with stable keys and absolute paths.

- `GET /api/state`: combined `enter`, `board --verbose`, `doctor`, and `reconcile` snapshot.
- `GET /api/dossier?path=<abs>`: read a dossier markdown file if it is under GitWarp's dossier root.
- `POST /api/init`: run init for the selected repo; supports `write_gitignore`.
- `POST /api/dispatch`: create a dossier-backed worktree and return launch command.
- `POST /api/start`: create a manual worktree.
- `POST /api/handoff`: append progress and optional lesson.
- `POST /api/finish`: record final progress; optional collapse with confirmation token.
- `POST /api/collapse`: destructive remove with confirmation token.

The server should also expose `GET /api/schema` with endpoint names, required fields, and mutability flags. This helps future agents discover the Web Console contract without scraping UI code.

`/api/state` response shape:

```json
{
  "ok": true,
  "repo_root": "/abs/repo",
  "readonly": true,
  "statusline": "GITWARP[main-repo]",
  "worktrees": [],
  "doctor": {"findings": [], "summary": {}, "cached": true},
  "reconcile": {"findings": [], "summary": {}},
  "recommended_next": []
}
```

Required mutation request fields:

- `POST /api/init`: `{"write_gitignore": false}`
- `POST /api/dispatch`: `{"agent": "codex", "agent_id": null, "branch": "...", "purpose": "..."}`
- `POST /api/start`: `{"agent_id": "...", "branch": "...", "purpose": "..."}`
- `POST /api/handoff`: `{"cwd": "/abs/worktree/or/nested", "status": "...", "progress": "...", "lesson": null}`
- `POST /api/finish`: `{"cwd": "/abs/worktree/or/nested", "status": "...", "progress": "...", "lesson": null, "collapse": false, "confirmation": null}`
- `POST /api/collapse`: `{"path": "/abs/worktree", "branch": null, "confirmation": "..."}`

`finish --purge-dossier` is not exposed in the Web Console MVP.

## Safety Rules

Default binding is `127.0.0.1` only. Binding to any non-loopback host must fail unless the user passes `--unsafe-host` with an explicit warning. Loopback validation must cover IPv4, IPv6, and hostnames by resolving the bind host and rejecting `0.0.0.0`, `::`, and non-loopback addresses unless unsafe mode is explicit.

Mutation endpoints require:

- JSON `Content-Type`.
- A per-server random CSRF token returned by `GET /api/session` and embedded in the initial HTML. Mutations require `X-GitWarp-Token`.
- Confirmation token for destructive actions. The token is derived from a freshly inspected absolute path, branch, HEAD, dirty summary, untracked summary, and timestamp for that request. Execution must re-read the same fields and reject the token if any field changed.

The Web Console must keep `doctor` read-only. It must never execute repository hooks. It may display hook health from existing static doctor findings.

Doctor checks used by `/api/state` should use a web-safe mode:

- Static checks run on every refresh.
- Shelling checks such as launcher `--version` and `codex plugin list --json` are cached for at least 30 seconds with timeouts.
- The UI marks cached doctor data with `cached: true` and `cache_age_seconds`.

## Status And Refresh

MVP uses polling:

- `/api/state` on page load.
- Manual refresh button.
- Optional 5-second auto-refresh toggle, off by default.

Server-sent events or WebSockets are deferred. Polling is enough because GitWarp state changes are user-driven and file-system based.

Startup output contract:

- On successful start, write one single-line JSON object to stdout, then keep the process running:

```json
{"ok":true,"url":"http://127.0.0.1:54321","host":"127.0.0.1","port":54321,"repo_root":"/abs/repo","readonly":false}
```

- Runtime access logs and warnings go to stderr.
- `--no-open` suppresses browser launch only; it does not change stdout readiness JSON.
- Tests stop the server by terminating the process. A later `/api/shutdown` endpoint is out of scope.

## Error Handling

Every failed API response returns:

```json
{"ok":false,"error":"...","code":"optional_machine_code"}
```

The UI shows the error inline and keeps the previous valid state visible. Mutations must not optimistically update state; after a successful mutation, the UI refreshes `/api/state`.

## Integration With Context Mounts

The Web Console should leave space for a later `context mounts` slice:

- `/api/state` can include `context_mounts` once CLI support exists.
- The UI can add a "Context" tab showing mounted `AGENTS.md`, `CLAUDE.md`, and local policy files.
- No context mount behavior is implemented in the Web Console MVP.

## Testing Strategy

Unit tests:

- Parser accepts `web` and `--web` forms.
- Server binds loopback by default and rejects non-loopback without unsafe flag.
- `/api/state` returns deterministic JSON shape for a temporary repo.
- `/api/state` does not create, normalize, prune, lock, or rewrite `.gitwarp/ledger.json`.
- Dossier endpoint refuses paths outside the dossier root.
- `/api/session` returns a CSRF token and `/api/schema` documents mutability and required fields.
- Mutating endpoints require CSRF token.
- Read-only mode rejects all mutation endpoints with a stable JSON error.
- Collapse/finish destructive endpoints require confirmation bound to path, branch, HEAD, dirty summary, and untracked summary.
- Existing dispatch launch metadata is included in state when present.
- Doctor web-safe cache avoids repeated external checks during rapid polling.
- Host validation rejects `0.0.0.0`, `::`, and non-loopback hosts without `--unsafe-host`.

Smoke test:

- Start `gitwarp web --cwd <tmprepo> --port 0 --no-open`.
- Fetch `/api/state`.
- Assert no ledger file is created by read-only state fetch before `init`.
- Run `init`, `dispatch`, `handoff`, and `finish` through API.
- Verify CLI `board` and `reconcile` agree with Web Console state.

Manual verification:

- Start from a real source checkout.
- Confirm board, doctor, reconcile, and dossier snippets render.
- Confirm browser launch can be disabled with `--no-open`.

## Rollout Plan

1. Add read-only server and UI with `/api/state`, `/api/schema`, and dossier reads.
2. Add safe mutation endpoints for init, dispatch/start, and handoff.
3. Add finish/collapse with strict confirmation after read-only and safe mutation flows are verified.
4. Update README, SKILL.md, install notes, plugin mirror, and smoke tests.

This sequencing keeps the first implementation useful even if destructive actions need more hardening before release.
