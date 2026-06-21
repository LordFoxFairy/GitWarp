from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.policies import first_non_empty, normalize_task_slug, normalize_target_agent
from ...infrastructure.instructions import build_instruction_plan
from ...infrastructure.runtime import GitWarpError, RepoContext, run_git
from ...infrastructure.worktrees import branch_exists, ensure_branch_available, parse_worktrees
from .navigation import shell_cd_command
from .provisioning import build_start_payload


@dataclass(frozen=True)
class TaskCreateRequest:
    title: str
    description: str | None = None
    base_branch: str | None = None
    branch: str | None = None
    target_agent: str | None = None
    agent_id: str | None = None
    purpose: str | None = None
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    instruction_profile: str | None = None
    instruction_mode: str = "copy"


def _clean_list(values: list[str] | None) -> list[str]:
    return [item.strip() for item in (values or []) if item.strip()]


def _ensure_branch_ref_format(ctx: RepoContext, branch: str) -> None:
    try:
        run_git(ctx.repo_root, "check-ref-format", "--branch", branch)
    except GitWarpError as exc:
        raise GitWarpError(f"invalid branch '{branch}': {exc}") from exc


def build_task_create_payload(ctx: RepoContext, request: TaskCreateRequest) -> dict[str, object]:
    title = request.title.strip()
    if not title:
        raise GitWarpError("title must not be blank")
    slug = normalize_task_slug(title)

    generated_branch = first_non_empty(request.branch) is None
    branch = first_non_empty(request.branch) or f"agent/{slug}"
    agent_id = first_non_empty(request.agent_id) or f"agent-{slug}"
    purpose = first_non_empty(request.purpose, request.description, title)
    if purpose is None:
        raise GitWarpError("purpose could not be resolved")
    target_agent = normalize_target_agent(request.target_agent)
    description = first_non_empty(request.description)
    base_branch = first_non_empty(request.base_branch)
    instruction_profile = first_non_empty(request.instruction_profile)
    acceptance = _clean_list(request.acceptance_criteria)
    verification = _clean_list(request.verification_commands)

    _ensure_branch_ref_format(ctx, branch)
    ensure_branch_available(parse_worktrees(ctx), branch)
    if generated_branch and branch_exists(ctx, branch):
        raise GitWarpError(f"generated branch already exists: {branch}")

    build_instruction_plan(
        ctx,
        raw_instructions=request.instructions,
        profile_name=instruction_profile,
        mode=request.instruction_mode,
    )

    payload = build_start_payload(
        ctx,
        agent_id=agent_id,
        branch=branch,
        purpose=purpose,
        base_branch=base_branch,
        instructions=request.instructions,
        instruction_profile=instruction_profile,
        instruction_mode=request.instruction_mode,
        task_title=title,
        task_description=description,
        target_agent=target_agent,
        acceptance_criteria=acceptance,
        verification_commands=verification,
    )
    payload["shell_command"] = shell_cd_command(str(payload["path"]))
    return payload
