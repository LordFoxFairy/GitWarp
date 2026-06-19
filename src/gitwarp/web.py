from __future__ import annotations

from .webapp.contracts import MUTATION_ENDPOINTS as _MUTATION_ENDPOINT_SPECS
from .webapp.contracts import build_schema_payload
from .webapp.resources import WEB_CONSOLE_HTML, render_console_html
from .webapp.security import (
    build_allowed_host_headers,
    decode_confirmation,
    encode_confirmation,
    host_for_header,
    host_for_url,
    normalize_host_header,
    validate_web_host,
)
from .webapp.server import GitWarpHTTPServer, WebConsoleState, run_web_console
from .webapp.transport import GitWarpWebHandler

MUTATION_ENDPOINTS = {
    path: {"required": list(spec.required)}
    for path, spec in _MUTATION_ENDPOINT_SPECS.items()
}

__all__ = [
    "GitWarpHTTPServer",
    "GitWarpWebHandler",
    "MUTATION_ENDPOINTS",
    "WEB_CONSOLE_HTML",
    "WebConsoleState",
    "build_allowed_host_headers",
    "build_schema_payload",
    "decode_confirmation",
    "encode_confirmation",
    "host_for_header",
    "host_for_url",
    "normalize_host_header",
    "render_console_html",
    "run_web_console",
    "validate_web_host",
]
