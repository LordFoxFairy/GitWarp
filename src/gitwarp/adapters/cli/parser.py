from __future__ import annotations

import argparse

from ... import __version__
from .read import (
    cmd_agents,
    cmd_board,
    cmd_branches,
    cmd_context,
    cmd_doctor,
    cmd_enter,
    cmd_matrix,
    cmd_next,
    cmd_reconcile,
    cmd_scan,
    cmd_statusline,
)
from .system import cmd_init, cmd_install, cmd_upgrade, cmd_web
from .workspaces import (
    cmd_adopt,
    cmd_annotate,
    cmd_collapse,
    cmd_create,
    cmd_dispatch,
    cmd_finish,
    cmd_handoff,
    cmd_pause,
    cmd_prune_branch,
    cmd_remove,
    cmd_resume,
    cmd_start,
    cmd_summon,
    cmd_sweep,
    cmd_switch,
    cmd_task_create,
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

    install = subparsers.add_parser("install", help="Install GitWarp itself or host integrations")
    install.add_argument("target", choices=["self", "gitwarp", "codex", "claude-code", "claude", "claudecode", "cc"])
    install.add_argument("--method", choices=["launcher", "pipx", "pip"], default="launcher", help="Installation method for target self")
    install.add_argument("--source", help="Source checkout for host plugins, or package source for self pip/pipx installs")
    install.add_argument("--dest", help="Launcher path when using --method launcher; defaults to ~/.local/bin/gitwarp")
    install.add_argument("--scope", choices=["user", "project", "local"], default="user", help="Host plugin installation scope")
    install.add_argument("--dry-run", action="store_true", help="Print planned commands without executing them")
    install.set_defaults(func=cmd_install)

    scan = subparsers.add_parser("scan", help="List live worktrees with GitWarp metadata")
    scan.add_argument("--cwd")
    scan.set_defaults(func=cmd_scan)

    agents = subparsers.add_parser("agents", help="List configured agent launch templates")
    agents.add_argument("--cwd")
    agents.set_defaults(func=cmd_agents)

    branches = subparsers.add_parser("branches", help="List local branch refs with GitWarp cleanup safety metadata")
    branches.add_argument("--cwd")
    branches.add_argument("--base", help="Branch used as the merge target for deletion safety; defaults to origin HEAD or main")
    branches.set_defaults(func=cmd_branches)

    matrix = subparsers.add_parser("matrix", help="Explain Git refs, worktrees, ledger rows, and dossiers in one read-only control-plane view")
    matrix.add_argument("--cwd")
    matrix.add_argument("--base", help="Branch used as the merge target for cleanup classification; defaults to origin HEAD or main")
    matrix.set_defaults(func=cmd_matrix)

    next_actions = subparsers.add_parser("next", help="List prioritized safe next actions without mutating GitWarp state")
    next_actions.add_argument("--cwd")
    next_actions.add_argument("--base", help="Branch used as the merge target for cleanup classification; defaults to origin HEAD or main")
    next_actions.set_defaults(func=cmd_next)

    create = subparsers.add_parser("create", help="Create an isolated worktree and dossier")
    create.add_argument("--cwd")
    create.add_argument("--agent-id")
    create.add_argument("--branch", required=True)
    create.add_argument("--role", choices=["base", "task"], default="task", help="Mark the worktree as a long-lived base or agent task")
    create.add_argument("--base", help="Parent base branch for task worktrees; defaults to the current base or main")
    create.add_argument("--purpose", required=True)
    create.add_argument("--instruction", action="append", default=[], help="Mount instruction file into the worktree; use TARGET=SOURCE to rename")
    create.add_argument("--instruction-profile", help="Mount instructions from .gitwarp/instruction_profiles.json")
    create.add_argument("--instruction-mode", choices=["copy", "symlink"], default="copy")
    create.set_defaults(func=cmd_create)

    task = subparsers.add_parser("task", help="High-level task intake for agent work")
    task_subparsers = task.add_subparsers(dest="task_command", required=True)
    task_create = task_subparsers.add_parser("create", help="Create a task worktree from a human task request")
    task_create.add_argument("--cwd")
    task_create.add_argument("--title", required=True)
    task_create.add_argument("--description")
    task_create.add_argument("--base")
    task_create.add_argument("--branch")
    task_create.add_argument("--agent", default="generic", help="Target-agent metadata: codex, claude, or generic")
    task_create.add_argument("--agent-id")
    task_create.add_argument("--purpose")
    task_create.add_argument("--acceptance", action="append", default=[])
    task_create.add_argument("--verify", action="append", default=[])
    task_create.add_argument(
        "--instruction",
        action="append",
        default=[],
        help="Mount instruction file into the worktree; use TARGET=SOURCE to rename",
    )
    task_create.add_argument("--instruction-profile")
    task_create.add_argument("--instruction-mode", choices=["copy", "symlink"], default="copy")
    task_create.set_defaults(func=cmd_task_create)

    switch = subparsers.add_parser("switch", help="Return the path or shell cd command for an existing worktree")
    switch.add_argument("--cwd")
    switch.add_argument("--path")
    switch.add_argument("--branch")
    switch.add_argument("--main", action="store_true")
    switch.add_argument("--format", choices=["json", "shell"], default="json")
    switch.set_defaults(func=cmd_switch)

    remove = subparsers.add_parser("remove", help="Destroy an isolated sandbox and its dossier without merging or deleting the branch")
    remove.add_argument("--cwd")
    remove.add_argument("--path")
    remove.add_argument("--branch")
    remove.add_argument("--force", action="store_true", help="Remove even when the target worktree has uncommitted or untracked files")
    remove.set_defaults(func=cmd_remove)

    prune_branch = subparsers.add_parser("prune-branch", help="Delete a safe, merged, untracked local branch ref")
    prune_branch.add_argument("--cwd")
    prune_branch.add_argument("--branch", required=True)
    prune_branch.add_argument("--base", help="Branch that must contain the target branch HEAD; defaults to origin HEAD or main")
    prune_branch.set_defaults(func=cmd_prune_branch)

    sweep = subparsers.add_parser("sweep", help="Safely clean selected GitWarp-managed task worktrees")
    sweep.add_argument("--cwd")
    sweep.add_argument("--merged-tasks", action="store_true", help="Remove clean task worktrees already merged into their base branch")
    sweep.add_argument("--dry-run", action="store_true", help="Preview candidates without removing worktrees, ledger rows, or dossiers")
    sweep.set_defaults(func=cmd_sweep)

    summon = subparsers.add_parser("summon", help="Create an isolated worktree for an agent")
    summon.add_argument("--cwd")
    summon.add_argument("--agent-id", required=True)
    summon.add_argument("--branch", required=True)
    summon.add_argument("--base", help="Parent base branch for this task worktree")
    summon.add_argument("--purpose", required=True)
    summon.set_defaults(func=cmd_summon)

    start = subparsers.add_parser("start", help="Create an isolated worktree with dossier files")
    start.add_argument("--cwd")
    start.add_argument("--agent-id", required=True)
    start.add_argument("--branch", required=True)
    start.add_argument("--base", help="Parent base branch for this task worktree")
    start.add_argument("--purpose", required=True)
    start.add_argument("--instruction", action="append", default=[], help="Mount instruction file into the worktree; use TARGET=SOURCE to rename")
    start.add_argument("--instruction-profile", help="Mount instructions from .gitwarp/instruction_profiles.json")
    start.add_argument("--instruction-mode", choices=["copy", "symlink"], default="copy")
    start.set_defaults(func=cmd_start)

    dispatch = subparsers.add_parser("dispatch", help="Create a worktree and render an agent launch command")
    dispatch.add_argument("--cwd")
    dispatch.add_argument("--agent")
    dispatch.add_argument("--agent-id")
    dispatch.add_argument("--branch", required=True)
    dispatch.add_argument("--base", help="Parent base branch for this task worktree")
    dispatch.add_argument("--purpose", required=True)
    dispatch.add_argument("--command-mode", choices=["print", "execute"], default="print")
    dispatch.add_argument("--instruction", action="append", default=[], help="Mount instruction file into the worktree; use TARGET=SOURCE to rename")
    dispatch.add_argument("--instruction-profile", help="Mount instructions from .gitwarp/instruction_profiles.json")
    dispatch.add_argument("--instruction-mode", choices=["copy", "symlink"], default="copy")
    dispatch.set_defaults(func=cmd_dispatch)

    adopt = subparsers.add_parser("adopt", help="Bind an existing non-main worktree to GitWarp metadata")
    adopt.add_argument("--cwd")
    adopt.add_argument("--path")
    adopt.add_argument("--agent-id")
    adopt.add_argument("--purpose")
    adopt.add_argument("--role", choices=["base", "task"], default="task")
    adopt.add_argument("--base", help="Parent base branch when adopting as a task")
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

    upgrade = subparsers.add_parser("upgrade", help="Check or refresh the installed gitwarp launcher")
    upgrade.add_argument("--cwd", help="Accepted for automation consistency; launcher sync does not mutate repository state")
    upgrade.add_argument("--dest", help="Launcher path to check or rewrite; defaults to ~/.local/bin/gitwarp")
    upgrade.add_argument("--check", action="store_true", help="Only inspect the launcher; do not write files")
    upgrade.set_defaults(func=cmd_upgrade)

    finish = subparsers.add_parser("finish", help="Record final progress; collapse only when explicitly destroying the sandbox")
    finish.add_argument("--cwd")
    finish.add_argument("--path")
    finish.add_argument("--branch")
    finish.add_argument("--status", required=True)
    finish.add_argument("--progress", required=True)
    finish.add_argument("--lesson")
    finish.add_argument("--collapse", action="store_true", help="Destroy the worktree, ledger row, and matching dossier after recording progress")
    finish.add_argument(
        "--collapse-merged",
        action="store_true",
        help="Destroy only a clean task worktree whose branch HEAD is already merged into its base branch",
    )
    finish.add_argument(
        "--purge-dossier",
        action="store_true",
        help="Also delete the matching dossier when not collapsing; collapse already deletes it",
    )
    finish.set_defaults(func=cmd_finish)

    collapse = subparsers.add_parser("collapse", help="Destroy a tracked isolated worktree and dossier without merging or deleting the branch")
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
