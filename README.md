# GitWarp

GitWarp is an Agent Skill plus installable CLI package for running Codex, Claude Code, and other coding agents in isolated Git worktrees. It gives each task a physical sandbox, a branch ownership record, and a small dossier (`task.md`, `progress.md`, `lessons.md`) so agents can resume work without guessing what happened before.

The project follows the common Agent Skills layout while keeping product code in a normal Python package. `src/gitwarp/` is the canonical runtime, `skills/gitwarp/` contains agent instructions plus tiny wrappers, and `plugins/gitwarp/` is the self-contained plugin distribution mirror.

## Why GitWarp

- Prevent branch collisions by refusing to allocate a branch already bound to a worktree.
- Keep the main checkout stable; agents do not run `git switch` in the public repo.
- Give every isolated workspace a task dossier for handoff and memory.
- Detect unmanaged worktree commits with non-mutating `head_drift` audit findings.
- Mark blocked work with `pause` and resume cleanly with `resume`.
- Emit strict one-line JSON for automation and a raw `statusline` banner for prompts.
- Support both standard skill discovery and Codex plugin installation.

## Install

### Codex Plugin Path

From this checkout:

```bash
scripts/install-codex-plugin.sh
gitwarp init --cwd "$PWD"
gitwarp doctor --cwd "$PWD"
```

This registers the local marketplace `gitwarp-dev`, installs `gitwarp@gitwarp-dev`, and writes the `gitwarp` launcher to `~/.local/bin/gitwarp`.

Manual equivalent:

```bash
codex plugin marketplace add "$PWD" --json
codex plugin add gitwarp@gitwarp-dev --json
python3 "$HOME/.codex/plugins/cache/gitwarp-dev/gitwarp/0.1.0/skills/gitwarp/scripts/install_cli.py"
```

### Standard Skill Path

GitWarp also exposes repo-local standard skill locations:

- Codex: `.agents/skills/gitwarp -> ../../skills/gitwarp`
- Claude Code: `.claude/skills/gitwarp -> ../../skills/gitwarp`

For source checkout installs, symlink the canonical skill folder so the wrapper can resolve the adjacent `src/gitwarp` package:

```bash
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
ln -s "$PWD/skills/gitwarp" "$HOME/.agents/skills/gitwarp"
ln -s "$PWD/skills/gitwarp" "$HOME/.claude/skills/gitwarp"
python3 "$PWD/skills/gitwarp/scripts/install_cli.py"
```

For copy-only installs, install the full plugin package or install the Python package first. Copying only `skills/gitwarp/` is not enough because the core implementation lives in `src/gitwarp/`.

## Quick Start

Initialize each target repository once, then run a read-only diagnostic:

```bash
gitwarp init --cwd "$PWD"
gitwarp doctor --cwd "$PWD"
```

Start every repository session with context:

```bash
gitwarp enter --cwd "$PWD"
```

Create a sandbox and get a ready-to-run worker command:

```bash
gitwarp dispatch --cwd "$PWD" \
  --agent codex \
  --branch feature/my-task \
  --purpose "Implement isolated task"
```

Run the returned `launch_command`. The worker should begin inside the returned absolute `path`, read `task.md`, `progress.md`, and `lessons.md`, then record milestones:

```bash
gitwarp handoff --cwd "$PWD" \
  --status testing \
  --progress "Implemented regression test and minimal fix" \
  --lesson "Read dossier before editing nested paths"
```

If work is blocked waiting for a human or external dependency:

```bash
gitwarp pause --cwd "$PWD" \
  --reason "Waiting for credentials" \
  --lesson "Do not retry deployment without credentials"

gitwarp resume --cwd "$PWD" \
  --progress "Credentials configured; continuing"
```

When the task is verified and pushed:

```bash
gitwarp finish --cwd "$PWD" \
  --status pushed \
  --progress "Verified and pushed" \
  --collapse
```

## Usage Modes

### Human Operator

Use these commands when you are coordinating agents from the main checkout:

