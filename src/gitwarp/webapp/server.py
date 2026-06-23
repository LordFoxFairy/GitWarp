from __future__ import annotations

import json
import secrets
import sys
import webbrowser
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from typing import Any

from ..domain.errors import GitWarpError
from ..infrastructure.ledger import discover_repo, register_project
from ..infrastructure.runtime import RepoContext, resolve_path
from .security import build_allowed_host_headers, host_for_url, validate_web_host
from .transport import GitWarpWebHandler


@dataclass
class WebConsoleState:
    ctx: RepoContext
    readonly: bool
    token: str
    doctor_cache: dict[str, Any]
    allowed_hosts: set[str]
    confirmation_secret: bytes
    registry_path: str


class GitWarpHTTPServer(ThreadingHTTPServer):
    state: WebConsoleState


def run_web_console(args: Any) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
    registry_path = register_project(ctx.repo_root, name=ctx.repo_root.name)
    validate_web_host(args.host, args.unsafe_host)
    if args.unsafe_host:
        print("warning: --unsafe-host allows non-loopback Web Console access", file=sys.stderr)

    try:
        server = GitWarpHTTPServer((args.host, args.port), GitWarpWebHandler)
    except OSError as exc:
        raise GitWarpError(f"failed to bind web console on {args.host}:{args.port}: {exc}") from exc

    port = int(server.server_address[1])
    token = secrets.token_urlsafe(32)
    server.state = WebConsoleState(
        ctx=ctx,
        readonly=bool(args.readonly),
        token=token,
        doctor_cache={},
        allowed_hosts=build_allowed_host_headers(args.host, port),
        confirmation_secret=secrets.token_bytes(32),
        registry_path=str(registry_path),
    )
    url = f"http://{host_for_url(args.host)}:{port}"
    print(
        json.dumps(
            {
                "ok": True,
                "url": url,
                "host": args.host,
                "port": port,
                "repo_root": str(ctx.repo_root),
                "readonly": bool(args.readonly),
                "registry_path": str(registry_path),
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
