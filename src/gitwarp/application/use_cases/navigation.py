from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from ...infrastructure.runtime import GitWarpError, RepoContext, resolve_path
from ...infrastructure.worktrees import parse_worktrees, select_live_target, sync_ledger
from ..views import statusline_banner


def shell_cd_command(path: str) -> str:
    return f"cd {shlex.quote(str(Path(path).resolve()))}"


def build_switch_payload(
    ctx: RepoContext,
    *,
    cwd: str | None,
    path: str | None,
    branch: str | None,
    main: bool,
) -> dict[str, Any]:
    if main and (path or branch):
        raise GitWarpError("switch --main cannot be combined with --path or --branch")
    if not main and not path and not branch:
        raise GitWarpError("switch requires --branch, --path, or --main")

    resolved_cwd = resolve_path(cwd or path or str(ctx.cwd))
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)

    if main:
        target = next((item for item in worktrees if item.get("is_main")), None)
        if target is None:
            raise GitWarpError("main repository checkout is not present in git worktree list")
    else:
        target = select_live_target(worktrees=worktrees, cwd=resolved_cwd, path_arg=path, branch_arg=branch)

    target_path = str(Path(target["path"]).resolve())
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "path": target_path,
        "branch": target.get("branch"),
        "agent_id": target.get("agent_id"),
        "purpose": target.get("purpose"),
        "status": target.get("status"),
        "is_main": target.get("is_main", False),
        "branch_role": target.get("branch_role"),
        "base_branch": target.get("base_branch"),
        "statusline": statusline_banner(target),
        "shell_command": shell_cd_command(target_path),
        "task_md": target.get("task_md"),
        "progress_md": target.get("progress_md"),
        "lessons_md": target.get("lessons_md"),
    }
