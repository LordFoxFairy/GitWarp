from __future__ import annotations

from helpers import *


class DossierTests(GitWarpTestCase):
    def test_dossier_repair_preserves_mounted_instruction_metadata(self) -> None:
        (self.repo / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md")
        run_git(self.repo, "commit", "-m", "add rules")
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-dossier-repair",
            "--branch",
            "feature/dossier-repair",
            "--purpose",
            "Repair dossier with instruction metadata",
            "--instruction",
            "AGENTS.md",
        )
        worktree_path = Path(str(start["path"]))
        task_md = Path(str(start["task_md"]))
        progress_md = Path(str(start["progress_md"]))
        lessons_md = Path(str(start["lessons_md"]))
        task_md.unlink()
        progress_md.unlink()
        lessons_md.unlink()

        run_gitwarp(
            self.repo,
            "handoff",
            "--cwd",
            str(worktree_path),
            "--status",
            "testing",
            "--progress",
            "Repaired dossier after missing files",
        )

        task_text = task_md.read_text(encoding="utf-8")
        self.assertIn("Mounted Instructions", task_text)
        self.assertIn("`AGENTS.md`", task_text)
        self.assertIn("Repaired dossier after missing files", progress_md.read_text(encoding="utf-8"))

    def test_pause_and_resume_record_blocked_and_active_handoffs(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-pause",
            "--branch",
            "feature/pause-resume",
            "--purpose",
            "Handle blocked work",
        )
        worktree_path = Path(str(start["path"]))
        progress_md = Path(str(start["progress_md"]))
        lessons_md = Path(str(start["lessons_md"]))

        pause = run_gitwarp(
            self.repo,
            "pause",
            "--cwd",
            str(worktree_path),
            "--reason",
            "Waiting for human credentials",
            "--lesson",
            "Do not retry deployment without credentials",
        )
        self.assertEqual(pause["status"], "blocked")
        self.assertEqual(pause["latest_progress"], "Waiting for human credentials")
        self.assertEqual(pause["latest_lesson"], "Do not retry deployment without credentials")

        resume = run_gitwarp(
            self.repo,
            "resume",
            "--cwd",
            str(worktree_path),
            "--progress",
            "Credentials configured; continuing implementation",
        )
        self.assertEqual(resume["status"], "active")
        self.assertEqual(resume["latest_progress"], "Credentials configured; continuing implementation")

        context = run_gitwarp(self.repo, "context", "--cwd", str(worktree_path))
        self.assertEqual(context["worktree"]["status"], "active")  # type: ignore[index]
        self.assertIn("Waiting for human credentials", progress_md.read_text(encoding="utf-8"))
        self.assertIn("Credentials configured", progress_md.read_text(encoding="utf-8"))
        self.assertIn("Do not retry deployment without credentials", lessons_md.read_text(encoding="utf-8"))
