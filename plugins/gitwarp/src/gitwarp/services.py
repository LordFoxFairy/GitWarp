from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .agents import build_agent_id, load_agent_registry, render_agent_prompt, render_command, shell_preview
from .diagnostics import build_doctor_payload, build_finding, summarize_findings
from .diagnostics import append_gitwarp_ignore_rule, init_recommendations, preflight_init
from .dossiers import create_dossier_files, dossier_paths, record_handoff
from .foundation import GitWarpError, RepoContext, now_iso, resolve_path, run_git
from .ledger import default_ledger, discover_repo, mutate_ledger, normalize_ledger_schema, write_ledger
from .reconcile import build_reconcile_payload
from .reporting import board_row, statusline_banner
from .worktrees import build_head_drift, create_worktree, ensure_branch_available, find_worktree_for_cwd, parse_worktrees
from .worktrees import select_collapse_target, select_live_target, sync_ledger


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
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "readonly": readonly,
        "statusline": statusline_banner(target),
        "worktrees": [web_board_row(item) for item in worktrees],
        "doctor": doctor,
        "reconcile": reconcile,
        "recommended_next": list(doctor.get("recommended_next", [])),
    }


def build_init_payload(ctx: RepoContext, *, write_gitignore: bool) -> dict[str, Any]:
    preflight = preflight_init(ctx, write_gitignore=write_gitignore)
    created = {
        "ledger_dir": not ctx.ledger_dir.exists(),
        "ledger": not ctx.ledger_path.exists(),
        "worktree_root": not ctx.worktree_root.exists(),
        "dossier_root": not ctx.dossier_root.exists(),
    }
    updated = {
        "ledger": bool(preflight["ledger_needs_write"]),
        "ignore_rule": bool(preflight["ignore_rule_needed"]),
    }

    ctx.ledger_dir.mkdir(parents=True, exist_ok=True)
    ctx.worktree_root.mkdir(parents=True, exist_ok=True)
    ctx.dossier_root.mkdir(parents=True, exist_ok=True)

    if created["ledger"]:
        write_ledger(ctx, default_ledger(ctx))
    elif updated["ledger"]:
        write_ledger(ctx, preflight["ledger"], touch_updated_at=False)

    if updated["ignore_rule"]:
        append_gitwarp_ignore_rule(preflight["ignore_target"])

    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "worktree_root": str(ctx.worktree_root),
        "dossier_root": str(ctx.dossier_root),
        "created": created,
        "updated": updated,
        "ignore_target": str(preflight["ignore_target"]),
        "recommended_next": init_recommendations(ctx),
    }


def build_start_payload(ctx: RepoContext, *, agent_id: str, branch: str, purpose: str) -> dict[str, Any]:
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)
    target_dir, existing_branch, head = create_worktree(ctx, branch)
    created_at = now_iso()
    dossier = dossier_paths(ctx, branch, target_dir)
    entry = {
        "path": str(target_dir),
        "branch": branch,
        "agent_id": agent_id,
        "purpose": purpose,
        "status": "active",
        "notes": [],
        "latest_progress": "Workspace created.",
        "last_seen_head": head,
        "created_at": created_at,
        **dossier,
    }
    create_dossier_files(
        dossier,
        agent_id=agent_id,
        branch=branch,
        worktree_path=str(target_dir),
        purpose=purpose,
        status="active",
        created_at=created_at,
    )

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    mutate_ledger(ctx, update)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "path": str(target_dir),
        "branch": branch,
        "head": head,
        "agent_id": agent_id,
        "purpose": purpose,
        "status": "active",
        "branch_created": not existing_branch,
        "last_seen_head": head,
        "latest_progress": "Workspace created.",
        **dossier,
    }


def build_dispatch_payload(
    ctx: RepoContext,
    *,
    agent: str | None,
    agent_id: str | None,
    branch: str,
    purpose: str,
) -> dict[str, Any]:
    registry = load_agent_registry(ctx)
    agent_name = agent or registry["default_agent"]
    agents_by_name = registry["agents_by_name"]
    if agent_name not in agents_by_name:
        raise GitWarpError(f"unknown agent '{agent_name}'; available agents: {', '.join(sorted(agents_by_name))}")
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)

    selected_agent = agents_by_name[agent_name]
    resolved_agent_id = agent_id or build_agent_id(agent_name, branch)
    target_dir, existing_branch, head = create_worktree(ctx, branch)
    created_at = now_iso()
    dossier = dossier_paths(ctx, branch, target_dir)
    prompt = render_agent_prompt(purpose)
    values = {
        "repo": str(ctx.repo_root),
        "worktree": str(target_dir),
        "branch": branch,
        "agent_id": resolved_agent_id,
        "purpose": purpose,
        "task_md": dossier["task_md"],
        "progress_md": dossier["progress_md"],
        "lessons_md": dossier["lessons_md"],
        "prompt": prompt,
    }
    launch_command = render_command(selected_agent["command"], values)
    launch_preview = shell_preview(launch_command)
    dispatch_meta = {
        "agent_name": agent_name,
        "command_mode": "print",
        "launch_command": launch_command,
        "launch_preview": launch_preview,
        "last_exit_code": None,
        "last_prepared_at": created_at,
        "last_started_at": None,
        "last_finished_at": None,
    }
    entry = {
        "path": str(target_dir),
        "branch": branch,
        "agent_id": resolved_agent_id,
        "purpose": purpose,
        "status": "dispatched",
        "notes": [],
        "latest_progress": "Dispatch command prepared.",
        "last_seen_head": head,
        "created_at": created_at,
        "updated_at": created_at,
        "dispatch": dispatch_meta,
        **dossier,
    }
    create_dossier_files(
        dossier,
        agent_id=resolved_agent_id,
        branch=branch,
        worktree_path=str(target_dir),
        purpose=purpose,
        status="dispatched",
        created_at=created_at,
    )

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    mutate_ledger(ctx, update)
    return {
        "ok": True,
        "mode": "print",
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "agent": agent_name,
        "agent_id": resolved_agent_id,
        "path": str(target_dir),
        "branch": branch,
        "head": head,
        "purpose": purpose,
        "status": "dispatched",
        "branch_created": not existing_branch,
        "last_seen_head": head,
        "launch_command": launch_command,
        "launch_preview": launch_preview,
        **dossier,
    }


