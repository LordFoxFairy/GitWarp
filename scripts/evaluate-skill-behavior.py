#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def codex_default_prompt() -> str:
    payload = json.loads(read(".codex-plugin/plugin.json"))
    return "\n".join(payload["interface"]["defaultPrompt"])


def require_contains(source: str, needle: str, label: str) -> str | None:
    if needle in source:
        return None
    return f"{label} must contain {needle!r}"


def require_absent(source: str, needle: str, label: str) -> str | None:
    if needle not in source:
        return None
    return f"{label} must not contain {needle!r}"


def scenario_new_task_prefers_task_create() -> list[str]:
    skill = read("skills/gitwarp/SKILL.md")
    presenter = read("src/gitwarp/adapters/presenters.py")
    plugin_prompt = codex_default_prompt()
    checks = [
        require_contains(skill, "`gitwarp task create` | Preferred intake", "SKILL.md"),
        require_contains(skill, 'gitwarp task create --title "Implement isolated task"', "SKILL.md"),
        require_contains(presenter, 'gitwarp task create --title "<title>"', "enter recommendations"),
        require_contains(plugin_prompt, "gitwarp task create", "Codex plugin prompt"),
    ]
    return [item for item in checks if item]


def scenario_existing_worktree_preserved() -> list[str]:
    skill = read("skills/gitwarp/SKILL.md")
    hook = read("hooks/session-start-codex")
    checks = [
        require_contains(skill, "If the user assigns an existing worktree", "SKILL.md"),
        require_contains(skill, "stop after verification unless the user explicitly asks", "SKILL.md"),
        require_contains(hook, "When assigned an existing worktree, leave it intact", "session hook"),
    ]
    return [item for item in checks if item]


def scenario_merged_cleanup_requires_explicit_action() -> list[str]:
    skill = read("skills/gitwarp/SKILL.md")
    checks = [
        require_contains(skill, "finish --collapse-merged", "SKILL.md"),
        require_contains(skill, "refuses base worktrees", "SKILL.md"),
        require_contains(skill, "They do not merge, push, or delete the Git branch", "SKILL.md"),
        require_contains(skill, "unless cleanup was explicitly requested", "SKILL.md"),
    ]
    return [item for item in checks if item]


def scenario_session_hook_is_low_noise() -> list[str]:
    checks: list[str] = []
    for relative in ("hooks/session-start", "hooks/session-start-codex"):
        hook = read(relative)
        checks.extend(
            item
            for item in (
                require_contains(hook, "gitwarp statusline --cwd", relative),
                require_contains(hook, "gitwarp task create --help", relative),
                require_contains(hook, "Use gitwarp matrix, then gitwarp next", relative),
                require_contains(hook, "Use gitwarp task create for new isolated work", relative),
                require_contains(hook, "run gitwarp enter only when full dossier context is needed", relative),
                require_absent(hook, "gitwarp enter --cwd", relative),
                require_absent(hook, "--format prompt", relative),
                require_absent(hook, "Current GitWarp Context", relative),
                require_absent(hook, "Agent protocol:", relative),
                require_absent(hook, "Use gitwarp create for isolated edits", relative),
            )
            if item
        )
    return checks


def scenario_plugin_prompt_matches_skill() -> list[str]:
    plugin_prompt = codex_default_prompt()
    skill = read("skills/gitwarp/SKILL.md")
    checks = [
        require_contains(plugin_prompt, "gitwarp task create", "Codex plugin prompt"),
        require_contains(plugin_prompt, "gitwarp create --role base", "Codex plugin prompt"),
        require_contains(skill, "Prefer `task create` for new work", "SKILL.md"),
        require_absent(plugin_prompt, "with gitwarp create", "Codex plugin prompt"),
    ]
    return [item for item in checks if item]


def scenario_skill_preserves_engineering_discipline() -> list[str]:
    skill = read("skills/gitwarp/SKILL.md")
    checks = [
        require_contains(skill, "Session Startup Loop", "SKILL.md"),
        require_contains(skill, "Read the dossier before editing", "SKILL.md"),
        require_contains(skill, "Failure Pivot Rule", "SKILL.md"),
        require_contains(skill, "Python and TypeScript Guardrails", "SKILL.md"),
        require_contains(skill, "run the narrowest relevant checks first", "SKILL.md"),
        require_contains(skill, "record the correction with `gitwarp handoff --lesson", "SKILL.md"),
        require_contains(skill, "Handoff Standard", "SKILL.md"),
    ]
    return [item for item in checks if item]


def scenario_install_commands_are_first_class() -> list[str]:
    skill = read("skills/gitwarp/SKILL.md")
    readme = read("README.md")
    parser = read("src/gitwarp/adapters/cli/parser.py")
    checks = [
        require_contains(skill, "`gitwarp install`", "SKILL.md"),
        require_contains(skill, "gitwarp install self", "SKILL.md"),
        require_contains(skill, "gitwarp install codex", "SKILL.md"),
        require_contains(skill, "gitwarp install claude-code", "SKILL.md"),
        require_contains(readme, "gitwarp install self", "README.md"),
        require_contains(readme, "gitwarp install codex", "README.md"),
        require_contains(readme, "gitwarp install claude-code", "README.md"),
        require_contains(parser, 'add_parser("install"', "CLI parser"),
    ]
    return [item for item in checks if item]


SCENARIOS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("new_task_prefers_task_create", scenario_new_task_prefers_task_create),
    ("existing_worktree_preserved", scenario_existing_worktree_preserved),
    ("merged_cleanup_requires_explicit_action", scenario_merged_cleanup_requires_explicit_action),
    ("session_hook_is_low_noise", scenario_session_hook_is_low_noise),
    ("plugin_prompt_matches_skill", scenario_plugin_prompt_matches_skill),
    ("skill_preserves_engineering_discipline", scenario_skill_preserves_engineering_discipline),
    ("install_commands_are_first_class", scenario_install_commands_are_first_class),
)


def main() -> int:
    scenarios: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for scenario_id, check in SCENARIOS:
        messages = check()
        scenarios.append({"id": scenario_id, "ok": not messages, "failures": messages})
        failures.extend({"scenario": scenario_id, "message": message} for message in messages)

    payload = {
        "ok": not failures,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "failures": failures,
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
