from __future__ import annotations

from helpers import *


class DossierTests(GitWarpTestCase):
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
