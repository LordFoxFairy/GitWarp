# GitWarp Agent Task Inbox Implementation Plan

> **For agentic workers:** REQUIRED: Use @superpowers:subagent-driven-development (if subagents available) or @superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `gitwarp task create` as the recommended high-level task intake flow for isolated agent work.

**Architecture:** Implement task intake as a thin application use case above existing provisioning. The new flow normalizes task metadata, validates branch safety, delegates worktree creation to the current start path, and renders richer dossiers. CLI and Web share the same use case; React calls the Web endpoint through typed API client methods.

**Tech Stack:** Python standard library, argparse, Git CLI, unittest, React 19, TypeScript, Primer React, Vite.

---

## Reference Documents

- Spec: `docs/superpowers/specs/2026-06-21-gitwarp-agent-task-inbox-design.md`
- Current provisioning: `src/gitwarp/application/use_cases/provisioning.py`
- Current dossier renderer: `src/gitwarp/infrastructure/dossiers.py`
- Current CLI adapter: `src/gitwarp/adapters/cli/parser.py`, `src/gitwarp/adapters/cli/workspaces.py`
- Current Web contract: `src/gitwarp/webapp/contracts.py`, `src/gitwarp/webapp/controllers.py`
- Current React action UI: `web/console/src/app/components/ActionPanel.tsx`

## File Structure

- Create `src/gitwarp/application/use_cases/tasks.py`: normalize task requests, generate defaults, validate branch rules, and call `build_start_payload`.
- Modify `src/gitwarp/domain/model.py`: persist optional task metadata on `WorkspaceRecord`.
- Modify `src/gitwarp/domain/policies.py`: add pure task title normalization and target-agent validation helpers.
- Modify `src/gitwarp/application/use_cases/provisioning.py`: accept optional task metadata and pass it to the ledger and dossier renderer.
- Modify `src/gitwarp/infrastructure/dossiers.py`: render richer task dossiers when task metadata exists, while keeping existing start/create dossiers compatible.
- Modify `src/gitwarp/application/use_cases/__init__.py`: export `build_task_create_payload`.
- Modify `src/gitwarp/adapters/cli/parser.py`: add nested `task create` parser.
- Modify `src/gitwarp/adapters/cli/workspaces.py`: add `cmd_task_create`.
- Create `tests/test_task_inbox.py`: CLI/application coverage for task intake.
- Modify `src/gitwarp/webapp/contracts.py`: add `/api/task/create` schema.
- Modify `src/gitwarp/webapp/controllers.py`: route `/api/task/create` to the shared use case.
- Modify `tests/test_web_api.py`: Web API success, schema, read-only, CSRF, unknown field, and wrong-type coverage.
- Modify `web/console/src/app/gitwarp-api.ts`: add `TaskCreateInput` and `createTask`.
- Modify `web/console/src/app/App.tsx`, `web/console/src/app/components/MetadataPanel.tsx`, `web/console/src/app/components/ActionPanel.tsx`: wire and display Create Task as the primary action.
- Modify `web/console/src/app/types.ts`: add optional task metadata fields to `WorktreeRow` if needed by UI.
- Regenerate `web/console/dist/*` and `src/gitwarp/assets/web_console/*` through `npm run build`.
- Modify `README.md` and `skills/gitwarp/SKILL.md`: make `gitwarp task create` the preferred new-work entry point.

## Chunk 1: Domain, Application, CLI, And Dossier

### Task 1: Add Failing Task Intake CLI Tests

**Files:**
- Create: `tests/test_task_inbox.py`

- [ ] **Step 1: Write task creation success test**

```python
from __future__ import annotations

from pathlib import Path

from helpers import *


class TaskInboxTests(GitWarpTestCase):
    def test_task_create_generates_names_and_rich_dossier(self) -> None:
        payload = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Polish matrix web UX",
            "--description",
            "Make branch and worktree state easier to understand",
            "--acceptance",
            "Web shows refs, worktrees, ledger rows, and dossiers clearly",
            "--verify",
            "python3 -m unittest discover -s tests -p 'test_*.py' -v",
            "--agent",
            "codex",
        )

        self.assertEqual(payload["branch"], "agent/polish-matrix-web-ux")
        self.assertEqual(payload["agent_id"], "agent-polish-matrix-web-ux")
        self.assertEqual(payload["target_agent"], "codex")
        self.assertEqual(payload["base_branch"], "main")
        self.assertEqual(payload["purpose"], "Make branch and worktree state easier to understand")
        self.assertEqual(payload["task_title"], "Polish matrix web UX")
        self.assertEqual(payload["task_description"], "Make branch and worktree state easier to understand")
        self.assertEqual(payload["acceptance_criteria"], ["Web shows refs, worktrees, ledger rows, and dossiers clearly"])
        self.assertEqual(payload["verification_commands"], ["python3 -m unittest discover -s tests -p 'test_*.py' -v"])
        self.assertEqual(payload["branch_role"], "task")
        self.assertTrue(str(payload["shell_command"]).startswith("cd "))

        task_md = Path(str(payload["task_md"])).read_text(encoding="utf-8")
        self.assertIn("## Objective", task_md)
        self.assertIn("Polish matrix web UX", task_md)
        self.assertIn("- Target Agent: codex", task_md)
        self.assertIn("- [ ] Web shows refs, worktrees, ledger rows, and dossiers clearly", task_md)
        self.assertIn("- [ ] `python3 -m unittest discover -s tests -p 'test_*.py' -v`", task_md)
        self.assertIn("Leave the task worktree for human review", task_md)

        progress_md = Path(str(payload["progress_md"])).read_text(encoding="utf-8")
        self.assertIn("Task created: Polish matrix web UX", progress_md)
        self.assertIn("Parent base: main", progress_md)
```

