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

For authoring, keep the canonical skill in `skills/gitwarp/` and mirror it into `plugins/gitwarp/skills/gitwarp/` before installing the plugin. The local Codex marketplace is defined at `.agents/plugins/api_marketplace.json` with marketplace name `gitwarp-dev`.

Install from the repository root:

```bash
scripts/install-codex-plugin.sh
```

Manual equivalent:

```bash
codex plugin marketplace add /absolute/path/to/GitWarp --json
codex plugin add gitwarp@gitwarp-dev --json
python3 "$HOME/.codex/plugins/cache/gitwarp-dev/gitwarp/0.1.0/skills/gitwarp/scripts/install_cli.py"
```

For direct skill-only experiments, copy or symlink `skills/gitwarp` into the tool-specific discovery directory:

- Codex: `$HOME/.codex/skills/gitwarp` or `$HOME/.agents/skills/gitwarp`
- Claude Code: `$HOME/.claude/skills/gitwarp`

## CLI command

After installing the plugin or skill, expose the bundled helper as `gitwarp`:

```bash
python3 /absolute/path/to/skills/gitwarp/scripts/install_cli.py
```

By default this writes a launcher to `~/.local/bin/gitwarp`. Override with `--dest /absolute/path/gitwarp` when needed.

Verify:

```bash
gitwarp scan --cwd /absolute/path/to/git/repo
```

The implementation is Python by design: it uses only the standard library plus the system `git` command, which keeps the skill portable while making JSON and path handling safer than shell-only parsing. Day to day, users should call `gitwarp`, not the Python file.
