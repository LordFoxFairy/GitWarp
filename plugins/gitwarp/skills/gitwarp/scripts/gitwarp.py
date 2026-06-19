#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import hashlib
import json
import re
import shutil
import shlex
import string
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


LEDGER_DIRNAME = ".gitwarp"
LEDGER_FILENAME = "ledger.json"
LEDGER_LOCK_FILENAME = "ledger.lock"
LOCK_TIMEOUT_SECONDS = 10.0
AGENTS_FILENAME = "agents.json"
WORKTREE_DIRNAME = "worktrees"
DOSSIER_DIRNAME = "dossiers"
TASK_FILENAME = "task.md"
PROGRESS_FILENAME = "progress.md"
LESSONS_FILENAME = "lessons.md"
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


class GitWarpError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepoContext:
    cwd: Path
    repo_root: Path
    checkout_root: Path
    common_dir: Path

    @property
    def ledger_dir(self) -> Path:
        return self.repo_root / LEDGER_DIRNAME

    @property
    def ledger_path(self) -> Path:
        return self.ledger_dir / LEDGER_FILENAME

    @property
    def ledger_lock_path(self) -> Path:
        return self.ledger_dir / LEDGER_LOCK_FILENAME

    @property
    def worktree_root(self) -> Path:
        return self.ledger_dir / WORKTREE_DIRNAME

    @property
    def dossier_root(self) -> Path:
        return self.ledger_dir / DOSSIER_DIRNAME

    @property
    def agents_path(self) -> Path:
        return self.ledger_dir / AGENTS_FILENAME


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def resolve_path(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def run_git(cwd: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitWarpError(f"failed to execute git: {exc}") from exc

    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise GitWarpError(message)
    return result.stdout.strip()


def discover_repo(cwd: Path) -> RepoContext:
    common_dir_raw = run_git(cwd, "rev-parse", "--git-common-dir")
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = (cwd / common_dir).resolve()
    checkout_root = Path(run_git(cwd, "rev-parse", "--show-toplevel")).resolve()
    repo_root = common_dir.parent if common_dir.name == ".git" else common_dir.resolve()
    return RepoContext(cwd=cwd, repo_root=repo_root, checkout_root=checkout_root, common_dir=common_dir)


def load_ledger(ctx: RepoContext) -> dict[str, Any]:
    if not ctx.ledger_path.exists():
        return {"version": 1, "repo_root": str(ctx.repo_root), "entries": []}
    try:
        data = json.loads(ctx.ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GitWarpError(f"invalid ledger file: {ctx.ledger_path}") from exc
    if "entries" not in data or not isinstance(data["entries"], list):
        raise GitWarpError(f"invalid ledger schema: {ctx.ledger_path}")
    data.setdefault("version", 1)
    data["repo_root"] = str(ctx.repo_root)
    return data


def load_raw_ledger(ctx: RepoContext) -> dict[str, Any]:
    return load_ledger(ctx)


@contextmanager
def ledger_write_lock(ctx: RepoContext, timeout: float = LOCK_TIMEOUT_SECONDS) -> Any:
    ctx.ledger_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(ctx.ledger_lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"pid": os.getpid(), "created_at": now_iso()}, sort_keys=True))
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise GitWarpError(f"timed out waiting for ledger lock: {ctx.ledger_lock_path}")
            time.sleep(0.025)
    try:
        yield
    finally:
        try:
            ctx.ledger_lock_path.unlink()
        except FileNotFoundError:
            pass


def write_ledger(ctx: RepoContext, ledger: dict[str, Any]) -> None:
    ctx.ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger["repo_root"] = str(ctx.repo_root)
    ledger["updated_at"] = now_iso()
    temp_path = ctx.ledger_dir / f".{LEDGER_FILENAME}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(ctx.ledger_path)


def mutate_ledger(
    ctx: RepoContext,
    callback: Callable[[dict[str, Any]], Any],
    *,
    live_worktrees: list[dict[str, Any]] | None = None,
) -> Any:
    with ledger_write_lock(ctx):
        ledger = load_ledger(ctx)
        if live_worktrees is not None:
            live_paths = {item["path"] for item in live_worktrees}
            ledger["entries"] = [entry for entry in ledger["entries"] if entry.get("path") in live_paths]
        result = callback(ledger)
        write_ledger(ctx, ledger)
        return result


def parse_worktrees(ctx: RepoContext) -> list[dict[str, Any]]:
    output = run_git(ctx.repo_root, "worktree", "list", "--porcelain")
    blocks = [block for block in output.split("\n\n") if block.strip()]
    worktrees: list[dict[str, Any]] = []
    for block in blocks:
        item: dict[str, Any] = {"branch": None, "detached": False}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                item["path"] = str(Path(value).resolve())
            elif key == "HEAD":
                item["head"] = value
            elif key == "branch":
                item["branch"] = value.removeprefix("refs/heads/")
            elif key == "detached":
                item["detached"] = True
        if "path" not in item or "head" not in item:
            continue
        item["is_main"] = Path(item["path"]) == ctx.repo_root
        worktrees.append(item)
    return worktrees


def sync_ledger(
    ctx: RepoContext,
    live_worktrees: list[dict[str, Any]],
    *,
    persist: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if persist:
        def prune(locked_ledger: dict[str, Any]) -> None:
            live_paths = {item["path"] for item in live_worktrees}
            locked_ledger["entries"] = [entry for entry in locked_ledger["entries"] if entry.get("path") in live_paths]

        mutate_ledger(ctx, prune)
    ledger = load_ledger(ctx)

    metadata_by_path = {entry["path"]: entry for entry in ledger["entries"]}
    enriched: list[dict[str, Any]] = []
    for item in live_worktrees:
        meta = metadata_by_path.get(item["path"], {})
        enriched.append(
            {
                "path": item["path"],
                "head": item["head"],
                "branch": item.get("branch"),
                "detached": item.get("detached", False),
                "is_main": item.get("is_main", False),
                "agent_id": meta.get("agent_id"),
                "purpose": meta.get("purpose"),
                "status": meta.get("status"),
                "notes": meta.get("notes", []),
                "dossier_path": meta.get("dossier_path"),
                "task_md": meta.get("task_md"),
                "progress_md": meta.get("progress_md"),
                "lessons_md": meta.get("lessons_md"),
                "latest_progress": meta.get("latest_progress"),
                "latest_lesson": meta.get("latest_lesson"),
                "created_at": meta.get("created_at"),
                "updated_at": meta.get("updated_at"),
            }
        )
    return ledger, enriched


def path_contains(parent: str, child: Path) -> bool:
    parent_path = Path(parent).resolve()
    return child == parent_path or parent_path in child.parents


def find_worktree_for_cwd(cwd: Path, worktrees: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [item for item in worktrees if path_contains(str(item["path"]), cwd)]
    if not matches:
        return None
    return max(matches, key=lambda item: len(str(item["path"])))


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "workspace"


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:6]


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


def dossier_paths(ctx: RepoContext, branch: str, worktree_path: Path) -> dict[str, str]:
    workspace_id = f"{sanitize_name(branch)}-{short_hash(str(worktree_path))}"
    dossier_path = (ctx.dossier_root / workspace_id).resolve()
    return {
        "dossier_path": str(dossier_path),
        "task_md": str(dossier_path / TASK_FILENAME),
        "progress_md": str(dossier_path / PROGRESS_FILENAME),
        "lessons_md": str(dossier_path / LESSONS_FILENAME),
    }


def create_dossier_files(
    paths: dict[str, str],
    *,
    agent_id: str | None,
    branch: str | None,
    worktree_path: str,
    purpose: str | None,
    status: str | None,
    created_at: str,
) -> None:
    dossier_path = Path(paths["dossier_path"])
    dossier_path.mkdir(parents=True, exist_ok=True)
    task = Path(paths["task_md"])
    progress = Path(paths["progress_md"])
    lessons = Path(paths["lessons_md"])

    if not task.exists():
        task.write_text(
            "\n".join(
                [
                    "# Task",
                    "",
                    f"- Agent: {agent_id or 'unassigned'}",
                    f"- Branch: {branch or 'detached'}",
                    f"- Worktree: {worktree_path}",
                    f"- Purpose: {purpose or 'unspecified'}",
                    f"- Status: {status or 'active'}",
                    f"- Created: {created_at}",
                    "",
                    "## Scope",
                    "",
                    purpose or "Unspecified task.",
                    "",
                    "## Success Criteria",
                    "",
                    "- [ ] Define concrete verification before finishing",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    if not progress.exists():
        progress.write_text(
            "\n".join(
                [
                    "# Progress",
                    "",
                    f"## {created_at}",
                    "",
                    f"- Status: {status or 'active'}",
                    "- Note: Workspace created.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    if not lessons.exists():
        lessons.write_text(
            "\n".join(
                [
                    "# Lessons",
                    "",
                    "## Notes For Future Agents",
                    "",
                    "- Add findings, pitfalls, and decisions that should survive handoff.",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def append_markdown_event(path: str, timestamp: str, lines: list[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {timestamp}\n\n")
        for line in lines:
            handle.write(f"{line}\n")
        handle.write("\n")


def ensure_branch_available(worktrees: list[dict[str, Any]], branch: str) -> None:
    for item in worktrees:
        if item.get("branch") == branch:
            raise GitWarpError(f"branch collision: '{branch}' is already bound to {item['path']}")


def branch_exists(ctx: RepoContext, branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(ctx.repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def create_worktree(ctx: RepoContext, branch: str) -> tuple[Path, bool, str]:
    target_dir = (ctx.worktree_root / sanitize_name(branch)).resolve()
    if target_dir.exists():
        raise GitWarpError(f"target path already exists: {target_dir}")

    ctx.worktree_root.mkdir(parents=True, exist_ok=True)
    existing_branch = branch_exists(ctx, branch)
    if existing_branch:
        run_git(ctx.repo_root, "worktree", "add", str(target_dir), branch)
    else:
        run_git(ctx.repo_root, "worktree", "add", "-b", branch, str(target_dir), "HEAD")

    head = run_git(target_dir, "rev-parse", "HEAD")
    return target_dir, existing_branch, head


def select_collapse_target(
    worktrees: list[dict[str, Any]],
    ledger: dict[str, Any],
    path_arg: str | None,
    branch_arg: str | None,
    repo_root: Path,
) -> tuple[str, str | None]:
    if path_arg:
        target_path = str(Path(path_arg).expanduser().resolve())
    elif branch_arg:
        matches = [item for item in worktrees if item.get("branch") == branch_arg]
        if not matches:
            matches = [item for item in ledger["entries"] if item.get("branch") == branch_arg]
        if not matches:
            raise GitWarpError(f"no live or tracked worktree found for branch '{branch_arg}'")
        target_path = matches[0]["path"]
    else:
        raise GitWarpError("collapse requires --path or --branch")

    if Path(target_path).resolve() == repo_root.resolve():
        raise GitWarpError("refusing to collapse the main repository checkout")

    branch = None
    for item in worktrees:
        if item["path"] == target_path:
            branch = item.get("branch")
            break
    if branch is None:
        for entry in ledger["entries"]:
            if entry.get("path") == target_path:
                branch = entry.get("branch")
                break
    return target_path, branch


def select_live_target(
    worktrees: list[dict[str, Any]],
    cwd: Path,
    path_arg: str | None,
    branch_arg: str | None,
) -> dict[str, Any]:
    if path_arg:
        target_path = str(Path(path_arg).expanduser().resolve())
        for item in worktrees:
            if item["path"] == target_path:
                return item
        raise GitWarpError(f"no live worktree found at path '{target_path}'")
    if branch_arg:
        matches = [item for item in worktrees if item.get("branch") == branch_arg]
        if not matches:
            raise GitWarpError(f"no live worktree found for branch '{branch_arg}'")
        return matches[0]
    target = find_worktree_for_cwd(cwd, worktrees)
    if target is None:
        raise GitWarpError(f"current directory is not inside a live worktree: {cwd}")
    return target


def ledger_entry_for_target(ledger: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    target_path = target["path"]
    entry = next((item for item in ledger["entries"] if item.get("path") == target_path), None)
    if entry is not None:
        return entry
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
    return entry


def ensure_dossier_for_entry(ctx: RepoContext, entry: dict[str, Any], target: dict[str, Any]) -> dict[str, str]:
    branch = entry.get("branch") or target.get("branch") or "detached"
    paths = {
        "dossier_path": entry.get("dossier_path"),
        "task_md": entry.get("task_md"),
        "progress_md": entry.get("progress_md"),
        "lessons_md": entry.get("lessons_md"),
    }
    if not all(paths.values()):
        paths = dossier_paths(ctx, branch, Path(target["path"]))
        entry.update(paths)
    concrete_paths = {key: str(value) for key, value in paths.items()}
    create_dossier_files(
        concrete_paths,
        agent_id=entry.get("agent_id"),
        branch=branch,
        worktree_path=target["path"],
        purpose=entry.get("purpose"),
        status=entry.get("status") or "active",
        created_at=entry.get("created_at") or now_iso(),
    )
    return concrete_paths


def record_handoff(
    ctx: RepoContext,
    target: dict[str, Any],
    *,
    status: str,
    progress: str,
    lesson: str | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if target.get("is_main"):
        raise GitWarpError("refusing to hand off the main repository checkout")

    result: dict[str, Any] = {}

    def update(ledger: dict[str, Any]) -> None:
        entry = ledger_entry_for_target(ledger, target)
        paths = ensure_dossier_for_entry(ctx, entry, target)
        timestamp = now_iso()
        append_markdown_event(
            paths["progress_md"],
            timestamp,
            [f"- Status: {status}", f"- Note: {progress}"],
        )
        if lesson:
            append_markdown_event(paths["lessons_md"], timestamp, [f"- {lesson}"])

        entry["status"] = status
        entry["updated_at"] = timestamp
        entry["latest_progress"] = progress
        if lesson:
            entry["latest_lesson"] = lesson
        entry.setdefault("notes", [])
        entry["notes"].append({"note": progress, "created_at": timestamp, "kind": "progress"})
        result["entry"] = dict(entry)
        result["paths"] = dict(paths)

    mutate_ledger(ctx, update)
    return result["entry"], result["paths"]


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_seconds(item: dict[str, Any], now: datetime) -> int | None:
    timestamp = parse_timestamp(item.get("updated_at") or item.get("created_at"))
    if timestamp is None:
        return None
    return max(0, int((now - timestamp).total_seconds()))


def board_row(item: dict[str, Any], *, verbose: bool = False) -> dict[str, Any]:
    row = {
        "path": item["path"],
        "branch": item.get("branch"),
        "agent_id": item.get("agent_id"),
        "purpose": item.get("purpose"),
        "status": item.get("status"),
        "is_main": item.get("is_main", False),
        "dossier_path": item.get("dossier_path"),
        "task_md": item.get("task_md"),
        "progress_md": item.get("progress_md"),
        "lessons_md": item.get("lessons_md"),
        "latest_progress": item.get("latest_progress"),
        "latest_lesson": item.get("latest_lesson"),
    }
    if verbose:
        row.update(
            {
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "snippets": {
                    "task": read_snippet(item.get("task_md")),
                    "progress": read_snippet(item.get("progress_md")),
                    "lessons": read_snippet(item.get("lessons_md")),
                },
            }
        )
    return row


def filter_board_rows(
    rows: list[dict[str, Any]],
    *,
    status: str | None,
    stale_hours: float | None,
    now: datetime,
) -> list[dict[str, Any]]:
    filtered = rows
    if status is not None:
        filtered = [row for row in filtered if row.get("status") == status]
    if stale_hours is not None:
        cutoff = max(0, int(stale_hours * 3600))
        stale_rows = []
        for row in filtered:
            age = age_seconds(row, now)
            if age is None or age < cutoff:
                continue
            row["age_seconds"] = age
            row["stale"] = True
            stale_rows.append(row)
        filtered = stale_rows
    return filtered


def worktree_dirty(path: str) -> bool:
    return bool(run_git(Path(path), "status", "--porcelain"))


def branch_merged_into_main(ctx: RepoContext, branch: str | None) -> bool:
    if not branch or branch == "main":
        return False
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "main"],
        cwd=str(ctx.repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def build_finding(
    code: str,
    severity: str,
    message: str,
    *,
    item: dict[str, Any] | None = None,
    path: str | None = None,
    branch: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "path": path if path is not None else (item or {}).get("path"),
        "branch": branch if branch is not None else (item or {}).get("branch"),
        "agent_id": agent_id if agent_id is not None else (item or {}).get("agent_id"),
    }


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for finding in findings:
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
        by_code[finding["code"]] = by_code.get(finding["code"], 0) + 1
    return {"total": len(findings), "by_severity": by_severity, "by_code": by_code}


def doctor_check(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    finding = {"code": code, "severity": severity, "message": message}
    if details:
        finding["details"] = details
    return finding


def run_command_for_doctor(command: list[str], cwd: Path, timeout: float = 3.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def print_board_table(rows: list[dict[str, Any]]) -> None:
    headers = ["branch", "agent", "status", "purpose", "progress"]
    print(" | ".join(headers))
    print(" | ".join("---" for _ in headers))
    for row in rows:
        print(
            " | ".join(
                [
                    str(row.get("branch") or ""),
                    str(row.get("agent_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("purpose") or ""),
                    str(row.get("latest_progress") or ""),
                ]
            )
        )


def statusline_banner(target: dict[str, Any] | None) -> str:
    if target is None:
        return "GITWARP[outside]"
    if target.get("is_main"):
        return "GITWARP[main-repo]"
    agent_id = target.get("agent_id") or "unassigned"
    branch = target.get("branch") or "detached"
    return f"GITWARP[{agent_id}@{branch}]"


def read_snippet(path: str | None, *, max_chars: int = 900) -> str | None:
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    text = target.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 4].rstrip() + "\n..."


def enter_recommendations(ctx: RepoContext | None, cwd: Path, target: dict[str, Any] | None) -> list[str]:
    if ctx is None:
        return ["Open a Git repository or pass --cwd /absolute/path/to/repo."]
    if target is None:
        return [f"Move inside a live worktree for {ctx.repo_root} or run gitwarp scan --cwd \"{ctx.repo_root}\"."]
    if target.get("is_main"):
        return [
            f"Run gitwarp start --cwd \"{ctx.repo_root}\" --agent-id <agent-id> --branch <branch> --purpose \"<purpose>\" before isolated work.",
            f"Run gitwarp board --cwd \"{ctx.repo_root}\" to inspect active dimensions.",
        ]
    return [
        "Read task.md, progress.md, and lessons.md before editing.",
        f"Record milestones with gitwarp handoff --cwd \"{cwd}\" --status <status> --progress \"<summary>\".",
        f"Finish with gitwarp finish --cwd \"{cwd}\" --status pushed --progress \"verified and pushed\" [--collapse].",
    ]


def build_enter_payload(cwd: Path) -> dict[str, Any]:
    try:
        ctx = discover_repo(cwd)
    except GitWarpError:
        return {
            "ok": True,
            "location": "outside",
            "cwd": str(cwd),
            "statusline": "GITWARP[outside]",
            "recommended_next": enter_recommendations(None, cwd, None),
        }

    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx), persist=False)
    target = find_worktree_for_cwd(cwd, worktrees)
    if target is None:
        return {
            "ok": True,
            "location": "outside-worktree",
            "repo_root": str(ctx.repo_root),
            "checkout_root": str(ctx.checkout_root),
            "cwd": str(cwd),
            "ledger_path": str(ctx.ledger_path),
            "statusline": "GITWARP[outside]",
            "recommended_next": enter_recommendations(ctx, cwd, None),
        }

    location = "main" if target.get("is_main") else "worktree"
    snippets: dict[str, str | None] = {}
    if location == "worktree":
        snippets = {
            "task": read_snippet(target.get("task_md")),
            "progress": read_snippet(target.get("progress_md")),
            "lessons": read_snippet(target.get("lessons_md")),
        }

    payload: dict[str, Any] = {
        "ok": True,
        "location": location,
        "repo_root": str(ctx.repo_root),
        "checkout_root": str(ctx.checkout_root),
        "cwd": str(cwd),
        "ledger_path": str(ctx.ledger_path),
        "statusline": statusline_banner(target),
        "worktree": target,
        "recommended_next": enter_recommendations(ctx, cwd, target),
    }
    if snippets:
        payload["snippets"] = snippets
    return payload


def format_enter_prompt(payload: dict[str, Any]) -> str:
    lines = [
        f"GitWarp Context: {payload['statusline']}",
        f"Location: {payload['location']}",
        f"CWD: {payload['cwd']}",
    ]
    worktree = payload.get("worktree")
    if isinstance(worktree, dict):
        lines.extend(
            [
                f"Branch: {worktree.get('branch') or 'detached'}",
                f"Agent: {worktree.get('agent_id') or 'unassigned'}",
                f"Purpose: {worktree.get('purpose') or 'unspecified'}",
                f"Status: {worktree.get('status') or 'unknown'}",
            ]
        )
        if not worktree.get("is_main"):
            lines.extend(
                [
                    f"Task: {worktree.get('task_md') or 'missing'}",
                    f"Progress: {worktree.get('progress_md') or 'missing'}",
                    f"Lessons: {worktree.get('lessons_md') or 'missing'}",
                    f"Latest progress: {worktree.get('latest_progress') or 'none'}",
                    f"Latest lesson: {worktree.get('latest_lesson') or 'none'}",
                ]
            )
    recommendations = payload.get("recommended_next") or []
    if recommendations:
        lines.append("Next:")
        lines.extend(f"- {item}" for item in recommendations)
    return "\n".join(lines)


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
            "launch_command": launch_command,
            "launch_preview": launch_preview,
            **dossier,
        }
    )


def guarded_worktree_root_contains(ctx: RepoContext, path: str) -> bool:
    return path_contains(str(ctx.worktree_root), Path(path).resolve())


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
    ledger = load_raw_ledger(ctx)
    live_worktrees = parse_worktrees(ctx)
    live_by_path = {item["path"]: item for item in live_worktrees}
    ledger_by_path = {entry.get("path"): entry for entry in ledger["entries"] if entry.get("path")}
    now = datetime.now(timezone.utc)
    findings: list[dict[str, Any]] = []

    for entry in ledger["entries"]:
        entry_path = entry.get("path")
        if entry_path and entry_path not in live_by_path:
            findings.append(
                build_finding(
                    "stale_ledger_entry",
                    "warning",
                    "Ledger entry points to a missing live worktree.",
                    item=entry,
                )
            )
        for key in ("task_md", "progress_md", "lessons_md"):
            value = entry.get(key)
            if value and not Path(value).exists():
                findings.append(
                    build_finding(
                        "missing_dossier_file",
                        "warning",
                        f"Tracked dossier file is missing: {key}.",
                        item=entry,
                    )
                )
        status = entry.get("status")
        if status in {"blocked", "dispatch_failed", "merged"}:
            findings.append(
                build_finding(
                    "attention_status",
                    "warning",
                    f"Worktree has attention status: {status}.",
                    item=entry,
                )
            )
        if args.stale is not None:
            age = age_seconds(entry, now)
            if age is not None and age >= max(0, int(args.stale * 3600)):
                findings.append(
                    build_finding(
                        "stale_worktree",
                        "warning",
                        f"Worktree ledger has not changed for {age} seconds.",
                        item=entry,
                    )
                )

    for item in live_worktrees:
        if item.get("is_main"):
            continue
        if item["path"] not in ledger_by_path:
            findings.append(
                build_finding(
                    "untracked_worktree",
                    "warning",
                    "Live non-main worktree is missing from the GitWarp ledger.",
                    item=item,
                )
            )
        if worktree_dirty(item["path"]):
            findings.append(
                build_finding(
                    "dirty_worktree",
                    "warning",
                    "Live worktree has uncommitted or untracked changes.",
                    item=ledger_by_path.get(item["path"], item),
                )
            )
        if branch_merged_into_main(ctx, item.get("branch")):
            findings.append(
                build_finding(
                    "merged_head",
                    "warning",
                    "Worktree branch HEAD is already merged into main.",
                    item=ledger_by_path.get(item["path"], item),
                )
            )

    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "findings": findings,
            "summary": summarize_findings(findings),
        }
    )


def cmd_doctor(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    findings: list[dict[str, Any]] = []

    git_path = shutil.which("git")
    findings.append(
        doctor_check(
            "git",
            "ok" if git_path else "error",
            "git is available." if git_path else "git is not available on PATH.",
            path=git_path,
        )
    )
    python_path = shutil.which("python3")
    findings.append(
        doctor_check(
            "python3",
            "ok" if python_path else "error",
            "python3 is available." if python_path else "python3 is not available on PATH.",
            path=python_path,
        )
    )
    launcher_path = shutil.which("gitwarp")
    launcher_severity = "warning"
    launcher_message = "gitwarp launcher is not available on PATH."
    launcher_details: dict[str, Any] = {"path": launcher_path}
    if launcher_path:
        version = run_command_for_doctor([launcher_path, "--version"], ctx.repo_root)
        if version and version.returncode == 0:
            launcher_severity = "ok"
            launcher_message = "gitwarp launcher is available."
            launcher_details["version"] = version.stdout.strip()
        else:
            launcher_severity = "error"
            launcher_message = "gitwarp launcher exists but --version failed."
    findings.append(doctor_check("gitwarp_launcher", launcher_severity, launcher_message, **launcher_details))

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".gitwarp"],
        cwd=str(ctx.repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    findings.append(
        doctor_check(
            "gitwarp_ignored",
            "ok" if ignored.returncode == 0 else "warning",
            ".gitwarp is ignored." if ignored.returncode == 0 else ".gitwarp is not ignored by this repository.",
        )
    )

    try:
        registry = load_agent_registry(ctx)
        for agent in registry["agents"]:
            findings.append(
                doctor_check(
                    "agent_binary",
                    "ok" if agent["available"] else "warning",
                    f"Agent binary for '{agent['name']}' is {'available' if agent['available'] else 'not available'}.",
                    agent=agent["name"],
                    command=agent["command"][0],
                )
            )
    except GitWarpError as exc:
        findings.append(doctor_check("agent_config", "error", str(exc), path=str(ctx.agents_path)))

    codex_path = shutil.which("codex")
    if codex_path:
        result = run_command_for_doctor(["codex", "plugin", "list", "--json"], ctx.repo_root, timeout=5.0)
        enabled = False
        if result and result.returncode == 0:
            raw = result.stdout
            start = raw.find("{")
            if start >= 0:
                try:
                    payload = json.loads(raw[start:])
                    enabled = any(
                        item.get("pluginId") == "gitwarp@gitwarp-dev" and item.get("enabled") is True
                        for item in payload.get("installed", [])
                    )
                except json.JSONDecodeError:
                    enabled = False
        findings.append(
            doctor_check(
                "codex_plugin_metadata",
                "ok" if enabled else "warning",
                "Codex GitWarp plugin is installed and enabled." if enabled else "Codex is available but GitWarp plugin metadata was not confirmed.",
                codex=codex_path,
            )
        )
    else:
        findings.append(doctor_check("codex_plugin_metadata", "warning", "codex is not available on PATH."))

    hook_path = ctx.repo_root / "hooks" / "session-start-codex"
    if hook_path.exists() and os.access(hook_path, os.X_OK):
        result = run_command_for_doctor([str(hook_path)], ctx.repo_root, timeout=5.0)
        hook_ok = bool(result and result.returncode == 0 and "GitWarp Context:" in result.stdout)
        findings.append(
            doctor_check(
                "session_hook_context",
                "ok" if hook_ok else "warning",
                "Session hook produced a GitWarp Context block." if hook_ok else "Session hook did not produce a GitWarp Context block.",
                path=str(hook_path),
            )
        )
    else:
        findings.append(doctor_check("session_hook_context", "warning", "Session hook script is not present or executable.", path=str(hook_path)))

    emit_json(
        {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "ledger_path": str(ctx.ledger_path),
            "findings": findings,
            "summary": summarize_findings(findings),
        }
    )


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitwarp",
        description="Manage isolated git worktree sandboxes for concurrent agents.",
    )
    parser.add_argument("--version", action="version", version="gitwarp 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    return parser


def main(argv: list[str] | None = None) -> int:
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