- [ ] **Step 2: Write branch safety and explicit reuse test**

```python
    def test_task_create_generated_branch_ref_must_be_unused_but_explicit_can_reuse(self) -> None:
        run_git(self.repo, "branch", "agent/reuse-me")

        generated = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Reuse Me",
            expect_ok=False,
        )
        self.assertIn("generated branch already exists", str(generated["error"]))

        explicit = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Reuse prepared ref",
            "--branch",
            "agent/reuse-me",
        )
        self.assertEqual(explicit["branch"], "agent/reuse-me")
        self.assertEqual(explicit["branch_created"], False)

    def test_task_create_live_branch_collision_does_not_mutate_control_plane(self) -> None:
        existing = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/live-collision",
            "--purpose",
            "Existing live task",
        )
        before_ledger = (self.repo / ".gitwarp" / "ledger.json").read_text(encoding="utf-8")
        before_dossiers = sorted(path.name for path in (self.repo / ".gitwarp" / "dossiers").iterdir())

        collision = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Live Collision",
            "--branch",
            "agent/live-collision",
            expect_ok=False,
        )

        self.assertIn("branch collision", str(collision["error"]))
        self.assertEqual((self.repo / ".gitwarp" / "ledger.json").read_text(encoding="utf-8"), before_ledger)
        self.assertEqual(sorted(path.name for path in (self.repo / ".gitwarp" / "dossiers").iterdir()), before_dossiers)
        self.assertTrue(Path(str(existing["path"])).exists())
```

- [ ] **Step 3: Write normalization and blank optional string test**

```python
    def test_task_create_normalization_and_blank_optional_values(self) -> None:
        payload = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "修复 Web 闪动",
            "--description",
            "   ",
            "--purpose",
            "   ",
        )
        self.assertEqual(payload["branch"], "agent/web")
        self.assertEqual(payload["agent_id"], "agent-web")
        self.assertEqual(payload["purpose"], "修复 Web 闪动")

        invalid = run_gitwarp(self.repo, "task", "create", "--title", "!!!", expect_ok=False)
        self.assertIn("normalizes to an empty slug", str(invalid["error"]))

        explicit_invalid = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "!!!",
            "--branch",
            "agent/explicit-invalid",
            "--agent-id",
            "agent-explicit-invalid",
            expect_ok=False,
        )
        self.assertIn("normalizes to an empty slug", str(explicit_invalid["error"]))
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "agent" / "explicit-invalid").exists())

        blank = run_gitwarp(self.repo, "task", "create", "--title", "   ", expect_ok=False)
        self.assertIn("title must not be blank", str(blank["error"]))
```

- [ ] **Step 4: Write ref-format and target-agent validation test**

```python
    def test_task_create_validates_ref_format_and_target_agent_before_mutation(self) -> None:
        bad_branch = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Bad branch",
            "--branch",
            "foo..bar",
            expect_ok=False,
        )
        self.assertIn("invalid branch", str(bad_branch["error"]))

        bad_agent = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Bad agent",
            "--agent",
            "gemini",
            expect_ok=False,
        )
        self.assertIn("target_agent must be one of", str(bad_agent["error"]))
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "agent" / "bad-agent").exists())
```

- [ ] **Step 5: Write instruction mount and rollback test**

