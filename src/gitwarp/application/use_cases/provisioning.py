from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ...domain.branch_roles import BASE_ROLE, DEFAULT_BASE_BRANCH, TASK_ROLE
from ...domain.model import DispatchPlan, DossierRef, WorkspaceRecord
from ...infrastructure.agents import build_agent_id, load_agent_registry, render_agent_prompt, render_command, shell_preview
from ...infrastructure.dossiers import create_dossier_files, dossier_paths
from ...infrastructure.instructions import build_instruction_plan, mount_instruction_files
from ...infrastructure.ledger import mutate_ledger
from ...infrastructure.runtime import GitWarpError, RepoContext, now_iso, run_git
from ...infrastructure.worktrees import create_worktree, ensure_branch_available, find_worktree_for_cwd, parse_worktrees, sync_ledger


def cleanup_created_dossier(ctx: RepoContext, raw_dossier_path: str | None) -> None:
    if not raw_dossier_path:
        return
    dossier_path = Path(raw_dossier_path).resolve()
    try:
        dossier_path.relative_to(ctx.dossier_root.resolve())
    except ValueError:
        return
    try:
        shutil.rmtree(dossier_path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def cleanup_created_worktree(
    ctx: RepoContext,
    target_dir: Any,
    *,
    branch: str,
    branch_created: bool,
    dossier_path: str | None = None,
) -> None:
    try:
        run_git(ctx.repo_root, "worktree", "remove", "--force", str(target_dir))
    except GitWarpError:
        pass
    if branch_created:
        try:
            run_git(ctx.repo_root, "branch", "-D", branch)
        except GitWarpError:
            pass
    cleanup_created_dossier(ctx, dossier_path)


def infer_base_branch(ctx: RepoContext, worktrees: list[dict[str, Any]], requested_base: str | None) -> str:
    if requested_base:
        return requested_base
    current = find_worktree_for_cwd(ctx.cwd, worktrees)
    if current:
        if current.get("branch_role") == BASE_ROLE and current.get("branch"):
            return str(current["branch"])
        if current.get("base_branch"):
            return str(current["base_branch"])
    return DEFAULT_BASE_BRANCH


def build_base_payload(ctx: RepoContext, *, branch: str, purpose: str) -> dict[str, Any]:
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)
    target_dir, existing_branch, head = create_worktree(ctx, branch)
    branch_created = not existing_branch
    created_at = now_iso()
    entry = WorkspaceRecord(
        path=str(target_dir),
        branch=branch,
        agent_id=None,
        purpose=purpose,
        status="base",
        notes=[],
        latest_progress="Base workspace created.",
        last_seen_head=head,
        branch_role=BASE_ROLE,
        base_branch=None,
        created_at=created_at,
    ).to_dict()

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    try:
        mutate_ledger(ctx, update)
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created)
        raise

    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "path": str(target_dir),
        "branch": branch,
        "head": head,
        "agent_id": None,
        "purpose": purpose,
        "status": "base",
        "branch_role": BASE_ROLE,
        "base_branch": None,
        "branch_created": not existing_branch,
        "last_seen_head": head,
        "latest_progress": "Base workspace created.",
    }


def build_start_payload(
    ctx: RepoContext,
    *,
    agent_id: str,
    branch: str,
    purpose: str,
    base_branch: str | None = None,
    instructions: list[str] | None = None,
    instruction_profile: str | None = None,
    instruction_mode: str = "copy",
) -> dict[str, Any]:
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)
    resolved_base_branch = infer_base_branch(ctx, worktrees, base_branch)
    instruction_plan = build_instruction_plan(
        ctx,
        raw_instructions=instructions,
        profile_name=instruction_profile,
        mode=instruction_mode,
    )
    target_dir, existing_branch, head = create_worktree(ctx, branch, start_point=resolved_base_branch)
    branch_created = not existing_branch
    created_at = now_iso()
    dossier = dossier_paths(ctx, branch, target_dir)
    cleanup_dossier = None if Path(dossier["dossier_path"]).exists() else dossier["dossier_path"]
    try:
        mounted_instructions = mount_instruction_files(target_dir, instruction_plan)
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created, dossier_path=cleanup_dossier)
        raise
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
        branch_role=TASK_ROLE,
        base_branch=resolved_base_branch,
        created_at=created_at,
        instructions=mounted_instructions or None,
        instruction_profile=instruction_profile,
        instruction_mode=instruction_mode,
    ).to_dict()
    try:
        create_dossier_files(
            dossier,
            agent_id=agent_id,
            branch=branch,
            worktree_path=str(target_dir),
            purpose=purpose,
            status="active",
            created_at=created_at,
            branch_role=TASK_ROLE,
            base_branch=resolved_base_branch,
            instructions=mounted_instructions,
            instruction_profile=instruction_profile,
        )
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created, dossier_path=cleanup_dossier)
        raise

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    try:
        mutate_ledger(ctx, update)
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created, dossier_path=cleanup_dossier)
        raise
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
        "branch_role": TASK_ROLE,
        "base_branch": resolved_base_branch,
        "branch_created": not existing_branch,
        "last_seen_head": head,
        "latest_progress": "Workspace created.",
        "instructions": mounted_instructions,
        "instruction_profile": instruction_profile,
        "instruction_mode": instruction_mode,
        **dossier,
    }


