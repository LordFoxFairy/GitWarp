# GitWarp

GitWarp is a Codex/Claude skill-plugin for coordinating concurrent coding agents with isolated `git worktree` sandboxes and task records. It follows the Agent Skills pattern: the reusable behavior lives in `skills/gitwarp/SKILL.md`, deterministic operations live in `scripts/`, and plugin shells expose the skill to supported agents.

The bundled CLI is implemented in Python with only the standard library plus the system `git` command. Treat Python as an implementation detail; after installation, agents should call `gitwarp`.

## Repository Layout

- `skills/gitwarp/`: canonical skill source, CLI helper, installer, and install reference.
- `plugins/gitwarp/`: marketplace-ready plugin package mirror used by Codex installation.
- `.codex-plugin/` and `.claude-plugin/`: plugin metadata shells.
- `.agents/plugins/api_marketplace.json`: local Codex marketplace entry named `gitwarp-dev`.
- `hooks/`: session hook assets kept for compatible hosts.
- `tests/`: Python regression tests for worktree lifecycle behavior.

## Install For Codex

From this checkout:

```bash
scripts/install-codex-plugin.sh
```

Manual equivalent:

```bash
codex plugin marketplace add "$PWD" --json
codex plugin add gitwarp@gitwarp-dev --json
python3 "$HOME/.codex/plugins/cache/gitwarp-dev/gitwarp/0.1.0/skills/gitwarp/scripts/install_cli.py"
```

Ensure `~/.local/bin` is on `PATH`, then verify:

```bash
gitwarp --version
gitwarp scan --cwd "$PWD"
```

## CLI Usage

```bash
gitwarp enter --cwd "$PWD"
gitwarp scan --cwd /absolute/path/to/repo
gitwarp start --cwd /absolute/path/to/repo \
  --agent-id codex-alpha \
  --branch feature/my-task \
  --purpose "Implement isolated task"
gitwarp context --cwd "$PWD"
gitwarp handoff --cwd "$PWD" \
  --status testing \
  --progress "Implemented first passing test" \
  --lesson "Read context before editing nested paths"
gitwarp board --cwd /absolute/path/to/repo --format table
gitwarp board --cwd /absolute/path/to/repo --status blocked --verbose
gitwarp board --cwd /absolute/path/to/repo --stale 4
gitwarp statusline --cwd "$PWD"
gitwarp finish --cwd "$PWD" \
  --status pushed \
  --progress "Verified and pushed" \
  --collapse
```

`enter`, `scan`, `start`, `summon`, `context`, `annotate`, `handoff`, `board`, `finish`, and `collapse` emit strict one-line JSON by default. `statusline` emits a raw banner such as `GITWARP[main-repo]` or `GITWARP[codex-alpha@feature/my-task]`. `enter --format prompt` and `board --format table` are the human-readable exceptions.

Use `enter` at the start of a session. In the main repo it returns the main badge and a recommended `gitwarp start` command; inside a sandbox it returns the active agent, branch, dossier paths, and short task/progress/lesson snippets. The session hooks call `gitwarp enter --format prompt` automatically when supported, but they do not create a worktree for you.

Use `start` for new isolated agent work because it creates the worktree plus `task.md`, `progress.md`, and `lessons.md` under `.gitwarp/dossiers/`. Use `context` for deeper machine-readable inspection. Use `handoff` after meaningful milestones so later agents can see progress and lessons through `enter`, `context`, or `board`. Low-level `summon`, `annotate`, and `collapse` remain available for scripts.

## Development Checks

```bash
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/verify-install.sh
```

Keep `skills/gitwarp/` and `plugins/gitwarp/skills/gitwarp/` synchronized when changing skill behavior. Runtime ledgers live in `.gitwarp/` and must stay ignored.
