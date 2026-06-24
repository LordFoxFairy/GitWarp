# Web Entry, Reload, and Version Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `gitwarp web start` expose a stable fixed entrypoint, add a safe `gitwarp reload` repair path, keep unmanaged branches visible in the Web UI, and enforce version bumps for every user-visible change.

**Architecture:** Keep the current repo-scoped Web Console server, but add a fixed-entry lifecycle layer that manages one active repo at a time and reports both public and backend URLs. Implement reload as a non-destructive rescan/re-registration use case shared by CLI and Web, then extend existing matrix/branch payloads so unmanaged refs remain visible in a dedicated UI section. Treat `src/gitwarp/__init__.py::__version__` as the single version source and add tests that fail when runtime/install behavior changes without a corresponding version bump.

**Tech Stack:** Python 3.10+, standard library HTTP/process/path handling, existing GitWarp DDD layers, React + TypeScript + Primer Web Console, unittest, Vite build checks.

## Global Constraints

- `gitwarp web start` must default to a stable public entrypoint at `http://127.0.0.1:6006`.
- The first implementation uses a single active repo for the fixed entrypoint; do not build multi-repo proxy routing.
- `reload` is a light repair action: rescan, re-register, and rebuild summaries, but never delete worktrees, branch refs, dossier directories, or ledger rows.
- Unknown / unmanaged branches must remain visible in Web and must not be reclassified as GitWarp `base` or `task` branches.
- Every user-visible behavior change must bump `src/gitwarp/__init__.py::__version__`.
- Keep `src/gitwarp/__init__.py::__version__` as the single version source referenced by packaging and runtime checks.
- Follow existing DDD boundaries: `application/` orchestrates use cases, `infrastructure/` handles runtime/filesystem/git helpers, `adapters/` owns CLI/Web entrypoints.
- Run focused tests first, then `scripts/check-release.sh` before claiming completion.

---

## File Structure

- `src/gitwarp/__init__.py` — single version source; bump version for this user-visible feature set.
- `src/gitwarp/infrastructure/runtime.py` — add global state path helpers if fixed-entry lifecycle needs shared home-level state.
- `src/gitwarp/application/use_cases/reload.py` — new light-repair use case for repo rescans and safe re-registration.
- `src/gitwarp/application/use_cases/__init__.py` — export the reload use case.
- `src/gitwarp/application/use_cases/web_state.py` — surface fixed-entry metadata and unmanaged branch grouping in Web payloads.
- `src/gitwarp/webapp/lifecycle.py` — manage fixed public entrypoint state, repo takeover, and backend/public URL reporting.
- `src/gitwarp/webapp/server.py` — emit readiness payload with `public_url`, `backend_url`, and active-repo metadata.
- `src/gitwarp/webapp/contracts.py` — define `/api/reload` mutation schema.
- `src/gitwarp/webapp/controllers.py` — wire `/api/reload` to the shared reload use case.
- `src/gitwarp/adapters/cli/parser.py` — add `reload` command and updated help text for `web`.
- `src/gitwarp/adapters/cli/system.py` — implement `cmd_reload` and forward fixed-entry lifecycle payloads.
- `web/console/src/app/gitwarp-api.ts` — add `reloadRepository()` API call and types for fixed-entry metadata if needed.
- `web/console/src/app/App.tsx` — trigger reload from UI and refresh state after completion.
- `web/console/src/app/components/BranchesPanel.tsx` — add unmanaged-branch section and show fixed-entry/reload controls if the design places them here.
- `web/console/src/app/types.ts` — extend branch row / session / state types for fixed-entry and unmanaged-branch grouping.
- `tests/test_cli_lifecycle.py` — fixed-entry lifecycle tests and CLI reload tests.
- `tests/test_web_api.py` — `/api/reload`, fixed-entry payloads, and unmanaged-branch visibility tests.
- `tests/test_runtime_sync.py` — version-sensitive runtime/install tests.
- `tests/test_packaging.py` — string/structure assertions for new CLI/Web API/UI entrypoints.
- `README.md` and `skills/gitwarp/SKILL.md` — document stable public entrypoint, reload semantics, unmanaged branches, and version-bump rule.

## Task 1: Bump version and add version-guard tests

**Files:**
- Modify: `src/gitwarp/__init__.py:1-4`
- Modify: `tests/test_runtime_sync.py:1-260`
- Modify: `tests/test_packaging.py:1-520`

