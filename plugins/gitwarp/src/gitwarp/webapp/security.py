from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import socket
import time
from typing import Any

from ..domain.errors import GitWarpError


def normalize_host_header(value: str) -> str:
    return value.strip().lower()


def host_for_header(host: str, port: int) -> str:
    clean = host.strip("[]")
    if ":" in clean:
        return f"[{clean}]:{port}"
    return f"{clean}:{port}"


def host_for_url(host: str) -> str:
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
        host_for_header(host, port),
        f"127.0.0.1:{port}",
        f"localhost:{port}",
        f"[::1]:{port}",
    }
    return {normalize_host_header(value) for value in headers}


def mac_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def encode_confirmation(secret: bytes, challenge: dict[str, Any], *, ttl_seconds: int = 300) -> tuple[str, int]:
    expires_at = int(time.time()) + ttl_seconds
    payload = {"challenge": challenge, "expires_at": expires_at}
    mac = hmac.new(secret, mac_payload(payload), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(
        json.dumps({"payload": payload, "mac": mac}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return token, expires_at


def decode_confirmation(secret: bytes, token: str) -> dict[str, Any]:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        envelope = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise GitWarpError("invalid confirmation token") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict) or not isinstance(envelope.get("mac"), str):
        raise GitWarpError("invalid confirmation token")
    expected = hmac.new(secret, mac_payload(envelope["payload"]), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, envelope["mac"]):
        raise GitWarpError("invalid confirmation token")
    expires_at = envelope["payload"].get("expires_at")
    if isinstance(expires_at, bool) or not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise TimeoutError("confirmation token expired")
    challenge = envelope["payload"].get("challenge")
    if not isinstance(challenge, dict):
        raise GitWarpError("invalid confirmation token")
    return challenge
