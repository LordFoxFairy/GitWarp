from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import (
    build_agent_id,
    load_agent_registry,
    render_agent_prompt,
    render_command,
    shell_preview,
)
from .diagnostics import (
    agent_config_check,
    append_gitwarp_ignore_rule,
    build_doctor_payload,
    build_finding,
    codex_plugin_metadata_check,
    doctor_check,
    gitwarp_ignored_check,
    gitwarp_initialized_check,
    init_recommendations,
    is_gitwarp_source_checkout,
    ledger_schema_check,
    preflight_init,
    recommended_next_for_findings,
    run_command_for_doctor,
    session_hook_context_check,
    standard_skill_links_check,
    summarize_findings,
)
from .dossiers import (
    create_dossier_files,
    dossier_paths,
    ensure_dossier_for_entry,
    record_handoff,
)
from .foundation import GitWarpError, RepoContext, emit_json, now_iso, path_contains, resolve_path, run_git
from .ledger import (
    default_ledger,
    discover_repo,
    load_raw_ledger,
    mutate_ledger,
    normalize_ledger_schema,
    write_ledger,
)
from .reconcile import build_reconcile_payload
from .reporting import (
    board_row,
    build_enter_payload,
    filter_board_rows,
    format_enter_prompt,
    print_board_table,
    statusline_banner,
)
from .worktrees import (
    branch_merged_into_main,
    create_worktree,
    ensure_branch_available,
    find_worktree_for_cwd,
    guarded_worktree_root_contains,
    parse_worktrees,
    select_collapse_target,
    select_live_target,
    sync_ledger,
    worktree_dirty,
)


def cmd_scan(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
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


def cmd_init(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    preflight = preflight_init(ctx, write_gitignore=args.write_gitignore)
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

    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "worktree_root": str(ctx.worktree_root),
            "dossier_root": str(ctx.dossier_root),
            "created": created,
            "updated": updated,
            "ignore_target": str(preflight["ignore_target"]),
            "recommended_next": init_recommendations(ctx),
        }
    )


def cmd_summon(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, args.branch)

    target_dir, existing_branch, head = create_worktree(ctx, args.branch)
    entry = {
        "path": str(target_dir),
        "branch": args.branch,
        "agent_id": args.agent_id,
        "purpose": args.purpose,
        "status": "active",
        "notes": [],
        "last_seen_head": head,
        "created_at": now_iso(),
    }

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    mutate_ledger(ctx, update)

    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": str(target_dir),
            "branch": args.branch,
            "head": head,
            "agent_id": args.agent_id,
            "purpose": args.purpose,
            "branch_created": not existing_branch,
        }
    )


def cmd_start(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, args.branch)

    target_dir, existing_branch, head = create_worktree(ctx, args.branch)
    created_at = now_iso()
    dossier = dossier_paths(ctx, args.branch, target_dir)
    entry = {
        "path": str(target_dir),
        "branch": args.branch,
        "agent_id": args.agent_id,
        "purpose": args.purpose,
        "status": "active",
        "notes": [],
        "latest_progress": "Workspace created.",
        "last_seen_head": head,
        "created_at": created_at,
        **dossier,
    }
    create_dossier_files(
        dossier,
        agent_id=args.agent_id,
        branch=args.branch,
        worktree_path=str(target_dir),
        purpose=args.purpose,
        status="active",
        created_at=created_at,
    )

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    mutate_ledger(ctx, update)

    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": str(target_dir),
            "branch": args.branch,
            "head": head,
            "agent_id": args.agent_id,
            "purpose": args.purpose,
            "status": "active",
            "branch_created": not existing_branch,
            "last_seen_head": head,
            "latest_progress": "Workspace created.",
            **dossier,
        }
    )


