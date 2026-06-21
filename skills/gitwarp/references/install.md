# GitWarp Install Notes

## Supported Shapes

GitWarp is distributed as a repository-root plugin package plus a standard Agent Skill:

- Runtime package: `src/gitwarp/`
- Canonical skill: `skills/gitwarp/`
- Codex marketplace entry: `.agents/plugins/api_marketplace.json`
- Repo-local skill links: `.agents/skills/gitwarp` and `.claude/skills/gitwarp`
- Launcher installer: `skills/gitwarp/scripts/install_cli.py`

Do not copy only `skills/gitwarp/` unless the `gitwarp` Python package is already installed or available beside it in the full repository/plugin checkout. Skill scripts are bootstrap helpers, not the product runtime.

## Claude Code Plugin Install

From the GitWarp repository root:

```bash
scripts/install-claude-plugin.sh
gitwarp init
gitwarp doctor
```

The installer registers or rebinds the Claude Code marketplace `gitwarp-dev`, installs `gitwarp@gitwarp-dev` with `claude plugin install gitwarp@gitwarp-dev --scope user`, and writes a `gitwarp` launcher to `~/.local/bin/gitwarp`.

Manual equivalent:

```bash
claude plugin marketplace add /absolute/path/to/GitWarp --scope user
claude plugin install gitwarp@gitwarp-dev --scope user
python3 /absolute/path/to/GitWarp/skills/gitwarp/scripts/install_cli.py
```

If installer output contains `"on_path":false`, add `~/.local/bin` to `PATH` or call the returned absolute `command`.

## Codex Plugin Install

From the GitWarp repository root:

```bash
scripts/install-codex-plugin.sh
gitwarp init
gitwarp doctor
```

The installer registers or rebinds the local marketplace `gitwarp-dev`, installs `gitwarp@gitwarp-dev`, and writes a `gitwarp` launcher to `~/.local/bin/gitwarp`.

Manual equivalent:

```bash
codex plugin marketplace add /absolute/path/to/GitWarp --json
plugin_json="$(codex plugin add gitwarp@gitwarp-dev --json)"
installed_path="$(PLUGIN_JSON="$plugin_json" python3 -c 'import json, os; print(json.loads(os.environ["PLUGIN_JSON"])["installedPath"])')"
python3 "$installed_path/skills/gitwarp/scripts/install_cli.py"
```

If installer output contains `"on_path":false`, add `~/.local/bin` to `PATH` or call the returned absolute `command`.

## Standard Skill Discovery

For source-checkout experiments, symlink the canonical skill into the host discovery directory:

```bash
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
ln -s /absolute/path/to/GitWarp/skills/gitwarp "$HOME/.agents/skills/gitwarp"
ln -s /absolute/path/to/GitWarp/skills/gitwarp "$HOME/.claude/skills/gitwarp"
python3 /absolute/path/to/GitWarp/skills/gitwarp/scripts/install_cli.py
```

The generated launcher runs `python -m gitwarp.adapters.cli.entrypoint` with the adjacent `src/` directory on `PYTHONPATH`.

## Verification

```bash
gitwarp --version
gitwarp init
gitwarp doctor
gitwarp task create --title "Verify install" --branch feature/check
gitwarp switch --branch feature/check
gitwarp remove --branch feature/check
```

`scripts/verify-install.sh` performs a full plugin and CLI smoke test. Set `GITWARP_BIN=/absolute/path/gitwarp` when the launcher is not on `PATH`.

Use `--cwd /absolute/path/to/git/repo` only when verifying a repository from outside that repository.
