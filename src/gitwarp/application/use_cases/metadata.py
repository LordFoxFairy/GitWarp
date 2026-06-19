from __future__ import annotations

from typing import Any

from ...domain.model import WorkspaceRecord
from ...infrastructure.dossiers import ensure_dossier_for_entry
from ...infrastructure.ledger import mutate_ledger
from ...infrastructure.runtime import GitWarpError, RepoContext, now_iso, resolve_path
from ...infrastructure.worktrees import guarded_worktree_root_contains, parse_worktrees, select_live_target, sync_ledger


def build_adopt_payload(
    ctx: RepoContext,
    *,
    cwd: str,
    path: str | None,
    agent_id: str,
    purpose: str,
) -> dict[str, Any]:
    resolved_cwd = resolve_path(cwd or path)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=resolved_cwd,
        path_arg=path,
        branch_arg=None,
    )
    if target.get("is_main"):
        raise GitWarpError("refusing to adopt the main repository checkout")
    if target.get("detached") or not target.get("branch"):
        raise GitWarpError("refusing to adopt a detached worktree")

    target_path = target["path"]
    target_branch = target.get("branch")
    outside_guarded_root = not guarded_worktree_root_contains(ctx, target_path)
    result: dict[str, Any] = {}

    def update(ledger: dict[str, Any]) -> None:
        same_path = next((item for item in ledger["entries"] if item.get("path") == target_path), None)
        same_branch = next(
            (item for item in ledger["entries"] if item.get("branch") == target_branch and item.get("path") != target_path),
            None,
        )
        if same_branch is not None:
            raise GitWarpError(f"branch '{target_branch}' is already tracked at {same_branch.get('path')}")
        same_agent = next(
            (item for item in ledger["entries"] if item.get("agent_id") == agent_id and item.get("path") != target_path),
            None,
        )
        if same_agent is not None:
            raise GitWarpError(f"agent '{agent_id}' is already assigned to {same_agent.get('path')}")

        entry = same_path
        if entry is None:
            entry = WorkspaceRecord(path=target_path, branch=target_branch, notes=[], created_at=now_iso()).to_dict()
            ledger["entries"].append(entry)
        entry["path"] = target_path
        entry["branch"] = target_branch
        entry["agent_id"] = agent_id
        entry["purpose"] = purpose
        entry["status"] = "adopted"
        entry["updated_at"] = now_iso()
        entry["latest_progress"] = "Worktree adopted."
        entry["last_seen_head"] = target.get("head")
        paths = ensure_dossier_for_entry(ctx, entry, target)
        result["entry"] = dict(entry)
        result["paths"] = dict(paths)

    mutate_ledger(ctx, update)
    entry = result["entry"]
    paths = result["paths"]
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "path": target_path,
        "branch": target_branch,
        "head": target.get("head"),
        "agent_id": entry.get("agent_id"),
        "purpose": entry.get("purpose"),
        "status": entry.get("status"),
        "outside_guarded_root": outside_guarded_root,
        **paths,
    }


def build_annotate_payload(
    ctx: RepoContext,
    *,
    cwd: str,
    path: str | None,
    branch: str | None,
    status: str | None,
    note: str,
) -> dict[str, Any]:
    resolved_cwd = resolve_path(cwd or path)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=resolved_cwd,
        path_arg=path,
        branch_arg=branch,
    )
    if target.get("is_main"):
        raise GitWarpError("refusing to annotate the main repository checkout")

    target_path = target["path"]
    result: dict[str, Any] = {}

    def update(ledger: dict[str, Any]) -> None:
        entry = next((item for item in ledger["entries"] if item.get("path") == target_path), None)
        if entry is None:
            entry = {
                "path": target_path,
                "branch": target.get("branch"),
                "agent_id": None,
                "purpose": None,
                "status": None,
                "notes": [],
                "created_at": now_iso(),
            }
            ledger["entries"].append(entry)

        timestamp = now_iso()
        if status:
            entry["status"] = status
        entry.setdefault("notes", [])
        entry["notes"].append({"note": note, "created_at": timestamp})
        entry["updated_at"] = timestamp
        result["entry"] = dict(entry)

    mutate_ledger(ctx, update)
    entry = result["entry"]
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "path": target_path,
        "branch": target.get("branch"),
        "agent_id": entry.get("agent_id"),
        "purpose": entry.get("purpose"),
        "status": entry.get("status"),
        "notes_count": len(entry["notes"]),
        "latest_note": entry["notes"][-1],
    }
