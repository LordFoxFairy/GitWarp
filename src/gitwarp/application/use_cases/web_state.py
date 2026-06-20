from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...application.diagnostics import build_doctor_payload, build_finding, summarize_findings
from ...application.reconcile import build_reconcile_payload
from ...application.views import board_row, statusline_banner
from ...infrastructure.ledger import default_ledger, discover_repo, normalize_ledger_schema
from ...infrastructure.runtime import GitWarpError, RepoContext, resolve_path
from ...infrastructure.worktrees import build_head_drift, find_worktree_for_cwd, parse_worktrees


def safe_load_ledger_for_web(ctx: RepoContext) -> tuple[dict[str, Any], str | None]:
    if not ctx.ledger_path.exists():
        return default_ledger(ctx), None
    try:
        data = json.loads(ctx.ledger_path.read_text(encoding="utf-8"))
        return normalize_ledger_schema(data, ctx), None
    except (GitWarpError, json.JSONDecodeError) as exc:
        return default_ledger(ctx), str(exc)

def sync_ledger_for_web(
    ctx: RepoContext,
    live_worktrees: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    ledger, ledger_error = safe_load_ledger_for_web(ctx)
    metadata_by_path = {entry["path"]: entry for entry in ledger["entries"] if entry.get("path")}
    enriched: list[dict[str, Any]] = []
    for item in live_worktrees:
        meta = metadata_by_path.get(item["path"], {})
        last_seen_head = meta.get("last_seen_head")
        enriched_item = {
            "path": item["path"],
            "head": item["head"],
            "branch": item.get("branch"),
            "detached": item.get("detached", False),
            "is_main": item.get("is_main", False),
            "agent_id": meta.get("agent_id"),
            "purpose": meta.get("purpose"),
            "status": meta.get("status"),
            "notes": meta.get("notes", []),
            "dossier_path": meta.get("dossier_path"),
            "task_md": meta.get("task_md"),
            "progress_md": meta.get("progress_md"),
            "lessons_md": meta.get("lessons_md"),
            "latest_progress": meta.get("latest_progress"),
            "latest_lesson": meta.get("latest_lesson"),
            "last_seen_head": last_seen_head,
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
            "dispatch": meta.get("dispatch"),
            "instructions": meta.get("instructions"),
            "instruction_profile": meta.get("instruction_profile"),
            "instruction_mode": meta.get("instruction_mode"),
        }
        head_drift = build_head_drift(last_seen_head, item.get("head"))
        if head_drift is not None:
            enriched_item["head_drift"] = head_drift
        enriched.append(enriched_item)
    return ledger, enriched, ledger_error

def web_board_row(item: dict[str, Any]) -> dict[str, Any]:
    row = board_row(item, verbose=True)
    if item.get("dispatch") is not None:
        row["dispatch"] = item["dispatch"]
    return row


def actionable_finding_count(group: dict[str, Any]) -> int:
    return sum(1 for finding in group.get("findings", []) if finding.get("severity") != "ok")


def build_project_summary(
    ctx: RepoContext,
    *,
    readonly: bool,
    statusline: str,
    worktree_rows: list[dict[str, Any]],
    doctor: dict[str, Any],
    reconcile: dict[str, Any],
) -> dict[str, Any]:
    active_worktrees = [row for row in worktree_rows if not row.get("is_main")]
    assigned_agents = {
        str(row["agent_id"])
        for row in active_worktrees
        if row.get("agent_id")
    }
    return {
        "id": str(ctx.repo_root),
        "name": ctx.repo_root.name,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "readonly": readonly,
        "statusline": statusline,
        "worktree_count": len(worktree_rows),
        "active_worktree_count": len(active_worktrees),
        "assigned_agent_count": len(assigned_agents),
        "doctor_finding_count": actionable_finding_count(doctor),
        "reconcile_finding_count": actionable_finding_count(reconcile),
    }

def build_web_state_payload(
    cwd: Path | str,
    *,
    readonly: bool,
    doctor_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = discover_repo(resolve_path(str(cwd)))
    _, worktrees, ledger_error = sync_ledger_for_web(ctx, parse_worktrees(ctx))
    target = find_worktree_for_cwd(ctx.cwd, worktrees)
    doctor = build_doctor_payload(ctx, web_safe=True, cache=doctor_cache)
    if ledger_error:
        reconcile = {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "findings": [
                build_finding(
                    "ledger_schema",
                    "error",
                    f"GitWarp ledger is invalid: {ledger_error}",
                    path=str(ctx.ledger_path),
                )
            ],
        }
        reconcile["summary"] = summarize_findings(reconcile["findings"])
    else:
        reconcile = build_reconcile_payload(ctx)
    worktree_rows = [web_board_row(item) for item in worktrees]
    statusline = statusline_banner(target)
    project = build_project_summary(
        ctx,
        readonly=readonly,
        statusline=statusline,
        worktree_rows=worktree_rows,
        doctor=doctor,
        reconcile=reconcile,
    )
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "readonly": readonly,
        "statusline": statusline,
        "projects": [project],
        "worktrees": worktree_rows,
        "doctor": doctor,
        "reconcile": reconcile,
        "recommended_next": list(doctor.get("recommended_next", [])),
    }
