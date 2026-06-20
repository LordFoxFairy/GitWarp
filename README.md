# GitWarp

GitWarp is an Agent Skill plus installable CLI package for running Codex, Claude Code, and other coding agents in isolated Git worktrees. It gives each task a physical sandbox, a branch ownership record, and a small dossier (`task.md`, `progress.md`, `lessons.md`) so agents can resume work without guessing what happened before.

The project follows the common Agent Skills layout while keeping product code in a normal Python package. `src/gitwarp/` is the single canonical runtime, `skills/gitwarp/` contains agent instructions plus bootstrap helpers, and the repository root is the plugin package. `plugins/gitwarp` is only a marketplace discovery symlink back to the repository root; it must not contain copied runtime files.

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
gitwarp init
gitwarp doctor
```

This registers or rebinds the local marketplace `gitwarp-dev`, installs `gitwarp@gitwarp-dev`, and writes the `gitwarp` launcher to `~/.local/bin/gitwarp`.
If the installer reports `on_path:false`, add `~/.local/bin` to `PATH` or run the returned absolute launcher path.

Manual equivalent:

```bash
codex plugin marketplace add "$PWD" --json
plugin_json="$(codex plugin add gitwarp@gitwarp-dev --json)"
installed_path="$(PLUGIN_JSON="$plugin_json" python3 -c 'import json, os; print(json.loads(os.environ["PLUGIN_JSON"])["installedPath"])')"
python3 "$installed_path/skills/gitwarp/scripts/install_cli.py"
```

### Standard Skill Path

GitWarp also exposes repo-local standard skill locations:

- Codex: `.agents/skills/gitwarp -> ../../skills/gitwarp`
- Claude Code: `.claude/skills/gitwarp -> ../../skills/gitwarp`

For source checkout installs, symlink the canonical skill folder and install the launcher from the adjacent `src/gitwarp` package:

```bash
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
ln -s "$PWD/skills/gitwarp" "$HOME/.agents/skills/gitwarp"
ln -s "$PWD/skills/gitwarp" "$HOME/.claude/skills/gitwarp"
python3 "$PWD/skills/gitwarp/scripts/install_cli.py"
```

For copy-only installs, copy the repository root or install the Python package first. Copying only `skills/gitwarp/` is not enough because the core implementation lives in `src/gitwarp/`.

## Quick Start

Initialize each target repository once, then run a read-only diagnostic:

```bash
gitwarp init
gitwarp doctor
```

Check repository context when a session starts:

```bash
gitwarp statusline
gitwarp enter
```

`statusline` is the low-noise automatic anchor for prompts and hooks. Run `enter` manually only when an agent needs the full dossier pointers and snippets.

Create a sandbox:

```bash
gitwarp create --branch feature/my-task \
  --purpose "Implement isolated task"
```

Move into an existing sandbox:

```bash
gitwarp switch --branch feature/my-task
eval "$(gitwarp switch --branch feature/my-task --format shell)"
```

If the worker needs local instruction files such as `AGENTS.md` or `CLAUDE.md`, mount them explicitly:

```bash
gitwarp create --branch feature/my-task \
  --purpose "Implement isolated task" \
  --instruction AGENTS.md \
  --instruction CLAUDE.md=docs/claude-code.md
```

Use `.gitwarp/instruction_profiles.json` for repeatable stacks:

```json
{
  "version": 1,
  "profiles": {
    "claude-code": {
      "description": "Claude Code local rules",
      "instructions": [
        "AGENTS.md",
        {"target": "CLAUDE.md", "source": "docs/claude-code.md"}
      ]
    }
  }
}
```

Then pass `--instruction-profile claude-code`. Instructions are copied by default as a safe snapshot; pass `--instruction-mode symlink` only when the worker should track live rule edits.

Begin inside the returned absolute `path`, read `task.md`, `progress.md`, and `lessons.md`, then record milestones:

```bash
gitwarp handoff --status testing \
  --progress "Implemented regression test and minimal fix" \
  --lesson "Read dossier before editing nested paths"
```

If work is blocked waiting for a human or external dependency:

```bash
gitwarp pause --reason "Waiting for credentials" \
  --lesson "Do not retry deployment without credentials"

gitwarp resume --progress "Credentials configured; continuing"
```

When the task is verified, record the outcome and leave the sandbox for human review:

```bash
gitwarp finish --status pushed \
  --progress "Verified and pushed"
```

Only collapse when the user explicitly wants the sandbox destroyed:

```bash
gitwarp finish --status pushed \
  --progress "Verified and pushed" \
  --collapse
