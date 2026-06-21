---
name: gitwarp
description: Use when concurrent Claude Code or Codex agents need isolated git worktrees, branch collision prevention, workspace context, task dossiers, prompt statusline banners, or persistent handoff records.
---

# GitWarp

## Purpose

GitWarp is the operating protocol for agent work in Git repositories. It keeps agents out of the public checkout by creating native Git worktrees, recording ownership in `.gitwarp/ledger.json`, and attaching a dossier to each task sandbox.

Use GitWarp instead of `git switch`, `git checkout`, or direct `git worktree add` whenever an automated agent will edit files, run experiments, or work concurrently with another agent.

## Operating Model

- The root checkout is the control plane. Use it for coordination, review, release checks, and Web Console supervision.
- Managed worktrees live under `.gitwarp/worktrees/` and follow branch hierarchy: `feature/my-task` maps to `.gitwarp/worktrees/feature/my-task`.
- Dossiers live under `.gitwarp/dossiers/` and contain `task.md`, `progress.md`, and `lessons.md`. They are read through `gitwarp enter`, `gitwarp context`, `gitwarp board`, or the Web Console Metadata tab.
- Git live state is the source of truth. `matrix` compares Git refs, live worktrees, ledger rows, and dossiers before any cleanup decision.

## Command Map

| Command | Use |
| --- | --- |
| `gitwarp task create` | Preferred intake for new user work; creates a task worktree and richer dossier from title, description, acceptance, and verification notes. |
| `gitwarp create` | Lower-level creation for explicit base worktrees or manually specified sandboxes. |
| `gitwarp switch` | Locate an existing worktree and print its path or a shell `cd` command. |
| `gitwarp remove` | Destroy one explicit sandbox and its dossier; use `--force` only when dirty removal is intended. |
| `gitwarp matrix` | Read-only control-plane view of refs, worktrees, ledger rows, and dossiers. |
| `gitwarp next` | Read-only prioritized action queue derived from `matrix`. |
| `gitwarp sweep` | Batch-clean clean, merged, GitWarp-managed task worktrees; preserves branch refs. |
| `gitwarp branches` | List local branch refs with cleanup safety metadata. |
| `gitwarp prune-branch` | Delete only a safe merged local branch ref after explicit selection. |
| `gitwarp handoff` | Record progress and optional lessons for the current sandbox. |
| `gitwarp pause` / `gitwarp resume` | Mark a task blocked or active without destroying context. |
| `gitwarp statusline` | Print a raw prompt banner such as `GITWARP[main-repo]`. |
| `gitwarp enter` | Return session context and dossier snippets when full task context is needed. |
| `gitwarp board` | List active sandboxes. |
| `gitwarp reconcile` | Read-only audit for dirty, stale, missing, merged, or drifted worktrees. |
| `gitwarp doctor` | Check install, hook, plugin, launcher, and runtime health. |
| `gitwarp upgrade --check` | Detect stale launchers without writing files. |
| `gitwarp upgrade` | Explicitly rewrite the local launcher from the current checkout or plugin cache. |
| `gitwarp web` | Start the local Web Console in the foreground. |

Prefer `task create` for new work. Use `create --role base` for long-lived user feature branches. Use `switch` for navigation and `remove` only when the sandbox should actually be destroyed.

## Session Startup Loop

At the start of substantial work:

1. Confirm location with `pwd` and `gitwarp statusline`.
2. Run `gitwarp matrix` or `gitwarp next` before creating, adopting, sweeping, pruning, or repairing anything.
3. If inside a task sandbox, run `gitwarp enter` and read `task.md`, `progress.md`, and `lessons.md`. Read the dossier before editing.
4. Check the repository's native dependency and smoke commands. For GitWarp itself, prefer `scripts/check-release.sh`; for narrow edits, run the closest focused checks first.
5. Work on one unfinished task until its verification gate passes or it is explicitly paused.

Use `statusline` in hooks. Do not wire full `enter` output into every session start; it is intentionally richer and noisier than a prompt badge.

## Creating Work

If edits are needed and the agent is in the main checkout, create an isolated task:

