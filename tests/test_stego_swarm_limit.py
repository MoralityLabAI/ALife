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
    delivered_fraction,
    generate_world,
    optimal_capacity,
    place_capital,
    place_controller_public,
    place_shared_weights_public,
    public_observations,
    run_episode,
    saturation_bits,
    summarize,
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

    def test_public_signal_controls_differ_except_with_a_rich_public_signal(self) -> None:
        world = generate_world(7901, "stationary", self.design)
        budget = int(self.design["coalition_budget"])
        members = int(self.design["members"])
        # The shared-weights arm splits its budget M ways; the controller is one pot.
        weak = public_observations(world, 0.08, 0)
        ctrl_weak = place_controller_public(world, self.design, weak, 0.08)
        wts_weak = place_shared_weights_public(world, self.design, weak, 0.08)
        self.assertEqual(ctrl_weak["boardings"], [budget])
        self.assertEqual(len(wts_weak["boardings"]), members)
        self.assertEqual(sum(wts_weak["boardings"]), budget)
        # With a weak public signal the controller's pooled-private placement genuinely
        # differs from the shared-weights public-only placement (not identical by construction).
        self.assertFalse(np.array_equal(ctrl_weak["capacity"], wts_weak["capacity"]))
        # With a near-perfect public signal they converge (pooling private views buys little).
        rich = public_observations(world, 0.99, 9)
        ctrl_rich = place_controller_public(world, self.design, rich, 0.99)
        wts_rich = place_shared_weights_public(world, self.design, rich, 0.99)
        weak_gap = int(np.abs(ctrl_weak["capacity"] - wts_weak["capacity"]).sum())
        rich_gap = int(np.abs(ctrl_rich["capacity"] - wts_rich["capacity"]).sum())
        self.assertLessEqual(rich_gap, weak_gap)

    def test_warden_firewall_is_regime_aware_and_measured(self) -> None:
        rows = [run_episode(sp, s, self.manifest) for sp in ("discovery", "confirmatory", "holdout")
                for s in self.manifest["seed_plan"][sp]]
        summary = summarize(rows, self.manifest)
        sweep = summary["holdout"]["warden_sweep"]
        # Capital warden separates at every public rate; trace warden falls to chance where
        # the channel is cheap (highest public rate), and its separability tracks channel value.
        self.assertTrue(all(cell["capital_warden_auc"] >= 0.95 for cell in sweep))
        low, high = sweep[0], sweep[-1]
        self.assertLessEqual(abs(high["trace_warden_auc"] - 0.5), 0.2)
        self.assertGreaterEqual(abs(low["trace_warden_auc"] - 0.5), abs(high["trace_warden_auc"] - 0.5))
        self.assertGreaterEqual(low["mean_channel_value"], high["mean_channel_value"])
        self.assertEqual(summary["hypothesis_assessment"]["H3_warden_firewall_regime_aware"], "supported")

    def test_capacity_saturation_is_exact(self) -> None:
        episode = run_episode("holdout", 7901, self.manifest)
        for regime in ("stationary", "shift"):
            result = episode["regimes"][regime]
            self.assertEqual(result["gain_at_saturation"], result["gain_at_infinity"])
            self.assertEqual(result["post_saturation_excess"], 0.0)

    def test_shift_collapses_success_toward_a_high_ceiling(self) -> None:
        episode = run_episode("holdout", 7901, self.manifest)
        stationary = episode["regimes"]["stationary"]
        shift = episode["regimes"]["shift"]
        stationary_success = stationary["independent_success"] + stationary["gain_at_infinity"]
        shift_success = shift["independent_success"] + shift["gain_at_infinity"]
        self.assertGreater(stationary["gain_at_saturation"], 0.0)
        # Success collapses under the shift while the optimal ceiling stays high: the loss
        # is a stale-forecast effect, not a capital one. Coordination barely helps under shift.
        self.assertGreater(stationary_success - shift_success, 0.3)
        self.assertGreater(shift["optimal_ceiling_success"], 0.5)
        self.assertLess(abs(shift["gain_at_infinity"]), 0.05)

    def test_optimal_capacity_is_a_true_ceiling_no_placement_exceeds(self) -> None:
        episode = run_episode("holdout", 7901, self.manifest)
        for regime in ("stationary", "shift"):
            result = episode["regimes"][regime]
            self.assertFalse(result["any_placement_exceeds_ceiling"])
        # The greedy-on-exceedance optimum dominates the mean-demand water-fill it replaced.
        world = generate_world(7901, "stationary", self.design)
        opt = delivered_fraction(world, optimal_capacity(world, self.design))
        mean_fill = delivered_fraction(world, water_fill(world["eval_mean"], int(self.design["coalition_budget"])))
        self.assertGreaterEqual(opt + 1e-12, mean_fill)

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
