from __future__ import annotations

import json
import shutil
import time
from typing import Any

from ...infrastructure.runtime import RepoContext
from .checks import (
    agent_config_check,
    codex_plugin_cache_check,
    codex_plugin_metadata_check,
    gitwarp_ignored_check,
    gitwarp_initialized_check,
    ledger_schema_check,
    session_hook_context_check,
    standard_skill_links_check,
)
from .findings import doctor_check, summarize_findings
from .init import is_gitwarp_source_checkout
from .process import run_command_for_doctor


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
        elif code == "codex_plugin_cache" and severity == "warning":
            recommendations.append("Run scripts/install-codex-plugin.sh from this checkout to refresh the installed Codex plugin cache.")
        elif code == "standard_skill_links" and severity == "warning":
            recommendations.append("Restore .agents/skills/gitwarp and .claude/skills/gitwarp links.")
        elif code == "session_hook_context" and severity == "warning":
            recommendations.append("Update hooks/session-start-codex to include compact gitwarp statusline context anchoring.")

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
        findings.append(codex_plugin_cache_check(ctx))

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
