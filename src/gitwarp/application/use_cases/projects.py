from __future__ import annotations

from typing import Any

from ...domain.errors import GitWarpError
from ...infrastructure.ledger import prune_missing_projects, unregister_project


def build_forget_project_payload(repo_root: str | None, *, prune_missing: bool) -> dict[str, Any]:
    if prune_missing:
        registry_path, removed = prune_missing_projects()
        return {
            "ok": True,
            "prune_missing": True,
            "removed": removed,
            "removed_count": len(removed),
            "registry_path": str(registry_path),
        }
    if not repo_root or not repo_root.strip():
        raise GitWarpError("forget-project requires repo_root unless prune_missing is set")
    registry_path, removed_count = unregister_project(repo_root)
    return {
        "ok": True,
        "prune_missing": False,
        "repo_root": repo_root,
        "removed": [repo_root] if removed_count else [],
        "removed_count": removed_count,
        "registry_path": str(registry_path),
    }
