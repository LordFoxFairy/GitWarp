# GitWarp Web Console

`web/console/` contains the React + TypeScript management UI for `gitwarp web`. The UI intentionally follows a GitHub/GitLab-style repository management model: first choose or add a project, then use a repository page with a Code-style worktree list, agent actions, and health checks. For people, this should be the default entrypoint; the CLI remains the precise control surface for scripted or advanced flows. Branch supervision must preserve `Unmanaged / Other Branches` so unknown refs do not disappear from the operator view.

Runtime assets are checked in under both `web/console/dist/` and `src/gitwarp/assets/web_console/`. The packaged copy lets the Python CLI serve the UI without requiring Node.js at startup. Editable source lives under `web/console/src/` and is built with Vite.

The console uses `@primer/react` and `@primer/octicons-react` for mature GitHub-like controls while keeping GitWarp-specific layout in `src/styles.css`. Prefer Primer components for buttons, labels, form controls, navigation, and alerts; keep custom CSS focused on page grids, dossier readouts, and worktree density.

Common commands:

- `cd web/console && npm install`: install local UI tooling.
- `cd web/console && npm run dev`: run the React UI in Vite for frontend iteration.
- `cd web/console && npm run build`: type-check, bundle React, and regenerate `dist/index.html`, `dist/app.css`, and `dist/app.js`.
- `cd web/console && npm run check:dist`: type-check and build React in a temporary directory, then fail if generated assets differ from the checked-in runtime copies.

Current backend web endpoints live in `src/gitwarp/webapp/` and are covered by `tests/test_web_api.py`.
