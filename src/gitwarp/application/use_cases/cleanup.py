from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ...domain.branch_roles import TASK_ROLE
from ...infrastructure.dossiers import record_handoff
from ...infrastructure.ledger import mutate_ledger
from ...infrastructure.runtime import GitWarpError, RepoContext, resolve_path, run_git
from ...infrastructure.worktrees import branch_merged_into_base, parse_worktrees, prune_empty_worktree_parents, select_collapse_target, select_live_target, sync_ledger


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
    if dossier_path.exists() and not dossier_path.is_dir():
        raise GitWarpError(f"refusing to purge non-directory dossier path: {dossier_path}")
    return dossier_path


def resolve_target_dossier_path(ctx: RepoContext, ledger: dict[str, Any], target_path: str) -> Path | None:
    entry = next((item for item in ledger["entries"] if item.get("path") == target_path), {})
    raw_path = entry.get("dossier_path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    return resolve_purgeable_dossier_path(ctx, raw_path)


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


def collapse_worktree(ctx: RepoContext, *, path: str | None, branch: str | None) -> tuple[str, str | None, str | None, bool]:
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target_path, removed_branch = select_collapse_target(
        worktrees=worktrees,
        ledger=ledger,
        path_arg=path,
        branch_arg=branch,
        repo_root=ctx.repo_root,
    )
    dossier_path = resolve_target_dossier_path(ctx, ledger, target_path)
    run_git(ctx.repo_root, "worktree", "remove", "--force", target_path)
    run_git(ctx.repo_root, "worktree", "prune", "--expire", "now")
    target_dir = Path(target_path)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    prune_empty_worktree_parents(ctx, target_dir)
    if dossier_path is not None:
        shutil.rmtree(dossier_path, ignore_errors=True)

    def update(locked_ledger: dict[str, Any]) -> None:
        locked_ledger["entries"] = [item for item in locked_ledger["entries"] if item.get("path") != target_path]

    mutate_ledger(ctx, update)
    return target_path, removed_branch, str(dossier_path) if dossier_path is not None else None, dossier_path is not None


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
    collapse_merged: bool = False,
    purge_dossier: bool = False,
) -> dict[str, Any]:
    resolved_cwd = resolve_path(cwd or path)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(worktrees=worktrees, cwd=resolved_cwd, path_arg=path, branch_arg=branch)
    if collapse_merged:
        if target.get("branch_role") != "task":
            raise GitWarpError("finish --collapse-merged only applies to task worktrees")
        dirty_summary, _ = worktree_status_summary(target["path"])
        if dirty_summary["count"]:
            raise GitWarpError(
                "finish --collapse-merged requires a clean task worktree; "
                f"dirty_count={dirty_summary['count']}"
            )
        if not branch_merged_into_base(ctx, target.get("branch"), target.get("base_branch")):
            raise GitWarpError(
                "finish --collapse-merged requires the task branch HEAD to be merged into its base_branch"
            )
    entry, paths = record_handoff(ctx, target, status=status, progress=progress, lesson=lesson)

    collapsed = False
    removed_branch = None
    purged_dossier = False
    if collapse or collapse_merged:
        _, removed_branch, _, purged_dossier = collapse_worktree(ctx, path=target["path"], branch=None)
        collapsed = True
    if purge_dossier and paths.get("dossier_path"):
        shutil.rmtree(resolve_purgeable_dossier_path(ctx, paths["dossier_path"]), ignore_errors=True)
        purged_dossier = True
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
        "branch_role": entry.get("branch_role"),
        "base_branch": entry.get("base_branch"),
        "latest_progress": entry.get("latest_progress"),
        "latest_lesson": entry.get("latest_lesson"),
        "collapsed": collapsed,
        "purged_dossier": purged_dossier,
        **paths,
    }


