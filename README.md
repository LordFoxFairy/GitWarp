# GitWarp

GitWarp is a Codex/Claude skill-plugin for coordinating concurrent coding agents with isolated `git worktree` sandboxes. It follows the Agent Skills pattern: the reusable behavior lives in `skills/gitwarp/SKILL.md`, deterministic operations live in `scripts/`, and plugin shells expose the skill to supported agents.

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
gitwarp scan --cwd /absolute/path/to/repo
gitwarp summon --cwd /absolute/path/to/repo \
  --agent-id codex-alpha \
  --branch feature/my-task \
  --purpose "Implement isolated task"
gitwarp statusline --cwd "$PWD"
gitwarp collapse --cwd /absolute/path/to/repo --branch feature/my-task
```

`scan`, `summon`, and `collapse` emit strict one-line JSON. `statusline` emits a raw banner such as `GITWARP[main-repo]` or `GITWARP[codex-alpha@feature/my-task]`.

## Development Checks

```bash
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/verify-install.sh
```

Keep `skills/gitwarp/` and `plugins/gitwarp/skills/gitwarp/` synchronized when changing skill behavior. Runtime ledgers live in `.gitwarp/` and must stay ignored.
