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

For authoring, keep the canonical skill in source control and copy or symlink it into the tool-specific discovery directory that you actually use:

- Codex: `.agents/skills/gitwarp` or `~/.agents/skills/gitwarp`
- Claude Code: `.claude/skills/gitwarp` or `~/.claude/skills/gitwarp`

If the skill later needs packaging for broader installation, wrap it in a plugin rather than changing the skill internals.

## CLI command

After installing the skill, expose the bundled helper as `gitwarp`:

```bash
python3 ~/.codex/skills/gitwarp/scripts/install_cli.py
```

By default this writes a launcher to `~/.local/bin/gitwarp`. Override with `--dest /absolute/path/gitwarp` when needed.

Verify:

```bash
gitwarp scan --cwd /absolute/path/to/git/repo
```

The implementation is Python by design: it uses only the standard library plus the system `git` command, which keeps the skill portable while making JSON and path handling safer than shell-only parsing. Day to day, users should call `gitwarp`, not the Python file.