def build_summon_payload(ctx: RepoContext, *, agent_id: str, branch: str, purpose: str, base_branch: str | None = None) -> dict[str, Any]:
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)
    resolved_base_branch = infer_base_branch(ctx, worktrees, base_branch)

    target_dir, existing_branch, head = create_worktree(ctx, branch, start_point=resolved_base_branch)
    branch_created = not existing_branch
    entry = WorkspaceRecord(
        path=str(target_dir),
        branch=branch,
        agent_id=agent_id,
        purpose=purpose,
        status="active",
        notes=[],
        last_seen_head=head,
        branch_role=TASK_ROLE,
        base_branch=resolved_base_branch,
        created_at=now_iso(),
    ).to_dict()

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    try:
        mutate_ledger(ctx, update)
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created)
        raise

    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "path": str(target_dir),
        "branch": branch,
        "head": head,
        "agent_id": agent_id,
        "purpose": purpose,
        "branch_role": TASK_ROLE,
        "base_branch": resolved_base_branch,
        "branch_created": not existing_branch,
    }


def build_dispatch_payload(
    ctx: RepoContext,
    *,
    agent: str | None,
    agent_id: str | None,
    branch: str,
    purpose: str,
    base_branch: str | None = None,
    instructions: list[str] | None = None,
    instruction_profile: str | None = None,
    instruction_mode: str = "copy",
) -> dict[str, Any]:
    registry = load_agent_registry(ctx)
    agent_name = agent or registry["default_agent"]
    agents_by_name = registry["agents_by_name"]
    if agent_name not in agents_by_name:
        raise GitWarpError(f"unknown agent '{agent_name}'; available agents: {', '.join(sorted(agents_by_name))}")
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, branch)
    resolved_base_branch = infer_base_branch(ctx, worktrees, base_branch)
    instruction_plan = build_instruction_plan(
        ctx,
        raw_instructions=instructions,
        profile_name=instruction_profile,
        mode=instruction_mode,
    )

    selected_agent = agents_by_name[agent_name]
    resolved_agent_id = agent_id or build_agent_id(agent_name, branch)
    target_dir, existing_branch, head = create_worktree(ctx, branch, start_point=resolved_base_branch)
    branch_created = not existing_branch
    created_at = now_iso()
    dossier = dossier_paths(ctx, branch, target_dir)
    cleanup_dossier = None if Path(dossier["dossier_path"]).exists() else dossier["dossier_path"]
    try:
        mounted_instructions = mount_instruction_files(target_dir, instruction_plan)
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created, dossier_path=cleanup_dossier)
        raise
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
        branch_role=TASK_ROLE,
        base_branch=resolved_base_branch,
        created_at=created_at,
        updated_at=created_at,
        dispatch=dispatch_meta,
        instructions=mounted_instructions or None,
        instruction_profile=instruction_profile,
        instruction_mode=instruction_mode,
    ).to_dict()
    try:
        create_dossier_files(
            dossier,
            agent_id=resolved_agent_id,
            branch=branch,
            worktree_path=str(target_dir),
            purpose=purpose,
            status="dispatched",
            created_at=created_at,
            branch_role=TASK_ROLE,
            base_branch=resolved_base_branch,
            instructions=mounted_instructions,
            instruction_profile=instruction_profile,
        )
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created, dossier_path=cleanup_dossier)
        raise

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    try:
        mutate_ledger(ctx, update)
    except Exception:
        cleanup_created_worktree(ctx, target_dir, branch=branch, branch_created=branch_created, dossier_path=cleanup_dossier)
        raise
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
        "branch_role": TASK_ROLE,
        "base_branch": resolved_base_branch,
        "branch_created": not existing_branch,
        "last_seen_head": head,
        "launch_command": launch_command,
        "launch_preview": launch_preview,
        "instructions": mounted_instructions,
        "instruction_profile": instruction_profile,
        "instruction_mode": instruction_mode,
        **dossier,
    }
