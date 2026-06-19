from __future__ import annotations

import json
import os
import shutil
from typing import Any

from ...infrastructure.agents import load_agent_registry
from ...infrastructure.ledger import normalize_ledger_schema
from ...infrastructure.runtime import GitWarpError, RepoContext
from .findings import doctor_check
from .init import git_ignores_gitwarp
from .process import run_command_for_doctor


def gitwarp_initialized_check(ctx: RepoContext) -> dict[str, Any]:
    exists = ctx.ledger_dir.is_dir() and ctx.worktree_root.is_dir() and ctx.dossier_root.is_dir()
    return doctor_check(
        "gitwarp_initialized",
        "ok" if exists else "warning",
        "GitWarp runtime directories are initialized." if exists else "GitWarp runtime directories are not initialized.",
        ledger_dir=str(ctx.ledger_dir),
        worktree_root=str(ctx.worktree_root),
        dossier_root=str(ctx.dossier_root),
        initialized=exists,
    )


def ledger_schema_check(ctx: RepoContext) -> dict[str, Any]:
    if not ctx.ledger_path.exists():
        return doctor_check(
            "ledger_schema",
            "warning",
            "GitWarp ledger has not been created.",
            path=str(ctx.ledger_path),
            exists=False,
        )
    try:
        raw = json.loads(ctx.ledger_path.read_text(encoding="utf-8"))
        normalize_ledger_schema(raw, ctx)
    except (GitWarpError, json.JSONDecodeError) as exc:
        return doctor_check(
            "ledger_schema",
            "error",
            f"GitWarp ledger is invalid: {exc}",
            path=str(ctx.ledger_path),
            exists=True,
        )
    return doctor_check(
        "ledger_schema",
        "ok",
        "GitWarp ledger schema is valid.",
        path=str(ctx.ledger_path),
        exists=True,
    )


def gitwarp_ignored_check(ctx: RepoContext) -> dict[str, Any]:
    ignored = git_ignores_gitwarp(ctx)
    return doctor_check(
        "gitwarp_ignored",
        "ok" if ignored else "warning",
        ".gitwarp is ignored." if ignored else ".gitwarp is not ignored by this repository.",
        ignored=ignored,
        gitignore_path=str(ctx.gitignore_path),
        info_exclude_path=str(ctx.git_info_exclude_path),
    )


def standard_skill_links_check(ctx: RepoContext) -> dict[str, Any]:
    links = {
        "codex": ctx.repo_root / ".agents" / "skills" / "gitwarp",
        "claude": ctx.repo_root / ".claude" / "skills" / "gitwarp",
    }
    target = (ctx.repo_root / "skills" / "gitwarp").resolve()
    states: dict[str, dict[str, Any]] = {}
    ok = True
    for name, path in links.items():
        exists = path.exists() or path.is_symlink()
        points_to_target = exists and path.resolve() == target
        ok = ok and bool(points_to_target)
        states[name] = {
            "path": str(path),
            "exists": exists,
            "is_symlink": path.is_symlink(),
            "target": str(path.resolve()) if exists else None,
        }
    return doctor_check(
        "standard_skill_links",
        "ok" if ok else "warning",
        "Standard skill discovery links point at the canonical skill." if ok else "Standard skill discovery links are missing or misdirected.",
        expected_target=str(target),
        links=states,
    )


def agent_config_check(ctx: RepoContext) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        registry = load_agent_registry(ctx)
    except GitWarpError as exc:
        return (
            doctor_check(
                "agent_config",
                "error",
                str(exc),
                path=str(ctx.agents_path),
                configured=ctx.agents_path.exists(),
            ),
            None,
        )
    return (
        doctor_check(
            "agent_config",
            "ok",
            "Agent config is valid or absent.",
            path=str(ctx.agents_path),
            configured=registry["config_loaded"],
            default_agent=registry["default_agent"],
            count=len(registry["agents"]),
        ),
        registry,
    )


def codex_plugin_metadata_check(ctx: RepoContext) -> dict[str, Any]:
    codex_path = shutil.which("codex")
    if not codex_path:
        return doctor_check("codex_plugin_metadata", "warning", "codex is not available on PATH.")

    result = run_command_for_doctor(["codex", "plugin", "list", "--json"], ctx.repo_root, timeout=5.0)
    enabled = False
    if result and result.returncode == 0:
        raw = result.stdout
        start = raw.find("{")
        if start >= 0:
            try:
                payload = json.loads(raw[start:])
                enabled = any(
                    item.get("pluginId") == "gitwarp@gitwarp-dev" and item.get("enabled") is True
                    for item in payload.get("installed", [])
                )
            except json.JSONDecodeError:
                enabled = False
    return doctor_check(
        "codex_plugin_metadata",
        "ok" if enabled else "warning",
        "Codex GitWarp plugin is installed and enabled." if enabled else "Codex is available but GitWarp plugin metadata was not confirmed.",
        codex=codex_path,
        plugin_id="gitwarp@gitwarp-dev",
        enabled=enabled,
    )


def session_hook_context_check(ctx: RepoContext) -> dict[str, Any]:
    hook_path = ctx.repo_root / "hooks" / "session-start-codex"
    if not hook_path.exists():
        return doctor_check(
            "session_hook_context",
            "warning",
            "Session hook script is not present.",
            path=str(hook_path),
            exists=False,
            executable=False,
        )
    text = hook_path.read_text(encoding="utf-8", errors="replace")
    executable = os.access(hook_path, os.X_OK)
    has_context = "GitWarp Context:" in text
    has_enter = "gitwarp enter --cwd" in text
    ok = executable and has_context and has_enter
    return doctor_check(
        "session_hook_context",
        "ok" if ok else "warning",
        "Session hook statically includes GitWarp context anchoring." if ok else "Session hook is missing executable/context/enter wiring.",
        path=str(hook_path),
        exists=True,
        executable=executable,
        has_context=has_context,
        has_enter=has_enter,
    )
