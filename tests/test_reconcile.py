from __future__ import annotations

from helpers import *


class ReconcileTests(GitWarpTestCase):
    def test_read_commands_do_not_prune_stale_ledger_entries(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-readonly-prune",
            "--branch",
            "feature/read-commands-do-not-prune",
            "--purpose",
            "Verify read commands do not mutate ledger",
        )
        worktree_path = Path(str(start["path"]))
        run_git(self.repo, "worktree", "remove", "--force", str(worktree_path))
        run_git(self.repo, "worktree", "prune")

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        before = ledger_path.read_bytes()
        scan = run_gitwarp(self.repo, "scan", "--cwd", str(self.repo))
        board = run_gitwarp(self.repo, "board", "--cwd", str(self.repo))
        context = run_gitwarp(self.repo, "context", "--cwd", str(self.repo))
        after = ledger_path.read_bytes()

        self.assertEqual(before, after)
        self.assertEqual(scan["tracked_entries"], 1)
        self.assertEqual(len(scan["worktrees"]), 1)
        self.assertEqual(len(board["worktrees"]), 1)
        self.assertTrue(context["worktree"]["is_main"])  # type: ignore[index]

    def test_reconcile_reports_findings_without_mutating_ledger(self) -> None:
        tracked = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-reconcile",
            "--branch",
            "feature/reconcile-tracked",
            "--purpose",
            "Track reconcile findings",
        )
        tracked_path = Path(str(tracked["path"]))
        (tracked_path / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        run_gitwarp(
            self.repo,
            "handoff",
            "--cwd",
            str(tracked_path),
            "--status",
            "blocked",
            "--progress",
            "Waiting on input",
        )
        Path(str(tracked["lessons_md"])).unlink()

        untracked_path = self.repo / "manual-untracked"
        run_git(self.repo, "worktree", "add", "-b", "feature/manual-untracked", str(untracked_path), "HEAD")

        merged_path = self.repo / "manual-merged"
        run_git(self.repo, "worktree", "add", "-b", "feature/already-merged", str(merged_path), "HEAD")

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["entries"].append(
            {
                "path": str(self.repo / "missing-worktree"),
                "branch": "feature/missing-worktree",
                "agent_id": "missing-agent",
                "purpose": "Missing worktree",
                "status": "dispatch_failed",
                "notes": [],
                "created_at": "2000-01-01T00:00:00+00:00",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        )
        ledger["entries"].append(
            {
                "path": str(merged_path.resolve()),
                "branch": "feature/already-merged",
                "agent_id": "merged-agent",
                "purpose": "Already merged",
                "status": "merged",
                "notes": [],
                "created_at": "2000-01-01T00:00:00+00:00",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        )
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        before = ledger_path.read_bytes()

        reconcile = run_gitwarp(self.repo, "reconcile", "--cwd", str(self.repo), "--stale", "0")
        after = ledger_path.read_bytes()
        self.assertEqual(before, after)
        codes = {finding["code"] for finding in reconcile["findings"]}  # type: ignore[index]
        self.assertIn("stale_ledger_entry", codes)
        self.assertIn("untracked_worktree", codes)
        self.assertIn("missing_dossier_file", codes)
        self.assertIn("dirty_worktree", codes)
        self.assertIn("attention_status", codes)
        self.assertIn("stale_worktree", codes)
        self.assertIn("merged_head", codes)
        self.assertGreaterEqual(reconcile["summary"]["total"], 7)  # type: ignore[index]

    def test_reconcile_and_enter_report_head_drift_without_mutation(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-drift",
            "--branch",
            "feature/head-drift",
            "--purpose",
            "Detect unmanaged commits",
        )
        worktree_path = Path(str(start["path"]))
        recorded_head = str(start["head"])

        (worktree_path / "drift.txt").write_text("manual commit\n", encoding="utf-8")
        run_git(worktree_path, "add", "drift.txt")
        run_git(worktree_path, "commit", "-m", "manual drift")
        current_head = run_git(worktree_path, "rev-parse", "HEAD")
        self.assertNotEqual(recorded_head, current_head)

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        before = ledger_path.read_bytes()
        reconcile = run_gitwarp(self.repo, "reconcile", "--cwd", str(self.repo))
        enter = run_gitwarp(self.repo, "enter", "--cwd", str(worktree_path))
        after = ledger_path.read_bytes()

        self.assertEqual(before, after)
        drift_findings = findings_with_code(reconcile, "head_drift")
        self.assertEqual(len(drift_findings), 1)
        self.assertEqual(drift_findings[0]["branch"], "feature/head-drift")
        drift = enter["worktree"]["head_drift"]  # type: ignore[index]
        self.assertTrue(drift["drifted"])  # type: ignore[index]
        self.assertEqual(drift["last_seen_head"], recorded_head)  # type: ignore[index]
        self.assertEqual(drift["current_head"], current_head)  # type: ignore[index]

    def test_head_drift_is_absent_for_healthy_worktree(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-no-drift",
            "--branch",
            "feature/no-head-drift",
            "--purpose",
            "Verify healthy drift output",
        )
        worktree_path = Path(str(start["path"]))

        enter = run_gitwarp(self.repo, "enter", "--cwd", str(worktree_path))
        board = run_gitwarp(self.repo, "board", "--cwd", str(self.repo), "--verbose")

        self.assertNotIn("head_drift", enter["worktree"])  # type: ignore[operator]
        row = next(item for item in board["worktrees"] if item["branch"] == "feature/no-head-drift")  # type: ignore[index]
        self.assertNotIn("head_drift", row)

    def test_annotate_does_not_clear_head_drift(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-annotate-drift",
            "--branch",
            "feature/annotate-head-drift",
            "--purpose",
            "Verify annotate does not acknowledge commits",
        )
        worktree_path = Path(str(start["path"]))
        recorded_head = str(start["head"])

        (worktree_path / "annotate-drift.txt").write_text("manual commit\n", encoding="utf-8")
        run_git(worktree_path, "add", "annotate-drift.txt")
        run_git(worktree_path, "commit", "-m", "manual annotate drift")
        current_head = run_git(worktree_path, "rev-parse", "HEAD")

        run_gitwarp(
            self.repo,
            "annotate",
            "--cwd",
            str(worktree_path),
            "--note",
            "Observed manual commit",
        )
        reconcile = run_gitwarp(self.repo, "reconcile", "--cwd", str(self.repo))
        enter = run_gitwarp(self.repo, "enter", "--cwd", str(worktree_path))

        drift_findings = findings_with_code(reconcile, "head_drift")
        self.assertEqual(len(drift_findings), 1)
        drift = enter["worktree"]["head_drift"]  # type: ignore[index]
        self.assertEqual(drift["last_seen_head"], recorded_head)  # type: ignore[index]
        self.assertEqual(drift["current_head"], current_head)  # type: ignore[index]