def cmd_dispatch(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    registry = load_agent_registry(ctx)
    agent_name = args.agent or registry["default_agent"]
    agents_by_name = registry["agents_by_name"]
    if agent_name not in agents_by_name:
        raise GitWarpError(f"unknown agent '{agent_name}'; available agents: {', '.join(sorted(agents_by_name))}")
    if args.command_mode == "execute":
        raise GitWarpError("dispatch command-mode execute is not supported yet")

    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    ensure_branch_available(worktrees, args.branch)

    agent = agents_by_name[agent_name]
    agent_id = args.agent_id or build_agent_id(agent_name, args.branch)
    target_dir, existing_branch, head = create_worktree(ctx, args.branch)
    created_at = now_iso()
    dossier = dossier_paths(ctx, args.branch, target_dir)
    prompt = render_agent_prompt(args.purpose)
    values = {
        "repo": str(ctx.repo_root),
        "worktree": str(target_dir),
        "branch": args.branch,
        "agent_id": agent_id,
        "purpose": args.purpose,
        "task_md": dossier["task_md"],
        "progress_md": dossier["progress_md"],
        "lessons_md": dossier["lessons_md"],
        "prompt": prompt,
    }
    launch_command = render_command(agent["command"], values)
    launch_preview = shell_preview(launch_command)
    dispatch_meta = {
        "agent_name": agent_name,
        "command_mode": "print",
        "launch_command": launch_command,
        "launch_preview": launch_preview,
        "last_exit_code": None,
        "last_prepared_at": created_at,
        "last_started_at": None,
        "last_finished_at": None,
    }
    entry = {
        "path": str(target_dir),
        "branch": args.branch,
        "agent_id": agent_id,
        "purpose": args.purpose,
        "status": "dispatched",
        "notes": [],
        "latest_progress": "Dispatch command prepared.",
        "last_seen_head": head,
        "created_at": created_at,
        "updated_at": created_at,
        "dispatch": dispatch_meta,
        **dossier,
    }
    create_dossier_files(
        dossier,
        agent_id=agent_id,
        branch=args.branch,
        worktree_path=str(target_dir),
        purpose=args.purpose,
        status="dispatched",
        created_at=created_at,
    )

    def update(ledger: dict[str, Any]) -> None:
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
        ledger["entries"].append(entry)

    mutate_ledger(ctx, update)

    emit_json(
        {
            "ok": True,
            "mode": "print",
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "agent": agent_name,
            "agent_id": agent_id,
            "path": str(target_dir),
            "branch": args.branch,
            "head": head,
            "purpose": args.purpose,
            "status": "dispatched",
            "branch_created": not existing_branch,
            "last_seen_head": head,
            "launch_command": launch_command,
            "launch_preview": launch_preview,
            **dossier,
        }
    )


def cmd_adopt(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=cwd,
        path_arg=args.path,
        branch_arg=None,
    )
    if target.get("is_main"):
        raise GitWarpError("refusing to adopt the main repository checkout")
    if target.get("detached") or not target.get("branch"):
        raise GitWarpError("refusing to adopt a detached worktree")

    target_path = target["path"]
    target_branch = target.get("branch")
    outside_guarded_root = not guarded_worktree_root_contains(ctx, target_path)
    result: dict[str, Any] = {}

    def update(ledger: dict[str, Any]) -> None:
        same_path = next((item for item in ledger["entries"] if item.get("path") == target_path), None)
        same_branch = next(
            (item for item in ledger["entries"] if item.get("branch") == target_branch and item.get("path") != target_path),
            None,
        )
        if same_branch is not None:
            raise GitWarpError(f"branch '{target_branch}' is already tracked at {same_branch.get('path')}")
        same_agent = next(
            (item for item in ledger["entries"] if item.get("agent_id") == args.agent_id and item.get("path") != target_path),
            None,
        )
        if same_agent is not None:
            raise GitWarpError(f"agent '{args.agent_id}' is already assigned to {same_agent.get('path')}")

        entry = same_path
        if entry is None:
            entry = {
                "path": target_path,
                "branch": target_branch,
                "notes": [],
                "created_at": now_iso(),
            }
            ledger["entries"].append(entry)
        entry["path"] = target_path
        entry["branch"] = target_branch
        entry["agent_id"] = args.agent_id
        entry["purpose"] = args.purpose
        entry["status"] = "adopted"
        entry["updated_at"] = now_iso()
        entry["latest_progress"] = "Worktree adopted."
        entry["last_seen_head"] = target.get("head")
        paths = ensure_dossier_for_entry(ctx, entry, target)
        result["entry"] = dict(entry)
        result["paths"] = dict(paths)

    mutate_ledger(ctx, update)
    entry = result["entry"]
    paths = result["paths"]
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": target_path,
            "branch": target_branch,
            "head": target.get("head"),
            "agent_id": entry.get("agent_id"),
            "purpose": entry.get("purpose"),
            "status": entry.get("status"),
            "outside_guarded_root": outside_guarded_root,
            **paths,
        }
    )


