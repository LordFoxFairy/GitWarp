from __future__ import annotations

from pathlib import Path
from typing import Any

from .dossiers import create_dossier_files, read_snippet


class FilesystemDossierStore:
    def create(self, paths: dict[str, str], **metadata: Any) -> None:
        create_dossier_files(paths, **metadata)

    def read_snippet(self, path: str | None, *, max_chars: int = 900) -> str | None:
        return read_snippet(path, max_chars=max_chars)

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")
