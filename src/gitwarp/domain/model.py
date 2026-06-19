from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HeadDrift:
    last_seen_head: str
    current_head: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "drifted": True,
            "last_seen_head": self.last_seen_head,
            "current_head": self.current_head,
        }


@dataclass(frozen=True)
class WorktreeSnapshot:
    path: str
    head: str
    branch: str | None = None
    detached: bool = False
    is_main: bool = False

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "WorktreeSnapshot":
        return cls(
            path=str(value["path"]),
            head=str(value["head"]),
            branch=value.get("branch") if isinstance(value.get("branch"), str) else None,
            detached=bool(value.get("detached", False)),
            is_main=bool(value.get("is_main", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "head": self.head,
            "branch": self.branch,
            "detached": self.detached,
            "is_main": self.is_main,
        }


@dataclass(frozen=True)
class DossierRef:
    dossier_path: str
    task_md: str
    progress_md: str
    lessons_md: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "DossierRef":
        return cls(
            dossier_path=str(value["dossier_path"]),
            task_md=str(value["task_md"]),
            progress_md=str(value["progress_md"]),
            lessons_md=str(value["lessons_md"]),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "dossier_path": self.dossier_path,
            "task_md": self.task_md,
            "progress_md": self.progress_md,
            "lessons_md": self.lessons_md,
        }


@dataclass(frozen=True)
class WorkspaceRecord:
    path: str
    branch: str | None
    agent_id: str | None = None
    purpose: str | None = None
    status: str | None = None
    notes: list[dict[str, Any]] = field(default_factory=list)
    dossier: DossierRef | None = None
    latest_progress: str | None = None
    latest_lesson: str | None = None
    last_seen_head: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    dispatch: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "WorkspaceRecord":
        dossier = None
        if all(value.get(key) for key in ("dossier_path", "task_md", "progress_md", "lessons_md")):
            dossier = DossierRef.from_mapping(value)
        return cls(
            path=str(value["path"]),
            branch=value.get("branch") if isinstance(value.get("branch"), str) else None,
            agent_id=value.get("agent_id") if isinstance(value.get("agent_id"), str) else None,
            purpose=value.get("purpose") if isinstance(value.get("purpose"), str) else None,
            status=value.get("status") if isinstance(value.get("status"), str) else None,
            notes=list(value.get("notes", [])),
            dossier=dossier,
            latest_progress=value.get("latest_progress") if isinstance(value.get("latest_progress"), str) else None,
            latest_lesson=value.get("latest_lesson") if isinstance(value.get("latest_lesson"), str) else None,
            last_seen_head=value.get("last_seen_head") if isinstance(value.get("last_seen_head"), str) else None,
            created_at=value.get("created_at") if isinstance(value.get("created_at"), str) else None,
            updated_at=value.get("updated_at") if isinstance(value.get("updated_at"), str) else None,
            dispatch=value.get("dispatch") if isinstance(value.get("dispatch"), dict) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "branch": self.branch,
            "agent_id": self.agent_id,
            "purpose": self.purpose,
            "status": self.status,
            "notes": self.notes,
            "latest_progress": self.latest_progress,
            "latest_lesson": self.latest_lesson,
            "last_seen_head": self.last_seen_head,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.dossier is not None:
            payload.update(self.dossier.to_dict())
        if self.dispatch is not None:
            payload["dispatch"] = self.dispatch
        return payload


@dataclass(frozen=True)
class DispatchPlan:
    agent_name: str
    agent_id: str
    launch_command: list[str]
    launch_preview: str
    prepared_at: str

    def to_metadata(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "command_mode": "print",
            "launch_command": self.launch_command,
            "launch_preview": self.launch_preview,
            "last_exit_code": None,
            "last_prepared_at": self.prepared_at,
            "last_started_at": None,
            "last_finished_at": None,
        }