def cmd_context(args: argparse.Namespace) -> None:
    cwd = resolve_path(args.cwd)
    ctx = discover_repo(cwd)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
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


def cmd_annotate(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=cwd,
        path_arg=args.path,
        branch_arg=args.branch,
    )
    if target.get("is_main"):
        raise GitWarpError("refusing to annotate the main repository checkout")

    target_path = target["path"]
    result: dict[str, Any] = {}

    def update(ledger: dict[str, Any]) -> None:
        entry = next((item for item in ledger["entries"] if item.get("path") == target_path), None)
        if entry is None:
            entry = {
                "path": target_path,
                "branch": target.get("branch"),
                "agent_id": None,
                "purpose": None,
                "status": None,
                "notes": [],
                "created_at": now_iso(),
            }
            ledger["entries"].append(entry)

        timestamp = now_iso()
        if args.status:
            entry["status"] = args.status
        entry.setdefault("notes", [])
        entry["notes"].append({"note": args.note, "created_at": timestamp})
        entry["updated_at"] = timestamp
        result["entry"] = dict(entry)

    mutate_ledger(ctx, update)
    entry = result["entry"]

    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": target_path,
            "branch": target.get("branch"),
            "agent_id": entry.get("agent_id"),
            "purpose": entry.get("purpose"),
            "status": entry.get("status"),
            "notes_count": len(entry["notes"]),
            "latest_note": entry["notes"][-1],
        }
    )


def cmd_handoff(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=cwd,
        path_arg=args.path,
        branch_arg=args.branch,
    )
    entry, paths = record_handoff(
        ctx,
        target,
        status=args.status,
        progress=args.progress,
        lesson=args.lesson,
    )
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": target["path"],
            "branch": target.get("branch"),
            "agent_id": entry.get("agent_id"),
            "purpose": entry.get("purpose"),
            "status": entry.get("status"),
            "latest_progress": entry.get("latest_progress"),
            "latest_lesson": entry.get("latest_lesson"),
            **paths,
        }
    )


def cmd_pause(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=cwd,
        path_arg=args.path,
        branch_arg=args.branch,
    )
    entry, paths = record_handoff(
        ctx,
        target,
        status="blocked",
        progress=args.reason,
        lesson=args.lesson,
    )
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": target["path"],
            "branch": target.get("branch"),
            "agent_id": entry.get("agent_id"),
            "purpose": entry.get("purpose"),
            "status": entry.get("status"),
            "latest_progress": entry.get("latest_progress"),
            "latest_lesson": entry.get("latest_lesson"),
            **paths,
        }
    )


def cmd_resume(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=cwd,
        path_arg=args.path,
        branch_arg=args.branch,
    )
    entry, paths = record_handoff(
        ctx,
        target,
        status="active",
        progress=args.progress,
        lesson=args.lesson,
    )
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": target["path"],
            "branch": target.get("branch"),
            "agent_id": entry.get("agent_id"),
            "purpose": entry.get("purpose"),
            "status": entry.get("status"),
            "latest_progress": entry.get("latest_progress"),
            "latest_lesson": entry.get("latest_lesson"),
            **paths,
        }
    )


