from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import GitWarpError


def path_contains(parent: str, child: Path) -> bool:
    parent_path = Path(parent).resolve()
    return child == parent_path or parent_path in child.parents


def build_head_drift(last_seen_head: str | None, current_head: str | None) -> dict[str, Any] | None:
    if not last_seen_head or not current_head or last_seen_head == current_head:
        return None
    return {
        "drifted": True,
        "last_seen_head": last_seen_head,
        "current_head": current_head,
    }


def find_worktree_for_cwd(cwd: Path, worktrees: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [item for item in worktrees if path_contains(str(item["path"]), cwd)]
    if not matches:
        return None
    return max(matches, key=lambda item: len(str(item["path"])))


def ensure_branch_available(worktrees: list[dict[str, Any]], branch: str) -> None:
    for item in worktrees:
        if item.get("branch") == branch:
            raise GitWarpError(f"branch collision: '{branch}' is already bound to {item['path']}")


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


def guarded_worktree_root_contains(worktree_root: Path, path: str) -> bool:
    return path_contains(str(worktree_root), Path(path).resolve())
