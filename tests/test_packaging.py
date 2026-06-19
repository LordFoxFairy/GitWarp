from __future__ import annotations

import shutil

from helpers import *


class PluginStructureTests(unittest.TestCase):
    def assert_directory_mirror(self, source: Path, target: Path) -> None:
        source_files = {
            path.relative_to(source)
            for path in source.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        target_files = {
            path.relative_to(target)
            for path in target.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(source_files, target_files)
        for relative_path in sorted(source_files):
            with self.subTest(path=str(relative_path)):
                self.assertEqual(
                    (source / relative_path).read_text(encoding="utf-8"),
                    (target / relative_path).read_text(encoding="utf-8"),
                )

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

    def test_plugin_src_package_matches_root_package(self) -> None:
        self.assert_directory_mirror(REPO_ROOT / "src" / "gitwarp", REPO_ROOT / "plugins" / "gitwarp" / "src" / "gitwarp")

    def test_plugin_wrapper_runs_from_installed_plugin_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_copy = Path(tempdir) / "gitwarp"
            shutil.copytree(REPO_ROOT / "plugins" / "gitwarp", plugin_copy)

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
        relative_paths.extend(
            str(path.relative_to(REPO_ROOT))
            for path in sorted((REPO_ROOT / "skills" / "gitwarp" / "scripts" / "gitwarp_core").glob("*.py"))
        )

        for relative_path in relative_paths:
            with self.subTest(path=relative_path):
                self.assertEqual(
                    (REPO_ROOT / relative_path).read_text(encoding="utf-8"),
                    (REPO_ROOT / "plugins" / "gitwarp" / relative_path).read_text(encoding="utf-8"),
                )