```

`remove` and `collapse` delete the worktree, its ledger row, and the matching `.gitwarp/dossiers/...` directory. They never merge, push, or delete the Git branch. Use `gitwarp remove` inside a sandbox only when it should be destroyed without a final handoff. From the main checkout, target one explicitly with `gitwarp remove --branch feature/my-task`. `remove` refuses dirty or untracked targets unless `--force` is provided.

## Usage Modes

### Human Operator

Use these commands when you are coordinating agents from the main checkout:

```bash
gitwarp board --format table
gitwarp reconcile --stale 4
gitwarp doctor
gitwarp web
```

`board` shows active sandboxes. `reconcile` audits stale ledger rows, dirty worktrees, missing dossiers, merged branches, and `head_drift` without mutating state. `head_drift` means the live worktree HEAD differs from the last GitWarp-recorded handoff point. `doctor` checks Git, Python, the launcher, plugin metadata, installed Codex plugin cache drift, hooks, ignored runtime files, and agent binaries. `web` starts the local React management console. Its first screen is a GitHub/GitLab-like Project Directory. Open a repository, choose a worktree from the dropdown, then use Code for tracked files at that worktree `HEAD`, Metadata for task/progress/lessons plus agent actions, and Health for doctor/reconcile findings.

### Automated Agent

Agents should use this minimal loop:

```bash
gitwarp statusline
gitwarp enter
# read returned task_md, progress_md, lessons_md
gitwarp handoff --status implementing --progress "Short milestone"
```

`statusline` prints an unquoted banner such as `GITWARP[main-repo]` or `GITWARP[codex-alpha@feature/my-task]` for shell prompts and downstream model context.
Session hooks should not print full `enter` output by default; they should inject the banner and remind the agent that `enter` is available when full context is needed.
If the user explicitly assigns an existing worktree, complete the work in that worktree and stop there after verification. Do not push, merge, remove, or collapse unless the user asked for that action.

### Existing Worktree

If a non-main worktree already exists, bind it into GitWarp instead of recreating it:

```bash
gitwarp adopt --cwd /absolute/path/to/repo \
  --path /absolute/path/to/existing-worktree \
  --agent-id claude-existing \
  --purpose "Continue existing sandbox"
```

## Runtime Model

GitWarp stores runtime state under `.gitwarp/` in the target repository. Run `gitwarp init` to create this state safely before dispatching agents.

- Worktrees: `.gitwarp/worktrees/<worktree-name>`
- Ledger: `.gitwarp/ledger.json`
- Agent launch config: `.gitwarp/agents.json`
- Instruction mount profiles: `.gitwarp/instruction_profiles.json`
- Dossiers: `.gitwarp/dossiers/<branch-slug>-<id>/`

By default, `init` writes `/.gitwarp/` to `.git/info/exclude`, which keeps runtime files local to one checkout. Use `gitwarp init --write-gitignore` when the team wants the ignore rule committed to `.gitignore`.

Dossiers are lifecycle files for active sandboxes, not long-term archives. `handoff` keeps them current while a worktree exists. `remove`, `collapse`, and `finish --collapse` delete the matching dossier directory together with the worktree and ledger row while leaving the branch untouched.

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

- `src/gitwarp/`: the only canonical runtime package root. It contains package metadata only; implementation lives in the DDD subpackages below.
- `src/gitwarp/domain/`: value objects and pure policies for worktree snapshots, workspace records, branch collisions, guarded paths, and head drift.
- `src/gitwarp/application/use_cases/`: orchestration for init, create/switch/remove, dispatch/start/handoff/finish/collapse, read-only web state, and repository file browsing.
- `src/gitwarp/application/health/`: doctor/init health checks, findings, process probes, and recommendations.
- `src/gitwarp/infrastructure/`: Git subprocess, ledger persistence, dossier files, agent registry, and repository discovery adapters.
- `src/gitwarp/adapters/cli/`: argparse parser, entrypoint, read commands, system commands, and workspace commands.
- `src/gitwarp/webapp/`: Web Console contracts, security, static resources, controllers, HTTP transport, and server lifecycle.
- `src/gitwarp/assets/web_console/`: packaged static assets served by `gitwarp web` without requiring Node.js at runtime.
- `skills/gitwarp/`: canonical Agent Skill instructions, launcher installer, and references.
- `.agents/skills/gitwarp` and `.claude/skills/gitwarp`: repo-local standard skill discovery links.
- `.codex-plugin/` and `.claude-plugin/`: plugin metadata shells.
- `.agents/plugins/api_marketplace.json`: local Codex marketplace entry named `gitwarp-dev`.
- `plugins/gitwarp -> ..`: Codex marketplace discovery symlink. Keep it as a symlink; do not add `plugins/gitwarp/src`.
- `hooks/`: session hook assets for compatible hosts. They are packaged as assets; enable them through the host-specific hook mechanism.
- `web/console/`: React + TypeScript Web Console source, Primer React UI components, Vite config, and checked-in runtime `dist/` assets.
- `tests/`: Python regression tests for GitWarp behavior and packaging.
- `CHANGELOG.md` and `LICENSE`: release history and MIT license text.

## Development

```bash
scripts/check-release.sh
scripts/verify-install.sh
```

`scripts/check-release.sh` is the tracked release gate used by CI. It runs whitespace checks, Python compilation, optional installed skill/plugin validators, the Web Console dist drift check, and the Python regression suite. `npm run check:dist` builds React into a temporary directory and fails if the generated runtime assets differ from both `web/console/dist/` and `src/gitwarp/assets/web_console/`; use `npm run build` to intentionally regenerate them.

Keep runtime behavior in DDD subpackages under `src/gitwarp/`. Do not recreate `plugins/gitwarp/src`; `plugins/gitwarp` is a symlink for marketplace discovery, not a second source tree. Keep plugin metadata at the repository root and standard discovery links pointing at the canonical skill folder.
