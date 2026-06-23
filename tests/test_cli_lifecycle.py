from __future__ import annotations

import shlex

from helpers import *


class CliLifecycleTests(GitWarpTestCase):
    def test_create_switch_and_remove_are_primary_workspace_commands(self) -> None:
        create = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "feature/primary-commands",
            "--purpose",
            "Exercise primary workspace commands",
        )
        worktree_path = Path(str(create["path"]))

        self.assertTrue(worktree_path.exists())
        self.assertEqual(create["branch"], "feature/primary-commands")
        self.assertEqual(create["agent_id"], "agent-feature-primary-commands")
        self.assertEqual(create["status"], "active")
        self.assertEqual(create["branch_role"], "task")
        self.assertEqual(create["base_branch"], "main")
        self.assertEqual(create["shell_command"], f"cd {shlex.quote(str(worktree_path))}")
        self.assertTrue(Path(str(create["task_md"])).exists())
        dossier_path = Path(str(create["dossier_path"]))
        self.assertTrue(dossier_path.exists())

        switch_json = run_gitwarp(self.repo, "switch", "--branch", "feature/primary-commands")
        self.assertEqual(switch_json["path"], str(worktree_path))
        self.assertEqual(switch_json["branch"], "feature/primary-commands")
        self.assertEqual(switch_json["agent_id"], "agent-feature-primary-commands")
        self.assertEqual(switch_json["branch_role"], "task")
        self.assertEqual(switch_json["base_branch"], "main")
        self.assertEqual(switch_json["shell_command"], f"cd {shlex.quote(str(worktree_path))}")
        self.assertEqual(switch_json["statusline"], "GITWARP[agent-feature-primary-commands@feature/primary-commands]")

        switch_shell = run_gitwarp_text(
            self.repo,
            "switch",
            "--branch",
            "feature/primary-commands",
            "--format",
            "shell",
        )
        self.assertEqual(switch_shell, f"cd {shlex.quote(str(worktree_path))}")

        switch_main = run_gitwarp(self.repo, "switch", "--main")
        self.assertEqual(switch_main["path"], str(self.repo.resolve()))
        self.assertEqual(switch_main["branch_role"], "base")
        self.assertEqual(switch_main["statusline"], "GITWARP[main-repo]")

        remove = run_gitwarp(self.repo, "remove", "--branch", "feature/primary-commands")
        self.assertEqual(remove["removed_path"], str(worktree_path))
        self.assertEqual(remove["removed_branch"], "feature/primary-commands")
        self.assertEqual(remove["dossier_path"], str(dossier_path))
        self.assertTrue(remove["purged_dossier"])
        self.assertFalse(worktree_path.exists())
        self.assertFalse(dossier_path.exists())
        self.assertIn("feature/primary-commands", run_git(self.repo, "branch", "--list", "feature/primary-commands"))

        current_create = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "feature/remove-current",
            "--purpose",
            "Remove current sandbox",
        )
        current_path = Path(str(current_create["path"]))
        current_dossier_path = Path(str(current_create["dossier_path"]))
        nested_current_path = current_path / "packages" / "agent"
        nested_current_path.mkdir(parents=True)
        current_remove = run_gitwarp(nested_current_path, "remove")
        self.assertEqual(current_remove["removed_path"], str(current_path))
        self.assertEqual(current_remove["removed_branch"], "feature/remove-current")
        self.assertEqual(current_remove["dossier_path"], str(current_dossier_path))
        self.assertTrue(current_remove["purged_dossier"])
        self.assertFalse(current_path.exists())
        self.assertFalse(current_dossier_path.exists())

        dirty_create = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "feature/remove-dirty",
            "--purpose",
            "Refuse unsafe remove",
        )
        dirty_path = Path(str(dirty_create["path"]))
        dirty_dossier_path = Path(str(dirty_create["dossier_path"]))
        (dirty_path / "untracked.txt").write_text("dirty\n", encoding="utf-8")

        refused = run_gitwarp(self.repo, "remove", "--branch", "feature/remove-dirty", expect_ok=False)
        self.assertIn("--force", str(refused["error"]))
        self.assertTrue(dirty_path.exists())

        forced = run_gitwarp(self.repo, "remove", "--branch", "feature/remove-dirty", "--force")
        self.assertEqual(forced["removed_path"], str(dirty_path))
        self.assertEqual(forced["removed_branch"], "feature/remove-dirty")
        self.assertEqual(forced["dossier_path"], str(dirty_dossier_path))
        self.assertTrue(forced["purged_dossier"])
        self.assertFalse(dirty_path.exists())
        self.assertFalse(dirty_dossier_path.exists())

    def test_scan_summon_statusline_and_collapse(self) -> None:
        scan = run_gitwarp(self.repo, "scan")
        self.assertEqual(Path(str(scan["repo_root"])).resolve(), self.repo.resolve())
        self.assertEqual(len(scan["worktrees"]), 1)

        main_context = run_gitwarp(self.repo, "context", "--cwd", str(self.repo))
        self.assertTrue(main_context["worktree"]["is_main"])  # type: ignore[index]
        self.assertEqual(main_context["worktree"]["branch"], "main")  # type: ignore[index]
        self.assertIsNone(main_context["worktree"]["agent_id"])  # type: ignore[index]

        summon = run_gitwarp(
            self.repo,
            "summon",
            "--agent-id",
            "codex-alpha",
            "--branch",
            "feature/statusline",
            "--purpose",
            "Implement prompt banner",
        )
        worktree_path = Path(str(summon["path"]))
        self.assertTrue(worktree_path.exists())
        self.assertEqual(summon["branch_created"], True)
        nested_path = worktree_path / "src"
        nested_path.mkdir()

        scan_after = run_gitwarp(self.repo, "scan")
        live = {item["path"]: item for item in scan_after["worktrees"]}  # type: ignore[index]
        self.assertIn(str(worktree_path), live)
        self.assertEqual(live[str(worktree_path)]["agent_id"], "codex-alpha")
        self.assertEqual(live[str(worktree_path)]["purpose"], "Implement prompt banner")

        statusline = subprocess.run(
            [*gitwarp_command(), "statusline", "--cwd", str(nested_path)],
            cwd=str(self.repo),
            env=gitwarp_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(statusline.stdout.strip(), "GITWARP[codex-alpha@feature/statusline]")

        annotate = run_gitwarp(
            self.repo,
            "annotate",
            "--cwd",
            str(nested_path),
            "--status",
            "testing",
            "--note",
            "Implemented prompt banner lookup",
        )
        self.assertEqual(annotate["branch"], "feature/statusline")
        self.assertEqual(annotate["status"], "testing")
        self.assertEqual(annotate["notes_count"], 1)

        context = run_gitwarp(self.repo, "context", "--cwd", str(nested_path))
        current = context["worktree"]  # type: ignore[index]
        self.assertEqual(context["cwd"], str(nested_path))
        self.assertFalse(current["is_main"])  # type: ignore[index]
        self.assertEqual(current["path"], str(worktree_path))  # type: ignore[index]
        self.assertEqual(current["branch"], "feature/statusline")  # type: ignore[index]
        self.assertEqual(current["agent_id"], "codex-alpha")  # type: ignore[index]
        self.assertEqual(current["purpose"], "Implement prompt banner")  # type: ignore[index]
        self.assertEqual(current["status"], "testing")  # type: ignore[index]
        self.assertEqual(current["notes"][-1]["note"], "Implemented prompt banner lookup")  # type: ignore[index]

        collapse = run_gitwarp(self.repo, "collapse", "--branch", "feature/statusline")
        self.assertEqual(collapse["removed_branch"], "feature/statusline")
        self.assertFalse(worktree_path.exists())

        final_scan = run_gitwarp(self.repo, "scan")
        self.assertEqual(len(final_scan["worktrees"]), 1)

    def test_start_creates_dossier_and_context_exposes_paths(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-dossier",
            "--branch",
            "feature/dossier",
            "--purpose",
            "Build dossier workflow",
        )
        worktree_path = Path(str(start["path"]))
        nested_path = worktree_path / "packages" / "cli"
        nested_path.mkdir(parents=True)

        self.assertTrue(worktree_path.exists())
        self.assertEqual(start["branch"], "feature/dossier")
        self.assertEqual(start["agent_id"], "codex-dossier")
        self.assertEqual(start["purpose"], "Build dossier workflow")
        self.assertEqual(start["status"], "active")

        dossier_path = Path(str(start["dossier_path"]))
        task_md = Path(str(start["task_md"]))
        progress_md = Path(str(start["progress_md"]))
        lessons_md = Path(str(start["lessons_md"]))
        self.assertEqual(dossier_path.parent.resolve(), (self.repo / ".gitwarp" / "dossiers").resolve())
        self.assertTrue(task_md.exists())
        self.assertTrue(progress_md.exists())
        self.assertTrue(lessons_md.exists())
        self.assertIn("Build dossier workflow", task_md.read_text(encoding="utf-8"))
        self.assertIn("Workspace created.", progress_md.read_text(encoding="utf-8"))
        self.assertIn("Notes For Future Agents", lessons_md.read_text(encoding="utf-8"))

        context = run_gitwarp(self.repo, "context", "--cwd", str(nested_path))
        worktree = context["worktree"]  # type: ignore[index]
        self.assertEqual(worktree["path"], str(worktree_path))  # type: ignore[index]
        self.assertEqual(worktree["dossier_path"], str(dossier_path))  # type: ignore[index]
        self.assertEqual(worktree["task_md"], str(task_md))  # type: ignore[index]
        self.assertEqual(worktree["progress_md"], str(progress_md))  # type: ignore[index]
        self.assertEqual(worktree["lessons_md"], str(lessons_md))  # type: ignore[index]

    def test_enter_reports_main_and_worktree_dossier_context(self) -> None:
        main_enter = run_gitwarp(self.repo, "enter", "--cwd", str(self.repo))
        self.assertEqual(main_enter["location"], "main")
        self.assertEqual(main_enter["statusline"], "GITWARP[main-repo]")
        self.assertIn("gitwarp task create", " ".join(main_enter["recommended_next"]))  # type: ignore[arg-type]

        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-enter",
            "--branch",
            "feature/enter-context",
            "--purpose",
            "Build automatic entry context",
        )
        worktree_path = Path(str(start["path"]))
        nested_path = worktree_path / "packages" / "cli"
        nested_path.mkdir(parents=True)

        run_gitwarp(
            self.repo,
            "handoff",
            "--cwd",
            str(nested_path),
            "--status",
            "testing",
            "--progress",
            "Parser done",
            "--lesson",
            "Read dossier before edits",
        )

        enter = run_gitwarp(self.repo, "enter", "--cwd", str(nested_path))
        self.assertEqual(enter["location"], "worktree")
        self.assertEqual(enter["statusline"], "GITWARP[codex-enter@feature/enter-context]")
        self.assertEqual(enter["cwd"], str(nested_path))
        worktree = enter["worktree"]  # type: ignore[index]
        snippets = enter["snippets"]  # type: ignore[index]
        self.assertEqual(worktree["branch"], "feature/enter-context")  # type: ignore[index]
        self.assertEqual(worktree["agent_id"], "codex-enter")  # type: ignore[index]
        self.assertEqual(worktree["task_md"], start["task_md"])  # type: ignore[index]
        self.assertIn("Build automatic entry context", snippets["task"])  # type: ignore[index]
        self.assertIn("Parser done", snippets["progress"])  # type: ignore[index]
        self.assertIn("Read dossier before edits", snippets["lessons"])  # type: ignore[index]
        self.assertIn("gitwarp handoff", " ".join(enter["recommended_next"]))  # type: ignore[arg-type]

        prompt = run_gitwarp_text(self.repo, "enter", "--cwd", str(nested_path), "--format", "prompt")
        self.assertIn("GitWarp Context: GITWARP[codex-enter@feature/enter-context]", prompt)
        self.assertIn("task.md", prompt)
        self.assertIn("progress.md", prompt)
        self.assertIn("lessons.md", prompt)
        self.assertIn("Parser done", prompt)

    def test_handoff_board_and_finish_collapse_purges_dossier_without_deleting_branch(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-dossier",
            "--branch",
            "feature/dossier-flow",
            "--purpose",
            "Build dossier flow",
        )
        worktree_path = Path(str(start["path"]))
        dossier_path = Path(str(start["dossier_path"]))
        progress_md = Path(str(start["progress_md"]))
        lessons_md = Path(str(start["lessons_md"]))

        handoff = run_gitwarp(
            self.repo,
            "handoff",
            "--cwd",
            str(worktree_path),
            "--status",
            "testing",
            "--progress",
            "Parser done",
            "--lesson",
            "Use context before edits",
        )
        self.assertEqual(handoff["status"], "testing")
        self.assertEqual(handoff["latest_progress"], "Parser done")
        self.assertEqual(handoff["latest_lesson"], "Use context before edits")
        self.assertIn("Parser done", progress_md.read_text(encoding="utf-8"))
        self.assertIn("Use context before edits", lessons_md.read_text(encoding="utf-8"))

        board = run_gitwarp(self.repo, "board", "--format", "json")
        rows = board["worktrees"]  # type: ignore[index]
        row = next(item for item in rows if item["branch"] == "feature/dossier-flow")  # type: ignore[index]
        self.assertEqual(row["agent_id"], "codex-dossier")  # type: ignore[index]
        self.assertEqual(row["status"], "testing")  # type: ignore[index]
        self.assertEqual(row["latest_progress"], "Parser done")  # type: ignore[index]
        self.assertEqual(row["latest_lesson"], "Use context before edits")  # type: ignore[index]
        self.assertEqual(row["progress_md"], str(progress_md))  # type: ignore[index]
        self.assertEqual(row["lessons_md"], str(lessons_md))  # type: ignore[index]

        table = subprocess.run(
            [*gitwarp_command(), "board", "--cwd", str(self.repo), "--format", "table"],
            cwd=str(self.repo),
            env=gitwarp_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("feature/dossier-flow", table.stdout)
        self.assertIn("Parser done", table.stdout)

        finish = run_gitwarp(
            self.repo,
            "finish",
            "--cwd",
            str(worktree_path),
            "--status",
            "pushed",
            "--progress",
            "Verified and pushed",
            "--lesson",
            "Dossier is lifecycle-scoped to active sandbox",
            "--collapse",
        )
        self.assertEqual(finish["status"], "pushed")
        self.assertEqual(finish["collapsed"], True)
        self.assertTrue(finish["purged_dossier"])
        self.assertEqual(finish["dossier_path"], str(dossier_path))
        self.assertFalse(worktree_path.exists())
        self.assertFalse(dossier_path.exists())
        self.assertFalse(progress_md.exists())
        self.assertFalse(lessons_md.exists())
        self.assertIn("feature/dossier-flow", run_git(self.repo, "branch", "--list", "feature/dossier-flow"))

    def test_finish_without_collapse_leaves_worktree_dossier_and_ledger_intact(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-review-stop",
            "--branch",
            "feature/review-stop",
            "--purpose",
            "Stop for human review",
        )
        worktree_path = Path(str(start["path"]))
        dossier_path = Path(str(start["dossier_path"]))

        finish = run_gitwarp(
            self.repo,
            "finish",
            "--cwd",
            str(worktree_path),
            "--status",
            "completed",
            "--progress",
            "Verified locally; awaiting user confirmation",
        )

        self.assertEqual(finish["status"], "completed")
        self.assertFalse(finish["collapsed"])
        self.assertFalse(finish["purged_dossier"])
        self.assertTrue(worktree_path.exists())
        self.assertTrue(dossier_path.exists())
        ledger = json.loads((self.repo / ".gitwarp" / "ledger.json").read_text(encoding="utf-8"))
        self.assertTrue(any(entry.get("path") == str(worktree_path) for entry in ledger["entries"]))
        self.assertIn("feature/review-stop", run_git(self.repo, "branch", "--list", "feature/review-stop"))

    def test_web_start_status_stop_manage_repo_local_service_state(self) -> None:
        start = run_gitwarp(
            self.repo,
            "web",
            "start",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )
        self.assertTrue(start["running"])
        self.assertTrue(start["started"])
        self.assertIsInstance(start["pid"], int)
        self.assertTrue(Path(str(start["state_path"])).exists())

        status = run_gitwarp(
            self.repo,
            "web",
            "status",
            "--cwd",
            str(self.repo),
        )
        self.assertTrue(status["running"])
        self.assertEqual(status["pid"], start["pid"])
        self.assertEqual(status["url"], start["url"])

        stop = run_gitwarp(
            self.repo,
            "web",
            "stop",
            "--cwd",
            str(self.repo),
        )
        self.assertFalse(stop["running"])
        self.assertTrue(stop["stopped"])
        self.assertFalse(Path(str(start["state_path"])).exists())

        final_status = run_gitwarp(
            self.repo,
            "web",
            "status",
            "--cwd",
            str(self.repo),
        )
        self.assertFalse(final_status["running"])

    def test_finish_collapse_dossier_purge_is_scoped_to_dossier_root(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-purge-dossier",
            "--branch",
            "feature/purge-dossier",
            "--purpose",
            "Purge completed dossier",
        )
        dossier_path = Path(str(start["dossier_path"]))
        worktree_path = Path(str(start["path"]))

        finish = run_gitwarp(
            self.repo,
            "finish",
            "--cwd",
            str(worktree_path),
            "--status",
            "pushed",
            "--progress",
            "Verified and ready to collapse",
            "--collapse",
        )

        self.assertTrue(finish["purged_dossier"])
        self.assertFalse(worktree_path.exists())
        self.assertFalse(dossier_path.exists())

        malicious = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-bad-purge",
            "--branch",
            "feature/bad-purge",
            "--purpose",
            "Reject unsafe purge",
        )
        malicious_path = Path(str(malicious["path"]))
        readme_before = (self.repo / "README.md").read_text(encoding="utf-8")
        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for entry in ledger["entries"]:
            if entry["path"] == str(malicious_path):
                entry["dossier_path"] = str(self.repo / "README.md")
                entry["task_md"] = str(self.repo / "README.md")
                entry["progress_md"] = str(self.repo / "README.md")
                entry["lessons_md"] = str(self.repo / "README.md")
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

        refused = run_gitwarp(
            self.repo,
            "finish",
            "--cwd",
            str(malicious_path),
            "--status",
            "pushed",
            "--progress",
            "Should not purge outside dossier root",
            "--collapse",
            expect_ok=False,
        )

        self.assertIn("outside GitWarp dossier root", str(refused["error"]))
        self.assertTrue(malicious_path.exists())
        self.assertTrue((self.repo / "README.md").exists())
        self.assertEqual((self.repo / "README.md").read_text(encoding="utf-8"), readme_before)
