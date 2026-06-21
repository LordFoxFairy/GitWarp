from __future__ import annotations

import argparse

from ...application.use_cases import build_init_payload, build_install_payload, build_upgrade_payload
from ...infrastructure.ledger import discover_repo
from ...infrastructure.runtime import emit_json, resolve_path


def cmd_init(args: argparse.Namespace) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    emit_json(build_init_payload(ctx, write_gitignore=args.write_gitignore))


def cmd_install(args: argparse.Namespace) -> None:
    installs_self = args.target in {"self", "gitwarp"}
    source = resolve_path(args.source) if args.source and not installs_self else None
    source_text = args.source if installs_self else None
    destination = resolve_path(args.dest) if args.dest else None
    emit_json(
        build_install_payload(
            args.target,
            method=args.method,
            source=source,
            source_text=source_text,
            destination=destination,
            dry_run=args.dry_run,
            scope=args.scope,
        )
    )


def cmd_upgrade(args: argparse.Namespace) -> None:
    destination = resolve_path(args.dest) if args.dest else None
    emit_json(build_upgrade_payload(destination, check=args.check))


def cmd_web(args: argparse.Namespace) -> None:
    from ...webapp.server import run_web_console

    run_web_console(args)
