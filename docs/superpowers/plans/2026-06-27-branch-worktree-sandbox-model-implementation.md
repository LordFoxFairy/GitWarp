# Branch Worktree Sandbox Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align GitWarp’s branch/worktree/sandbox model with native Git/GitHub semantics so branches remain the asset layer, sandboxes remain managed worktrees, unmanaged refs stay visible, and instruction mounting never breaks worktree isolation.

**Architecture:** Keep Git as the source of truth: branches are refs, worktrees are isolated directories, and GitWarp only adds metadata, dossier, and workflow semantics on top. Rework CLI/Web presentation so `branches` is branch-first, `board` is sandbox-first, and unmanaged branches are explicit. Remove any remaining product behavior or wording that reintroduces shared mutable state between worktrees.

**Tech Stack:** Python 3.10+, standard library, Git CLI, current GitWarp DDD layers, React + TypeScript + Primer, unittest, Vite.

## Global Constraints

- Git branch remains the primary code asset model; GitWarp must not replace it with sandbox-first language in human-facing entrypoints.
- Git worktree remains the isolation boundary; GitWarp must not reintroduce shared mutable state between worktrees.
- GitWarp sandbox means a GitWarp-managed worktree with ledger + dossier metadata; unmanaged worktrees must not be mislabeled as sandboxes.
- Unknown / unmanaged branches must remain visible in CLI/Web and must not be silently reclassified as `base`.
- Instruction files mounted into worktrees must remain copy-only.
- CLI, Web, and docs must consistently distinguish branch, worktree, sandbox, and agent.
- Run focused tests first, then `scripts/check-release.sh` before claiming completion.

---

## File Structure

- `src/gitwarp/application/use_cases/branches.py` — branch asset classification and unmanaged/base/task rules.
- `src/gitwarp/application/use_cases/web_state.py` — branch-first and sandbox-first payload shaping for Web.
- `src/gitwarp/application/use_cases/matrix.py` — keep diagnostic role explicit while exposing row grouping for UI.
- `src/gitwarp/adapters/cli/read.py` / `src/gitwarp/adapters/presenters.py` — if needed, refine human-facing `branches` / `board` formatting text.
- `web/console/src/app/components/BranchesPanel.tsx` — branch-first display and unmanaged sections.
- `web/console/src/app/components/CodePanel.tsx` / `RepositoryHeader.tsx` / `RepositoryTabs.tsx` — if needed, rename tabs/labels to separate Branches vs Sandboxes vs Diagnostics.
- `web/console/src/app/types.ts` — explicit payload types for branch and sandbox groupings.
- `README.md` — human-facing product model.
- `skills/gitwarp/SKILL.md` — agent-facing model and rules.
- `tests/test_branches.py` — branch asset classification tests.
- `tests/test_matrix.py` — diagnostic matrix expectations.
- `tests/test_web_api.py` — branch visibility and Web grouping tests.
- `tests/test_packaging.py` — UI/text surface assertions.

## Task 1: Make CLI branch inventory explicitly asset-first

**Files:**
- Modify: `src/gitwarp/application/use_cases/branches.py`
- Modify: `tests/test_branches.py`
- Modify: `tests/test_matrix.py` (only if matrix/branch role interactions need updated expectations)

**Interfaces:**
- Consumes: `build_branches_payload(ctx, base_branch=None) -> dict[str, Any]`
- Produces: branch rows whose `category`, `branch_role`, `managed_state`, and `classification_basis` keep branch assets visible without auto-promoting unmanaged refs to `base`.

- [ ] **Step 1: Write the failing branch classification test**

```python
# tests/test_branches.py
    def test_unknown_branch_refs_remain_visible_and_unmanaged(self) -> None:
        run_git(self.repo, "branch", "feature/manual-visible")
        run_git(self.repo, "branch", "legacy/manual-visible")

        payload = run_gitwarp(self.repo, "branches", "--cwd", str(self.repo))
        rows = {row["name"]: row for row in payload["branches"]}

        self.assertEqual(rows["feature/manual-visible"]["managed_state"], "unmanaged")
        self.assertEqual(rows["legacy/manual-visible"]["managed_state"], "unmanaged")
        self.assertNotEqual(rows["feature/manual-visible"]["branch_role"], "base")
        self.assertNotEqual(rows["legacy/manual-visible"]["branch_role"], "base")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_branches.py' -v
```

