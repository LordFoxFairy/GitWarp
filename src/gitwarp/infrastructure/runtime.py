from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..domain.errors import GitWarpError
from ..domain.policies import path_contains


LEDGER_DIRNAME = ".gitwarp"
LEDGER_FILENAME = "ledger.json"
LEDGER_LOCK_FILENAME = "ledger.lock"
LOCK_TIMEOUT_SECONDS = 10.0
AGENTS_FILENAME = "agents.json"
INSTRUCTION_PROFILES_FILENAME = "instruction_profiles.json"
WORKTREE_DIRNAME = "worktrees"
DOSSIER_DIRNAME = "dossiers"
TASK_FILENAME = "task.md"
PROGRESS_FILENAME = "progress.md"
LESSONS_FILENAME = "lessons.md"


@dataclass(frozen=True)
class RepoContext:
    cwd: Path
    repo_root: Path
    checkout_root: Path
    common_dir: Path

    @property
    def ledger_dir(self) -> Path:
        return self.repo_root / LEDGER_DIRNAME

    @property
    def ledger_path(self) -> Path:
        return self.ledger_dir / LEDGER_FILENAME

    @property
    def ledger_lock_path(self) -> Path:
        return self.ledger_dir / LEDGER_LOCK_FILENAME

    @property
    def worktree_root(self) -> Path:
        return self.ledger_dir / WORKTREE_DIRNAME

    @property
    def dossier_root(self) -> Path:
        return self.ledger_dir / DOSSIER_DIRNAME

    @property
    def agents_path(self) -> Path:
        return self.ledger_dir / AGENTS_FILENAME

    @property
    def instruction_profiles_path(self) -> Path:
        return self.ledger_dir / INSTRUCTION_PROFILES_FILENAME

    @property
    def git_info_exclude_path(self) -> Path:
        return self.common_dir / "info" / "exclude"

    @property
    def gitignore_path(self) -> Path:
        return self.repo_root / ".gitignore"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def resolve_path(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def run_git(cwd: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitWarpError(f"failed to execute git: {exc}") from exc

    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise GitWarpError(message)
    return result.stdout.strip()


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "workspace"


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:6]


def gitwarp_home_path() -> Path:
    raw = os.environ.get("GITWARP_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".gitwarp"


def project_registry_path() -> Path:
    return gitwarp_home_path() / "projects.json"


def global_web_state_path() -> Path:
    return gitwarp_home_path() / "web-console-global-state.json"
