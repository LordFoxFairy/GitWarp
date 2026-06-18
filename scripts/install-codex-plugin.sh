#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PLUGIN_ID="gitwarp@gitwarp-dev"

command -v codex >/dev/null 2>&1 || {
  echo "codex CLI is required" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required" >&2
  exit 1
}

marketplace_output="$(codex plugin marketplace add "$REPO_ROOT" --json 2>&1)"
plugin_output="$(codex plugin add "$PLUGIN_ID" --json 2>&1)"

installed_path="$(
  PLUGIN_OUTPUT="$plugin_output" python3 - <<'PY'
import json
import os
import sys

raw = os.environ["PLUGIN_OUTPUT"]
start = raw.find("{")
if start < 0:
    print(raw, file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[start:])
print(payload["installedPath"])
PY
)"

cli_output="$(python3 "$installed_path/skills/gitwarp/scripts/install_cli.py")"

MARKETPLACE_OUTPUT="$marketplace_output" \
PLUGIN_OUTPUT="$plugin_output" \
CLI_OUTPUT="$cli_output" \
python3 - <<'PY'
import json
import os


def parse(raw: str) -> dict:
    start = raw.find("{")
    if start < 0:
        return {"raw": raw}
    return json.loads(raw[start:])


print(
    json.dumps(
        {
            "ok": True,
            "marketplace": parse(os.environ["MARKETPLACE_OUTPUT"]),
            "plugin": parse(os.environ["PLUGIN_OUTPUT"]),
            "cli": parse(os.environ["CLI_OUTPUT"]),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
