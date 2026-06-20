from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ...infrastructure.dossiers import record_handoff
from ...infrastructure.ledger import mutate_ledger
from ...infrastructure.runtime import GitWarpError, RepoContext, resolve_path, run_git
from ...infrastructure.worktrees import parse_worktrees, select_collapse_target, select_live_target, sync_ledger


def worktree_status_summary(path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    lines = run_git(Path(path), "status", "--porcelain").splitlines()
    untracked = [line[3:] for line in lines if line.startswith("?? ")]
    return (
        {"count": len(lines), "sample": lines[:20]},
        {"count": len(untracked), "sample": untracked[:20]},
    )


def resolve_purgeable_dossier_path(ctx: RepoContext, raw_path: str) -> Path:
    dossier_root = ctx.dossier_root.resolve()
    dossier_path = Path(raw_path).expanduser().resolve()
    try:
        dossier_path.relative_to(dossier_root)
    except ValueError as exc:
        raise GitWarpError(f"refusing to purge dossier outside GitWarp dossier root: {dossier_path}") from exc
    if dossier_path == dossier_root:
        raise GitWarpError("refusing to purge the dossier root")
    return dossier_path


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
    purge_dossier: bool = False,
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
    if purge_dossier and paths.get("dossier_path"):
        shutil.rmtree(resolve_purgeable_dossier_path(ctx, paths["dossier_path"]), ignore_errors=True)
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
        "purged_dossier": bool(purge_dossier),
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
