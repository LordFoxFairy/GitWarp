from __future__ import annotations

from helpers import *


class DoctorTests(GitWarpTestCase):
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
        self.assertIn("gitwarp_initialized", codes)
        self.assertIn("ledger_schema", codes)
        self.assertIn("gitwarp_ignored", codes)
        self.assertIn("agent_config", codes)
        self.assertIn("codex_plugin_metadata", codes)
        self.assertNotIn("session_hook_context", codes)
        self.assertLessEqual(severities, {"ok", "warning", "error"})
        self.assertEqual(doctor["summary"]["total"], len(findings))  # type: ignore[index]

    def test_init_bootstraps_runtime_state_and_is_idempotent(self) -> None:
        init = run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        worktree_root = self.repo / ".gitwarp" / "worktrees"
        dossier_root = self.repo / ".gitwarp" / "dossiers"
        exclude_path = self.repo / ".git" / "info" / "exclude"

        self.assertTrue(ledger_path.exists())
        self.assertTrue(worktree_root.is_dir())
        self.assertTrue(dossier_root.is_dir())
        self.assertEqual(init["ledger_path"], str(ledger_path.resolve()))
        self.assertEqual(init["worktree_root"], str(worktree_root.resolve()))
        self.assertEqual(init["dossier_root"], str(dossier_root.resolve()))
        self.assertEqual(init["ignore_target"], str(exclude_path.resolve()))
        self.assertTrue(init["created"]["ledger_dir"])  # type: ignore[index]
        self.assertTrue(init["created"]["ledger"])  # type: ignore[index]
        self.assertTrue(init["created"]["worktree_root"])  # type: ignore[index]
        self.assertTrue(init["created"]["dossier_root"])  # type: ignore[index]
        self.assertFalse(init["updated"]["ledger"])  # type: ignore[index]
        self.assertTrue(init["updated"]["ignore_rule"])  # type: ignore[index]
        self.assertIn("/.gitwarp/", exclude_path.read_text(encoding="utf-8"))
        self.assertIn("gitwarp doctor", " ".join(init["recommended_next"]))  # type: ignore[arg-type]

        first_ledger = ledger_path.read_bytes()
        second = run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        second_ledger = ledger_path.read_bytes()
        self.assertEqual(first_ledger, second_ledger)
        self.assertFalse(second["created"]["ledger_dir"])  # type: ignore[index]
        self.assertFalse(second["created"]["ledger"])  # type: ignore[index]
        self.assertFalse(second["created"]["worktree_root"])  # type: ignore[index]
        self.assertFalse(second["created"]["dossier_root"])  # type: ignore[index]
        self.assertFalse(second["updated"]["ledger"])  # type: ignore[index]
        self.assertFalse(second["updated"]["ignore_rule"])  # type: ignore[index]

    def test_init_preserves_existing_ledger_entries(self) -> None:
        ledger_dir = self.repo / ".gitwarp"
        ledger_dir.mkdir()
        ledger_path = ledger_dir / "ledger.json"
        entry = {
            "path": str(self.repo / "missing-worktree"),
            "branch": "feature/preserve",
            "agent_id": "codex-preserve",
            "purpose": "Preserve ledger",
            "status": "active",
            "notes": [{"note": "keep me", "created_at": "2000-01-01T00:00:00+00:00"}],
            "created_at": "2000-01-01T00:00:00+00:00",
        }
        ledger_path.write_text(
            json.dumps({"entries": [entry], "custom": {"keep": True}}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        init = run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["version"], 1)
        self.assertEqual(ledger["repo_root"], str(self.repo.resolve()))
        self.assertEqual(ledger["entries"], [entry])
        self.assertEqual(ledger["custom"], {"keep": True})
        self.assertTrue(init["updated"]["ledger"])  # type: ignore[index]

    def test_init_refuses_invalid_existing_state(self) -> None:
        cases = [".gitwarp", ".gitwarp/worktrees", ".gitwarp/dossiers"]
        for relative_path in cases:
            with self.subTest(path=relative_path):
                repo = self.make_repo()
                target = repo / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("not a directory\n", encoding="utf-8")

                result = run_gitwarp(repo, "init", "--cwd", str(repo), expect_ok=False)

                self.assertIn(str(target.resolve()), str(result["error"]))
                self.assertFalse((repo / ".gitwarp" / "ledger.json").exists())

    def test_init_refuses_invalid_ledger_variants_without_overwrite(self) -> None:
        cases: list[object] = [
            "[]",
            "{not-json",
            {"version": 1},
            {"version": 1, "entries": {}},
            {"version": "1", "entries": []},
            {"version": 2, "entries": []},
            {"version": None, "entries": []},
            {"version": True, "entries": []},
            {"version": 1, "repo_root": [], "entries": []},
        ]
        for value in cases:
            with self.subTest(value=value):
                repo = self.make_repo()
                ledger_path = repo / ".gitwarp" / "ledger.json"
                ledger_path.parent.mkdir()
                if isinstance(value, str):
                    ledger_path.write_text(value, encoding="utf-8")
                else:
                    ledger_path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
                before = ledger_path.read_bytes()

                result = run_gitwarp(repo, "init", "--cwd", str(repo), expect_ok=False)

                self.assertIn("ledger", str(result["error"]))
                self.assertEqual(ledger_path.read_bytes(), before)

    def test_init_write_gitignore_and_deduplicates_ignore_rules(self) -> None:
        run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        exclude_path = self.repo / ".git" / "info" / "exclude"
        self.assertEqual(exclude_path.read_text(encoding="utf-8").count("/.gitwarp/"), 1)

        run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        self.assertEqual(exclude_path.read_text(encoding="utf-8").count("/.gitwarp/"), 1)

        repo_with_gitignore = self.make_repo()
        gitignore_path = repo_with_gitignore / ".gitignore"
        gitignore_path.write_text("/.gitwarp/\n", encoding="utf-8")
        exclude_before = (repo_with_gitignore / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        default_init = run_gitwarp(repo_with_gitignore, "init", "--cwd", str(repo_with_gitignore))
        exclude_after = (repo_with_gitignore / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertFalse(default_init["updated"]["ignore_rule"])  # type: ignore[index]
        self.assertEqual(exclude_after, exclude_before)

        team_repo = self.make_repo()
        team_exclude = team_repo / ".git" / "info" / "exclude"
        team_exclude.write_text(team_exclude.read_text(encoding="utf-8") + "\n/.gitwarp/\n", encoding="utf-8")
        team_init = run_gitwarp(team_repo, "init", "--cwd", str(team_repo), "--write-gitignore")
        self.assertTrue(team_init["updated"]["ignore_rule"])  # type: ignore[index]
        self.assertEqual((team_repo / ".gitignore").read_text(encoding="utf-8").count("/.gitwarp/"), 1)

        second_team_init = run_gitwarp(team_repo, "init", "--cwd", str(team_repo), "--write-gitignore")
        self.assertFalse(second_team_init["updated"]["ignore_rule"])  # type: ignore[index]
        self.assertEqual((team_repo / ".gitignore").read_text(encoding="utf-8").count("/.gitwarp/"), 1)

    def test_init_reports_ignore_target_write_failure_before_mutation(self) -> None:
        gitignore_path = self.repo / ".gitignore"
        gitignore_path.mkdir()

        result = run_gitwarp(self.repo, "init", "--cwd", str(self.repo), "--write-gitignore", expect_ok=False)

        self.assertIn(str(gitignore_path.resolve()), str(result["error"]))
        self.assertFalse((self.repo / ".gitwarp" / "ledger.json").exists())

    def test_doctor_reports_setup_guidance_without_mutation(self) -> None:
        doctor = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))
        codes = {finding["code"] for finding in doctor["findings"]}  # type: ignore[index]
        recommended = " ".join(doctor["recommended_next"])  # type: ignore[arg-type]

        self.assertIn("gitwarp_initialized", codes)
        self.assertIn("ledger_schema", codes)
        self.assertIn("gitwarp_ignored", codes)
        self.assertIn("agent_config", codes)
        self.assertIn(f"gitwarp init --cwd \"{self.repo.resolve()}\"", recommended)
        self.assertFalse((self.repo / ".gitwarp" / "ledger.json").exists())

        run_gitwarp(self.repo, "init", "--cwd", str(self.repo))
        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        before = ledger_path.read_bytes()
        after_init_doctor = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))
        after = ledger_path.read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(findings_with_code(after_init_doctor, "gitwarp_initialized")[0]["severity"], "ok")
        self.assertEqual(findings_with_code(after_init_doctor, "ledger_schema")[0]["severity"], "ok")

    def test_doctor_reports_invalid_ledger_error_without_mutation(self) -> None:
        ledger_path = self.repo / ".gitwarp" / "ledger.json"
        ledger_path.parent.mkdir()
        ledger_path.write_text("{not-json", encoding="utf-8")
        before = ledger_path.read_bytes()

        doctor = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))

        ledger_findings = findings_with_code(doctor, "ledger_schema")
        self.assertEqual(ledger_findings[0]["severity"], "error")
        self.assertEqual(ledger_path.read_bytes(), before)

    def test_doctor_does_not_execute_repo_hook(self) -> None:
        repo = self.make_repo()
        (repo / "skills" / "gitwarp" / "scripts").mkdir(parents=True)
        (repo / "skills" / "gitwarp" / "SKILL.md").write_text("---\nname: gitwarp\n---\n", encoding="utf-8")
        (repo / "skills" / "gitwarp" / "scripts" / "install_cli.py").write_text("# placeholder\n", encoding="utf-8")
        (repo / "src" / "gitwarp" / "adapters" / "cli").mkdir(parents=True)
        (repo / "src" / "gitwarp" / "adapters" / "cli" / "entrypoint.py").write_text("# placeholder\n", encoding="utf-8")
        (repo / ".codex-plugin").mkdir()
        (repo / ".codex-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
        (repo / ".agents" / "plugins").mkdir(parents=True)
        (repo / ".agents" / "plugins" / "api_marketplace.json").write_text("{}\n", encoding="utf-8")
        hook_path = repo / "hooks" / "session-start-codex"
        marker_path = repo / "hook-ran"
        hook_path.parent.mkdir()
        hook_path.write_text(f"#!/usr/bin/env sh\ntouch {marker_path}\necho bad\n", encoding="utf-8")
        hook_path.chmod(0o755)

        doctor = run_gitwarp(repo, "doctor", "--cwd", str(repo))

        self.assertFalse(marker_path.exists())
        hook_finding = findings_with_code(doctor, "session_hook_context")[0]
        self.assertEqual(hook_finding["severity"], "warning")

    def test_doctor_reports_agent_config_for_absent_valid_and_invalid_config(self) -> None:
        absent = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))
        absent_config = findings_with_code(absent, "agent_config")
        self.assertEqual(len(absent_config), 1)
        self.assertEqual(absent_config[0]["severity"], "ok")
        self.assertFalse(absent_config[0]["details"]["configured"])  # type: ignore[index]

        config_path = self.repo / ".gitwarp" / "agents.json"
        config_path.parent.mkdir(exist_ok=True)
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
        valid = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))
        valid_config = findings_with_code(valid, "agent_config")
        self.assertEqual(len(valid_config), 1)
        self.assertEqual(valid_config[0]["severity"], "ok")
        self.assertTrue(valid_config[0]["details"]["configured"])  # type: ignore[index]
        self.assertTrue(findings_with_code(valid, "agent_binary"))

        config_path.write_text("{not-json", encoding="utf-8")
        invalid = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))
        invalid_config = findings_with_code(invalid, "agent_config")
        self.assertEqual(len(invalid_config), 1)
        self.assertEqual(invalid_config[0]["severity"], "error")
        self.assertFalse(findings_with_code(invalid, "agent_binary"))
        self.assertIn(str(config_path.resolve()), " ".join(invalid["recommended_next"]))  # type: ignore[arg-type]

    def test_doctor_source_checkout_checks_are_scoped(self) -> None:
        ordinary = self.make_repo()
        ordinary_doctor = run_gitwarp(ordinary, "doctor", "--cwd", str(ordinary))
        ordinary_codes = {finding["code"] for finding in ordinary_doctor["findings"]}  # type: ignore[index]
        self.assertNotIn("standard_skill_links", ordinary_codes)
        self.assertNotIn("session_hook_context", ordinary_codes)

        source_doctor = run_gitwarp(REPO_ROOT, "doctor", "--cwd", str(REPO_ROOT))
        source_codes = {finding["code"] for finding in source_doctor["findings"]}  # type: ignore[index]
        self.assertIn("standard_skill_links", source_codes)
        self.assertIn("session_hook_context", source_codes)
        hook_findings = findings_with_code(source_doctor, "session_hook_context")
        self.assertEqual(hook_findings[0]["severity"], "ok")
        configs = hook_findings[0]["details"]["configs"]  # type: ignore[index]
        self.assertTrue(configs["default"]["ok"])  # type: ignore[index]
        self.assertTrue(configs["codex"]["ok"])  # type: ignore[index]

    def test_doctor_source_checkout_uses_worktree_hook_files(self) -> None:
        source_repo = self.make_repo()
        (source_repo / "skills" / "gitwarp" / "scripts").mkdir(parents=True)
        (source_repo / "skills" / "gitwarp" / "SKILL.md").write_text("---\nname: gitwarp\n---\n", encoding="utf-8")
        (source_repo / "skills" / "gitwarp" / "scripts" / "install_cli.py").write_text("# installer\n", encoding="utf-8")
        (source_repo / "src" / "gitwarp" / "adapters" / "cli").mkdir(parents=True)
        (source_repo / "src" / "gitwarp" / "adapters" / "cli" / "entrypoint.py").write_text("# entrypoint\n", encoding="utf-8")
        (source_repo / ".codex-plugin").mkdir()
        (source_repo / ".codex-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
        (source_repo / ".agents" / "plugins").mkdir(parents=True)
        (source_repo / ".agents" / "plugins" / "api_marketplace.json").write_text("{}\n", encoding="utf-8")
        (source_repo / "hooks").mkdir()
        (source_repo / "hooks" / "session-start-codex").write_text(
            'gitwarp enter --cwd "$PWD"\nGitWarp Context:\nDiagnostics:\n',
            encoding="utf-8",
        )
        (source_repo / "hooks" / "session-start-codex").chmod(0o755)
        hook_command = (
            "bash -lc 'root=\"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}\"; "
            "[ -n \"$root\" ] || exit 0; "
            "exec \"$root/hooks/run-hook.cmd\" session-start-codex'"
        )
        hook_config = {
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": "startup|resume|clear",
                        "hooks": [
                            {
                                "type": "command",
                                "command": hook_command,
                                "async": False,
                            }
                        ],
                    }
                ]
            }
        }
        (source_repo / "hooks" / "hooks.json").write_text(json.dumps(hook_config), encoding="utf-8")
        (source_repo / "hooks" / "hooks-codex.json").write_text(json.dumps(hook_config), encoding="utf-8")
        run_git(source_repo, "add", ".")
        run_git(source_repo, "commit", "-m", "source checkout shape")

        worktree_path = source_repo.parent / "source-worktree"
        run_git(source_repo, "worktree", "add", "-b", "feature/source-worktree-doctor", str(worktree_path), "HEAD")
        self.addCleanup(
            subprocess.run,
            ["git", "-C", str(source_repo), "branch", "-D", "feature/source-worktree-doctor"],
            capture_output=True,
            text=True,
        )
        self.addCleanup(
            subprocess.run,
            ["git", "-C", str(source_repo), "worktree", "remove", "--force", str(worktree_path)],
            capture_output=True,
            text=True,
        )
        (source_repo / "hooks" / "session-start-codex").write_text("gitwarp enter --cwd \"$PWD\"\n", encoding="utf-8")

        doctor = run_gitwarp(worktree_path, "doctor", "--cwd", str(worktree_path))
        hook_finding = findings_with_code(doctor, "session_hook_context")[0]

        self.assertEqual(hook_finding["severity"], "ok")
        self.assertEqual(
            hook_finding["details"]["path"],  # type: ignore[index]
            str((worktree_path / "hooks" / "session-start-codex").resolve()),
        )