def cmd_board(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
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


def cmd_finish(args: argparse.Namespace) -> None:
    anchor = args.cwd or args.path
    cwd = resolve_path(anchor)
    ctx = discover_repo(cwd)
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=cwd,
        path_arg=args.path,
        branch_arg=args.branch,
    )
    entry, paths = record_handoff(
        ctx,
        target,
        status=args.status,
        progress=args.progress,
        lesson=args.lesson,
    )

    collapsed = False
    removed_branch = None
    if args.collapse:
        target_path, removed_branch = select_collapse_target(
            worktrees=worktrees,
            ledger=ledger,
            path_arg=target["path"],
            branch_arg=None,
            repo_root=ctx.repo_root,
        )
        run_git(ctx.repo_root, "worktree", "remove", "--force", target_path)
        run_git(ctx.repo_root, "worktree", "prune", "--expire", "now")
        target_dir = Path(target_path)
        if target_dir.exists():
            shutil.rmtree(target_dir)

        def update(locked_ledger: dict[str, Any]) -> None:
            locked_ledger["entries"] = [item for item in locked_ledger["entries"] if item.get("path") != target_path]

        mutate_ledger(ctx, update)
        collapsed = True
    if args.purge_dossier and paths.get("dossier_path"):
        shutil.rmtree(paths["dossier_path"], ignore_errors=True)

    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "path": target["path"],
            "branch": target.get("branch"),
            "removed_branch": removed_branch,
            "agent_id": entry.get("agent_id"),
            "purpose": entry.get("purpose"),
            "status": entry.get("status"),
            "latest_progress": entry.get("latest_progress"),
            "latest_lesson": entry.get("latest_lesson"),
            "collapsed": collapsed,
            "purged_dossier": bool(args.purge_dossier),
            **paths,
        }
    )


def cmd_collapse(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target_path, branch = select_collapse_target(
        worktrees=worktrees,
        ledger=ledger,
        path_arg=args.path,
        branch_arg=args.branch,
        repo_root=ctx.repo_root,
    )

    run_git(ctx.repo_root, "worktree", "remove", "--force", target_path)
    run_git(ctx.repo_root, "worktree", "prune", "--expire", "now")
    target_dir = Path(target_path)
    if target_dir.exists():
        shutil.rmtree(target_dir)

    def update(locked_ledger: dict[str, Any]) -> None:
        locked_ledger["entries"] = [item for item in locked_ledger["entries"] if item.get("path") != target_path]

    mutate_ledger(ctx, update)
    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "removed_path": target_path,
            "removed_branch": branch,
        }
    )


def cmd_statusline(args: argparse.Namespace) -> None:
    cwd = resolve_path(args.cwd)
    try:
        ctx = discover_repo(cwd)
    except GitWarpError:
        print(statusline_banner(None))
        return

    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    print(statusline_banner(find_worktree_for_cwd(cwd, worktrees)))


