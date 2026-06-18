#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path


def default_destination() -> Path:
    return Path.home() / ".local" / "bin" / "gitwarp"


def write_launcher(destination: Path, script_path: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    launcher = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f'exec python3 "{script_path}" "$@"',
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
    args = build_parser().parse_args()
    script_path = (Path(__file__).resolve().parent / "gitwarp.py").resolve()
    destination = Path(args.dest).expanduser().resolve()
    write_launcher(destination, script_path)
    path_entries = [Path(entry).expanduser().resolve() for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    payload = {
        "ok": True,
        "command": str(destination),
        "script": str(script_path),
        "on_path": destination.parent in path_entries,
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
