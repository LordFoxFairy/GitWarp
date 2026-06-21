# GitWarp Agent Task Inbox Design

## Problem

GitWarp has reliable low-level primitives for isolated agent work: `create`, `start`, `dispatch`, dossiers, mounted instructions, ledger tracking, matrix reconciliation, and the web console. The remaining UX problem is task intake. A human or agent still has to choose branch names, base branches, agent IDs, purpose text, instruction mounts, and dossier content manually.

That makes agent work inconsistent. Agents can invent branches that do not match the user's intent, create weak `task.md` files, forget acceptance criteria, or start from the wrong base branch. The web console also exposes too many low-level forms for the common case: "I have a task; create the right sandbox and tell the agent what to do."

## Goals

- Add a high-level task intake facade above the existing provisioning use cases.
- Keep `create`, `start`, and `dispatch` as advanced/automation commands; do not remove or rename them.
- Generate deterministic branch names and agent IDs from a task title when the user does not provide them.
- Create richer task dossiers with objective, user request, scope, acceptance criteria, verification commands, mounted instructions, and finish policy.
- Make the web console's primary action feel like creating a task, not manually wiring a worktree.
- Preserve deterministic single-line JSON for CLI and API mutations.
- Avoid automatic merge, push, branch deletion, or destructive cleanup.

## Non-Goals

- No LLM planning or autonomous task decomposition inside GitWarp.
- No hosted queue, database, issue tracker sync, PR creation, or remote runner.
- No automatic merge from task branch to base branch.
- No automatic deletion of base worktrees or user-selected feature branches.
- No replacement for dossiers; the task inbox writes better dossiers instead of inventing a second task database.

## Proposed User Model

GitWarp should expose one common workflow:

```bash
gitwarp task create \
  --title "Polish matrix web UX" \
  --description "Make branch and worktree state easier to understand" \
  --acceptance "Web shows refs, worktrees, ledger rows, and dossiers clearly" \
  --verify "python3 -m unittest discover -s tests -p 'test_*.py' -v"
```

If the caller omits branch and agent ID, GitWarp derives them:

- Branch: `agent/<slugified-title>`.
- Agent ID: `agent-<slugified-title>`.
- Base branch: inferred from the current GitWarp context with the existing `infer_base_branch` rule.

If the user supplies `--branch`, GitWarp must use it exactly after existing branch validation. User-provided branch names are intent, not hints.

The command returns the same kind of payload as `gitwarp create`: repository root, absolute worktree path, branch, base branch, dossier paths, mounted instructions, and a shell navigation command when requested.

## CLI And API Contract

Add a new CLI command group:

```bash
gitwarp task create [options]
```

Supported options:

- `--title <text>`: required, short human task title.
- `--description <text>`: optional full user request or problem statement.
- `--base <branch>`: optional parent base branch.
- `--branch <branch>`: optional explicit task branch.
- `--agent <codex|claude|generic>`: optional launch target metadata.
- `--agent-id <id>`: optional explicit owner ID.
- `--purpose <text>`: optional compatibility alias; defaults from title/description.
- `--acceptance <text>`: repeatable acceptance criteria.
- `--verify <command>`: repeatable verification commands.
- `--instruction <source[=target]>`: repeatable instruction mount, same semantics as `create`.
- `--instruction-profile <name>`: existing profile support.
- `--instruction-mode <copy|symlink>`: existing instruction mount mode.
- `--format <json|shell>`: JSON by default; `shell` prints a `cd` command after creation.

Add a web mutation endpoint:

```text
POST /api/task/create
```

It accepts the same fields as the CLI request and delegates to the same application use case. The endpoint remains CSRF protected and disabled in read-only web mode.

## Application Architecture

Add `src/gitwarp/application/use_cases/tasks.py` with a single orchestration entry point:

```python
build_task_create_payload(ctx, request: TaskCreateRequest) -> dict
```

This use case should not duplicate worktree creation. It normalizes the task request, generates missing names, constructs richer dossier metadata, and then delegates to the existing provisioning path used by `build_start_payload`. If richer dossier creation needs new arguments, extend the dossier infrastructure deliberately rather than writing markdown from the CLI adapter.

Recommended boundaries:

