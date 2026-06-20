from __future__ import annotations

import argparse
import os

from ...application.use_cases import (
    build_adopt_payload,
    build_annotate_payload,
    build_base_payload,
    build_collapse_payload,
    build_dispatch_payload,
    build_finish_payload,
    build_handoff_payload,
    build_start_payload,
    build_switch_payload,
    build_summon_payload,
    inspect_destructive_target,
    shell_cd_command,
)
from ...infrastructure.agents import build_agent_id
from ...infrastructure.ledger import discover_repo
from ...infrastructure.runtime import GitWarpError, emit_json, resolve_path
from ...infrastructure.worktrees import parse_worktrees, select_live_target, sync_ledger


def default_agent_id(branch: str) -> str:
    return (
        os.environ.get("GITWARP_AGENT_ID")
        or os.environ.get("CODEX_AGENT_ID")
        or os.environ.get("CLAUDE_AGENT_ID")
        or build_agent_id("agent", branch)
    )


def cmd_summon(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_summon_payload(ctx, agent_id=args.agent_id, branch=args.branch, purpose=args.purpose, base_branch=args.base))


def cmd_create(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    if args.role == "base":
        payload = build_base_payload(
            ctx,
            branch=args.branch,
            purpose=args.purpose,
        )
        payload["shell_command"] = shell_cd_command(str(payload["path"]))
        emit_json(payload)
        return
    payload = build_start_payload(
        ctx,
        agent_id=args.agent_id or default_agent_id(args.branch),
        branch=args.branch,
        purpose=args.purpose,
        base_branch=args.base,
        instructions=args.instruction,
        instruction_profile=args.instruction_profile,
        instruction_mode=args.instruction_mode,
    )
    payload["shell_command"] = shell_cd_command(str(payload["path"]))
    emit_json(payload)


def cmd_start(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(
        build_start_payload(
            ctx,
            agent_id=args.agent_id,
            branch=args.branch,
            purpose=args.purpose,
            base_branch=args.base,
            instructions=args.instruction,
            instruction_profile=args.instruction_profile,
            instruction_mode=args.instruction_mode,
        )
    )


def cmd_dispatch(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    if args.command_mode == "execute":
        raise GitWarpError("dispatch command-mode execute is not supported yet")
    emit_json(
        build_dispatch_payload(
            ctx,
            agent=args.agent,
            agent_id=args.agent_id,
            branch=args.branch,
            purpose=args.purpose,
            base_branch=args.base,
            instructions=args.instruction,
            instruction_profile=args.instruction_profile,
            instruction_mode=args.instruction_mode,
        )
    )


def cmd_adopt(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    emit_json(
        build_adopt_payload(
            ctx,
            cwd=str(cwd),
            path=args.path,
            agent_id=args.agent_id,
            purpose=args.purpose,
            branch_role=args.role,
            base_branch=args.base,
        )
    )


def cmd_annotate(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    emit_json(
        build_annotate_payload(
            ctx,
            cwd=str(cwd),
            path=args.path,
            branch=args.branch,
            status=args.status,
            note=args.note,
        )
    )


def cmd_handoff(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    emit_json(
        build_handoff_payload(
            ctx,
            cwd=str(cwd),
            path=args.path,
            branch=args.branch,
            status=args.status,
            progress=args.progress,
            lesson=args.lesson,
        )
    )


def cmd_pause(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    emit_json(
        build_handoff_payload(
            ctx,
            cwd=str(cwd),
            path=args.path,
            branch=args.branch,
            status="blocked",
            progress=args.reason,
            lesson=args.lesson,
        )
    )


def cmd_resume(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    emit_json(
        build_handoff_payload(
            ctx,
            cwd=str(cwd),
            path=args.path,
            branch=args.branch,
            status="active",
            progress=args.progress,
            lesson=args.lesson,
        )
    )


def cmd_finish(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    payload = build_finish_payload(
        ctx,
        cwd=str(cwd),
        path=args.path,
        branch=args.branch,
        status=args.status,
        progress=args.progress,
        lesson=args.lesson,
        collapse=args.collapse,
        collapse_merged=args.collapse_merged,
        purge_dossier=args.purge_dossier,
    )
    emit_json(payload)


def cmd_collapse(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_collapse_payload(ctx, path=args.path, branch=args.branch))


def cmd_remove(args: argparse.Namespace) -> None:
    cwd = resolve_path(args.cwd or args.path)
    ctx = discover_repo(cwd)
    target_path = args.path
    if target_path is None and args.branch is None:
        _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
        target_path = select_live_target(worktrees=worktrees, cwd=cwd, path_arg=None, branch_arg=None)["path"]
    if not args.force:
        target = inspect_destructive_target(
            ctx,
            action="remove",
            cwd=str(cwd),
            path=target_path,
            branch=args.branch,
        )
        dirty_count = target["dirty_summary"]["count"]
        if dirty_count:
            raise GitWarpError(
                "remove target has uncommitted or untracked files; "
                f"rerun with --force to remove anyway (dirty_count={dirty_count})"
            )
    emit_json(build_collapse_payload(ctx, path=target_path, branch=args.branch))


def cmd_switch(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    ctx = discover_repo(resolve_path(anchor))
    payload = build_switch_payload(ctx, cwd=args.cwd, path=args.path, branch=args.branch, main=args.main)
    if args.format == "shell":
        print(payload["shell_command"])
        return
    emit_json(payload)
