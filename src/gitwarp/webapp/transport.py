from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..application.use_cases import (
    build_branches_payload,
    build_matrix_payload,
    build_repository_file_payload,
    build_repository_tree_payload,
    build_web_state_payload,
)
from ..domain.errors import GitWarpError
from ..infrastructure.ledger import discover_repo
from ..infrastructure.runtime import resolve_path
from .contracts import (
    MUTATION_ENDPOINTS,
    PayloadValidationError,
    build_schema_payload,
    validate_mutation_payload,
)
from .controllers import BadConfirmation, ConfirmationRequired, StaleConfirmation, handle_mutation
from .resources import read_dossier_file, render_console_html
from .security import normalize_host_header


class GitWarpWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

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

    def send_empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def check_host(self) -> bool:
        host = self.headers.get("Host")
        if not host or normalize_host_header(host) not in self.server.state.allowed_hosts:
            self.send_json(403, {"ok": False, "error": "invalid Host header", "code": "bad_host"})
            return False
        return True

    def parse_json_body(self) -> dict[str, Any] | None:
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            self.send_json(415, {"ok": False, "error": "mutation requests require application/json", "code": "bad_content_type"})
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"ok": False, "error": "Content-Length must be an integer", "code": "bad_content_length"})
            return None
        if length < 0:
            self.send_json(400, {"ok": False, "error": "Content-Length must not be negative", "code": "bad_content_length"})
            return None
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

    def send_dossier(self, query: str) -> None:
        values = parse_qs(query)
        raw_path = values.get("path", [None])[0]
        raw_cwd = values.get("cwd", [str(self.server.state.ctx.repo_root)])[0] or str(self.server.state.ctx.repo_root)
        try:
            ctx = discover_repo(resolve_path(raw_cwd))
            payload = read_dossier_file(raw_path, ctx.dossier_root)
        except PermissionError:
            self.send_json(403, {"ok": False, "error": "path is outside GitWarp dossier root", "code": "outside_dossier_root"})
            return
        except FileNotFoundError:
            target = str(Path(raw_path or "").expanduser().resolve()) if raw_path else ""
            self.send_json(404, {"ok": False, "error": "dossier file not found", "code": "not_found", "path": target})
            return
        except GitWarpError as exc:
            self.send_json(400, {"ok": False, "error": str(exc), "code": "missing_path"})
            return
        self.send_json(200, payload)

    def send_repository_tree(self, query: str) -> None:
        values = parse_qs(query)
        raw_cwd = values.get("cwd", [str(self.server.state.ctx.repo_root)])[0] or str(self.server.state.ctx.repo_root)
        try:
            ctx = discover_repo(resolve_path(raw_cwd))
            payload = build_repository_tree_payload(
                ctx,
                cwd=values.get("cwd", [None])[0],
                path=values.get("path", [None])[0],
            )
        except GitWarpError as exc:
            self.send_json(400, {"ok": False, "error": str(exc), "code": "bad_repository_path"})
            return
        self.send_json(200, payload)

    def send_repository_file(self, query: str) -> None:
        values = parse_qs(query)
        raw_cwd = values.get("cwd", [str(self.server.state.ctx.repo_root)])[0] or str(self.server.state.ctx.repo_root)
        try:
            ctx = discover_repo(resolve_path(raw_cwd))
            payload = build_repository_file_payload(
                ctx,
                cwd=values.get("cwd", [None])[0],
                path=values.get("path", [None])[0],
            )
        except GitWarpError as exc:
            self.send_json(400, {"ok": False, "error": str(exc), "code": "bad_repository_path"})
            return
        self.send_json(200, payload)

    def send_branches(self, query: str) -> None:
        values = parse_qs(query)
        try:
            cwd = values.get("cwd", [str(self.server.state.ctx.repo_root)])[0] or str(self.server.state.ctx.repo_root)
            ctx = discover_repo(resolve_path(cwd))
            payload = build_branches_payload(
                ctx,
                base_branch=values.get("base", [None])[0],
            )
        except GitWarpError as exc:
            self.send_json(400, {"ok": False, "error": str(exc), "code": "bad_branch_query"})
            return
        self.send_json(200, payload)

    def send_matrix(self, query: str) -> None:
        values = parse_qs(query)
        try:
            cwd = values.get("cwd", [str(self.server.state.ctx.repo_root)])[0] or str(self.server.state.ctx.repo_root)
            ctx = discover_repo(resolve_path(cwd))
            payload = build_matrix_payload(
                ctx,
                base_branch=values.get("base", [None])[0],
            )
        except GitWarpError as exc:
            self.send_json(400, {"ok": False, "error": str(exc), "code": "bad_matrix_query"})
            return
        self.send_json(200, payload)

    def do_GET(self) -> None:
        if not self.check_host():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html(200, render_console_html(self.server.state.token))
            return
        if parsed.path == "/favicon.ico":
            self.send_empty(204)
            return
        if parsed.path == "/api/session":
            self.send_json(200, {"ok": True, "token": self.server.state.token})
            return
        if parsed.path == "/api/schema":
            self.send_json(200, build_schema_payload(self.server.state.readonly))
            return
        if parsed.path == "/api/state":
            state = self.server.state
            values = parse_qs(parsed.query)
            cwd = values.get("cwd", [str(state.ctx.repo_root)])[0] or str(state.ctx.repo_root)
            try:
                payload = build_web_state_payload(
                    cwd,
                    readonly=state.readonly,
                    doctor_cache=state.doctor_cache,
                )
            except GitWarpError as exc:
                self.send_json(400, {"ok": False, "error": str(exc), "code": "bad_state_query"})
                return
            self.send_json(200, payload)
            return
        if parsed.path == "/api/dossier":
            self.send_dossier(parsed.query)
            return
        if parsed.path == "/api/repository/tree":
            if not self.require_token():
                return
            self.send_repository_tree(parsed.query)
            return
        if parsed.path == "/api/repository/file":
            if not self.require_token():
                return
            self.send_repository_file(parsed.query)
            return
        if parsed.path == "/api/branches":
            if not self.require_token():
                return
            self.send_branches(parsed.query)
            return
        if parsed.path == "/api/matrix":
            if not self.require_token():
                return
            self.send_matrix(parsed.query)
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
        payload = self.parse_json_body()
        if payload is None:
            return
        if self.server.state.readonly:
            self.send_json(403, {"ok": False, "error": "Web console is read-only", "code": "readonly"})
            return
        try:
            validate_mutation_payload(parsed.path, payload)
        except PayloadValidationError as exc:
            self.send_json(400, {"ok": False, "error": str(exc), "code": "bad_payload"})
            return
        try:
            mutation_cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) and payload.get("cwd") else str(self.server.state.ctx.repo_root)
            mutation_ctx = discover_repo(resolve_path(str(mutation_cwd)))
            result = handle_mutation(
                parsed.path,
                mutation_ctx,
                payload,
                confirmation_secret=self.server.state.confirmation_secret,
            )
        except ConfirmationRequired as exc:
            self.send_json(403, {"ok": False, "error": str(exc), "code": "confirmation_required"})
            return
        except TimeoutError as exc:
            self.send_json(403, {"ok": False, "error": str(exc), "code": "confirmation_expired"})
            return
        except BadConfirmation as exc:
            self.send_json(403, {"ok": False, "error": str(exc), "code": "bad_confirmation"})
            return
        except StaleConfirmation as exc:
            self.send_json(409, {"ok": False, "error": str(exc), "code": "stale_confirmation"})
            return
        except GitWarpError as exc:
            self.send_json(400, {"ok": False, "error": str(exc), "code": "gitwarp_error"})
            return
        self.send_json(200, result)
