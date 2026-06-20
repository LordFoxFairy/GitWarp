from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..domain.branch_roles import enrich_role_metadata
from ..domain import policies
from .ledger import load_ledger, mutate_ledger
from .runtime import (
    GitWarpError,
    LESSONS_FILENAME,
    PROGRESS_FILENAME,
    RepoContext,
    TASK_FILENAME,
    run_git,
    sanitize_name,
)


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
    return policies.build_head_drift(last_seen_head, current_head)


def sync_ledger(
    ctx: RepoContext,
    live_worktrees: list[dict[str, Any]],
    *,
    persist: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if persist:

        def prune(locked_ledger: dict[str, Any]) -> None:
            live_paths = {item["path"] for item in live_worktrees}
            stale_entries = [entry for entry in locked_ledger["entries"] if entry.get("path") not in live_paths]
            for entry in stale_entries:
                purge_orphan_dossier(ctx, entry)
            locked_ledger["entries"] = [entry for entry in locked_ledger["entries"] if entry.get("path") in live_paths]
            purge_unreferenced_dossiers(ctx, locked_ledger)

        mutate_ledger(ctx, prune)
    ledger = load_ledger(ctx)

    metadata_by_path = {entry["path"]: entry for entry in ledger["entries"]}
    enriched: list[dict[str, Any]] = []
    for item in live_worktrees:
        meta = metadata_by_path.get(item["path"], {})
        last_seen_head = meta.get("last_seen_head")
        branch_role, base_branch = enrich_role_metadata(item, meta)
        enriched_item = {
            "path": item["path"],
            "head": item["head"],
            "branch": item.get("branch"),
            "detached": item.get("detached", False),
            "is_main": item.get("is_main", False),
            "branch_role": branch_role,
            "base_branch": base_branch,
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
            "instructions": meta.get("instructions"),
            "instruction_profile": meta.get("instruction_profile"),
            "instruction_mode": meta.get("instruction_mode"),
        }
        head_drift = build_head_drift(last_seen_head, item.get("head"))
        if head_drift is not None:
            enriched_item["head_drift"] = head_drift
        enriched.append(enriched_item)
    return ledger, enriched


def purge_orphan_dossier(ctx: RepoContext, entry: dict[str, Any]) -> None:
    raw_path = entry.get("dossier_path")
    if not isinstance(raw_path, str) or not raw_path:
        return
    dossier_path = resolve_dossier_child(ctx, raw_path)
    if dossier_path is None:
        return
    if dossier_path.is_dir():
        shutil.rmtree(dossier_path, ignore_errors=True)


def resolve_dossier_child(ctx: RepoContext, raw_path: str) -> Path | None:
    dossier_path = Path(raw_path).expanduser().resolve()
    dossier_root = ctx.dossier_root.resolve()
    try:
        dossier_path.relative_to(dossier_root)
    except ValueError:
        return None
    if dossier_path == dossier_root:
        return None
    return dossier_path


def referenced_dossier_paths(ctx: RepoContext, ledger: dict[str, Any]) -> set[Path]:
    referenced: set[Path] = set()
    for entry in ledger.get("entries", []):
        for key in ("dossier_path", "task_md", "progress_md", "lessons_md"):
            raw_path = entry.get(key)
            if not isinstance(raw_path, str) or not raw_path:
                continue
            resolved = resolve_dossier_child(ctx, raw_path)
            if resolved is None:
                continue
            referenced.add(resolved if key == "dossier_path" else resolved.parent)
    return referenced


def looks_like_gitwarp_dossier(path: Path) -> bool:
    return any((path / filename).exists() for filename in (TASK_FILENAME, PROGRESS_FILENAME, LESSONS_FILENAME))


def purge_unreferenced_dossiers(ctx: RepoContext, ledger: dict[str, Any]) -> list[str]:
    dossier_root = ctx.dossier_root.resolve()
    if not dossier_root.is_dir():
        return []
    referenced = referenced_dossier_paths(ctx, ledger)
    removed: list[str] = []
    for child in dossier_root.iterdir():
        if child.is_symlink() or not child.is_dir():
            continue
        child_path = child.resolve()
        if child_path in referenced:
            continue
        try:
            child_path.relative_to(dossier_root)
        except ValueError:
            continue
        if not looks_like_gitwarp_dossier(child_path):
            continue
        shutil.rmtree(child_path, ignore_errors=True)
        removed.append(str(child_path))
    return removed


def find_worktree_for_cwd(cwd: Path, worktrees: list[dict[str, Any]]) -> dict[str, Any] | None:
    return policies.find_worktree_for_cwd(cwd, worktrees)


def ensure_branch_available(worktrees: list[dict[str, Any]], branch: str) -> None:
    policies.ensure_branch_available(worktrees, branch)


def branch_exists(ctx: RepoContext, branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(ctx.repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def create_worktree(ctx: RepoContext, branch: str, *, start_point: str = "HEAD") -> tuple[Path, bool, str]:
    target_dir = (ctx.worktree_root / sanitize_name(branch)).resolve()
    if target_dir.exists():
        raise GitWarpError(f"target path already exists: {target_dir}")

    ctx.worktree_root.mkdir(parents=True, exist_ok=True)
    existing_branch = branch_exists(ctx, branch)
    if existing_branch:
        run_git(ctx.repo_root, "worktree", "add", str(target_dir), branch)
    else:
        run_git(ctx.repo_root, "worktree", "add", "-b", branch, str(target_dir), start_point)

    head = run_git(target_dir, "rev-parse", "HEAD")
    return target_dir, existing_branch, head


def select_collapse_target(
    worktrees: list[dict[str, Any]],
    ledger: dict[str, Any],
    path_arg: str | None,
    branch_arg: str | None,
    repo_root: Path,
) -> tuple[str, str | None]:
    return policies.select_collapse_target(worktrees, ledger, path_arg, branch_arg, repo_root)


def select_live_target(
    worktrees: list[dict[str, Any]],
    cwd: Path,
    path_arg: str | None,
    branch_arg: str | None,
) -> dict[str, Any]:
    return policies.select_live_target(worktrees, cwd, path_arg, branch_arg)


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


def branch_merged_into_base(ctx: RepoContext, branch: str | None, base_branch: str | None) -> bool:
    if not branch or not base_branch or branch == base_branch:
        return False
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, base_branch],
        cwd=str(ctx.repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def guarded_worktree_root_contains(ctx: RepoContext, path: str) -> bool:
    return policies.guarded_worktree_root_contains(ctx.worktree_root, path)
