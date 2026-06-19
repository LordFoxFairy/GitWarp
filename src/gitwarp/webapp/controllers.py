from __future__ import annotations

from typing import Any

from ..domain.errors import GitWarpError
from ..infrastructure.runtime import RepoContext
from ..application.services import (
    build_collapse_payload,
    build_dispatch_payload,
    build_finish_payload,
    build_handoff_payload,
    build_init_payload,
    build_start_payload,
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
    value = payload.get("instructions")
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GitWarpError("instructions must be a list of strings")
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
            cwd=payload.get("cwd") if isinstance(payload.get("cwd"), str) else None,
            path=payload.get("path") if isinstance(payload.get("path"), str) else None,
            branch=payload.get("branch") if isinstance(payload.get("branch"), str) else None,
        )
    except TimeoutError:
        raise
    except GitWarpError as exc:
        raise BadConfirmation(str(exc)) from exc
    if challenge != current:
        raise StaleConfirmation("confirmation no longer matches target state")


def handle_mutation(path: str, ctx: RepoContext, payload: dict[str, Any], *, confirmation_secret: bytes) -> dict[str, Any]:
    if path == "/api/init":
        return build_init_payload(ctx, write_gitignore=bool(payload.get("write_gitignore", False)))
    if path == "/api/dispatch":
        return build_dispatch_payload(
            ctx,
            agent=payload.get("agent") if isinstance(payload.get("agent"), str) else None,
            agent_id=payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else None,
            branch=str(payload["branch"]),
            purpose=str(payload["purpose"]),
            instructions=optional_instruction_list(payload),
            instruction_profile=optional_instruction_profile(payload),
            instruction_mode=optional_instruction_mode(payload),
        )
    if path == "/api/start":
        return build_start_payload(
            ctx,
            agent_id=str(payload["agent_id"]),
            branch=str(payload["branch"]),
            purpose=str(payload["purpose"]),
            instructions=optional_instruction_list(payload),
            instruction_profile=optional_instruction_profile(payload),
            instruction_mode=optional_instruction_mode(payload),
        )
    if path == "/api/handoff":
        return build_handoff_payload(
            ctx,
            cwd=str(payload["cwd"]),
            path=payload.get("path") if isinstance(payload.get("path"), str) else None,
            branch=payload.get("branch") if isinstance(payload.get("branch"), str) else None,
            status=str(payload["status"]),
            progress=str(payload["progress"]),
            lesson=payload.get("lesson") if isinstance(payload.get("lesson"), str) else None,
        )
    if path == "/api/confirmation":
        action = str(payload["action"])
        challenge = inspect_destructive_target(
            ctx,
            action=action,
            cwd=payload.get("cwd") if isinstance(payload.get("cwd"), str) else None,
            path=payload.get("path") if isinstance(payload.get("path"), str) else None,
            branch=payload.get("branch") if isinstance(payload.get("branch"), str) else None,
        )
        confirmation, expires_at = encode_confirmation(confirmation_secret, challenge)
        return {"ok": True, "confirmation": confirmation, "expires_at": expires_at, "challenge": challenge}
    if path == "/api/finish":
        collapse = bool(payload.get("collapse", False))
        if collapse:
            require_confirmation(secret=confirmation_secret, ctx=ctx, action="finish-collapse", payload=payload)
        return build_finish_payload(
            ctx,
            cwd=str(payload["cwd"]),
            path=payload.get("path") if isinstance(payload.get("path"), str) else None,
            branch=payload.get("branch") if isinstance(payload.get("branch"), str) else None,
            status=str(payload["status"]),
            progress=str(payload["progress"]),
            lesson=payload.get("lesson") if isinstance(payload.get("lesson"), str) else None,
            collapse=collapse,
        )
    if path == "/api/collapse":
        require_confirmation(secret=confirmation_secret, ctx=ctx, action="collapse", payload=payload)
        return build_collapse_payload(
            ctx,
            path=payload.get("path") if isinstance(payload.get("path"), str) else None,
            branch=payload.get("branch") if isinstance(payload.get("branch"), str) else None,
        )
    raise GitWarpError("mutation endpoint is not implemented yet")
