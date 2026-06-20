from __future__ import annotations

import argparse

from ...application.use_cases import build_init_payload
from ...infrastructure.ledger import discover_repo
from ...infrastructure.runtime import emit_json, resolve_path


def cmd_init(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_init_payload(ctx, write_gitignore=args.write_gitignore))


def cmd_web(args: argparse.Namespace) -> None:
    from ...webapp.server import run_web_console

    run_web_console(args)