```python
    def test_task_create_mounts_instructions_and_rolls_back_on_instruction_failure(self) -> None:
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "agent.md").write_text("rules\n", encoding="utf-8")
        run_git(self.repo, "add", "docs/agent.md")
        run_git(self.repo, "commit", "-m", "add instruction")

        payload = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Instruction Mounts",
            "--instruction",
            "AGENTS.md=docs/agent.md",
        )
        self.assertEqual(payload["instructions"][0]["target"], "AGENTS.md")  # type: ignore[index]
        self.assertTrue(Path(str(payload["path"]), "AGENTS.md").exists())

        failed = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Missing Instruction",
            "--instruction",
            "missing.md",
            expect_ok=False,
        )
        self.assertIn("instruction source", str(failed["error"]))
        self.assertEqual(run_git(self.repo, "branch", "--list", "agent/missing-instruction"), "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "agent" / "missing-instruction").exists())

    def test_task_create_preserves_explicit_base_agent_and_instruction_metadata(self) -> None:
        base = run_gitwarp(
            self.repo,
            "create",
            "--role",
            "base",
            "--branch",
            "feature/user-request",
            "--purpose",
            "Coordinate user request",
        )
        (self.repo / "docs").mkdir(exist_ok=True)
        (self.repo / "docs" / "agent.md").write_text("rules\n", encoding="utf-8")
        run_git(self.repo, "add", "docs/agent.md")
        run_git(self.repo, "commit", "-m", "add explicit instruction")

        payload = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Explicit Task",
            "--base",
            str(base["branch"]),
            "--branch",
            "agent/explicit-task",
            "--agent-id",
            "codex-explicit-task",
            "--instruction",
            "AGENTS.md=docs/agent.md",
        )

        self.assertEqual(payload["base_branch"], "feature/user-request")
        self.assertEqual(payload["agent_id"], "codex-explicit-task")
        self.assertEqual(payload["branch"], "agent/explicit-task")
        self.assertEqual(payload["instructions"][0]["target"], "AGENTS.md")  # type: ignore[index]
        task_md = Path(str(payload["task_md"])).read_text(encoding="utf-8")
        self.assertIn("- Parent Base: feature/user-request", task_md)
        self.assertIn("`AGENTS.md` from", task_md)

    def test_task_create_slug_edge_cases(self) -> None:
        invalid = run_gitwarp(self.repo, "task", "create", "--title", ".", expect_ok=False)
        self.assertIn("normalizes to an empty slug", str(invalid["error"]))

        cases = {
            "foo..bar": "agent/foo-bar",
            "foo.lock": "agent/foo-lock",
            "foo.": "agent/foo",
        }
        for title, expected_branch in cases.items():
            with self.subTest(title=title):
                payload = run_gitwarp(self.repo, "task", "create", "--title", title)
                self.assertEqual(payload["branch"], expected_branch)
                run_gitwarp(self.repo, "remove", "--branch", str(payload["branch"]))

        long_title = "A" * 80
        payload = run_gitwarp(self.repo, "task", "create", "--title", long_title)
        self.assertLessEqual(len(str(payload["branch"]).removeprefix("agent/")), 64)
```

- [ ] **Step 6: Run failing tests**

Run: `python3 -m unittest tests.test_task_inbox -v`

Expected: FAIL because `gitwarp task` is not implemented.

### Task 2: Implement Task Request Normalization

**Files:**
- Modify: `src/gitwarp/domain/policies.py`
- Modify: `src/gitwarp/domain/model.py`
- Create: `src/gitwarp/application/use_cases/tasks.py`

- [ ] **Step 1: Add pure policy helpers**

Add to `src/gitwarp/domain/policies.py`:

```python
import re

TARGET_AGENTS = {"codex", "claude", "generic"}


def normalize_task_slug(title: str) -> str:
    if not title.strip():
        raise GitWarpError("title must not be blank")
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    slug = slug[:64].rstrip("-")
    if not slug:
        raise GitWarpError("title normalizes to an empty slug")
    return slug


def derive_task_branch(title: str) -> str:
    return f"agent/{normalize_task_slug(title)}"


def derive_task_agent_id(title: str) -> str:
    return f"agent-{normalize_task_slug(title)}"


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_target_agent(value: str | None) -> str:
    target = first_non_empty(value) or "generic"
    if target not in TARGET_AGENTS:
        raise GitWarpError("target_agent must be one of: codex, claude, generic")
    return target
```

- [ ] **Step 2: Add optional task metadata to `WorkspaceRecord`**

Add fields:

```python
    task_title: str | None = None
    task_description: str | None = None
    target_agent: str | None = None
    acceptance_criteria: list[str] | None = None
    verification_commands: list[str] | None = None
```

Update `from_mapping()` and `to_dict()` so the fields round-trip only when present.

- [ ] **Step 3: Add task request/use case**

