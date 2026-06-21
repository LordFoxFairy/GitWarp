from __future__ import annotations

from helpers import *


class NextActionTests(GitWarpTestCase):
    def test_next_reports_empty_queue_for_healthy_repo_without_mutation(self) -> None:
        ledger_path = self.repo / ".gitwarp" / "ledger.json"

        payload = run_gitwarp(self.repo, "next", "--cwd", str(self.repo))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["summary"]["total"], 0)
        self.assertEqual(payload["summary"]["by_safety"], {})
        self.assertFalse(ledger_path.exists())

    def test_next_prioritizes_matrix_cleanup_and_adoption_actions(self) -> None:
        run_git(self.repo, "branch", "feature/merged-local")
        managed = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/merged-next-task",
            "--base",
            "main",
            "--purpose",
            "Task that will be merged before cleanup",
        )
        task_path = Path(str(managed["path"]))
        (task_path / "done.txt").write_text("done\n", encoding="utf-8")
        run_git(task_path, "add", "done.txt")
        run_git(task_path, "commit", "-m", "done task")
        run_git(self.repo, "merge", "--no-ff", "agent/merged-next-task", "-m", "merge next task")

        manual_path = self.repo / "manual-next"
        run_git(self.repo, "worktree", "add", "-b", "feature/manual-next", str(manual_path), "HEAD")

        payload = run_gitwarp(self.repo, "next", "--cwd", str(self.repo))
        actions = payload["actions"]
        categories = [action["category"] for action in actions]

        self.assertIn("merged_task", categories)
        self.assertIn("merged_ref", categories)
        self.assertIn("untracked_worktree", categories)
        self.assertEqual([action["priority"] for action in actions], sorted(action["priority"] for action in actions))

        merged_task = next(action for action in actions if action["category"] == "merged_task")
        self.assertEqual(merged_task["severity"], "warning")
        self.assertEqual(merged_task["safety"], "confirm_destructive")
        self.assertIn("gitwarp finish", merged_task["command"])
        self.assertEqual(merged_task["branch"], "agent/merged-next-task")
        self.assertEqual(merged_task["source"]["kind"], "matrix")

        merged_ref = next(action for action in actions if action["category"] == "merged_ref")
        self.assertEqual(merged_ref["safety"], "confirm_destructive")
        self.assertIn("gitwarp prune-branch", merged_ref["command"])

        untracked = next(action for action in actions if action["category"] == "untracked_worktree")
        self.assertEqual(untracked["safety"], "review")
        self.assertIn("gitwarp adopt", untracked["command"])

    def test_next_reports_stale_ledger_and_orphan_dossier_as_repair_actions(self) -> None:
        task = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-stale-next",
            "--branch",
            "feature/stale-next",
            "--purpose",
            "Stale next action",
        )
        task_path = Path(str(task["path"]))
        run_git(self.repo, "worktree", "remove", "--force", str(task_path))
        run_git(self.repo, "worktree", "prune")

        orphan = self.repo / ".gitwarp" / "dossiers" / "feature-orphan-next"
        orphan.mkdir(parents=True)
        for filename in ("task.md", "progress.md", "lessons.md"):
            (orphan / filename).write_text(f"# {filename}\n", encoding="utf-8")

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        before = ledger_path.read_bytes()
        payload = run_gitwarp(self.repo, "next", "--cwd", str(self.repo))
        after = ledger_path.read_bytes()
        actions = payload["actions"]
        categories = [action["category"] for action in actions]

        self.assertEqual(before, after)
        self.assertIn("stale_ledger", categories)
        self.assertIn("orphan_dossier", categories)
        for action in actions:
            if action["category"] in {"stale_ledger", "orphan_dossier"}:
                self.assertEqual(action["safety"], "review")
                self.assertEqual(action["command"], "gitwarp init")
                self.assertEqual(action["severity"], "warning")

    def test_next_does_not_recommend_collapsing_dirty_merged_task(self) -> None:
        task = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/dirty-merged-next",
            "--base",
            "main",
            "--purpose",
            "Dirty merged task should not be collapsed first",
        )
        task_path = Path(str(task["path"]))
        (task_path / "done.txt").write_text("done\n", encoding="utf-8")
        run_git(task_path, "add", "done.txt")
        run_git(task_path, "commit", "-m", "done dirty merged task")
        run_git(self.repo, "merge", "--no-ff", "agent/dirty-merged-next", "-m", "merge dirty task")
        (task_path / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")

        payload = run_gitwarp(self.repo, "next", "--cwd", str(self.repo))
        branch_actions = [action for action in payload["actions"] if action.get("branch") == "agent/dirty-merged-next"]

        self.assertEqual([action["category"] for action in branch_actions], ["dirty_worktree"])
        self.assertEqual(branch_actions[0]["safety"], "review")
        self.assertIn("gitwarp reconcile", branch_actions[0]["command"])
        self.assertNotIn("--collapse-merged", branch_actions[0]["command"])

    def test_next_cli_accepts_base_branch_for_branch_cleanup_context(self) -> None:
        run_git(self.repo, "checkout", "-b", "feature/parent")
        (self.repo / "parent.txt").write_text("parent\n", encoding="utf-8")
        run_git(self.repo, "add", "parent.txt")
        run_git(self.repo, "commit", "-m", "parent branch work")
        run_git(self.repo, "branch", "feature/child")
        run_git(self.repo, "checkout", "main")

        default_payload = run_gitwarp(self.repo, "next", "--cwd", str(self.repo))
        feature_payload = run_gitwarp(self.repo, "next", "--cwd", str(self.repo), "--base", "feature/parent")

        self.assertNotIn("feature/child", [action.get("branch") for action in default_payload["actions"]])
        child_action = next(action for action in feature_payload["actions"] if action["branch"] == "feature/child")
        self.assertEqual(child_action["category"], "merged_ref")
        self.assertEqual(child_action["safety"], "confirm_destructive")
        self.assertIn("feature/child", child_action["command"])
