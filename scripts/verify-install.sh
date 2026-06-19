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

repo_enter="$(gitwarp enter --cwd "$REPO_ROOT")"
REPO_ENTER="$repo_enter" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["REPO_ENTER"])
assert payload["ok"] is True
assert payload["statusline"].startswith("GITWARP[")
assert payload["location"] in {"main", "worktree"}
PY

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

pre_init_doctor="$(gitwarp doctor --cwd "$tmpdir")"
PRE_INIT_DOCTOR="$pre_init_doctor" TMPDIR="$tmpdir" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["PRE_INIT_DOCTOR"])
assert payload["ok"] is True
codes = {finding["code"] for finding in payload["findings"]}
assert {"gitwarp_initialized", "ledger_schema", "gitwarp_ignored", "agent_config"} <= codes
assert any("gitwarp init --cwd" in item for item in payload["recommended_next"])
assert not os.path.exists(os.path.join(os.environ["TMPDIR"], ".gitwarp", "ledger.json"))
PY

init_output="$(gitwarp init --cwd "$tmpdir")"
INIT_OUTPUT="$init_output" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["INIT_OUTPUT"])
assert payload["ok"] is True
assert payload["created"]["ledger"] is True
assert payload["updated"]["ignore_rule"] is True
for key in ("ledger_path", "worktree_root", "dossier_root"):
    assert payload[key]
    assert Path(payload[key]).exists()
assert payload["ignore_target"].endswith("/.git/info/exclude")
assert any("gitwarp doctor" in item for item in payload["recommended_next"])
PY

second_init_output="$(gitwarp init --cwd "$tmpdir")"
SECOND_INIT_OUTPUT="$second_init_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["SECOND_INIT_OUTPUT"])
assert payload["ok"] is True
assert payload["created"]["ledger"] is False
assert payload["updated"]["ignore_rule"] is False
PY

post_init_doctor="$(gitwarp doctor --cwd "$tmpdir")"
POST_INIT_DOCTOR="$post_init_doctor" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["POST_INIT_DOCTOR"])
assert payload["ok"] is True
findings = {finding["code"]: finding for finding in payload["findings"]}
assert findings["gitwarp_initialized"]["severity"] == "ok"
assert findings["ledger_schema"]["severity"] == "ok"
assert findings["gitwarp_ignored"]["severity"] == "ok"
assert findings["agent_config"]["severity"] == "ok"
PY

main_enter="$(gitwarp enter --cwd "$tmpdir")"
MAIN_ENTER="$main_enter" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["MAIN_ENTER"])
assert payload["ok"] is True
assert payload["location"] == "main"
assert payload["statusline"] == "GITWARP[main-repo]"
assert any("gitwarp start" in item for item in payload["recommended_next"])
PY

agents_output="$(gitwarp agents --cwd "$tmpdir")"
AGENTS_OUTPUT="$agents_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["AGENTS_OUTPUT"])
assert payload["ok"] is True
assert payload["default_agent"] == "codex"
names = {agent["name"] for agent in payload["agents"]}
assert {"codex", "claude"} <= names
assert payload["config_path"].endswith("/.gitwarp/agents.json")
PY

cat > "$tmpdir/.gitwarp/agents.json" <<'JSON'
{"version":1,"default_agent":"local","agents":{"local":{"description":"Local smoke agent","command":["python3","-c","{prompt}","{worktree}"],"status":"enabled"}}}
JSON

scan_output="$(gitwarp scan --cwd "$tmpdir")"
SCAN_OUTPUT="$scan_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["SCAN_OUTPUT"])
assert payload["ok"] is True
assert len(payload["worktrees"]) == 1
PY

dispatch_output="$(
  gitwarp dispatch --cwd "$tmpdir" \
    --agent local \
    --branch feature/verify-dispatch \
    --purpose "Verify dispatch print"
)"
dispatch_path="$(
  DISPATCH_OUTPUT="$dispatch_output" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["DISPATCH_OUTPUT"])
assert payload["ok"] is True
assert payload["mode"] == "print"
assert payload["agent"] == "local"
assert payload["status"] == "dispatched"
assert payload["branch"] == "feature/verify-dispatch"
assert payload["path"].endswith("/.gitwarp/worktrees/feature-verify-dispatch")
assert payload["launch_command"][0:2] == ["python3", "-c"]
assert "gitwarp enter" in payload["launch_command"][2]
assert "Record milestones with gitwarp handoff" in payload["launch_command"][2]
assert payload["launch_command"][3] == payload["path"]
for key in ("task_md", "progress_md", "lessons_md"):
    assert Path(payload[key]).exists()
print(payload["path"])
PY
)"

set +e
execute_output="$(
  gitwarp dispatch --cwd "$tmpdir" \
    --agent local \
    --branch feature/verify-execute \
    --purpose "Verify execute rejection" \
    --command-mode execute
)"
execute_rc=$?
set -e
if [[ "$execute_rc" -eq 0 ]]; then
  echo "dispatch execute unexpectedly succeeded" >&2
  exit 1
