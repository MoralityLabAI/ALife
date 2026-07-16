import json
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from confinement_transfer import (  # noqa: E402
    mutate_schedule,
    random_schedule,
    run_episode,
    simulate_schedule,
)


class ConfinementTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "experiments" / "confinement_transfer_v1" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        cls.design = cls.manifest["design"]

    def test_schedule_and_mutation_preserve_exact_action_budget(self) -> None:
        rng = np.random.default_rng(123)
        schedule = random_schedule(rng, 80, 24)
        mutated = mutate_schedule(schedule, rng, 80, 5)
        self.assertEqual(len(schedule), 24)
        self.assertEqual(len(mutated), 24)
        self.assertEqual(len(set(mutated)), 24)
        self.assertTrue(all(0 <= value < 80 for value in mutated))

    def test_original_projection_validity_gates_are_preserved(self) -> None:
        schedule = tuple(range(24))
        row = simulate_schedule(schedule, {"id": "test", "beta": 0.55, "y_step": 0.04}, self.design)
        self.assertEqual(row["advance_actions_executed"], 24)
        self.assertEqual(row["proxy_failure_steps"], 0)
        self.assertEqual(row["max_abs_closure_defect_eta"], 0.0)
        self.assertGreater(row["kernel_escape_rate"], 0.0)

    def test_null_schedule_has_no_kernel_escape(self) -> None:
        row = simulate_schedule((), {"id": "null", "beta": 0.55, "y_step": 0.04}, self.design)
        self.assertEqual(row["kernel_escape_steps"], 0)
        self.assertIsNone(row["fidelity_half_life_step"])

    def test_paired_episode_is_deterministic_and_compute_matched(self) -> None:
        first = run_episode("holdout", 6901, self.manifest)
        replay = run_episode("holdout", 6901, self.manifest)
        self.assertEqual(first["episode_sha256"], replay["episode_sha256"])
        self.assertTrue(first["validity_gate_pass"])
        self.assertEqual(first["methods"][0]["candidate_evaluations"], 128)
        self.assertEqual(first["methods"][1]["candidate_evaluations"], 128)
        self.assertEqual(first["methods"][0]["action_budget"], 24)
        self.assertEqual(first["methods"][1]["action_budget"], 24)

    def test_manifest_plan_and_seeds(self) -> None:
        sets = [set(self.manifest["seed_plan"][split]) for split in ("discovery", "confirmatory", "holdout")]
        self.assertEqual(sum(len(values) for values in sets), 24)
        self.assertFalse(sets[0] & sets[1])
        self.assertFalse(sets[0] & sets[2])
        self.assertFalse(sets[1] & sets[2])


if __name__ == "__main__":
    unittest.main()
