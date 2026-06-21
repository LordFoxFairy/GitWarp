from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EndpointSpec:
    method: str
    mutates: bool
    required: tuple[str, ...] = ()


@dataclass(frozen=True)
class FieldSpec:
    kind: str
    required: bool = False
    choices: tuple[str, ...] = ()


class PayloadValidationError(ValueError):
    pass


MUTATION_ENDPOINTS: dict[str, EndpointSpec] = {
    "/api/init": EndpointSpec("POST", True, ("write_gitignore",)),
    "/api/dispatch": EndpointSpec("POST", True, ("branch", "purpose")),
    "/api/start": EndpointSpec("POST", True, ("agent_id", "branch", "purpose")),
    "/api/handoff": EndpointSpec("POST", True, ("cwd", "status", "progress")),
    "/api/confirmation": EndpointSpec("POST", True, ("action",)),
    "/api/finish": EndpointSpec("POST", True, ("cwd", "status", "progress")),
    "/api/collapse": EndpointSpec("POST", True, ("confirmation",)),
    "/api/prune-branch": EndpointSpec("POST", True, ("branch", "confirm_branch")),
}


MUTATION_FIELD_SPECS: dict[str, dict[str, FieldSpec]] = {
    "/api/init": {
        "write_gitignore": FieldSpec("boolean", required=True),
    },
    "/api/dispatch": {
        "agent": FieldSpec("string"),
        "agent_id": FieldSpec("string"),
        "branch": FieldSpec("string", required=True),
        "base_branch": FieldSpec("string"),
        "purpose": FieldSpec("string", required=True),
        "instructions": FieldSpec("string_list"),
        "instruction_profile": FieldSpec("string"),
        "instruction_mode": FieldSpec("string", choices=("copy", "symlink")),
    },
    "/api/start": {
        "agent_id": FieldSpec("string", required=True),
        "branch": FieldSpec("string", required=True),
        "base_branch": FieldSpec("string"),
        "purpose": FieldSpec("string", required=True),
        "instructions": FieldSpec("string_list"),
        "instruction_profile": FieldSpec("string"),
        "instruction_mode": FieldSpec("string", choices=("copy", "symlink")),
    },
    "/api/handoff": {
        "cwd": FieldSpec("string", required=True),
        "path": FieldSpec("string"),
        "branch": FieldSpec("string"),
        "status": FieldSpec("string", required=True),
        "progress": FieldSpec("string", required=True),
        "lesson": FieldSpec("string"),
    },
    "/api/confirmation": {
        "action": FieldSpec("string", required=True, choices=("collapse", "finish-collapse")),
        "cwd": FieldSpec("string"),
        "path": FieldSpec("string"),
        "branch": FieldSpec("string"),
    },
    "/api/finish": {
        "cwd": FieldSpec("string", required=True),
        "path": FieldSpec("string"),
        "branch": FieldSpec("string"),
        "status": FieldSpec("string", required=True),
        "progress": FieldSpec("string", required=True),
        "lesson": FieldSpec("string"),
        "collapse": FieldSpec("boolean"),
        "collapse_merged": FieldSpec("boolean"),
        "confirmation": FieldSpec("string"),
    },
    "/api/collapse": {
        "cwd": FieldSpec("string"),
        "path": FieldSpec("string"),
        "branch": FieldSpec("string"),
        "confirmation": FieldSpec("string", required=True),
    },
    "/api/prune-branch": {
        "cwd": FieldSpec("string"),
        "branch": FieldSpec("string", required=True),
        "base_branch": FieldSpec("string"),
        "confirm_branch": FieldSpec("string", required=True),
    },
}


READ_ENDPOINTS: dict[str, EndpointSpec] = {
    "/api/session": EndpointSpec("GET", False),
    "/api/schema": EndpointSpec("GET", False),
    "/api/state": EndpointSpec("GET", False),
    "/api/matrix": EndpointSpec("GET", False),
    "/api/dossier": EndpointSpec("GET", False, ("path",)),
    "/api/repository/tree": EndpointSpec("GET", False),
    "/api/repository/file": EndpointSpec("GET", False, ("path",)),
    "/api/branches": EndpointSpec("GET", False),
}


def build_schema_payload(readonly: bool) -> dict[str, Any]:
    endpoints = {
        path: {
            "method": spec.method,
            "mutates": spec.mutates,
            "required": list(spec.required),
            **({"fields": serialize_field_specs(MUTATION_FIELD_SPECS[path])} if path in MUTATION_FIELD_SPECS else {}),
        }
        for path, spec in {**READ_ENDPOINTS, **MUTATION_ENDPOINTS}.items()
    }
    return {"ok": True, "readonly": readonly, "endpoints": endpoints}


def serialize_field_specs(specs: dict[str, FieldSpec]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "type": spec.kind,
            "required": spec.required,
            **({"choices": list(spec.choices)} if spec.choices else {}),
        }
        for name, spec in specs.items()
    }


def validate_mutation_payload(path: str, payload: dict[str, Any]) -> None:
    specs = MUTATION_FIELD_SPECS[path]
    unknown = sorted(set(payload) - set(specs))
    if unknown:
        raise PayloadValidationError(f"unknown field(s): {', '.join(unknown)}")

    missing = [name for name, spec in specs.items() if spec.required and is_absent(payload.get(name))]
    if missing:
        raise PayloadValidationError(f"missing required field(s): {', '.join(missing)}")

    for name, value in payload.items():
        if value is None:
            continue
        validate_field(name, value, specs[name])


def is_absent(value: Any) -> bool:
    return value is None or value == ""


def validate_field(name: str, value: Any, spec: FieldSpec) -> None:
    if spec.kind == "string":
        if not isinstance(value, str):
            raise PayloadValidationError(f"{name} must be a string")
        if spec.required and not value.strip():
            raise PayloadValidationError(f"{name} must not be empty")
        if spec.choices and value not in spec.choices:
            raise PayloadValidationError(f"{name} must be one of: {', '.join(spec.choices)}")
        return
    if spec.kind == "boolean":
        if not isinstance(value, bool):
            raise PayloadValidationError(f"{name} must be a boolean")
        return
    if spec.kind == "string_list":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise PayloadValidationError(f"{name} must be a list of strings")
        return
    raise PayloadValidationError(f"{name} has unsupported schema type: {spec.kind}")
