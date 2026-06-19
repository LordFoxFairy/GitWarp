# GitWarp Src Layout Restructure Implementation Plan

> Status: Historical record. Superseded by `2026-06-20-gitwarp-ddd-architecture.md` and the repository README. Do not follow old `plugins/gitwarp` mirror instructions.

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move GitWarp from skill-script-hosted product code to a standard `src/gitwarp` Python package with clean skill/plugin wrappers and maintainable split tests.

**Architecture:** Treat `src/gitwarp/` as the product runtime package, `web/` as future React/Vite source, `skills/gitwarp/` as the Agent Skill distribution wrapper, and `plugins/gitwarp/` as the installable plugin mirror. Preserve all current CLI behavior by keeping `skills/gitwarp/scripts/gitwarp.py` as a compatibility wrapper while adding `pyproject.toml` console-script installation. Split tests by responsibility before adding more Web UI work.

**Tech Stack:** Python standard library, Git CLI, PyPA `pyproject.toml` with `src` layout, unittest, Bash smoke scripts, future React/Vite static build output.

---

## Standards Baseline

- Python package source should live under `src/` to avoid accidental imports from the repository root during tests and local execution.
- CLI entrypoint should be declared in `pyproject.toml` as `gitwarp = "gitwarp.cli:main"`.
- Agent Skill directories should contain `SKILL.md`, references, optional assets, and thin scripts; they should not be the canonical product source tree.
- Plugin directories should be generated or mirrored from canonical product and skill sources, with tests preventing stale copied files.
- Standalone copy-only skill installs are not enough once product code moves to `src/`; supported installs are plugin install, source-checkout symlink, editable package install, or an installer that also makes the package available.

## Target Repository Layout

```text
src/gitwarp/
  __init__.py
  agents.py
  cli.py
  diagnostics.py
  dossiers.py
  foundation.py
  ledger.py
  reconcile.py
  reporting.py
  services.py
  web.py
  worktrees.py
  assets/web-console/          # future React build output only

web/                           # future React/Vite source only
  src/
  package.json
  vite.config.ts

skills/gitwarp/
  SKILL.md
  agents/openai.yaml
  references/install.md
  scripts/gitwarp.py           # thin wrapper to src package or bundled plugin package
  scripts/install_cli.py

plugins/gitwarp/
  src/gitwarp/                 # mirrored package for plugin install/runtime
  skills/gitwarp/              # mirrored skill wrapper
  hooks/
  .codex-plugin/
  .claude-plugin/

tests/
  helpers.py
  test_cli_lifecycle.py
  test_ledger.py
  test_worktrees.py
  test_dossiers.py
  test_reconcile.py
  test_doctor.py
  test_web_api.py
  test_packaging.py
```

## File Mapping

- Move `skills/gitwarp/scripts/gitwarp_core/__init__.py` -> `src/gitwarp/__init__.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/agents.py` -> `src/gitwarp/agents.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/cli.py` -> `src/gitwarp/cli.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/diagnostics.py` -> `src/gitwarp/diagnostics.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/dossiers.py` -> `src/gitwarp/dossiers.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/foundation.py` -> `src/gitwarp/foundation.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/ledger.py` -> `src/gitwarp/ledger.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/reconcile.py` -> `src/gitwarp/reconcile.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/reporting.py` -> `src/gitwarp/reporting.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/services.py` -> `src/gitwarp/services.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/web.py` -> `src/gitwarp/web.py`.
- Move `skills/gitwarp/scripts/gitwarp_core/worktrees.py` -> `src/gitwarp/worktrees.py`.
- Replace `skills/gitwarp/scripts/gitwarp_core/` with no canonical code after wrappers and plugin mirror are stable.
- Keep `skills/gitwarp/scripts/gitwarp.py` as a compatibility launcher that puts the repo/plugin package root on `sys.path` and calls `gitwarp.cli.main`.

## Chunk 1: Split Tests Before Moving Source

### Task 1: Extract shared test helpers

**Files:**
- Create: `tests/helpers.py`
- Modify: `tests/test_gitwarp.py`

- [ ] Move common constants and helpers from `tests/test_gitwarp.py` into `tests/helpers.py`:
  - `REPO_ROOT`
  - `SCRIPT`
  - `SCRIPT_DIR`
  - `run_git`
  - `run_gitwarp`
  - `run_gitwarp_text`
  - `findings_with_code`
  - import loaders
  - web request helpers if they remain class-independent
- [ ] Keep behavior unchanged.
- [ ] Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] Commit:

```bash
git add tests/helpers.py tests/test_gitwarp.py
git commit -m "test: extract gitwarp test helpers"
```

### Task 2: Split `tests/test_gitwarp.py` by surface

