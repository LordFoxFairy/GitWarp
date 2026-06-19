from __future__ import annotations

from typing import Any

from ...infrastructure.dossiers import record_handoff
from ...infrastructure.runtime import RepoContext, resolve_path
from ...infrastructure.worktrees import parse_worktrees, select_live_target, sync_ledger


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