fi
EXECUTE_OUTPUT="$execute_output" TMPDIR="$tmpdir" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["EXECUTE_OUTPUT"])
assert payload["ok"] is False
assert "execute is not supported yet" in payload["error"]
assert not (Path(os.environ["TMPDIR"]) / ".gitwarp" / "worktrees" / "feature-verify-execute").exists()
PY

manual_path="$tmpdir/manual-adopt"
git -C "$tmpdir" worktree add -b feature/verify-adopt "$manual_path" HEAD >/dev/null
adopt_output="$(
  gitwarp adopt --cwd "$tmpdir" \
    --path "$manual_path" \
    --agent-id verify-adopt \
    --purpose "Verify adopt"
)"
ADOPT_OUTPUT="$adopt_output" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["ADOPT_OUTPUT"])
assert payload["ok"] is True
assert payload["status"] == "adopted"
assert payload["branch"] == "feature/verify-adopt"
assert payload["outside_guarded_root"] is True
for key in ("task_md", "progress_md", "lessons_md"):
    assert Path(payload[key]).exists()
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

enter_output="$(gitwarp enter --cwd "$nested_path")"
ENTER_OUTPUT="$enter_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["ENTER_OUTPUT"])
assert payload["ok"] is True
assert payload["location"] == "worktree"
assert payload["statusline"] == "GITWARP[verify-agent@feature/verify-install]"
assert payload["worktree"]["branch"] == "feature/verify-install"
assert "Verify GitWarp install" in payload["snippets"]["task"]
assert "Verified install smoke flow" in payload["snippets"]["progress"]
assert "Dossier smoke test passed" in payload["snippets"]["lessons"]
PY

enter_prompt="$(gitwarp enter --cwd "$nested_path" --format prompt)"
if [[ "$enter_prompt" != *"GitWarp Context: GITWARP[verify-agent@feature/verify-install]"* ]]; then
  echo "enter prompt did not include GitWarp context" >&2
  exit 1
fi
if [[ "$enter_prompt" != *"task.md"* || "$enter_prompt" != *"progress.md"* || "$enter_prompt" != *"lessons.md"* ]]; then
  echo "enter prompt did not include dossier paths" >&2
  exit 1
fi

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

board_status_output="$(gitwarp board --cwd "$tmpdir" --status verified)"
BOARD_STATUS_OUTPUT="$board_status_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["BOARD_STATUS_OUTPUT"])
assert payload["ok"] is True
branches = {item["branch"] for item in payload["worktrees"]}
assert branches == {"feature/verify-install"}
PY

board_stale_output="$(gitwarp board --cwd "$tmpdir" --stale 0)"
BOARD_STALE_OUTPUT="$board_stale_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["BOARD_STALE_OUTPUT"])
row = next(item for item in payload["worktrees"] if item["branch"] == "feature/verify-install")
assert row["stale"] is True
assert isinstance(row["age_seconds"], int)
PY

board_verbose_output="$(gitwarp board --cwd "$tmpdir" --verbose)"
BOARD_VERBOSE_OUTPUT="$board_verbose_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["BOARD_VERBOSE_OUTPUT"])
row = next(item for item in payload["worktrees"] if item["branch"] == "feature/verify-install")
assert "Verify GitWarp install" in row["snippets"]["task"]
assert "Verified install smoke flow" in row["snippets"]["progress"]
assert "Dossier smoke test passed" in row["snippets"]["lessons"]
PY

table_output="$(gitwarp board --cwd "$tmpdir" --format table)"
if [[ "$table_output" != *"feature/verify-install"* ]]; then
  echo "board table did not include feature/verify-install" >&2
  exit 1
fi

reconcile_output="$(gitwarp reconcile --cwd "$tmpdir" --stale 0)"
RECONCILE_OUTPUT="$reconcile_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["RECONCILE_OUTPUT"])
assert payload["ok"] is True
assert payload["repo_root"]
assert "summary" in payload
assert isinstance(payload["findings"], list)
codes = {finding["code"] for finding in payload["findings"]}
assert "merged_head" in codes
PY

doctor_output="$(gitwarp doctor --cwd "$tmpdir")"
DOCTOR_OUTPUT="$doctor_output" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["DOCTOR_OUTPUT"])
assert payload["ok"] is True
codes = {finding["code"] for finding in payload["findings"]}
expected = {
    "git",
    "python3",
    "gitwarp_launcher",
    "gitwarp_initialized",
    "ledger_schema",
    "gitwarp_ignored",
    "agent_config",
    "agent_binary",
    "codex_plugin_metadata",
}
assert expected <= codes
assert "session_hook_context" not in codes
assert "summary" in payload
PY

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
DISPATCH_PATH="$dispatch_path" \
python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "ok": True,
            "plugin": os.environ["PLUGIN_ID"],
            "cli": os.environ["CLI_PATH"],
            "dispatch_path": os.environ["DISPATCH_PATH"],
            "smoke": "init-agents-dispatch-adopt-reconcile-doctor-enter-start-context-handoff-board-statusline-finish",
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
