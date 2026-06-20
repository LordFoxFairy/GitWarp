from __future__ import annotations

from typing import Any

from .errors import GitWarpError


BASE_ROLE = "base"
TASK_ROLE = "task"
DEFAULT_BASE_BRANCH = "main"
VALID_BRANCH_ROLES = {BASE_ROLE, TASK_ROLE}


def normalize_branch_role(value: Any, *, is_main: bool = False) -> str:
    if is_main:
        return BASE_ROLE
    if value in VALID_BRANCH_ROLES:
        return str(value)
    return TASK_ROLE


def require_branch_role(value: str) -> str:
    if value not in VALID_BRANCH_ROLES:
        raise GitWarpError(f"branch role must be one of: {', '.join(sorted(VALID_BRANCH_ROLES))}")
    return value


def normalize_base_branch(value: Any, *, branch_role: str) -> str | None:
    if branch_role == BASE_ROLE:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_BASE_BRANCH


def enrich_role_metadata(item: dict[str, Any], meta: dict[str, Any]) -> tuple[str, str | None]:
    branch_role = normalize_branch_role(meta.get("branch_role"), is_main=bool(item.get("is_main")))
    base_branch = normalize_base_branch(meta.get("base_branch"), branch_role=branch_role)
    return branch_role, base_branch
