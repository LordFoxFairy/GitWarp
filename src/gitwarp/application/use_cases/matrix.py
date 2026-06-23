from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.branch_roles import BASE_ROLE, TASK_ROLE
from ...infrastructure.runtime import LESSONS_FILENAME, PROGRESS_FILENAME, RepoContext, TASK_FILENAME
from ...infrastructure.worktrees import find_worktree_for_cwd, parse_worktrees, sync_ledger
from ..reconcile import build_reconcile_payload
from ..views import statusline_banner
from .branches import build_branches_payload


def build_matrix_payload(ctx: RepoContext, *, base_branch: str | None = None) -> dict[str, Any]:
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    branches = build_branches_payload(ctx, base_branch=base_branch)
    reconcile = build_reconcile_payload(ctx)
    live_by_path = {item["path"]: item for item in worktrees}
    live_by_branch = {item["branch"]: item for item in worktrees if item.get("branch")}
    indexed_ledger = list(enumerate(ledger["entries"]))
    branch_rows = {str(row["name"]): row for row in branches["branches"]}
    matched_ledger_indexes: set[int] = set()

    rows: list[dict[str, Any]] = []
    seen_live_paths: set[str] = set()
    for branch_name in sorted(branch_rows):
        live = live_by_branch.get(branch_name)
        ledger_index, ledger_entry = find_ledger_for_live(indexed_ledger, live, matched_ledger_indexes)
        if ledger_index is not None:
            matched_ledger_indexes.add(ledger_index)
        if live is not None:
            seen_live_paths.add(str(live["path"]))
        rows.append(
            build_matrix_row(
                row_id=f"branch:{branch_name}",
                branch_name=branch_name,
                branch_ref=branch_rows[branch_name],
                live=live,
                ledger_entry=ledger_entry,
                live_by_path=live_by_path,
            )
        )

    for live in sorted(worktrees, key=lambda item: item["path"]):
        if live["path"] in seen_live_paths:
            continue
        live_branch = live.get("branch")
        ledger_index, ledger_entry = find_ledger_for_live(indexed_ledger, live, matched_ledger_indexes)
        if ledger_index is not None:
            matched_ledger_indexes.add(ledger_index)
        rows.append(
            build_matrix_row(
                row_id=f"worktree:{live['path']}",
                branch_name=live_branch or f"detached:{live['path']}",
                branch_ref=None,
                live=live,
                ledger_entry=ledger_entry,
                live_by_path=live_by_path,
            )
        )

    for index, entry in sorted(indexed_ledger, key=lambda item: str(item[1].get("branch") or item[1].get("path") or "")):
        if index in matched_ledger_indexes:
            continue
        branch_name = entry.get("branch")
        row_key = branch_name if isinstance(branch_name, str) else f"ledger:{entry.get('path')}"
        rows.append(
            build_matrix_row(
                row_id=f"ledger:{index}:{row_key}",
                branch_name=str(row_key),
                branch_ref=None,
                live=None,
                ledger_entry=entry,
                live_by_path=live_by_path,
            )
        )

    referenced_dossiers = referenced_dossier_dirs(ledger)
    dossier_dirs = list_dossier_dirs(ctx)
    for dossier_path in dossier_dirs:
        if dossier_path in referenced_dossiers:
            continue
        rows.append(build_orphan_dossier_row(dossier_path))

    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "default_branch": branches["default_branch"],
        "merge_base": branches["merge_base"],
        "statusline": statusline_banner(find_worktree_for_cwd(ctx.cwd, worktrees)),
        "sources": {
            "git_branch_refs": len(branches["branches"]),
            "git_worktrees": len(worktrees),
            "ledger_entries": len(ledger["entries"]),
            "dossier_dirs": len(dossier_dirs),
            "reconcile_findings": reconcile["summary"]["total"],
        },
        "summary": summarize_matrix(rows),
        "rows": rows,
        "reconcile": reconcile,
    }


