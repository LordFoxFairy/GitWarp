from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dossiers import read_snippet
from .foundation import GitWarpError, RepoContext
from .ledger import discover_repo
from .worktrees import find_worktree_for_cwd, parse_worktrees, sync_ledger


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_seconds(item: dict[str, Any], now: datetime) -> int | None:
    timestamp = parse_timestamp(item.get("updated_at") or item.get("created_at"))
    if timestamp is None:
        return None
    return max(0, int((now - timestamp).total_seconds()))


def board_row(item: dict[str, Any], *, verbose: bool = False) -> dict[str, Any]:
    row = {
        "path": item["path"],
        "branch": item.get("branch"),
        "agent_id": item.get("agent_id"),
        "purpose": item.get("purpose"),
        "status": item.get("status"),
        "is_main": item.get("is_main", False),
        "dossier_path": item.get("dossier_path"),
        "task_md": item.get("task_md"),
        "progress_md": item.get("progress_md"),
        "lessons_md": item.get("lessons_md"),
        "latest_progress": item.get("latest_progress"),
        "latest_lesson": item.get("latest_lesson"),
        "last_seen_head": item.get("last_seen_head"),
    }
    if item.get("head_drift") is not None:
        row["head_drift"] = item["head_drift"]
    if verbose:
        row.update(
            {
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "snippets": {
                    "task": read_snippet(item.get("task_md")),
                    "progress": read_snippet(item.get("progress_md")),
                    "lessons": read_snippet(item.get("lessons_md")),
                },
            }
        )
    return row


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


def statusline_banner(target: dict[str, Any] | None) -> str:
    if target is None:
        return "GITWARP[outside]"
    if target.get("is_main"):
        return "GITWARP[main-repo]"
    agent_id = target.get("agent_id") or "unassigned"
    branch = target.get("branch") or "detached"
    return f"GITWARP[{agent_id}@{branch}]"


def enter_recommendations(ctx: RepoContext | None, cwd: Path, target: dict[str, Any] | None) -> list[str]:
    if ctx is None:
        return ["Open a Git repository or pass --cwd /absolute/path/to/repo."]
    if target is None:
        return [f"Move inside a live worktree for {ctx.repo_root} or run gitwarp scan --cwd \"{ctx.repo_root}\"."]
    if target.get("is_main"):
        return [
            f"Run gitwarp start --cwd \"{ctx.repo_root}\" --agent-id <agent-id> --branch <branch> --purpose \"<purpose>\" before isolated work.",
            f"Run gitwarp board --cwd \"{ctx.repo_root}\" to inspect active dimensions.",
        ]
    return [
        "Read task.md, progress.md, and lessons.md before editing.",
        f"Record milestones with gitwarp handoff --cwd \"{cwd}\" --status <status> --progress \"<summary>\".",
        f"Finish with gitwarp finish --cwd \"{cwd}\" --status pushed --progress \"verified and pushed\" [--collapse].",
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
    recommendations = payload.get("recommended_next") or []
    if recommendations:
        lines.append("Next:")
        lines.extend(f"- {item}" for item in recommendations)
    return "\n".join(lines)
