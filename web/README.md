# GitWarp Web Console

`web/console/` contains the React + TypeScript management UI for `gitwarp web`.

Runtime assets are checked in under `web/console/dist/` so the Python CLI can serve the UI without requiring Node.js at startup. Editable source lives under `web/console/src/` and is built with Vite.

Common commands:

- `cd web/console && npm install`: install local UI tooling.
- `cd web/console && npm run dev`: run the React UI in Vite for frontend iteration.
- `cd web/console && npm run build`: type-check, bundle React, and regenerate `dist/index.html`, `dist/app.css`, and `dist/app.js`.

Current backend web endpoints live in `src/gitwarp/webapp/` and are covered by `tests/test_web_api.py`.
