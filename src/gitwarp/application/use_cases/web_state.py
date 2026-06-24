from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...application.diagnostics import build_doctor_payload, build_finding, summarize_findings
from ...application.reconcile import build_reconcile_payload
from ...application.views import board_row, statusline_banner
from ...domain.errors import GitWarpError as DomainGitWarpError
from ...domain.branch_roles import enrich_role_metadata
from ...infrastructure.ledger import default_ledger, discover_repo, load_project_registry, normalize_ledger_schema
from ...infrastructure.runtime import GitWarpError, RepoContext, project_registry_path, resolve_path
from ...infrastructure.worktrees import (
    build_head_drift,
    find_worktree_for_cwd,
    metadata_by_worktree_key,
    parse_worktrees,
    worktree_metadata_key,
)
from .branches import list_local_branch_refs, resolve_default_branch
from .matrix import build_matrix_payload
from .next_actions import build_next_actions_payload


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
    metadata_by_key = metadata_by_worktree_key(ledger)
    enriched: list[dict[str, Any]] = []
    for item in live_worktrees:
        meta = metadata_by_key.get(worktree_metadata_key(item), {})
        last_seen_head = meta.get("last_seen_head")
        branch_role, base_branch = enrich_role_metadata(item, meta)
        enriched_item = {
            "path": item["path"],
            "head": item["head"],
            "branch": item.get("branch"),
            "detached": item.get("detached", False),
            "is_main": item.get("is_main", False),
            "branch_role": branch_role,
            "base_branch": base_branch,
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
    branch_ref_count: int,
    doctor: dict[str, Any],
    reconcile: dict[str, Any],
    next_actions: list[dict[str, Any]],
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
        "branch_ref_count": branch_ref_count,
        "worktree_count": len(worktree_rows),
        "active_worktree_count": len(active_worktrees),
        "assigned_agent_count": len(assigned_agents),
        "doctor_finding_count": actionable_finding_count(doctor),
        "reconcile_finding_count": actionable_finding_count(reconcile),
        "next_action_count": len(next_actions),
        "destructive_action_count": sum(1 for action in next_actions if action.get("safety") == "confirm_destructive"),
    }



def build_registry_project_summary(repo_root: str, *, readonly: bool) -> dict[str, Any]:
    path = Path(repo_root).expanduser().resolve()
    try:
        ctx = discover_repo(path)
        _, worktrees, ledger_error = sync_ledger_for_web(ctx, parse_worktrees(ctx))
        branch_ref_count = len(list_local_branch_refs(ctx))
        target = find_worktree_for_cwd(ctx.cwd, worktrees)
        doctor = build_doctor_payload(ctx, web_safe=True)
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
        next_actions = build_next_actions_payload(ctx)["actions"]
        worktree_rows = [web_board_row(item) for item in worktrees]
        statusline = statusline_banner(target)
        return build_project_summary(
            ctx,
            readonly=readonly,
            statusline=statusline,
            worktree_rows=worktree_rows,
            branch_ref_count=branch_ref_count,
            doctor=doctor,
            reconcile=reconcile,
            next_actions=next_actions,
        )
    except Exception:
        return {
            "id": str(path),
            "name": path.name,
            "repo_root": str(path),
            "ledger_path": str(path / ".gitwarp" / "ledger.json"),
            "readonly": readonly,
            "statusline": statusline_banner(None),
            "branch_ref_count": 0,
            "worktree_count": 0,
            "active_worktree_count": 0,
            "assigned_agent_count": 0,
            "doctor_finding_count": 0,
            "reconcile_finding_count": 0,
            "next_action_count": 0,
            "destructive_action_count": 0,
        }



def group_matrix_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "base_branches": [row for row in rows if row.get("managed_state") == "gitwarp_managed" and row.get("role") == "base"],
        "task_branches": [row for row in rows if row.get("managed_state") == "gitwarp_managed" and row.get("role") == "task"],
        "unmanaged_branches": [
            row
            for row in rows
            if row.get("managed_state") not in {"gitwarp_managed"}
            and row.get("git", {}).get("branch_ref")
            and row.get("category") not in {"main", "base"}
        ],
    }


def merge_projects(
    selected_project: dict[str, Any],
    *,
    readonly: bool,
    registry_projects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_root = selected_project["repo_root"]
    ordered_roots = [selected_root]
    ordered_roots.extend(
        repo_root
        for item in registry_projects
        if isinstance((repo_root := item.get("repo_root")), str) and repo_root != selected_root
    )
    projects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for repo_root in ordered_roots:
        if repo_root in seen:
            continue
        if repo_root == selected_root:
            projects.append(selected_project)
        else:
            projects.append(build_registry_project_summary(repo_root, readonly=readonly))
        seen.add(repo_root)
    return projects



def build_web_state_payload(
    cwd: Path | str,
    *,
    readonly: bool,
    doctor_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = discover_repo(resolve_path(str(cwd)))
    _, worktrees, ledger_error = sync_ledger_for_web(ctx, parse_worktrees(ctx))
    branch_ref_count = len(list_local_branch_refs(ctx))
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
    next_actions = build_next_actions_payload(ctx)["actions"]
    worktree_rows = [web_board_row(item) for item in worktrees]
    statusline = statusline_banner(target)
    project = build_project_summary(
        ctx,
        readonly=readonly,
        statusline=statusline,
        worktree_rows=worktree_rows,
        branch_ref_count=branch_ref_count,
        doctor=doctor,
        reconcile=reconcile,
        next_actions=next_actions,
    )
    registry = load_project_registry(project_registry_path())
    projects = merge_projects(project, readonly=readonly, registry_projects=registry["projects"])
    try:
        matrix = build_matrix_payload(ctx)
    except DomainGitWarpError as exc:
        if ledger_error:
            default_branch = resolve_default_branch(ctx)
            matrix = {
                "ok": True,
                "repo_root": str(ctx.repo_root),
                "ledger_path": str(ctx.ledger_path),
                "default_branch": default_branch,
                "merge_base": default_branch,
                "statusline": statusline,
                "sources": {
                    "git_branch_refs": branch_ref_count,
                    "git_worktrees": len(worktree_rows),
                    "ledger_entries": 0,
                    "dossier_dirs": 0,
                    "reconcile_findings": 1,
                },
                "summary": {
                    "rows": 0,
                    "active_gitwarp_tasks": 0,
                    "untracked_worktrees": 0,
                    "stale_ledger_entries": 0,
                    "merged_gitwarp_tasks": 0,
                    "prunable_branch_refs": 0,
                    "orphan_branch_refs": 0,
                    "orphan_dossiers": 0,
                },
                "rows": [],
                "reconcile": {
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
                    "summary": summarize_findings([
                        build_finding(
                            "ledger_schema",
                            "error",
                            f"GitWarp ledger is invalid: {ledger_error}",
                            path=str(ctx.ledger_path),
                        )
                    ]),
                },
                "warning": str(exc),
            }
        else:
            raise
    matrix["groups"] = group_matrix_rows(matrix["rows"])
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "readonly": readonly,
        "statusline": statusline,
        "projects": projects,
        "worktrees": worktree_rows,
        "doctor": doctor,
        "reconcile": reconcile,
        "matrix": matrix,
        "next_actions": next_actions,
        "recommended_next": list(doctor.get("recommended_next", [])),
    }
