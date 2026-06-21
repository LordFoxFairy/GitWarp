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

If the user supplies `--branch`, GitWarp must use it exactly after existing branch validation. User-provided branch names are intent, not hints. Explicit branches may bind to an existing unbound local branch, matching the existing `create` behavior. Auto-generated branches are stricter: if `refs/heads/<generated-branch>` already exists or any live worktree is already bound to that branch, task creation fails before mutation. GitWarp must not silently attach a generated task to stale local branch history.

The command returns the same kind of payload as `gitwarp create`: repository root, absolute worktree path, branch, base branch, dossier paths, mounted instructions, and a shell navigation command when requested.

## Naming And Metadata Rules

Task intake must use one deterministic normalization path:

| Input title | Slug | Generated branch | Generated agent ID |
| --- | --- | --- | --- |
| `Polish matrix web UX` | `polish-matrix-web-ux` | `agent/polish-matrix-web-ux` | `agent-polish-matrix-web-ux` |
| `修复 Web 闪动` | `web` | `agent/web` | `agent-web` |
| `!!!` | invalid | rejected | rejected |

Normalization rules:

- Trim whitespace.
- Lowercase ASCII letters.
- Replace every non-`[a-z0-9]` run with `-`.
- Collapse repeated `-`.
- Strip leading and trailing `-`.
- Reject if the result is empty after cleanup.
- Limit the slug to 64 characters by cutting at a character boundary and stripping a trailing `-`.
- Validate the final generated branch with `git check-ref-format --branch <branch>` before any mutation.

Purpose resolution order:

1. `--purpose` when provided as a non-empty trimmed value.
2. `--description` when provided as a non-empty trimmed value.
3. `--title`.

Blank optional strings are treated as absent after trimming. The required title is rejected when blank or when it normalizes to an empty slug.

`--agent` is target-agent metadata only. It must never start an external process. Store it as `target_agent` in the ledger entry, return it in the JSON payload, and render it in `task.md`. Allowed values for v1 are `codex`, `claude`, and `generic`; default is `generic`. `agent_id` remains the workspace owner identity and is independent from `target_agent`.

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
- `--agent <codex|claude|generic>`: optional target-agent metadata; default `generic`.
- `--agent-id <id>`: optional explicit owner ID.
- `--purpose <text>`: optional compatibility alias; defaults from title/description.
- `--acceptance <text>`: repeatable acceptance criteria.
- `--verify <command>`: repeatable verification commands.
- `--instruction <source>` or `--instruction <target=source>`: repeatable instruction mount, same semantics as `create`.
- `--instruction-profile <name>`: existing profile support.
- `--instruction-mode <copy|symlink>`: existing instruction mount mode.

CLI output is deterministic single-line JSON. It must include at least:

```json
{"ok":true,"repo_root":"/abs/repo","path":"/abs/worktree","branch":"agent/example","base_branch":"main","agent_id":"agent-example","target_agent":"generic","purpose":"Example","task_title":"Example","task_description":null,"acceptance_criteria":[],"verification_commands":[],"branch_created":true,"head":"...","dossier_path":"/abs/.gitwarp/dossiers/...","task_md":"/abs/.../task.md","progress_md":"/abs/.../progress.md","lessons_md":"/abs/.../lessons.md","instructions":[],"shell_command":"cd /abs/worktree"}
```

Add a web mutation endpoint:

```text
POST /api/task/create
```

It accepts these JSON fields and delegates to the same application use case. The endpoint remains CSRF protected, appears in `/api/schema`, and is disabled in read-only web mode. Successful responses return the same task-create payload keys as the CLI, including `target_agent`, `task_title`, `task_description`, `acceptance_criteria`, `verification_commands`, and `shell_command`.

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `title` | string | yes | none | Must not normalize to an empty slug. |
| `description` | string | no | null | Full user request. |
| `base_branch` | string | no | inferred | API uses `base_branch`, not CLI-only `--base`. |
| `branch` | string | no | generated | Explicit branch may reuse an unbound local ref. |
| `target_agent` | string | no | `generic` | One of `codex`, `claude`, `generic`. |
| `agent_id` | string | no | generated | Workspace owner identity. |
| `purpose` | string | no | resolved | Uses purpose resolution order above. |
| `acceptance_criteria` | string list | no | `[]` | Repeatable CLI `--acceptance` maps here. |
| `verification_commands` | string list | no | `[]` | Repeatable CLI `--verify` maps here. |
| `instructions` | string list | no | `[]` | Same string syntax as CLI: `<source>` or `<target=source>`. |
| `instruction_profile` | string | no | null | Existing instruction profile. |
| `instruction_mode` | string | no | `copy` | One of `copy`, `symlink`. |

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
- Target Agent: <target_agent>

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
- Auto-generated branches also fail if the local branch ref already exists, even when no worktree currently uses it.
- Explicit `--branch` may reuse an existing unbound local branch, but must still fail if that branch is checked out by any live worktree.
- Both generated and explicit branches must pass `git check-ref-format --branch` before any mutation.
- Generated branch collisions return a deterministic error. Do not append random suffixes in the first release.
- Empty titles are rejected.
- Titles that normalize to an empty slug are rejected.
- `target_agent` validation happens before any Git or filesystem mutation.
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
- CLI: generated branch fails when the local branch ref already exists; explicit branch may reuse an unbound local ref.
- CLI: slug normalization covers whitespace, punctuation, Unicode-only titles, mixed ASCII/Unicode titles, `.`, `foo..bar`, `foo.lock`, `foo.`, maximum length, Git ref-format validation, and empty-after-cleanup rejection.
- CLI/API: blank optional `purpose` and `description` values are treated as absent; blank required `title` is rejected.
- CLI: JSON payload includes `task_title`, `task_description`, `target_agent`, `acceptance_criteria`, `verification_commands`, and `shell_command`.
- Safety: branch collision aborts before ledger or dossier mutation.
- Safety: instruction mount failure rolls back created artifacts.
- Web API: `/api/task/create` validates required fields, rejects unknown fields and wrong types, rejects read-only mode, requires CSRF, appears in `/api/schema`, and returns stable JSON.
- Web API: successful `/api/task/create` returns the same task-create payload keys as CLI.
- Web API: request field names are `base_branch`, `target_agent`, `acceptance_criteria`, and `verification_commands`; tests must reject CLI flag spellings such as `base` or `verify`.
- Frontend: `gitwarp-api.ts` defines a typed `TaskCreateInput` and posts to `/api/task/create`.
- Web UI: Create Task posts to the new endpoint and selects the created worktree without a full page reload.
- Dossier: generated `task.md` includes separate `Agent` and `Target Agent` rows.
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
