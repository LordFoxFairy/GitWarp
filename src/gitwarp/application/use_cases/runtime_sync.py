from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import gitwarp as gitwarp_package

from ...domain.errors import GitWarpError


ENTRYPOINT_MODULE = ".".join(("gitwarp", "adapters", "cli", "entrypoint"))
PROBE_TIMEOUT_SECONDS = 5.0
REQUIRED_LAUNCHER_PROBES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("version", ("--version",)),
    ("install", ("install", "--help")),
    ("upgrade", ("upgrade", "--help")),
    ("task_create", ("task", "create", "--help")),
    ("next", ("next", "--help")),
    ("sweep", ("sweep", "--help")),
)


def default_launcher_destination() -> Path:
    return (Path.home() / ".local" / "bin" / "gitwarp").expanduser().resolve()


def current_package_root() -> Path:
    return Path(gitwarp_package.__file__).resolve().parent.parent


def _path_entries() -> list[Path]:
    return [Path(entry).expanduser().resolve() for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]


def launcher_on_path(destination: Path) -> bool:
    return destination.expanduser().resolve().parent in _path_entries()


def compact_output(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped.splitlines()[0][:240]


def run_launcher_probe(destination: Path, name: str, args: tuple[str, ...]) -> dict[str, Any]:
    probe: dict[str, Any] = {"name": name, "args": list(args), "ok": False}
    if not destination.exists():
        probe["error"] = "launcher is missing"
        probe["returncode"] = None
        return probe
    try:
        result = subprocess.run(
            [str(destination), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        probe["error"] = "probe timed out"
        probe["returncode"] = None
        return probe
    except OSError as exc:
        probe["error"] = str(exc)
        probe["returncode"] = None
        return probe

    probe["returncode"] = result.returncode
    probe["ok"] = result.returncode == 0
    stdout = compact_output(result.stdout)
    stderr = compact_output(result.stderr)
    if stdout:
        probe["stdout"] = stdout
    if stderr:
        probe["stderr"] = stderr
    return probe


def inspect_launcher(destination: Path | None = None) -> dict[str, Any]:
    if destination is None:
        discovered = shutil.which("gitwarp")
        destination = Path(discovered).expanduser().resolve() if discovered else default_launcher_destination()
    else:
        destination = destination.expanduser().resolve()

    exists = destination.is_file()
    executable = bool(exists and os.access(destination, os.X_OK))
    probes = [run_launcher_probe(destination, name, args) for name, args in REQUIRED_LAUNCHER_PROBES] if exists else []
    upgrade_required = not exists or not executable or any(not probe["ok"] for probe in probes)
    if not exists:
        status = "missing"
    elif upgrade_required:
        status = "stale"
    else:
        status = "current"
    return {
        "command": str(destination),
        "exists": exists,
        "executable": executable,
        "status": status,
        "upgrade_required": upgrade_required,
        "probes": probes,
        "on_path": launcher_on_path(destination),
    }


def launcher_text(package_root: Path) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"export PYTHONPATH={shlex.quote(str(package_root))}${{PYTHONPATH:+\":$PYTHONPATH\"}}",
            f"exec {shlex.quote(sys.executable)} -m {shlex.quote(ENTRYPOINT_MODULE)} \"$@\"",
            "",
        ]
    )


def write_launcher(destination: Path, package_root: Path) -> None:
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(launcher_text(package_root), encoding="utf-8")
        temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(temporary, destination)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise GitWarpError(f"failed to write gitwarp launcher: {exc}") from exc


def module_upgrade_command(destination: Path) -> str:
    package_root = current_package_root()
    return " ".join(
        [
            f"PYTHONPATH={shlex.quote(str(package_root))}",
            shlex.quote(sys.executable),
            "-m",
            shlex.quote(ENTRYPOINT_MODULE),
            "upgrade",
            "--dest",
            shlex.quote(str(destination.expanduser().resolve())),
        ]
    )


def build_upgrade_payload(destination: Path | None = None, *, check: bool = False) -> dict[str, Any]:
    package_root = current_package_root()
    resolved_destination = (destination or default_launcher_destination()).expanduser().resolve()
    before = inspect_launcher(resolved_destination)

    if check:
        status = before["status"]
        probes = before["probes"]
        upgrade_required = before["upgrade_required"]
    else:
        write_launcher(resolved_destination, package_root)
        after = inspect_launcher(resolved_destination)
        if after["upgrade_required"]:
            raise GitWarpError(f"gitwarp launcher was written but failed validation: {after['probes']}")
        status = "written"
        probes = after["probes"]
        upgrade_required = False

    recommended_next: list[str] = []
    if check and upgrade_required:
        recommended_next.append(f'gitwarp upgrade --dest "{resolved_destination}"')
    if not launcher_on_path(resolved_destination):
        recommended_next.append(f"Add {resolved_destination.parent} to PATH or run gitwarp with {resolved_destination}.")

    return {
        "ok": True,
        "command": str(resolved_destination),
        "module": ENTRYPOINT_MODULE,
        "package_root": str(package_root),
        "python": sys.executable,
        "check": check,
        "status": status,
        "upgrade_required": upgrade_required,
        "on_path": launcher_on_path(resolved_destination),
        "probes": probes,
        "recommended_next": recommended_next,
    }
