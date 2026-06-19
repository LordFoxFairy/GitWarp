from __future__ import annotations

from helpers import *


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
