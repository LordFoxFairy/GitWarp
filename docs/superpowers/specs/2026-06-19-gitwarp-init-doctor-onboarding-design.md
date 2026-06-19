# GitWarp Init And Doctor Onboarding Design

## Problem

GitWarp has a working skill/plugin shape and a useful CLI, but first-run setup still feels manual. A user or agent must infer whether `.gitwarp/` is ignored, whether runtime folders exist, whether the launcher points to the installed plugin, whether repo-local skill discovery links are present, and whether session hooks are usable. The current `doctor` command reports some environment health, but it does not give an explicit setup path and it executes the session hook as part of diagnosis, which is too invasive for a read-only audit command.

## Goals

- Add a deterministic `gitwarp init` command that bootstraps GitWarp runtime state for a repository.
- Make first-run setup safe by default: initialize ignored runtime files without dirtying the tracked worktree.
- Preserve existing valid ledger entries and make repeated `init` runs idempotent.
- Strengthen `doctor` into a fully read-only diagnostic command with concrete `recommended_next` guidance.
- Detect and report broken setup states before users dispatch agents.
- Keep all automation-facing output strict single-line JSON.
- Update README, SKILL, install notes, plugin mirror, tests, and smoke verification so setup feels like a standard skill/plugin workflow.

## Non-Goals

- Do not add tmux/process launch mode in this iteration.
- Do not add batch task dispatch or task YAML schema in this iteration.
- Do not automatically install Codex or Claude Code.
- Do not mutate tracked `.gitignore` unless the user explicitly requests it.
- Do not auto-run `gitwarp init` from hooks or `doctor`.
- Do not repair malformed ledgers silently.
- Do not add non-standard-library dependencies.

## Design Summary

Add `gitwarp init --cwd <repo>` as the explicit first-run repository setup command. It creates `.gitwarp/`, `.gitwarp/worktrees/`, `.gitwarp/dossiers/`, and `.gitwarp/ledger.json` if needed. By default it appends `/.gitwarp/` to `.git/info/exclude`, not `.gitignore`, so a local user can initialize GitWarp without creating a tracked diff. `--write-gitignore` is available when a team wants the ignore rule committed.

Refactor `doctor` around reusable checks and make it read-only. It should report runtime initialization, ledger schema, ignore coverage, standard skill discovery links, launcher/version, agent registry, plugin metadata, static hook presence, and setup recommendations. It must never execute repository hook scripts.

## Command: `gitwarp init`

### CLI

```bash
gitwarp init --cwd /absolute/path/to/repo
gitwarp init --cwd /absolute/path/to/repo --write-gitignore
```

### Default Behavior

1. Discover the root repository from `--cwd` or current directory.
2. Validate that `.gitwarp` is absent or a directory.
3. Create `.gitwarp/`, `.gitwarp/worktrees/`, and `.gitwarp/dossiers/`.
4. Create `.gitwarp/ledger.json` only if absent.
5. If a valid ledger already exists, preserve it exactly except for normal schema normalization when a write is required.
6. Ensure the repo ignores `/.gitwarp/` by appending it to `.git/info/exclude` if no ignore rule already covers `.gitwarp`.
7. Return JSON containing paths, created/updated booleans, ignore target, and recommended next commands.

### `--write-gitignore`

When passed, `init` writes `/.gitwarp/` to the tracked `.gitignore` instead of `.git/info/exclude`. This is explicit because it dirties the repo and should be a team decision.

Rules:

- Do not duplicate ignore entries if either `.git/info/exclude` or `.gitignore` already ignores `.gitwarp`.
- Preserve existing file content and append a newline before the new entry when needed.
- If `.gitignore` is a directory or cannot be written, return `ok:false`.

### JSON Shape

```json
{
  "ok": true,
  "repo_root": "/abs/repo",
  "ledger_path": "/abs/repo/.gitwarp/ledger.json",
  "worktree_root": "/abs/repo/.gitwarp/worktrees",
  "dossier_root": "/abs/repo/.gitwarp/dossiers",
  "created": {
    "ledger_dir": true,
    "ledger": true,
    "worktree_root": true,
    "dossier_root": true,
    "ignore_rule": true
  },
  "ignore_target": "/abs/repo/.git/info/exclude",
  "recommended_next": [
    "gitwarp doctor --cwd \"/abs/repo\"",
    "gitwarp enter --cwd \"/abs/repo\"",
    "gitwarp dispatch --cwd \"/abs/repo\" --agent codex --branch <branch> --purpose \"<purpose>\""
  ]
}
```

### Failure Cases

