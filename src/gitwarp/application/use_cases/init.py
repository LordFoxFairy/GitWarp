from __future__ import annotations

from typing import Any

from ...application.diagnostics import append_gitwarp_ignore_rule, init_recommendations, preflight_init
from ...infrastructure.ledger import default_ledger, load_project_registry, project_registry_path, register_project, write_ledger
from ...infrastructure.runtime import RepoContext
from ...infrastructure.worktrees import parse_worktrees, sync_ledger


def build_init_payload(ctx: RepoContext, *, write_gitignore: bool) -> dict[str, Any]:
    preflight = preflight_init(ctx, write_gitignore=write_gitignore)
    created = {
        "ledger_dir": not ctx.ledger_dir.exists(),
        "ledger": not ctx.ledger_path.exists(),
        "worktree_root": not ctx.worktree_root.exists(),
        "dossier_root": not ctx.dossier_root.exists(),
    }
    updated = {
        "ledger": bool(preflight["ledger_needs_write"]),
        "ignore_rule": bool(preflight["ignore_rule_needed"]),
    }

    ctx.ledger_dir.mkdir(parents=True, exist_ok=True)
    ctx.worktree_root.mkdir(parents=True, exist_ok=True)
    ctx.dossier_root.mkdir(parents=True, exist_ok=True)

    if created["ledger"]:
        write_ledger(ctx, default_ledger(ctx))
    elif updated["ledger"]:
        write_ledger(ctx, preflight["ledger"], touch_updated_at=False)

    if updated["ignore_rule"]:
        append_gitwarp_ignore_rule(preflight["ignore_target"])

    ledger_before_sync = ctx.ledger_path.read_bytes()
    sync_ledger(ctx, parse_worktrees(ctx))
    updated["ledger"] = updated["ledger"] or ledger_before_sync != ctx.ledger_path.read_bytes()

    registry = load_project_registry(project_registry_path())
    existing = any(item.get("repo_root") == str(ctx.repo_root) for item in registry["projects"])
    registry_path = register_project(ctx.repo_root, name=ctx.repo_root.name)

    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "worktree_root": str(ctx.worktree_root),
        "dossier_root": str(ctx.dossier_root),
        "created": created,
        "updated": updated,
        "ignore_target": str(preflight["ignore_target"]),
        "registry_path": str(registry_path),
        "registered": {
            "name": ctx.repo_root.name,
            "added_new": not existing,
            "refreshed": existing,
            "position": 0,
        },
        "recommended_next": init_recommendations(ctx),
    }


def build_add_payload(ctx: RepoContext, *, write_gitignore: bool) -> dict[str, Any]:
    return build_init_payload(ctx, write_gitignore=write_gitignore)