def cmd_web(args: argparse.Namespace) -> None:
    from .web import run_web_console

    run_web_console(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitwarp",
        description="Manage isolated git worktree sandboxes for concurrent agents.",
    )
    parser.add_argument("--version", action="version", version="gitwarp 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Initialize GitWarp runtime state for this repository")
    init.add_argument("--cwd")
    init.add_argument("--write-gitignore", action="store_true")
    init.set_defaults(func=cmd_init)

    scan = subparsers.add_parser("scan", help="List live worktrees with GitWarp metadata")
    scan.add_argument("--cwd")
    scan.set_defaults(func=cmd_scan)

    agents = subparsers.add_parser("agents", help="List configured agent launch templates")
    agents.add_argument("--cwd")
    agents.set_defaults(func=cmd_agents)

    summon = subparsers.add_parser("summon", help="Create an isolated worktree for an agent")
    summon.add_argument("--cwd")
    summon.add_argument("--agent-id", required=True)
    summon.add_argument("--branch", required=True)
    summon.add_argument("--purpose", required=True)
    summon.set_defaults(func=cmd_summon)

    start = subparsers.add_parser("start", help="Create an isolated worktree with dossier files")
    start.add_argument("--cwd")
    start.add_argument("--agent-id", required=True)
    start.add_argument("--branch", required=True)
    start.add_argument("--purpose", required=True)
    start.set_defaults(func=cmd_start)

    dispatch = subparsers.add_parser("dispatch", help="Create a worktree and render an agent launch command")
    dispatch.add_argument("--cwd")
    dispatch.add_argument("--agent")
    dispatch.add_argument("--agent-id")
    dispatch.add_argument("--branch", required=True)
    dispatch.add_argument("--purpose", required=True)
    dispatch.add_argument("--command-mode", choices=["print", "execute"], default="print")
    dispatch.set_defaults(func=cmd_dispatch)

    adopt = subparsers.add_parser("adopt", help="Bind an existing non-main worktree to GitWarp metadata")
    adopt.add_argument("--cwd")
    adopt.add_argument("--path")
    adopt.add_argument("--agent-id", required=True)
    adopt.add_argument("--purpose", required=True)
    adopt.set_defaults(func=cmd_adopt)

    context = subparsers.add_parser("context", help="Print JSON context for the current worktree")
    context.add_argument("--cwd")
    context.set_defaults(func=cmd_context)

    enter = subparsers.add_parser("enter", help="Print startup context and dossier pointers")
    enter.add_argument("--cwd")
    enter.add_argument("--format", choices=["json", "prompt"], default="json")
    enter.set_defaults(func=cmd_enter)

    annotate = subparsers.add_parser("annotate", help="Append a progress note to a tracked worktree")
    annotate.add_argument("--cwd")
    annotate.add_argument("--path")
    annotate.add_argument("--branch")
    annotate.add_argument("--status")
    annotate.add_argument("--note", required=True)
    annotate.set_defaults(func=cmd_annotate)

    handoff = subparsers.add_parser("handoff", help="Append progress and optional lessons to a worktree dossier")
    handoff.add_argument("--cwd")
    handoff.add_argument("--path")
    handoff.add_argument("--branch")
    handoff.add_argument("--status", required=True)
    handoff.add_argument("--progress", required=True)
    handoff.add_argument("--lesson")
    handoff.set_defaults(func=cmd_handoff)

    pause = subparsers.add_parser("pause", help="Mark a worktree blocked and record why")
    pause.add_argument("--cwd")
    pause.add_argument("--path")
    pause.add_argument("--branch")
    pause.add_argument("--reason", required=True)
    pause.add_argument("--lesson")
    pause.set_defaults(func=cmd_pause)

    resume = subparsers.add_parser("resume", help="Mark a paused worktree active again")
    resume.add_argument("--cwd")
    resume.add_argument("--path")
    resume.add_argument("--branch")
    resume.add_argument("--progress", required=True)
    resume.add_argument("--lesson")
    resume.set_defaults(func=cmd_resume)

    board = subparsers.add_parser("board", help="List active GitWarp worktrees for humans or automation")
    board.add_argument("--cwd")
    board.add_argument("--format", choices=["json", "table"], default="json")
    board.add_argument("--status", help="Only include worktrees with this GitWarp status")
    board.add_argument("--stale", type=float, help="Only include worktrees unchanged for at least N hours")
    board.add_argument("--verbose", action="store_true", help="Include timestamps and dossier snippets")
    board.set_defaults(func=cmd_board)

    reconcile = subparsers.add_parser("reconcile", help="Audit live Git worktrees against GitWarp ledger and dossiers")
    reconcile.add_argument("--cwd")
    reconcile.add_argument("--stale", type=float)
    reconcile.set_defaults(func=cmd_reconcile)

    doctor = subparsers.add_parser("doctor", help="Audit local GitWarp CLI, plugin, hook, and agent setup")
    doctor.add_argument("--cwd")
    doctor.set_defaults(func=cmd_doctor)

    finish = subparsers.add_parser("finish", help="Record final progress and optionally collapse a worktree")
    finish.add_argument("--cwd")
    finish.add_argument("--path")
    finish.add_argument("--branch")
    finish.add_argument("--status", required=True)
    finish.add_argument("--progress", required=True)
    finish.add_argument("--lesson")
    finish.add_argument("--collapse", action="store_true")
    finish.add_argument("--purge-dossier", action="store_true")
    finish.set_defaults(func=cmd_finish)

    collapse = subparsers.add_parser("collapse", help="Force-remove a tracked isolated worktree")
    collapse.add_argument("--cwd")
    collapse.add_argument("--path")
    collapse.add_argument("--branch")
    collapse.set_defaults(func=cmd_collapse)

    statusline = subparsers.add_parser("statusline", help="Print a raw prompt banner for a CWD")
    statusline.add_argument("--cwd")
    statusline.set_defaults(func=cmd_statusline)

    web = subparsers.add_parser("web", help="Start the local GitWarp Web Console")
    web.add_argument("--cwd")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=0)
    web.add_argument("--no-open", action="store_true")
    web.add_argument("--readonly", action="store_true")
    web.add_argument("--unsafe-host", action="store_true")
    web.set_defaults(func=cmd_web)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--web":
        argv = ["web", *argv[1:]]
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except GitWarpError as exc:
        emit_json({"ok": False, "error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
