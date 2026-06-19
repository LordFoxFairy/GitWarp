from __future__ import annotations

from helpers import *


class LedgerTests(GitWarpTestCase):
    def test_parallel_handoffs_do_not_lose_ledger_updates(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-parallel",
            "--branch",
            "feature/parallel-handoff",
            "--purpose",
            "Verify concurrent handoff safety",
        )
        worktree_path = Path(str(start["path"]))

        expected_notes: list[str] = []
        for round_index in range(10):
            results: list[subprocess.CompletedProcess[str] | None] = [None] * 8
            threads = []
            for worker_index in range(8):
                progress = f"parallel progress {round_index}-{worker_index}"
                expected_notes.append(progress)

                def run_handoff(index: int = worker_index, note: str = progress) -> None:
                    results[index] = subprocess.run(
                        [
                            *gitwarp_command(),
                            "handoff",
                            "--cwd",
                            str(worktree_path),
                            "--status",
                            "testing",
                            "--progress",
                            note,
                        ],
                        cwd=str(self.repo),
                        env=gitwarp_env(),
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                thread = threading.Thread(target=run_handoff)
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
            for result in results:
                self.assertIsNotNone(result)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)  # type: ignore[union-attr]

        context = run_gitwarp(self.repo, "context", "--cwd", str(worktree_path))
        notes = [item["note"] for item in context["worktree"]["notes"]]  # type: ignore[index]
        for expected in expected_notes:
            self.assertIn(expected, notes)
        self.assertFalse((self.repo / ".gitwarp" / "ledger.lock").exists())

    def test_ledger_lock_hijacks_dead_pid_after_timeout(self) -> None:
        ledger_module = load_gitwarp_ledger()
        ctx = ledger_module.discover_repo(self.repo)
        lock_path = self.repo / ".gitwarp" / "ledger.lock"
        lock_path.parent.mkdir()
        lock_path.write_text(
            json.dumps({"pid": 99999999, "created_at": "2000-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )

        with ledger_module.ledger_write_lock(ctx, timeout=0.05):
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(lock["pid"], os.getpid())

        self.assertFalse(lock_path.exists())

    def test_ledger_lock_keeps_live_pid_lock(self) -> None:
        ledger_module = load_gitwarp_ledger()
        ctx = ledger_module.discover_repo(self.repo)
        lock_path = self.repo / ".gitwarp" / "ledger.lock"
        lock_path.parent.mkdir()
        lock_path.write_text(
            json.dumps({"pid": os.getpid(), "created_at": "2000-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )

        with self.assertRaises(ledger_module.GitWarpError):
            with ledger_module.ledger_write_lock(ctx, timeout=0.05):
                pass

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock["pid"], os.getpid())
