import json
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery_curriculum import (  # noqa: E402
    TASK_FAMILIES,
    abstain_submission,
    build_task,
    calibrated_submission,
    exact_causal_sites,
    run_task_episode,
    score_submission,
    simulate_rule90,
    simulate_shift,
)


class DiscoveryCurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "experiments" / "discovery_curriculum_v1" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def test_rule90_exact_causal_sites_match_bruteforce(self) -> None:
        initial = np.array([1, 0, 1, 1, 0, 0, 1, 0], dtype=bool)
        target = 2
        horizon = 3
        expected = []
        baseline = simulate_rule90(initial, horizon)[target]
        for site in range(initial.size):
            treated = initial.copy()
            treated[site] = ~treated[site]
            if simulate_rule90(treated, horizon)[target] != baseline:
                expected.append(site)
        self.assertEqual(exact_causal_sites(initial, horizon, target), expected)

    def test_reversible_shift_conserves_live_count(self) -> None:
        state = np.array([1, 0, 1, 1, 0, 0], dtype=bool)
        self.assertEqual(int(state.sum()), int(simulate_shift(state, 17).sum()))

    def test_point_and_set_identification_are_distinct(self) -> None:
        interval_task = build_task("masked_interval", 101, 16, 5)
        point_task = build_task("masked_point", 101, 16, 5)
        self.assertTrue(interval_task["oracle"]["identifiable_with_budget"])
        self.assertEqual(interval_task["identification"], "set")
        self.assertFalse(point_task["oracle"]["identifiable_with_budget"])
        self.assertEqual(point_task["identification"], "not_point_identified")

    def test_registered_abstention_is_rewarded_only_when_needed(self) -> None:
        identified = build_task("true_null", 102, 16, 5)
        unidentified = build_task("masked_point", 102, 16, 5)
        identified_score = score_submission(identified, abstain_submission(identified))
        unidentified_score = score_submission(unidentified, calibrated_submission(unidentified))
        self.assertTrue(identified_score["avoidable_abstention"])
        self.assertEqual(identified_score["evidence_score"], 0.0)
        self.assertTrue(unidentified_score["correct_abstention"])
        self.assertEqual(unidentified_score["evidence_score"], 1.0)

    def test_episode_is_deterministic_and_complete(self) -> None:
        first = run_task_episode("holdout", "causal_sites", 5901, 16, 5)
        replay = run_task_episode("holdout", "causal_sites", 5901, 16, 5)
        self.assertEqual(first["episode_sha256"], replay["episode_sha256"])
        self.assertEqual(len(first["investigations"]), 3)
        self.assertTrue(first["oracle_receipt"]["oracle_present"])

    def test_manifest_plan_fits_budget_and_seeds_are_disjoint(self) -> None:
        plan = sum(
            len(self.manifest["seed_plan"][split]) * len(TASK_FAMILIES)
            for split in ("discovery", "confirmatory", "holdout")
        )
        self.assertEqual(plan, 63)
        self.assertLessEqual(plan, self.manifest["budget"]["max_episodes"])
        seed_sets = [set(self.manifest["seed_plan"][split]) for split in ("discovery", "confirmatory", "holdout")]
        self.assertFalse(seed_sets[0] & seed_sets[1])
        self.assertFalse(seed_sets[0] & seed_sets[2])
        self.assertFalse(seed_sets[1] & seed_sets[2])


if __name__ == "__main__":
    unittest.main()
