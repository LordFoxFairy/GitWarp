#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PLUGIN_ID="gitwarp@gitwarp-dev"

command -v codex >/dev/null 2>&1 || {
  echo "codex CLI is required" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || {
  echo "git is required" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required" >&2
  exit 1
}

command -v gitwarp >/dev/null 2>&1 || {
  echo "gitwarp is not on PATH" >&2
  exit 1
}

plugin_list="$(codex plugin list --json 2>&1)"
PLUGIN_LIST="$plugin_list" PLUGIN_ID="$PLUGIN_ID" python3 - <<'PY'
import json
import os
import sys

raw = os.environ["PLUGIN_LIST"]
start = raw.find("{")
if start < 0:
    print(raw, file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[start:])
for plugin in payload.get("installed", []):
    if plugin.get("pluginId") == os.environ["PLUGIN_ID"] and plugin.get("enabled") is True:
        raise SystemExit(0)
print(f"{os.environ['PLUGIN_ID']} is not installed and enabled", file=sys.stderr)
raise SystemExit(1)
PY

version="$(gitwarp --version)"
if [[ "$version" != "gitwarp 0.1.0" ]]; then
  echo "unexpected gitwarp version: $version" >&2
  exit 1
fi

banner="$(gitwarp statusline --cwd "$REPO_ROOT")"
if [[ "$banner" != "GITWARP[main-repo]" ]]; then
  echo "unexpected repository banner: $banner" >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

git -C "$tmpdir" init -b main >/dev/null
git -C "$tmpdir" config user.name "GitWarp Verify"
git -C "$tmpdir" config user.email "verify@example.com"
printf "hello\n" > "$tmpdir/README.md"
git -C "$tmpdir" add README.md
git -C "$tmpdir" commit -m init >/dev/null

scan_output="$(gitwarp scan --cwd "$tmpdir")"
SCAN_OUTPUT="$scan_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["SCAN_OUTPUT"])
assert payload["ok"] is True
assert len(payload["worktrees"]) == 1
PY

summon_output="$(
  gitwarp summon --cwd "$tmpdir" \
    --agent-id verify-agent \
    --branch feature/verify-install \
    --purpose "Verify GitWarp install"
)"

worktree_path="$(
  SUMMON_OUTPUT="$summon_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["SUMMON_OUTPUT"])
assert payload["ok"] is True
print(payload["path"])
PY
)"

nested_path="$worktree_path/src"
mkdir -p "$nested_path"

worktree_banner="$(gitwarp statusline --cwd "$nested_path")"
if [[ "$worktree_banner" != "GITWARP[verify-agent@feature/verify-install]" ]]; then
  echo "unexpected worktree banner: $worktree_banner" >&2
  exit 1
fi

annotate_output="$(
  gitwarp annotate --cwd "$nested_path" \
    --status verified \
    --note "Verified install smoke flow"
)"
ANNOTATE_OUTPUT="$annotate_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["ANNOTATE_OUTPUT"])
assert payload["ok"] is True
assert payload["status"] == "verified"
assert payload["notes_count"] == 1
PY

context_output="$(gitwarp context --cwd "$nested_path")"
CONTEXT_OUTPUT="$context_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["CONTEXT_OUTPUT"])
worktree = payload["worktree"]
assert payload["ok"] is True
assert payload["cwd"].endswith("/src")
assert worktree["branch"] == "feature/verify-install"
assert worktree["agent_id"] == "verify-agent"
assert worktree["purpose"] == "Verify GitWarp install"
assert worktree["status"] == "verified"
assert worktree["notes"][-1]["note"] == "Verified install smoke flow"
PY

collapse_output="$(gitwarp collapse --cwd "$tmpdir" --branch feature/verify-install)"
COLLAPSE_OUTPUT="$collapse_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["COLLAPSE_OUTPUT"])
assert payload["ok"] is True
assert payload["removed_branch"] == "feature/verify-install"
PY

if [[ -e "$worktree_path" ]]; then
  echo "worktree path still exists after collapse: $worktree_path" >&2
  exit 1
fi

CLI_PATH="$(command -v gitwarp)" \
PLUGIN_ID="$PLUGIN_ID" \
python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "ok": True,
            "plugin": os.environ["PLUGIN_ID"],
            "cli": os.environ["CLI_PATH"],
            "smoke": "scan-summon-context-annotate-statusline-collapse",
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
