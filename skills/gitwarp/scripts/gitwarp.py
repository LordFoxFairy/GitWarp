#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def candidate_package_roots() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        here.parents[3] / "src",
        here.parents[5] / "src" if len(here.parents) > 5 else here.parents[3] / "src",
    ]


for root in candidate_package_roots():
    if (root / "gitwarp" / "cli.py").exists():
        sys.path.insert(0, str(root))
        break

from gitwarp.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
