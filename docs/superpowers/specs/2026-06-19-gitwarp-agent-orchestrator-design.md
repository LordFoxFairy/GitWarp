# GitWarp Agent Orchestrator Design

> Status: Historical record. Superseded by `2026-06-20-gitwarp-ddd-architecture-design.md` and the repository README. Do not follow old `plugins/gitwarp` mirror instructions.

## Problem

GitWarp now gives agents isolated worktrees, task dossiers, startup context, and a board. The next gap is orchestration: a human or lead agent still has to manually choose an agent CLI, create the worktree, copy the path, construct the launch command, and later detect stale or broken work. That friction makes parallel Codex and Claude Code development possible but not yet smooth.

## Goals

- Add a deterministic orchestration layer for Codex, Claude Code, and custom agent commands.
- Keep GitWarp's core safety model: one branch per worktree, no main-repo branch switching, no hidden checkout mutation.
- Make dispatch auditable by generating explicit launch commands before execution.
- Let existing worktrees be adopted into GitWarp metadata without losing previous work.
- Add health checks that detect stale Git metadata, missing CLI/plugin setup, broken ledger entries, missing dossiers, dirty worktrees, and blocked/stale assignments.
- Preserve strict JSON for automation-facing commands.
- Make ledger updates safe for concurrent agent commands.

## Non-Goals

- Do not build a background daemon in this iteration.
- Do not implement autonomous task stealing or queue scheduling yet.
- Do not attempt to control Codex or Claude Code internals after launch.
- Do not merge branches, push code, or claim verification automatically.
- Do not execute long-running agent CLIs in the first orchestration slice.
- Do not add non-standard-library runtime dependencies.

## Core Principle

GitWarp orchestrates workspaces and launch boundaries, not model cognition. An agent is considered correctly managed when it starts in the intended worktree, receives `gitwarp enter` context, records progress with `handoff`, and leaves a verifiable Git/dossier trail. GitWarp should never rely on an agent's chat memory as source of truth.

## Concurrency Requirements

The orchestration layer is explicitly for parallel agents, so ledger writes must become concurrency-safe before adding dispatch/adopt mutations.

Requirements:

- All commands that write `.gitwarp/ledger.json` must acquire a repository-local lock, for example `.gitwarp/ledger.lock`.
- Lock acquisition should have a bounded timeout and return `ok:false` with a clear error if the lock cannot be acquired.
- Ledger writes should use atomic replace: write to a temporary file in `.gitwarp/`, flush, then replace `ledger.json`.
- Read-only audit commands such as `enter`, `statusline`, `agents`, `reconcile`, and `doctor` must not acquire write locks unless an explicit future repair/fix flag is used.
- Tests must include parallel handoff or dispatch-style writes that would have exposed lost updates.

## Configuration

Add a repo-local configuration file:

```text
.gitwarp/agents.json
```

This file is runtime configuration and remains ignored by Git by default. A later command may export a template into tracked docs, but the live agent registry should stay local because command paths, flags, and model choices vary by machine.

Minimal schema:

```json
{
  "version": 1,
  "default_agent": "codex",
  "agents": {
    "codex": {
      "description": "Codex CLI non-interactive worker",
      "command": [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "-C",
        "{worktree}",
        "{prompt}"
      ],
      "status": "enabled"
    },
    "claude": {
      "description": "Claude Code worker",
      "command": [
        "claude",
        "-C",
        "{worktree}",
        "{prompt}"
      ],
      "status": "enabled"
    }
  }
}
```

Supported template variables:

- `{repo}`: absolute root repository path.
- `{worktree}`: absolute GitWarp worktree path.
- `{branch}`: isolated branch.
- `{agent_id}`: GitWarp agent id.
- `{purpose}`: assignment purpose.
- `{task_md}`, `{progress_md}`, `{lessons_md}`: dossier paths.
- `{prompt}`: generated instruction prompt.

JSON is the first implementation format because GitWarp intentionally uses only Python's standard library. A future `agents.yaml` importer can be added later if there is real demand, but the execution path should stay JSON-first to keep parsing deterministic.

Validation rules:

- Unknown top-level fields are allowed but ignored.
- `version` must be `1`.
- `agents` must be an object keyed by agent name.
- Each enabled agent must have a non-empty command array.
- Command arrays must contain both `{worktree}` and `{prompt}` so the worker starts in the correct directory and receives the assignment.
- Unknown template variables are rejected.
- If the config is malformed, `agents`, `dispatch`, and `doctor` report the parse error with `ok:false` or an `error` severity finding.

