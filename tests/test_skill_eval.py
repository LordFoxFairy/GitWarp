from __future__ import annotations

from helpers import *


class SkillEvaluationTests(unittest.TestCase):
    def test_skill_behavior_evaluation_passes_required_scenarios(self) -> None:
        result = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "evaluate-skill-behavior.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(result.stdout.strip())
        self.assertTrue(payload["ok"], payload)
        scenario_ids = {scenario["id"] for scenario in payload["scenarios"]}
        self.assertEqual(
            {
                "new_task_prefers_task_create",
                "existing_worktree_preserved",
                "merged_cleanup_requires_explicit_action",
                "session_hook_is_low_noise",
                "plugin_prompt_matches_skill",
            },
            scenario_ids,
        )
        self.assertEqual([], payload["failures"])
