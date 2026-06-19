#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEDGER_DIRNAME = ".gitwarp"
LEDGER_FILENAME = "ledger.json"
WORKTREE_DIRNAME = "worktrees"
DOSSIER_DIRNAME = "dossiers"
TASK_FILENAME = "task.md"
PROGRESS_FILENAME = "progress.md"
LESSONS_FILENAME = "lessons.md"


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
    def worktree_root(self) -> Path:
        return self.ledger_dir / WORKTREE_DIRNAME

    @property
    def dossier_root(self) -> Path:
        return self.ledger_dir / DOSSIER_DIRNAME


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


def write_ledger(ctx: RepoContext, ledger: dict[str, Any]) -> None:
    ctx.ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger["repo_root"] = str(ctx.repo_root)
    ledger["updated_at"] = now_iso()
    ctx.ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def sync_ledger(ctx: RepoContext, live_worktrees: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ledger = load_ledger(ctx)
    live_paths = {item["path"] for item in live_worktrees}
    ledger["entries"] = [entry for entry in ledger["entries"] if entry.get("path") in live_paths]
    write_ledger(ctx, ledger)

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
    ledger: dict[str, Any],
    target: dict[str, Any],
    *,
    status: str,
    progress: str,
    lesson: str | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if target.get("is_main"):
        raise GitWarpError("refusing to hand off the main repository checkout")

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
    write_ledger(ctx, ledger)
    return entry, paths


def board_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
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


def cmd_summon(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
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
    ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
    ledger["entries"].append(entry)
    write_ledger(ctx, ledger)

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
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
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
    ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != entry["path"]]
    ledger["entries"].append(entry)
    write_ledger(ctx, ledger)

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


def cmd_annotate(args: argparse.Namespace) -> None:
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
    if target.get("is_main"):
        raise GitWarpError("refusing to annotate the main repository checkout")

    target_path = target["path"]
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
    write_ledger(ctx, ledger)

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
    ledger, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    target = select_live_target(
        worktrees=worktrees,
        cwd=cwd,
        path_arg=args.path,
        branch_arg=args.branch,
    )
    entry, paths = record_handoff(
        ctx,
        ledger,
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
    rows = [board_row(item) for item in worktrees]
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
        ledger,
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
        ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != target_path]
        write_ledger(ctx, ledger)
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

    ledger["entries"] = [item for item in ledger["entries"] if item.get("path") != target_path]
    write_ledger(ctx, ledger)
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
        print("GITWARP[outside]")
        return

    _, worktrees = sync_ledger(ctx, parse_worktrees(ctx))
    cwd_str = str(cwd)
    for item in worktrees:
        path = item["path"]
        if item.get("is_main"):
            continue
        if cwd_str == path or cwd_str.startswith(path + os.sep):
            agent_id = item.get("agent_id") or "unassigned"
            branch = item.get("branch") or "detached"
            print(f"GITWARP[{agent_id}@{branch}]")
            return
    print("GITWARP[main-repo]")


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

    context = subparsers.add_parser("context", help="Print JSON context for the current worktree")
    context.add_argument("--cwd")
    context.set_defaults(func=cmd_context)

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
    board.set_defaults(func=cmd_board)

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