## Status Model

Existing status values remain free-form for compatibility, but GitWarp-owned workflows should use this canonical set:

| Status | Meaning |
| --- | --- |
| `active` | Worktree exists and is assigned. |
| `dispatched` | Dispatch command was generated for an agent. |
| `adopted` | Existing non-main worktree was bound to GitWarp. |
| `implementing` | Agent reports active implementation. |
| `testing` | Agent reports verification in progress. |
| `blocked` | Agent cannot progress without input. |
| `ready` | Agent believes work is ready for human/main verification. |
| `pushed` | Agent reports branch pushed upstream. |
| `merged` | Main integration is complete or branch has been merged. |
| `dispatch_failed` | Execute-mode launch failed. |

`board` and `reconcile` may still display unknown custom statuses, but automation should only infer lifecycle meaning from the canonical values above.

## Commands

### `gitwarp agents`

Lists configured agents and whether each launch binary appears available on `PATH`.

Default output is single-line JSON:

```json
{"ok":true,"config_path":"/abs/repo/.gitwarp/agents.json","agents":[{"name":"codex","status":"enabled","available":true}]}
```

If no config exists, return built-in recommendations for `codex` and `claude` but mark them as `configured:false`. Do not fail solely because the file is missing.

### `gitwarp dispatch`

Creates a dossier-backed worktree and prepares an agent launch.

Example:

```bash
gitwarp dispatch --cwd /abs/repo \
  --agent codex \
  --branch feature/foo \
  --purpose "Implement foo" \
  --command-mode print
```

Modes:

- `--command-mode print` is the default. It returns JSON containing `launch_command` and does not execute it.
- `--command-mode execute` is deferred. The first orchestration implementation should reject it with a clear `ok:false` message explaining that process execution is not yet supported.

Behavior:

1. Load agent config or built-in fallback.
2. Validate `--command-mode`, agent name, config schema, required template variables, and branch collision before creating any worktree.
3. Reject unsupported `execute` mode before any worktree, dossier, or ledger mutation.
4. Call the same allocation path as `start`.
5. Generate an instruction prompt that tells the agent to run/read `gitwarp enter`, read dossier files, avoid branch switching, use `handoff`, and stop before merge.
6. Render the command template with absolute paths.
7. In print mode, return the command array and shell-escaped preview.
8. Set ledger status to `dispatched` after the launch command is generated.

JSON fields:

```json
{
  "ok": true,
  "mode": "print",
  "agent": "codex",
  "agent_id": "codex-feature-foo",
  "path": "/abs/repo/.gitwarp/worktrees/feature-foo",
  "branch": "feature/foo",
  "task_md": "/abs/repo/.gitwarp/dossiers/.../task.md",
  "launch_command": ["codex","--ask-for-approval","never","exec","-C","/abs/worktree","..."],
  "launch_preview": "codex --ask-for-approval never exec -C /abs/worktree '...'"
}
```

### `gitwarp adopt`

Binds an existing live worktree to GitWarp metadata and creates missing dossier files.

Example:

```bash
gitwarp adopt --cwd /abs/repo \
  --path /abs/repo/.gitwarp/worktrees/existing \
  --agent-id claude-existing \
  --purpose "Continue existing work"
```

Rules:

- Refuse the main checkout.
- Refuse paths that are not live Git worktrees.
- Refuse detached worktrees unless `--allow-detached` is added in a later design.
- Refuse adoption when another live worktree already uses the same branch.
- If a ledger entry already exists for the same path, update that entry instead of creating a duplicate.
- If a ledger entry exists for the same branch but a different path, return `ok:false`.
- Duplicate `agent_id` is allowed only when it points to the same path; otherwise return `ok:false` to avoid ambiguous ownership.
- Paths outside `.gitwarp/worktrees/` are allowed if they are live Git worktrees, but the response must include `outside_guarded_root:true`.
- Preserve existing branch and HEAD.
- Create dossier files if missing.
- Update ledger status to `adopted`.

### `gitwarp reconcile`

Audits live Git state against the ledger and dossiers.

Checks:

- Ledger entries whose worktree no longer exists.
- Live Git worktrees missing from the ledger.
- Missing `task.md`, `progress.md`, or `lessons.md`.
- Worktrees with uncommitted changes.
- Worktrees whose `updated_at` is older than `--stale HOURS`.
- Worktrees whose status is `blocked`, `dispatch_failed`, or `merged`.
- Branches whose worktree HEAD is already merged into main.

