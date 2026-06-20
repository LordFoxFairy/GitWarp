from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
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
    source_root = ctx.checkout_root
    links = {
        "codex": source_root / ".agents" / "skills" / "gitwarp",
        "claude": source_root / ".claude" / "skills" / "gitwarp",
    }
    target = (source_root / "skills" / "gitwarp").resolve()
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


def hook_config_state(path: Path) -> dict[str, Any]:
    state: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "valid_json": False,
        "has_session_start": False,
        "commands": [],
        "has_run_hook": False,
        "has_context_hook": False,
        "has_plugin_root": False,
        "has_claude_fallback": False,
        "safe_without_root": False,
        "ok": False,
    }
    if not path.exists():
        return state
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        state["error"] = str(exc)
        return state

    state["valid_json"] = True
    session_start = payload.get("hooks", {}).get("SessionStart") if isinstance(payload, dict) else None
    if not isinstance(session_start, list) or not session_start:
        return state

    commands: list[str] = []
    for group in session_start:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []):
            if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                commands.append(hook["command"])

    joined = "\n".join(commands)
    state["has_session_start"] = True
    state["commands"] = commands
    state["has_run_hook"] = "run-hook.cmd" in joined
    state["has_context_hook"] = "session-start-codex" in joined
    state["has_plugin_root"] = "PLUGIN_ROOT" in joined
    state["has_claude_fallback"] = "CLAUDE_PLUGIN_ROOT" in joined
    state["safe_without_root"] = "exit 0" in joined
    state["ok"] = bool(
        state["has_run_hook"]
        and state["has_context_hook"]
        and state["has_plugin_root"]
        and state["has_claude_fallback"]
        and state["safe_without_root"]
    )
    return state


def session_hook_context_check(ctx: RepoContext) -> dict[str, Any]:
    hook_path = ctx.checkout_root / "hooks" / "session-start-codex"
    config_paths = {
        "default": ctx.checkout_root / "hooks" / "hooks.json",
        "codex": ctx.checkout_root / "hooks" / "hooks-codex.json",
    }
    config_states = {name: hook_config_state(path) for name, path in config_paths.items()}
    if not hook_path.exists():
        return doctor_check(
            "session_hook_context",
            "warning",
            "Session hook script is not present.",
            path=str(hook_path),
            exists=False,
            executable=False,
            configs=config_states,
        )
    text = hook_path.read_text(encoding="utf-8", errors="replace")
    executable = os.access(hook_path, os.X_OK)
    has_context = "GitWarp:" in text
    has_statusline = "gitwarp statusline --cwd" in text
    has_enter_reference = "gitwarp enter" in text
    has_diagnostics = "Diagnostics:" in text
    configs_ok = all(state["ok"] for state in config_states.values())
    ok = executable and has_context and has_statusline and has_enter_reference and has_diagnostics and configs_ok
    return doctor_check(
        "session_hook_context",
        "ok" if ok else "warning",
        "Session hook and host hook configs include compact GitWarp context anchoring." if ok else "Session hook is missing executable/context/config wiring.",
        path=str(hook_path),
        exists=True,
        executable=executable,
        has_context=has_context,
        has_statusline=has_statusline,
        has_enter_reference=has_enter_reference,
        has_diagnostics=has_diagnostics,
        configs=config_states,
    )
