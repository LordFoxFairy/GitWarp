#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import stat
import sys
from pathlib import Path

MIN_PYTHON = (3, 10)
ENTRYPOINT_MODULE = "gitwarp.adapters.cli.entrypoint"


def default_destination() -> Path:
    return Path.home() / ".local" / "bin" / "gitwarp"


def candidate_package_roots(installer_path: Path) -> list[Path]:
    here = installer_path.resolve()
    candidates: list[Path] = []
    for index in (3, 2):
        if len(here.parents) > index:
            candidates.append(here.parents[index] / "src")

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped


def find_package_root(installer_path: Path) -> Path | None:
    for candidate in candidate_package_roots(installer_path):
        if (candidate / "gitwarp" / "adapters" / "cli" / "entrypoint.py").is_file():
            return candidate
    return None


def entrypoint_is_importable() -> bool:
    return importlib.util.find_spec(ENTRYPOINT_MODULE) is not None


def write_launcher(destination: Path, package_root: Path | None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
    ]
    if package_root is not None:
        lines.append(f"export PYTHONPATH={shlex.quote(str(package_root))}${{PYTHONPATH:+\":$PYTHONPATH\"}}")
    lines.extend(
        [
            f"exec {shlex.quote(sys.executable)} -m {shlex.quote(ENTRYPOINT_MODULE)} \"$@\"",
            "",
        ]
    )
    launcher = "\n".join(lines)
    destination.write_text(launcher, encoding="utf-8")
    destination.chmod(
        destination.stat().st_mode
        | stat.S_IXUSR
        | stat.S_IXGRP
        | stat.S_IXOTH
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", default=str(default_destination()))
    return parser


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "GitWarp requires Python 3.10 or newer.",
                    "python": sys.version.split()[0],
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1

    args = build_parser().parse_args()
    installer_path = Path(__file__).resolve()
    package_root = find_package_root(installer_path)
    destination = Path(args.dest).expanduser().resolve()
    if package_root is None and not entrypoint_is_importable():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "could not locate the GitWarp Python package; install from a full plugin/source checkout or install the package first.",
                    "module": ENTRYPOINT_MODULE,
                    "searched": [str(path) for path in candidate_package_roots(installer_path)],
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    try:
        write_launcher(destination, package_root)
    except OSError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"failed to write launcher: {exc}",
                    "command": str(destination),
                    "module": ENTRYPOINT_MODULE,
                    "package_root": str(package_root) if package_root is not None else None,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    path_entries = [Path(entry).expanduser().resolve() for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    on_path = destination.parent in path_entries
    recommended_next = []
    if not on_path:
        recommended_next.append(f"Add {destination.parent} to PATH or run gitwarp with {destination}.")
    payload = {
        "ok": True,
        "command": str(destination),
        "module": ENTRYPOINT_MODULE,
        "package_root": str(package_root) if package_root is not None else None,
        "on_path": on_path,
        "python": sys.executable,
        "recommended_next": recommended_next,
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
