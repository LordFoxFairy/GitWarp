# GitWarp Web Console

This directory is reserved for the future rich web console source. Keep framework source, package manager files, tests, and design assets here instead of under `skills/`.

The Python package serves only built assets. When a React or similar frontend is added, compile it into `src/gitwarp/assets/web-console/` and mirror that built output into `plugins/gitwarp/src/gitwarp/assets/web-console/` for plugin distribution.

Current backend web endpoints live in `src/gitwarp/web.py` and are covered by `tests/test_web_api.py`.
