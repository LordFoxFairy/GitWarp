from __future__ import annotations

import json
import shlex
import shutil
import string
from typing import Any

from .foundation import GitWarpError, RepoContext, sanitize_name


ALLOWED_AGENT_TEMPLATE_FIELDS = {
    "repo",
    "worktree",
    "branch",
    "agent_id",
    "purpose",
    "task_md",
    "progress_md",
    "lessons_md",
    "prompt",
}

BUILTIN_AGENTS: dict[str, dict[str, Any]] = {
    "codex": {
        "description": "Codex CLI non-interactive worker",
        "command": ["codex", "--ask-for-approval", "never", "exec", "-C", "{worktree}", "{prompt}"],
        "status": "enabled",
    },
    "claude": {
        "description": "Claude Code worker",
        "command": ["claude", "-C", "{worktree}", "{prompt}"],
        "status": "enabled",
    },
}


def template_fields(values: list[str]) -> set[str]:
    fields: set[str] = set()
    formatter = string.Formatter()
    for value in values:
        for _, field_name, _, _ in formatter.parse(value):
            if field_name:
                fields.add(field_name)
    return fields


def validate_command_template(command: Any, agent_name: str) -> list[str]:
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise GitWarpError(f"agent config '{agent_name}' command must be a non-empty list of strings")
    fields = template_fields(command)
    missing = {"worktree", "prompt"} - fields
    if missing:
        raise GitWarpError(f"agent config '{agent_name}' command missing required template field(s): {', '.join(sorted(missing))}")
    unknown = fields - ALLOWED_AGENT_TEMPLATE_FIELDS
    if unknown:
        raise GitWarpError(f"agent config '{agent_name}' command contains unknown template field(s): {', '.join(sorted(unknown))}")
    return command


def normalize_agent_entry(name: str, raw_entry: Any, *, configured: bool) -> dict[str, Any]:
    if not isinstance(raw_entry, dict):
        raise GitWarpError(f"agent config '{name}' must be an object")
    command = validate_command_template(raw_entry.get("command"), name)
    status = raw_entry.get("status", "enabled")
    if not isinstance(status, str):
        raise GitWarpError(f"agent config '{name}' status must be a string")
    description = raw_entry.get("description", "")
    if not isinstance(description, str):
        raise GitWarpError(f"agent config '{name}' description must be a string")
    return {
        "name": name,
        "description": description,
        "command": command,
        "status": status,
        "configured": configured,
        "available": shutil.which(command[0]) is not None,
    }


def render_agent_prompt(purpose: str) -> str:
    return "\n".join(
        [
            "You are assigned to a GitWarp isolated worktree.",
            'Run: gitwarp enter --cwd "$PWD"',
            "Read task.md, progress.md, and lessons.md from that context before editing.",
            "Do not run git checkout/git switch in the main repository.",
            "Do not switch branches inside the isolated worktree.",
            "Record milestones with gitwarp handoff.",
            "Stop after implementation and verification; do not merge main unless explicitly asked.",
            "",
            f"Task: {purpose}",
        ]
    )


def build_agent_id(agent_name: str, branch: str) -> str:
    return f"{sanitize_name(agent_name)}-{sanitize_name(branch)}"


def render_command(command: list[str], values: dict[str, str]) -> list[str]:
    return [item.format(**values) for item in command]


def shell_preview(command: list[str]) -> str:
    return shlex.join(command)


def load_agent_registry(ctx: RepoContext) -> dict[str, Any]:
    agents = {
        name: normalize_agent_entry(name, entry, configured=False)
        for name, entry in BUILTIN_AGENTS.items()
    }
    default_agent = "codex"
    config_loaded = False
    if ctx.agents_path.exists():
        config_loaded = True
        try:
            raw = json.loads(ctx.agents_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GitWarpError(f"agent config invalid JSON: {ctx.agents_path}") from exc
        if not isinstance(raw, dict):
            raise GitWarpError("agent config root must be an object")
        if raw.get("version") != 1:
            raise GitWarpError("agent config version must be 1")
        raw_agents = raw.get("agents")
        if not isinstance(raw_agents, dict):
            raise GitWarpError("agent config 'agents' must be an object")
        configured_default = raw.get("default_agent")
        if configured_default is not None:
            if not isinstance(configured_default, str):
                raise GitWarpError("agent config default_agent must be a string")
            default_agent = configured_default
        for name, entry in raw_agents.items():
            if not isinstance(name, str):
                raise GitWarpError("agent config names must be strings")
            agents[name] = normalize_agent_entry(name, entry, configured=True)
    if default_agent not in agents:
        raise GitWarpError(f"agent config default_agent '{default_agent}' is not defined")
    return {
        "config_path": str(ctx.agents_path),
        "config_loaded": config_loaded,
        "default_agent": default_agent,
        "agents": [agents[name] for name in sorted(agents)],
        "agents_by_name": agents,
    }
