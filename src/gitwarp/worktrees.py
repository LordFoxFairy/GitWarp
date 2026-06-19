from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .foundation import GitWarpError, RepoContext, path_contains, run_git, sanitize_name
from .ledger import load_ledger, mutate_ledger


def parse_worktrees(ctx: RepoContext) -> list[dict[str, Any]]:
    output = run_git(ctx.repo_root, "worktree", "list", "--porcelain")
    blocks = [block for block in output.split("\n\n") if block.strip()]
    worktrees: list[dict[str, Any]] = []
    for block in blocks:
        item: dict[str, Any] = {"branch": None, "detached": False}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                item["path"] = str(Path(value).resolve())
            elif key == "HEAD":
                item["head"] = value
            elif key == "branch":
                item["branch"] = value.removeprefix("refs/heads/")
            elif key == "detached":
                item["detached"] = True
        if "path" not in item or "head" not in item:
            continue
        item["is_main"] = Path(item["path"]) == ctx.repo_root
        worktrees.append(item)
    return worktrees


def build_head_drift(last_seen_head: str | None, current_head: str | None) -> dict[str, Any] | None:
    if not last_seen_head or not current_head or last_seen_head == current_head:
        return None
    return {
        "drifted": True,
        "last_seen_head": last_seen_head,
        "current_head": current_head,
    }


def sync_ledger(
    ctx: RepoContext,
    live_worktrees: list[dict[str, Any]],
    *,
    persist: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if persist:

        def prune(locked_ledger: dict[str, Any]) -> None:
            live_paths = {item["path"] for item in live_worktrees}
            locked_ledger["entries"] = [entry for entry in locked_ledger["entries"] if entry.get("path") in live_paths]

        mutate_ledger(ctx, prune)
    ledger = load_ledger(ctx)

    metadata_by_path = {entry["path"]: entry for entry in ledger["entries"]}
    enriched: list[dict[str, Any]] = []
    for item in live_worktrees:
        meta = metadata_by_path.get(item["path"], {})
        last_seen_head = meta.get("last_seen_head")
        enriched_item = {
            "path": item["path"],
            "head": item["head"],
            "branch": item.get("branch"),
            "detached": item.get("detached", False),
            "is_main": item.get("is_main", False),
            "agent_id": meta.get("agent_id"),
            "purpose": meta.get("purpose"),
            "status": meta.get("status"),
            "notes": meta.get("notes", []),
            "dossier_path": meta.get("dossier_path"),
            "task_md": meta.get("task_md"),
            "progress_md": meta.get("progress_md"),
            "lessons_md": meta.get("lessons_md"),
            "latest_progress": meta.get("latest_progress"),
            "latest_lesson": meta.get("latest_lesson"),
            "last_seen_head": last_seen_head,
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
        }
        head_drift = build_head_drift(last_seen_head, item.get("head"))
        if head_drift is not None:
            enriched_item["head_drift"] = head_drift
        enriched.append(enriched_item)
    return ledger, enriched


def find_worktree_for_cwd(cwd: Path, worktrees: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [item for item in worktrees if path_contains(str(item["path"]), cwd)]
    if not matches:
        return None
    return max(matches, key=lambda item: len(str(item["path"])))


def ensure_branch_available(worktrees: list[dict[str, Any]], branch: str) -> None:
    for item in worktrees:
        if item.get("branch") == branch:
            raise GitWarpError(f"branch collision: '{branch}' is already bound to {item['path']}")


def branch_exists(ctx: RepoContext, branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(ctx.repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def create_worktree(ctx: RepoContext, branch: str) -> tuple[Path, bool, str]:
    target_dir = (ctx.worktree_root / sanitize_name(branch)).resolve()
    if target_dir.exists():
        raise GitWarpError(f"target path already exists: {target_dir}")

    ctx.worktree_root.mkdir(parents=True, exist_ok=True)
    existing_branch = branch_exists(ctx, branch)
    if existing_branch:
        run_git(ctx.repo_root, "worktree", "add", str(target_dir), branch)
    else:
        run_git(ctx.repo_root, "worktree", "add", "-b", branch, str(target_dir), "HEAD")

    head = run_git(target_dir, "rev-parse", "HEAD")
    return target_dir, existing_branch, head


def select_collapse_target(
    worktrees: list[dict[str, Any]],
    ledger: dict[str, Any],
    path_arg: str | None,
    branch_arg: str | None,
    repo_root: Path,
) -> tuple[str, str | None]:
    if path_arg:
        target_path = str(Path(path_arg).expanduser().resolve())
    elif branch_arg:
        matches = [item for item in worktrees if item.get("branch") == branch_arg]
        if not matches:
            matches = [item for item in ledger["entries"] if item.get("branch") == branch_arg]
        if not matches:
            raise GitWarpError(f"no live or tracked worktree found for branch '{branch_arg}'")
        target_path = matches[0]["path"]
    else:
        raise GitWarpError("collapse requires --path or --branch")

    if Path(target_path).resolve() == repo_root.resolve():
        raise GitWarpError("refusing to collapse the main repository checkout")

    branch = None
    for item in worktrees:
        if item["path"] == target_path:
            branch = item.get("branch")
            break
    if branch is None:
        for entry in ledger["entries"]:
            if entry.get("path") == target_path:
                branch = entry.get("branch")
                break
    return target_path, branch


def select_live_target(
    worktrees: list[dict[str, Any]],
    cwd: Path,
    path_arg: str | None,
    branch_arg: str | None,
) -> dict[str, Any]:
    if path_arg:
        target_path = str(Path(path_arg).expanduser().resolve())
        for item in worktrees:
            if item["path"] == target_path:
                return item
        raise GitWarpError(f"no live worktree found at path '{target_path}'")
    if branch_arg:
        matches = [item for item in worktrees if item.get("branch") == branch_arg]
        if not matches:
            raise GitWarpError(f"no live worktree found for branch '{branch_arg}'")
        return matches[0]
    target = find_worktree_for_cwd(cwd, worktrees)
    if target is None:
        raise GitWarpError(f"current directory is not inside a live worktree: {cwd}")
    return target


def worktree_dirty(path: str) -> bool:
    return bool(run_git(Path(path), "status", "--porcelain"))


def branch_merged_into_main(ctx: RepoContext, branch: str | None) -> bool:
    if not branch or branch == "main":
        return False
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "main"],
        cwd=str(ctx.repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def guarded_worktree_root_contains(ctx: RepoContext, path: str) -> bool:
    return path_contains(str(ctx.worktree_root), Path(path).resolve())
