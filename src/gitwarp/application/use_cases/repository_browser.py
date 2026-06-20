from __future__ import annotations

import base64
import subprocess
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from ...infrastructure.runtime import GitWarpError, RepoContext, run_git
from ...infrastructure.worktrees import parse_worktrees

MAX_TEXT_BYTES = 512_000


def normalize_repository_path(raw_path: str | None) -> str:
    if raw_path in (None, "", "."):
        return ""
    if "\x00" in raw_path or raw_path.startswith("/") or "\\" in raw_path:
        raise GitWarpError("repository path must be a relative POSIX path")
    path = PurePosixPath(raw_path)
    parts = path.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise GitWarpError("repository path must not contain empty, current, or parent segments")
    if ".git" in parts:
        raise GitWarpError("refusing to expose Git internals")
    return path.as_posix()


def select_repository_checkout(ctx: RepoContext, raw_cwd: str | None) -> dict[str, Any]:
    live_worktrees = parse_worktrees(ctx)
    if not raw_cwd:
        raw_cwd = str(ctx.repo_root)
    try:
        target = str(Path(raw_cwd).expanduser().resolve())
    except OSError as exc:
        raise GitWarpError(f"invalid repository checkout path: {raw_cwd}") from exc
    for worktree in live_worktrees:
        if worktree["path"] == target:
            return worktree
    raise GitWarpError("repository checkout is not an active Git worktree")


def git_object(commit: str, repository_path: str) -> str:
    return f"{commit}^{{tree}}" if not repository_path else f"{commit}:{repository_path}"


def run_git_bytes(cwd: str, *args: str, check: bool = True) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise GitWarpError(f"failed to execute git: {exc}") from exc
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip() or result.stdout.decode("utf-8", errors="replace").strip()
        raise GitWarpError(message or "git command failed")
    return result.stdout


def read_git_blob_preview(cwd: str, object_name: str, limit: int) -> tuple[bytes, bool]:
    try:
        process = subprocess.Popen(
            ["git", "cat-file", "blob", object_name],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise GitWarpError(f"failed to execute git: {exc}") from exc

    if process.stdout is None:
        raise GitWarpError("failed to read git blob")
    preview = process.stdout.read(limit + 1)
    truncated = len(preview) > limit
    if truncated:
        process.kill()
        _, stderr = process.communicate()
        return preview[:limit], True
    _, stderr = process.communicate()
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip() or "git command failed"
        raise GitWarpError(message)
    return preview, False


def parse_tree_entries(raw: bytes, parent_path: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        meta, _, name_bytes = record.partition(b"\t")
        fields = meta.decode("ascii", errors="replace").split(" ")
        if len(fields) != 3:
            continue
        mode, object_type, object_id = fields
        name = name_bytes.decode("utf-8", errors="replace")
        path = f"{parent_path}/{name}" if parent_path else name
        entries.append(
            {
                "name": name,
                "path": path,
                "type": "directory" if object_type == "tree" else "file",
                "mode": mode,
                "object": object_id,
            }
        )
    return sorted(entries, key=lambda item: (item["type"] != "directory", item["name"].lower()))


def build_breadcrumbs(repository_path: str) -> list[dict[str, str]]:
    breadcrumbs = [{"name": "root", "path": ""}]
    current: list[str] = []
    for part in PurePosixPath(repository_path).parts if repository_path else ():
        current.append(part)
        breadcrumbs.append({"name": part, "path": "/".join(current)})
    return breadcrumbs


def build_repository_tree_payload(ctx: RepoContext, *, cwd: str | None, path: str | None) -> dict[str, Any]:
    worktree = select_repository_checkout(ctx, cwd)
    repository_path = normalize_repository_path(path)
    commit = str(worktree["head"])
    object_name = git_object(commit, repository_path)
    object_type = run_git(worktree["path"], "cat-file", "-t", object_name)
    if object_type != "tree":
        raise GitWarpError("repository path is not a directory")
    raw_entries = run_git_bytes(worktree["path"], "ls-tree", "-z", object_name)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "checkout_path": worktree["path"],
        "branch": worktree.get("branch"),
        "commit": commit,
        "path": repository_path,
        "breadcrumbs": build_breadcrumbs(repository_path),
        "entries": parse_tree_entries(raw_entries, repository_path),
    }


def build_repository_file_payload(ctx: RepoContext, *, cwd: str | None, path: str | None) -> dict[str, Any]:
    worktree = select_repository_checkout(ctx, cwd)
    repository_path = normalize_repository_path(path)
    if not repository_path:
        raise GitWarpError("repository file path is required")
    commit = str(worktree["head"])
    object_name = git_object(commit, repository_path)
    object_type = run_git(worktree["path"], "cat-file", "-t", object_name)
    if object_type != "blob":
        raise GitWarpError("repository path is not a file")
    size = int(run_git(worktree["path"], "cat-file", "-s", object_name))
    raw_content, truncated = read_git_blob_preview(worktree["path"], object_name, MAX_TEXT_BYTES)
    try:
        content = raw_content.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = base64.b64encode(raw_content).decode("ascii")
        encoding = "base64"
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "checkout_path": worktree["path"],
        "branch": worktree.get("branch"),
        "commit": commit,
        "path": repository_path,
        "name": PurePosixPath(repository_path).name,
        "size": size,
        "encoding": encoding,
        "truncated": truncated,
        "content": content,
    }
