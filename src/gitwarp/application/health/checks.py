from __future__ import annotations

import hashlib
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


GITWARP_PLUGIN_ID = "gitwarp@gitwarp-dev"
PLUGIN_CACHE_RELATIVE_PATHS = (
    "hooks/session-start-codex",
    "hooks/hooks-codex.json",
    "hooks/hooks.json",
    "skills/gitwarp/SKILL.md",
    "skills/gitwarp/scripts/install_cli.py",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_codex_plugin_list(raw: str) -> list[dict[str, Any]]:
    start = raw.find("{")
    if start < 0:
        return []
    try:
        payload = json.loads(raw[start:])
    except json.JSONDecodeError:
        return []
    installed = payload.get("installed", [])
    if not isinstance(installed, list):
        return []
    return [item for item in installed if isinstance(item, dict)]


def gitwarp_plugin_entry(plugin_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((item for item in plugin_items if item.get("pluginId") == GITWARP_PLUGIN_ID), None)


def infer_codex_plugin_cache_path(entry: dict[str, Any], cache_root: Path) -> Path | None:
    marketplace = entry.get("marketplaceName")
    name = entry.get("name")
    version = entry.get("version")
    if not all(isinstance(value, str) and value for value in (marketplace, name, version)):
        return None
    return cache_root / marketplace / name / version


def plugin_source_root(entry: dict[str, Any]) -> Path | None:
    marketplace_source = entry.get("marketplaceSource")
    if isinstance(marketplace_source, dict) and isinstance(marketplace_source.get("source"), str):
        return Path(marketplace_source["source"]).expanduser().resolve()
    source = entry.get("source")
    if isinstance(source, dict) and isinstance(source.get("path"), str):
        return Path(source["path"]).expanduser().resolve()
    return None


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
        enabled = any(item.get("pluginId") == GITWARP_PLUGIN_ID and item.get("enabled") is True for item in parse_codex_plugin_list(result.stdout))
    return doctor_check(
        "codex_plugin_metadata",
        "ok" if enabled else "warning",
        "Codex GitWarp plugin is installed and enabled." if enabled else "Codex is available but GitWarp plugin metadata was not confirmed.",
        codex=codex_path,
        plugin_id=GITWARP_PLUGIN_ID,
        enabled=enabled,
    )


def codex_plugin_cache_check(
    ctx: RepoContext,
    *,
    plugin_items: list[dict[str, Any]] | None = None,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    codex_path = shutil.which("codex")
    if plugin_items is None:
        if not codex_path:
            return doctor_check("codex_plugin_cache", "warning", "codex is not available on PATH.", plugin_id=GITWARP_PLUGIN_ID)
        result = run_command_for_doctor(["codex", "plugin", "list", "--json"], ctx.repo_root, timeout=5.0)
        if result is None or result.returncode != 0:
            return doctor_check("codex_plugin_cache", "warning", "Codex plugin list was not available.", plugin_id=GITWARP_PLUGIN_ID)
        plugin_items = parse_codex_plugin_list(result.stdout)

    entry = gitwarp_plugin_entry(plugin_items)
    if entry is None or entry.get("enabled") is not True:
        return doctor_check("codex_plugin_cache", "warning", "Codex GitWarp plugin cache was not checked because the plugin is not enabled.", plugin_id=GITWARP_PLUGIN_ID)

    cache_path = infer_codex_plugin_cache_path(entry, cache_root or (Path.home() / ".codex" / "plugins" / "cache"))
    source_root = plugin_source_root(entry)
    expected_source = ctx.checkout_root.resolve()
    source_matches = source_root is None or source_root == expected_source
    if cache_path is None:
        return doctor_check(
            "codex_plugin_cache",
            "warning",
            "Codex GitWarp plugin cache path could not be inferred.",
            plugin_id=GITWARP_PLUGIN_ID,
            source_root=str(source_root) if source_root else None,
            source_matches=source_matches,
        )

    checked: list[dict[str, Any]] = []
    source_missing: list[str] = []
    missing: list[str] = []
    mismatches: list[str] = []
    for relative in PLUGIN_CACHE_RELATIVE_PATHS:
        source_file = expected_source / relative
        cached_file = cache_path / relative
        source_exists = source_file.is_file()
        cached_exists = cached_file.is_file()
        source_hash = sha256_file(source_file) if source_exists else None
        cached_hash = sha256_file(cached_file) if cached_exists else None
        matches = bool(source_hash and cached_hash and source_hash == cached_hash)
        checked.append(
            {
                "relative_path": relative,
                "source_exists": source_exists,
                "cached_exists": cached_exists,
                "matches": matches,
            }
        )
        if not cached_exists:
            missing.append(relative)
        if not source_exists:
            source_missing.append(relative)
        elif source_exists and not matches:
            mismatches.append(relative)

    ok = source_matches and cache_path.is_dir() and not source_missing and not missing and not mismatches
    return doctor_check(
        "codex_plugin_cache",
        "ok" if ok else "warning",
        "Installed Codex GitWarp plugin cache matches this checkout."
        if ok
        else "Installed Codex GitWarp plugin cache is stale or does not match this checkout.",
        plugin_id=GITWARP_PLUGIN_ID,
        cache_path=str(cache_path),
        cache_exists=cache_path.is_dir(),
        source_root=str(source_root) if source_root else None,
        expected_source=str(expected_source),
        source_matches=source_matches,
        source_missing=source_missing,
        missing=missing,
        mismatches=mismatches,
        checked=checked,
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
    has_install_guard = "if ! command -v gitwarp" in text
    has_task_create_probe = "gitwarp task create --help" in text
    configs_ok = all(state["ok"] for state in config_states.values())
    ok = (
        executable
        and has_context
        and has_statusline
        and has_enter_reference
        and has_diagnostics
        and has_install_guard
        and has_task_create_probe
        and configs_ok
    )
    return doctor_check(
        "session_hook_context",
        "ok" if ok else "warning",
        "Session hook and host hook configs include compact GitWarp context anchoring." if ok else "Session hook is missing executable/context/install-guard/config wiring.",
        path=str(hook_path),
        exists=True,
        executable=executable,
        has_context=has_context,
        has_statusline=has_statusline,
        has_enter_reference=has_enter_reference,
        has_diagnostics=has_diagnostics,
        has_install_guard=has_install_guard,
        has_task_create_probe=has_task_create_probe,
        configs=config_states,
    )
