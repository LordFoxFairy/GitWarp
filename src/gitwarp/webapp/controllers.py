from __future__ import annotations

from typing import Any

from ..domain.errors import GitWarpError
from ..foundation import RepoContext
from ..services import (
    build_collapse_payload,
    build_dispatch_payload,
    build_finish_payload,
    build_handoff_payload,
    build_init_payload,
    build_start_payload,
    inspect_destructive_target,
)
from .security import decode_confirmation, encode_confirmation


def require_confirmation(
    *,
    secret: bytes,
    ctx: RepoContext,
    action: str,
    payload: dict[str, Any],
) -> None:
    token = payload.get("confirmation")
    if not isinstance(token, str) or not token:
        raise PermissionError("destructive action requires confirmation")
    challenge = decode_confirmation(secret, token)
    current = inspect_destructive_target(
        ctx,
        action=action,
        cwd=payload.get("cwd") if isinstance(payload.get("cwd"), str) else None,
        path=payload.get("path") if isinstance(payload.get("path"), str) else None,
        branch=payload.get("branch") if isinstance(payload.get("branch"), str) else None,
    )
    if challenge != current:
        raise RuntimeError("confirmation no longer matches target state")


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
        )
    if path == "/api/start":
        return build_start_payload(ctx, agent_id=str(payload["agent_id"]), branch=str(payload["branch"]), purpose=str(payload["purpose"]))
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
