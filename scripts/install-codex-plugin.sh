#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MARKETPLACE_NAME="gitwarp-dev"
PLUGIN_ID="gitwarp@${MARKETPLACE_NAME}"

command -v codex >/dev/null 2>&1 || {
  echo "codex CLI is required" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required" >&2
  exit 1
}

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "Python 3.10 or newer is required" >&2
  exit 1
}

marketplace_list="$(codex plugin marketplace list --json 2>&1)"
existing_root="$(
  MARKETPLACE_LIST="$marketplace_list" MARKETPLACE_NAME="$MARKETPLACE_NAME" python3 - <<'PY'
import json
import os
import sys

raw = os.environ["MARKETPLACE_LIST"]
start = raw.find("{")
if start < 0:
    print(raw, file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[start:])
for marketplace in payload.get("marketplaces", []):
    if marketplace.get("name") == os.environ["MARKETPLACE_NAME"]:
        print(marketplace.get("root") or "")
        break
PY
)"

marketplace_remove_output=""
marketplace_rebound=false
if [[ -n "$existing_root" && "$existing_root" != "$REPO_ROOT" ]]; then
  marketplace_remove_output="$(codex plugin marketplace remove "$MARKETPLACE_NAME" --json 2>&1)"
  marketplace_rebound=true
  existing_root=""
fi

if [[ "$existing_root" == "$REPO_ROOT" ]]; then
  marketplace_output="$(
    MARKETPLACE_NAME="$MARKETPLACE_NAME" REPO_ROOT="$REPO_ROOT" python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "ok": True,
            "already_present": True,
            "name": os.environ["MARKETPLACE_NAME"],
            "root": os.environ["REPO_ROOT"],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
  )"
else
  marketplace_output="$(codex plugin marketplace add "$REPO_ROOT" --json 2>&1)"
fi
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
MARKETPLACE_REMOVE_OUTPUT="$marketplace_remove_output" \
MARKETPLACE_REBOUND="$marketplace_rebound" \
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

cli = parse(os.environ["CLI_OUTPUT"])
recommended_next = []
if isinstance(cli, dict):
    recommended_next.extend(cli.get("recommended_next") or [])


print(
    json.dumps(
        {
            "ok": True,
            "marketplace": parse(os.environ["MARKETPLACE_OUTPUT"]),
            "marketplace_rebound": os.environ["MARKETPLACE_REBOUND"] == "true",
            "marketplace_remove": parse(os.environ["MARKETPLACE_REMOVE_OUTPUT"]) if os.environ["MARKETPLACE_REMOVE_OUTPUT"] else None,
            "plugin": parse(os.environ["PLUGIN_OUTPUT"]),
            "cli": cli,
            "recommended_next": recommended_next,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
