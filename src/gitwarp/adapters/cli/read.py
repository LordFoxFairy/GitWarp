from __future__ import annotations

import argparse
from datetime import datetime, timezone

from ...adapters.presenters import (
    board_row,
    build_enter_payload,
    filter_board_rows,
    format_enter_prompt,
    print_board_table,
    statusline_banner,
)
from ...application.use_cases import build_branches_payload, build_matrix_payload
from ...application.diagnostics import build_doctor_payload
from ...application.reconcile import build_reconcile_payload
from ...infrastructure.agents import load_agent_registry
from ...infrastructure.ledger import discover_repo
from ...infrastructure.runtime import GitWarpError, emit_json, resolve_path
from ...infrastructure.worktrees import find_worktree_for_cwd, parse_worktrees, sync_ledger


def cmd_scan(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "checkout_root": str(ctx.checkout_root),
            "ledger_path": str(ctx.ledger_path),
            "worktree_root": str(ctx.worktree_root),
            "tracked_entries": len(ledger["entries"]),
            "worktrees": worktrees,
        }
    )


def cmd_agents(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    registry = load_agent_registry(ctx)
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "config_path": registry["config_path"],
            "config_loaded": registry["config_loaded"],
            "default_agent": registry["default_agent"],
            "agents": registry["agents"],
        }
    )


def cmd_branches(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_branches_payload(ctx, base_branch=args.base))


def cmd_matrix(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_matrix_payload(ctx, base_branch=args.base))


def cmd_context(args: argparse.Namespace) -> None:
    cwd = resolve_path(args.cwd)
    ctx = discover_repo(cwd)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    target = find_worktree_for_cwd(cwd, worktrees)
    if target is None:
        raise GitWarpError(f"current directory is not inside a live worktree: {cwd}")
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "checkout_root": str(ctx.checkout_root),
            "cwd": str(cwd),
            "ledger_path": str(ctx.ledger_path),
            "worktree": target,
        }
    )


def cmd_enter(args: argparse.Namespace) -> None:
    payload = build_enter_payload(resolve_path(args.cwd))
    if args.format == "prompt":
        print(format_enter_prompt(payload))
        return
    emit_json(payload)


def cmd_board(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    rows = [board_row(item, verbose=args.verbose or args.stale is not None) for item in worktrees]
    rows = filter_board_rows(
        rows,
        status=args.status,
        stale_hours=args.stale,
        now=datetime.now(timezone.utc),
    )
    if args.format == "table":
        print_board_table(rows)
        return
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "worktrees": rows,
        }
    )


def cmd_reconcile(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_reconcile_payload(ctx, stale_hours=args.stale))


def cmd_doctor(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_doctor_payload(ctx))


def cmd_statusline(args: argparse.Namespace) -> None:
    cwd = resolve_path(args.cwd)
    try:
        ctx = discover_repo(cwd)
    except GitWarpError:
        print(statusline_banner(None))
        return

    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    print(statusline_banner(find_worktree_for_cwd(cwd, worktrees)))
