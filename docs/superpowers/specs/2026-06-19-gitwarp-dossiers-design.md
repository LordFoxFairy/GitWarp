# GitWarp Dossiers Design

> Status: Historical record. Superseded by `2026-06-20-gitwarp-ddd-architecture-design.md` and the repository README. Do not follow old `plugins/gitwarp` mirror instructions.

## Problem

GitWarp can isolate agents in worktrees and record metadata, but the current memory model is still too thin. An agent can identify its worktree, branch, owner, purpose, status, and notes, yet it does not get a durable task dossier that explains the assignment, current progress, and lessons learned in a way both humans and future agents can scan quickly.

## Goals

- Give every GitWarp-managed worktree a local dossier with `task.md`, `progress.md`, and `lessons.md`.
- Make the high-level agent workflow feel natural through `start`, `board`, `handoff`, and `finish`.
- Keep low-level commands (`summon`, `context`, `annotate`, `collapse`) available and deterministic.
- Keep generated dossier files out of feature branches by default.
- Make it easy for a new agent entering any nested directory in a worktree to understand prior work.

## Non-Goals

- Do not build a full TUI or web UI in this iteration.
- Do not store dossiers inside feature worktree roots by default.
- Do not replace commits, PR descriptions, or issue trackers.
- Do not sync dossier files to remote storage yet.

## Dossier Storage

Each repository keeps dossiers under:

```text
.gitwarp/dossiers/<workspace-id>/
├── task.md
├── progress.md
└── lessons.md
```

`<workspace-id>` should be deterministic and collision-resistant. Use a sanitized branch name plus a short stable suffix derived from the worktree path or branch, for example `feature-my-task-a1b2c3`.

Ledger entries will include absolute paths:

```json
{
  "dossier_path": "/abs/repo/.gitwarp/dossiers/feature-my-task-a1b2c3",
  "task_md": "/abs/repo/.gitwarp/dossiers/feature-my-task-a1b2c3/task.md",
  "progress_md": "/abs/repo/.gitwarp/dossiers/feature-my-task-a1b2c3/progress.md",
  "lessons_md": "/abs/repo/.gitwarp/dossiers/feature-my-task-a1b2c3/lessons.md"
}
```

## File Templates

`task.md` is the stable assignment brief:

```markdown
# Task

- Agent: codex-alpha
- Branch: feature/my-task
- Worktree: /abs/repo/.gitwarp/worktrees/feature-my-task
- Purpose: Implement isolated task
- Status: active
- Created: 2026-06-19T00:00:00+00:00

## Scope

Implement isolated task

## Success Criteria

- [ ] Define concrete verification before finishing
```

`progress.md` is the running work log:

```markdown
# Progress

## 2026-06-19T00:00:00+00:00

- Status: active
- Note: Workspace created.
```

`lessons.md` is durable handoff knowledge:

```markdown
# Lessons

## Notes For Future Agents

- Add findings, pitfalls, and decisions that should survive handoff.
```

## Command Design

### `gitwarp start`

High-level agent entry command. It should perform `summon` plus dossier creation.

Example:

```bash
gitwarp start --cwd /abs/repo \
  --agent-id codex-alpha \
  --branch feature/my-task \
  --purpose "Implement isolated task"
```

Output remains single-line JSON and includes the worktree path plus dossier file paths.

Rules:

- Abort on branch collision.
- Create dossier files before returning success.
- Set initial status to `active`.
- Keep `summon` as a lower-level command. `summon` may either keep current behavior or accept `--with-dossier` later; `start` is the recommended default.

### `gitwarp context`

Extend current context output to include dossier paths and lightweight extracted summaries:

```json
{
  "worktree": {
    "agent_id": "codex-alpha",
    "branch": "feature/my-task",
    "purpose": "Implement isolated task",
    "status": "testing",
    "task_md": "/abs/.../task.md",
    "progress_md": "/abs/.../progress.md",
    "lessons_md": "/abs/.../lessons.md"
  }
}
```

Agents should read the three Markdown files after `context` when resuming a worktree.

### `gitwarp handoff`

Append a progress note and optionally a lesson.

Example:

```bash
gitwarp handoff --cwd "$PWD" \
  --status testing \
  --progress "Implemented parser and tests pass locally." \
  --lesson "Do not use direct git checkout in the main repo."
```

Behavior:

- Append progress to `progress.md`.
- Append lesson to `lessons.md` when provided.
- Update ledger `status`, `updated_at`, `notes`, and latest summary.
- Return single-line JSON.

### `gitwarp board`

Human management view across all active GitWarp worktrees.

Default output should stay automation-safe JSON:

```bash
gitwarp board --cwd /abs/repo
```

Rows include branch, agent, status, purpose, worktree path, task file, latest progress note, and latest lesson.

For humans, add a deterministic table view:

```bash
gitwarp board --cwd /abs/repo --format table
```

The table view can be multi-line text and is explicitly not the automation contract.

### `gitwarp finish`

High-level exit command. It should append final progress/lesson records and then collapse or archive.

Example:

```bash
gitwarp finish --cwd "$PWD" \
  --status pushed \
  --progress "Tests passed and branch pushed." \
  --lesson "Fixture setup must happen before worktree creation." \
  --collapse
```

Rules:

- Default should not destroy work unless `--collapse` is provided.
- With `--collapse`, call the same forceful removal path as `collapse`.
- Dossier should remain under `.gitwarp/dossiers/` after collapse for audit unless `--purge-dossier` is explicitly provided.

## Data Flow

1. User or agent runs `gitwarp start`.
2. GitWarp creates a worktree and ledger entry.
3. GitWarp creates dossier files and stores their absolute paths in the ledger.
4. Agent enters the worktree and runs `gitwarp context --cwd "$PWD"`.
5. Agent reads `task.md`, `progress.md`, and `lessons.md`.
6. Agent uses `handoff` during meaningful milestones.
7. User runs `board` to inspect all active work.
8. Agent runs `finish` after verification and optional push.

## Error Handling

- Missing dossier paths: `context` should report them as missing but not fail; `start` and `handoff` should repair by recreating missing templates when safe.
- Branch collision: `start` aborts with the same hard error as `summon`.
- Main repository handoff: refuse unless `--path` or `--branch` targets a non-main worktree.
- Collapse with unverified state: GitWarp cannot prove verification, so require explicit `finish --collapse`; do not collapse implicitly.
- Dossier write failure: command returns `ok:false` and must not partially claim success.

## Testing Strategy

- Unit/integration tests create temporary Git repositories.
- Test `start` creates a worktree, ledger entry, and all three Markdown files.
- Test `context` from a nested worktree directory returns dossier paths.
- Test `handoff` appends progress and lesson text and updates ledger status.
- Test `board` JSON includes task/progress/lesson summaries.
- Test `finish --collapse` removes the worktree while preserving the dossier.
- Extend install smoke checks to cover `start`, `handoff`, `board`, `context`, and `finish`.

## Migration

Existing worktrees created with `summon` will not have dossiers. `context` should still work. A later `gitwarp dossier init --cwd "$PWD"` or `handoff` can create missing dossier files, but that repair command can wait unless needed during implementation.