**Files:**
- Create: `tests/test_cli_lifecycle.py`
- Create: `tests/test_ledger.py`
- Create: `tests/test_worktrees.py`
- Create: `tests/test_dossiers.py`
- Create: `tests/test_reconcile.py`
- Create: `tests/test_doctor.py`
- Create: `tests/test_web_api.py`
- Create: `tests/test_packaging.py`
- Delete or shrink: `tests/test_gitwarp.py`

- [ ] Move lifecycle commands (`scan`, `summon`, `start`, `finish`, `collapse`, `statusline`, `enter`) to `test_cli_lifecycle.py`.
- [ ] Move lock and atomic ledger behavior to `test_ledger.py`.
- [ ] Move dispatch/adopt/board/worktree collision behavior to `test_worktrees.py`.
- [ ] Move dossier creation/handoff/pause/resume snippets to `test_dossiers.py`.
- [ ] Move reconcile/head-drift findings to `test_reconcile.py`.
- [ ] Move doctor/init/install diagnostics to `test_doctor.py`.
- [ ] Move all HTTP/Web API tests to `test_web_api.py`.
- [ ] Move plugin/marketplace/mirror tests to `test_packaging.py`.
- [ ] Keep class setup helpers DRY through `tests/helpers.py`; do not duplicate temp repo bootstrapping.
- [ ] Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] Commit:

```bash
git add tests
git commit -m "test: split gitwarp regression suite"
```

## Chunk 2: Packaging Skeleton Without Behavior Change

### Task 3: Add package structure tests

**Files:**
- Modify: `tests/test_packaging.py`

- [ ] Add a packaging test that asserts `pyproject.toml` exists and contains project name `gitwarp` plus `[project.scripts] gitwarp = "gitwarp.cli:main"`.
- [ ] Add a packaging test that imports `gitwarp.cli` from `src/` by inserting `REPO_ROOT / "src"` into `sys.path`.
- [ ] Add a wrapper test that runs `python3 skills/gitwarp/scripts/gitwarp.py --version` and still receives `gitwarp 0.1.0`.
- [ ] Add a test that `src/gitwarp/__init__.py` defines `__version__` and `gitwarp.cli` uses it for `--version`.
- [ ] Run:

```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
```

- [ ] Expected: fail because `pyproject.toml` and `src/gitwarp` do not exist.

### Task 4: Create `pyproject.toml` and copy package

**Files:**
- Create: `pyproject.toml`
- Create: `src/gitwarp/*.py`
- Modify: `skills/gitwarp/scripts/gitwarp.py`
- Modify: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py`

- [ ] Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gitwarp"
dynamic = ["version"]
description = "Agent worktree isolation manager for concurrent coding agents"
requires-python = ">=3.10"
readme = "README.md"
license = "MIT"
dependencies = []

[project.scripts]
gitwarp = "gitwarp.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.dynamic]
version = {attr = "gitwarp.__version__"}

[tool.setuptools.package-data]
gitwarp = ["assets/*", "assets/**/*"]
```

- [ ] Copy the current modules from `skills/gitwarp/scripts/gitwarp_core/*.py` to `src/gitwarp/*.py`.
- [ ] Keep module internals unchanged except package name import assumptions, because relative imports already work after the move.
- [ ] Set `src/gitwarp/__init__.py` to include `__version__ = "0.1.0"`.
- [ ] Update `src/gitwarp/cli.py` to read `__version__` for `--version` instead of hard-coding `gitwarp 0.1.0`.
- [ ] Replace `skills/gitwarp/scripts/gitwarp.py` with a wrapper:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def _candidate_package_roots() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        here.parents[3] / "src",                 # source checkout: skills/gitwarp/scripts/gitwarp.py
        here.parents[3] / "plugins" / "gitwarp" / "src",
        here.parents[2] / "src",                 # plugin package: skills/gitwarp/scripts/gitwarp.py
    ]


for root in _candidate_package_roots():
    if (root / "gitwarp" / "cli.py").exists():
        sys.path.insert(0, str(root))
        break

from gitwarp.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] Run targeted packaging tests and `--version`.
- [ ] Do not delete `skills/gitwarp/scripts/gitwarp_core` in this task; keep fallback during migration.
- [ ] Commit:

```bash
git add pyproject.toml src/gitwarp skills/gitwarp/scripts/gitwarp.py plugins/gitwarp/skills/gitwarp/scripts/gitwarp.py tests/test_packaging.py
git commit -m "refactor: add src package for gitwarp"
```

## Chunk 3: Plugin Mirror And Installer Compatibility

### Task 5: Mirror package into plugin

**Files:**
- Create: `plugins/gitwarp/src/gitwarp/*.py`
- Modify: `tests/test_packaging.py`
- Modify: `scripts/install-codex-plugin.sh`
- Modify: `skills/gitwarp/scripts/install_cli.py`
- Modify: `plugins/gitwarp/skills/gitwarp/scripts/install_cli.py`

