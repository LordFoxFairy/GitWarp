from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from ...domain.errors import GitWarpError
from .runtime_sync import build_upgrade_payload, default_launcher_destination, current_package_root


DEFAULT_REPOSITORY_URL = "git+https://github.com/LordFoxFairy/GitWarp.git"
INSTALL_TIMEOUT_SECONDS = 120.0


def normalize_install_target(raw: str) -> str:
    value = raw.strip().lower().replace("_", "-")
    aliases = {
        "cc": "claude-code",
        "claude": "claude-code",
        "claudecode": "claude-code",
        "claude-code": "claude-code",
        "codex": "codex",
        "self": "self",
        "gitwarp": "self",
    }
    try:
        return aliases[value]
    except KeyError as exc:
        raise GitWarpError("install target must be one of: self, codex, claude-code") from exc


def source_root_from_package() -> Path:
    return current_package_root().parent.resolve()


def shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def parse_json_output(raw: str) -> dict[str, Any]:
    start = raw.find("{")
    if start < 0:
        return {"raw": raw.strip()}
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError:
        return {"raw": raw.strip()}


def run_checked(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=INSTALL_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitWarpError(f"install command timed out: {shell_join(command)}") from exc
    except OSError as exc:
        raise GitWarpError(f"failed to execute install command: {exc}") from exc

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "install command failed"
        raise GitWarpError(message)

    payload = parse_json_output(result.stdout)
    payload.setdefault("raw_stdout", result.stdout.strip())
    return payload


def self_install_command(method: str, source: str | None, destination: Path | None) -> list[str]:
    if method == "launcher":
        command = ["gitwarp", "upgrade"]
        if destination is not None:
            command.extend(["--dest", str(destination)])
        return command
    if method == "pipx":
        return ["python3", "-m", "pipx", "install", source or DEFAULT_REPOSITORY_URL]
    if method == "pip":
        return [sys.executable, "-m", "pip", "install", source or DEFAULT_REPOSITORY_URL]
    raise GitWarpError("self install method must be one of: launcher, pipx, pip")


def build_self_install_payload(
    *,
    method: str,
    source: str | None,
    destination: Path | None,
    dry_run: bool,
) -> dict[str, Any]:
    resolved_destination = destination or default_launcher_destination()
    command = self_install_command(method, source, resolved_destination if method == "launcher" else None)
    if dry_run:
        return {
            "ok": True,
            "target": "self",
            "method": method,
            "dry_run": True,
            "command": command,
            "shell_command": shell_join(command),
            "recommended_next": [
                "Run without --dry-run to execute the selected installation method.",
                "Use pipx for an isolated global install, pip for the active Python environment, or launcher for this checkout/plugin runtime.",
            ],
        }

    if method == "launcher":
        payload = build_upgrade_payload(resolved_destination, check=False)
    else:
        payload = run_checked(command)
    return {
        "ok": True,
        "target": "self",
        "method": method,
        "dry_run": False,
        "command": command,
        "shell_command": shell_join(command),
        "result": payload,
        "recommended_next": payload.get("recommended_next", []) if isinstance(payload, dict) else [],
    }


def host_installer_script(target: str, source_root: Path) -> Path:
    name = "claude" if target == "claude-code" else target
    return source_root / "scripts" / f"install-{name}-plugin.sh"


def build_host_install_payload(
    *,
    target: str,
    source: Path | None,
    dry_run: bool,
    scope: str,
) -> dict[str, Any]:
    source_root = (source or source_root_from_package()).expanduser().resolve()
    script = host_installer_script(target, source_root)
    command = [str(script)]
    env = os.environ.copy()
    if target == "claude-code":
        env["CLAUDE_PLUGIN_SCOPE"] = scope

    payload: dict[str, Any] = {
        "ok": True,
        "target": target,
        "dry_run": dry_run,
        "source_root": str(source_root),
        "script": str(script),
        "command": command,
        "shell_command": shell_join(command),
        "recommended_next": [],
    }

    if dry_run:
        payload["recommended_next"] = [f"Run {shell_join(command)} to install the {target} plugin."]
        if not script.exists():
            payload["warning"] = "installer script does not exist at source_root"
        return payload

    if not script.is_file():
        raise GitWarpError(f"installer script is missing: {script}")

    result = run_checked(command, env=env)
    payload["result"] = result
    if isinstance(result, dict):
        payload["recommended_next"] = result.get("recommended_next", [])
    return payload


def build_install_payload(
    raw_target: str,
    *,
    method: str = "launcher",
    source: Path | None = None,
    source_text: str | None = None,
    destination: Path | None = None,
    dry_run: bool = False,
    scope: str = "user",
) -> dict[str, Any]:
    target = normalize_install_target(raw_target)
    if target == "self":
        return build_self_install_payload(
            method=method,
            source=source_text or (str(source.expanduser().resolve()) if source is not None else None),
            destination=destination,
            dry_run=dry_run,
        )
    return build_host_install_payload(target=target, source=source, dry_run=dry_run, scope=scope)
