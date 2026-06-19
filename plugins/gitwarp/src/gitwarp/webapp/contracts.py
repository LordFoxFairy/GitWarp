from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EndpointSpec:
    method: str
    mutates: bool
    required: tuple[str, ...] = ()


MUTATION_ENDPOINTS: dict[str, EndpointSpec] = {
    "/api/init": EndpointSpec("POST", True, ("write_gitignore",)),
    "/api/dispatch": EndpointSpec("POST", True, ("branch", "purpose")),
    "/api/start": EndpointSpec("POST", True, ("agent_id", "branch", "purpose")),
    "/api/handoff": EndpointSpec("POST", True, ("cwd", "status", "progress")),
    "/api/confirmation": EndpointSpec("POST", True, ("action",)),
    "/api/finish": EndpointSpec("POST", True, ("cwd", "status", "progress")),
    "/api/collapse": EndpointSpec("POST", True, ("confirmation",)),
}


READ_ENDPOINTS: dict[str, EndpointSpec] = {
    "/api/session": EndpointSpec("GET", False),
    "/api/schema": EndpointSpec("GET", False),
    "/api/state": EndpointSpec("GET", False),
    "/api/dossier": EndpointSpec("GET", False, ("path",)),
}


def build_schema_payload(readonly: bool) -> dict[str, Any]:
    endpoints = {
        path: {"method": spec.method, "mutates": spec.mutates, "required": list(spec.required)}
        for path, spec in {**READ_ENDPOINTS, **MUTATION_ENDPOINTS}.items()
    }
    return {"ok": True, "readonly": readonly, "endpoints": endpoints}


def missing_required_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if field not in payload or payload[field] is None or payload[field] == ""]
