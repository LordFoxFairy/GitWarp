# GitWarp DDD Architecture Design

## Problem

GitWarp's current runtime works, but its production code is still organized like a grown script. `cli.py`, `services.py`, `worktrees.py`, and `web.py` mix domain rules, orchestration, Git subprocess calls, filesystem persistence, HTTP transport, and JSON presentation. This makes future features risky because new interfaces can easily duplicate workflow logic or bypass safety rules.

The biggest correctness risk is the web console: it combines security policy, confirmation-token cryptography, route handling, file reads, service dispatch, server lifecycle, and inline HTML in one module. The inline UI also renders ledger-controlled strings with `innerHTML`, which can turn branch, purpose, or progress text into console XSS.

## Goals

- Move toward a DDD-style architecture with explicit domain objects, application use cases, infrastructure adapters, and presentation adapters.
- Preserve all current CLI command names, JSON payload shape, plugin packaging, and install behavior during the migration.
- Make CLI and Web share the same application use cases instead of duplicating workflows.
- Split Web into security, contracts, resources, controllers, transport, and server lifecycle modules.
- Fix the inline web console XSS risk while keeping the current no-build stdlib UI.
- Keep changes testable in small slices with compatibility facades.

## Non-Goals

- Do not add a React build in this refactor.
- Do not change GitWarp ledger schema version.
- Do not change public CLI JSON contracts unless existing tests prove the contract already permits it.
- Do not introduce third-party runtime dependencies.

## Target Package Boundaries

```text
src/gitwarp/
  domain/
    errors.py          # domain-facing GitWarpError compatibility
    model.py           # typed value objects for workspace and dossier concepts
    policies.py        # branch collision, target selection, head drift, guarded-root policy
  application/
    dto.py             # JSON-compatible request/result DTO helpers
    services.py        # use cases used by CLI/Web compatibility facades
  infrastructure/
    git_cli.py         # Git command adapter
    json_ledger.py     # ledger persistence compatibility surface
    filesystem_dossiers.py
  webapp/
    contracts.py       # endpoint registry, request validation, schema generation
    security.py        # host policy, CSRF token, confirmation token validation
    resources.py       # inline/static console HTML and dossier reads
    controllers.py     # route-to-use-case orchestration
    transport.py       # BaseHTTPRequestHandler concerns
    server.py          # server lifecycle and readiness JSON
```

Existing modules remain as compatibility shims initially:

- `foundation.py` re-exports core constants, `RepoContext`, `GitWarpError`, path/time helpers, and `run_git`.
- `services.py` re-exports application use cases.
- `web.py` re-exports the public web API and `run_web_console`.
- `cli.py` keeps argparse and JSON emission, but delegates workflows to application services.

## Domain Model

The first migration step introduces typed domain objects without forcing the whole codebase to use them immediately:

- `WorktreeSnapshot`: live Git worktree path, head, branch, detached/main flags.
- `HeadDrift`: last recorded head versus current head.
- `DossierRef`: dossier root and markdown file paths.
- `WorkspaceRecord`: ledger-backed workspace ownership and handoff metadata.
- `DispatchPlan`: rendered agent launch command and preview.

Each object has `from_mapping` / `to_dict` boundaries where current JSON-compatible dictionaries are still required. This lets the runtime move from dicts to types incrementally while preserving output shape.

## Web Architecture

The new `webapp` package owns all HTTP-specific responsibilities:

- `contracts.py` is the only place that knows endpoint required fields and request validation.
- `security.py` owns host validation, accepted Host headers, request token checks, and destructive confirmation tokens.
- `resources.py` owns the web console HTML and safe dossier reads.
- `controllers.py` maps validated requests to application use cases.
- `transport.py` handles HTTP parsing, JSON response envelopes, status codes, and routing.
- `server.py` starts the stdlib HTTP server and prints deterministic readiness JSON.

The inline UI must use DOM text assignment instead of `innerHTML` for ledger-controlled values.

## Testing Strategy

- Characterization tests must continue covering existing command behavior before each extraction.
- Packaging tests must ensure root `src/gitwarp` and plugin `plugins/gitwarp/src/gitwarp` stay mirrored.
- Web tests should be split by responsibility: contracts, security, resources, and end-to-end API workflows.
- Final verification must include py_compile, skill validation, plugin validation, full unittest discovery, install smoke, and `git diff --check`.

## Migration Order

1. Add DDD architecture docs and tests that assert the new package boundaries exist.
2. Introduce `domain`, `application`, and `infrastructure` compatibility modules.
3. Move shared workflow builders from root `services.py` into `application/services.py`; keep root `services.py` as a re-export.
4. Extract web contracts, security, resources, controllers, transport, and server from `web.py`; keep root `web.py` as a re-export.
5. Refactor CLI command handlers to delegate duplicated workflows to application services.
6. Split web tests by new module boundary and add an XSS regression test.
7. Mirror all runtime package changes into the plugin package.

## Acceptance Criteria

- `src/gitwarp/domain`, `src/gitwarp/application`, `src/gitwarp/infrastructure`, and `src/gitwarp/webapp` exist with production code, not placeholders.
- `src/gitwarp/web.py` and `src/gitwarp/services.py` are compatibility shims under 80 lines each.
- Web security, contracts, resources, controllers, transport, and server lifecycle are separate modules.
- Inline console no longer injects ledger-controlled strings via template `innerHTML`.
- All existing tests pass, plus new boundary and XSS tests.
- Plugin mirror is byte-for-byte aligned with root runtime package.