Default output is JSON with `findings` and `summary`. Add `--repair safe` later or in the same iteration only for non-destructive repairs: prune stale ledger entries and recreate missing dossier templates. Do not delete worktrees or branches from `reconcile`.

Important implementation constraint: `reconcile` must load the raw ledger without calling the existing syncing path that prunes dead entries. Audit mode must be non-mutating so stale ledger entries can be reported instead of silently removed.

### `gitwarp doctor`

Audits the local machine and plugin setup.

Checks:

- `git`, `python3`, and optional configured agent binaries are available.
- `gitwarp --version` works when launcher is on `PATH`.
- Installed launcher points to an existing script.
- Codex plugin metadata exists when Codex is installed.
- Session hook can produce a GitWarp Context block.
- `.gitwarp/` is ignored.

Output should include `severity` values: `ok`, `warning`, or `error`. `doctor` should not mutate state unless a later `--fix` flag is introduced.

## Agent Launch Prompt

Generated dispatch prompts should be short and operational:

```text
You are assigned to a GitWarp isolated worktree.
Run: gitwarp enter --cwd "$PWD"
Read task.md, progress.md, and lessons.md from that context before editing.
Do not run git checkout/git switch in the main repository.
Do not switch branches inside the isolated worktree.
Record milestones with gitwarp handoff.
Stop after implementation and verification; do not merge main unless explicitly asked.

Task: {purpose}
```

The prompt must not duplicate the entire `SKILL.md`. Codex and Claude Code should load the GitWarp skill or session hook themselves.

## Data Model Additions

Ledger entries may gain:

```json
{
  "dispatch": {
    "agent_name": "codex",
    "command_mode": "print",
    "launch_command": ["codex", "..."],
    "launch_preview": "codex ...",
    "last_exit_code": null,
    "last_prepared_at": "2026-06-19T00:00:00+00:00",
    "last_started_at": null,
    "last_finished_at": null
  }
}
```

Keep this optional so existing ledgers remain valid.

## Error Handling

- Missing agent config: use built-in suggestions for `agents`; `dispatch` may use built-in `codex`/`claude` templates if the binary exists.
- Unknown agent: return `ok:false` with available agent names.
- Branch collision: reuse existing hard failure from `start`.
- Command template missing `{worktree}` or `{prompt}`: reject config because it could launch an agent in the wrong directory or without an assignment.
- Execute mode requested in the first slice: return `ok:false` before creating any worktree, dossier, or ledger entry, and do not launch a process.
- Dirty worktree in `reconcile`: report only; do not clean.
- Missing dossier in `adopt`: recreate safe templates.
- Ledger lock timeout: return `ok:false`; do not retry indefinitely.

## Testing Strategy

- Unit tests create temporary Git repositories.
- Test `agents` with no config returns built-in recommendations.
- Test `agents` with a local config parses command arrays and reports binary availability.
- Test malformed config, unknown agent, missing binary, missing `{worktree}`, missing `{prompt}`, and unknown template variable failures.
- Test `dispatch --command-mode print` creates a worktree, creates dossiers, returns rendered command array, and does not spawn a process.
- Test `dispatch --command-mode execute` returns a clear unsupported error without spawning a process and without creating a worktree, dossier, branch, or ledger entry.
- Test `adopt` refuses main, detached worktrees, duplicate branch/path conflicts, and duplicate agent ownership conflicts.
- Test `adopt` accepts an existing non-main worktree and repairs missing dossier files.
- Test `reconcile` reports missing dossiers, dirty worktrees, stale ledger entries, and blocked statuses without mutating the ledger.
- Test `doctor` reports `.gitwarp/` ignore state and launcher status without mutating files.
- Test concurrent ledger writes do not lose updates.
- Extend smoke checks to cover `agents`, `dispatch --command-mode print`, `adopt`, `reconcile`, and `doctor`.

## Rollout Plan

Implement in two slices:

1. Safe orchestration foundation: ledger locking/atomic writes, `agents`, JSON config parser, prompt renderer, `dispatch --command-mode print`, docs, tests.
2. Management audits: `adopt`, `reconcile`, `doctor`, smoke checks.

This keeps the first slice useful without introducing process-management risk too early.

## Open Questions

- Should GitWarp provide `gitwarp agents init` to write a local `.gitwarp/agents.json` from built-in templates?
- What exact process contract should a future `dispatch --command-mode execute` support: timeout, stdin, TTY, logs, cancellation, and output truncation?
- Should Claude Code's exact non-interactive command template be detected dynamically via `claude --help`, or documented as user-configured only?