- `.gitwarp` exists as a file: fail before mutation.
- `.gitwarp/worktrees` or `.gitwarp/dossiers` exists as a file: fail before mutation.
- `ledger.json` exists but is invalid JSON or has invalid schema: fail and do not overwrite.
- Git repository discovery fails: existing JSON error path handles this.
- Ignore target cannot be written: fail with a clear path in the error.

## Doctor Redesign

`doctor` remains a read-only JSON command.

### Required Checks

| Code | Severity Rules |
| --- | --- |
| `git` | `ok` when `git` is on `PATH`, else `error`. |
| `python3` | `ok` when `python3` is on `PATH`, else `error`. |
| `gitwarp_launcher` | `ok` when launcher exists and `--version` works, `warning` when missing, `error` when broken. |
| `gitwarp_initialized` | `ok` when `.gitwarp/`, `worktrees/`, `dossiers/`, and ledger exist; `warning` when not initialized; `error` on path collisions. |
| `ledger_schema` | `ok` for valid ledger or absent ledger before init; `error` for malformed JSON/schema. |
| `gitwarp_ignored` | `ok` when Git ignore covers `.gitwarp`; `warning` otherwise. |
| `standard_skill_links` | `ok` when repo-local `.agents/skills/gitwarp` and `.claude/skills/gitwarp` resolve to `skills/gitwarp`; `warning` when missing or wrong. |
| `agent_binary` | One finding per configured/built-in agent, same as current behavior. |
| `agent_config` | `ok` when valid or absent; `error` when `.gitwarp/agents.json` is malformed. |
| `codex_plugin_metadata` | Existing Codex plugin check, warning if Codex/plugin metadata unavailable. |
| `session_hook_context` | Static check only: hook file exists, executable, and contains `gitwarp enter --cwd`; do not execute it. |

### Recommended Next

Add top-level `recommended_next: string[]`. Populate it from findings, for example:

- Missing runtime: `gitwarp init --cwd "<repo>"`
- Missing ignore rule: `gitwarp init --cwd "<repo>"`
- Missing launcher: `python3 "<skill>/scripts/install_cli.py"`
- Invalid agents config: fix `.gitwarp/agents.json` or remove it.
- Missing plugin: `scripts/install-codex-plugin.sh`
- Missing standard links: restore `.agents/skills/gitwarp` and `.claude/skills/gitwarp` symlinks or install the plugin.

Recommendations should be deterministic and de-duplicated.

### Hook Safety

The current hook diagnostic executes `hooks/session-start-codex`, which may install the CLI and call GitWarp. Replace this with static inspection:

- Check file exists.
- Check executable bit.
- Read text and verify it references `gitwarp enter --cwd`.
- Report `warning` if the hook is missing, not executable, or lacks context injection.

## Documentation Updates

README quick start should become:

```bash
scripts/install-codex-plugin.sh
gitwarp init --cwd "$PWD"
gitwarp doctor --cwd "$PWD"
```

SKILL.md should state that agents should recommend `gitwarp init` when `doctor` reports missing runtime, but should not auto-initialize without user intent unless the task is explicitly repository setup.

Install notes should explain the two ignore modes:

- Default local mode: `.git/info/exclude`
- Team mode: `--write-gitignore`

Session hook text may mention `gitwarp init`, but hooks must not run it automatically.

## Test Strategy

Add tests in `tests/test_gitwarp.py`:

- `test_init_bootstraps_runtime_state_and_is_idempotent`
- `test_init_preserves_existing_ledger_entries`
- `test_init_refuses_invalid_existing_state`
- `test_doctor_reports_setup_guidance_without_mutation`
- `test_doctor_reports_invalid_ledger_error`
- `test_doctor_does_not_execute_repo_hook`

Update `scripts/verify-install.sh` to call `gitwarp init` in the temporary repo before writing `.gitwarp/agents.json`, assert init JSON fields, assert doctor includes the new check codes, and update the smoke label to include `init`.

Keep existing lifecycle tests unchanged unless the new setup checks require expected code additions.

## Rollout

Implement in small commits:

1. Tests for `init` behavior.
2. `init` implementation.
3. Tests for safe `doctor`.
4. `doctor` refactor.
5. Docs, skill, plugin mirror, and install smoke.

Run:

```bash
bash -n scripts/verify-install.sh hooks/session-start hooks/session-start-codex scripts/install-codex-plugin.sh
python3 -m py_compile skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
scripts/verify-install.sh
```

## Open Decisions

- Keep the default ignore target as `.git/info/exclude`. This is a decision, not an open question.
- Keep `doctor` read-only. Any future repair command should be explicit, for example `gitwarp repair`, not hidden inside `doctor`.
- Do not implement `launch` or batch dispatch in this slice.