```bash
gitwarp board --cwd "$PWD" --format table
gitwarp reconcile --cwd "$PWD" --stale 4
gitwarp doctor --cwd "$PWD"
```

`board` shows active sandboxes. `reconcile` audits stale ledger rows, dirty worktrees, missing dossiers, merged branches, and `head_drift` without mutating state. `head_drift` means the live worktree HEAD differs from the last GitWarp-recorded handoff point. `doctor` checks Git, Python, the launcher, plugin metadata, hooks, ignored runtime files, and agent binaries.

### Automated Agent

Agents should use this minimal loop:

```bash
gitwarp enter --cwd "$PWD"
# read returned task_md, progress_md, lessons_md
gitwarp handoff --cwd "$PWD" --status implementing --progress "Short milestone"
gitwarp statusline --cwd "$PWD"
```

`statusline` prints an unquoted banner such as `GITWARP[main-repo]` or `GITWARP[codex-alpha@feature/my-task]` for shell prompts and downstream model context.

### Existing Worktree

If a non-main worktree already exists, bind it into GitWarp instead of recreating it:

```bash
gitwarp adopt --cwd /absolute/path/to/repo \
  --path /absolute/path/to/existing-worktree \
  --agent-id claude-existing \
  --purpose "Continue existing sandbox"
```

## Runtime Model

GitWarp stores runtime state under `.gitwarp/` in the target repository. Run `gitwarp init --cwd "$PWD"` to create this state safely before dispatching agents.

- Worktrees: `.gitwarp/worktrees/<worktree-name>`
- Ledger: `.gitwarp/ledger.json`
- Agent launch config: `.gitwarp/agents.json`
- Dossiers: `.gitwarp/dossiers/<branch-slug>-<id>/`

By default, `init` writes `/.gitwarp/` to `.git/info/exclude`, which keeps runtime files local to one checkout. Use `gitwarp init --write-gitignore` when the team wants the ignore rule committed to `.gitignore`.

`dispatch` is intentionally print-only in this release. `--command-mode execute` fails before creating anything so humans can review agent launch commands and host-specific flags.

Example `.gitwarp/agents.json`:

```json
{
  "version": 1,
  "default_agent": "codex",
  "agents": {
    "codex": {
      "command": ["codex", "--ask-for-approval", "never", "exec", "-C", "{worktree}", "{prompt}"]
    },
    "claude": {
      "command": ["claude", "-C", "{worktree}", "{prompt}"]
    }
  }
}
```

## Repository Layout

- `src/gitwarp/`: canonical Python package and CLI implementation.
- `src/gitwarp/assets/`: packaged static assets; future web builds go under `assets/web-console/`.
- `skills/gitwarp/`: canonical Agent Skill instructions, wrapper script, installer, and references.
- `.agents/skills/gitwarp` and `.claude/skills/gitwarp`: repo-local standard skill discovery links.
- `plugins/gitwarp/`: marketplace-ready Codex plugin package mirror, including its own `src/gitwarp/` copy.
- `.codex-plugin/` and `.claude-plugin/`: plugin metadata shells.
- `.agents/plugins/api_marketplace.json`: local Codex marketplace entry named `gitwarp-dev`.
- `hooks/`: session hook assets for compatible hosts.
- `web/`: future rich web console source; do not put frontend source under `skills/`.
- `tests/`: Python regression tests for GitWarp behavior and packaging.

## Development

```bash
python3 -m py_compile src/gitwarp/*.py plugins/gitwarp/src/gitwarp/*.py skills/gitwarp/scripts/*.py plugins/gitwarp/skills/gitwarp/scripts/*.py
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/verify-install.sh
```

Keep `src/gitwarp/` and `plugins/gitwarp/src/gitwarp/` synchronized when changing runtime behavior. Keep `skills/gitwarp/` and `plugins/gitwarp/skills/gitwarp/` synchronized when changing skill behavior. Keep the standard discovery links pointing at the canonical skill folder.
