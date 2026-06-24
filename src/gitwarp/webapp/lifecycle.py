from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

DEVNULL = subprocess.DEVNULL

from ..domain.errors import GitWarpError
from ..infrastructure.ledger import discover_repo, process_is_alive
from ..infrastructure.runtime import RepoContext, global_web_state_path, now_iso, resolve_path

WEB_STATE_FILENAME = "web-console-state.json"
DEFAULT_PUBLIC_WEB_HOST = "127.0.0.1"
DEFAULT_PUBLIC_WEB_PORT = 6006


def web_state_path(ctx: RepoContext) -> Path:
    return ctx.ledger_dir / WEB_STATE_FILENAME


def load_global_web_state() -> dict[str, Any] | None:
    path = global_web_state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GitWarpError(f"invalid global web state file: {path}") from exc
    if not isinstance(data, dict):
        raise GitWarpError(f"invalid global web state file: {path}")
    return data


def write_global_web_state(payload: dict[str, Any]) -> Path:
    path = global_web_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def remove_global_web_state() -> None:
    try:
        global_web_state_path().unlink()
    except FileNotFoundError:
        pass


def load_web_state(ctx: RepoContext) -> dict[str, Any] | None:
    path = web_state_path(ctx)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GitWarpError(f"invalid web state file: {path}") from exc
    if not isinstance(data, dict):
        raise GitWarpError(f"invalid web state file: {path}")
    return data


def write_web_state(ctx: RepoContext, payload: dict[str, Any]) -> Path:
    path = web_state_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def remove_web_state(ctx: RepoContext) -> None:
    try:
        web_state_path(ctx).unlink()
    except FileNotFoundError:
        pass


def same_web_process(ctx: RepoContext, state: dict[str, Any]) -> bool:
    pid = state.get("pid")
    if not isinstance(pid, int) or not process_is_alive(pid):
        return False
    repo_root = state.get("repo_root")
    if not isinstance(repo_root, str) or repo_root != str(ctx.repo_root):
        return False
    return True


def build_web_status_payload(ctx: RepoContext) -> dict[str, Any]:
    state = load_web_state(ctx)
    if state is None:
        return {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "running": False,
            "state_path": str(web_state_path(ctx)),
            "global_state_path": str(global_web_state_path()),
        }
    running = same_web_process(ctx, state)
    if not running:
        return {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "running": False,
            "state_path": str(web_state_path(ctx)),
            "global_state_path": str(global_web_state_path()),
            "stale": True,
            **state,
        }
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "running": True,
        "state_path": str(web_state_path(ctx)),
        "global_state_path": str(global_web_state_path()),
        **state,
    }


def start_web_console_service(args: Any) -> dict[str, Any]:
    ctx = discover_repo(resolve_path(args.cwd))
    current = load_web_state(ctx)
    if current is not None:
        if same_web_process(ctx, current):
            return {
                "ok": True,
                "repo_root": str(ctx.repo_root),
                "running": True,
                "already_running": True,
                "replaced_existing": False,
                "state_path": str(web_state_path(ctx)),
                "global_state_path": str(global_web_state_path()),
                **current,
            }
        remove_web_state(ctx)

    replaced_existing = False
    global_state = load_global_web_state()
    if global_state is not None:
        global_pid = global_state.get("pid")
        global_repo_root = global_state.get("repo_root")
        if isinstance(global_pid, int) and process_is_alive(global_pid):
            if global_repo_root == str(ctx.repo_root):
                return {
                    "ok": True,
                    "repo_root": str(ctx.repo_root),
                    "running": True,
                    "already_running": True,
                    "replaced_existing": False,
                    "state_path": str(web_state_path(ctx)),
                    "global_state_path": str(global_web_state_path()),
                    **global_state,
                }
            os.kill(global_pid, signal.SIGTERM)
            deadline = time.time() + 5.0
            while time.time() < deadline and process_is_alive(global_pid):
                time.sleep(0.05)
            replaced_existing = True
        remove_global_web_state()

    effective_port = DEFAULT_PUBLIC_WEB_PORT if int(args.port) == 0 else int(args.port)
    command = [
        sys.executable,
        "-m",
        "gitwarp.adapters.cli.entrypoint",
        "web",
        "start",
        "--cwd",
        str(ctx.repo_root),
        "--host",
        str(args.host),
        "--port",
        str(effective_port),
        "--serve-internal",
    ]
    if args.no_open:
        command.append("--no-open")
    if args.readonly:
        command.append("--readonly")
    if args.unsafe_host:
        command.append("--unsafe-host")

    env = os.environ.copy()
    result = subprocess.Popen(
        command,
        cwd=str(ctx.repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=DEVNULL,
        text=True,
    )
    assert result.stdout is not None
    line = result.stdout.readline().strip()
    if not line:
        stderr = result.stderr.read().strip() if result.stderr else ""
        raise GitWarpError(f"web start failed: {stderr or 'missing readiness JSON'}")
    try:
        readiness = json.loads(line)
    except json.JSONDecodeError as exc:
        raise GitWarpError(f"web start emitted invalid readiness JSON: {line}") from exc
    if readiness.get("ok") is not True:
        raise GitWarpError(str(readiness.get("error") or "web start failed"))
    state = {
        "pid": result.pid,
        "host": readiness.get("host"),
        "port": readiness.get("port"),
        "url": readiness.get("url"),
        "backend_url": readiness.get("backend_url", readiness.get("url")),
        "public_url": readiness.get("public_url", readiness.get("url")),
        "public_port": readiness.get("public_port", readiness.get("port")),
        "repo_root": readiness.get("repo_root"),
        "active_repo_root": readiness.get("active_repo_root", readiness.get("repo_root")),
        "readonly": readiness.get("readonly"),
        "registry_path": readiness.get("registry_path"),
        "command": command,
        "started_at": now_iso(),
    }
    write_web_state(ctx, state)
    write_global_web_state(state)
    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "running": True,
        "started": True,
        "already_running": False,
        "replaced_existing": replaced_existing,
        "state_path": str(web_state_path(ctx)),
        "global_state_path": str(global_web_state_path()),
        **state,
    }


def stop_web_console_service(args: Any) -> dict[str, Any]:
    ctx = discover_repo(resolve_path(args.cwd))
    state = load_web_state(ctx)
    if state is None:
        return {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "running": False,
            "stopped": False,
            "state_path": str(web_state_path(ctx)),
            "global_state_path": str(global_web_state_path()),
        }
    pid = state.get("pid")
    if not isinstance(pid, int) or not process_is_alive(pid):
        remove_web_state(ctx)
        remove_global_web_state()
        return {
            "ok": True,
            "repo_root": str(ctx.repo_root),
            "running": False,
            "stopped": False,
            "stale": True,
            "state_path": str(web_state_path(ctx)),
            "global_state_path": str(global_web_state_path()),
            **state,
        }
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if not process_is_alive(pid):
            remove_web_state(ctx)
            remove_global_web_state()
            return {
                "ok": True,
                "repo_root": str(ctx.repo_root),
                "running": False,
                "stopped": True,
                "state_path": str(web_state_path(ctx)),
                "global_state_path": str(global_web_state_path()),
                **state,
            }
        time.sleep(0.05)
    raise GitWarpError(f"timed out waiting for web console pid {pid} to stop")
