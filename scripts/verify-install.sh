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
if [[ "$banner" != "GITWARP[main-repo]" && "$banner" != GITWARP\[*@*\] ]]; then
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

start_output="$(
  gitwarp start --cwd "$tmpdir" \
    --agent-id verify-agent \
    --branch feature/verify-install \
    --purpose "Verify GitWarp install"
)"

worktree_path="$(
  START_OUTPUT="$start_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["START_OUTPUT"])
assert payload["ok"] is True
assert payload["status"] == "active"
for key in ("task_md", "progress_md", "lessons_md"):
    assert payload[key]
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

handoff_output="$(
  gitwarp handoff --cwd "$nested_path" \
    --status verified \
    --progress "Verified install smoke flow" \
    --lesson "Dossier smoke test passed"
)"
HANDOFF_OUTPUT="$handoff_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["HANDOFF_OUTPUT"])
assert payload["ok"] is True
assert payload["status"] == "verified"
assert payload["latest_progress"] == "Verified install smoke flow"
assert payload["latest_lesson"] == "Dossier smoke test passed"
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
assert worktree["latest_progress"] == "Verified install smoke flow"
assert worktree["latest_lesson"] == "Dossier smoke test passed"
for key in ("task_md", "progress_md", "lessons_md"):
    assert worktree[key]
PY

board_output="$(gitwarp board --cwd "$tmpdir")"
BOARD_OUTPUT="$board_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["BOARD_OUTPUT"])
assert payload["ok"] is True
row = next(item for item in payload["worktrees"] if item["branch"] == "feature/verify-install")
assert row["latest_progress"] == "Verified install smoke flow"
assert row["latest_lesson"] == "Dossier smoke test passed"
PY

table_output="$(gitwarp board --cwd "$tmpdir" --format table)"
if [[ "$table_output" != *"feature/verify-install"* ]]; then
  echo "board table did not include feature/verify-install" >&2
  exit 1
fi

finish_output="$(
  gitwarp finish --cwd "$nested_path" \
    --status pushed \
    --progress "Verified and pushed" \
    --lesson "Dossier preserved after collapse" \
    --collapse
)"
FINISH_OUTPUT="$finish_output" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["FINISH_OUTPUT"])
assert payload["ok"] is True
assert payload["status"] == "pushed"
assert payload["collapsed"] is True
assert Path(payload["progress_md"]).exists()
assert Path(payload["lessons_md"]).exists()
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
            "smoke": "scan-start-context-handoff-board-statusline-finish",
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