Create `src/gitwarp/application/use_cases/tasks.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.policies import first_non_empty, normalize_task_slug, normalize_target_agent
from ...infrastructure.runtime import GitWarpError, RepoContext, run_git
from ...infrastructure.worktrees import branch_exists, ensure_branch_available, parse_worktrees
from .navigation import shell_cd_command
from .provisioning import build_start_payload


@dataclass(frozen=True)
class TaskCreateRequest:
    title: str
    description: str | None = None
    base_branch: str | None = None
    branch: str | None = None
    target_agent: str | None = None
    agent_id: str | None = None
    purpose: str | None = None
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    instruction_profile: str | None = None
    instruction_mode: str = "copy"


def _clean_list(values: list[str] | None) -> list[str]:
    return [item.strip() for item in (values or []) if item.strip()]


def _ensure_branch_ref_format(ctx: RepoContext, branch: str) -> None:
    try:
        run_git(ctx.repo_root, "check-ref-format", "--branch", branch)
    except GitWarpError as exc:
        raise GitWarpError(f"invalid branch '{branch}': {exc}") from exc


def build_task_create_payload(ctx: RepoContext, request: TaskCreateRequest) -> dict[str, object]:
    title = request.title.strip()
    if not title:
        raise GitWarpError("title must not be blank")
    slug = normalize_task_slug(title)

    generated_branch = request.branch is None or not request.branch.strip()
    branch = request.branch.strip() if request.branch and request.branch.strip() else f"agent/{slug}"
    agent_id = first_non_empty(request.agent_id) or f"agent-{slug}"
    purpose = first_non_empty(request.purpose, request.description, title)
    if purpose is None:
        raise GitWarpError("purpose could not be resolved")
    target_agent = normalize_target_agent(request.target_agent)
    description = first_non_empty(request.description)
    acceptance = _clean_list(request.acceptance_criteria)
    verification = _clean_list(request.verification_commands)

    _ensure_branch_ref_format(ctx, branch)
    ensure_branch_available(parse_worktrees(ctx), branch)
    if generated_branch and branch_exists(ctx, branch):
        raise GitWarpError(f"generated branch already exists: {branch}")

    payload = build_start_payload(
        ctx,
        agent_id=agent_id,
        branch=branch,
        purpose=purpose,
        base_branch=first_non_empty(request.base_branch),
        instructions=request.instructions,
        instruction_profile=first_non_empty(request.instruction_profile),
        instruction_mode=request.instruction_mode,
        task_title=title,
        task_description=description,
        target_agent=target_agent,
        acceptance_criteria=acceptance,
        verification_commands=verification,
    )
    payload["task_title"] = title
    payload["task_description"] = description
    payload["target_agent"] = target_agent
    payload["acceptance_criteria"] = acceptance
    payload["verification_commands"] = verification
    payload["shell_command"] = shell_cd_command(str(payload["path"]))
    return payload
```

Implementation note: preserve no-mutation validation before `build_start_payload`. Use `parse_worktrees(ctx)` directly for live worktree collision precheck; do not call `sync_ledger()` in this use case before the collision precheck because `sync_ledger()` may prune ledger/dossier state.

- [ ] **Step 4: Export the use case**

Modify `src/gitwarp/application/use_cases/__init__.py`:

```python
from .tasks import TaskCreateRequest, build_task_create_payload
```

Add both names to `__all__`.

### Task 3: Extend Provisioning And Dossiers For Task Metadata

**Files:**
- Modify: `src/gitwarp/application/use_cases/provisioning.py`
- Modify: `src/gitwarp/infrastructure/dossiers.py`

- [ ] **Step 1: Extend `build_start_payload` signature**

Add keyword-only optional parameters:

```python
    task_title: str | None = None,
    task_description: str | None = None,
    target_agent: str | None = None,
    acceptance_criteria: list[str] | None = None,
    verification_commands: list[str] | None = None,
```

- [ ] **Step 2: Persist task metadata in `WorkspaceRecord`**

Pass the new values into `WorkspaceRecord(...)`.

- [ ] **Step 3: Return task metadata in payload**

Add these keys to the returned payload:

```python
        "task_title": task_title,
        "task_description": task_description,
        "target_agent": target_agent,
        "acceptance_criteria": acceptance_criteria or [],
        "verification_commands": verification_commands or [],
```

- [ ] **Step 4: Pass task metadata into `create_dossier_files`**

Forward the same values from `build_start_payload`.

- [ ] **Step 5: Render richer dossier only when task metadata exists**

Modify `create_dossier_files()` to accept the new optional fields. When `task_title` exists, render the richer template from the spec. Otherwise keep the existing template so `start` and `create` tests remain compatible.

Use helper functions:

```python
def checkbox_lines(values: list[str] | None, fallback: str) -> list[str]:
    items = [item.strip() for item in (values or []) if item.strip()]
    if not items:
        return [f"- [ ] {fallback}"]
    return [f"- [ ] {item}" for item in items]


def command_checkbox_lines(values: list[str] | None) -> list[str]:
    items = [item.strip() for item in (values or []) if item.strip()]
    if not items:
        return ["- [ ] Define concrete verification before finishing"]
    return [f"- [ ] `{item}`" for item in items]
```

