from __future__ import annotations

from typing import Any

from ...domain.model import DispatchPlan, DossierRef, WorkspaceRecord
from ...infrastructure.agents import build_agent_id, load_agent_registry, render_agent_prompt, render_command, shell_preview
from ...infrastructure.dossiers import create_dossier_files, dossier_paths
from ...infrastructure.ledger import mutate_ledger
from ...infrastructure.runtime import GitWarpError, RepoContext, now_iso
from ...infrastructure.worktrees import create_worktree, ensure_branch_available, parse_worktrees, sync_ledger


def build_start_payload(ctx: RepoContext, *, agent_id: str, branch: str, purpose: str) -> dict[str, Any]:
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)
    target_dir, existing_branch, head = create_worktree(ctx, branch)
    created_at = now_iso()
    dossier = dossier_paths(ctx, branch, target_dir)
    entry = WorkspaceRecord(
        path=str(target_dir),
        branch=branch,
        agent_id=agent_id,
        purpose=purpose,
        status="active",
        notes=[],
        dossier=DossierRef.from_mapping(dossier),
        latest_progress="Workspace created.",
        last_seen_head=head,
        created_at=created_at,
    ).to_dict()
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


def build_summon_payload(ctx: RepoContext, *, agent_id: str, branch: str, purpose: str) -> dict[str, Any]:
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)

    target_dir, existing_branch, head = create_worktree(ctx, branch)
    entry = WorkspaceRecord(
        path=str(target_dir),
        branch=branch,
        agent_id=agent_id,
        purpose=purpose,
        status="active",
        notes=[],
        last_seen_head=head,
        created_at=now_iso(),
    ).to_dict()

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
        "branch_created": not existing_branch,
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
    dispatch_meta = DispatchPlan(
        agent_name=agent_name,
        agent_id=resolved_agent_id,
        launch_command=launch_command,
        launch_preview=launch_preview,
        prepared_at=created_at,
    ).to_metadata()
    entry = WorkspaceRecord(
        path=str(target_dir),
        branch=branch,
        agent_id=resolved_agent_id,
        purpose=purpose,
        status="dispatched",
        notes=[],
        dossier=DossierRef.from_mapping(dossier),
        latest_progress="Dispatch command prepared.",
        last_seen_head=head,
        created_at=created_at,
        updated_at=created_at,
        dispatch=dispatch_meta,
    ).to_dict()
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
