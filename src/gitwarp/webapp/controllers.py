from __future__ import annotations

from typing import Any

from ..domain.errors import GitWarpError
from ..infrastructure.ledger import discover_repo
from ..infrastructure.runtime import RepoContext, resolve_path
from ..application.use_cases import (
    TaskCreateRequest,
    build_add_payload,
    build_collapse_payload,
    build_dispatch_payload,
    build_base_payload,
    build_finish_payload,
    build_handoff_payload,
    build_init_payload,
    build_reload_payload,
    build_remove_payload,
    build_prune_branch_payload,
    build_start_payload,
    build_task_create_payload,
    inspect_destructive_target,
)
from .security import decode_confirmation, encode_confirmation


class ConfirmationRequired(PermissionError):
    pass


class BadConfirmation(PermissionError):
    pass


class StaleConfirmation(RuntimeError):
    pass


def optional_instruction_list(payload: dict[str, Any]) -> list[str] | None:
    return optional_string_list(payload, "instructions")


def optional_string_list(payload: dict[str, Any], field: str) -> list[str] | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GitWarpError(f"{field} must be a list of strings")
    return value


def optional_instruction_profile(payload: dict[str, Any]) -> str | None:
    value = payload.get("instruction_profile")
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise GitWarpError("instruction_profile must be a string")
    return value


def optional_instruction_mode(payload: dict[str, Any]) -> str:
    value = payload.get("instruction_mode")
    if value is None or value == "":
        return "copy"
    if not isinstance(value, str) or value not in {"copy", "symlink"}:
        raise GitWarpError("instruction_mode must be copy or symlink")
    return value


def string_field(payload: dict[str, Any], field: str) -> str:
    value = payload[field]
    if not isinstance(value, str):
        raise GitWarpError(f"{field} must be a string")
    return value


def optional_string_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise GitWarpError(f"{field} must be a string")
    return value


def optional_bool_field(payload: dict[str, Any], field: str, default: bool = False) -> bool:
    value = payload.get(field, default)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise GitWarpError(f"{field} must be a boolean")
    return value


def bool_field(payload: dict[str, Any], field: str) -> bool:
    value = payload[field]
    if not isinstance(value, bool):
        raise GitWarpError(f"{field} must be a boolean")
    return value


def require_confirmation(
    *,
    secret: bytes,
    ctx: RepoContext,
    action: str,
    payload: dict[str, Any],
) -> None:
    token = payload.get("confirmation")
    if not isinstance(token, str) or not token:
        raise ConfirmationRequired("destructive action requires confirmation")
    try:
        challenge = decode_confirmation(secret, token)
        current = inspect_destructive_target(
            ctx,
            action=action,
            cwd=optional_string_field(payload, "cwd"),
            path=optional_string_field(payload, "path"),
            branch=optional_string_field(payload, "branch"),
        )
    except TimeoutError:
        raise
    except GitWarpError as exc:
        raise BadConfirmation(str(exc)) from exc
    if challenge != current:
        raise StaleConfirmation("confirmation no longer matches target state")