**Interfaces:**
- Consumes: `src/gitwarp/__init__.py::__version__: str`
- Produces: version-sensitive tests that later tasks must keep green; updated `gitwarp --version` expectation.

- [ ] **Step 1: Write the failing version guard test**

```python
# tests/test_runtime_sync.py
import gitwarp as gitwarp_package

...
    def test_runtime_reports_bumped_version_for_user_visible_release(self) -> None:
        destination = self.repo / "bin" / "gitwarp"

        payload = run_gitwarp(self.repo, "upgrade", "--cwd", str(self.repo), "--dest", str(destination))

        version = subprocess.run(
            [str(destination), "--version"],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(version.stdout.strip(), f"gitwarp {gitwarp_package.__version__}")
        self.assertNotEqual(gitwarp_package.__version__, "0.1.0")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_runtime_sync.py' -v
```

Expected: FAIL because `__version__` is still `0.1.0`.

- [ ] **Step 3: Bump the version minimally**

```python
# src/gitwarp/__init__.py
"""GitWarp core package."""

__version__ = "0.2.0"
```

- [ ] **Step 4: Add a packaging assertion that the docs/runtime now expose the bumped version source**

```python
# tests/test_packaging.py
    def test_python_entrypoint_reports_version_from_package(self) -> None:
        package = (REPO_ROOT / "src" / "gitwarp" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.2.0"', package)
```

- [ ] **Step 5: Run focused tests to verify they pass**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_runtime_sync.py' -v
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
```

Expected: PASS, including the new version assertions.

- [ ] **Step 6: Commit**

```bash
git add src/gitwarp/__init__.py tests/test_runtime_sync.py tests/test_packaging.py
git commit -m "feat: bump gitwarp version to 0.2.0"
```

## Task 2: Implement fixed public Web entrypoint lifecycle

**Files:**
- Modify: `src/gitwarp/infrastructure/runtime.py:116-125`
- Modify: `src/gitwarp/webapp/lifecycle.py:1-220`
- Modify: `src/gitwarp/webapp/server.py:1-90`
- Modify: `src/gitwarp/adapters/cli/system.py:1-80`
- Modify: `tests/test_cli_lifecycle.py:1-360`
- Modify: `tests/test_web_api.py:1-360`

**Interfaces:**
- Consumes: `start_web_console_service(args) -> dict[str, Any]`, `build_web_status_payload(ctx) -> dict[str, Any]`, `run_web_console(args) -> None`
- Produces:
  - `public_url: str`
  - `backend_url: str`
  - `active_repo_root: str`
  - `already_running: bool`
  - `replaced_existing: bool`

- [ ] **Step 1: Write the failing lifecycle tests**

```python
# tests/test_cli_lifecycle.py
    def test_web_start_uses_fixed_public_entrypoint(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
        )

        self.assertEqual(ready["public_url"], "http://127.0.0.1:6006")
        self.assertIn("backend_url", ready)
        self.assertEqual(ready["active_repo_root"], str(self.repo.resolve()))

    def test_web_start_reuses_same_repo_and_replaces_other_repo(self) -> None:
        other_repo = self.make_repo()
        _, first = self.start_web_server(self.repo, "web", "--cwd", str(self.repo), "--port", "0", "--no-open")
        second = run_gitwarp(self.repo, "web", "status", "--cwd", str(self.repo))
        self.assertEqual(second["public_url"], "http://127.0.0.1:6006")
        self.assertEqual(second["active_repo_root"], str(self.repo.resolve()))

        takeover = run_gitwarp(other_repo, "web", "start", "--cwd", str(other_repo), "--port", "0", "--no-open")
        self.assertTrue(takeover["replaced_existing"])
        self.assertEqual(takeover["active_repo_root"], str(other_repo.resolve()))
```

- [ ] **Step 2: Run the lifecycle tests to verify they fail**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_cli_lifecycle.py' -v
```

Expected: FAIL because readiness payload only exposes `url` and has no fixed public entrypoint behavior.

- [ ] **Step 3: Add global fixed-entry state helpers**

```python
# src/gitwarp/infrastructure/runtime.py
GLOBAL_WEB_STATE_FILENAME = "web-console-global-state.json"

...

def global_web_state_path() -> Path:
    return gitwarp_home_path() / GLOBAL_WEB_STATE_FILENAME
```

- [ ] **Step 4: Implement fixed-entry takeover logic in lifecycle**

