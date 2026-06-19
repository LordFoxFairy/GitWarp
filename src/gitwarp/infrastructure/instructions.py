from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path
from typing import Any

from .runtime import GitWarpError, RepoContext


def resolve_source(ctx: RepoContext, raw_source: str) -> Path:
    source = Path(raw_source).expanduser()
    if not source.is_absolute():
        source = ctx.repo_root / source
    source = source.resolve()
    if not source.is_file():
        raise GitWarpError(f"instruction source is not a file: {source}")
    return source


def validate_target(raw_target: str) -> str:
    target = Path(raw_target)
    if not raw_target.strip() or target.is_absolute() or ".." in target.parts:
        raise GitWarpError(f"instruction target must be a relative path inside the worktree: {raw_target}")
    normalized = target.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized or normalized == ".":
        raise GitWarpError(f"instruction target must be a file path: {raw_target}")
    if normalized == ".git" or normalized.startswith(".git/"):
        raise GitWarpError("instruction target cannot be inside .git")
    return normalized


def parse_instruction_spec(value: str) -> dict[str, str]:
    if "=" in value:
        raw_target, raw_source = value.split("=", 1)
        return {"source": raw_source.strip(), "target": validate_target(raw_target.strip())}
    source = value.strip()
    return {"source": source, "target": validate_target(Path(source).name)}


def load_instruction_profile(ctx: RepoContext, profile_name: str) -> list[dict[str, str]]:
    if not ctx.instruction_profiles_path.exists():
        raise GitWarpError(f"instruction profile '{profile_name}' requested but {ctx.instruction_profiles_path} does not exist")
    try:
        payload = json.loads(ctx.instruction_profiles_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GitWarpError(f"instruction profile config is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("profiles"), dict):
        raise GitWarpError("instruction profile config must be an object with version 1 and profiles")
    profile = payload["profiles"].get(profile_name)
    if not isinstance(profile, dict) or not isinstance(profile.get("instructions"), list):
        raise GitWarpError(f"unknown instruction profile '{profile_name}'")

    specs: list[dict[str, str]] = []
    for item in profile["instructions"]:
        if isinstance(item, str):
            specs.append(parse_instruction_spec(item))
        elif isinstance(item, dict) and isinstance(item.get("source"), str):
            target = item.get("target")
            if target is not None and not isinstance(target, str):
                raise GitWarpError(f"instruction profile '{profile_name}' contains a non-string target")
            specs.append({"source": item["source"], "target": validate_target(target if isinstance(target, str) else Path(item["source"]).name)})
        else:
            raise GitWarpError(f"instruction profile '{profile_name}' contains an invalid instruction entry")
    return specs


def build_instruction_plan(
    ctx: RepoContext,
    *,
    raw_instructions: list[str] | None,
    profile_name: str | None,
    mode: str,
) -> list[dict[str, str]]:
    if mode not in {"copy", "symlink"}:
        raise GitWarpError("instruction mode must be copy or symlink")
    specs: list[dict[str, str]] = []
    if profile_name:
        specs.extend(load_instruction_profile(ctx, profile_name))
    specs.extend(parse_instruction_spec(value) for value in (raw_instructions or []))

    plan: list[dict[str, str]] = []
    seen_targets: set[str] = set()
    for spec in specs:
        source = resolve_source(ctx, spec["source"])
        target = validate_target(spec["target"])
        if target in seen_targets:
            raise GitWarpError(f"instruction target is specified more than once: {target}")
        seen_targets.add(target)
        existing_target = ctx.repo_root / target
        if existing_target.exists() and existing_target.is_file() and existing_target.read_bytes() != source.read_bytes():
            raise GitWarpError(f"instruction target already exists with different content: {target}")
        plan.append({"source": str(source), "target": target, "mode": mode})
    return plan


def mount_instruction_files(worktree_path: Path, plan: list[dict[str, str]]) -> list[dict[str, Any]]:
    mounted: list[dict[str, Any]] = []
    worktree_root = worktree_path.resolve()
    for item in plan:
        source = Path(item["source"]).resolve()
        source_bytes = source.read_bytes()
        target = item["target"]
        destination = (worktree_root / target).resolve()
        try:
            destination.relative_to(worktree_root)
        except ValueError as exc:
            raise GitWarpError(f"instruction target escapes worktree: {target}") from exc
        if destination.exists():
            if not destination.is_file() or destination.read_bytes() != source.read_bytes():
                raise GitWarpError(f"instruction target already exists with different content: {target}")
            status = "existing"
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if item["mode"] == "copy":
                shutil.copy2(source, destination)
                status = "copied"
            else:
                destination.symlink_to(source)
                status = "linked"
        mounted.append(
            {
                "source": str(source),
                "target": target,
                "path": str(destination),
                "mode": item["mode"],
                "status": status,
                "sha256": hashlib.sha256(source_bytes).hexdigest(),
                "bytes": len(source_bytes),
            }
        )
    return mounted
