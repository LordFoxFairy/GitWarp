from __future__ import annotations

import json
import subprocess
import tempfile
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


class PluginStructureTests(unittest.TestCase):
    def test_codex_plugin_points_at_canonical_skill_and_hooks(self) -> None:
        plugin = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "api_marketplace.json").read_text(encoding="utf-8"))
        hooks = json.loads((REPO_ROOT / "hooks" / "hooks-codex.json").read_text(encoding="utf-8"))

        self.assertEqual(plugin["name"], "gitwarp")
        self.assertEqual(plugin["skills"], "./skills/")
        self.assertNotIn("hooks", plugin)
        self.assertEqual(marketplace["name"], "gitwarp-dev")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/gitwarp")
        self.assertIn("CODEX", marketplace["plugins"][0]["policy"]["products"])
        self.assertIn("SessionStart", hooks["hooks"])

    def test_marketplace_plugin_package_matches_root_sources(self) -> None:
        relative_paths = [
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "hooks/hooks-codex.json",
            "hooks/run-hook.cmd",
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