```python
# src/gitwarp/webapp/lifecycle.py
DEFAULT_PUBLIC_WEB_HOST = "127.0.0.1"
DEFAULT_PUBLIC_WEB_PORT = 6006

...

def start_web_console_service(args: Any) -> dict[str, Any]:
    ctx = discover_repo(resolve_path(args.cwd))
    public_host = DEFAULT_PUBLIC_WEB_HOST if str(args.host) == "127.0.0.1" else str(args.host)
    public_port = DEFAULT_PUBLIC_WEB_PORT
    backend_port = int(args.port)
    ...
    state = {
        "pid": result.pid,
        "public_url": f"http://{public_host}:{public_port}",
        "backend_url": readiness.get("url"),
        "host": public_host,
        "port": public_port,
        "backend_port": readiness.get("port"),
        "repo_root": str(ctx.repo_root),
        "active_repo_root": str(ctx.repo_root),
        "readonly": readiness.get("readonly"),
        "registry_path": readiness.get("registry_path"),
        "replaced_existing": replaced_existing,
        "already_running": False,
        "started_at": now_iso(),
    }
```

Use a home-level fixed-entry state file so a second repo can detect and replace the active repo. Reuse repo-local state for stop/status, but include the fixed public entrypoint fields in both places.

- [ ] **Step 5: Extend readiness payload and status payload**

```python
# src/gitwarp/webapp/server.py
print(json.dumps({
    "ok": True,
    "url": backend_url,
    "backend_url": backend_url,
    "public_url": public_url,
    "host": args.host,
    "port": backend_port,
    "public_port": public_port,
    "repo_root": str(ctx.repo_root),
    "active_repo_root": str(ctx.repo_root),
    "readonly": bool(args.readonly),
    "registry_path": str(registry_path),
}, ...))
```

- [ ] **Step 6: Run focused tests to verify the new lifecycle**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_cli_lifecycle.py' -v
python3 -m unittest discover -s tests -p 'test_web_api.py' -v
```

Expected: PASS, including fixed public URL assertions and repo takeover semantics.

- [ ] **Step 7: Commit**

```bash
git add src/gitwarp/infrastructure/runtime.py src/gitwarp/webapp/lifecycle.py src/gitwarp/webapp/server.py src/gitwarp/adapters/cli/system.py tests/test_cli_lifecycle.py tests/test_web_api.py
git commit -m "feat: add fixed gitwarp web entrypoint"
```

## Task 3: Add non-destructive reload for CLI and Web

**Files:**
- Create: `src/gitwarp/application/use_cases/reload.py`
- Modify: `src/gitwarp/application/use_cases/__init__.py:1-80`
- Modify: `src/gitwarp/adapters/cli/parser.py:240-310`
- Modify: `src/gitwarp/adapters/cli/system.py:1-100`
- Modify: `src/gitwarp/webapp/contracts.py:25-140`
- Modify: `src/gitwarp/webapp/controllers.py:120-250`
- Modify: `tests/test_cli_lifecycle.py:1-420`
- Modify: `tests/test_web_api.py:1-420`

**Interfaces:**
- Consumes: `discover_repo(cwd: Path) -> RepoContext`, `build_init_payload(ctx, write_gitignore: bool) -> dict[str, Any]`, `build_web_state_payload(cwd, readonly=False) -> dict[str, Any]`
- Produces:
  - `build_reload_payload(ctx: RepoContext) -> dict[str, Any]`
  - CLI `gitwarp reload`
  - Web `POST /api/reload`

- [ ] **Step 1: Write the failing reload tests**

```python
# tests/test_cli_lifecycle.py
    def test_reload_re_registers_repo_without_destructive_cleanup(self) -> None:
        run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        registry_path = self.repo / ".gitwarp-test-home" / "projects.json"
        registry_path.unlink()

        payload = run_gitwarp(self.repo, "reload", "--cwd", str(self.repo))

        self.assertTrue(payload["reloaded"])
        self.assertTrue(payload["registered"]["added_new"] or payload["registered"]["refreshed"])
        self.assertEqual(payload["repo_root"], str(self.repo.resolve()))

