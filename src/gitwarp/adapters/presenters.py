from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..infrastructure.dossiers import read_snippet
from ..infrastructure.ledger import discover_repo
from ..infrastructure.runtime import GitWarpError, RepoContext
from ..infrastructure.worktrees import find_worktree_for_cwd, parse_worktrees, sync_ledger
from ..application.views import age_seconds, board_row, statusline_banner


def filter_board_rows(
    rows: list[dict[str, Any]],
    *,
    status: str | None,
    stale_hours: float | None,
    now: datetime,
) -> list[dict[str, Any]]:
    filtered = rows
    if status is not None:
        filtered = [row for row in filtered if row.get("status") == status]
    if stale_hours is not None:
        cutoff = max(0, int(stale_hours * 3600))
        stale_rows = []
        for row in filtered:
            age = age_seconds(row, now)
            if age is None or age < cutoff:
                continue
            row["age_seconds"] = age
            row["stale"] = True
            stale_rows.append(row)
        filtered = stale_rows
    return filtered


def print_board_table(rows: list[dict[str, Any]]) -> None:
    headers = ["branch", "agent", "status", "purpose", "progress"]
    print(" | ".join(headers))
    print(" | ".join("---" for _ in headers))
    for row in rows:
        print(
            " | ".join(
                [
                    str(row.get("branch") or ""),
                    str(row.get("agent_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("purpose") or ""),
                    str(row.get("latest_progress") or ""),
                ]
            )
        )


def enter_recommendations(ctx: RepoContext | None, cwd: Path, target: dict[str, Any] | None) -> list[str]:
    if ctx is None:
        return ["Open a Git repository or pass --cwd /absolute/path/to/repo."]
    if target is None:
        return [f"Move inside a live worktree for {ctx.repo_root} or run gitwarp scan."]
    if target.get("is_main"):
        return [
            'Run gitwarp create --branch <branch> --purpose "<purpose>" before isolated work.',
            "Run gitwarp switch --branch <branch> --format shell to print a cd command for an existing sandbox.",
            "Run gitwarp board to inspect active sandboxes.",
        ]
    return [
        "Read task.md, progress.md, and lessons.md before editing.",
        'Record milestones with gitwarp handoff --status <status> --progress "<summary>".',
        "Leave this worktree intact after verification unless the user explicitly asks for push, merge, remove, or collapse.",
        'Use gitwarp finish --status <status> --progress "<summary>" --collapse only when this sandbox should be destroyed.',
    ]


def build_enter_payload(cwd: Path) -> dict[str, Any]:
    try:
        ctx = discover_repo(cwd)
    except GitWarpError:
        return {
            "ok": True,
            "location": "outside",
            "cwd": str(cwd),
            "statusline": "GITWARP[outside]",
            "recommended_next": enter_recommendations(None, cwd, None),
        }

    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    target = find_worktree_for_cwd(cwd, worktrees)
    if target is None:
        return {
            "ok": True,
            "location": "outside-worktree",
            "repo_root": str(ctx.repo_root),
            "checkout_root": str(ctx.checkout_root),
            "cwd": str(cwd),
            "ledger_path": str(ctx.ledger_path),
            "statusline": "GITWARP[outside]",
            "recommended_next": enter_recommendations(ctx, cwd, None),
        }

    location = "main" if target.get("is_main") else "worktree"
    snippets: dict[str, str | None] = {}
    if location == "worktree":
        snippets = {
            "task": read_snippet(target.get("task_md")),
            "progress": read_snippet(target.get("progress_md")),
            "lessons": read_snippet(target.get("lessons_md")),
        }

    payload: dict[str, Any] = {
        "ok": True,
        "location": location,
        "repo_root": str(ctx.repo_root),
        "checkout_root": str(ctx.checkout_root),
        "cwd": str(cwd),
        "ledger_path": str(ctx.ledger_path),
        "statusline": statusline_banner(target),
        "worktree": target,
        "recommended_next": enter_recommendations(ctx, cwd, target),
    }
    if snippets:
        payload["snippets"] = snippets
    return payload


def format_enter_prompt(payload: dict[str, Any]) -> str:
    lines = [
        f"GitWarp Context: {payload['statusline']}",
        f"Location: {payload['location']}",
        f"CWD: {payload['cwd']}",
    ]
    worktree = payload.get("worktree")
    if isinstance(worktree, dict):
        lines.extend(
            [
                f"Branch: {worktree.get('branch') or 'detached'}",
                f"Agent: {worktree.get('agent_id') or 'unassigned'}",
                f"Purpose: {worktree.get('purpose') or 'unspecified'}",
                f"Status: {worktree.get('status') or 'unknown'}",
            ]
        )
        if not worktree.get("is_main"):
            lines.extend(
                [
                    f"Task: {worktree.get('task_md') or 'missing'}",
                    f"Progress: {worktree.get('progress_md') or 'missing'}",
                    f"Lessons: {worktree.get('lessons_md') or 'missing'}",
                    f"Latest progress: {worktree.get('latest_progress') or 'none'}",
                    f"Latest lesson: {worktree.get('latest_lesson') or 'none'}",
                ]
            )
            instructions = worktree.get("instructions")
            if isinstance(instructions, list) and instructions:
                lines.append("Instructions:")
                for item in instructions:
                    if isinstance(item, dict):
                        lines.append(
                            f"- {item.get('target') or 'unknown'} ({item.get('mode') or 'copy'}; {item.get('status') or 'mounted'})"
                        )
    recommendations = payload.get("recommended_next") or []
    if recommendations:
        lines.append("Next:")
        lines.extend(f"- {item}" for item in recommendations)
    return "\n".join(lines)
