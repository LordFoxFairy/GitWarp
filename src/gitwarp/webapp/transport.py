from __future__ import annotations

from http.server import BaseHTTPRequestHandler


class JsonHttpHandler(BaseHTTPRequestHandler):
    """Marker base for GitWarp web transport handlers."""
