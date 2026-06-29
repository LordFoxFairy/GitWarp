# Changelog

## Unreleased

- Renamed Web Console tabs to a branch-first information architecture (Branches, Sandboxes, Repository, Diagnostics) and made Branches the default view when opening a project.
- Reworked the Branches view into branch-first sections (Primary, Base Branches, Task Branches, Unmanaged / Other Branches).
- Added Project Directory cleanup: missing repositories are flagged, can be removed individually, and `Remove missing` prunes every dead registry entry. New `POST /api/forget-project` endpoint backs this, and project summaries now report `exists`.
- Isolated `GITWARP_HOME` per test so the suite no longer pollutes the real `~/.gitwarp/projects.json` registry.

## 0.1.0

- Initial GitWarp skill and CLI package for isolated Git worktree sandboxes.
- Added dossier-backed task records: `task.md`, `progress.md`, and `lessons.md`.
- Added JSON-first commands for init, scan, start, dispatch, adopt, handoff, pause, resume, finish, collapse, reconcile, doctor, board, context, agents, and web state.
- Added prompt-friendly `statusline` and `enter --format prompt` context anchors.
- Added Codex and Claude skill discovery links, local marketplace metadata, installer scripts, and session hook assets.
- Added DDD-oriented Python package layout under `src/gitwarp/` plus regression tests for runtime behavior and packaging.