```bash
gitwarp task create --title "Implement isolated task" \
  --branch agent/user-request-impl \
  --description "Build the requested change in an isolated worktree" \
  --acceptance "Tests cover the new behavior" \
  --verify "python3 -m unittest discover -s tests -p 'test_*.py' -v"
```

Move into the returned `path`. To return later:

```bash
gitwarp switch --branch agent/user-request-impl
gitwarp switch --branch agent/user-request-impl --format shell
```

If the user asks for a dedicated feature branch, create it as a base first, then create task branches under it:

```bash
gitwarp create --role base --branch feature/user-request \
  --purpose "Coordinate user-request work"

gitwarp task create --base feature/user-request \
  --title "Implement user-request task" \
  --branch agent/user-request-impl \
  --description "Implement the requested feature in an agent task worktree"
```

## Branch Roles

- `base`: long-lived coordination branch. `main` is always base. User-requested feature branches are usually base. Base worktrees do not have task dossiers and must not be auto-collapsed.
- `task`: short-lived agent branch under a `base_branch`. Task branches have dossiers and may be removed only after they are merged into their parent base or when the user explicitly requests removal.

Unknown legacy branches should be treated as base-like until `matrix` classifies them. Mark merged or deprecated candidates for user review; do not silently prune them.

## Working Inside A Sandbox

Inside a task worktree, read the dossier first, then make the smallest coherent change. Record milestones:

```bash
gitwarp handoff --status implementing \
  --progress "Short, factual milestone"
```

If blocked:

```bash
gitwarp pause --reason "Waiting for credentials"
gitwarp resume --progress "Credentials configured; continuing"
```

If the user assigns an existing worktree, finish the requested work there and stop after verification unless the user explicitly asks for push, merge, remove, collapse, sweep, or prune.

## Cleanup Semantics

Completion is not cleanup. Verification, push, merge, worktree removal, and branch-ref pruning are separate actions.

When verified, record the outcome and leave the sandbox intact unless cleanup was explicitly requested:

```bash
gitwarp finish --status pushed \
  --progress "Verified and pushed"
```

When a task branch has already been merged into its parent base and the worktree is clean:

```bash
gitwarp finish --status merged \
  --progress "Merged into parent base" \
  --collapse-merged
```

`finish --collapse-merged` refuses base worktrees, dirty worktrees, and task branches whose HEAD is not merged into `base_branch`.

To clean multiple merged task sandboxes:

```bash
gitwarp sweep --merged-tasks --dry-run
gitwarp sweep --merged-tasks
```

`sweep --merged-tasks` removes only clean GitWarp-managed task worktrees whose branch HEAD is merged into their parent `base_branch`. It deletes the worktree, ledger row, and matching dossier. It does not delete local branch refs, base worktrees, unmanaged worktrees, dirty worktrees, or unmerged task worktrees.

For explicit destructive removal regardless of merge state:

```bash
gitwarp finish --status pushed \
  --progress "Verified and pushed" \
  --collapse
```

`gitwarp remove`, `gitwarp finish --collapse`, `gitwarp finish --collapse-merged`, and `gitwarp sweep --merged-tasks` delete the worktree, its ledger row, and the matching `.gitwarp/dossiers/...` directory. They do not merge, push, or delete the Git branch.

For local branch refs, use separate commands:

```bash
gitwarp branches
gitwarp prune-branch --branch feature/old-merged-task
```

`prune-branch` refuses the default branch, base branches, branches checked out in any worktree, branches still tracked in the GitWarp ledger, and branches whose HEAD is not merged into the selected base.

## Matrix And Repair

Use `gitwarp matrix` when onboarding a repository or when `.git` and `.gitwarp` look inconsistent. It is read-only.

Use `gitwarp next` after `matrix` for a short prioritized queue. It returns actions such as `merged_task`, `merged_ref`, `untracked_worktree`, `stale_ledger`, and `orphan_dossier` with `safety`, `priority`, and suggested commands.

