from __future__ import annotations

import shutil

from helpers import *


class PluginStructureTests(unittest.TestCase):
    def assert_script_tree_allowlist(self, root: Path) -> None:
        files = {
            path.relative_to(root)
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual({Path("install_cli.py")}, files)

    def test_pyproject_declares_gitwarp_console_script(self) -> None:
        pyproject_path = REPO_ROOT / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")

        self.assertIn('name = "gitwarp"', content)
        self.assertIn("[project.scripts]", content)
        self.assertIn('gitwarp = "gitwarp.adapters.cli.entrypoint:main"', content)
        self.assertIn('package-dir = {"" = "src"}', content)

    def test_src_package_imports_and_declares_version(self) -> None:
        src_dir = str(REPO_ROOT / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        gitwarp = importlib.import_module("gitwarp")
        cli = importlib.import_module("gitwarp.adapters.cli.entrypoint")

        self.assertEqual(gitwarp.__version__, "0.1.0")
        self.assertTrue(callable(cli.main))

    def test_python_entrypoint_reports_version_from_package(self) -> None:
        result = subprocess.run(
            [*gitwarp_command(), "--version"],
            cwd=str(REPO_ROOT),
            env=gitwarp_env(),
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(result.stdout.strip(), "gitwarp 0.1.0")

    def test_release_metadata_files_exist(self) -> None:
        self.assertIn("MIT License", (REPO_ROOT / "LICENSE").read_text(encoding="utf-8"))
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## 0.1.0", changelog)

    def test_runtime_source_exists_only_in_root_src(self) -> None:
        self.assertTrue((REPO_ROOT / "src" / "gitwarp" / "adapters" / "cli" / "entrypoint.py").is_file())
        plugin_link = REPO_ROOT / "plugins" / "gitwarp"
        self.assertTrue(plugin_link.is_symlink())
        self.assertEqual(plugin_link.resolve(), REPO_ROOT.resolve())

    def test_runtime_package_has_ddd_boundaries(self) -> None:
        expected_modules = {
            "domain/__init__.py",
            "domain/errors.py",
            "domain/model.py",
            "domain/policies.py",
            "application/__init__.py",
            "application/diagnostics.py",
            "application/dto.py",
            "application/health/__init__.py",
            "application/health/checks.py",
            "application/health/doctor.py",
            "application/health/findings.py",
            "application/health/init.py",
            "application/health/process.py",
            "application/reconcile.py",
            "application/views.py",
            "application/use_cases/__init__.py",
            "application/use_cases/cleanup.py",
            "application/use_cases/handoff.py",
            "application/use_cases/init.py",
            "application/use_cases/navigation.py",
            "application/use_cases/metadata.py",
            "application/use_cases/provisioning.py",
            "application/use_cases/repository_browser.py",
            "application/use_cases/web_state.py",
            "adapters/__init__.py",
            "adapters/cli/__init__.py",
            "adapters/cli/entrypoint.py",
            "adapters/cli/parser.py",
            "adapters/cli/read.py",
            "adapters/cli/system.py",
            "adapters/cli/workspaces.py",
            "adapters/presenters.py",
            "infrastructure/__init__.py",
            "infrastructure/agents.py",
            "infrastructure/dossiers.py",
            "infrastructure/git_cli.py",
            "infrastructure/instructions.py",
            "infrastructure/ledger.py",
            "infrastructure/runtime.py",
            "infrastructure/worktrees.py",
            "infrastructure/json_ledger.py",
            "infrastructure/filesystem_dossiers.py",
            "webapp/__init__.py",
            "webapp/contracts.py",
            "webapp/security.py",
            "webapp/resources.py",
            "webapp/controllers.py",
            "webapp/transport.py",
            "webapp/server.py",
        }

        for relative_path in sorted(expected_modules):
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / "src" / "gitwarp" / relative_path).is_file())

    def test_core_layers_do_not_depend_on_adapters(self) -> None:
        layer_roots = [
            REPO_ROOT / "src" / "gitwarp" / "domain",
            REPO_ROOT / "src" / "gitwarp" / "application",
            REPO_ROOT / "src" / "gitwarp" / "infrastructure",
        ]
        forbidden = ("..adapters", "...adapters", "gitwarp.adapters")
        offenders: list[str] = []
        for root in layer_roots:
            for path in root.rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8")
                if any(token in text for token in forbidden):
                    offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual([], offenders)

    def test_cli_adapter_does_not_mutate_ledger_directly(self) -> None:
        cli_root = REPO_ROOT / "src" / "gitwarp" / "adapters" / "cli"
        offenders: list[str] = []
        for path in cli_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "mutate_ledger" in text or "create_worktree(" in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual([], offenders)

    def test_root_package_does_not_keep_compatibility_shims(self) -> None:
        root_modules = {
            path.name
            for path in (REPO_ROOT / "src" / "gitwarp").glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(set(), root_modules)
        self.assertFalse((REPO_ROOT / "src" / "gitwarp" / "application" / "services.py").exists())
        self.assertFalse((REPO_ROOT / "src" / "gitwarp" / "application" / "use_cases" / "workspace_lifecycle.py").exists())

    def test_skill_wrappers_do_not_ship_product_core(self) -> None:
        self.assertFalse((REPO_ROOT / "skills" / "gitwarp" / "scripts" / "gitwarp_core").exists())
        self.assert_script_tree_allowlist(REPO_ROOT / "skills" / "gitwarp" / "scripts")

    def test_web_source_and_packaged_assets_have_clear_boundaries(self) -> None:
        self.assertTrue((REPO_ROOT / "web" / "README.md").exists())
        self.assertTrue((REPO_ROOT / "web" / "console" / "package.json").exists())
        self.assertTrue((REPO_ROOT / "web" / "console" / "src" / "app" / "App.tsx").exists())
        self.assertTrue((REPO_ROOT / "web" / "console" / "dist" / "index.html").exists())
        self.assertTrue((REPO_ROOT / "src" / "gitwarp" / "assets" / "web_console" / "index.html").exists())
        self.assertTrue((REPO_ROOT / "src" / "gitwarp" / "assets" / "web_console" / "app.css").exists())
        self.assertTrue((REPO_ROOT / "src" / "gitwarp" / "assets" / "web_console" / "app.js").exists())
        self.assertTrue((REPO_ROOT / "src" / "gitwarp" / "assets" / ".gitkeep").exists())
        self.assertFalse((REPO_ROOT / "skills" / "gitwarp" / "package.json").exists())
        self.assertFalse((REPO_ROOT / "skills" / "gitwarp" / "web").exists())

    def test_web_runtime_assets_do_not_drift_between_source_and_package(self) -> None:
        package_json = json.loads((REPO_ROOT / "web" / "console" / "package.json").read_text(encoding="utf-8"))
        self.assertIn("check:dist", package_json["scripts"])
        self.assertEqual(package_json["scripts"]["check:dist"], "node scripts/check-runtime.mjs")
        check_script = (REPO_ROOT / "web" / "console" / "scripts" / "check-runtime.mjs").read_text(encoding="utf-8")
        self.assertIn("mkdtemp", check_script)
        self.assertIn("write-runtime.mjs", check_script)

        expected = {"index.html", "app.css", "app.js"}
        self.assertEqual(expected, {path.name for path in (REPO_ROOT / "web" / "console" / "dist").iterdir() if path.is_file()})
        self.assertEqual(expected, {path.name for path in (REPO_ROOT / "src" / "gitwarp" / "assets" / "web_console").iterdir() if path.is_file()})

        for filename in ("index.html", "app.css", "app.js"):
            with self.subTest(filename=filename):
                web_asset = REPO_ROOT / "web" / "console" / "dist" / filename
                package_asset = REPO_ROOT / "src" / "gitwarp" / "assets" / "web_console" / filename
                self.assertEqual(web_asset.read_bytes(), package_asset.read_bytes())

    def test_root_plugin_copy_installs_launcher_from_adjacent_src(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_copy = Path(tempdir) / "gitwarp"
            launcher = Path(tempdir) / "bin" / "gitwarp"
            shutil.copytree(
                REPO_ROOT,
                plugin_copy,
                symlinks=True,
                ignore=shutil.ignore_patterns(".git", ".gitwarp", "tmp", "__pycache__", "node_modules", ".playwright-cli", ".vite"),
            )

            install = subprocess.run(
                ["python3", str(plugin_copy / "skills" / "gitwarp" / "scripts" / "install_cli.py"), "--dest", str(launcher)],
                cwd=str(plugin_copy),
                capture_output=True,
                text=True,
                check=True,
            )
            result = subprocess.run(
                [str(launcher), "--version"],
                cwd=str(plugin_copy),
                capture_output=True,
                text=True,
                check=True,
            )

            install_payload = json.loads(install.stdout.strip())
            self.assertEqual(install_payload["package_root"], str((plugin_copy / "src").resolve()))
            launcher_text = launcher.read_text(encoding="utf-8")
            self.assertIn("PYTHONPATH", launcher_text)
            self.assertIn("gitwarp.adapters.cli.entrypoint", launcher_text)
            self.assertEqual(result.stdout.strip(), "gitwarp 0.1.0")

    def test_codex_plugin_points_at_canonical_skill_and_hooks(self) -> None:
        plugin = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "api_marketplace.json").read_text(encoding="utf-8"))
        root_marketplace = json.loads((REPO_ROOT / "marketplace.json").read_text(encoding="utf-8"))
        claude_marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        default_hooks = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        hooks = json.loads((REPO_ROOT / "hooks" / "hooks-codex.json").read_text(encoding="utf-8"))
        default_session_hook = (REPO_ROOT / "hooks" / "session-start").read_text(encoding="utf-8")
        session_hook = (REPO_ROOT / "hooks" / "session-start-codex").read_text(encoding="utf-8")
        codex_skill_link = REPO_ROOT / ".agents" / "skills" / "gitwarp"
        claude_skill_link = REPO_ROOT / ".claude" / "skills" / "gitwarp"
        default_command = default_hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        codex_command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]

        self.assertEqual(plugin["name"], "gitwarp")
        self.assertEqual(plugin["skills"], "./skills/")
        self.assertNotIn("hooks", plugin)
        self.assertEqual(marketplace["name"], "gitwarp-dev")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/gitwarp")
        self.assertFalse((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").exists())
        self.assertEqual(root_marketplace["plugins"][0]["source"]["path"], "./plugins/gitwarp")
        self.assertEqual(claude_marketplace["plugins"][0]["source"], "./")
        self.assertIn("CODEX", marketplace["plugins"][0]["policy"]["products"])
        self.assertEqual(root_marketplace["plugins"][0]["policy"], marketplace["plugins"][0]["policy"])
        self.assertIn("SessionStart", default_hooks["hooks"])
        self.assertIn("SessionStart", hooks["hooks"])
        self.assertIn("session-start-codex", default_command)
        self.assertIn("session-start-codex", codex_command)
        self.assertIn("PLUGIN_ROOT", default_command)
        self.assertIn("CLAUDE_PLUGIN_ROOT", default_command)
        self.assertIn("exit 0", default_command)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}/hooks", default_command)
        self.assertEqual(default_session_hook, session_hook)
        self.assertIn("GitWarp:", session_hook)
        self.assertIn("Diagnostics:", session_hook)
        self.assertIn("gitwarp statusline --cwd", session_hook)
        self.assertIn("gitwarp enter", session_hook)
        self.assertIn("if ! command -v gitwarp", session_hook)
        self.assertIn("leave it intact after verification", session_hook)
        self.assertIn("push, merge, remove, or collapse", session_hook)
        self.assertNotIn("Agent protocol:", session_hook)
        self.assertNotIn("Current GitWarp Context:", session_hook)
        self.assertIn("gitwarp create", session_hook)
        self.assertIn("gitwarp switch", session_hook)
        self.assertTrue(codex_skill_link.is_symlink())
        self.assertTrue(claude_skill_link.is_symlink())
        self.assertEqual(codex_skill_link.resolve(), (REPO_ROOT / "skills" / "gitwarp").resolve())
        self.assertEqual(claude_skill_link.resolve(), (REPO_ROOT / "skills" / "gitwarp").resolve())

    def test_marketplace_uses_root_package_sources(self) -> None:
        relative_paths = [
            ".github/workflows/check.yml",
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
            ".agents/plugins/api_marketplace.json",
            "marketplace.json",
            ".claude-plugin/marketplace.json",
            "hooks/hooks.json",
            "hooks/hooks-codex.json",
            "hooks/run-hook.cmd",
            "hooks/session-start",
            "hooks/session-start-codex",
            "skills/gitwarp/SKILL.md",
            "skills/gitwarp/agents/openai.yaml",
            "skills/gitwarp/references/install.md",
            "skills/gitwarp/scripts/install_cli.py",
            "scripts/check-release.sh",
            "src/gitwarp/assets/web_console/index.html",
            "src/gitwarp/assets/web_console/app.css",
            "src/gitwarp/assets/web_console/app.js",
            "web/console/index.html",
            "web/console/package.json",
            "web/console/package-lock.json",
            "web/console/scripts/check-runtime.mjs",
            "web/console/scripts/write-runtime.mjs",
            "web/console/vite.config.ts",
            "web/console/src/main.tsx",
            "web/console/src/styles.css",
            "web/console/src/app/App.tsx",
            "web/console/src/app/gitwarp-api.ts",
            "web/console/src/app/types.ts",
            "web/console/src/app/components/ActionPanel.tsx",
            "web/console/src/app/components/CodePanel.tsx",
            "web/console/src/app/components/DossierPanel.tsx",
            "web/console/src/app/components/HealthPanel.tsx",
            "web/console/src/app/components/Header.tsx",
            "web/console/src/app/components/MetadataPanel.tsx",
            "web/console/src/app/components/OutputPanel.tsx",
            "web/console/src/app/components/ProjectDirectory.tsx",
            "web/console/src/app/components/RepositoryHeader.tsx",
            "web/console/src/app/components/RepositoryTabs.tsx",
            "web/console/src/app/components/WorktreePicker.tsx",
            "web/console/dist/index.html",
            "web/console/dist/app.css",
            "web/console/dist/app.js",
            "LICENSE",
            "CHANGELOG.md",
        ]

        for relative_path in relative_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file())
        self.assertTrue((REPO_ROOT / "plugins" / "gitwarp").is_symlink())

    def test_web_source_encodes_github_like_worktree_experience(self) -> None:
        app = (REPO_ROOT / "web" / "console" / "src" / "app" / "App.tsx").read_text(encoding="utf-8")
        code_panel = (REPO_ROOT / "web" / "console" / "src" / "app" / "components" / "CodePanel.tsx").read_text(encoding="utf-8")
        dossier_panel = (REPO_ROOT / "web" / "console" / "src" / "app" / "components" / "DossierPanel.tsx").read_text(encoding="utf-8")
        action_panel = (REPO_ROOT / "web" / "console" / "src" / "app" / "components" / "ActionPanel.tsx").read_text(encoding="utf-8")
        tabs = (REPO_ROOT / "web" / "console" / "src" / "app" / "components" / "RepositoryTabs.tsx").read_text(encoding="utf-8")
        picker = (REPO_ROOT / "web" / "console" / "src" / "app" / "components" / "WorktreePicker.tsx").read_text(encoding="utf-8")

        self.assertIn('setActiveTab("metadata")', app)
        self.assertIn("setSelectedWorktreePath(String(result.path))", app)
        self.assertIn("repository-content-grid", code_panel)
        self.assertIn("repo-about", code_panel)
        self.assertIn("View metadata", code_panel)
        self.assertIn("FileViewer", code_panel)
        self.assertIn("Repository file viewer", code_panel)
        self.assertIn("Back to directory", code_panel)
        self.assertIn("repository-tab-stack", app)
        self.assertIn("finishAndCollapse(worktree.path, status, progress)", app)
        self.assertIn('hidden={activeTab !== "code"}', app)
        self.assertIn('hidden={activeTab !== "metadata"}', app)
        self.assertIn('hidden={activeTab !== "health"}', app)
        self.assertIn("delete the matching dossier directory", dossier_panel)
        self.assertIn("It will not push, merge, or delete the branch.", dossier_panel)
        self.assertIn("Final status", dossier_panel)
        self.assertIn("async (event", action_panel)
        self.assertIn("await onStart", action_panel)
        self.assertIn("await onDispatch", action_panel)
        self.assertIn('aria-current={tab.id === activeTab ? "page" : undefined}', tabs)
        self.assertLess(
            picker.index("worktrees.find((worktree) => worktree.is_main)"),
            picker.index("worktrees.find((worktree) => !worktree.is_main)"),
        )

    def test_release_gate_runs_required_checks(self) -> None:
        gate = (REPO_ROOT / "scripts" / "check-release.sh").read_text(encoding="utf-8")
        workflow = (REPO_ROOT / ".github" / "workflows" / "check.yml").read_text(encoding="utf-8")

        for command in (
            "git diff --check",
            "python3 -m compileall",
            "npm run check:dist",
            "python3 -m unittest discover",
        ):
            with self.subTest(command=command):
                self.assertIn(command, gate)
        self.assertIn("scripts/check-release.sh", workflow)

    def test_install_scripts_have_version_and_path_guards(self) -> None:
        installer = (REPO_ROOT / "skills" / "gitwarp" / "scripts" / "install_cli.py").read_text(encoding="utf-8")
        install_script = (REPO_ROOT / "scripts" / "install-codex-plugin.sh").read_text(encoding="utf-8")
        verify_script = (REPO_ROOT / "scripts" / "verify-install.sh").read_text(encoding="utf-8")

        self.assertIn("MIN_PYTHON = (3, 10)", installer)
        self.assertIn('ENTRYPOINT_MODULE = "gitwarp.adapters.cli.entrypoint"', installer)
        self.assertIn("PYTHONPATH", installer)
        self.assertIn("package_root", installer)
        self.assertNotIn("script_path", installer)
        self.assertIn("sys.executable", installer)
        self.assertIn("except OSError", installer)
        self.assertIn("recommended_next", installer)
        self.assertIn("sys.version_info >= (3, 10)", install_script)
        self.assertIn("marketplace_rebound", install_script)
        self.assertIn("codex plugin marketplace remove", install_script)
        self.assertIn("recommended_next", install_script)
        self.assertIn("GITWARP_BIN", verify_script)
        self.assertIn("~/.local/bin", verify_script)
