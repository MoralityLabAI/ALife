import json
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stego_swarm_limit import (  # noqa: E402
    INF_BITS,
    coordinated_units,
    generate_world,
    place_capital,
    place_shared_weights,
    run_episode,
    saturation_bits,
    water_fill,
)


class StegoSwarmLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "experiments" / "stego_swarm_limit_v1" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        cls.design = cls.manifest["design"]

    def test_water_fill_conserves_budget_and_never_covers_zero_demand(self) -> None:
        estimate = np.array([5.0, 4.0, 3.0, 0.0, 0.0, 0.0])
        capacity = water_fill(estimate, 48)
        self.assertEqual(int(capacity.sum()), 48)
        # No unit is ever placed on a zero-estimate location while real demand exists.
        self.assertTrue(np.all(capacity[3:] == 0))

    def test_coordinated_units_saturate_at_budget(self) -> None:
        budget = int(self.design["coalition_budget"])
        warmup = int(self.design["warmup_rounds"])
        locations = int(self.design["locations"])
        self.assertEqual(coordinated_units(0, warmup, locations, budget), 0)
        self.assertEqual(coordinated_units(INF_BITS, warmup, locations, budget), budget)
        # Beyond the saturation threshold, more bandwidth directs no further unit.
        sat = saturation_bits(self.design)
        self.assertEqual(
            coordinated_units(sat, warmup, locations, budget),
            coordinated_units(sat * 100, warmup, locations, budget),
        )

    def test_shared_weights_matches_controller_capacity_but_splits_budget(self) -> None:
        world = generate_world(7901, "stationary", self.design)
        controller = place_capital(world, self.design, INF_BITS)
        weights = place_shared_weights(world, self.design)
        # Same-weights focal-point coordination reproduces the pooled controller's
        # placement exactly; only the capital accounting differs.
        self.assertTrue(np.array_equal(controller["capacity"], weights["capacity"]))
        self.assertEqual(sum(weights["boardings"]), int(self.design["coalition_budget"]))
        self.assertEqual(len(weights["boardings"]), int(self.design["members"]))
        self.assertLess(max(weights["boardings"]), int(self.design["coalition_budget"]))

    def test_capacity_saturation_is_exact(self) -> None:
        episode = run_episode("holdout", 7901, self.manifest)
        for regime in ("stationary", "shift"):
            result = episode["regimes"][regime]
            self.assertEqual(result["gain_at_saturation"], result["gain_at_infinity"])
            self.assertEqual(result["post_saturation_excess"], 0.0)

    def test_shift_gain_is_zero_and_stationary_gain_is_positive(self) -> None:
        episode = run_episode("holdout", 7901, self.manifest)
        self.assertEqual(episode["regimes"]["shift"]["gain_at_infinity"], 0.0)
        self.assertGreater(episode["regimes"]["stationary"]["gain_at_saturation"], 0.0)
        # The capital ceiling (oracle with future demand) is high under both regimes,
        # so the shift loss is a stale-forecast effect, not a capital one.
        self.assertGreater(episode["regimes"]["shift"]["oracle_ceiling_success"], 0.5)

    def test_episode_is_deterministic(self) -> None:
        first = run_episode("holdout", 7902, self.manifest)
        replay = run_episode("holdout", 7902, self.manifest)
        self.assertEqual(first["episode_sha256"], replay["episode_sha256"])
        self.assertTrue(first["validity_gate_pass"])

    def test_manifest_seed_splits_are_disjoint(self) -> None:
        sets = [set(self.manifest["seed_plan"][split]) for split in ("discovery", "confirmatory", "holdout")]
        self.assertEqual(sum(len(values) for values in sets), 24)
        self.assertFalse(sets[0] & sets[1])
        self.assertFalse(sets[0] & sets[2])
        self.assertFalse(sets[1] & sets[2])

    def test_module_imports_no_network_surface(self) -> None:
        # Defensive invariant: the harness never imports a network, wallet, or RPC client.
        import ast

        source = (ROOT / "src" / "stego_swarm_limit.py").read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        banned = {"socket", "requests", "urllib", "http", "asyncio", "ssl", "grpc"}
        self.assertEqual(imported & banned, set(), f"network imports present: {imported & banned}")


if __name__ == "__main__":
    unittest.main()
