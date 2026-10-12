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
    focal_partition_boardings,
    generate_world,
    optimal_capacity,
    place_capital,
    place_naive_decentralised,
    public_observations,
    run_episode,
    saturation_bits,
    summarize,
    warden_estimate,
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

    def test_information_access_placement_differs_except_with_a_rich_public_signal(self) -> None:
        world = generate_world(7901, "stationary", self.design)
        budget = int(self.design["coalition_budget"])

        def cap(info, obs, rate):
            return water_fill(warden_estimate(info, world, self.design, obs, rate), budget)

        weak = public_observations(world, 0.08, 0)
        rich = public_observations(world, 0.99, 9)
        # The pooled-private estimate differs from public-only at a weak signal (the channel
        # buys a different placement) and converges at a near-perfect public signal.
        weak_gap = int(np.abs(cap("public_only", weak, 0.08) - cap("pooled_private", weak, 0.08)).sum())
        rich_gap = int(np.abs(cap("public_only", rich, 0.99) - cap("pooled_private", rich, 0.99)).sum())
        self.assertGreater(weak_gap, 0)
        self.assertLessEqual(rich_gap, weak_gap)

    def test_focal_partition_is_decentralised_and_sums_to_budget(self) -> None:
        budget = int(self.design["coalition_budget"])
        members = int(self.design["members"])
        boardings = focal_partition_boardings(budget, members)
        self.assertEqual(len(boardings), members)
        self.assertEqual(sum(boardings), budget)
        # Each member's slice is a pure function of (budget, members, its index): no member
        # observes another's choice, so the partition is focal-point, not a channel.
        self.assertLessEqual(max(boardings) - min(boardings), 1)

    def test_naive_decentralised_is_much_worse_than_focal(self) -> None:
        # Point 1 of the review: the focal-partition convention is load-bearing. A naive
        # population (each member fills its own share from the public signal) piles onto the
        # same locations and delivers far less than the coordinated public-only placement.
        world = generate_world(7901, "stationary", self.design)
        budget = int(self.design["coalition_budget"])
        obs = public_observations(world, 0.08, 0)
        naive = delivered_fraction(world, place_naive_decentralised(world, self.design, obs, 0.08))
        focal = delivered_fraction(world, water_fill(warden_estimate("public_only", world, self.design, obs, 0.08), budget))
        self.assertLess(naive, focal - 0.1)

    def test_warden_factorial_is_regime_aware_and_measured(self) -> None:
        rows = [run_episode(sp, s, self.manifest) for sp in ("discovery", "confirmatory", "holdout")
                for s in self.manifest["seed_plan"][sp]]
        summary = summarize(rows, self.manifest)
        sweep = summary["warden_firewall"]["pooled_rate_sweep"]
        # Capital warden (account axis) separates at every public rate; trace warden (info
        # axis) falls to chance where the channel is cheap, and its separability tracks value.
        self.assertTrue(all(cell["capital_warden_auc"] >= 0.95 for cell in sweep))
        low, high = sweep[0], sweep[-1]
        self.assertLessEqual(abs(high["trace_warden_auc"] - 0.5), 0.2)
        self.assertGreaterEqual(abs(low["trace_warden_auc"] - 0.5), abs(high["trace_warden_auc"] - 0.5))
        self.assertGreaterEqual(low["mean_channel_value"], high["mean_channel_value"])
        self.assertEqual(summary["hypothesis_assessment"]["H3_warden_firewall_regime_aware"], "supported")

    def test_trained_attributed_warden_reads_account_everywhere_info_only_where_valuable(self) -> None:
        rows = [run_episode(sp, s, self.manifest) for sp in ("discovery", "confirmatory", "holdout")
                for s in self.manifest["seed_plan"][sp]]
        summary = summarize(rows, self.manifest)
        trained = summary["trained_warden"]["rate_sweep"]
        # The trained attributed warden reads account structure out of sample at every rate
        # (attribution exposes it), and reads information access strongly only where the channel
        # is valuable (the weakest public rate), eroding as the channel loses value.
        self.assertTrue(all(cell["trained_account_axis_auc"] >= 0.9 for cell in trained))
        self.assertGreaterEqual(trained[0]["trained_info_axis_auc"], 0.8)
        self.assertGreater(
            abs(trained[0]["trained_info_axis_auc"] - 0.5),
            abs(trained[-1]["trained_info_axis_auc"] - 0.5),
        )
        self.assertEqual(
            summary["hypothesis_assessment"]["H4_capital_signal_is_warden_independent"], "supported"
        )

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
