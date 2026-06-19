from __future__ import annotations

import argparse

from ...application.services import (
    build_adopt_payload,
    build_annotate_payload,
    build_collapse_payload,
    build_dispatch_payload,
    build_finish_payload,
    build_handoff_payload,
    build_start_payload,
    build_summon_payload,
)
from ...infrastructure.ledger import discover_repo
from ...infrastructure.runtime import GitWarpError, emit_json, resolve_path


def cmd_summon(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_summon_payload(ctx, agent_id=args.agent_id, branch=args.branch, purpose=args.purpose))


def cmd_start(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(
        build_start_payload(
            ctx,
            agent_id=args.agent_id,
            branch=args.branch,
            purpose=args.purpose,
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
            instructions=args.instruction,
            instruction_profile=args.instruction_profile,
            instruction_mode=args.instruction_mode,
        )
    )


def cmd_adopt(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    emit_json(build_adopt_payload(ctx, cwd=str(cwd), path=args.path, agent_id=args.agent_id, purpose=args.purpose))


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
        purge_dossier=args.purge_dossier,
    )
    emit_json(payload)


def cmd_collapse(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_collapse_payload(ctx, path=args.path, branch=args.branch))
