#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

run() {
  printf '==> %s\n' "$*"
  "$@"
}

run git diff --check
run python3 -m compileall -q src skills/gitwarp/scripts

SKILL_VALIDATOR="${GITWARP_SKILL_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"
PLUGIN_VALIDATOR="${GITWARP_PLUGIN_VALIDATOR:-$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py}"

if [[ -f "$SKILL_VALIDATOR" ]]; then
  run python3 "$SKILL_VALIDATOR" skills/gitwarp
else
  printf '==> skip missing skill validator: %s\n' "$SKILL_VALIDATOR"
fi

if [[ -f "$PLUGIN_VALIDATOR" ]]; then
  run python3 "$PLUGIN_VALIDATOR" .
else
  printf '==> skip missing plugin validator: %s\n' "$PLUGIN_VALIDATOR"
fi

run python3 scripts/evaluate-skill-behavior.py

(
  cd web/console
  if [[ ! -d node_modules ]]; then
    run npm ci
  fi
  run npm run check:dist
)

run python3 -m unittest discover -s tests -p 'test_*.py' -v
