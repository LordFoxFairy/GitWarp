# Project Directory dead-entry handling + branch-first Branches view

Date: 2026-06-28
Status: accepted (autonomous; user requested completion without mid-way interaction)

## Problem

1. The Web Project Directory lists every entry in the global registry
   `~/.gitwarp/projects.json` without checking whether the directory still
   exists. Test pollution (now fixed at the source) had filled the registry
   with 1600+ dead temp-dir entries, drowning real projects and making the
   `add` feature feel useless. There is no way to remove a registry entry from
   the web UI, and no existence validation.
2. The backend already emits `branch_groups` (primary/base/task/unmanaged) and
   `sandbox_groups`, and the tabs were renamed to a branch-first IA
   (Branches/Sandboxes/Repository/Diagnostics), but the Branches panel still
   renders a single flat control-plane matrix instead of the branch-first
   sections the design calls for.

## Part A — Dead-entry handling

### Backend
- `infrastructure/ledger.py`
  - `unregister_project(repo_root, *, path=None) -> tuple[Path, int]`: remove all
    entries matching `repo_root`; returns registry path and removed count.
  - `prune_missing_projects(*, path=None) -> tuple[Path, list[str]]`: drop every
    entry whose `repo_root` is not an existing directory; returns removed roots.
- `application/use_cases/projects.py` (new)
  - `build_forget_project_payload(repo_root, *, prune_missing) -> dict`: dispatch
    to the two ledger helpers. `prune_missing=True` ignores `repo_root`.
- `application/use_cases/web_state.py`
  - Every project summary carries `exists: bool` (`Path(repo_root).is_dir()`),
    computed independently of `discover_repo` so it agrees with prune semantics.
- `webapp/contracts.py` + `webapp/controllers.py`
  - New mutation endpoint `POST /api/forget-project` with optional `repo_root`
    (string) and optional `prune_missing` (boolean). Mutates the registry only;
    it never touches repository contents, so no destructive-confirmation token is
    required (consistent with how `/api/add` registers without one).

### Frontend
- `types.ts`: `ProjectSummary.exists?: boolean`.
- `gitwarp-api.ts`: `forgetProject(repoRoot)`, `pruneMissingProjects()`.
- `ProjectDirectory.tsx`: dead rows show a "missing" badge, disable Open, and
  expose a per-row Remove button; a header action "Remove missing (N)" appears
  when any dead entries exist.
- `App.tsx`: wires the two handlers, refreshing state afterwards.

Non-mutating reads stay non-mutating: existence is only surfaced, never
auto-pruned. Cleanup is always an explicit user action.

## Part B — Branch-first Branches view

`BranchesPanel.tsx` regroups the matrix rows into four labelled sections —
Primary / Base Branches / Task Branches / Unmanaged & Other — using the same
predicates as `group_branch_assets` (category `main`; role `base` & not main;
role `task`; `managed_state == "unmanaged"`). The control-plane summary
(default branch, sources, prunable counts) and the cleanup-base picker remain as
the panel header; per-row rendering and prune confirmation are unchanged
(`MatrixRowView`). Sandboxes (the renamed Metadata panel) is already
execution-first and is left as-is.

## Testing
- New ledger unit tests for `unregister_project` / `prune_missing_projects`.
- New web API tests: `/api/forget-project` removes one entry and prunes missing;
  schema advertises the endpoint; state payload carries `exists`.
- Packaging test updated for the branch-first section headings.
- Full `unittest` suite + `npm run build` + `check:dist` + Playwright main path.