- `domain/model.py`: add a small `TaskIntake` or `TaskCreateRequest` value object if it helps validation.
- `domain/policies.py`: add deterministic slug and branch derivation policy.
- `application/use_cases/tasks.py`: request normalization and orchestration.
- `infrastructure/dossiers.py`: richer task dossier rendering.
- `adapters/cli/parser.py` and `adapters/cli/workspaces.py`: parse and invoke the new task command.
- `webapp/contracts.py` and `webapp/controllers.py`: expose `/api/task/create`.
- `web/console/src/app/components/ActionPanel.tsx`: make "Create Task" the primary form.

## Dossier Template

Task-created worktrees should initialize `task.md` with concrete sections:

```markdown
# Task

## Objective
<short title>

## User Request
<description or purpose>

## Scope
- Branch: <branch>
- Parent Base: <base>
- Worktree: <absolute path>
- Agent: <agent id>

## Acceptance Criteria
- [ ] <criterion>

## Verification
- [ ] `<command>`

## Mounted Instructions
- `<target>` from `<source>` (<mode>)

## Finish Policy
Leave the task worktree for human review after verification unless the user explicitly requests merge, remove, or collapse.
```

`progress.md` should start with a "Task created" event that includes the title and base branch. `lessons.md` can keep the existing future-agent notes section.

Existing dossiers from `create` or `handoff` remain compatible. Missing optional task fields must render sensible placeholders rather than breaking matrix, board, or web metadata views.

## Web Console UX

The web console should present "Create Task" as the first action in the agent/tools panel. Advanced forms for raw sandbox creation and launch preparation can remain available but should be secondary.

The Create Task form should ask for:

- Title.
- Description.
- Base branch selector.
- Optional explicit branch.
- Acceptance criteria.
- Verification commands.
- Instruction profile and extra instruction mounts.

After creation, the UI selects the new worktree, shows its dossier in Metadata, and provides a clear copyable `cd` command. It must not start an external agent process automatically.

## Safety Rules

- Branch collision checks stay strict. If the derived or explicit branch is already bound to a live worktree, abort before mutation.
- Generated branch collisions return a deterministic error. Do not append random suffixes in the first release.
- Empty titles are rejected.
- Instruction mount failure must roll back the created worktree, branch, and dossier using existing cleanup paths.
- Task-created worktrees always use `branch_role=task`.
- Base worktrees remain explicit through `gitwarp create --role base`; the task inbox does not create long-lived base branches in its first release.
- Finish behavior remains unchanged: verification records progress; merge, push, collapse, remove, and branch prune require explicit user intent.

## Alternatives Considered

### A. Keep Improving `create`

This is the smallest change, but it keeps the primary UX parameter-driven. It does not solve weak dossiers or agent branch invention.

### B. Add A Full Queue System

A queue with states like pending, assigned, running, review, and done would be powerful, but it requires a new persistence model and more UI. GitWarp does not need that yet.

### C. Add A Thin Task Facade

This is the recommended path. It reuses existing worktree, ledger, instruction, and dossier mechanics while giving humans and agents a clearer entry point.

## Testing Strategy

- CLI: `gitwarp task create --title ...` creates a task worktree with generated branch, generated agent ID, absolute paths, and a richer dossier.
- CLI: explicit `--branch`, `--agent-id`, `--base`, `--acceptance`, `--verify`, and instruction options are preserved in output and dossier files.
- Safety: branch collision aborts before ledger or dossier mutation.
- Safety: instruction mount failure rolls back created artifacts.
- Web API: `/api/task/create` validates required fields, rejects read-only mode, requires CSRF, and returns stable JSON.
- Web UI: Create Task posts to the new endpoint and selects the created worktree without a full page reload.
- Compatibility: existing `create`, `start`, `dispatch`, `matrix`, `board`, `finish`, and `remove` tests continue passing.

## Rollout Plan

1. Implement CLI and application use case for `gitwarp task create`.
2. Add richer dossier rendering and tests.
3. Add `/api/task/create` using the same use case.
4. Promote Create Task in the web console and keep advanced sandbox controls secondary.
5. Update README and `skills/gitwarp/SKILL.md` so agents prefer task intake for new user work.

## Acceptance Criteria

- `gitwarp task create` is the recommended entry point for new agent work.
- Generated branch and agent IDs are deterministic.
- Created dossiers contain objective, request, acceptance criteria, verification, mounted instructions, and finish policy.
- The web console exposes a simple Create Task flow.
- Existing low-level commands remain available and backward compatible.
- No command performs automatic merge, push, worktree deletion, or branch deletion.
