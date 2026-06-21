from __future__ import annotations

from helpers import *


class MatrixTests(GitWarpTestCase):
    def rows_for_branch(self, matrix: dict[str, object], branch: str) -> list[dict[str, object]]:
        return [
            row
            for row in matrix["rows"]  # type: ignore[index]
            if row["branch"] == branch
        ]

    def test_matrix_explains_git_refs_worktrees_ledger_and_dossiers_without_mutation(self) -> None:
        run_git(self.repo, "branch", "feature/merged-local")
        task = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-matrix",
            "--branch",
            "feature/active-task",
            "--purpose",
            "Active task for matrix",
        )
        task_path = Path(str(task["path"]))
        (task_path / "task-change.txt").write_text("task change\n", encoding="utf-8")
        run_git(task_path, "add", "task-change.txt")
        run_git(task_path, "commit", "-m", "task matrix change")

        manual_path = self.repo / "manual-untracked"
        run_git(self.repo, "worktree", "add", "-b", "feature/manual-untracked", str(manual_path), "HEAD")

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        before = ledger_path.read_bytes()
        matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo))
        after = ledger_path.read_bytes()
        rows = {row["branch"]: row for row in matrix["rows"]}  # type: ignore[index]

        self.assertEqual(before, after)
        self.assertEqual(matrix["sources"]["ledger_entries"], 1)  # type: ignore[index]
        self.assertEqual(matrix["summary"]["active_gitwarp_tasks"], 1)  # type: ignore[index]
        self.assertEqual(matrix["summary"]["untracked_worktrees"], 1)  # type: ignore[index]
        self.assertGreaterEqual(matrix["summary"]["prunable_branch_refs"], 1)  # type: ignore[index]

        self.assertEqual(rows["main"]["category"], "main")
        self.assertEqual(rows["main"]["recommended_action"], "use_main")
        self.assertEqual(rows["feature/active-task"]["category"], "active_task")
        self.assertEqual(rows["feature/active-task"]["gitwarp"]["dossier_state"], "ok")
        self.assertEqual(rows["feature/active-task"]["recommended_action"], "switch")
        self.assertIn("gitwarp switch", rows["feature/active-task"]["next_command"])
        self.assertEqual(rows["feature/manual-untracked"]["category"], "untracked_worktree")
        self.assertEqual(rows["feature/manual-untracked"]["recommended_action"], "adopt")
        self.assertIn("gitwarp adopt", rows["feature/manual-untracked"]["next_command"])
        self.assertEqual(rows["feature/merged-local"]["category"], "merged_ref")
        self.assertEqual(rows["feature/merged-local"]["recommended_action"], "prune_branch")
        self.assertEqual(rows["feature/merged-local"]["legacy_state"], "deprecated")
        self.assertIn("gitwarp prune-branch", rows["feature/merged-local"]["next_command"])

    def test_matrix_reports_stale_ledger_and_dossier_without_pruning(self) -> None:
        task = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-stale-matrix",
            "--branch",
            "feature/stale-matrix",
            "--purpose",
            "Stale matrix task",
        )
        task_path = Path(str(task["path"]))
        dossier_path = Path(str(task["dossier_path"]))
        run_git(self.repo, "worktree", "remove", "--force", str(task_path))
        run_git(self.repo, "worktree", "prune")

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        before = ledger_path.read_bytes()
        matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo))
        after = ledger_path.read_bytes()
        rows = {row["branch"]: row for row in matrix["rows"]}  # type: ignore[index]

        self.assertEqual(before, after)
        self.assertTrue(dossier_path.exists())
        self.assertEqual(rows["feature/stale-matrix"]["category"], "stale_ledger")
        self.assertEqual(rows["feature/stale-matrix"]["gitwarp"]["dossier_state"], "stale")
        self.assertEqual(rows["feature/stale-matrix"]["recommended_action"], "repair_metadata")
        self.assertEqual(rows["feature/stale-matrix"]["next_command"], "gitwarp init")
        self.assertEqual(matrix["summary"]["stale_ledger_entries"], 1)  # type: ignore[index]

    def test_matrix_keeps_duplicate_stale_ledger_rows_visible(self) -> None:
        task = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-duplicate-matrix",
            "--branch",
            "feature/duplicate-matrix",
            "--purpose",
            "Live matrix task",
        )
        task_path = Path(str(task["path"]))
        (task_path / "live.txt").write_text("live\n", encoding="utf-8")
        run_git(task_path, "add", "live.txt")
        run_git(task_path, "commit", "-m", "live matrix task")

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        stale_dossier = self.repo / ".gitwarp" / "dossiers" / "feature-duplicate-matrix-stale"
        stale_dossier.mkdir(parents=True)
        stale_entry = dict(ledger["entries"][0])
        stale_entry.update(
            {
                "agent_id": "codex-old-duplicate",
                "path": str(self.repo / "missing-duplicate-worktree"),
                "dossier_path": str(stale_dossier),
                "task_md": str(stale_dossier / "task.md"),
                "progress_md": str(stale_dossier / "progress.md"),
                "lessons_md": str(stale_dossier / "lessons.md"),
            }
        )
        for filename in ("task.md", "progress.md", "lessons.md"):
            (stale_dossier / filename).write_text(f"# {filename}\n", encoding="utf-8")
        ledger["entries"].append(stale_entry)
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")

        matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo))
        duplicate_rows = self.rows_for_branch(matrix, "feature/duplicate-matrix")
        categories = {row["category"] for row in duplicate_rows}

        self.assertEqual(len(duplicate_rows), 2)
        self.assertIn("active_task", categories)
        self.assertIn("stale_ledger", categories)
        stale_row = next(row for row in duplicate_rows if row["category"] == "stale_ledger")
        self.assertEqual(stale_row["agent_id"], "codex-old-duplicate")
        self.assertEqual(stale_row["legacy_state"], "legacy")
        self.assertEqual(stale_row["recommended_action"], "repair_metadata")
        self.assertTrue(str(stale_row["row_id"]).startswith("ledger:"))

    def test_matrix_reports_orphan_dossier_directories(self) -> None:
        run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        orphan = self.repo / ".gitwarp" / "dossiers" / "feature-orphan-dossier"
        orphan.mkdir(parents=True)
        for filename in ("task.md", "progress.md", "lessons.md"):
            (orphan / filename).write_text(f"# {filename}\n", encoding="utf-8")

        matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo))
        orphan_rows = [
            row
            for row in matrix["rows"]  # type: ignore[index]
            if row["category"] == "orphan_dossier"
        ]

        self.assertEqual(len(orphan_rows), 1)
        self.assertEqual(orphan_rows[0]["legacy_state"], "legacy")
        self.assertEqual(orphan_rows[0]["recommended_action"], "repair_metadata")
        self.assertEqual(orphan_rows[0]["gitwarp"]["dossier_path"], str(orphan.resolve()))
        self.assertEqual(matrix["summary"]["orphan_dossiers"], 1)  # type: ignore[index]

    def test_matrix_marks_merged_live_task_for_user_selected_collapse(self) -> None:
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
        task = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/merged-matrix-task",
            "--base",
            "feature/user-request",
            "--purpose",
            "Implement merged task",
        )
        base_path = Path(str(base["path"]))
        task_path = Path(str(task["path"]))
        (task_path / "merged-task.txt").write_text("merged\n", encoding="utf-8")
        run_git(task_path, "add", "merged-task.txt")
        run_git(task_path, "commit", "-m", "merged task work")
        run_git(base_path, "merge", "--no-ff", "agent/merged-matrix-task", "-m", "merge matrix task")

        matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo))
        row = self.rows_for_branch(matrix, "agent/merged-matrix-task")[0]

        self.assertEqual(row["category"], "merged_task")
        self.assertEqual(row["legacy_state"], "deprecated")
        self.assertEqual(row["recommended_action"], "finish_collapse_merged")
        self.assertIn("gitwarp finish", row["next_command"])
        self.assertEqual(matrix["summary"]["merged_gitwarp_tasks"], 1)  # type: ignore[index]

    def test_matrix_accepts_base_for_feature_branch_cleanup_context(self) -> None:
        run_git(self.repo, "checkout", "-b", "feature/parent")
        (self.repo / "parent.txt").write_text("parent\n", encoding="utf-8")
        run_git(self.repo, "add", "parent.txt")
        run_git(self.repo, "commit", "-m", "parent branch work")
        run_git(self.repo, "branch", "feature/child")
        run_git(self.repo, "checkout", "main")

        default_matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo))
        feature_matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo), "--base", "feature/parent")
        default_rows = {row["branch"]: row for row in default_matrix["rows"]}  # type: ignore[index]
        feature_rows = {row["branch"]: row for row in feature_matrix["rows"]}  # type: ignore[index]

        self.assertEqual(feature_matrix["merge_base"], "feature/parent")
        self.assertEqual(default_rows["feature/child"]["category"], "orphan_ref")
        self.assertEqual(feature_rows["feature/child"]["category"], "merged_ref")
        self.assertEqual(feature_rows["feature/child"]["recommended_action"], "prune_branch")
        self.assertEqual(feature_rows["feature/parent"]["category"], "base")
        self.assertEqual(feature_rows["feature/parent"]["recommended_action"], "create_base_worktree")
        self.assertIn("gitwarp create --role base", feature_rows["feature/parent"]["next_command"])

    def test_matrix_exposes_unmanaged_branch_classification_without_cleanup(self) -> None:
        run_git(self.repo, "branch", "feature/legacy-merged")
        run_git(self.repo, "checkout", "-b", "feature/legacy-unmerged")
        (self.repo / "legacy.txt").write_text("legacy\n", encoding="utf-8")
        run_git(self.repo, "add", "legacy.txt")
        run_git(self.repo, "commit", "-m", "legacy unmerged work")
        run_git(self.repo, "checkout", "main")

        matrix = run_gitwarp(self.repo, "matrix", "--cwd", str(self.repo))
        rows = {row["branch"]: row for row in matrix["rows"]}  # type: ignore[index]

        merged = rows["feature/legacy-merged"]
        self.assertEqual(merged["category"], "merged_ref")
        self.assertEqual(merged["managed_state"], "unmanaged")
        self.assertEqual(merged["commit_state"], "merged")
        self.assertEqual(merged["cleanup_policy"], "user_confirmed_ref_prune")
        self.assertEqual(merged["classification_basis"]["base_branch"], "main")
        self.assertFalse(merged["classification_basis"]["managed_by_gitwarp"])
        self.assertEqual(merged["legacy_state"], "deprecated")

        unmerged = rows["feature/legacy-unmerged"]
        self.assertEqual(unmerged["category"], "orphan_ref")
        self.assertEqual(unmerged["managed_state"], "unmanaged")
        self.assertEqual(unmerged["commit_state"], "unmerged")
        self.assertEqual(unmerged["cleanup_policy"], "review_unmerged_ref")
        self.assertEqual(unmerged["recommended_action"], "inspect")
        self.assertIsNone(unmerged["next_command"])