def handle_mutation(path: str, ctx: RepoContext, payload: dict[str, Any], *, confirmation_secret: bytes) -> dict[str, Any]:
    if path == "/api/init":
        return build_init_payload(ctx, write_gitignore=bool_field(payload, "write_gitignore"))
    if path == "/api/add":
        target_path = optional_string_field(payload, "path")
        target_ctx = discover_repo(resolve_path(target_path or str(ctx.repo_root)))
        return build_add_payload(target_ctx, write_gitignore=bool_field(payload, "write_gitignore"))
    if path == "/api/reload":
        return build_reload_payload(ctx)
    if path == "/api/task/create":
        return build_task_create_payload(
            ctx,
            TaskCreateRequest(
                title=string_field(payload, "title"),
                description=optional_string_field(payload, "description"),
                base_branch=optional_string_field(payload, "base_branch"),
                branch=optional_string_field(payload, "branch"),
                target_agent=optional_string_field(payload, "target_agent"),
                agent_id=optional_string_field(payload, "agent_id"),
                purpose=optional_string_field(payload, "purpose"),
                acceptance_criteria=optional_string_list(payload, "acceptance_criteria") or [],
                verification_commands=optional_string_list(payload, "verification_commands") or [],
                instructions=optional_instruction_list(payload) or [],
                instruction_profile=optional_instruction_profile(payload),
                instruction_mode=optional_instruction_mode(payload),
            ),
        )
    if path == "/api/base":
        return build_base_payload(
            ctx,
            branch=string_field(payload, "branch"),
            purpose=optional_string_field(payload, "purpose") or f"Base checkout for {string_field(payload, 'branch')}",
        )
    if path == "/api/dispatch":
        return build_dispatch_payload(
            ctx,
            agent=optional_string_field(payload, "agent"),
            agent_id=optional_string_field(payload, "agent_id"),
            branch=string_field(payload, "branch"),
            purpose=string_field(payload, "purpose"),
            base_branch=optional_string_field(payload, "base_branch"),
            instructions=optional_instruction_list(payload),
            instruction_profile=optional_instruction_profile(payload),
            instruction_mode=optional_instruction_mode(payload),
        )
    if path == "/api/start":
        return build_start_payload(
            ctx,
            agent_id=string_field(payload, "agent_id"),
            branch=string_field(payload, "branch"),
            purpose=string_field(payload, "purpose"),
            base_branch=optional_string_field(payload, "base_branch"),
            instructions=optional_instruction_list(payload),
            instruction_profile=optional_instruction_profile(payload),
            instruction_mode=optional_instruction_mode(payload),
        )
    if path == "/api/handoff":
        return build_handoff_payload(
            ctx,
            cwd=string_field(payload, "cwd"),
            path=optional_string_field(payload, "path"),
            branch=optional_string_field(payload, "branch"),
            status=string_field(payload, "status"),
            progress=string_field(payload, "progress"),
            lesson=optional_string_field(payload, "lesson"),
        )
    if path == "/api/confirmation":
        action = string_field(payload, "action")
        challenge = inspect_destructive_target(
            ctx,
            action=action,
            cwd=optional_string_field(payload, "cwd"),
            path=optional_string_field(payload, "path"),
            branch=optional_string_field(payload, "branch"),
        )
        confirmation, expires_at = encode_confirmation(confirmation_secret, challenge)
        return {"ok": True, "confirmation": confirmation, "expires_at": expires_at, "challenge": challenge}
    if path == "/api/finish":
        collapse = optional_bool_field(payload, "collapse")
        collapse_merged = optional_bool_field(payload, "collapse_merged")
        if collapse:
            require_confirmation(secret=confirmation_secret, ctx=ctx, action="finish-collapse", payload=payload)
        return build_finish_payload(
            ctx,
            cwd=string_field(payload, "cwd"),
            path=optional_string_field(payload, "path"),
            branch=optional_string_field(payload, "branch"),
            status=string_field(payload, "status"),
            progress=string_field(payload, "progress"),
            lesson=optional_string_field(payload, "lesson"),
            collapse=collapse,
            collapse_merged=collapse_merged,
        )
    if path == "/api/collapse":
        require_confirmation(secret=confirmation_secret, ctx=ctx, action="collapse", payload=payload)
        return build_collapse_payload(
            ctx,
            path=optional_string_field(payload, "path"),
            branch=optional_string_field(payload, "branch"),
        )
    if path == "/api/remove":
        require_confirmation(secret=confirmation_secret, ctx=ctx, action="remove", payload=payload)
        return build_remove_payload(
            ctx,
            path=optional_string_field(payload, "path"),
            branch=optional_string_field(payload, "branch"),
        )
    if path == "/api/prune-branch":
        branch = string_field(payload, "branch")
        if string_field(payload, "confirm_branch") != branch:
            raise GitWarpError("confirm_branch must exactly match branch")
        target_cwd = optional_string_field(payload, "cwd") or str(ctx.repo_root)
        target_ctx = discover_repo(resolve_path(target_cwd))
        return build_prune_branch_payload(
            target_ctx,
            branch=branch,
            base_branch=optional_string_field(payload, "base_branch"),
        )
    raise GitWarpError("mutation endpoint is not implemented yet")
