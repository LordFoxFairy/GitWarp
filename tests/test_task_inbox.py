from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
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
        self.assertEqual(payload["shell_command"], f"cd {shlex.quote(str(payload['path']))}")

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
        self.assertIsNone(payload["task_description"])

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
        self.assertIn("`AGENTS.md` from", Path(str(payload["task_md"])).read_text(encoding="utf-8"))

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
        self.assertIn("- Agent: codex-explicit-task", task_md)
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

    def test_task_create_computes_slug_even_when_branch_and_agent_are_explicit(self) -> None:
        payload = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Explicit Everything",
            "--branch",
            "agent/custom-task",
            "--agent-id",
            "owner-custom-task",
        )
        self.assertEqual(payload["branch"], "agent/custom-task")
        self.assertEqual(payload["agent_id"], "owner-custom-task")

        invalid = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "!!!",
            "--branch",
            "agent/custom-invalid",
            "--agent-id",
            "owner-custom-invalid",
            expect_ok=False,
        )
        self.assertIn("normalizes to an empty slug", str(invalid["error"]))
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "agent" / "custom-invalid").exists())

    def test_task_create_rollback_keeps_ledger_dossiers_and_branch_clean(self) -> None:
        before_ledger = None
        before_dossiers: list[str] = []
        if (self.repo / ".gitwarp" / "ledger.json").exists():
            before_ledger = (self.repo / ".gitwarp" / "ledger.json").read_text(encoding="utf-8")
        if (self.repo / ".gitwarp" / "dossiers").exists():
            before_dossiers = sorted(path.name for path in (self.repo / ".gitwarp" / "dossiers").iterdir())

        failed = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Rollback Missing Instruction",
            "--instruction",
            "missing.md",
            expect_ok=False,
        )
        self.assertIn("instruction source", str(failed["error"]))
        if before_ledger is None:
            self.assertFalse((self.repo / ".gitwarp" / "ledger.json").exists())
        else:
            self.assertEqual((self.repo / ".gitwarp" / "ledger.json").read_text(encoding="utf-8"), before_ledger)
        self.assertEqual(run_git(self.repo, "branch", "--list", "agent/rollback-missing-instruction"), "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "agent" / "rollback-missing-instruction").exists())
        current_dossiers = []
        if (self.repo / ".gitwarp" / "dossiers").exists():
            current_dossiers = sorted(path.name for path in (self.repo / ".gitwarp" / "dossiers").iterdir())
        self.assertEqual(current_dossiers, before_dossiers)

    def test_workspace_record_task_metadata_round_trips_only_when_present(self) -> None:
        ensure_src_path()
        from gitwarp.domain.model import WorkspaceRecord

        minimal = WorkspaceRecord.from_mapping({"path": "/repo/worktree", "branch": "agent/minimal"}).to_dict()
        self.assertNotIn("task_title", minimal)
        self.assertNotIn("task_description", minimal)
        self.assertNotIn("target_agent", minimal)
        self.assertNotIn("acceptance_criteria", minimal)
        self.assertNotIn("verification_commands", minimal)

        record = WorkspaceRecord.from_mapping(
            {
                "path": "/repo/worktree",
                "branch": "agent/task",
                "task_title": "Task",
                "task_description": "Description",
                "target_agent": "codex",
                "acceptance_criteria": ["Done"],
                "verification_commands": ["python3 -m unittest"],
            }
        )

        self.assertEqual(record.task_title, "Task")
        self.assertEqual(record.task_description, "Description")
        self.assertEqual(record.target_agent, "codex")
        self.assertEqual(record.acceptance_criteria, ["Done"])
        self.assertEqual(record.verification_commands, ["python3 -m unittest"])
        self.assertEqual(record.to_dict()["task_title"], "Task")

    def test_cli_invalid_target_agent_is_json_not_argparse_error(self) -> None:
        result = subprocess.run(
            [*gitwarp_command(), "task", "create", "--title", "Bad agent", "--agent", "gemini"],
            cwd=str(self.repo),
            env=gitwarp_env(),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["ok"], False)
        self.assertIn("target_agent must be one of", str(payload["error"]))

    def test_task_create_supports_instruction_profile_and_blank_profile_is_absent(self) -> None:
        (self.repo / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md")
        run_git(self.repo, "commit", "-m", "add root instruction")
        (self.repo / ".gitwarp").mkdir()
        (self.repo / ".gitwarp" / "instruction_profiles.json").write_text(
            json.dumps({"version": 1, "profiles": {"codex": {"instructions": ["AGENTS.md"]}}}),
            encoding="utf-8",
        )

        payload = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Profile Task",
            "--instruction-profile",
            "codex",
        )
        self.assertEqual(payload["instruction_profile"], "codex")
        self.assertEqual(payload["instructions"][0]["target"], "AGENTS.md")  # type: ignore[index]

        blank = run_gitwarp(
            self.repo,
            "task",
            "create",
            "--title",
            "Blank Profile",
            "--instruction-profile",
            "   ",
        )
        self.assertIsNone(blank["instruction_profile"])

    def test_task_create_generated_branch_precheck_does_not_mutate_for_existing_ref(self) -> None:
        run_git(self.repo, "branch", "agent/existing-ref")
        with tempfile.TemporaryDirectory() as tempdir:
            orphan_dossier = self.repo / ".gitwarp" / "dossiers" / "orphan"
            orphan_dossier.mkdir(parents=True, exist_ok=True)
            (orphan_dossier / "task.md").write_text("orphan\n", encoding="utf-8")
            before_dossiers = sorted(path.name for path in (self.repo / ".gitwarp" / "dossiers").iterdir())
            before_worktree_list = run_git(self.repo, "worktree", "list", "--porcelain")

            failed = run_gitwarp(
                Path(tempdir),
                "task",
                "create",
                "--cwd",
                str(self.repo),
                "--title",
                "Existing Ref",
                expect_ok=False,
            )

        self.assertIn("generated branch already exists", str(failed["error"]))
        self.assertEqual(sorted(path.name for path in (self.repo / ".gitwarp" / "dossiers").iterdir()), before_dossiers)
        self.assertEqual(run_git(self.repo, "worktree", "list", "--porcelain"), before_worktree_list)
