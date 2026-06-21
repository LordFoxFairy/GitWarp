#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MARKETPLACE_NAME="gitwarp-dev"
PLUGIN_ID="gitwarp@gitwarp-dev"
SCOPE="${CLAUDE_PLUGIN_SCOPE:-user}"

command -v claude >/dev/null 2>&1 || {
  echo "claude CLI is required" >&2
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

marketplace_list="$(claude plugin marketplace list --json 2>&1)"
existing_root="$(
  MARKETPLACE_LIST="$marketplace_list" MARKETPLACE_NAME="$MARKETPLACE_NAME" python3 - <<'PY'
import json
import os
import sys

raw = os.environ["MARKETPLACE_LIST"]
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print(raw, file=sys.stderr)
    raise SystemExit(1)

for marketplace in payload:
    if marketplace.get("name") == os.environ["MARKETPLACE_NAME"]:
        print(marketplace.get("path") or marketplace.get("installLocation") or "")
        break
PY
)"

marketplace_remove_output=""
marketplace_rebound=false
if [[ -n "$existing_root" && "$existing_root" != "$REPO_ROOT" ]]; then
  marketplace_remove_output="$(claude plugin marketplace remove "$MARKETPLACE_NAME" 2>&1)"
  marketplace_rebound=true
  existing_root=""
fi

if [[ "$existing_root" == "$REPO_ROOT" ]]; then
  marketplace_output="$(
    MARKETPLACE_NAME="$MARKETPLACE_NAME" REPO_ROOT="$REPO_ROOT" SCOPE="$SCOPE" python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "ok": True,
            "already_present": True,
            "name": os.environ["MARKETPLACE_NAME"],
            "root": os.environ["REPO_ROOT"],
            "scope": os.environ["SCOPE"],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
  )"
else
  marketplace_output="$(claude plugin marketplace add "$REPO_ROOT" --scope "$SCOPE" 2>&1)"
fi

plugin_install_output=""
plugin_install_ok=true
if ! plugin_install_output="$(claude plugin install "$PLUGIN_ID" --scope "$SCOPE" 2>&1)"; then
  plugin_install_ok=false
fi

plugin_update_output=""
plugin_update_ok=true
if ! plugin_update_output="$(claude plugin update "$PLUGIN_ID" --scope "$SCOPE" 2>&1)"; then
  plugin_update_ok=false
fi

plugin_list="$(claude plugin list --json 2>&1)"
plugin_json="$(
  PLUGIN_LIST="$plugin_list" PLUGIN_ID="$PLUGIN_ID" python3 - <<'PY'
import json
import os
import sys

raw = os.environ["PLUGIN_LIST"]
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print(raw, file=sys.stderr)
    raise SystemExit(1)

for plugin in payload:
    if plugin.get("id") == os.environ["PLUGIN_ID"]:
        print(json.dumps(plugin, separators=(",", ":"), sort_keys=True))
        break
else:
    raise SystemExit(2)
PY
)" || {
  printf '%s\n' "$plugin_install_output" >&2
  exit 1
}

install_cli="$REPO_ROOT/skills/gitwarp/scripts/install_cli.py"
cli_output="$(python3 "$install_cli")"

MARKETPLACE_OUTPUT="$marketplace_output" \
MARKETPLACE_REMOVE_OUTPUT="$marketplace_remove_output" \
MARKETPLACE_REBOUND="$marketplace_rebound" \
PLUGIN_ID="$PLUGIN_ID" \
PLUGIN_INSTALL_OK="$plugin_install_ok" \
PLUGIN_INSTALL_OUTPUT="$plugin_install_output" \
PLUGIN_UPDATE_OK="$plugin_update_ok" \
PLUGIN_UPDATE_OUTPUT="$plugin_update_output" \
PLUGIN_JSON="$plugin_json" \
CLI_OUTPUT="$cli_output" \
python3 - <<'PY'
import json
import os


def parse_maybe_json(raw: str) -> dict[str, object]:
    raw = raw.strip()
    if not raw:
        return {}
    start = raw.find("{")
    if start >= 0:
        try:
            return json.loads(raw[start:])
        except json.JSONDecodeError:
            pass
    return {"raw": raw}


cli = parse_maybe_json(os.environ["CLI_OUTPUT"])
recommended_next = []
if isinstance(cli, dict):
    recommended_next.extend(cli.get("recommended_next") or [])

payload = {
    "ok": True,
    "marketplace": parse_maybe_json(os.environ["MARKETPLACE_OUTPUT"]),
    "marketplace_rebound": os.environ["MARKETPLACE_REBOUND"] == "true",
    "marketplace_remove": parse_maybe_json(os.environ["MARKETPLACE_REMOVE_OUTPUT"])
    if os.environ["MARKETPLACE_REMOVE_OUTPUT"]
    else None,
    "plugin": json.loads(os.environ["PLUGIN_JSON"]),
    "plugin_install": {
        "ok": os.environ["PLUGIN_INSTALL_OK"] == "true",
        "plugin_id": os.environ["PLUGIN_ID"],
        "output": os.environ["PLUGIN_INSTALL_OUTPUT"].strip(),
    },
    "plugin_update": {
        "ok": os.environ["PLUGIN_UPDATE_OK"] == "true",
        "plugin_id": os.environ["PLUGIN_ID"],
        "output": os.environ["PLUGIN_UPDATE_OUTPUT"].strip(),
    },
    "cli": cli,
    "recommended_next": recommended_next,
}

print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
PY