# tests/test_web_api.py
    def test_web_reload_repairs_state_without_deleting_entries(self) -> None:
        _, ready = self.start_web_server(self.repo, "web", "--cwd", str(self.repo), "--port", "0", "--no-open")
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])
        status, payload = self.fetch_web_json(str(ready["url"]), "/api/reload", method="POST", token=token, data={})
        self.assertEqual(status, 200)
        self.assertTrue(payload["reloaded"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_cli_lifecycle.py' -v
python3 -m unittest discover -s tests -p 'test_web_api.py' -v
```

Expected: FAIL because `reload` command and `/api/reload` do not exist yet.

- [ ] **Step 3: Implement the shared reload use case**

```python
# src/gitwarp/application/use_cases/reload.py
from __future__ import annotations

from typing import Any

from ...infrastructure.ledger import load_project_registry, project_registry_path, register_project
from ...infrastructure.runtime import RepoContext
from .init import build_init_payload


def build_reload_payload(ctx: RepoContext) -> dict[str, Any]:
    init_payload = build_init_payload(ctx, write_gitignore=False)
    registry = load_project_registry(project_registry_path())
    existing = any(item.get("repo_root") == str(ctx.repo_root) for item in registry["projects"])
    registry_path = register_project(ctx.repo_root, name=ctx.repo_root.name)
    return {
        **init_payload,
        "reloaded": True,
        "registry_path": str(registry_path),
        "registered": {
            "name": ctx.repo_root.name,
            "added_new": not existing,
            "refreshed": existing,
            "position": 0,
        },
    }
```

This intentionally reuses `build_init_payload()` for safe runtime/bootstrap repair and adds only non-destructive registry refresh semantics.

- [ ] **Step 4: Wire CLI and Web endpoints**

```python
# src/gitwarp/adapters/cli/parser.py
reload_cmd = subparsers.add_parser("reload", help="Rescan Git and GitWarp state, then repair safe missing metadata")
reload_cmd.add_argument("--cwd")
reload_cmd.set_defaults(func=cmd_reload)

# src/gitwarp/adapters/cli/system.py
def cmd_reload(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_reload_payload(ctx))

# src/gitwarp/webapp/contracts.py
"/api/reload": EndpointSpec("POST", True),

# src/gitwarp/webapp/controllers.py
if path == "/api/reload":
    return build_reload_payload(ctx)
```

- [ ] **Step 5: Run focused tests to verify reload works**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_cli_lifecycle.py' -v
python3 -m unittest discover -s tests -p 'test_web_api.py' -v
```

Expected: PASS, and no test should show worktree/dossier deletion side effects.

- [ ] **Step 6: Commit**

```bash
git add src/gitwarp/application/use_cases/reload.py src/gitwarp/application/use_cases/__init__.py src/gitwarp/adapters/cli/parser.py src/gitwarp/adapters/cli/system.py src/gitwarp/webapp/contracts.py src/gitwarp/webapp/controllers.py tests/test_cli_lifecycle.py tests/test_web_api.py
git commit -m "feat: add non-destructive gitwarp reload"
```

## Task 4: Keep unmanaged branches visible in Web

**Files:**
- Modify: `src/gitwarp/application/use_cases/web_state.py:1-320`
- Modify: `web/console/src/app/types.ts:1-260`
- Modify: `web/console/src/app/components/BranchesPanel.tsx:1-320`
- Modify: `tests/test_web_api.py:260-420`
- Modify: `tests/test_packaging.py:377-449`

**Interfaces:**
- Consumes: `MatrixPayload.rows`, `MatrixRow.classification_basis`, `MatrixRow.recommended_action`
- Produces:
  - grouped unmanaged branch metadata in Web state / matrix payload
  - `Unmanaged / Other Branches` UI section

- [ ] **Step 1: Write the failing Web visibility tests**

```python
# tests/test_web_api.py
    def test_web_matrix_groups_unknown_refs_as_unmanaged_other_branches(self) -> None:
        run_git(self.repo, "branch", "feature/unmanaged-one")
        run_git(self.repo, "branch", "feature/unmanaged-two")

        services = load_gitwarp_services()
        payload = services.build_web_state_payload(self.repo, readonly=True)
        unmanaged = payload["matrix"]["groups"]["unmanaged_branches"]

        self.assertEqual([row["branch"] for row in unmanaged], ["feature/unmanaged-one", "feature/unmanaged-two"])
        self.assertTrue(all(row["managed_state"] == "unmanaged" for row in unmanaged))
```

- [ ] **Step 2: Run the failing tests**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_web_api.py' -v
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
```

Expected: FAIL because there is no `unmanaged_branches` grouping or dedicated UI copy yet.

- [ ] **Step 3: Extend payload shaping for grouped unmanaged branches**

```python
# src/gitwarp/application/use_cases/web_state.py

def group_matrix_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "base_branches": [row for row in rows if row.get("managed_state") == "base"],
        "task_branches": [row for row in rows if row.get("managed_state") == "task"],
        "unmanaged_branches": [
            row for row in rows
            if row.get("managed_state") not in {"base", "task"} and row.get("git", {}).get("branch_ref")
        ],
    }
```

Add the grouped structure alongside the existing flat matrix rows so the UI can render both summary metrics and explicit unmanaged sections.

- [ ] **Step 4: Render the dedicated UI section**

```tsx
// web/console/src/app/components/BranchesPanel.tsx
const unmanagedRows = payload?.groups?.unmanaged_branches ?? [];
...
{unmanagedRows.length > 0 ? (
  <section className="branch-subsection" aria-label="Unmanaged or other branches">
    <h3>Unmanaged / Other Branches</h3>
    <p className="muted-hint">These refs exist in Git but are not classified as GitWarp base or task branches.</p>
    {unmanagedRows.map((row) => (
      <MatrixRowView ... />
    ))}
  </section>
) : null}
```

- [ ] **Step 5: Add packaging assertions for the new copy**

```python
# tests/test_packaging.py
        self.assertIn("Unmanaged / Other Branches", branches_panel)
        self.assertIn("not classified as GitWarp base or task branches", branches_panel)
```

- [ ] **Step 6: Run focused tests to verify visibility**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_web_api.py' -v
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
cd web/console && npm run build
```

Expected: PASS, and the build should succeed without type errors.

- [ ] **Step 7: Commit**

```bash
git add src/gitwarp/application/use_cases/web_state.py web/console/src/app/types.ts web/console/src/app/components/BranchesPanel.tsx tests/test_web_api.py tests/test_packaging.py
git commit -m "feat: keep unmanaged branches visible in web"
```

## Task 5: Document public entrypoint and reload behavior, then verify release gate

**Files:**
- Modify: `README.md:30-220`
- Modify: `skills/gitwarp/SKILL.md:20-280`
- Modify: `web/README.md:1-40`
- Test: `tests/test_packaging.py`

**Interfaces:**
- Consumes: CLI/Web behavior from Tasks 2-4
- Produces: user/operator docs that match the shipped behavior and fixed-entry semantics.

- [ ] **Step 1: Write the failing packaging/documentation assertions**

```python
# tests/test_packaging.py
        self.assertIn("127.0.0.1:6006", readme)
        self.assertIn("gitwarp reload", readme)
        self.assertIn("Unmanaged / Other Branches", web_readme)
        self.assertIn("every user-visible change must bump version", skill)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
```

Expected: FAIL because the new docs/copy do not exist yet.

- [ ] **Step 3: Update user-facing docs**

```markdown
# README.md
gitwarp web start
# Open http://127.0.0.1:6006

gitwarp reload
# Rescan Git and GitWarp state, repair safe missing metadata, do not delete anything.
```

```markdown
# skills/gitwarp/SKILL.md
- `gitwarp reload` | Re-read Git, ledger, dossiers, and registry; repair safe missing metadata without destructive cleanup. |
- `gitwarp web start` serves a stable public entrypoint at `http://127.0.0.1:6006`.
- Every user-visible change must bump `src/gitwarp/__init__.py::__version__`.
```

```markdown
# web/README.md
Project Directory and branch views preserve `Unmanaged / Other Branches` so unknown refs do not disappear from supervision.
```

- [ ] **Step 4: Run focused checks and the full release gate**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
cd web/console && npm run build
cd web/console && npm run check:dist
scripts/check-release.sh
```

Expected: PASS, including `159 tests OK` or the current full-suite equivalent.

- [ ] **Step 5: Commit**

```bash
git add README.md skills/gitwarp/SKILL.md web/README.md tests/test_packaging.py
git commit -m "docs: explain fixed web entry and reload"
```

## Self-Review

- Spec coverage: all four approved design pillars are mapped to tasks — fixed entrypoint (Task 2), reload (Task 3), unmanaged branches (Task 4), and version policy (Task 1 + Task 5). No spec section is left without an implementation task.
- Placeholder scan: no `TODO`, `TBD`, “add tests later”, or unnamed interfaces remain in the plan.
- Type consistency: later tasks consistently refer to `public_url`, `backend_url`, `active_repo_root`, `build_reload_payload(ctx)`, and `unmanaged_branches`; no alternate names are introduced.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-24-web-entry-reload-version-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?