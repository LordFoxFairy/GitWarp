#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
                "created_at": meta.get("created_at"),
            }
        )
    return ledger, enriched


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "workspace"


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

    target_dir = (ctx.worktree_root / sanitize_name(args.branch)).resolve()
    if target_dir.exists():
        raise GitWarpError(f"target path already exists: {target_dir}")

    ctx.worktree_root.mkdir(parents=True, exist_ok=True)
    existing_branch = branch_exists(ctx, args.branch)
    if existing_branch:
        run_git(ctx.repo_root, "worktree", "add", str(target_dir), args.branch)
    else:
        run_git(ctx.repo_root, "worktree", "add", "-b", args.branch, str(target_dir), "HEAD")

    head = run_git(target_dir, "rev-parse", "HEAD")
    entry = {
        "path": str(target_dir),
        "branch": args.branch,
        "agent_id": args.agent_id,
        "purpose": args.purpose,
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
