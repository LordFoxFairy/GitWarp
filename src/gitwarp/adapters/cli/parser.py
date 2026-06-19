from __future__ import annotations

import argparse

from ... import __version__
from .read import (
    cmd_agents,
    cmd_board,
    cmd_context,
    cmd_doctor,
    cmd_enter,
    cmd_reconcile,
    cmd_scan,
    cmd_statusline,
)
from .system import cmd_init, cmd_web
from .workspaces import (
    cmd_adopt,
    cmd_annotate,
    cmd_collapse,
    cmd_dispatch,
    cmd_finish,
    cmd_handoff,
    cmd_pause,
    cmd_resume,
    cmd_start,
    cmd_summon,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitwarp",
        description="Manage isolated git worktree sandboxes for concurrent agents.",
    )
    parser.add_argument("--version", action="version", version=f"gitwarp {__version__}")
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
