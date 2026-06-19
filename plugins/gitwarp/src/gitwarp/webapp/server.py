from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..foundation import RepoContext


@dataclass
class WebConsoleState:
    ctx: RepoContext
    readonly: bool
    token: str
    doctor_cache: dict[str, Any]
    allowed_hosts: set[str]
    confirmation_secret: bytes