- [ ] Add mirror tests that recursively compare:
  - `src/gitwarp/**` with `plugins/gitwarp/src/gitwarp/**`.
  - `skills/gitwarp/SKILL.md`, `agents/`, `references/`, and wrapper scripts with `plugins/gitwarp/skills/gitwarp/**`.
  - Hook files with `plugins/gitwarp/hooks/**`.
- [ ] Add negative mirror tests:
  - no `__pycache__` under `plugins/gitwarp`.
  - no extra stale files under mirrored directories.
  - no product package code under `skills/gitwarp/scripts` except wrappers during final cleanup.
- [ ] Update `install_cli.py` so the generated launcher still executes the installed skill wrapper script, not a hard-coded source checkout path.
- [ ] Ensure installed plugin path `~/.codex/plugins/cache/.../skills/gitwarp/scripts/gitwarp.py` can locate `plugins/gitwarp/src`.
- [ ] Add an installed-plugin simulation test: copy `plugins/gitwarp` to a temp cache path and run `python3 <temp>/skills/gitwarp/scripts/gitwarp.py --version`.
- [ ] Run:

```bash
python3 -m unittest discover -s tests -p 'test_packaging.py' -v
python3 -m py_compile src/gitwarp/*.py plugins/gitwarp/src/gitwarp/*.py skills/gitwarp/scripts/*.py plugins/gitwarp/skills/gitwarp/scripts/*.py
```

- [ ] Commit:

```bash
git add src/gitwarp plugins/gitwarp/src tests/test_packaging.py scripts/install-codex-plugin.sh skills/gitwarp/scripts plugins/gitwarp/skills/gitwarp/scripts
git commit -m "refactor: mirror gitwarp package into plugin"
```

## Chunk 4: Remove Old Canonical Core From Skill Wrapper

### Task 6: Delete duplicated canonical code from `skills/`

**Files:**
- Delete: `skills/gitwarp/scripts/gitwarp_core/*.py`
- Delete: `plugins/gitwarp/skills/gitwarp/scripts/gitwarp_core/*.py`
- Modify: `tests/test_packaging.py`
- Modify: `README.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`
- Sync: `plugins/gitwarp/skills/gitwarp/**`

- [ ] Update tests to assert `skills/gitwarp/scripts/gitwarp_core` no longer exists.
- [ ] Update tests to assert no React source is committed inside `skills/gitwarp`.
- [ ] Update docs to say product code lives in `src/gitwarp`; skill scripts are wrappers.
- [ ] Update docs to say copy-only skill installs must also install/package `src/gitwarp`, while repo-local symlink installs are supported.
- [ ] Update plugin mirror test to compare `plugins/gitwarp/src/gitwarp` against `src/gitwarp`.
- [ ] Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile src/gitwarp/*.py plugins/gitwarp/src/gitwarp/*.py skills/gitwarp/scripts/*.py plugins/gitwarp/skills/gitwarp/scripts/*.py
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
```

- [ ] Commit:

```bash
git add README.md skills/gitwarp plugins/gitwarp tests src/gitwarp
git commit -m "refactor: make skills wrappers for gitwarp package"
```

## Chunk 5: Future Web UI Placement Only

### Task 7: Add placeholder structure for future React without implementation

**Files:**
- Create: `web/README.md`
- Create: `src/gitwarp/assets/.gitkeep`
- Modify: `README.md`
- Modify: `tests/test_packaging.py`

- [ ] Document that future React/Vite source belongs under `web/`.
- [ ] Document that build output belongs under `src/gitwarp/assets/web-console/` and is package data.
- [ ] Do not create `package.json` or install frontend dependencies in this restructure slice.
- [ ] Add tests that no React source is committed inside `skills/gitwarp/`.
- [ ] Commit:

```bash
git add web/README.md src/gitwarp/assets/.gitkeep README.md tests/test_packaging.py
git commit -m "docs: reserve web source and asset boundaries"
```

## Final Verification

- [ ] Run:

```bash
bash -n scripts/verify-install.sh hooks/session-start hooks/session-start-codex scripts/install-codex-plugin.sh
python3 -m py_compile src/gitwarp/*.py plugins/gitwarp/src/gitwarp/*.py skills/gitwarp/scripts/*.py plugins/gitwarp/skills/gitwarp/scripts/*.py
python3 /Users/nako/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gitwarp
python3 /Users/nako/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/gitwarp
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/verify-install.sh
git diff --check
```

- [ ] If `scripts/verify-install.sh` fails due external Codex/plugin install state, capture exact stdout/stderr and do not claim smoke success.
- [ ] Write `gitwarp handoff` with final commit hashes and verification evidence.