- [ ] **Step 6: Update dossier repair path**

In `ensure_dossier_for_entry()`, pass optional metadata from the ledger entry into `create_dossier_files()` so repaired task dossiers preserve task metadata.

- [ ] **Step 7: Run task tests**

Run: `python3 -m unittest tests.test_task_inbox -v`

Expected: still FAIL until CLI parser/command is wired, but pure import errors should be resolved.

### Task 4: Wire CLI `gitwarp task create`

**Files:**
- Modify: `src/gitwarp/adapters/cli/parser.py`
- Modify: `src/gitwarp/adapters/cli/workspaces.py`

- [ ] **Step 1: Add `cmd_task_create`**

Import `TaskCreateRequest` and `build_task_create_payload`, then add:

```python
def cmd_task_create(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(
        build_task_create_payload(
            ctx,
            TaskCreateRequest(
                title=args.title,
                description=args.description,
                base_branch=args.base,
                branch=args.branch,
                target_agent=args.agent,
                agent_id=args.agent_id,
                purpose=args.purpose,
                acceptance_criteria=args.acceptance or [],
                verification_commands=args.verify or [],
                instructions=args.instruction or [],
                instruction_profile=args.instruction_profile,
                instruction_mode=args.instruction_mode,
            ),
        )
    )
```

- [ ] **Step 2: Add nested argparse command**

In `build_parser()`:

First add `cmd_task_create` to the existing `.workspaces` import tuple.

```python
    task = subparsers.add_parser("task", help="High-level task intake for agent work")
    task_subparsers = task.add_subparsers(dest="task_command", required=True)
    task_create = task_subparsers.add_parser("create", help="Create a task worktree from a human task request")
    task_create.add_argument("--cwd")
    task_create.add_argument("--title", required=True)
    task_create.add_argument("--description")
    task_create.add_argument("--base")
    task_create.add_argument("--branch")
    task_create.add_argument("--agent", default="generic", help="Target-agent metadata: codex, claude, or generic")
    task_create.add_argument("--agent-id")
    task_create.add_argument("--purpose")
    task_create.add_argument("--acceptance", action="append", default=[])
    task_create.add_argument("--verify", action="append", default=[])
    task_create.add_argument("--instruction", action="append", default=[], help="Mount instruction file into the worktree; use TARGET=SOURCE to rename")
    task_create.add_argument("--instruction-profile")
    task_create.add_argument("--instruction-mode", choices=["copy", "symlink"], default="copy")
    task_create.set_defaults(func=cmd_task_create)
```

- [ ] **Step 3: Run focused CLI tests**

Run: `python3 -m unittest tests.test_task_inbox tests.test_cli_lifecycle tests.test_worktrees -v`

Expected: PASS. If existing dossier string assertions fail, keep existing non-task dossier rendering unchanged rather than weakening tests.

- [ ] **Step 4: Commit chunk 1**

```bash
git add src/gitwarp/domain/model.py src/gitwarp/domain/policies.py src/gitwarp/application/use_cases/tasks.py src/gitwarp/application/use_cases/__init__.py src/gitwarp/application/use_cases/provisioning.py src/gitwarp/infrastructure/dossiers.py src/gitwarp/adapters/cli/parser.py src/gitwarp/adapters/cli/workspaces.py tests/test_task_inbox.py
git commit -m "feat: add task inbox cli"
```

## Chunk 2: Web API Contract

### Task 5: Add Failing Web API Tests

**Files:**
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add successful `/api/task/create` mutation test**

Add a test near existing mutation tests:

```python
    def test_web_task_create_mutation_returns_task_payload(self) -> None:
        _, ready = self.start_web_server(self.repo, "web", "--port", "0", "--no-open")
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])

        status, payload = self.fetch_web_json(
            str(ready["url"]),
            "/api/task/create",
            method="POST",
            token=token,
            data={
                "title": "Web Task Intake",
                "description": "Create task from web API",
                "purpose": "   ",
                "target_agent": "codex",
                "acceptance_criteria": ["Task endpoint returns stable payload"],
                "verification_commands": ["python3 -m unittest tests.test_web_api -v"],
            },
        )

        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["branch"], "agent/web-task-intake")
        self.assertEqual(payload["target_agent"], "codex")
        self.assertEqual(payload["task_title"], "Web Task Intake")
        self.assertEqual(payload["task_description"], "Create task from web API")
        self.assertEqual(payload["acceptance_criteria"], ["Task endpoint returns stable payload"])
        self.assertEqual(payload["verification_commands"], ["python3 -m unittest tests.test_web_api -v"])
        self.assertIn("shell_command", payload)
        for key in (
            "repo_root",
            "path",
            "branch",
            "base_branch",
            "agent_id",
            "target_agent",
            "purpose",
            "task_title",
            "task_description",
            "acceptance_criteria",
            "verification_commands",
            "branch_created",
            "head",
            "dossier_path",
            "task_md",
            "progress_md",
            "lessons_md",
            "instructions",
            "shell_command",
        ):
            self.assertIn(key, payload)
```

