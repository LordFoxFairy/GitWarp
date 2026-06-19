#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import stat
import sys
from pathlib import Path

MIN_PYTHON = (3, 10)


def default_destination() -> Path:
    return Path.home() / ".local" / "bin" / "gitwarp"


def write_launcher(destination: Path, script_path: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    launcher = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"exec {shlex.quote(sys.executable)} {shlex.quote(str(script_path))} \"$@\"",
            "",
        ]
    )
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
    script_path = (Path(__file__).resolve().parent / "gitwarp.py").resolve()
    destination = Path(args.dest).expanduser().resolve()
    try:
        write_launcher(destination, script_path)
    except OSError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"failed to write launcher: {exc}",
                    "command": str(destination),
                    "script": str(script_path),
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
        "script": str(script_path),
        "on_path": on_path,
        "python": sys.executable,
        "recommended_next": recommended_next,
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