- `untracked_worktree`: ask before adopting, then use the printed `gitwarp adopt ...` command.
- `stale_ledger`: metadata points to a worktree Git no longer reports. Treat this as metadata repair, not branch deletion.
- `orphan_dossier`: legacy dossier directory not referenced by the ledger. Do not delete manually unless asked.
- `merged_ref`: unmanaged local branch ref merged into the selected baseline and safe by GitWarp blockers. Delete only after explicit user selection.
- `merged_task`: live task worktree already merged into its parent base. Collapse only through `finish --collapse-merged` or `sweep --merged-tasks`.

If rows share a branch, use `row_id` to distinguish branch refs, live worktrees, stale ledger rows, and dossier-only records.

## Python and TypeScript Guardrails

When changing Python runtime code, preserve DDD boundaries: `domain/` stays pure, `application/` orchestrates use cases, `infrastructure/` owns Git/filesystem/process adapters, and `adapters/` owns CLI/Web entrypoints. Do not leak subprocess, filesystem, framework, or Web concerns into domain code.

Prefer Python standard library, small functions, and explicit data flow. Avoid compatibility shims, deferred imports, `type: ignore`, broad `Any`, cross-module private access, and speculative abstractions unless a real boundary requires them.

When changing Web Console TypeScript, keep API contracts explicit, validate unsafe payloads at the boundary, avoid `any`, and follow the existing React/Vite/Primer structure. Do not manually duplicate backend contracts when a generated or shared contract path exists.

For both stacks, run the narrowest relevant checks first, then the broader release gate before claiming completion.

## Failure Pivot Rule

If a command, test, or assumption fails unexpectedly:

1. Stop the current implementation path.
2. Re-read the relevant callers, exports, tests, and shared helpers.
3. Update the plan or dossier with the new finding.
4. If the failure came from user correction, record the correction with `gitwarp handoff --lesson "..."` so later agents do not repeat it.

Do not patch around unexplained failures. Diagnose first, then change code or documentation.

## Handoff Standard

Before pausing, handing off, or asking for review:

- Record what changed with `gitwarp handoff --status <status> --progress "<summary>"`.
- Add `--lesson` for reusable rules, pitfalls, or user preferences.
- State the exact verification command that passed, or the exact blocker that remains.
- Leave assigned existing worktrees intact unless the user explicitly asked for push, merge, remove, collapse, sweep, or prune.
- Keep the working tree free of unrelated untracked files; ignore or remove generated residue before final status.

## Instruction Mounting

Local instruction files are not mounted automatically. Pass them explicitly when creating a sandbox:

```bash
gitwarp task create --title "Implement isolated task" \
  --branch agent/isolated-task \
  --instruction AGENTS.md \
  --instruction CLAUDE.md=docs/claude-code.md
```

Repeatable instruction stacks live in `.gitwarp/instruction_profiles.json` and are selected with `--instruction-profile <name>`. Instructions are copied by default; use `--instruction-mode symlink` only when live rule edits are intended.

## Output Contract

Automation commands print deterministic single-line JSON. `statusline`, `enter --format prompt`, `board --format table`, and `switch --format shell` intentionally print raw text.

If a JSON command returns nonzero or `"ok": false`, stop and report the `error` field.

`--cwd /absolute/path` is optional. Use it from hooks, Web/API handlers, scripts, or when controlling a repository from another directory. For normal terminal use inside the target repo or sandbox, omit it.

## Web Console

Use `gitwarp web` for human supervision. It opens a local GitHub-like console where users can select a project, choose base and task worktrees, browse committed files, inspect Metadata, review Refs & Worktrees, and check Health.

Use `--readonly` when supervising without mutations. Use `--host` and `--port` only when the local environment requires explicit binding.

## Installation Notes

Use `gitwarp` from `PATH`. The skill `scripts/` directory contains bootstrap helpers only, primarily `scripts/install_cli.py`; product runtime code belongs in `src/gitwarp/`.

After installing or refreshing a plugin cache, run `gitwarp upgrade --check`. A `stale` result means the shell launcher still points at older runtime behavior; run `gitwarp upgrade` only when the user or operator agrees to refresh it.

Read `references/install.md` only when installing, packaging, or troubleshooting plugin discovery.