- [ ] **Step 2: Extend schema/read-only/CSRF test**

Update `test_web_session_schema_and_readonly_mutation_rejection()` to assert:

```python
        self.assertIn("/api/task/create", schema["endpoints"])
        self.assertTrue(schema["endpoints"]["/api/task/create"]["mutates"])  # type: ignore[index]
        fields = schema["endpoints"]["/api/task/create"]["fields"]  # type: ignore[index]
        self.assertTrue(fields["title"]["required"])
        self.assertEqual(fields["target_agent"]["choices"], ["codex", "claude", "generic"])
```

Also post to `/api/task/create` in read-only mode and expect `code == "readonly"`.

- [ ] **Step 3: Add strict payload validation cases**

Extend `test_web_mutation_payload_schema_rejects_wrong_types_and_unknown_fields()`:

```python
            (
                "/api/task/create",
                {"title": "Bad field", "verify": ["wrong spelling"]},
                "unknown field(s): verify",
            ),
            (
                "/api/task/create",
                {"title": "Bad base", "base": "main"},
                "unknown field(s): base",
            ),
            (
                "/api/task/create",
                {"title": 42},
                "title must be a string",
            ),
            (
                "/api/task/create",
                {"title": "Bad criteria", "acceptance_criteria": "one"},
                "acceptance_criteria must be a list of strings",
            ),
```

- [ ] **Step 4: Run failing web tests**

Run: `python3 -m unittest tests.test_web_api -v`

Expected: FAIL because `/api/task/create` is not yet registered.

### Task 6: Implement Web Contract And Controller

**Files:**
- Modify: `src/gitwarp/webapp/contracts.py`
- Modify: `src/gitwarp/webapp/controllers.py`

- [ ] **Step 1: Add endpoint spec**

In `MUTATION_ENDPOINTS`:

```python
    "/api/task/create": EndpointSpec("POST", True, ("title",)),
```

- [ ] **Step 2: Add field specs**

In `MUTATION_FIELD_SPECS`:

```python
    "/api/task/create": {
        "title": FieldSpec("string", required=True),
        "description": FieldSpec("string"),
        "base_branch": FieldSpec("string"),
        "branch": FieldSpec("string"),
        "target_agent": FieldSpec("string", choices=("codex", "claude", "generic")),
        "agent_id": FieldSpec("string"),
        "purpose": FieldSpec("string"),
        "acceptance_criteria": FieldSpec("string_list"),
        "verification_commands": FieldSpec("string_list"),
        "instructions": FieldSpec("string_list"),
        "instruction_profile": FieldSpec("string"),
        "instruction_mode": FieldSpec("string", choices=("copy", "symlink")),
    },
```

- [ ] **Step 3: Add optional blank string handling and list helper**

First update `validate_field()` in `contracts.py` so optional blank strings can reach use-case defaults:

```python
        if not spec.required and not value.strip():
            return
```

Place this after the existing required-string empty check and before choice validation. This preserves the spec rule that blank optional strings are treated as absent, including optional fields with choices such as `target_agent`.

In `controllers.py`:

```python
def optional_string_list(payload: dict[str, Any], field: str) -> list[str] | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GitWarpError(f"{field} must be a list of strings")
    return value
```

Refactor `optional_instruction_list()` to call this helper if desired.

- [ ] **Step 4: Route `/api/task/create`**

Import `TaskCreateRequest` and `build_task_create_payload`, then add before `/api/dispatch`:

```python
    if path == "/api/task/create":
        return build_task_create_payload(
            ctx,
            TaskCreateRequest(
                title=string_field(payload, "title"),
                description=optional_string_field(payload, "description"),
                base_branch=optional_string_field(payload, "base_branch"),
                branch=optional_string_field(payload, "branch"),
                target_agent=optional_string_field(payload, "target_agent"),
                agent_id=optional_string_field(payload, "agent_id"),
                purpose=optional_string_field(payload, "purpose"),
                acceptance_criteria=optional_string_list(payload, "acceptance_criteria") or [],
                verification_commands=optional_string_list(payload, "verification_commands") or [],
                instructions=optional_instruction_list(payload) or [],
                instruction_profile=optional_instruction_profile(payload),
                instruction_mode=optional_instruction_mode(payload),
            ),
        )
```

- [ ] **Step 5: Run web tests**

Run: `python3 -m unittest tests.test_web_api -v`

