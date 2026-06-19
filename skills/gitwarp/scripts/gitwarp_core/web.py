from __future__ import annotations

import ipaddress
import json
import secrets
import socket
import sys
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .foundation import GitWarpError, RepoContext, resolve_path
from .ledger import discover_repo
from .services import build_web_state_payload


WEB_CONSOLE_HTML = """<!doctype html>
<html lang="en" data-gitwarp-token="__TOKEN__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GitWarp Web Console</title>
  <style>
    :root { color-scheme: light; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    body { margin: 0; background: #f4efe5; color: #1f2421; }
    main { max-width: 1120px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 30px; margin: 0 0 8px; }
    .card { background: #fffaf0; border: 2px solid #1f2421; border-radius: 14px; padding: 16px; box-shadow: 5px 5px 0 #1f2421; }
    button { border: 2px solid #1f2421; background: #d96c4a; color: #fffaf0; border-radius: 10px; padding: 9px 12px; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; margin-top: 14px; }
    th, td { text-align: left; border-bottom: 1px solid #d8c8aa; padding: 9px; vertical-align: top; }
    pre { white-space: pre-wrap; background: #1f2421; color: #fffaf0; padding: 12px; border-radius: 10px; overflow: auto; }
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>GitWarp Web Console</h1>
      <p id="summary">Loading /api/state...</p>
      <button id="refresh">Refresh</button>
      <table>
        <thead><tr><th>Branch</th><th>Agent</th><th>Status</th><th>Purpose</th><th>Progress</th></tr></thead>
        <tbody id="worktrees"></tbody>
      </table>
      <pre id="raw"></pre>
    </section>
  </main>
  <script>
    const token = document.documentElement.dataset.gitwarpToken;
    async function refresh() {
      const response = await fetch('/api/state', {headers: {'X-GitWarp-Token': token}});
      const state = await response.json();
      document.querySelector('#summary').textContent =
        `${state.statusline} | doctor=${state.doctor.summary.total} reconcile=${state.reconcile.summary.total}`;
      document.querySelector('#worktrees').innerHTML = state.worktrees.map((row) =>
        `<tr><td>${row.branch || ''}</td><td>${row.agent_id || ''}</td><td>${row.status || ''}</td><td>${row.purpose || ''}</td><td>${row.latest_progress || ''}</td></tr>`
      ).join('');
      document.querySelector('#raw').textContent = JSON.stringify(state, null, 2);
    }
    document.querySelector('#refresh').addEventListener('click', refresh);
    refresh().catch((error) => { document.querySelector('#summary').textContent = String(error); });
  </script>
</body>
</html>
"""


MUTATION_ENDPOINTS = {
    "/api/init": {"required": ["write_gitignore"]},
    "/api/dispatch": {"required": ["branch", "purpose"]},
    "/api/start": {"required": ["agent_id", "branch", "purpose"]},
    "/api/handoff": {"required": ["cwd", "status", "progress"]},
    "/api/confirmation": {"required": ["action"]},
    "/api/finish": {"required": ["cwd", "status", "progress"]},
    "/api/collapse": {"required": ["confirmation"]},
}


@dataclass
class WebConsoleState:
    ctx: RepoContext
    readonly: bool
    token: str
    doctor_cache: dict[str, Any]
    allowed_hosts: set[str]
    confirmation_secret: bytes


class GitWarpHTTPServer(ThreadingHTTPServer):
    state: WebConsoleState


def _normalize_host_header(value: str) -> str:
    return value.strip().lower()


def _host_for_header(host: str, port: int) -> str:
    clean = host.strip("[]")
    if ":" in clean:
        return f"[{clean}]:{port}"
    return f"{clean}:{port}"


def _host_for_url(host: str) -> str:
    clean = host.strip("[]")
    if ":" in clean:
        return f"[{clean}]"
    return clean


