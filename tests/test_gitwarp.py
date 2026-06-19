from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "gitwarp" / "scripts" / "gitwarp.py"


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def run_gitwarp(repo: Path, *args: str, expect_ok: bool = True) -> dict[str, object]:
    result = subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout.strip())
    if expect_ok:
        assert result.returncode == 0, result.stdout or result.stderr
        assert payload["ok"] is True, payload
    else:
        assert result.returncode != 0, payload
        assert payload["ok"] is False, payload
    return payload


def run_gitwarp_text(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class GitWarpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        run_git(self.repo, "init", "-b", "main")
        run_git(self.repo, "config", "user.name", "Test User")
        run_git(self.repo, "config", "user.email", "test@example.com")
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        run_git(self.repo, "add", "README.md")
        run_git(self.repo, "commit", "-m", "init")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

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
            ["python3", str(SCRIPT), "statusline", "--cwd", str(nested_path)],
            cwd=str(self.repo),
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

    def test_existing_branch_and_collision_are_reported(self) -> None:
        run_git(self.repo, "branch", "feature/existing")

        summon = run_gitwarp(
            self.repo,
            "summon",
            "--agent-id",
            "claude-beta",
            "--branch",
            "feature/existing",
            "--purpose",
            "Reuse prepared branch",
        )
        self.assertEqual(summon["branch_created"], False)

        collision = run_gitwarp(
            self.repo,
            "summon",
            "--agent-id",
            "codex-gamma",
            "--branch",
            "feature/existing",
            "--purpose",
            "Should fail",
            expect_ok=False,
        )
        self.assertIn("branch collision", str(collision["error"]))

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
        self.assertIn("gitwarp start", " ".join(main_enter["recommended_next"]))  # type: ignore[arg-type]

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

    def test_handoff_board_and_finish_preserve_dossier(self) -> None:
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
            ["python3", str(SCRIPT), "board", "--cwd", str(self.repo), "--format", "table"],
            cwd=str(self.repo),
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
            "Keep dossier after collapse",
            "--collapse",
        )
        self.assertEqual(finish["status"], "pushed")
        self.assertEqual(finish["collapsed"], True)
        self.assertFalse(worktree_path.exists())
        self.assertTrue(progress_md.exists())
        self.assertTrue(lessons_md.exists())
        self.assertIn("Verified and pushed", progress_md.read_text(encoding="utf-8"))
        self.assertIn("Keep dossier after collapse", lessons_md.read_text(encoding="utf-8"))

    def test_board_filters_status_stale_and_verbose_snippets(self) -> None:
        testing = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-board",
            "--branch",
            "feature/board-testing",
            "--purpose",
            "Build board filtering",
        )
        blocked = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "claude-board",
            "--branch",
            "feature/board-blocked",
            "--purpose",
            "Investigate blocker visibility",
        )

        run_gitwarp(
            self.repo,
            "handoff",
            "--cwd",
            str(testing["path"]),
            "--status",
            "testing",
            "--progress",
            "Parser done",
            "--lesson",
            "Use board before dispatch",
        )
        run_gitwarp(
            self.repo,
            "handoff",
            "--cwd",
            str(blocked["path"]),
            "--status",
            "blocked",
            "--progress",
            "Waiting for dependency",
        )

        filtered = run_gitwarp(self.repo, "board", "--status", "testing")
        filtered_branches = {row["branch"] for row in filtered["worktrees"]}  # type: ignore[index]
        self.assertEqual(filtered_branches, {"feature/board-testing"})

        stale = run_gitwarp(self.repo, "board", "--stale", "0")
        stale_row = next(row for row in stale["worktrees"] if row["branch"] == "feature/board-testing")  # type: ignore[index]
        self.assertEqual(stale_row["stale"], True)  # type: ignore[index]
        self.assertIsInstance(stale_row["age_seconds"], int)  # type: ignore[index]

        verbose = run_gitwarp(self.repo, "board", "--verbose")
        verbose_row = next(row for row in verbose["worktrees"] if row["branch"] == "feature/board-testing")  # type: ignore[index]
        snippets = verbose_row["snippets"]  # type: ignore[index]
        self.assertIn("Build board filtering", snippets["task"])  # type: ignore[index]
        self.assertIn("Parser done", snippets["progress"])  # type: ignore[index]
        self.assertIn("Use board before dispatch", snippets["lessons"])  # type: ignore[index]

    def test_parallel_handoffs_do_not_lose_ledger_updates(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-parallel",
            "--branch",
            "feature/parallel-handoff",
            "--purpose",
            "Verify concurrent handoff safety",
        )
        worktree_path = Path(str(start["path"]))

        expected_notes: list[str] = []
        for round_index in range(10):
            results: list[subprocess.CompletedProcess[str] | None] = [None] * 8
            threads = []
            for worker_index in range(8):
                progress = f"parallel progress {round_index}-{worker_index}"
                expected_notes.append(progress)

                def run_handoff(index: int = worker_index, note: str = progress) -> None:
                    results[index] = subprocess.run(
                        [
                            "python3",
                            str(SCRIPT),
                            "handoff",
                            "--cwd",
                            str(worktree_path),
                            "--status",
                            "testing",
                            "--progress",
                            note,
                        ],
                        cwd=str(self.repo),
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                thread = threading.Thread(target=run_handoff)
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
            for result in results:
                self.assertIsNotNone(result)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)  # type: ignore[union-attr]

        context = run_gitwarp(self.repo, "context", "--cwd", str(worktree_path))
        notes = [item["note"] for item in context["worktree"]["notes"]]  # type: ignore[index]
        for expected in expected_notes:
            self.assertIn(expected, notes)
        self.assertFalse((self.repo / ".gitwarp" / "ledger.lock").exists())

    def test_agents_lists_builtin_templates_without_config(self) -> None:
        agents = run_gitwarp(self.repo, "agents", "--cwd", str(self.repo))
        self.assertEqual(Path(str(agents["config_path"])), (self.repo / ".gitwarp" / "agents.json").resolve())
        rows = {item["name"]: item for item in agents["agents"]}  # type: ignore[index]
        self.assertIn("codex", rows)
        self.assertIn("claude", rows)
        self.assertEqual(rows["codex"]["configured"], False)
        self.assertEqual(rows["claude"]["configured"], False)
        self.assertIn("{worktree}", rows["codex"]["command"])  # type: ignore[operator]
        self.assertIn("{prompt}", rows["codex"]["command"])  # type: ignore[operator]

    def test_agents_loads_json_config_and_validates_templates(self) -> None:
        config_path = self.repo / ".gitwarp" / "agents.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "default_agent": "local",
                    "agents": {
                        "local": {
                            "description": "Local test agent",
                            "command": ["python3", "-c", "{prompt}", "{worktree}"],
                            "status": "enabled",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        agents = run_gitwarp(self.repo, "agents", "--cwd", str(self.repo))
        rows = {item["name"]: item for item in agents["agents"]}  # type: ignore[index]
        self.assertEqual(agents["default_agent"], "local")
        self.assertEqual(rows["local"]["configured"], True)
        self.assertEqual(rows["local"]["available"], True)
        self.assertEqual(rows["local"]["command"], ["python3", "-c", "{prompt}", "{worktree}"])

        bad_configs = [
            {"version": 2, "agents": {}},
            {"version": 1, "agents": {"bad": {"command": ["python3", "{prompt}"]}}},
            {"version": 1, "agents": {"bad": {"command": ["python3", "{worktree}"]}}},
            {"version": 1, "agents": {"bad": {"command": ["python3", "{unknown}", "{worktree}", "{prompt}"]}}},
        ]
        for bad_config in bad_configs:
            with self.subTest(config=bad_config):
                config_path.write_text(json.dumps(bad_config), encoding="utf-8")
                result = run_gitwarp(self.repo, "agents", "--cwd", str(self.repo), expect_ok=False)
                self.assertIn("agent config", str(result["error"]))

    def test_dispatch_print_creates_worktree_and_renders_launch_command(self) -> None:
        config_path = self.repo / ".gitwarp" / "agents.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "default_agent": "local",
                    "agents": {
                        "local": {
                            "description": "Local test agent",
                            "command": ["python3", "-c", "{prompt}", "{worktree}"],
                            "status": "enabled",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        dispatch = run_gitwarp(
            self.repo,
            "dispatch",
            "--cwd",
            str(self.repo),
            "--agent",
            "local",
            "--branch",
            "feature/dispatch-print",
            "--purpose",
            "Implement dispatch print",
        )
        worktree_path = Path(str(dispatch["path"]))
        self.assertEqual(dispatch["mode"], "print")
        self.assertEqual(dispatch["agent"], "local")
        self.assertEqual(dispatch["status"], "dispatched")
        self.assertTrue(worktree_path.exists())
        self.assertEqual(Path(str(dispatch["task_md"])).exists(), True)
        command = dispatch["launch_command"]  # type: ignore[assignment]
        self.assertIn(str(worktree_path), command)  # type: ignore[arg-type]
        prompt_arg = command[-2]  # type: ignore[index]
        self.assertIn("gitwarp enter", prompt_arg)
        self.assertIn("gitwarp handoff", prompt_arg)
        self.assertIn("Implement dispatch print", prompt_arg)
        self.assertIn(str(worktree_path), dispatch["launch_preview"])

        context = run_gitwarp(self.repo, "context", "--cwd", str(worktree_path))
        worktree = context["worktree"]  # type: ignore[index]
        self.assertEqual(worktree["status"], "dispatched")  # type: ignore[index]
        self.assertEqual(worktree["agent_id"], "local-feature-dispatch-print")  # type: ignore[index]

    def test_dispatch_execute_is_rejected_before_mutation(self) -> None:
        result = run_gitwarp(
            self.repo,
            "dispatch",
            "--cwd",
            str(self.repo),
            "--agent",
            "codex",
            "--branch",
            "feature/execute-unsupported",
            "--purpose",
            "Should not mutate",
            "--command-mode",
            "execute",
            expect_ok=False,
        )
        self.assertIn("execute", str(result["error"]))
        branches = run_git(self.repo, "branch", "--list", "feature/execute-unsupported")
        self.assertEqual(branches, "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "feature-execute-unsupported").exists())
        scan = run_gitwarp(self.repo, "scan", "--cwd", str(self.repo))
        self.assertNotIn(
            "feature/execute-unsupported",
            {item["branch"] for item in scan["worktrees"]},  # type: ignore[index]
        )

    def test_adopt_binds_existing_worktree_and_repairs_dossier(self) -> None:
        manual_path = self.repo / "manual-worktree"
        run_git(self.repo, "worktree", "add", "-b", "feature/manual-adopt", str(manual_path), "HEAD")

        adopt = run_gitwarp(
            self.repo,
            "adopt",
            "--cwd",
            str(self.repo),
            "--path",
            str(manual_path),
            "--agent-id",
            "claude-existing",
            "--purpose",
            "Continue existing work",
        )
        self.assertEqual(adopt["status"], "adopted")
        self.assertEqual(adopt["branch"], "feature/manual-adopt")
        self.assertEqual(adopt["agent_id"], "claude-existing")
        self.assertEqual(adopt["outside_guarded_root"], True)
        self.assertTrue(Path(str(adopt["task_md"])).exists())
        self.assertTrue(Path(str(adopt["progress_md"])).exists())
        self.assertTrue(Path(str(adopt["lessons_md"])).exists())

        context = run_gitwarp(self.repo, "context", "--cwd", str(manual_path))
        worktree = context["worktree"]  # type: ignore[index]
        self.assertEqual(worktree["status"], "adopted")  # type: ignore[index]
        self.assertEqual(worktree["purpose"], "Continue existing work")  # type: ignore[index]

        main_refusal = run_gitwarp(
            self.repo,
            "adopt",
            "--cwd",
            str(self.repo),
            "--path",
            str(self.repo),
            "--agent-id",
            "bad-main",
            "--purpose",
            "Should fail",
            expect_ok=False,
        )
        self.assertIn("main", str(main_refusal["error"]))

        run_git(self.repo, "worktree", "add", "-b", "feature/manual-second", str(self.repo / "manual-second"), "HEAD")
        duplicate_agent = run_gitwarp(
            self.repo,
            "adopt",
            "--cwd",
            str(self.repo),
            "--path",
            str(self.repo / "manual-second"),
            "--agent-id",
            "claude-existing",
            "--purpose",
            "Should fail duplicate agent",
            expect_ok=False,
        )
        self.assertIn("agent", str(duplicate_agent["error"]))

        updated_same_path = run_gitwarp(
            self.repo,
            "adopt",
            "--cwd",
            str(self.repo),
            "--path",
            str(manual_path),
            "--agent-id",
            "other-agent",
            "--purpose",
            "Update same worktree ownership",
        )
        self.assertEqual(updated_same_path["agent_id"], "other-agent")
        self.assertEqual(updated_same_path["path"], str(manual_path.resolve()))

        detached_path = self.repo / "manual-detached"
        run_git(self.repo, "worktree", "add", "--detach", str(detached_path), "HEAD")
        detached = run_gitwarp(
            self.repo,
            "adopt",
            "--cwd",
            str(self.repo),
            "--path",
            str(detached_path),
            "--agent-id",
            "detached-agent",
            "--purpose",
            "Should fail detached",
            expect_ok=False,
        )
        self.assertIn("detached", str(detached["error"]))

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

    def test_doctor_reports_environment_without_mutation(self) -> None:
        run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-doctor",
            "--branch",
            "feature/doctor",
            "--purpose",
            "Doctor environment",
        )
        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        before = ledger_path.read_bytes()

        doctor = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))
        after = ledger_path.read_bytes()
        self.assertEqual(before, after)
        findings = doctor["findings"]  # type: ignore[index]
        codes = {finding["code"] for finding in findings}
        severities = {finding["severity"] for finding in findings}
        self.assertIn("git", codes)
        self.assertIn("python3", codes)
        self.assertIn("gitwarp_launcher", codes)
        self.assertIn("gitwarp_ignored", codes)
        self.assertIn("codex_plugin_metadata", codes)
        self.assertIn("session_hook_context", codes)
        self.assertLessEqual(severities, {"ok", "warning", "error"})
        self.assertEqual(doctor["summary"]["total"], len(findings))  # type: ignore[index]


class PluginStructureTests(unittest.TestCase):
    def test_codex_plugin_points_at_canonical_skill_and_hooks(self) -> None:
        plugin = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "api_marketplace.json").read_text(encoding="utf-8"))
        hooks = json.loads((REPO_ROOT / "hooks" / "hooks-codex.json").read_text(encoding="utf-8"))
        session_hook = (REPO_ROOT / "hooks" / "session-start-codex").read_text(encoding="utf-8")
        codex_skill_link = REPO_ROOT / ".agents" / "skills" / "gitwarp"
        claude_skill_link = REPO_ROOT / ".claude" / "skills" / "gitwarp"

        self.assertEqual(plugin["name"], "gitwarp")
        self.assertEqual(plugin["skills"], "./skills/")
        self.assertNotIn("hooks", plugin)
        self.assertEqual(marketplace["name"], "gitwarp-dev")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/gitwarp")
        self.assertIn("CODEX", marketplace["plugins"][0]["policy"]["products"])
        self.assertIn("SessionStart", hooks["hooks"])
        self.assertIn("gitwarp enter --cwd", session_hook)
        self.assertIn("gitwarp start", session_hook)
        self.assertIn("gitwarp handoff", session_hook)
        self.assertTrue(codex_skill_link.is_symlink())
        self.assertTrue(claude_skill_link.is_symlink())
        self.assertEqual(codex_skill_link.resolve(), (REPO_ROOT / "skills" / "gitwarp").resolve())
        self.assertEqual(claude_skill_link.resolve(), (REPO_ROOT / "skills" / "gitwarp").resolve())

    def test_marketplace_plugin_package_matches_root_sources(self) -> None:
        relative_paths = [
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "hooks/hooks.json",
            "hooks/hooks-codex.json",
            "hooks/run-hook.cmd",
            "hooks/session-start",
            "hooks/session-start-codex",
            "skills/gitwarp/SKILL.md",
            "skills/gitwarp/agents/openai.yaml",
            "skills/gitwarp/references/install.md",
            "skills/gitwarp/scripts/gitwarp.py",
            "skills/gitwarp/scripts/install_cli.py",
        ]

        for relative_path in relative_paths:
            with self.subTest(path=relative_path):
                self.assertEqual(
                    (REPO_ROOT / relative_path).read_text(encoding="utf-8"),
                    (REPO_ROOT / "plugins" / "gitwarp" / relative_path).read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
