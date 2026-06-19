from __future__ import annotations

from pathlib import Path

from .runtime import run_git


class GitCli:
    def run(self, cwd: Path, *args: str, check: bool = True) -> str:
        return run_git(cwd, *args, check=check)
