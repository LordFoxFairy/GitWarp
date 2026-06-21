from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ...infrastructure.ledger import normalize_ledger_schema
from ...infrastructure.runtime import GitWarpError, RepoContext


def git_ignores_gitwarp(ctx: RepoContext) -> bool:
    for candidate in (".gitwarp/", ".gitwarp"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", candidate],
            cwd=str(ctx.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True
    return False


def target_contains_gitwarp_rule(path: Path) -> bool:
    if not path.exists():
        return False
    if not path.is_file():
        raise GitWarpError(f"ignore target is not a file: {path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    normalized = {line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")}
    return "/.gitwarp/" in normalized or ".gitwarp/" in normalized or ".gitwarp" in normalized or "/.gitwarp" in normalized


def append_gitwarp_ignore_rule(path: Path) -> None:
    if path.exists() and not path.is_file():
        raise GitWarpError(f"ignore target is not a file: {path}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        prefix = "" if not current or current.endswith("\n") else "\n"
        path.write_text(current + prefix + "/.gitwarp/\n", encoding="utf-8")
    except OSError as exc:
        raise GitWarpError(f"failed to write ignore target {path}: {exc}") from exc


def ensure_ignore_target_writable(path: Path) -> None:
    if path.exists() and not path.is_file():
        raise GitWarpError(f"ignore target is not a file: {path}")
    parent = path.parent
    if parent.exists() and not parent.is_dir():
        raise GitWarpError(f"ignore target parent is not a directory: {parent}")


def preflight_init(ctx: RepoContext, *, write_gitignore: bool) -> dict[str, Any]:
    if ctx.ledger_dir.exists() and not ctx.ledger_dir.is_dir():
        raise GitWarpError(f"runtime path is not a directory: {ctx.ledger_dir}")
    for path in (ctx.worktree_root, ctx.dossier_root):
        if path.exists() and not path.is_dir():
            raise GitWarpError(f"runtime path is not a directory: {path}")

    ledger: dict[str, Any] | None = None
    ledger_needs_write = False
    if ctx.ledger_path.exists():
        try:
            raw = json.loads(ctx.ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GitWarpError(f"invalid ledger file: {ctx.ledger_path}") from exc
        before = json.dumps(raw, sort_keys=True)
        ledger = normalize_ledger_schema(raw, ctx)
        after = json.dumps(ledger, sort_keys=True)
        ledger_needs_write = before != after

    ignore_target = ctx.gitignore_path if write_gitignore else ctx.git_info_exclude_path
    ensure_ignore_target_writable(ignore_target)
    ignore_rule_needed = not target_contains_gitwarp_rule(ignore_target)
    if not write_gitignore and git_ignores_gitwarp(ctx):
        ignore_rule_needed = False

    return {
        "ledger": ledger,
        "ledger_needs_write": ledger_needs_write,
        "ignore_target": ignore_target,
        "ignore_rule_needed": ignore_rule_needed,
    }


def init_recommendations(ctx: RepoContext) -> list[str]:
    return [
        "gitwarp doctor",
        "gitwarp enter",
        'gitwarp task create --title "<title>" --description "<summary>"',
    ]


def is_gitwarp_source_checkout(ctx: RepoContext) -> bool:
    source_root = ctx.checkout_root
    required = [
        source_root / "skills" / "gitwarp" / "SKILL.md",
        source_root / "skills" / "gitwarp" / "scripts" / "install_cli.py",
        source_root / "src" / "gitwarp" / "adapters" / "cli" / "entrypoint.py",
        source_root / ".codex-plugin" / "plugin.json",
        source_root / ".agents" / "plugins" / "api_marketplace.json",
    ]
    return all(path.exists() for path in required)
