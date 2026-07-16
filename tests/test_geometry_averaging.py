from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geometry_averaging_experiment import (  # noqa: E402
    condition_specs,
    mean_field_next,
    neighborhood_offsets,
    rule_counts,
    run_episode,
)


class GeometryAveragingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "experiments" / "geometry_averaging_v1" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def test_moore_degree_grows_exponentially(self) -> None:
        self.assertEqual(len(neighborhood_offsets(2, "moore", 12)), 8)
        self.assertEqual(len(neighborhood_offsets(3, "moore", 12)), 26)
        self.assertEqual(len(neighborhood_offsets(4, "moore", 12)), 80)

    def test_degree_matched_is_symmetric_and_spans_axes(self) -> None:
        for dimension in (2, 3, 4, 5):
            offsets = neighborhood_offsets(dimension, "degree_matched", 12)
            self.assertEqual(len(offsets), 12)
            offset_set = set(offsets)
            for offset in offsets:
                self.assertIn(tuple(-value for value in offset), offset_set)
            for axis in range(dimension):
                self.assertTrue(any(offset[axis] != 0 for offset in offsets))

    def test_fraction_band_recovers_conway_counts_at_degree_eight(self) -> None:
        births, survivals = rule_counts("fraction_band", 8)
        self.assertEqual(births, (3,))
        self.assertEqual(survivals, (2, 3))

    def test_mean_field_dead_state_is_absorbing(self) -> None:
        births, survivals = rule_counts("literal_b3s23", 8)
        self.assertEqual(mean_field_next(0.0, 8, births, survivals), 0.0)

    def test_manifest_episode_plan_fits_budget(self) -> None:
        planned = sum(
            len(self.manifest["seed_plan"][split])
            * len(condition_specs(self.manifest, split, False))
            for split in ("discovery", "confirmatory", "holdout")
        )
        self.assertEqual(planned, 144)
        self.assertLessEqual(planned, self.manifest["budget"]["max_episodes"])

    def test_episode_replay_is_deterministic_and_initialization_is_paired(self) -> None:
        common = {
            "split": "discovery",
            "seed": 123,
            "dimension": 2,
            "side": 12,
            "density": 0.35,
            "rule_profile": "fraction_band",
            "matched_degree": 12,
            "steps": 6,
            "burn_in": 2,
            "correlation_max_lag": 3,
            "deadline": time.monotonic() + 30,
            "max_ram_mb": 512,
        }
        first = run_episode(neighborhood="axis", **common)
        second = run_episode(neighborhood="axis", **common)
        matched = run_episode(neighborhood="degree_matched", **common)
        self.assertEqual(
            first["provenance"]["trajectory_sha256"],
            second["provenance"]["trajectory_sha256"],
        )
        self.assertEqual(
            first["provenance"]["final_state_sha256"],
            second["provenance"]["final_state_sha256"],
        )
        self.assertEqual(
            first["provenance"]["initial_state_sha256"],
            matched["provenance"]["initial_state_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
