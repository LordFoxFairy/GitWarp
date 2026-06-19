# GitWarp Install Notes

## Official init and discovery surfaces

### Codex

- Author new skills with the built-in creator: `$skill-creator`
- Repo-local discovery path: `$REPO_ROOT/.agents/skills/<skill-name>/SKILL.md`
- User-local discovery path: `$HOME/.agents/skills/<skill-name>/SKILL.md`
- Curated installer for local use: `$skill-installer`

### Claude Code

- Skills live under `~/.claude/skills/<skill-name>/SKILL.md` or `.claude/skills/<skill-name>/SKILL.md`
- Official plugin scaffold CLI: `claude plugin init <name>`
- Plain skills do not require a plugin, but plugins are the formal distribution wrapper when you want install surfaces, hooks, MCP servers, or namespacing.

## Recommended repo strategy

For authoring, keep the canonical runtime in `src/gitwarp/` and the canonical skill in `skills/gitwarp/`. The repository root is the plugin package; do not maintain a second runtime mirror. `plugins/gitwarp` is only a symlink back to the repository root so Codex marketplace discovery can keep using the standard `./plugins/<name>` source path. Repo-local standard discovery paths are symlinks:

- `.agents/skills/gitwarp -> ../../skills/gitwarp`
- `.claude/skills/gitwarp -> ../../skills/gitwarp`

The local Codex marketplace is defined at `.agents/plugins/api_marketplace.json` with marketplace name `gitwarp-dev`.

Install from the repository root:

```bash
scripts/install-codex-plugin.sh
gitwarp init --cwd "$PWD"
gitwarp doctor --cwd "$PWD"
```

Manual equivalent:

```bash
codex plugin marketplace add /absolute/path/to/GitWarp --json
codex plugin add gitwarp@gitwarp-dev --json
python3 "$HOME/.codex/plugins/cache/gitwarp-dev/gitwarp/0.1.0/skills/gitwarp/scripts/install_cli.py"
```

For direct skill-only experiments from a source checkout, symlink `skills/gitwarp` into the tool-specific discovery directory:

- Codex: `$HOME/.agents/skills/gitwarp`
- Claude Code: `$HOME/.claude/skills/gitwarp`

Example:

```bash
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
ln -s /absolute/path/to/GitWarp/skills/gitwarp "$HOME/.agents/skills/gitwarp"
ln -s /absolute/path/to/GitWarp/skills/gitwarp "$HOME/.claude/skills/gitwarp"
```

Do not copy only `skills/gitwarp/` unless the `gitwarp` Python package is already installed. The wrapper in `skills/gitwarp/scripts/gitwarp.py` loads product code from the adjacent repository-root `src/gitwarp/` package.

## CLI command

After installing the plugin or skill, expose the bundled helper as `gitwarp`:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/install_cli.py
```

By default this writes a launcher to `~/.local/bin/gitwarp`. Override with `--dest /absolute/path/gitwarp` when needed.

Verify:

```bash
gitwarp init --cwd /absolute/path/to/git/repo
gitwarp doctor --cwd /absolute/path/to/git/repo
gitwarp enter --cwd /absolute/path/to/git/repo
gitwarp scan --cwd /absolute/path/to/git/repo
gitwarp agents --cwd /absolute/path/to/git/repo
gitwarp context --cwd /absolute/path/to/git/repo
gitwarp board --cwd /absolute/path/to/git/repo --format table
```

## Repository initialization

`gitwarp init --cwd /absolute/path/to/git/repo` creates `.gitwarp/`, `.gitwarp/worktrees/`, `.gitwarp/dossiers/`, and `.gitwarp/ledger.json`. The command is idempotent and validates existing state before writing.

Default local mode writes `/.gitwarp/` to `.git/info/exclude`, so runtime files stay ignored without touching tracked files. Team mode writes the same rule to `.gitignore`:

```bash
gitwarp init --cwd /absolute/path/to/git/repo --write-gitignore
```

Use team mode only when the project wants the ignore rule committed. If `.gitignore` already has the rule, `init` will not duplicate it.

Plugin session hooks install the CLI and attempt `gitwarp enter --cwd "$PWD" --format prompt` at session start. That injects the current main/worktree context for agents, but it does not initialize runtime state or allocate a worktree automatically. Start isolated work explicitly with `gitwarp dispatch` or `gitwarp start`.

For orchestrated agent launches, use `gitwarp dispatch`. It allocates a project-local worktree under `<repo>/.gitwarp/worktrees/<worktree-name>`, creates the dossier files, records ownership, and prints a launch command without executing it. Optional local launch templates live in ignored runtime config at `.gitwarp/agents.json`; built-in templates are available for `codex` and `claude`.

The implementation is Python by design: it uses only the standard library plus the system `git` command, which keeps the skill portable while making JSON and path handling safer than shell-only parsing. Product modules live in `src/gitwarp/`; skill scripts are wrappers and installers only. Day to day, users should call `gitwarp`, not the Python file.
