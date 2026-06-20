from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..infrastructure.dossiers import read_snippet


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
        "branch_role": item.get("branch_role"),
        "base_branch": item.get("base_branch"),
        "dossier_path": item.get("dossier_path"),
        "task_md": item.get("task_md"),
        "progress_md": item.get("progress_md"),
        "lessons_md": item.get("lessons_md"),
        "latest_progress": item.get("latest_progress"),
        "latest_lesson": item.get("latest_lesson"),
        "last_seen_head": item.get("last_seen_head"),
        "instructions": item.get("instructions"),
        "instruction_profile": item.get("instruction_profile"),
        "instruction_mode": item.get("instruction_mode"),
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


def statusline_banner(target: dict[str, Any] | None) -> str:
    if target is None:
        return "GITWARP[outside]"
    if target.get("is_main"):
        return "GITWARP[main-repo]"
    agent_id = target.get("agent_id") or "unassigned"
    branch = target.get("branch") or "detached"
    return f"GITWARP[{agent_id}@{branch}]"
