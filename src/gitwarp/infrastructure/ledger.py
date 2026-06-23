from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from .runtime import (
    GitWarpError,
    LEDGER_FILENAME,
    LOCK_TIMEOUT_SECONDS,
    RepoContext,
    now_iso,
    project_registry_path,
    run_git,
)


def default_ledger(ctx: RepoContext) -> dict[str, Any]:
    return {"version": 1, "repo_root": str(ctx.repo_root), "entries": []}


def normalize_ledger_schema(data: Any, ctx: RepoContext) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise GitWarpError(f"invalid ledger schema: {ctx.ledger_path}")
    version = data.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise GitWarpError(f"invalid ledger schema: {ctx.ledger_path}")
    repo_root = data.get("repo_root", str(ctx.repo_root))
    if not isinstance(repo_root, str):
        raise GitWarpError(f"invalid ledger schema: {ctx.ledger_path}")
    if "entries" not in data or not isinstance(data["entries"], list):
        raise GitWarpError(f"invalid ledger schema: {ctx.ledger_path}")
    data["version"] = 1
    data["repo_root"] = str(ctx.repo_root)
    return data


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
        return default_ledger(ctx)
    try:
        data = json.loads(ctx.ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GitWarpError(f"invalid ledger file: {ctx.ledger_path}") from exc
    return normalize_ledger_schema(data, ctx)


def load_raw_ledger(ctx: RepoContext) -> dict[str, Any]:
    return load_ledger(ctx)


def load_project_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or project_registry_path()
    if not registry_path.exists():
        return {"version": 1, "projects": []}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GitWarpError(f"invalid project registry: {registry_path}") from exc
    if not isinstance(data, dict) or data.get("version", 1) != 1 or not isinstance(data.get("projects"), list):
        raise GitWarpError(f"invalid project registry: {registry_path}")
    projects: list[dict[str, Any]] = []
    for item in data["projects"]:
        if not isinstance(item, dict):
            raise GitWarpError(f"invalid project registry: {registry_path}")
        repo_root = item.get("repo_root")
        name = item.get("name")
        if not isinstance(repo_root, str) or not repo_root:
            raise GitWarpError(f"invalid project registry: {registry_path}")
        if not isinstance(name, str) or not name:
            raise GitWarpError(f"invalid project registry: {registry_path}")
        project: dict[str, Any] = {"repo_root": repo_root, "name": name}
        last_opened_at = item.get("last_opened_at")
        if isinstance(last_opened_at, str) and last_opened_at:
            project["last_opened_at"] = last_opened_at
        projects.append(project)
    return {"version": 1, "projects": projects}


def write_project_registry(registry: dict[str, Any], path: Path | None = None) -> Path:
    registry_path = path or project_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return registry_path


def register_project(repo_root: Path, *, name: str | None = None, path: Path | None = None) -> Path:
    registry_path = path or project_registry_path()
    registry = load_project_registry(registry_path)
    repo_key = str(repo_root)
    project_name = name or repo_root.name
    last_opened_at = now_iso()
    projects = [item for item in registry["projects"] if item.get("repo_root") != repo_key]
    projects.insert(
        0,
        {
            "repo_root": repo_key,
            "name": project_name,
            "last_opened_at": last_opened_at,
        },
    )
    write_project_registry({"version": 1, "projects": projects}, registry_path)
    return registry_path


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def lock_owner_is_alive(raw_lock: str) -> bool:
    try:
        metadata = json.loads(raw_lock)
    except json.JSONDecodeError:
        return False
    pid = metadata.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int):
        return False
    return process_is_alive(pid)


def break_stale_lock(ctx: RepoContext) -> bool:
    try:
        raw_lock = ctx.ledger_lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    if lock_owner_is_alive(raw_lock):
        return False
    try:
        if ctx.ledger_lock_path.read_text(encoding="utf-8") != raw_lock:
            return False
        ctx.ledger_lock_path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


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
                if break_stale_lock(ctx):
                    deadline = time.monotonic() + timeout
                    continue
                raise GitWarpError(f"timed out waiting for live ledger lock: {ctx.ledger_lock_path}")
            time.sleep(0.025)
    try:
        yield
    finally:
        try:
            ctx.ledger_lock_path.unlink()
        except FileNotFoundError:
            pass


def write_ledger(ctx: RepoContext, ledger: dict[str, Any], *, touch_updated_at: bool = True) -> None:
    temp_path: Path | None = None
    try:
        ctx.ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger["repo_root"] = str(ctx.repo_root)
        if touch_updated_at:
            ledger["updated_at"] = now_iso()
        temp_path = ctx.ledger_dir / f".{LEDGER_FILENAME}.{os.getpid()}.{time.monotonic_ns()}.tmp"
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(ctx.ledger_path)
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise GitWarpError(f"failed to write ledger {ctx.ledger_path}: {exc}") from exc


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
