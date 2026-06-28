from __future__ import annotations

from helpers import *


class BranchRefTests(GitWarpTestCase):
    def test_custom_base_does_not_make_default_branch_prunable(self) -> None:
        run_git(self.repo, "checkout", "-b", "feature/parent")

        branches = run_gitwarp(self.repo, "branches", "--cwd", str(self.repo), "--base", "feature/parent")
        rows = {row["name"]: row for row in branches["branches"]}  # type: ignore[index]

        self.assertEqual(branches["default_branch"], "main")
        self.assertEqual(rows["main"]["category"], "base")
        self.assertFalse(rows["main"]["deletable"])
        self.assertIn("default branch", rows["main"]["delete_blockers"])

        refused = run_gitwarp(
            self.repo,
            "prune-branch",
            "--cwd",
            str(self.repo),
            "--branch",
            "main",
            "--base",
            "feature/parent",
            expect_ok=False,
        )
        self.assertIn("default branch", str(refused["error"]))
        self.assertIn("main", run_git(self.repo, "branch", "--format", "%(refname:short)").splitlines())

    def test_branches_classify_and_prune_only_safe_local_refs(self) -> None:
        run_git(self.repo, "branch", "feature/merged-local")
        active = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "feature/active-task",
            "--purpose",
            "Active task branch",
        )
        active_path = Path(str(active["path"]))

        unmerged_path = self.repo / "manual-unmerged"
        run_git(self.repo, "worktree", "add", "-b", "feature/unmerged-local", str(unmerged_path), "HEAD")
        (unmerged_path / "unmerged.txt").write_text("unmerged\n", encoding="utf-8")
        run_git(unmerged_path, "add", "unmerged.txt")
        run_git(unmerged_path, "commit", "-m", "unmerged branch change")
        run_git(self.repo, "worktree", "remove", "--force", str(unmerged_path))

        branches = run_gitwarp(self.repo, "branches", "--cwd", str(self.repo))
        rows = {row["name"]: row for row in branches["branches"]}  # type: ignore[index]

        self.assertEqual(branches["default_branch"], "main")
        self.assertEqual(rows["main"]["category"], "base")
        self.assertFalse(rows["main"]["deletable"])
        self.assertEqual(rows["feature/active-task"]["category"], "active")
        self.assertFalse(rows["feature/active-task"]["deletable"])
        self.assertEqual(rows["feature/active-task"]["worktree_path"], str(active_path))
        self.assertEqual(rows["feature/merged-local"]["category"], "merged")
        self.assertTrue(rows["feature/merged-local"]["deletable"])
        self.assertEqual(rows["feature/unmerged-local"]["category"], "orphan")
        self.assertFalse(rows["feature/unmerged-local"]["deletable"])

        deleted = run_gitwarp(self.repo, "prune-branch", "--cwd", str(self.repo), "--branch", "feature/merged-local")
        self.assertTrue(deleted["deleted"])
        self.assertEqual(deleted["branch"], "feature/merged-local")
        remaining = run_git(self.repo, "branch", "--format", "%(refname:short)")
        self.assertNotIn("feature/merged-local", remaining.splitlines())

        active_refused = run_gitwarp(
            self.repo,
            "prune-branch",
            "--cwd",
            str(self.repo),
            "--branch",
            "feature/active-task",
            expect_ok=False,
        )
        self.assertIn("checked out in a worktree", str(active_refused["error"]))

        unmerged_refused = run_gitwarp(
            self.repo,
            "prune-branch",
            "--cwd",
            str(self.repo),
            "--branch",
            "feature/unmerged-local",
            expect_ok=False,
        )
        self.assertIn("not merged into main", str(unmerged_refused["error"]))

        main_refused = run_gitwarp(
            self.repo,
            "prune-branch",
            "--cwd",
            str(self.repo),
            "--branch",
            "main",
            expect_ok=False,
        )
        self.assertIn("default branch", str(main_refused["error"]))

    def test_unmanaged_branch_refs_explain_main_baseline_and_commit_state(self) -> None:
        run_git(self.repo, "branch", "feature/legacy-merged")
        run_git(self.repo, "checkout", "-b", "feature/legacy-unmerged")
        (self.repo / "legacy.txt").write_text("legacy\n", encoding="utf-8")
        run_git(self.repo, "add", "legacy.txt")
        run_git(self.repo, "commit", "-m", "legacy unmerged work")
        run_git(self.repo, "checkout", "main")

        branches = run_gitwarp(self.repo, "branches", "--cwd", str(self.repo))
        rows = {row["name"]: row for row in branches["branches"]}  # type: ignore[index]

        merged = rows["feature/legacy-merged"]
        unmerged = rows["feature/legacy-unmerged"]
        self.assertEqual(merged["managed_state"], "unmanaged")
        self.assertIsNone(merged["branch_role"])
        self.assertEqual(merged["base_branch"], "main")
        self.assertEqual(merged["commit_state"], "merged")
        self.assertEqual(merged["cleanup_policy"], "user_confirmed_ref_prune")
        self.assertEqual(merged["classification_basis"]["base_branch"], "main")
        self.assertEqual(merged["classification_basis"]["head"], merged["head"])
        self.assertTrue(merged["classification_basis"]["merged_to_base"])
        self.assertFalse(merged["classification_basis"]["managed_by_gitwarp"])

        self.assertEqual(unmerged["managed_state"], "unmanaged")
        self.assertIsNone(unmerged["branch_role"])
        self.assertEqual(unmerged["base_branch"], "main")
        self.assertEqual(unmerged["commit_state"], "unmerged")
        self.assertEqual(unmerged["cleanup_policy"], "review_unmerged_ref")
        self.assertFalse(unmerged["deletable"])
        self.assertIn("not merged into main", unmerged["delete_blockers"])

    def test_guarded_branch_ref_delete_rejects_advanced_ref(self) -> None:
        ensure_src_path()
        from gitwarp.application.use_cases.branches import delete_branch_ref
        from gitwarp.infrastructure.ledger import discover_repo

        run_git(self.repo, "branch", "feature/racy-local")
        old_head = run_git(self.repo, "rev-parse", "feature/racy-local")
        race_path = self.repo / "race"
        run_git(self.repo, "worktree", "add", str(race_path), "feature/racy-local")
        (race_path / "race.txt").write_text("new commit\n", encoding="utf-8")
        run_git(race_path, "add", "race.txt")
        run_git(race_path, "commit", "-m", "advance branch before prune")
        run_git(self.repo, "worktree", "remove", "--force", str(race_path))

        with self.assertRaisesRegex(Exception, "changed while pruning"):
            delete_branch_ref(discover_repo(self.repo), "feature/racy-local", old_head)

        self.assertIn("feature/racy-local", run_git(self.repo, "branch", "--format", "%(refname:short)").splitlines())
