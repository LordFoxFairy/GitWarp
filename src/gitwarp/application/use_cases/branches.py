from __future__ import annotations

from typing import Any

from ...domain.branch_roles import BASE_ROLE, TASK_ROLE
from ...domain.errors import GitWarpError
from ...infrastructure.runtime import RepoContext, run_git
from ...infrastructure.worktrees import branch_exists, branch_merged_into_base, parse_worktrees, sync_ledger


def resolve_default_branch(ctx: RepoContext) -> str:
    try:
        remote_head = run_git(ctx.repo_root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    except GitWarpError:
        remote_head = ""
    if remote_head.startswith("origin/"):
        candidate = remote_head.removeprefix("origin/")
        if branch_exists(ctx, candidate):
            return candidate
    if branch_exists(ctx, "main"):
        return "main"
    current = run_git(ctx.repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    if current and current != "HEAD":
        return current
    branches = list_local_branch_refs(ctx)
    if branches:
        return str(branches[0]["name"])
    raise GitWarpError("repository has no local branches")


def list_local_branch_refs(ctx: RepoContext) -> list[dict[str, Any]]:
    output = run_git(
        ctx.repo_root,
        "for-each-ref",
        "--sort=refname",
        "--format=%(refname:short)%09%(objectname)%09%(upstream:short)",
        "refs/heads",
    )
    branches: list[dict[str, Any]] = []
    for line in output.splitlines():
        name, head, upstream = (line.split("\t") + ["", ""])[:3]
        if not name:
            continue
        branches.append({"name": name, "head": head, "upstream": upstream or None})
    return branches


def branch_delete_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if row["is_default"]:
        blockers.append("default branch")
    elif row["branch_role"] == BASE_ROLE:
        blockers.append("base branch")
    if row["has_worktree"]:
        blockers.append("checked out in a worktree")
    if row["in_ledger"]:
        blockers.append("tracked in GitWarp ledger")
    if row["base_branch"] and not row["merged_to_base"]:
        blockers.append(f"not merged into {row['base_branch']}")
    return blockers


def build_branch_row(
    ctx: RepoContext,
    branch: dict[str, Any],
    *,
    default_branch: str,
    merge_base: str,
    live_by_branch: dict[str, dict[str, Any]],
    ledger_by_branch: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    name = str(branch["name"])
    live = live_by_branch.get(name)
    ledger_entries = ledger_by_branch.get(name, [])
    ledger_entry = ledger_entries[0] if ledger_entries else {}
    is_default = name == default_branch
    has_worktree = live is not None
    in_ledger = bool(ledger_entries)
    branch_role = resolve_branch_role(is_default=is_default, live=live, ledger_entry=ledger_entry)
    base_branch = resolve_base_branch(
        merge_base=merge_base,
        branch_role=branch_role,
        live=live,
        ledger_entry=ledger_entry,
    )
    merged_to_base = False if is_default else branch_merged_into_base(ctx, name, base_branch)
    row = {
        "name": name,
        "head": branch["head"],
        "upstream": branch.get("upstream"),
        "is_default": is_default,
        "base_branch": base_branch,
        "branch_role": branch_role,
        "has_worktree": has_worktree,
        "worktree_path": live.get("path") if live is not None else None,
        "in_ledger": in_ledger,
        "agent_id": ledger_entry.get("agent_id"),
        "status": ledger_entry.get("status"),
        "merged_to_base": merged_to_base,
    }
    blockers = branch_delete_blockers(row)
    row["deletable"] = not blockers
    row["delete_blockers"] = blockers
    row["category"] = categorize_branch(row)
    return row


def resolve_branch_role(
    *,
    is_default: bool,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any],
) -> str:
    if is_default:
        return BASE_ROLE
    if live is not None and isinstance(live.get("branch_role"), str):
        return str(live["branch_role"])
    if isinstance(ledger_entry.get("branch_role"), str):
        return str(ledger_entry["branch_role"])
    return TASK_ROLE


def resolve_base_branch(
    *,
    merge_base: str,
    branch_role: str,
    live: dict[str, Any] | None,
    ledger_entry: dict[str, Any],
) -> str | None:
    if branch_role == BASE_ROLE:
        return None
    if live is not None and isinstance(live.get("base_branch"), str):
        return str(live["base_branch"])
    if isinstance(ledger_entry.get("base_branch"), str):
        return str(ledger_entry["base_branch"])
    return merge_base


def categorize_branch(row: dict[str, Any]) -> str:
    if row["is_default"] or row["branch_role"] == BASE_ROLE:
        return "base"
    if row["has_worktree"] or row["in_ledger"]:
        return "active"
    if row["merged_to_base"]:
        return "merged"
    return "orphan"


def build_branches_payload(ctx: RepoContext, *, base_branch: str | None = None) -> dict[str, Any]:
    default_branch = resolve_default_branch(ctx)
    merge_base = base_branch or default_branch
    if base_branch and not branch_exists(ctx, base_branch):
        raise GitWarpError(f"base branch does not exist: {base_branch}")
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    live_by_branch = {item["branch"]: item for item in worktrees if item.get("branch")}
    ledger_by_branch: dict[str, list[dict[str, Any]]] = {}
    for entry in ledger["entries"]:
        branch = entry.get("branch")
        if isinstance(branch, str):
            ledger_by_branch.setdefault(branch, []).append(entry)
    rows = []
    for branch in list_local_branch_refs(ctx):
        row = build_branch_row(
            ctx,
            branch,
            default_branch=default_branch,
            merge_base=merge_base,
            live_by_branch=live_by_branch,
            ledger_by_branch=ledger_by_branch,
        )
        rows.append(row)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "default_branch": default_branch,
        "merge_base": merge_base,
        "branches": rows,
        "summary": summarize_branches(rows),
    }


def summarize_branches(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    for row in rows:
        category = str(row["category"])
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "total": len(rows),
        "deletable": sum(1 for row in rows if row["deletable"]),
        "by_category": by_category,
    }


def build_prune_branch_payload(ctx: RepoContext, *, branch: str, base_branch: str | None = None) -> dict[str, Any]:
    payload = build_branches_payload(ctx, base_branch=base_branch)
    row = next((item for item in payload["branches"] if item["name"] == branch), None)
    if row is None:
        raise GitWarpError(f"local branch does not exist: {branch}")
    if not row["deletable"]:
        blockers = ", ".join(row["delete_blockers"])
        raise GitWarpError(f"refusing to delete branch '{branch}': {blockers}")
    delete_branch_ref(ctx, branch, str(row["head"]))
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "branch": branch,
        "base_branch": row["base_branch"],
        "deleted": True,
        "deleted_ref": row,
    }


def delete_branch_ref(ctx: RepoContext, branch: str, expected_head: str) -> None:
    current_head = run_git(ctx.repo_root, "rev-parse", "--verify", branch)
    if current_head != expected_head:
        raise GitWarpError(f"branch '{branch}' changed while pruning; refresh branches before retrying")
    try:
        # -D is needed when the selected merge base is not the current HEAD.
        # Git still refuses to delete a branch checked out in any worktree.
        run_git(ctx.repo_root, "branch", "-D", branch)
    except GitWarpError as exc:
        raise GitWarpError(f"refusing to delete branch '{branch}': {exc}") from exc