def build_collapse_payload(ctx: RepoContext, *, path: str | None, branch: str | None) -> dict[str, Any]:
    target_path, removed_branch, dossier_path, purged_dossier = collapse_worktree(ctx, path=path, branch=branch)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "removed_path": target_path,
        "removed_branch": removed_branch,
        "dossier_path": dossier_path,
        "purged_dossier": purged_dossier,
    }


def build_remove_payload(ctx: RepoContext, *, path: str | None, branch: str | None) -> dict[str, Any]:
    target_path, removed_branch, dossier_path, purged_dossier = collapse_worktree(ctx, path=path, branch=branch)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "removed_path": target_path,
        "removed_branch": removed_branch,
        "dossier_path": dossier_path,
        "purged_dossier": purged_dossier,
    }


def build_sweep_payload(ctx: RepoContext, *, merged_tasks: bool, dry_run: bool) -> dict[str, Any]:
    if not merged_tasks:
        raise GitWarpError("sweep requires an explicit target selector such as --merged-tasks")

    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []

    for worktree in sorted(worktrees, key=lambda item: str(item.get("path") or "")):
        row = build_sweep_row(ctx, worktree)
        if row["decision"] == "remove":
            candidates.append(row)
        elif row["decision"] == "skip" and row["reason"] in {"dirty_worktree", "unmerged_task"}:
            skipped.append(row)

    if not dry_run:
        for candidate in candidates:
            removed_path, removed_branch, dossier_path, purged_dossier = collapse_worktree(
                ctx,
                path=str(candidate["path"]),
                branch=None,
            )
            removed.append(
                {
                    **candidate,
                    "removed_path": removed_path,
                    "removed_branch": removed_branch,
                    "dossier_path": dossier_path,
                    "purged_dossier": purged_dossier,
                }
            )

    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "dry_run": dry_run,
        "mode": "merged_tasks",
        "summary": {
            "candidates": len(candidates) + len(skipped),
            "removable": len(candidates),
            "removed": len(removed),
            "skipped": len(skipped),
        },
        "removable": candidates,
        "removed": removed,
        "skipped": skipped,
        "preserved": {
            "branch_refs": True,
            "base_worktrees": True,
            "unmanaged_worktrees": True,
        },
    }


def build_sweep_row(ctx: RepoContext, worktree: dict[str, Any]) -> dict[str, Any]:
    branch = worktree.get("branch")
    path = worktree.get("path")
    branch_role = worktree.get("branch_role")
    base_branch = worktree.get("base_branch")
    base = {
        "path": path,
        "branch": branch,
        "branch_role": branch_role,
        "base_branch": base_branch,
        "agent_id": worktree.get("agent_id"),
        "purpose": worktree.get("purpose"),
        "dossier_path": worktree.get("dossier_path"),
    }
    if worktree.get("is_main"):
        return {**base, "decision": "preserve", "reason": "main_checkout"}
    if worktree.get("agent_id") is None:
        return {**base, "decision": "preserve", "reason": "unmanaged_worktree"}
    if branch_role != TASK_ROLE:
        return {**base, "decision": "preserve", "reason": "base_worktree"}
    if not isinstance(path, str) or not path:
        return {**base, "decision": "skip", "reason": "missing_worktree_path"}
    checked_branch = branch if isinstance(branch, str) else None
    checked_base = base_branch if isinstance(base_branch, str) else None
    if not branch_merged_into_base(ctx, checked_branch, checked_base):
        return {**base, "decision": "skip", "reason": "unmerged_task"}

    dirty_summary, untracked_summary = worktree_status_summary(str(path))
    if dirty_summary["count"]:
        return {
            **base,
            "decision": "skip",
            "reason": "dirty_worktree",
            "dirty_summary": dirty_summary,
            "untracked_summary": untracked_summary,
        }
    return {
        **base,
        "decision": "remove",
        "reason": "merged_clean_task",
        "dirty_summary": dirty_summary,
        "untracked_summary": untracked_summary,
    }