def build_handoff_payload(
    ctx: RepoContext,
    *,
    cwd: str,
    path: str | None,
    branch: str | None,
    status: str,
    progress: str,
    lesson: str | None,
) -> dict[str, Any]:
    resolved_cwd = resolve_path(cwd or path)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(worktrees=worktrees, cwd=resolved_cwd, path_arg=path, branch_arg=branch)
    entry, paths = record_handoff(ctx, target, status=status, progress=progress, lesson=lesson)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "path": target["path"],
        "branch": target.get("branch"),
        "agent_id": entry.get("agent_id"),
        "purpose": entry.get("purpose"),
        "status": entry.get("status"),
        "latest_progress": entry.get("latest_progress"),
        "latest_lesson": entry.get("latest_lesson"),
        **paths,
    }


def worktree_status_summary(path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    lines = run_git(Path(path), "status", "--porcelain").splitlines()
    untracked = [line[3:] for line in lines if line.startswith("?? ")]
    return (
        {"count": len(lines), "sample": lines[:20]},
        {"count": len(untracked), "sample": untracked[:20]},
    )


def inspect_destructive_target(
    ctx: RepoContext,
    *,
    action: str,
    cwd: str | None,
    path: str | None,
    branch: str | None,
) -> dict[str, Any]:
    resolved_cwd = resolve_path(cwd or path or str(ctx.cwd))
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    target = select_live_target(worktrees=worktrees, cwd=resolved_cwd, path_arg=path, branch_arg=branch)
    if target.get("is_main"):
        raise GitWarpError("refusing to target the main repository checkout")
    target_path = target["path"]
    dirty_summary, untracked_summary = worktree_status_summary(target_path)
    entry = next((item for item in ledger["entries"] if item.get("path") == target_path), {})
    return {
        "action": action,
        "path": target_path,
        "branch": target.get("branch"),
        "head": run_git(Path(target_path), "rev-parse", "HEAD"),
        "dirty_summary": dirty_summary,
        "untracked_summary": untracked_summary,
        "agent_id": entry.get("agent_id"),
        "purpose": entry.get("purpose"),
        "status": entry.get("status"),
        "dossier_path": entry.get("dossier_path"),
    }


def collapse_worktree(ctx: RepoContext, *, path: str | None, branch: str | None) -> tuple[str, str | None]:
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target_path, removed_branch = select_collapse_target(
        worktrees=worktrees,
        ledger=ledger,
        path_arg=path,
        branch_arg=branch,
        repo_root=ctx.repo_root,
    )
    run_git(ctx.repo_root, "worktree", "remove", "--force", target_path)
    run_git(ctx.repo_root, "worktree", "prune", "--expire", "now")
    target_dir = Path(target_path)
    if target_dir.exists():
        shutil.rmtree(target_dir)

    def update(locked_ledger: dict[str, Any]) -> None:
        locked_ledger["entries"] = [item for item in locked_ledger["entries"] if item.get("path") != target_path]

    mutate_ledger(ctx, update)
    return target_path, removed_branch


def build_finish_payload(
    ctx: RepoContext,
    *,
    cwd: str,
    path: str | None,
    branch: str | None,
    status: str,
    progress: str,
    lesson: str | None,
    collapse: bool,
) -> dict[str, Any]:
    resolved_cwd = resolve_path(cwd or path)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(worktrees=worktrees, cwd=resolved_cwd, path_arg=path, branch_arg=branch)
    entry, paths = record_handoff(ctx, target, status=status, progress=progress, lesson=lesson)

    collapsed = False
    removed_branch = None
    if collapse:
        _, removed_branch = collapse_worktree(ctx, path=target["path"], branch=None)
        collapsed = True
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "path": target["path"],
        "branch": target.get("branch"),
        "removed_branch": removed_branch,
        "agent_id": entry.get("agent_id"),
        "purpose": entry.get("purpose"),
        "status": entry.get("status"),
        "latest_progress": entry.get("latest_progress"),
        "latest_lesson": entry.get("latest_lesson"),
        "collapsed": collapsed,
        "purged_dossier": False,
        **paths,
    }


def build_collapse_payload(ctx: RepoContext, *, path: str | None, branch: str | None) -> dict[str, Any]:
    target_path, removed_branch = collapse_worktree(ctx, path=path, branch=branch)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "removed_path": target_path,
        "removed_branch": removed_branch,
    }
