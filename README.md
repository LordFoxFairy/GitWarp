# GitWarp

GitWarp is an Agent Skill plus CLI for running Codex, Claude Code, and other coding agents in isolated Git worktrees. It gives each task a physical sandbox, a branch ownership record, and a small dossier (`task.md`, `progress.md`, `lessons.md`) so agents can resume work without guessing what happened before.

The project follows the common Agent Skills layout: `SKILL.md` contains the agent instructions, `scripts/` contains deterministic tools, `references/` contains optional details, and plugin wrappers expose the same skill to supported hosts.

## Why GitWarp

- Prevent branch collisions by refusing to allocate a branch already bound to a worktree.
- Keep the main checkout stable; agents do not run `git switch` in the public repo.
- Give every isolated workspace a task dossier for handoff and memory.
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

For user-global installs, copy or symlink the canonical skill folder:

```bash
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
ln -s "$PWD/skills/gitwarp" "$HOME/.agents/skills/gitwarp"
ln -s "$PWD/skills/gitwarp" "$HOME/.claude/skills/gitwarp"
python3 "$PWD/skills/gitwarp/scripts/install_cli.py"
```

The skill works without the plugin wrapper as long as the host can discover `SKILL.md` and the `gitwarp` launcher is on `PATH`.

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

`board` shows active sandboxes. `reconcile` audits stale ledger rows, dirty worktrees, missing dossiers, and merged branches without mutating state. `doctor` checks Git, Python, the launcher, plugin metadata, hooks, ignored runtime files, and agent binaries.

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

- `skills/gitwarp/`: canonical skill source, CLI helper, installer, and references.
- `.agents/skills/gitwarp` and `.claude/skills/gitwarp`: repo-local standard skill discovery links.
- `plugins/gitwarp/`: marketplace-ready Codex plugin package mirror.
- `.codex-plugin/` and `.claude-plugin/`: plugin metadata shells.
- `.agents/plugins/api_marketplace.json`: local Codex marketplace entry named `gitwarp-dev`.
- `hooks/`: session hook assets for compatible hosts.
- `tests/`: Python regression tests for GitWarp behavior and packaging.

## Development

```bash
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/verify-install.sh
```

Keep `skills/gitwarp/` and `plugins/gitwarp/skills/gitwarp/` synchronized when changing skill behavior. Keep the standard discovery links pointing at the canonical skill folder.
