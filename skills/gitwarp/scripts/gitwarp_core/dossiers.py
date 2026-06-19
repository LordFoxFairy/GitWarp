from __future__ import annotations

from pathlib import Path
from typing import Any

from .foundation import (
    GitWarpError,
    LESSONS_FILENAME,
    PROGRESS_FILENAME,
    RepoContext,
    TASK_FILENAME,
    now_iso,
    sanitize_name,
    short_hash,
)
from .ledger import mutate_ledger


def dossier_paths(ctx: RepoContext, branch: str, worktree_path: Path) -> dict[str, str]:
    workspace_id = f"{sanitize_name(branch)}-{short_hash(str(worktree_path))}"
    dossier_path = (ctx.dossier_root / workspace_id).resolve()
    return {
        "dossier_path": str(dossier_path),
        "task_md": str(dossier_path / TASK_FILENAME),
        "progress_md": str(dossier_path / PROGRESS_FILENAME),
        "lessons_md": str(dossier_path / LESSONS_FILENAME),
    }


def create_dossier_files(
    paths: dict[str, str],
    *,
    agent_id: str | None,
    branch: str | None,
    worktree_path: str,
    purpose: str | None,
    status: str | None,
    created_at: str,
) -> None:
    dossier_path = Path(paths["dossier_path"])
    dossier_path.mkdir(parents=True, exist_ok=True)
    task = Path(paths["task_md"])
    progress = Path(paths["progress_md"])
    lessons = Path(paths["lessons_md"])

    if not task.exists():
        task.write_text(
            "\n".join(
                [
                    "# Task",
                    "",
                    f"- Agent: {agent_id or 'unassigned'}",
                    f"- Branch: {branch or 'detached'}",
                    f"- Worktree: {worktree_path}",
                    f"- Purpose: {purpose or 'unspecified'}",
                    f"- Status: {status or 'active'}",
                    f"- Created: {created_at}",
                    "",
                    "## Scope",
                    "",
                    purpose or "Unspecified task.",
                    "",
                    "## Success Criteria",
                    "",
                    "- [ ] Define concrete verification before finishing",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    if not progress.exists():
        progress.write_text(
            "\n".join(
                [
                    "# Progress",
                    "",
                    f"## {created_at}",
                    "",
                    f"- Status: {status or 'active'}",
                    "- Note: Workspace created.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    if not lessons.exists():
        lessons.write_text(
            "\n".join(
                [
                    "# Lessons",
                    "",
                    "## Notes For Future Agents",
                    "",
                    "- Add findings, pitfalls, and decisions that should survive handoff.",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def append_markdown_event(path: str, timestamp: str, lines: list[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {timestamp}\n\n")
        for line in lines:
            handle.write(f"{line}\n")
        handle.write("\n")


def ledger_entry_for_target(ledger: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    target_path = target["path"]
    entry = next((item for item in ledger["entries"] if item.get("path") == target_path), None)
    if entry is not None:
        return entry
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
    return entry


def ensure_dossier_for_entry(ctx: RepoContext, entry: dict[str, Any], target: dict[str, Any]) -> dict[str, str]:
    branch = entry.get("branch") or target.get("branch") or "detached"
    paths = {
        "dossier_path": entry.get("dossier_path"),
        "task_md": entry.get("task_md"),
        "progress_md": entry.get("progress_md"),
        "lessons_md": entry.get("lessons_md"),
    }
    if not all(paths.values()):
        paths = dossier_paths(ctx, branch, Path(target["path"]))
        entry.update(paths)
    concrete_paths = {key: str(value) for key, value in paths.items()}
    create_dossier_files(
        concrete_paths,
        agent_id=entry.get("agent_id"),
        branch=branch,
        worktree_path=target["path"],
        purpose=entry.get("purpose"),
        status=entry.get("status") or "active",
        created_at=entry.get("created_at") or now_iso(),
    )
    return concrete_paths


def record_handoff(
    ctx: RepoContext,
    target: dict[str, Any],
    *,
    status: str,
    progress: str,
    lesson: str | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if target.get("is_main"):
        raise GitWarpError("refusing to hand off the main repository checkout")

    result: dict[str, Any] = {}

    def update(ledger: dict[str, Any]) -> None:
        entry = ledger_entry_for_target(ledger, target)
        paths = ensure_dossier_for_entry(ctx, entry, target)
        timestamp = now_iso()
        append_markdown_event(
            paths["progress_md"],
            timestamp,
            [f"- Status: {status}", f"- Note: {progress}"],
        )
        if lesson:
            append_markdown_event(paths["lessons_md"], timestamp, [f"- {lesson}"])

        entry["status"] = status
        entry["updated_at"] = timestamp
        entry["latest_progress"] = progress
        if lesson:
            entry["latest_lesson"] = lesson
        entry.setdefault("notes", [])
        entry["notes"].append({"note": progress, "created_at": timestamp, "kind": "progress"})
        result["entry"] = dict(entry)
        result["paths"] = dict(paths)

    mutate_ledger(ctx, update)
    return result["entry"], result["paths"]


def read_snippet(path: str | None, *, max_chars: int = 900) -> str | None:
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    text = target.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 4].rstrip() + "\n..."