Expected: FAIL if unknown refs are still auto-promoted into task/base language in ways that hide their unmanaged nature.

- [ ] **Step 3: Implement minimal branch role/classification fix**

```python
# src/gitwarp/application/use_cases/branches.py

def resolve_branch_role(...):
    if is_default or is_merge_base:
        return BASE_ROLE
    if live is not None and isinstance(live.get("branch_role"), str):
        return str(live["branch_role"])
    if isinstance(ledger_entry.get("branch_role"), str):
        return str(ledger_entry["branch_role"])
    return None


def categorize_branch(row: dict[str, Any]) -> str:
    if row["is_default"]:
        return "base"
    if row["branch_role"] == BASE_ROLE:
        return "base"
    if row["branch_role"] == TASK_ROLE:
        return "active" if (row["has_worktree"] or row["in_ledger"]) else "merged" if row["merged_to_base"] else "orphan"
    return "unmanaged"
```

Keep unmanaged refs visible without silently assigning them to `base`.

- [ ] **Step 4: Run focused tests to verify it passes**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_branches.py' -v
python3 -m unittest discover -s tests -p 'test_matrix.py' -v
```

Expected: PASS, including the new unmanaged branch coverage.

- [ ] **Step 5: Commit**

```bash
git add src/gitwarp/application/use_cases/branches.py tests/test_branches.py tests/test_matrix.py
git commit -m "fix: keep unmanaged branches visible in cli"
```

## Task 2: Shape Web payloads into asset-first branches and sandbox-first execution views

**Files:**
- Modify: `src/gitwarp/application/use_cases/web_state.py`
- Modify: `src/gitwarp/application/use_cases/matrix.py`
- Modify: `web/console/src/app/types.ts`
- Modify: `tests/test_web_api.py`

**Interfaces:**
- Consumes: `build_web_state_payload(cwd, readonly=False)`, `build_matrix_payload(ctx)`
- Produces:
  - explicit `branch_groups`
  - explicit `sandbox_groups`
  - diagnostic matrix row groups that do not hide unmanaged refs

- [ ] **Step 1: Write the failing Web payload test**

```python
# tests/test_web_api.py
    def test_web_state_distinguishes_branch_assets_from_sandbox_execution(self) -> None:
        run_git(self.repo, "branch", "feature/manual-asset")
        task = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-asset-task",
            "--branch",
            "agent/execution-task",
            "--purpose",
            "Execution sandbox",
        )

        services = load_gitwarp_services()
        payload = services.build_web_state_payload(self.repo, readonly=True)

        self.assertIn("branch_groups", payload)
        self.assertIn("sandbox_groups", payload)
        self.assertEqual(payload["branch_groups"]["unmanaged"][0]["branch"], "feature/manual-asset")
        self.assertEqual(payload["sandbox_groups"]["managed"][0]["branch"], "agent/execution-task")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_web_api.py' -v
```

Expected: FAIL because payload does not yet separate assets from execution views.

- [ ] **Step 3: Implement grouped payloads**

```python
# src/gitwarp/application/use_cases/web_state.py

def group_branch_assets(matrix_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "primary": [row for row in matrix_rows if row.get("category") == "main"],
        "base": [row for row in matrix_rows if row.get("role") == "base" and row.get("category") != "main"],
        "task": [row for row in matrix_rows if row.get("role") == "task"],
        "unmanaged": [row for row in matrix_rows if row.get("managed_state") == "unmanaged"],
    }


def group_sandboxes(worktree_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "managed": [row for row in worktree_rows if not row.get("is_main") and row.get("branch_role") in {"base", "task"}],
        "unmanaged": [row for row in worktree_rows if not row.get("is_main") and row.get("branch_role") not in {"base", "task"}],
    }
```

Attach these groups to the Web payload. Keep matrix itself diagnostic-first.

- [ ] **Step 4: Run focused tests to verify grouped payloads**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_web_api.py' -v
```

Expected: PASS, including explicit branch/sandbox grouping.

- [ ] **Step 5: Commit**

```bash
git add src/gitwarp/application/use_cases/web_state.py src/gitwarp/application/use_cases/matrix.py web/console/src/app/types.ts tests/test_web_api.py
git commit -m "feat: split branch and sandbox web views"
```

## Task 3: Rename and reorganize Web UI around branch-first and sandbox-first views