def build_matrix_row(
    *,
    row_id: str,
    branch_name: str,
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
    live_by_path: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    branch_role = resolve_role(branch_ref, live, ledger_entry)
    ledger_live = ledger_entry_matches_live(ledger_entry, live_by_path)
    dossier_state = resolve_dossier_state(ledger_entry, ledger_live=ledger_live)
    category = categorize_matrix_row(
        branch_ref=branch_ref,
        live=live,
        ledger_entry=ledger_entry,
        ledger_live=ledger_live,
        branch_role=branch_role,
    )
    return {
        "row_id": row_id,
        "branch": branch_name,
        "category": category,
        "legacy_state": legacy_state(category),
        "recommended_action": recommended_action(category, branch_ref, live),
        "next_command": next_command(category, branch_name, branch_ref, live, ledger_entry),
        "path": live.get("path") if live is not None else ledger_entry.get("path") if ledger_entry else None,
        "head": live.get("head") if live is not None else branch_ref.get("head") if branch_ref else ledger_entry.get("last_seen_head") if ledger_entry else None,
        "role": branch_role,
        "managed_state": resolve_managed_state(branch_ref, live, ledger_entry),
        "commit_state": resolve_commit_state(category, branch_ref, live, ledger_entry),
        "cleanup_policy": resolve_cleanup_policy(category, branch_ref, live, ledger_entry),
        "classification_basis": resolve_classification_basis(branch_ref, live, ledger_entry),
        "agent_id": ledger_entry.get("agent_id") if ledger_entry else None,
        "status": ledger_entry.get("status") if ledger_entry else None,
        "purpose": ledger_entry.get("purpose") if ledger_entry else None,
        "git": {
            "branch_ref": branch_ref is not None,
            "worktree": live is not None,
            "merged_to_base": branch_ref.get("merged_to_base") if branch_ref is not None else None,
            "prunable": branch_ref.get("deletable") if branch_ref is not None else False,
        },
        "gitwarp": {
            "ledger": ledger_entry is not None,
            "ledger_live": ledger_live,
            "dossier_state": dossier_state,
            "dossier_path": ledger_entry.get("dossier_path") if ledger_entry else None,
            "task_md": ledger_entry.get("task_md") if ledger_entry else None,
            "progress_md": ledger_entry.get("progress_md") if ledger_entry else None,
            "lessons_md": ledger_entry.get("lessons_md") if ledger_entry else None,
        },
    }


def resolve_managed_state(
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
) -> str:
    if branch_ref is not None and isinstance(branch_ref.get("managed_state"), str):
        return str(branch_ref["managed_state"])
    if ledger_entry is not None:
        return "gitwarp_managed"
    if live is not None:
        return "unmanaged_worktree"
    return "unmanaged"


def resolve_commit_state(
    category: str,
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
) -> str:
    if branch_ref is not None and isinstance(branch_ref.get("commit_state"), str):
        return str(branch_ref["commit_state"])
    if category in {"main", "base"}:
        return "base"
    merged = branch_ref.get("merged_to_base") if branch_ref is not None else None
    if merged:
        return "merged"
    if live is not None or ledger_entry is not None:
        return "active"
    return "unmerged"


def resolve_cleanup_policy(
    category: str,
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
) -> str:
    if branch_ref is not None and isinstance(branch_ref.get("cleanup_policy"), str):
        return str(branch_ref["cleanup_policy"])
    if category in {"main", "base"}:
        return "preserve_base"
    if category == "merged_task":
        return "finish_collapse_merged"
    if category == "merged_ref":
        return "user_confirmed_ref_prune"
    if live is not None or ledger_entry is not None:
        return "preserve_managed"
    if category == "orphan_ref":
        return "review_unmerged_ref"
    return "review"


def resolve_classification_basis(
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    if branch_ref is not None and isinstance(branch_ref.get("classification_basis"), dict):
        return dict(branch_ref["classification_basis"])
    return {
        "base_branch": branch_ref.get("base_branch") if branch_ref is not None else ledger_entry.get("base_branch") if ledger_entry else None,
        "head": live.get("head") if live is not None else branch_ref.get("head") if branch_ref is not None else ledger_entry.get("last_seen_head") if ledger_entry else None,
        "merged_to_base": branch_ref.get("merged_to_base") if branch_ref is not None else None,
        "managed_by_gitwarp": ledger_entry is not None,
        "has_worktree": live is not None,
    }


def resolve_role(
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
) -> str | None:
    for source in (branch_ref, live, ledger_entry):
        if source is not None and isinstance(source.get("branch_role"), str):
            return str(source["branch_role"])
    return None


def ledger_entry_matches_live(entry: dict[str, Any] | None, live_by_path: dict[str, dict[str, Any]]) -> bool:
    if entry is None or not isinstance(entry.get("path"), str):
        return False
    live = live_by_path.get(entry["path"])
    return live is not None and live.get("branch") == entry.get("branch")


def resolve_dossier_state(entry: dict[str, Any] | None, *, ledger_live: bool) -> str:
    if entry is None or not isinstance(entry.get("dossier_path"), str):
        return "none"
    dossier_path = Path(entry["dossier_path"])
    required = [entry.get("task_md"), entry.get("progress_md"), entry.get("lessons_md")]
    if not dossier_path.exists() or any(not isinstance(path, str) or not Path(path).exists() for path in required):
        return "missing"
    if not ledger_live:
        return "stale"
    return "ok"


def categorize_matrix_row(
    *,
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
    ledger_live: bool,
    branch_role: str | None,
) -> str:
    if branch_ref is not None and branch_ref.get("is_default"):
        return "main"
    if ledger_entry is not None and not ledger_live:
        return "stale_ledger"
    if live is not None and ledger_entry is None and not live.get("is_main"):
        return "untracked_worktree"
    if (
        live is not None
        and ledger_entry is not None
        and branch_role == TASK_ROLE
        and branch_ref is not None
        and branch_ref.get("merged_to_base")
    ):
        return "merged_task"
    if branch_role == BASE_ROLE:
        return "base"
    if live is not None and ledger_entry is not None and branch_role == TASK_ROLE:
        return "active_task"
    if branch_ref is not None and branch_ref.get("deletable"):
        return "merged_ref"
    if branch_ref is not None and branch_ref.get("category") == "orphan":
        return "orphan_ref"
    return "inspect"


def recommended_action(category: str, branch_ref: dict[str, Any] | None, live: dict[str, Any] | None) -> str:
    if category == "main":
        return "use_main"
    if category == "base":
        return "switch" if live is not None else "create_base_worktree"
    if category == "active_task":
        if branch_ref is not None and branch_ref.get("merged_to_base") and not branch_ref.get("deletable"):
            return "finish_collapse_merged"
        return "switch"
    if category == "merged_task":
        return "finish_collapse_merged"
    if category == "untracked_worktree":
        return "adopt"
    if category == "stale_ledger":
        return "repair_metadata"
    if category == "orphan_dossier":
        return "repair_metadata"
    if category == "merged_ref":
        return "prune_branch"
    return "inspect"


def legacy_state(category: str) -> str:
    if category in {"merged_ref", "merged_task"}:
        return "deprecated"
    if category in {"orphan_ref", "stale_ledger", "orphan_dossier"}:
        return "legacy"
    return "current"


def next_command(
    category: str,
    branch_name: str,
    branch_ref: dict[str, Any] | None,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
) -> str | None:
    if category == "base" and live is None:
        return f'gitwarp create --role base --branch {branch_name} --purpose "<purpose>"'
    if category in {"base", "active_task"} and branch_ref is not None:
        return f"gitwarp switch --branch {branch_name}"
    if category == "merged_task":
        return (
            f'gitwarp finish --branch {branch_name} --status merged '
            '--progress "Merged into parent base" --collapse-merged'
        )
    if category == "untracked_worktree" and live is not None:
        role = BASE_ROLE if branch_ref is not None and branch_ref.get("is_default") else TASK_ROLE
        return f'gitwarp adopt --path {live["path"]} --role {role} --purpose "<purpose>"'
    if category == "merged_ref":
        return f"gitwarp prune-branch --branch {branch_name}"
    if category in {"stale_ledger", "orphan_dossier"}:
        return "gitwarp init"
    if category == "main":
        return "gitwarp statusline"
    if ledger_entry is not None and isinstance(ledger_entry.get("path"), str):
        return f"gitwarp reconcile --cwd {ledger_entry['path']}"
    return None


def summarize_matrix(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "rows": len(rows),
        "active_gitwarp_tasks": sum(1 for row in rows if row["category"] == "active_task"),
        "untracked_worktrees": sum(1 for row in rows if row["category"] == "untracked_worktree"),
        "stale_ledger_entries": sum(1 for row in rows if row["category"] == "stale_ledger"),
        "merged_gitwarp_tasks": sum(1 for row in rows if row["category"] == "merged_task"),
        "prunable_branch_refs": sum(1 for row in rows if row["category"] == "merged_ref"),
        "orphan_branch_refs": sum(1 for row in rows if row["category"] == "orphan_ref"),
        "orphan_dossiers": sum(1 for row in rows if row["category"] == "orphan_dossier"),
    }


def find_ledger_for_live(
    indexed_ledger: list[tuple[int, dict[str, Any]]],
    live: dict[str, Any] | None,
    matched_indexes: set[int],
) -> tuple[int | None, dict[str, Any] | None]:
    if live is None:
        return None, None
    for index, entry in indexed_ledger:
        if index in matched_indexes:
            continue
        if entry.get("path") == live.get("path") and entry.get("branch") == live.get("branch"):
            return index, entry
    return None, None


def list_dossier_dirs(ctx: RepoContext) -> list[Path]:
    if not ctx.dossier_root.is_dir():
        return []
    return sorted(
        (item.resolve() for item in ctx.dossier_root.iterdir() if item.is_dir() and not item.is_symlink()),
        key=str,
    )


def referenced_dossier_dirs(ledger: dict[str, Any]) -> set[Path]:
    referenced: set[Path] = set()
    for entry in ledger.get("entries", []):
        for key in ("dossier_path", "task_md", "progress_md", "lessons_md"):
            raw_path = entry.get(key)
            if not isinstance(raw_path, str) or not raw_path:
                continue
            path = Path(raw_path).expanduser().resolve()
            referenced.add(path if key == "dossier_path" else path.parent)
    return referenced


def build_orphan_dossier_row(dossier_path: Path) -> dict[str, Any]:
    task_md = dossier_path / TASK_FILENAME
    progress_md = dossier_path / PROGRESS_FILENAME
    lessons_md = dossier_path / LESSONS_FILENAME
    return {
        "row_id": f"dossier:{dossier_path}",
        "branch": dossier_path.name,
        "category": "orphan_dossier",
        "legacy_state": "legacy",
        "recommended_action": "repair_metadata",
        "next_command": "gitwarp init",
        "path": None,
        "head": None,
        "role": None,
        "agent_id": None,
        "status": None,
        "purpose": None,
        "git": {
            "branch_ref": False,
            "worktree": False,
            "merged_to_base": None,
            "prunable": False,
        },
        "gitwarp": {
            "ledger": False,
            "ledger_live": False,
            "dossier_state": "orphan",
            "dossier_path": str(dossier_path),
            "task_md": str(task_md) if task_md.exists() else None,
            "progress_md": str(progress_md) if progress_md.exists() else None,
            "lessons_md": str(lessons_md) if lessons_md.exists() else None,
        },
    }
