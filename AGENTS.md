# Repository Guidelines

## Project Structure & Module Organization
`src/gitwarp/` is the only runtime package. Root modules are compatibility shims; implementation belongs under `domain/`, `application/use_cases/`, `application/health/`, `infrastructure/`, `adapters/cli/`, and `webapp/`. `skills/gitwarp/` is the canonical skill source with `SKILL.md`, UI metadata in `agents/openai.yaml`, install notes in `references/`, and executable helpers in `scripts/`. `.agents/skills/gitwarp` and `.claude/skills/gitwarp` are repo-local standard skill discovery links back to the canonical folder. `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json` provide the plugin shells, `.agents/plugins/api_marketplace.json` is the Codex marketplace entry, and `hooks/` installs the `gitwarp` CLI plus session context. `tests/` contains Python regression tests for the Git worktree helper.

## Build, Test, and Development Commands
- `python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp`: validate the canonical skill shape.
- `python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .`: validate the repository-root Codex plugin package.
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`: run GitWarp worktree behavior tests.
- `scripts/install-codex-plugin.sh`: register the local marketplace, install the plugin, and expose the `gitwarp` launcher.
- `scripts/verify-install.sh`: verify the installed plugin and run a real agents/dispatch/adopt/reconcile/doctor/enter/start/context/handoff/board/statusline/finish smoke test.
- `python3 skills/gitwarp/scripts/install_cli.py`: install only the `gitwarp` launcher to `~/.local/bin`.
- `gitwarp scan --cwd "$PWD"`: verify the installed CLI can inspect the current repository.
- `codex plugin marketplace add "$PWD" --json`: register this checkout as a local Codex marketplace.
- `codex plugin add gitwarp@gitwarp-dev --json`: install GitWarp through the Codex plugin path.

## Coding Style & Naming Conventions
Use Python standard library code for deterministic Git and JSON operations; avoid adding runtime dependencies unless the benefit is clear. Keep skill instructions concise and put fragile or repeatable operations in `scripts/`. Use lowercase hyphenated skill names, snake_case Python identifiers, and explicit JSON output for automation-facing commands.

## Testing Guidelines
Behavior changes must include or update focused tests under `tests/`. Tests should create temporary Git repositories and exercise public CLI behavior such as `enter`, `scan`, `agents`, `dispatch`, `start`, `summon`, `adopt`, `context`, `annotate`, `handoff`, `board`, `reconcile`, `doctor`, `finish`, `statusline`, and `collapse`. Keep hook files and repository-root plugin metadata covered by structure tests. Always run both skill validation and unittest discovery before claiming the skill is ready.

## Commit & Pull Request Guidelines
Use short, imperative Conventional Commit messages, for example `feat: add gitwarp skill` or `fix: reject branch collisions`. Pull requests should describe the skill behavior, mention installation impact, include verification commands, and show representative CLI JSON when command output changes.

## Configuration Notes
Runtime ledgers live under `.gitwarp/` inside target repositories and must stay ignored. Do not commit editor state, `__pycache__/`, `.pytest_cache/`, or temporary worktree contents. Keep the plugin manifest, hooks, and canonical skill source synchronized when changing install behavior.
Keep `.agents/skills/gitwarp` and `.claude/skills/gitwarp` as symlinks to `../../skills/gitwarp`; do not replace them with copied skill folders.
Keep `plugins/gitwarp` as a symlink to `..` for Codex marketplace compatibility. Do not replace it with a directory and do not recreate `plugins/gitwarp/src`; `src/gitwarp/` is the single source of truth.
