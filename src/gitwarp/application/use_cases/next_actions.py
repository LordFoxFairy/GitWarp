from __future__ import annotations

import shlex
from typing import Any

from ...infrastructure.runtime import GitWarpError, RepoContext
from ...infrastructure.worktrees import worktree_dirty
from .matrix import build_matrix_payload


ACTION_RULES: dict[str, dict[str, Any]] = {
    "merged_task": {
        "priority": 10,
        "severity": "warning",
        "safety": "confirm_destructive",
        "title": "Collapse merged task worktree",
        "description": "This task branch is merged into its parent base. Collapse only after confirming the sandbox is no longer needed.",
    },
    "merged_ref": {
        "priority": 20,
        "severity": "warning",
        "safety": "confirm_destructive",
        "title": "Prune merged local branch ref",
        "description": "This local branch ref is merged and has no live worktree or GitWarp ledger row. Delete it only after explicit confirmation.",
    },
    "untracked_worktree": {
        "priority": 30,
        "severity": "warning",
        "safety": "review",
        "title": "Adopt untracked worktree",
        "description": "Git reports a live worktree that GitWarp is not tracking. Adopt it or ask the user whether it should stay unmanaged.",
    },
    "dirty_worktree": {
        "priority": 15,
        "severity": "warning",
        "safety": "review",
        "title": "Review dirty merged task",
        "description": "This task branch is merged, but its worktree still has uncommitted or untracked changes. Inspect changes before any collapse.",
    },
    "stale_ledger": {
        "priority": 40,
        "severity": "warning",
        "safety": "review",
        "title": "Repair stale ledger metadata",
        "description": "A GitWarp ledger row points at a worktree Git no longer reports. Run init only when the user wants metadata repair.",
    },
    "orphan_dossier": {
        "priority": 50,
        "severity": "warning",
        "safety": "review",
        "title": "Review orphan dossier",
        "description": "A dossier directory is not referenced by the ledger. Treat it as legacy metadata until the user confirms cleanup.",
    },
}


def build_next_actions_payload(ctx: RepoContext, *, base_branch: str | None = None) -> dict[str, Any]:
    try:
        matrix = build_matrix_payload(ctx, base_branch=base_branch)
    except GitWarpError as exc:
        actions = [build_ledger_review_action(ctx, str(exc))]
        return {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "default_branch": None,
            "merge_base": base_branch,
            "statusline": "GITWARP[unknown]",
            "summary": summarize_actions(actions),
            "actions": actions,
        }
    actions = sorted(
        (
            action
            for row in matrix["rows"]
            if (action := build_action_from_matrix_row(row)) is not None
        ),
        key=lambda action: (int(action["priority"]), str(action["id"])),
    )
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "default_branch": matrix["default_branch"],
        "merge_base": matrix["merge_base"],
        "statusline": matrix["statusline"],
        "summary": summarize_actions(actions),
        "actions": actions,
    }


def build_ledger_review_action(ctx: RepoContext, error: str) -> dict[str, Any]:
    return {
        "id": "ledger_schema:ledger",
        "priority": 5,
        "severity": "error",
        "safety": "review",
        "category": "ledger_schema",
        "title": "Review invalid GitWarp ledger",
        "description": f"GitWarp could not read the ledger: {error}",
        "command": "gitwarp doctor",
        "branch": None,
        "path": str(ctx.ledger_path),
        "role": None,
        "source": {
            "kind": "ledger",
            "row_id": "ledger",
            "recommended_action": "review_metadata",
            "legacy_state": "legacy",
        },
    }


def build_action_from_matrix_row(row: dict[str, Any]) -> dict[str, Any] | None:
    category = str(row.get("category") or "")
    path = row.get("path")
    if category == "merged_task" and isinstance(path, str) and worktree_dirty(path):
        category = "dirty_worktree"
        row = {**row, "category": category, "next_command": f"gitwarp reconcile --cwd {shlex.quote(path)}"}
    rule = ACTION_RULES.get(category)
    command = row.get("next_command")
    if rule is None or not isinstance(command, str) or not command:
        return None
    branch = row.get("branch")
    row_id = str(row.get("row_id") or category)
    return {
        "id": f"{category}:{row_id}",
        "priority": rule["priority"],
        "severity": rule["severity"],
        "safety": rule["safety"],
        "category": category,
        "title": rule["title"],
        "description": rule["description"],
        "command": command,
        "branch": branch if isinstance(branch, str) else None,
        "path": row.get("path") if isinstance(row.get("path"), str) else None,
        "role": row.get("role") if isinstance(row.get("role"), str) else None,
        "source": {
            "kind": "matrix",
            "row_id": row_id,
            "recommended_action": row.get("recommended_action"),
            "legacy_state": row.get("legacy_state"),
        },
    }


def summarize_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    by_safety: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for action in actions:
        by_safety[str(action["safety"])] = by_safety.get(str(action["safety"]), 0) + 1
        by_severity[str(action["severity"])] = by_severity.get(str(action["severity"]), 0) + 1
    return {
        "total": len(actions),
        "by_safety": dict(sorted(by_safety.items())),
        "by_severity": dict(sorted(by_severity.items())),
    }