**Files:**
- Modify: `web/console/src/app/App.tsx`
- Modify: `web/console/src/app/components/BranchesPanel.tsx`
- Modify: `web/console/src/app/components/RepositoryTabs.tsx`
- Modify: `web/console/src/app/components/RepositoryHeader.tsx` (only if labels need to change)
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Consumes: Web payload groupings from Task 2.
- Produces: explicit “Branches” and “Sandboxes” language in UI, with unmanaged branch sections preserved.

- [ ] **Step 1: Write the failing packaging/UI assertions**

```python
# tests/test_packaging.py
        self.assertIn("Branches", tabs)
        self.assertIn("Sandboxes", tabs)
        self.assertIn("Unmanaged / Other Branches", branches_panel)
        self.assertIn("GitWarp-managed worktree", app)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
cd web/console && npm run build
```

Expected: FAIL because current UI text still mixes branch/worktree semantics.

- [ ] **Step 3: Implement the minimal UI rename/restructure**

```tsx
// web/console/src/app/components/RepositoryTabs.tsx
const tabs = [
  { id: "branches", label: "Branches" },
  { id: "metadata", label: "Sandboxes" },
  { id: "code", label: "Repository" },
  { id: "health", label: "Diagnostics" },
]

// web/console/src/app/App.tsx
const [activeTab, setActiveTab] = useState<RepositoryTab>("branches")
```

In `BranchesPanel.tsx`, render the grouped branch sections (`primary`, `base`, `task`, `unmanaged`) with clear headings, and reserve sandbox-specific actions/details for the sandbox-oriented panel.

- [ ] **Step 4: Run focused UI checks**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
cd web/console && npm run build
cd web/console && npm run check:dist
```

Expected: PASS, including the updated product language assertions.

- [ ] **Step 5: Commit**

```bash
git add web/console/src/app/App.tsx web/console/src/app/components/BranchesPanel.tsx web/console/src/app/components/RepositoryTabs.tsx web/console/src/app/components/RepositoryHeader.tsx tests/test_packaging.py
git commit -m "feat: make web branch-first for humans"
```

## Task 4: Align CLI/Web/docs language with the Git-first model

**Files:**
- Modify: `README.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `web/README.md`
- Modify: `src/gitwarp/adapters/cli/parser.py` (help text only if needed)
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Consumes: approved object model from the spec.
- Produces: human- and agent-facing language that consistently says GitWarp wraps Git worktrees instead of replacing Git branch semantics.

- [ ] **Step 1: Write the failing documentation assertions**

```python
# tests/test_packaging.py
        self.assertIn("Git branch remains the code asset model", readme)
        self.assertIn("sandbox means a GitWarp-managed worktree", skill)
        self.assertIn("GitWarp wraps git worktree", web_readme)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
```

Expected: FAIL because the exact Git-first language is not in docs yet.

- [ ] **Step 3: Update the docs and help text**

```markdown
# README.md
Git branch remains the primary code asset model. Git worktrees are isolated directories. GitWarp sandboxes are managed worktrees layered on top of Git.
```

```markdown
# skills/gitwarp/SKILL.md
GitWarp wraps Git worktrees with ledger, dossier, and agent workflow metadata. It does not replace Git’s branch model.
A sandbox means a GitWarp-managed worktree.
```

```markdown
# web/README.md
GitWarp wraps git worktree behavior for supervised sandbox management; it should not hide unmanaged branches or blur the distinction between branch assets and sandbox execution views.
```

- [ ] **Step 4: Run focused checks and the full release gate**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
cd web/console && npm run build
cd web/console && npm run check:dist
scripts/check-release.sh
```

Expected: PASS, including the current full-suite equivalent.

- [ ] **Step 5: Commit**

```bash
git add README.md skills/gitwarp/SKILL.md web/README.md src/gitwarp/adapters/cli/parser.py tests/test_packaging.py
git commit -m "docs: align gitwarp language with git worktree model"
```

## Self-Review

- Spec coverage: object model, branch/task/base/unmanaged rules, branch-first CLI/Web surfaces, and worktree isolation are all mapped to tasks.
- Placeholder scan: no `TODO`, `TBD`, “fix later”, or undefined interfaces remain.
- Type consistency: the plan consistently uses branch, worktree, sandbox, unmanaged, `branch_groups`, and `sandbox_groups` without alternate names.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-27-branch-worktree-sandbox-model-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?