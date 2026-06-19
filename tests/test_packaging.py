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
        self.assertEqual({Path("gitwarp.py"), Path("install_cli.py")}, files)

    def test_pyproject_declares_gitwarp_console_script(self) -> None:
        pyproject_path = REPO_ROOT / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")

        self.assertIn('name = "gitwarp"', content)
        self.assertIn("[project.scripts]", content)
        self.assertIn('gitwarp = "gitwarp.cli:main"', content)
        self.assertIn('package-dir = {"" = "src"}', content)

    def test_src_package_imports_and_declares_version(self) -> None:
        src_dir = str(REPO_ROOT / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        gitwarp = importlib.import_module("gitwarp")
        cli = importlib.import_module("gitwarp.cli")

        self.assertEqual(gitwarp.__version__, "0.1.0")
        self.assertTrue(callable(cli.main))

    def test_skill_wrapper_reports_version_from_package(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT), "--version"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(result.stdout.strip(), "gitwarp 0.1.0")

    def test_runtime_source_exists_only_in_root_src(self) -> None:
        self.assertTrue((REPO_ROOT / "src" / "gitwarp" / "cli.py").is_file())
        self.assertFalse((REPO_ROOT / "plugins" / "gitwarp" / "src").exists())

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
            "application/services.py",
            "application/views.py",
            "application/use_cases/__init__.py",
            "application/use_cases/cleanup.py",
            "application/use_cases/handoff.py",
            "application/use_cases/init.py",
            "application/use_cases/metadata.py",
            "application/use_cases/provisioning.py",
            "application/use_cases/web_state.py",
            "application/use_cases/workspace_lifecycle.py",
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

    def test_root_runtime_modules_are_compatibility_shims(self) -> None:
        shim_modules = {
            "agents.py",
            "cli.py",
            "diagnostics.py",
            "dossiers.py",
            "foundation.py",
            "ledger.py",
            "reconcile.py",
            "reporting.py",
            "services.py",
            "web.py",
            "worktrees.py",
        }
        for relative_path in sorted(shim_modules):
            with self.subTest(path=relative_path):
                line_count = len((REPO_ROOT / "src" / "gitwarp" / relative_path).read_text(encoding="utf-8").splitlines())
                self.assertLessEqual(line_count, 80)

    def test_skill_wrappers_do_not_ship_product_core(self) -> None:
        self.assertFalse((REPO_ROOT / "skills" / "gitwarp" / "scripts" / "gitwarp_core").exists())
        self.assert_script_tree_allowlist(REPO_ROOT / "skills" / "gitwarp" / "scripts")

    def test_web_source_and_packaged_assets_have_clear_boundaries(self) -> None:
        self.assertTrue((REPO_ROOT / "web" / "README.md").exists())
        self.assertTrue((REPO_ROOT / "src" / "gitwarp" / "assets" / ".gitkeep").exists())
        self.assertFalse((REPO_ROOT / "skills" / "gitwarp" / "package.json").exists())
        self.assertFalse((REPO_ROOT / "skills" / "gitwarp" / "web").exists())

    def test_root_plugin_copy_runs_skill_wrapper_from_adjacent_src(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_copy = Path(tempdir) / "gitwarp"
            shutil.copytree(
                REPO_ROOT,
                plugin_copy,
                ignore=shutil.ignore_patterns(".git", ".gitwarp", "tmp", "__pycache__"),
            )

            result = subprocess.run(
                ["python3", str(plugin_copy / "skills" / "gitwarp" / "scripts" / "gitwarp.py"), "--version"],
                cwd=str(plugin_copy),
                capture_output=True,
                text=True,
                check=True,
            )

        self.assertEqual(result.stdout.strip(), "gitwarp 0.1.0")

    def test_codex_plugin_points_at_canonical_skill_and_hooks(self) -> None:
        plugin = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "api_marketplace.json").read_text(encoding="utf-8"))
        legacy_marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        root_marketplace = json.loads((REPO_ROOT / "marketplace.json").read_text(encoding="utf-8"))
        claude_marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        hooks = json.loads((REPO_ROOT / "hooks" / "hooks-codex.json").read_text(encoding="utf-8"))
        session_hook = (REPO_ROOT / "hooks" / "session-start-codex").read_text(encoding="utf-8")
        codex_skill_link = REPO_ROOT / ".agents" / "skills" / "gitwarp"
        claude_skill_link = REPO_ROOT / ".claude" / "skills" / "gitwarp"

        self.assertEqual(plugin["name"], "gitwarp")
        self.assertEqual(plugin["skills"], "./skills/")
        self.assertNotIn("hooks", plugin)
        self.assertEqual(marketplace["name"], "gitwarp-dev")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], ".")
        self.assertEqual(legacy_marketplace["plugins"][0]["source"]["path"], ".")
        self.assertEqual(root_marketplace["plugins"][0]["source"]["path"], ".")
        self.assertEqual(claude_marketplace["plugins"][0]["source"], "./")
        self.assertIn("CODEX", marketplace["plugins"][0]["policy"]["products"])
        self.assertIn("SessionStart", hooks["hooks"])
        self.assertIn("gitwarp enter --cwd", session_hook)
        self.assertIn("gitwarp start", session_hook)
        self.assertIn("gitwarp handoff", session_hook)
        self.assertTrue(codex_skill_link.is_symlink())
        self.assertTrue(claude_skill_link.is_symlink())
        self.assertEqual(codex_skill_link.resolve(), (REPO_ROOT / "skills" / "gitwarp").resolve())
        self.assertEqual(claude_skill_link.resolve(), (REPO_ROOT / "skills" / "gitwarp").resolve())

    def test_marketplace_uses_root_package_sources(self) -> None:
        relative_paths = [
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
            ".agents/plugins/marketplace.json",
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
            "skills/gitwarp/scripts/gitwarp.py",
            "skills/gitwarp/scripts/install_cli.py",
        ]

        for relative_path in relative_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file())
        self.assertFalse((REPO_ROOT / "plugins" / "gitwarp").exists())
