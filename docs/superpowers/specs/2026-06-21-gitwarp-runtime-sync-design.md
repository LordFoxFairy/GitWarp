# GitWarp Runtime Sync Design

## Problem
The installed `gitwarp` launcher can lag behind the repository or installed plugin cache. A stale launcher may still answer `gitwarp --version`, but fail newer commands such as `gitwarp next` or `gitwarp task create`. This creates a hidden mismatch between the active skill instructions and the executable runtime.

## Goals
- Add `gitwarp upgrade --check` for a non-mutating launcher health check.
- Add `gitwarp upgrade` for an explicit local launcher rewrite.
- Teach `gitwarp doctor` to detect launcher capability drift and recommend `gitwarp upgrade`.
- Keep hooks lightweight: they may report the issue, but must not silently repair or mutate user state.

## Non-Goals
- No network update, package-manager install, or remote plugin refresh.
- No automatic major repair from SessionStart hooks.
- No Git repository mutation.

## Architecture
- Domain remains unchanged; runtime sync is operational application behavior.
- Application layer owns the `runtime_sync` use case and returns deterministic JSON-ready DTOs.
- CLI adapter exposes `upgrade` and delegates to the use case.
- Doctor reuses the same launcher inspection probes, so CLI and health output cannot drift.

## Acceptance Criteria
- `gitwarp upgrade --check` reports `missing`, `stale`, or `current` without writing files.
- `gitwarp upgrade --dest <path>` writes a launcher that executes the current package entrypoint.
- `gitwarp doctor` emits a warning when the launcher exists but lacks required current commands.
- Existing single-line JSON behavior is preserved for automation-facing commands.
