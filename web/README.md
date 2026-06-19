# GitWarp Web Console

This directory is reserved for the future rich web console source. Keep framework source, package manager files, tests, and design assets here instead of under `skills/`.

The current console is a lightweight inline HTML implementation in `src/gitwarp/web.py`. When a React or similar frontend replaces it, keep editable source here, compile production assets into `src/gitwarp/assets/web-console/`, and mirror that built output into `plugins/gitwarp/src/gitwarp/assets/web-console/` for plugin distribution.

Current backend web endpoints live in `src/gitwarp/web.py` and are covered by `tests/test_web_api.py`.
