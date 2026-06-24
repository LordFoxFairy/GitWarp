from __future__ import annotations

from typing import Any

from ...infrastructure.ledger import load_project_registry, project_registry_path, register_project
from ...infrastructure.runtime import RepoContext
from .init import build_init_payload


def build_reload_payload(ctx: RepoContext) -> dict[str, Any]:
    init_payload = build_init_payload(ctx, write_gitignore=False)
    registry = load_project_registry(project_registry_path())
    existing = any(item.get("repo_root") == str(ctx.repo_root) for item in registry["projects"])
    registry_path = register_project(ctx.repo_root, name=ctx.repo_root.name)
    return {
        **init_payload,
        "reloaded": True,
        "registry_path": str(registry_path),
        "registered": {
            "name": ctx.repo_root.name,
            "added_new": not existing,
            "refreshed": existing,
            "position": 0,
        },
    }
