from __future__ import annotations

from helpers import *


class WorktreeTests(GitWarpTestCase):
    def test_managed_worktree_paths_follow_branch_hierarchy(self) -> None:
        created = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "feature/nested-worktree-path",
            "--purpose",
            "Verify hierarchical worktree paths",
        )
        expected_path = self.repo / ".gitwarp" / "worktrees" / "feature" / "nested-worktree-path"
        worktree_path = Path(str(created["path"]))

        self.assertEqual(worktree_path, expected_path.resolve())
        self.assertTrue(worktree_path.exists())

        removed = run_gitwarp(self.repo, "remove", "--branch", "feature/nested-worktree-path")

        self.assertEqual(removed["removed_path"], str(expected_path.resolve()))
        self.assertFalse(worktree_path.exists())
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "feature").exists())

    def test_base_and_task_roles_group_work_to_parent_branch(self) -> None:
        base = run_gitwarp(
            self.repo,
            "create",
            "--role",
            "base",
            "--branch",
            "feature/user-request",
            "--purpose",
            "User requested feature line",
        )
        base_path = Path(str(base["path"]))
        self.assertTrue(base_path.exists())
        self.assertEqual(base["branch_role"], "base")
        self.assertIsNone(base["base_branch"])
        self.assertNotIn("task_md", base)

        task = run_gitwarp(
            base_path,
            "create",
            "--branch",
            "agent/user-request-impl",
            "--purpose",
            "Implement the user request under the feature line",
        )
        self.assertEqual(task["branch_role"], "task")
        self.assertEqual(task["base_branch"], "feature/user-request")
        self.assertTrue(Path(str(task["task_md"])).exists())

        board = run_gitwarp(self.repo, "board", "--cwd", str(self.repo))
        rows = {row["branch"]: row for row in board["worktrees"]}  # type: ignore[index]
        self.assertEqual(rows["main"]["branch_role"], "base")
        self.assertEqual(rows["feature/user-request"]["branch_role"], "base")
        self.assertEqual(rows["agent/user-request-impl"]["branch_role"], "task")
        self.assertEqual(rows["agent/user-request-impl"]["base_branch"], "feature/user-request")

    def test_finish_collapse_merged_removes_clean_task_after_parent_merge(self) -> None:
        base = run_gitwarp(
            self.repo,
            "create",
            "--role",
            "base",
            "--branch",
            "feature/parent",
            "--purpose",
            "Parent feature line",
        )
        base_path = Path(str(base["path"]))
        task = run_gitwarp(
            self.repo,
            "create",
            "--base",
            "feature/parent",
            "--branch",
            "agent/parent-task",
            "--purpose",
            "Task under parent",
        )
        task_path = Path(str(task["path"]))
        dossier_path = Path(str(task["dossier_path"]))

        (task_path / "feature.txt").write_text("done\n", encoding="utf-8")
        run_git(task_path, "add", "feature.txt")
        run_git(task_path, "commit", "-m", "task change")

        refused = run_gitwarp(
            self.repo,
            "finish",
            "--cwd",
            str(task_path),
            "--status",
            "merged",
            "--progress",
            "Attempt before merge",
            "--collapse-merged",
            expect_ok=False,
        )
        self.assertIn("merged into its base_branch", str(refused["error"]))
        self.assertTrue(task_path.exists())

        run_git(base_path, "merge", "--no-ff", "agent/parent-task", "-m", "merge task")

        finish = run_gitwarp(
            self.repo,
            "finish",
            "--cwd",
            str(task_path),
            "--status",
            "merged",
            "--progress",
            "Merged into parent",
            "--collapse-merged",
        )
        self.assertTrue(finish["collapsed"])
        self.assertTrue(finish["purged_dossier"])
        self.assertEqual(finish["removed_branch"], "agent/parent-task")
        self.assertFalse(task_path.exists())
        self.assertFalse(dossier_path.exists())
        self.assertTrue(base_path.exists())

    def test_finish_collapse_merged_backfills_legacy_role_metadata(self) -> None:
        task = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/legacy-role-output",
            "--purpose",
            "Legacy role output",
        )
        task_path = Path(str(task["path"]))
        dossier_path = Path(str(task["dossier_path"]))

        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for entry in ledger["entries"]:
            if entry.get("branch") == "agent/legacy-role-output":
                entry.pop("branch_role", None)
                entry.pop("base_branch", None)
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        (task_path / "legacy.txt").write_text("done\n", encoding="utf-8")
        run_git(task_path, "add", "legacy.txt")
        run_git(task_path, "commit", "-m", "legacy task")
        run_git(self.repo, "merge", "--no-ff", "agent/legacy-role-output", "-m", "merge legacy task")

        finish = run_gitwarp(
            self.repo,
            "finish",
            "--cwd",
            str(task_path),
            "--status",
            "merged",
            "--progress",
            "Merged legacy task",
            "--collapse-merged",
        )

        self.assertEqual(finish["branch_role"], "task")
        self.assertEqual(finish["base_branch"], "main")
        self.assertTrue(finish["collapsed"])
        self.assertTrue(finish["purged_dossier"])
        self.assertFalse(task_path.exists())
        self.assertFalse(dossier_path.exists())

    def test_sync_prunes_dead_worktree_entries_and_orphan_dossiers(self) -> None:
        task = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/dead-task",
            "--purpose",
            "Create task that disappears outside GitWarp",
        )
        task_path = Path(str(task["path"]))
        dossier_path = Path(str(task["dossier_path"]))
        self.assertTrue(dossier_path.exists())

        run_git(self.repo, "worktree", "remove", "--force", str(task_path))
        run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/next-task",
            "--purpose",
            "Trigger safe sync cleanup",
        )

        self.assertFalse(dossier_path.exists())
        board = run_gitwarp(self.repo, "board", "--cwd", str(self.repo))
        branches = {row["branch"] for row in board["worktrees"]}  # type: ignore[index]
        self.assertNotIn("agent/dead-task", branches)

    def test_sync_prunes_unreferenced_dossier_directories(self) -> None:
        task = run_gitwarp(
            self.repo,
            "create",
            "--branch",
            "agent/live-dossier",
            "--purpose",
            "Keep live dossier",
        )
        live_dossier = Path(str(task["dossier_path"]))
        orphan_dossier = self.repo / ".gitwarp" / "dossiers" / "agent-orphan-dossier-deadbeef"
        orphan_dossier.mkdir(parents=True)
        (orphan_dossier / "task.md").write_text("# Task\n", encoding="utf-8")
        (orphan_dossier / "progress.md").write_text("# Progress\n", encoding="utf-8")
        (orphan_dossier / "lessons.md").write_text("# Lessons\n", encoding="utf-8")
        manual_dir = self.repo / ".gitwarp" / "dossiers" / "manual-notes"
        manual_dir.mkdir(parents=True)
        (manual_dir / "README.md").write_text("manual\n", encoding="utf-8")

        scan = run_gitwarp(self.repo, "scan", "--cwd", str(self.repo))
        self.assertEqual(scan["tracked_entries"], 1)
        self.assertTrue(orphan_dossier.exists())

        run_gitwarp(self.repo, "init", "--cwd", str(self.repo))

        self.assertTrue(live_dossier.exists())
        self.assertFalse(orphan_dossier.exists())
        self.assertTrue(manual_dir.exists())

    def test_sync_drops_metadata_when_same_path_recreated_for_different_branch(self) -> None:
        old = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "old-agent",
            "--branch",
            "agent/old-path",
            "--purpose",
            "Old task metadata",
        )
        old_path = Path(str(old["path"]))
        old_dossier = Path(str(old["dossier_path"]))

        run_git(self.repo, "worktree", "remove", "--force", str(old_path))
        run_git(self.repo, "worktree", "add", "-b", "agent/new-path", str(old_path), "HEAD")

        run_gitwarp(self.repo, "init", "--cwd", str(self.repo))

        ledger = json.loads((self.repo / ".gitwarp" / "ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["entries"], [])
        self.assertFalse(old_dossier.exists())
        scan = run_gitwarp(self.repo, "scan", "--cwd", str(self.repo))
        rows = {row["branch"]: row for row in scan["worktrees"]}  # type: ignore[index]
        self.assertIsNone(rows["agent/new-path"]["agent_id"])
        self.assertIsNone(rows["agent/new-path"]["dossier_path"])

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
        self.assertIn("Do not push, merge, remove, or collapse unless explicitly asked.", prompt_arg)
        self.assertIn("Implement dispatch print", prompt_arg)
        self.assertIn(str(worktree_path), dispatch["launch_preview"])

        context = run_gitwarp(self.repo, "context", "--cwd", str(worktree_path))
        worktree = context["worktree"]  # type: ignore[index]
        self.assertEqual(worktree["status"], "dispatched")  # type: ignore[index]
        self.assertEqual(worktree["agent_id"], "local-feature-dispatch-print")  # type: ignore[index]

    def test_start_mounts_explicit_instruction_files(self) -> None:
        (self.repo / "docs").mkdir()
        (self.repo / "AGENTS.md").write_text("root agent rules\n", encoding="utf-8")
        (self.repo / "docs" / "codex-rules.md").write_text("codex local rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md", "docs/codex-rules.md")
        run_git(self.repo, "commit", "-m", "add instruction fixtures")

        start = run_gitwarp(
            self.repo,
            "start",
            "--cwd",
            str(self.repo),
            "--agent-id",
            "codex-instructions",
            "--branch",
            "feature/instruction-mounts",
            "--purpose",
            "Verify instruction mounts",
            "--instruction",
            "AGENTS.md",
            "--instruction",
            ".agents/CODEX.md=docs/codex-rules.md",
        )
        worktree_path = Path(str(start["path"]))
        instructions = start["instructions"]  # type: ignore[index]

        self.assertEqual([item["target"] for item in instructions], ["AGENTS.md", ".agents/CODEX.md"])  # type: ignore[index]
        self.assertEqual(start["instruction_mode"], "copy")
        self.assertEqual(instructions[1]["status"], "copied")  # type: ignore[index]
        self.assertEqual(instructions[1]["bytes"], len("codex local rules\n"))  # type: ignore[index]
        self.assertRegex(str(instructions[1]["sha256"]), r"^[a-f0-9]{64}$")  # type: ignore[index]
        self.assertEqual((worktree_path / "AGENTS.md").read_text(encoding="utf-8"), "root agent rules\n")
        self.assertEqual((worktree_path / ".agents" / "CODEX.md").read_text(encoding="utf-8"), "codex local rules\n")
        self.assertIn("Mounted Instructions", Path(str(start["task_md"])).read_text(encoding="utf-8"))

        context = run_gitwarp(self.repo, "context", "--cwd", str(worktree_path))
        worktree = context["worktree"]  # type: ignore[index]
        self.assertEqual(worktree["instructions"], instructions)  # type: ignore[index]
        prompt = run_gitwarp_text(self.repo, "enter", "--cwd", str(worktree_path), "--format", "prompt")
        self.assertIn("Instructions:", prompt)
        self.assertIn("- AGENTS.md", prompt)
        self.assertIn("- .agents/CODEX.md", prompt)

    def test_dispatch_mounts_instruction_profile_from_config(self) -> None:
        (self.repo / "docs").mkdir()
        (self.repo / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
        (self.repo / "docs" / "claude.md").write_text("claude rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md", "docs/claude.md")
        run_git(self.repo, "commit", "-m", "add profile fixtures")
        profile_path = self.repo / ".gitwarp" / "instruction_profiles.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "profiles": {
                        "claude-code": {
                            "description": "Claude Code instruction stack",
                            "instructions": [
                                "AGENTS.md",
                                {"target": "CLAUDE.md", "source": "docs/claude.md"},
                            ],
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
            "codex",
            "--branch",
            "feature/profile-mounts",
            "--purpose",
            "Verify instruction profile",
            "--instruction-profile",
            "claude-code",
        )
        worktree_path = Path(str(dispatch["path"]))

        self.assertEqual(dispatch["instruction_profile"], "claude-code")
        self.assertEqual(dispatch["instruction_mode"], "copy")
        self.assertEqual((worktree_path / "AGENTS.md").read_text(encoding="utf-8"), "root rules\n")
        self.assertEqual((worktree_path / "CLAUDE.md").read_text(encoding="utf-8"), "claude rules\n")
        self.assertIn("CLAUDE.md", Path(str(dispatch["task_md"])).read_text(encoding="utf-8"))

    def test_dispatch_rolls_back_existing_branch_when_instruction_mount_conflicts(self) -> None:
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "rules.md").write_text("source rules\n", encoding="utf-8")
        run_git(self.repo, "add", "docs/rules.md")
        run_git(self.repo, "commit", "-m", "add source rules")
        run_git(self.repo, "checkout", "-b", "feature/conflicting-mount")
        (self.repo / ".agents").mkdir()
        (self.repo / ".agents" / "CODEX.md").write_text("branch existing rules\n", encoding="utf-8")
        run_git(self.repo, "add", ".agents/CODEX.md")
        run_git(self.repo, "commit", "-m", "add conflicting branch target")
        run_git(self.repo, "checkout", "main")

        result = run_gitwarp(
            self.repo,
            "dispatch",
            "--cwd",
            str(self.repo),
            "--agent",
            "codex",
            "--branch",
            "feature/conflicting-mount",
            "--purpose",
            "Should roll back worktree on mount failure",
            "--instruction",
            ".agents/CODEX.md=docs/rules.md",
            expect_ok=False,
        )
        scan = run_gitwarp(self.repo, "scan", "--cwd", str(self.repo))

        self.assertIn("different content", str(result["error"]))
        self.assertNotEqual(run_git(self.repo, "branch", "--list", "feature/conflicting-mount"), "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "feature-conflicting-mount").exists())
        self.assertNotIn(
            "feature/conflicting-mount",
            {item["branch"] for item in scan["worktrees"]},  # type: ignore[index]
        )

    def test_start_rolls_back_partial_instruction_mount_failure(self) -> None:
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "keep.txt").write_text("keep docs directory\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md", "docs/keep.txt")
        run_git(self.repo, "commit", "-m", "add rollback fixtures")

        result = run_gitwarp(
            self.repo,
            "start",
            "--cwd",
            str(self.repo),
            "--agent-id",
            "codex-rollback",
            "--branch",
            "feature/partial-mount-failure",
            "--purpose",
            "Should roll back partial instruction mounts",
            "--instruction",
            ".mounted/AGENTS.md=AGENTS.md",
            "--instruction",
            "docs=AGENTS.md",
            expect_ok=False,
        )
        scan = run_gitwarp(self.repo, "scan", "--cwd", str(self.repo))

        self.assertIn("different content", str(result["error"]))
        self.assertEqual(run_git(self.repo, "branch", "--list", "feature/partial-mount-failure"), "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "feature-partial-mount-failure").exists())
        self.assertNotIn(
            "feature/partial-mount-failure",
            {item["branch"] for item in scan["worktrees"]},  # type: ignore[index]
        )

    def test_start_rolls_back_worktree_and_dossier_when_ledger_write_fails(self) -> None:
        ensure_src_path()
        provisioning = importlib.import_module("gitwarp.application.use_cases.provisioning")
        ledger = importlib.import_module("gitwarp.infrastructure.ledger")
        ctx = ledger.discover_repo(self.repo)
        original_mutate_ledger = provisioning.mutate_ledger

        def fail_mutate_ledger(*_args: object, **_kwargs: object) -> None:
            raise provisioning.GitWarpError("simulated ledger write failure")

        provisioning.mutate_ledger = fail_mutate_ledger
        try:
            with self.assertRaises(provisioning.GitWarpError):
                provisioning.build_start_payload(
                    ctx,
                    agent_id="codex-ledger-failure",
                    branch="feature/ledger-failure",
                    purpose="Should roll back if ledger cannot persist",
                )
        finally:
            provisioning.mutate_ledger = original_mutate_ledger

        self.assertEqual(run_git(self.repo, "branch", "--list", "feature/ledger-failure"), "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "feature-ledger-failure").exists())
        remaining_dossiers = list((self.repo / ".gitwarp" / "dossiers").glob("feature-ledger-failure-*"))
        self.assertEqual([], remaining_dossiers)

    def test_instruction_profile_schema_rejects_invalid_targets_and_duplicates(self) -> None:
        (self.repo / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md")
        run_git(self.repo, "commit", "-m", "add rules")
        profile_path = self.repo / ".gitwarp" / "instruction_profiles.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)

        profile_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "profiles": {
                        "bad-target": {
                            "instructions": [{"source": "AGENTS.md", "target": 42}],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        bad_target = run_gitwarp(
            self.repo,
            "start",
            "--cwd",
            str(self.repo),
            "--agent-id",
            "codex-bad-profile",
            "--branch",
            "feature/bad-profile",
            "--purpose",
            "Reject invalid profile target",
            "--instruction-profile",
            "bad-target",
            expect_ok=False,
        )
        self.assertIn("non-string target", str(bad_target["error"]))
        self.assertEqual(run_git(self.repo, "branch", "--list", "feature/bad-profile"), "")

        profile_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "profiles": {
                        "duplicate": {
                            "instructions": ["AGENTS.md"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        duplicate = run_gitwarp(
            self.repo,
            "dispatch",
            "--cwd",
            str(self.repo),
            "--agent",
            "codex",
            "--branch",
            "feature/duplicate-profile",
            "--purpose",
            "Reject duplicate instruction targets",
            "--instruction-profile",
            "duplicate",
            "--instruction",
            "AGENTS.md",
            expect_ok=False,
        )
        self.assertIn("specified more than once", str(duplicate["error"]))
        self.assertEqual(run_git(self.repo, "branch", "--list", "feature/duplicate-profile"), "")

    def test_instruction_symlink_mode_and_validation_do_not_mutate_on_error(self) -> None:
        (self.repo / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md")
        run_git(self.repo, "commit", "-m", "add rules")

        linked = run_gitwarp(
            self.repo,
            "start",
            "--cwd",
            str(self.repo),
            "--agent-id",
            "codex-symlink",
            "--branch",
            "feature/symlink-instructions",
            "--purpose",
            "Verify symlink mode",
            "--instruction",
            ".rules/AGENTS.md=AGENTS.md",
            "--instruction-mode",
            "symlink",
        )
        link_path = Path(str(linked["path"])) / ".rules" / "AGENTS.md"
        self.assertTrue(link_path.is_symlink())
        self.assertEqual(linked["instructions"][0]["status"], "linked")  # type: ignore[index]

        missing = run_gitwarp(
            self.repo,
            "start",
            "--cwd",
            str(self.repo),
            "--agent-id",
            "codex-missing",
            "--branch",
            "feature/missing-instruction",
            "--purpose",
            "Should not mutate",
            "--instruction",
            "MISSING.md",
            expect_ok=False,
        )
        self.assertIn("instruction source", str(missing["error"]))
        self.assertEqual(run_git(self.repo, "branch", "--list", "feature/missing-instruction"), "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "feature-missing-instruction").exists())

        escape = run_gitwarp(
            self.repo,
            "dispatch",
            "--cwd",
            str(self.repo),
            "--agent",
            "codex",
            "--branch",
            "feature/escape-instruction",
            "--purpose",
            "Should not mutate",
            "--instruction",
            "../AGENTS.md=AGENTS.md",
            expect_ok=False,
        )
        self.assertIn("relative path", str(escape["error"]))
        self.assertEqual(run_git(self.repo, "branch", "--list", "feature/escape-instruction"), "")
        self.assertFalse((self.repo / ".gitwarp" / "worktrees" / "feature-escape-instruction").exists())

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