def validate_web_host(host: str, unsafe: bool) -> None:
    if unsafe:
        return
    stripped = host.strip("[]")
    try:
        infos = socket.getaddrinfo(stripped, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise GitWarpError(f"web host must resolve to loopback unless --unsafe-host is used: {host}") from exc
    if not infos:
        raise GitWarpError(f"web host must resolve to loopback unless --unsafe-host is used: {host}")
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise GitWarpError(f"web host must resolve to loopback unless --unsafe-host is used: {host}") from exc
        if not ip.is_loopback:
            raise GitWarpError(f"web host must resolve only to loopback unless --unsafe-host is used: {host}")


def build_allowed_host_headers(host: str, port: int) -> set[str]:
    headers = {
        _host_for_header(host, port),
        f"127.0.0.1:{port}",
        f"localhost:{port}",
        f"[::1]:{port}",
    }
    return {_normalize_host_header(value) for value in headers}


def build_schema_payload(readonly: bool) -> dict[str, Any]:
    endpoints: dict[str, dict[str, Any]] = {
        "/api/session": {"method": "GET", "mutates": False, "required": []},
        "/api/schema": {"method": "GET", "mutates": False, "required": []},
        "/api/state": {"method": "GET", "mutates": False, "required": []},
        "/api/dossier": {"method": "GET", "mutates": False, "required": ["path"]},
    }
    endpoints.update(
        {
            path: {"method": "POST", "mutates": True, "required": spec["required"]}
            for path, spec in MUTATION_ENDPOINTS.items()
        }
    )
    return {"ok": True, "readonly": readonly, "endpoints": endpoints}


class GitWarpWebHandler(BaseHTTPRequestHandler):
    server: GitWarpHTTPServer

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def check_host(self) -> bool:
        host = self.headers.get("Host")
        if not host or _normalize_host_header(host) not in self.server.state.allowed_hosts:
            self.send_json(403, {"ok": False, "error": "invalid Host header", "code": "bad_host"})
            return False
        return True

    def parse_json_body(self) -> dict[str, Any] | None:
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            self.send_json(415, {"ok": False, "error": "mutation requests require application/json", "code": "bad_content_type"})
            return None
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            self.send_json(413, {"ok": False, "error": "request body too large", "code": "body_too_large"})
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"ok": False, "error": "invalid JSON request body", "code": "bad_json"})
            return None
        if not isinstance(payload, dict):
            self.send_json(400, {"ok": False, "error": "JSON request body must be an object", "code": "bad_json"})
            return None
        return payload

    def require_token(self) -> bool:
        if self.headers.get("X-GitWarp-Token") != self.server.state.token:
            self.send_json(403, {"ok": False, "error": "missing or invalid GitWarp token", "code": "bad_token"})
            return False
        return True

    def do_GET(self) -> None:
        if not self.check_host():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = WEB_CONSOLE_HTML.replace("__TOKEN__", self.server.state.token)
            self.send_html(200, html)
            return
        if parsed.path == "/api/session":
            self.send_json(200, {"ok": True, "token": self.server.state.token})
            return
        if parsed.path == "/api/schema":
            self.send_json(200, build_schema_payload(self.server.state.readonly))
            return
        if parsed.path == "/api/state":
            state = self.server.state
            self.send_json(
                200,
                build_web_state_payload(
                    state.ctx.cwd,
                    readonly=state.readonly,
                    doctor_cache=state.doctor_cache,
                ),
            )
            return
        self.send_json(404, {"ok": False, "error": "unknown route", "code": "not_found"})

    def do_POST(self) -> None:
        if not self.check_host():
            return
        parsed = urlparse(self.path)
        if parsed.path not in MUTATION_ENDPOINTS:
            self.send_json(404, {"ok": False, "error": "unknown route", "code": "not_found"})
            return
        if not self.require_token():
            return
        if self.parse_json_body() is None:
            return
        if self.server.state.readonly:
            self.send_json(403, {"ok": False, "error": "Web console is read-only", "code": "readonly"})
            return
        self.send_json(501, {"ok": False, "error": "mutation endpoint is not implemented yet", "code": "not_implemented"})


def run_web_console(args: Any) -> None:
    ctx = discover_repo(resolve_path(args.cwd))
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
    )
    url = f"http://{_host_for_url(args.host)}:{port}"
    print(
        json.dumps(
            {
                "ok": True,
                "url": url,
                "host": args.host,
                "port": port,
                "repo_root": str(ctx.repo_root),
                "readonly": bool(args.readonly),
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
