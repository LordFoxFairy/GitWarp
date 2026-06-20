from __future__ import annotations

from pathlib import Path
from typing import Any

from .runtime import (
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
    branch_role: str | None = None,
    base_branch: str | None = None,
    instructions: list[dict[str, Any]] | None = None,
    instruction_profile: str | None = None,
) -> None:
    dossier_path = Path(paths["dossier_path"])
    dossier_path.mkdir(parents=True, exist_ok=True)
    task = Path(paths["task_md"])
    progress = Path(paths["progress_md"])
    lessons = Path(paths["lessons_md"])

    if not task.exists():
        instruction_lines: list[str] = []
        if instructions:
            instruction_lines.extend(["", "## Mounted Instructions", ""])
            if instruction_profile:
                instruction_lines.extend([f"- Profile: {instruction_profile}"])
            instruction_lines.extend(f"- `{item['target']}` from `{item['source']}` ({item['mode']})" for item in instructions)
        task.write_text(
            "\n".join(
                [
                    "# Task",
                    "",
                    f"- Agent: {agent_id or 'unassigned'}",
                    f"- Branch: {branch or 'detached'}",
                    f"- Role: {branch_role or 'task'}",
                    f"- Parent Base: {base_branch or 'none'}",
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
                    *instruction_lines,
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
        "last_seen_head": target.get("head"),
        "created_at": now_iso(),
    }
    ledger["entries"].append(entry)
    return entry


def validate_dossier_paths(ctx: RepoContext, paths: dict[str, str]) -> None:
    dossier_root = ctx.dossier_root.resolve()
    for key, raw_path in paths.items():
        target = Path(raw_path).expanduser().resolve()
        try:
            target.relative_to(dossier_root)
        except ValueError as exc:
            raise GitWarpError(f"refusing dossier path outside GitWarp dossier root: {key}={target}") from exc
    if Path(paths["dossier_path"]).expanduser().resolve() == dossier_root:
        raise GitWarpError("refusing to use the dossier root as a worktree dossier")


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
    validate_dossier_paths(ctx, concrete_paths)
    create_dossier_files(
        concrete_paths,
        agent_id=entry.get("agent_id"),
        branch=branch,
        worktree_path=target["path"],
        purpose=entry.get("purpose"),
        status=entry.get("status") or "active",
        created_at=entry.get("created_at") or now_iso(),
        branch_role=entry.get("branch_role") if isinstance(entry.get("branch_role"), str) else None,
        base_branch=entry.get("base_branch") if isinstance(entry.get("base_branch"), str) else None,
        instructions=entry.get("instructions") if isinstance(entry.get("instructions"), list) else None,
        instruction_profile=entry.get("instruction_profile") if isinstance(entry.get("instruction_profile"), str) else None,
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
        entry["last_seen_head"] = target.get("head")
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
