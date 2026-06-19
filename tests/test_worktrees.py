from __future__ import annotations

from helpers import *


class WorktreeTests(GitWarpTestCase):
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
