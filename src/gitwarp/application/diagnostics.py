from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ..infrastructure.agents import load_agent_registry
from ..infrastructure.ledger import normalize_ledger_schema
from ..infrastructure.runtime import GitWarpError, RepoContext


def build_finding(
    code: str,
    severity: str,
    message: str,
    *,
    item: dict[str, Any] | None = None,
    path: str | None = None,
    branch: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "path": path if path is not None else (item or {}).get("path"),
        "branch": branch if branch is not None else (item or {}).get("branch"),
        "agent_id": agent_id if agent_id is not None else (item or {}).get("agent_id"),
    }


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for finding in findings:
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
        by_code[finding["code"]] = by_code.get(finding["code"], 0) + 1
    return {"total": len(findings), "by_severity": by_severity, "by_code": by_code}


def doctor_check(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    finding = {"code": code, "severity": severity, "message": message}
    if details:
        finding["details"] = details
    return finding


def run_command_for_doctor(command: list[str], cwd: Path, timeout: float = 3.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


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
        f"gitwarp doctor --cwd \"{ctx.repo_root}\"",
        f"gitwarp enter --cwd \"{ctx.repo_root}\"",
        f"gitwarp dispatch --cwd \"{ctx.repo_root}\" --agent codex --branch <branch> --purpose \"<purpose>\"",
    ]


def is_gitwarp_source_checkout(ctx: RepoContext) -> bool:
    required = [
        ctx.repo_root / "skills" / "gitwarp" / "SKILL.md",
        ctx.repo_root / "skills" / "gitwarp" / "scripts" / "gitwarp.py",
        ctx.repo_root / ".codex-plugin" / "plugin.json",
        ctx.repo_root / ".agents" / "plugins" / "api_marketplace.json",
    ]
    return all(path.exists() for path in required)


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


def recommended_next_for_findings(ctx: RepoContext, findings: list[dict[str, Any]]) -> list[str]:
    recommendations: list[str] = []
    for finding in findings:
        code = finding["code"]
        severity = finding["severity"]
        details = finding.get("details", {})
        if code in {"gitwarp_initialized", "ledger_schema", "gitwarp_ignored"} and severity in {"warning", "error"}:
            recommendations.append(f"gitwarp init --cwd \"{ctx.repo_root}\"")
        elif code == "agent_config" and severity == "error":
            recommendations.append(f"Fix or remove {ctx.agents_path}")
        elif code == "gitwarp_launcher" and severity in {"warning", "error"}:
            recommendations.append("Run the GitWarp CLI installer from the skill scripts directory.")
        elif code == "codex_plugin_metadata" and severity == "warning" and details.get("codex"):
            recommendations.append("Install or enable gitwarp@gitwarp-dev in Codex.")
        elif code == "standard_skill_links" and severity == "warning":
            recommendations.append("Restore .agents/skills/gitwarp and .claude/skills/gitwarp links.")
        elif code == "session_hook_context" and severity == "warning":
            recommendations.append("Update hooks/session-start-codex to include gitwarp enter --cwd context anchoring.")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in recommendations:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def build_doctor_payload(
    ctx: RepoContext,
    *,
    web_safe: bool = False,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cache_key = str(ctx.repo_root)
    if web_safe and cache is not None:
        cached_entry = cache.get(cache_key)
        if isinstance(cached_entry, dict):
            age = int(time.monotonic() - float(cached_entry.get("created_at", 0.0)))
            if age < 30 and isinstance(cached_entry.get("payload"), dict):
                payload = json.loads(json.dumps(cached_entry["payload"]))
                payload["cached"] = True
                payload["cache_age_seconds"] = age
                return payload

    findings: list[dict[str, Any]] = []
    source_checkout = is_gitwarp_source_checkout(ctx)

    git_path = shutil.which("git")
    findings.append(
        doctor_check(
            "git",
            "ok" if git_path else "error",
            "git is available." if git_path else "git is not available on PATH.",
            path=git_path,
        )
    )
    python_path = shutil.which("python3")
    findings.append(
        doctor_check(
            "python3",
            "ok" if python_path else "error",
            "python3 is available." if python_path else "python3 is not available on PATH.",
            path=python_path,
        )
    )
    launcher_path = shutil.which("gitwarp")
    launcher_severity = "warning"
    launcher_message = "gitwarp launcher is not available on PATH."
    launcher_details: dict[str, Any] = {"path": launcher_path}
    if launcher_path:
        version = run_command_for_doctor([launcher_path, "--version"], ctx.repo_root)
        if version and version.returncode == 0:
            launcher_severity = "ok"
            launcher_message = "gitwarp launcher is available."
            launcher_details["version"] = version.stdout.strip()
        else:
            launcher_severity = "error"
            launcher_message = "gitwarp launcher exists but --version failed."
    findings.append(doctor_check("gitwarp_launcher", launcher_severity, launcher_message, **launcher_details))

    findings.append(gitwarp_initialized_check(ctx))
    findings.append(ledger_schema_check(ctx))
    findings.append(gitwarp_ignored_check(ctx))

    agent_config, registry = agent_config_check(ctx)
    findings.append(agent_config)
    if registry is not None:
        for agent in registry["agents"]:
            findings.append(
                doctor_check(
                    "agent_binary",
                    "ok" if agent["available"] else "warning",
                    f"Agent binary for '{agent['name']}' is {'available' if agent['available'] else 'not available'}.",
                    agent=agent["name"],
                    command=agent["command"][0],
                )
            )

    findings.append(codex_plugin_metadata_check(ctx))
    if source_checkout:
        findings.append(standard_skill_links_check(ctx))
        findings.append(session_hook_context_check(ctx))

    payload = {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "findings": findings,
        "summary": summarize_findings(findings),
        "recommended_next": recommended_next_for_findings(ctx, findings),
    }
    if web_safe:
        payload["cached"] = False
        payload["cache_age_seconds"] = 0
        if cache is not None:
            cache[cache_key] = {"created_at": time.monotonic(), "payload": json.loads(json.dumps(payload))}
    return payload