Expected: PASS.

- [ ] **Step 6: Commit chunk 2**

```bash
git add src/gitwarp/webapp/contracts.py src/gitwarp/webapp/controllers.py tests/test_web_api.py
git commit -m "feat: expose task inbox web api"
```

## Chunk 3: React Web Console

### Task 7: Add Typed API Method

**Files:**
- Modify: `web/console/src/app/gitwarp-api.ts`
- Modify: `web/console/src/app/types.ts`

- [ ] **Step 1: Add `TaskCreateInput`**

```ts
export interface TaskCreateInput {
  title: string;
  description?: string;
  base_branch?: string;
  branch?: string;
  target_agent?: "codex" | "claude" | "generic";
  agent_id?: string;
  purpose?: string;
  acceptance_criteria?: string[];
  verification_commands?: string[];
  instructions?: string[];
  instruction_profile?: string;
  instruction_mode?: "copy" | "symlink";
}
```

- [ ] **Step 2: Add API client method**

```ts
  createTask(input: TaskCreateInput): Promise<CommandResult> {
    return this.post("/api/task/create", input);
  }
```

- [ ] **Step 3: Add optional task metadata to `WorktreeRow`**

Add optional fields:

```ts
  task_title?: string;
  task_description?: string | null;
  target_agent?: "codex" | "claude" | "generic" | string;
  acceptance_criteria?: string[];
  verification_commands?: string[];
```

### Task 8: Promote Create Task In Action Panel

**Files:**
- Modify: `web/console/src/app/App.tsx`
- Modify: `web/console/src/app/components/MetadataPanel.tsx`
- Modify: `web/console/src/app/components/ActionPanel.tsx`

- [ ] **Step 1: Thread `onRunTaskCreate` from `App`**

Import `TaskCreateInput`. Add prop in `RepositorySectionProps`:

```ts
  onRunTaskCreate: (input: TaskCreateInput) => Promise<CommandResult>;
```

Pass:

```tsx
onRunTaskCreate={(input) => runCommand("Create task", () => api.createTask(input))}
```

- [ ] **Step 2: Thread through `MetadataPanel`**

Add `onRunTaskCreate` prop and pass it into `ActionPanel`.

- [ ] **Step 3: Add `task` mode as primary action**

Change action mode:

```ts
type ActionMode = "task" | "create" | "launch" | null;
```

Add `onTaskCreate` prop to `ActionPanel`.

- [ ] **Step 4: Implement task form parser**

Add helpers:

```ts
function lines(form: HTMLFormElement, name: string): string[] {
  return value(form, name)
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}
```

Submit:

```ts
const submitTaskCreate = async (event: FormEvent<HTMLFormElement>) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    await onTaskCreate({
      title: value(form, "title"),
      ...(value(form, "description") ? { description: value(form, "description") } : {}),
      ...(baseBranch ? { base_branch: baseBranch } : {}),
      ...(value(form, "branch") ? { branch: value(form, "branch") } : {}),
      target_agent: ["codex", "claude"].includes(value(form, "target_agent"))
        ? (value(form, "target_agent") as "codex" | "claude")
        : "generic",
      ...(lines(form, "acceptance_criteria").length ? { acceptance_criteria: lines(form, "acceptance_criteria") } : {}),
      ...(lines(form, "verification_commands").length ? { verification_commands: lines(form, "verification_commands") } : {}),
      ...instructionOptions(form),
    });
    form.reset();
    setMode(null);
  } catch {
    // Keep the form open so validation errors can be corrected.
  }
};
```

- [ ] **Step 5: Add `CreateTaskForm`**

Fields:

- Title, required.
- Description.
- Base branch selector or a clearly labelled selected-base hint backed by the existing `WorktreePicker`.
- Target agent select: generic, codex, claude.
- Optional branch.
- Acceptance criteria, one per line.
- Verification commands, one per line.
- Existing instruction fields.

Button labels:

- Primary button: `Create Task`.
- Advanced buttons remain `Create Sandbox` and `Prepare Agent Launch`.

- [ ] **Step 6: Add base selector and copyable shell command handling**

If the existing `WorktreePicker` already determines `baseBranch`, document it in a form hint and continue passing it through. If the form needs explicit control, add a base branch selector populated from base worktrees in state.

After successful create, display the returned `shell_command` in the command output and add a visible copy button or read-only text field labelled `cd command`. Do not launch an agent process.

- [ ] **Step 7: Add lightweight source assertions for Web task UI**

Modify `tests/test_packaging.py` to assert:

