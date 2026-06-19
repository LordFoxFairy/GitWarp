from __future__ import annotations

from pathlib import Path

from helpers import *


ensure_src_path()


class DomainModelTests(unittest.TestCase):
    def test_worktree_snapshot_round_trips_json_shape(self) -> None:
        domain = importlib.import_module("gitwarp.domain")
        snapshot = domain.WorktreeSnapshot.from_mapping(
            {
                "path": "/repo/.gitwarp/worktrees/task",
                "head": "abc123",
                "branch": "feature-task",
                "detached": False,
                "is_main": False,
            }
        )

        self.assertEqual(snapshot.branch, "feature-task")
        self.assertEqual(
            snapshot.to_dict(),
            {
                "path": "/repo/.gitwarp/worktrees/task",
                "head": "abc123",
                "branch": "feature-task",
                "detached": False,
                "is_main": False,
            },
        )

    def test_workspace_record_preserves_dossier_and_dispatch_metadata(self) -> None:
        model = importlib.import_module("gitwarp.domain.model")
        record = model.WorkspaceRecord.from_mapping(
            {
                "path": "/repo/.gitwarp/worktrees/task",
                "branch": "feature-task",
                "agent_id": "codex-task",
                "purpose": "Implement task",
                "status": "dispatched",
                "notes": [{"note": "started"}],
                "dossier_path": "/repo/.gitwarp/dossiers/task",
                "task_md": "/repo/.gitwarp/dossiers/task/task.md",
                "progress_md": "/repo/.gitwarp/dossiers/task/progress.md",
                "lessons_md": "/repo/.gitwarp/dossiers/task/lessons.md",
                "latest_progress": "Dispatch command prepared.",
                "last_seen_head": "abc123",
                "dispatch": {"agent_name": "codex"},
                "instructions": [{"target": "AGENTS.md", "source": "/repo/AGENTS.md", "mode": "copy"}],
                "instruction_profile": "codex",
                "instruction_mode": "copy",
            }
        )

        payload = record.to_dict()
        self.assertEqual(payload["agent_id"], "codex-task")
        self.assertEqual(payload["dossier_path"], "/repo/.gitwarp/dossiers/task")
        self.assertEqual(payload["dispatch"], {"agent_name": "codex"})
        self.assertEqual(payload["instructions"][0]["target"], "AGENTS.md")
        self.assertEqual(payload["instruction_profile"], "codex")
        self.assertEqual(payload["instruction_mode"], "copy")

    def test_dispatch_plan_serializes_to_ledger_metadata(self) -> None:
        model = importlib.import_module("gitwarp.domain.model")
        plan = model.DispatchPlan(
            agent_name="codex",
            agent_id="codex-feature",
            launch_command=["codex", "exec"],
            launch_preview="codex exec",
            prepared_at="2026-06-20T00:00:00+00:00",
        )

        self.assertEqual(
            plan.to_metadata(),
            {
                "agent_name": "codex",
                "command_mode": "print",
                "launch_command": ["codex", "exec"],
                "launch_preview": "codex exec",
                "last_exit_code": None,
                "last_prepared_at": "2026-06-20T00:00:00+00:00",
                "last_started_at": None,
                "last_finished_at": None,
            },
        )


class DomainPolicyTests(unittest.TestCase):
    def test_head_drift_policy_matches_existing_json_contract(self) -> None:
        policies = importlib.import_module("gitwarp.domain.policies")

        self.assertIsNone(policies.build_head_drift("abc", "abc"))
        self.assertEqual(
            policies.build_head_drift("abc", "def"),
            {"drifted": True, "last_seen_head": "abc", "current_head": "def"},
        )

    def test_branch_collision_raises_domain_error(self) -> None:
        domain = importlib.import_module("gitwarp.domain")
        policies = importlib.import_module("gitwarp.domain.policies")

        with self.assertRaises(domain.GitWarpError):
            policies.ensure_branch_available([{"branch": "feature-a", "path": "/tmp/a"}], "feature-a")

    def test_select_live_target_prefers_deepest_path_for_cwd(self) -> None:
        policies = importlib.import_module("gitwarp.domain.policies")
        worktrees = [
            {"path": "/repo", "branch": "main", "head": "1"},
            {"path": "/repo/.gitwarp/worktrees/task", "branch": "task", "head": "2"},
        ]

        target = policies.select_live_target(worktrees, Path("/repo/.gitwarp/worktrees/task/src"), None, None)

        self.assertEqual(target["branch"], "task")

    def test_select_collapse_target_refuses_main_checkout(self) -> None:
        domain = importlib.import_module("gitwarp.domain")
        policies = importlib.import_module("gitwarp.domain.policies")

        with self.assertRaises(domain.GitWarpError):
            policies.select_collapse_target([], {"entries": []}, "/repo", None, Path("/repo"))

    def test_guarded_root_policy_detects_nested_worktree(self) -> None:
        policies = importlib.import_module("gitwarp.domain.policies")

        self.assertTrue(policies.guarded_worktree_root_contains(Path("/repo/.gitwarp/worktrees"), "/repo/.gitwarp/worktrees/task"))
        self.assertFalse(policies.guarded_worktree_root_contains(Path("/repo/.gitwarp/worktrees"), "/repo/other"))