```python
        api = (REPO_ROOT / "web" / "console" / "src" / "app" / "gitwarp-api.ts").read_text(encoding="utf-8")
        action_panel = (REPO_ROOT / "web" / "console" / "src" / "app" / "components" / "ActionPanel.tsx").read_text(encoding="utf-8")
        app = (REPO_ROOT / "web" / "console" / "src" / "app" / "App.tsx").read_text(encoding="utf-8")

        self.assertIn("createTask", api)
        self.assertIn("/api/task/create", api)
        self.assertIn("Create Task", action_panel)
        self.assertIn("acceptance_criteria", action_panel)
        self.assertIn("verification_commands", action_panel)
        self.assertIn("shell_command", app)
```

If `shell_command` display is implemented in `ActionPanel` instead of `App`, assert it there instead. This is not a substitute for browser tests, but it prevents accidentally shipping only the API client without the Create Task UI.

- [ ] **Step 8: Run TypeScript build**

Run: `npm run build`

Working directory: `web/console`

Expected: PASS and regenerated `web/console/dist/*` plus `src/gitwarp/assets/web_console/*`.

- [ ] **Step 9: Run packaging tests**

Run: `python3 -m unittest tests.test_packaging -v`

Expected: PASS. If dist drift tests fail, rerun `npm run build` and include regenerated assets.

- [ ] **Step 10: Commit chunk 3**

```bash
git add web/console/src/app/gitwarp-api.ts web/console/src/app/types.ts web/console/src/app/App.tsx web/console/src/app/components/MetadataPanel.tsx web/console/src/app/components/ActionPanel.tsx web/console/dist src/gitwarp/assets/web_console tests/test_packaging.py
git commit -m "feat: add create task web flow"
```

## Chunk 4: Documentation, Skill Guidance, And Final Verification

### Task 9: Update User And Agent Documentation

**Files:**
- Modify: `README.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify if needed: `skills/gitwarp/agents/openai.yaml`

- [ ] **Step 1: Update README primary workflow**

Add a short example before lower-level `create` examples:

```bash
gitwarp task create \
  --title "Implement billing export" \
  --description "Create an isolated task workspace with acceptance criteria" \
  --acceptance "Export command writes CSV" \
  --verify "python3 -m unittest discover -s tests -p 'test_*.py' -v"
```

Explain that `create`, `start`, and `dispatch` remain advanced commands.

- [ ] **Step 2: Update skill instructions**

In `skills/gitwarp/SKILL.md`, make `gitwarp task create` the preferred command for new user work. Keep base branch guidance:

```bash
gitwarp create --role base --branch feature/user-request \
  --purpose "Coordinate user-request work"

gitwarp task create --base feature/user-request \
  --title "Implement user-request"
```

Do not remove explicit `create`, `switch`, or `remove` guidance.

- [ ] **Step 3: Run documentation validators**

Run:

```bash
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
```

Expected: PASS.

- [ ] **Step 4: Commit docs**

```bash
git add README.md skills/gitwarp/SKILL.md skills/gitwarp/agents/openai.yaml
git commit -m "docs: prefer task inbox workflow"
```

### Task 10: Full Verification And Handoff

**Files:**
- No source edits unless verification finds a bug.

- [ ] **Step 1: Run Python compile check**

Run:

```bash
python3 -m compileall -q src tests
```

Expected: PASS.

- [ ] **Step 2: Run full unittest suite**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: PASS.

- [ ] **Step 3: Run web build and dist check**

Run:

```bash
npm run build
npm run check:dist
```

Working directory: `web/console`

Expected: PASS.

- [ ] **Step 4: Run install smoke if time allows**

Run:

```bash
scripts/verify-install.sh
```

Expected: PASS. If it fails because installed plugin cache is stale, reinstall with `scripts/install-codex-plugin.sh` and rerun.

- [ ] **Step 5: Run Git diff checks**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no whitespace errors and only intended tracked changes before final commits.

- [ ] **Step 6: Record GitWarp handoff**

Run:

```bash
gitwarp handoff --cwd "$PWD" --status verified --progress "Implemented task inbox workflow; full verification passed."
```

- [ ] **Step 7: Stop before merge/removal**

Leave the implementation worktree intact for human review. Do not merge, push, remove, collapse, or prune branches unless explicitly requested.

## Suggested Subagent Split

- Worker A owns Chunk 1: `src/gitwarp/domain`, `src/gitwarp/application/use_cases`, `src/gitwarp/infrastructure/dossiers.py`, CLI adapter, and `tests/test_task_inbox.py`.
- Worker B owns Chunk 2: `src/gitwarp/webapp`, `tests/test_web_api.py`.
- Worker C owns Chunk 3: `web/console`, generated web assets, and packaging tests.
- Main session owns Chunk 4 and final integration verification.

Do not run Worker B or C against stale assumptions if Worker A changes payload names. The API schema in the spec is the contract: `base_branch`, `target_agent`, `acceptance_criteria`, and `verification_commands`.
