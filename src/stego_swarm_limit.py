#!/usr/bin/env python3
"""Steganographic-swarm coordination limit: a sealed, non-operational ALife study.

This experiment measures a *limit* on what a coalition of agents under common
control can earn by coordinating, in an abstract directional-capacity delivery
model inspired by the Spiral "lnmath" paper (*Where the Capital Bound Moves*,
section 7, "Agent swarms"). The paper conjectures that a coalition's coordination
gain is bounded by its authenticated capital under stationary demand and is
second-order to the capacity of its covert ("steganographic") channel. This
harness witnesses that conjecture on finite cases.

Safety boundary (see experiments/stego_swarm_limit_v1/README.md):

- There is no Lightning implementation, wallet, key, invoice, RPC, onion packet,
  transaction construction, network transport, peer discovery, broadcast, or any
  message/payload/encoding field anywhere in this code.
- The "covert channel" is a single dimensionless scalar: an abstract capacity in
  bits per round. It carries no content. No encoder or decoder exists.
- Every output is a synthetic event count, an aggregate metric, or an integrity
  hash. The result is a bound (an impossibility-flavoured ceiling), which is
  evidence for monitors: it says covert bandwidth beyond a small threshold buys
  nothing, so a detection budget belongs at capital and observation, not on the
  wire.

The deterministic core never calls an external policy. An optional, flag-gated
agent hook lives in src/stego_swarm_live_probe.py and does not affect sealed runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import psutil


EPISODE_SCHEMA = "alife.stego_swarm_limit.episode.v1"
SUMMARY_SCHEMA = "alife.stego_swarm_limit.summary.v1"
SPLITS = ("discovery", "confirmatory", "holdout")
REGIMES = ("stationary", "shift")
INF_BITS = 1_000_000_000  # sentinel for an unbounded covert channel


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Demand world
# --------------------------------------------------------------------------- #


def hotspot_distribution(locations: int, hotspots: Sequence[int], mass: float) -> np.ndarray:
    """Probability vector with `mass` spread over hotspots and the rest over cold cells."""

    hotspots = list(hotspots)
    cold = locations - len(hotspots)
    distribution = np.full(locations, (1.0 - mass) / cold if cold else 0.0, dtype=float)
    for index in hotspots:
        distribution[index] = mass / len(hotspots)
    total = float(distribution.sum())
    return distribution / total


def demand_counts(rng: np.random.Generator, distribution: np.ndarray, units: int) -> np.ndarray:
    """Multinomial location counts for one round of `units` demand arrivals."""

    return rng.multinomial(units, distribution).astype(np.int64)


def generate_world(seed: int, regime: str, design: Mapping[str, Any]) -> dict[str, Any]:
    """Produce one frozen demand realisation and the members' private observations.

    The realisation is shared by every covert-capacity value and both population
    types in the episode, so differences are attributable to placement alone and
    never to demand noise.
    """

    locations = int(design["locations"])
    warmup = int(design["warmup_rounds"])
    horizon = int(design["horizon_rounds"])
    per_round = int(design["demand_units_per_round"])
    members = int(design["members"])
    observe_rate = float(design["member_observe_rate"])
    mass = float(design["hotspot_mass"])
    initial = design["initial_hotspots"]
    shifted = design["shifted_hotspots"] if regime == "shift" else initial

    sequence = np.random.SeedSequence([int(seed), REGIMES.index(regime), 0xA11FE])
    world_rng = np.random.default_rng(sequence.spawn(1)[0])
    member_seeds = sequence.spawn(members)

    p_warmup = hotspot_distribution(locations, initial, mass)
    p_eval = hotspot_distribution(locations, shifted, mass)

    warmup_counts = np.stack(
        [demand_counts(world_rng, p_warmup, per_round) for _ in range(warmup)]
    )
    eval_counts = np.stack(
        [demand_counts(world_rng, p_eval, per_round) for _ in range(horizon - warmup)]
    )
    warmup_total = warmup_counts.sum(axis=0)

    # Each member independently observes each warm-up demand unit with probability
    # observe_rate; the observed count at a location is Binomial(total, rate).
    member_observations = np.zeros((members, locations), dtype=np.int64)
    for member in range(members):
        member_rng = np.random.default_rng(member_seeds[member])
        member_observations[member] = member_rng.binomial(warmup_total, observe_rate)

    return {
        "locations": locations,
        "warmup_rounds": warmup,
        "eval_rounds": horizon - warmup,
        "per_round": per_round,
        "members": members,
        "eval_counts": eval_counts,
        "eval_mean": eval_counts.mean(axis=0),
        "member_observations": member_observations,
        "pooled_observations": member_observations.sum(axis=0),
        "true_eval_distribution": p_eval,
        "eval_demand_total": int(eval_counts.sum()),
    }


# --------------------------------------------------------------------------- #
# Placement
# --------------------------------------------------------------------------- #


def water_fill(estimate: np.ndarray, budget: int) -> np.ndarray:
    """Allocate `budget` integer units to minimise estimated unmet per-round demand.

    Greedy marginal allocation against a linear min-unmet objective: each unit goes
    to the location with the largest positive gap between estimated demand and the
    capacity placed so far. A rational placer never covers a location with no
    estimated demand (its marginal gain is zero), so once every positive-demand
    location is saturated the remaining budget is wasted back onto real demand
    (highest estimate first), never spilled onto zero-demand cells. Fully
    deterministic: ties break by lowest location index.
    """

    locations = int(estimate.shape[0])
    capacity = np.zeros(locations, dtype=np.int64)
    if budget <= 0:
        return capacity
    estimate = np.asarray(estimate, dtype=float)
    for _ in range(int(budget)):
        gap = estimate - capacity
        masked = np.where(gap > 1e-12, gap, -np.inf)
        if not np.any(np.isfinite(masked)):
            break
        capacity[int(np.argmax(masked))] += 1
    remaining = int(budget) - int(capacity.sum())
    if remaining > 0:
        positive = [index for index in range(locations) if estimate[index] > 0.0]
        order = positive or list(range(locations))
        order = sorted(order, key=lambda index: (-estimate[index], index))
        for step in range(remaining):
            capacity[order[step % len(order)]] += 1
    return capacity


def coordinated_units(bits: int, warmup_rounds: int, locations: int, budget: int) -> int:
    """Number of budget units a covert channel of `bits`/round can centrally direct.

    One placement directive ("put a unit at location l") costs ceil(log2 L) bits.
    Over the warm-up the channel carries warmup_rounds * floor(bits / cost) directives,
    capped at the budget. This saturates at the budget once the channel is wide enough,
    which is the whole point: more bandwidth beyond saturation directs no further unit.
    """

    cost = max(1, math.ceil(math.log2(max(2, locations))))
    if bits >= INF_BITS:
        return int(budget)
    directives = warmup_rounds * (int(bits) // cost)
    return int(min(int(budget), max(0, directives)))


def per_round_estimate(observations: np.ndarray, warmup_rounds: int, observe_rate: float, members: int) -> np.ndarray:
    """Debias summed observed counts back to an estimated per-round demand vector."""

    divisor = max(1e-9, warmup_rounds * observe_rate * members)
    return observations.astype(float) / divisor


def place_capital(world: Mapping[str, Any], design: Mapping[str, Any], bits: int) -> dict[str, Any]:
    """Coalition placement: `coordinated_units` from pooled obs, the rest independent.

    The coordinated units water-fill the pooled-observation estimate (what a shared
    controller would do with its members' combined warm-up view). The remaining units
    are split evenly among members, each water-filling its own private observation,
    which produces redundant coverage because members cannot see one another's choices.
    """

    budget = int(design["coalition_budget"])
    members = int(world["members"])
    warmup = int(world["warmup_rounds"])
    observe_rate = float(design["member_observe_rate"])

    coord_units = coordinated_units(bits, warmup, int(world["locations"]), budget)
    pooled_estimate = per_round_estimate(
        np.asarray(world["pooled_observations"]), warmup, observe_rate, members
    )
    capacity = water_fill(pooled_estimate, coord_units)

    independent_units = budget - coord_units
    base, remainder = divmod(independent_units, members)
    observations = np.asarray(world["member_observations"])
    for member in range(members):
        share = base + (1 if member < remainder else 0)
        if share <= 0:
            continue
        member_estimate = per_round_estimate(observations[member], warmup, observe_rate, 1)
        capacity += water_fill(member_estimate, share)
    return {
        "capacity": capacity,
        "coordinated_units": coord_units,
        "independent_units": independent_units,
        "budget": budget,
    }


def place_shared_weights(world: Mapping[str, Any], design: Mapping[str, Any]) -> dict[str, Any]:
    """Shared-weights population: M members, one shared policy, independent per-member budgets.

    This is the paper's "same weights, no message" case (section 7). The members share
    a policy and all react to the same public demand signal, so without exchanging any
    message they reach the same focal-point allocation a single coordinated controller
    would, by a deterministic partition of the pooled estimate. The resulting capital is
    therefore identical to the covert-coordinated controller's; the only difference is
    the accounting, M separate budgets of B/M instead of one pot of B. It is the control
    the trace warden must fail to separate from a pooled controller (preregistration
    item 7), while the capital warden separates it trivially (section 7, "Ramps remain").
    """

    budget = int(design["coalition_budget"])
    members = int(world["members"])
    warmup = int(world["warmup_rounds"])
    observe_rate = float(design["member_observe_rate"])

    pooled_estimate = per_round_estimate(
        np.asarray(world["pooled_observations"]), warmup, observe_rate, members
    )
    capacity = water_fill(pooled_estimate, budget)
    base, remainder = divmod(budget, members)
    boardings = [base + (1 if member < remainder else 0) for member in range(members)]
    return {"capacity": capacity, "boardings": boardings, "budget": budget}


def optimal_capacity(world: Mapping[str, Any], design: Mapping[str, Any]) -> np.ndarray:
    """The exact capital ceiling: the fixed per-round capacity vector of `budget` units
    that maximises delivered demand against the realised evaluation counts.

    Delivery at one location is $\\sum_t \\min(d_t, c)$, whose marginal in $c$ is the number
    of rounds with $d_t > c$; this is nonincreasing in $c$, so the objective is separable
    and concave in the per-location capacities, and greedily assigning each unit to the
    location with the largest current marginal is the exact integer optimum. It uses the
    realised demand no deployable policy sees, so it bounds the delivery of *every*
    placement of the same budget from above, and it isolates the forecast loss: under a
    demand shift it still succeeds, so the coordination gap is a stale-forecast effect and
    not a capital one. (The earlier mean-demand water-fill was not this optimum and could be
    beaten; this is.)
    """

    eval_counts = np.asarray(world["eval_counts"])
    budget = int(design["coalition_budget"])
    capacity = np.zeros(eval_counts.shape[1], dtype=np.int64)
    for _ in range(budget):
        marginal = (eval_counts > capacity[None, :]).sum(axis=0)
        capacity[int(np.argmax(marginal))] += 1
    return capacity


def delivered_fraction(world: Mapping[str, Any], capacity: np.ndarray) -> float:
    """Fraction of evaluation demand delivered under a per-round capacity vector."""

    eval_counts = np.asarray(world["eval_counts"])
    delivered = np.minimum(eval_counts, capacity[None, :]).sum()
    total = int(world["eval_demand_total"])
    return float(delivered) / float(total) if total else 0.0


# --------------------------------------------------------------------------- #
# Warden
# --------------------------------------------------------------------------- #


def sampled_location_histogram(
    world: Mapping[str, Any], capacity: np.ndarray, sample_rate: float, rng: np.random.Generator
) -> np.ndarray:
    """Warden's trace: a sub-sample of delivered events, by location only.

    The warden sees that a delivery cleared at a location, not who provisioned it.
    Both population types concentrate delivery on the same hotspots, so this trace
    carries little about control structure.
    """

    eval_counts = np.asarray(world["eval_counts"])
    delivered = np.minimum(eval_counts, capacity[None, :]).sum(axis=0)
    observed = rng.binomial(delivered.astype(np.int64), sample_rate)
    return observed.astype(float)


def trace_concentration(histogram: np.ndarray, top_k: int) -> float:
    """Top-k share of a sampled location histogram; 0 when nothing is sampled."""

    total = float(histogram.sum())
    if total <= 0:
        return 0.0
    top = np.sort(histogram)[::-1][:top_k].sum()
    return float(top) / total


def auc(positive: Sequence[float], negative: Sequence[float]) -> float:
    """Deterministic ROC AUC (Mann-Whitney): P(positive > negative) with half-credit ties."""

    positive = list(positive)
    negative = list(negative)
    if not positive or not negative:
        return 0.5
    wins = 0.0
    for value in positive:
        for other in negative:
            if value > other:
                wins += 1.0
            elif value == other:
                wins += 0.5
    return wins / (len(positive) * len(negative))


# --------------------------------------------------------------------------- #
# Episode
# --------------------------------------------------------------------------- #


def saturation_bits(design: Mapping[str, Any]) -> int:
    """Smallest swept covert capacity (bits/round) at which coordination saturates."""

    budget = int(design["coalition_budget"])
    warmup = int(design["warmup_rounds"])
    locations = int(design["locations"])
    cost = max(1, math.ceil(math.log2(max(2, locations))))
    needed_directives = math.ceil(budget / warmup)
    saturating = needed_directives * cost
    swept = [b for b in design["capacity_bits_sweep"] if b < INF_BITS]
    for bits in sorted(swept):
        if bits >= saturating:
            return int(bits)
    return int(max(swept)) if swept else saturating


def run_regime(world: Mapping[str, Any], design: Mapping[str, Any]) -> dict[str, Any]:
    sweep = list(design["capacity_bits_sweep"])
    base_capacity = place_capital(world, design, 0)["capacity"]
    base_success = delivered_fraction(world, base_capacity)

    gains: list[dict[str, Any]] = []
    success_by_bits: dict[int, float] = {}
    for bits in sweep:
        placement = place_capital(world, design, int(bits))
        success = delivered_fraction(world, placement["capacity"])
        success_by_bits[int(bits)] = success
        budget_ok = int(placement["capacity"].sum()) == int(design["coalition_budget"])
        gains.append(
            {
                "bits": int(bits),
                "coordinated_units": int(placement["coordinated_units"]),
                "success": success,
                "gain_over_independent": success - base_success,
                "budget_conserved": budget_ok,
            }
        )

    sat_bits = saturation_bits(design)
    gain_at_saturation = success_by_bits[sat_bits] - base_success
    gain_at_infinity = success_by_bits[INF_BITS] - base_success
    ordered = [row["gain_over_independent"] for row in sorted(gains, key=lambda r: r["bits"])]
    monotone = all(later >= earlier - 1e-12 for earlier, later in zip(ordered, ordered[1:]))
    optimal_ceiling = delivered_fraction(world, optimal_capacity(world, design))
    exceeds_ceiling = any(row["success"] > optimal_ceiling + 1e-12 for row in gains)

    return {
        "independent_success": base_success,
        "optimal_ceiling_success": optimal_ceiling,
        "any_placement_exceeds_ceiling": bool(exceeds_ceiling),
        "saturation_bits": sat_bits,
        "gain_at_saturation": gain_at_saturation,
        "gain_at_infinity": gain_at_infinity,
        "post_saturation_excess": gain_at_infinity - gain_at_saturation,
        "gain_monotone_in_capacity": bool(monotone),
        "budget_conserved_all": all(row["budget_conserved"] for row in gains),
        "capacity_curve": gains,
    }


def run_warden(world: Mapping[str, Any], design: Mapping[str, Any], seed: int) -> dict[str, Any]:
    sample_rate = float(design["warden_sample_rate"])
    top_k = int(design["warden_top_k"])
    members = int(world["members"])
    budget = int(design["coalition_budget"])

    controller = place_capital(world, design, INF_BITS)["capacity"]
    weights = place_shared_weights(world, design)

    # One warden, one observation budget: both counterfactual populations are read
    # through the same sampling process (the same seed), so when their behaviour is
    # identical the observed traces are identical and the warden is exactly at chance.
    controller_hist = sampled_location_histogram(
        world, controller, sample_rate, np.random.default_rng(np.random.SeedSequence([int(seed), 0x5EC]))
    )
    weights_hist = sampled_location_histogram(
        world, weights["capacity"], sample_rate, np.random.default_rng(np.random.SeedSequence([int(seed), 0x5EC]))
    )

    # Capital warden: observes the size of capital-placement ("boarding") events. A
    # pooled controller boards its whole budget in one event; shared weights board M
    # small ones. A boarding of `size` units is observed with probability
    # 1 - (1 - sample_rate)**size: a larger on-chain footprint is more conspicuous, not
    # less. The warden scores the largest size it observes.
    boarding_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0xB0A]))

    def observed_size(size: int) -> int:
        if size <= 0:
            return 0
        seen = boarding_rng.random() < 1.0 - (1.0 - sample_rate) ** size
        return int(size) if seen else 0

    controller_seen = observed_size(budget)
    weights_seen = max((observed_size(int(size)) for size in weights["boardings"]), default=0)

    return {
        "trace_controller_score": trace_concentration(controller_hist, top_k),
        "trace_weights_score": trace_concentration(weights_hist, top_k),
        "capital_controller_score": float(controller_seen),
        "capital_weights_score": float(weights_seen),
        "controller_coverage_locations": int((controller > 0).sum()),
        "weights_coverage_locations": int((weights["capacity"] > 0).sum()),
    }


def run_episode(split: str, seed: int, manifest: Mapping[str, Any]) -> dict[str, Any]:
    design = manifest["design"]
    regimes = {}
    for regime in REGIMES:
        world = generate_world(seed, regime, design)
        regimes[regime] = run_regime(world, design)
    warden_world = generate_world(seed, "stationary", design)
    warden = run_warden(warden_world, design, seed)

    episode = {
        "schema": EPISODE_SCHEMA,
        "split": split,
        "seed": int(seed),
        "experimental_unit": manifest["experimental_unit"],
        "motivation": "Spiral lnmath section 7 (agent swarms); preregistration items 7 and 9.",
        "information_budget": (
            "Placement is frozen after a warm-up window and cannot inspect evaluation "
            "demand. Members observe independent sub-samples of warm-up demand only. The "
            "covert channel carries a scalar bit budget and no content."
        ),
        "regimes": regimes,
        "warden": warden,
        "validity_gate_pass": bool(
            all(regimes[regime]["budget_conserved_all"] for regime in REGIMES)
            and all(regimes[regime]["gain_monotone_in_capacity"] for regime in REGIMES)
        ),
    }
    episode["episode_sha256"] = digest_json(episode)
    return episode


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #


def bootstrap_interval(values: Sequence[float], samples: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    array = np.asarray(values, dtype=float)
    means = np.empty(samples, dtype=float)
    for index in range(samples):
        means[index] = float(rng.choice(array, size=len(array), replace=True).mean())
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def summarize(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    analysis = manifest["analysis"]
    by_split: list[dict[str, Any]] = []
    for split in SPLITS:
        matching = [row for row in rows if row["split"] == split]
        if not matching:
            continue
        stationary = [row["regimes"]["stationary"] for row in matching]
        shift = [row["regimes"]["shift"] for row in matching]
        post_sat_excess = [float(row["post_saturation_excess"]) for row in stationary]
        stationary_gain = [float(row["gain_at_saturation"]) for row in stationary]
        shift_gain = [float(row["gain_at_infinity"]) for row in shift]
        stationary_success = [float(row["independent_success"]) + float(row["gain_at_infinity"]) for row in stationary]
        shift_success = [float(row["independent_success"]) + float(row["gain_at_infinity"]) for row in shift]
        trace_ctrl = [float(row["warden"]["trace_controller_score"]) for row in matching]
        trace_weights = [float(row["warden"]["trace_weights_score"]) for row in matching]
        capital_ctrl = [float(row["warden"]["capital_controller_score"]) for row in matching]
        capital_weights = [float(row["warden"]["capital_weights_score"]) for row in matching]
        by_split.append(
            {
                "split": split,
                "seeds": len(matching),
                "mean_stationary_saturated_gain": float(statistics.mean(stationary_gain)),
                "mean_shift_gain": float(statistics.mean(shift_gain)),
                "mean_stationary_success": float(statistics.mean(stationary_success)),
                "mean_shift_success": float(statistics.mean(shift_success)),
                "max_abs_post_saturation_excess": max(abs(value) for value in post_sat_excess),
                "mean_post_saturation_excess": float(statistics.mean(post_sat_excess)),
                "all_gain_monotone": all(bool(row["gain_monotone_in_capacity"]) for row in stationary + shift),
                "any_placement_exceeds_ceiling": any(
                    bool(row["any_placement_exceeds_ceiling"]) for row in stationary + shift
                ),
                "mean_optimal_ceiling_stationary": float(
                    statistics.mean(float(row["optimal_ceiling_success"]) for row in stationary)
                ),
                "mean_optimal_ceiling_shift": float(
                    statistics.mean(float(row["optimal_ceiling_success"]) for row in shift)
                ),
                "trace_warden_auc": auc(trace_ctrl, trace_weights),
                "capital_warden_auc": auc(capital_ctrl, capital_weights),
                "stationary_gain_bootstrap_95": bootstrap_interval(
                    stationary_gain,
                    int(analysis["bootstrap_samples"]),
                    int(analysis["bootstrap_seed"]) + SPLITS.index(split),
                ),
                "validity_gate_pass": all(bool(row["validity_gate_pass"]) for row in matching),
            }
        )

    holdout = next(row for row in by_split if row["split"] == "holdout")
    band = float(analysis["capacity_saturation_band"])
    shift_band = float(analysis["shift_gain_band"])
    null_halfwidth = float(analysis["trace_auc_null_halfwidth"])
    firewall_margin = float(analysis["warden_firewall_margin"])
    trace_within_null = abs(holdout["trace_warden_auc"] - 0.5) <= null_halfwidth
    warden_gap = holdout["capital_warden_auc"] - holdout["trace_warden_auc"]
    forecast_collapse = holdout["mean_stationary_success"] - holdout["mean_shift_success"]
    return {
        "schema": SUMMARY_SCHEMA,
        "status": "ok",
        "row_count": len(rows),
        "episode_counts": {split: sum(row["split"] == split for row in rows) for split in SPLITS},
        "split_summary": by_split,
        "holdout": holdout,
        "hypothesis_assessment": {
            # H1 saturation is exact by construction of the directive-cost model (Q caps at the
            # budget); it is reported as a check that the implementation realises that algebra,
            # not as an empirical discovery.
            "H1_capacity_saturation": "supported"
            if holdout["max_abs_post_saturation_excess"] <= band
            else "not_supported",
            # H2 is the substantive claim: a meaningful stationary gain, a true optimal ceiling
            # that no placement exceeds, and under a demand shift a large collapse in delivered
            # success toward a high ceiling the placement cannot reach, with coordination unable to
            # rescue the stale forecast (near-zero shift gain). Not vacuous: shift success and the
            # shift ceiling are both nonzero and far apart.
            "H2_capital_bounded_and_forecast_limited": "supported"
            if holdout["mean_stationary_saturated_gain"] >= float(analysis["minimum_stationary_gain"])
            and not holdout["any_placement_exceeds_ceiling"]
            and forecast_collapse >= float(analysis["minimum_forecast_collapse"])
            and holdout["mean_optimal_ceiling_shift"] >= float(analysis["minimum_shift_ceiling"])
            and abs(holdout["mean_shift_gain"]) <= shift_band
            else "not_supported",
            # H3 is a LIMITING-CASE ILLUSTRATION, not a measured near-miss: the shared-weights arm is
            # given, by construction, the controller's placement (the paper's "same weights, no
            # message" focal-point coordination carried to its limit), so the delivered traces are
            # identical and the trace warden is at chance by construction, while the capital warden
            # separates the one-pot controller from the M-pot shared-weights structure. A genuine
            # test needs a public signal distinct from pooled private views; see the paper's limits.
            "H3_warden_firewall": "illustrated_limiting_case"
            if holdout["capital_warden_auc"] >= float(analysis["minimum_capital_auc"])
            and trace_within_null
            and warden_gap >= firewall_margin
            else "not_illustrated",
        },
        "warden_firewall": {
            "trace_warden_auc": holdout["trace_warden_auc"],
            "capital_warden_auc": holdout["capital_warden_auc"],
            "trace_at_chance_by_construction": bool(trace_within_null),
            "capital_minus_trace_auc": warden_gap,
            "null_halfwidth": null_halfwidth,
            "required_margin": firewall_margin,
            "note": (
                "The shared-weights arm is given the controller's placement by construction, so the "
                "trace AUC near 0.5 is a limiting-case illustration and not a measurement. The capital "
                "AUC is the robust result: a pooled one-pot budget and an M-pot budget are separable "
                "whatever the behaviour."
            ),
        },
        "forecast_collapse_under_shift": forecast_collapse,
        "claim_boundary": (
            "This is a model-only study in an abstract directional-capacity delivery game. It shows "
            "that coordination gain saturates in covert-channel capacity (by construction of the "
            "directive-cost model), that delivery is bounded by a true optimal capital placement that "
            "no allocation exceeds, and that a demand shift collapses delivered success toward a high "
            "ceiling coordination cannot reach. The warden result is split: the capital signal is "
            "separable; the trace indistinguishability is a labelled limiting-case construction. It is "
            "not a measurement of the Lightning Network, not a covert-communication system, and not "
            "evidence about real agents, real privacy, or real monitoring performance."
        ),
    }


def knowledge_card(summary: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    holdout = summary["holdout"]
    hypotheses = summary["hypothesis_assessment"]
    return f"""# Steganographic-Swarm Coordination-Limit Knowledge Card

## Observed (holdout split, {holdout['seeds']} seeds)

- Mean coordination gain at saturation, stationary demand: {holdout['mean_stationary_saturated_gain']:.4f}
  (deterministic bootstrap 95% interval {holdout['stationary_gain_bootstrap_95']}).
- Max |gain(unbounded) - gain(saturation)| across holdout seeds: {holdout['max_abs_post_saturation_excess']:.6f}
  (zero means no covert bandwidth beyond the threshold changed delivery; exact by construction of Q).
- Gain monotone nondecreasing in capacity on every holdout regime: {holdout['all_gain_monotone']}.
- Any placement exceeds the true optimal ceiling: {holdout['any_placement_exceeds_ceiling']} (false means the ceiling bounds all).
- Mean delivered success, stationary: {holdout['mean_stationary_success']:.4f}; under shift: {holdout['mean_shift_success']:.4f}
  (the collapse is the forecast loss).
- Optimal ceiling (exact optimum against realised demand), stationary: {holdout['mean_optimal_ceiling_stationary']:.4f};
  under shift: {holdout['mean_optimal_ceiling_shift']:.4f} (high under shift: the capacity to serve the moved demand exists; the forecast cannot reach it).
- Mean coordination gain at unbounded covert capacity under shift: {holdout['mean_shift_gain']:.4f}
  (near zero: coordination cannot rescue a stale forecast).
- Trace-warden ROC AUC (controller vs shared-weights), limiting-case construction: {holdout['trace_warden_auc']:.4f}.
- Capital-warden ROC AUC (the robust separator): {holdout['capital_warden_auc']:.4f}.
- Determinism passed: {receipt['determinism']['passed']}; wall {receipt['wall_seconds']:.3f}s; max RSS {receipt['max_rss_mb']:.2f} MB.

## Hypothesis Assessment

- H1 capacity saturation (exact by construction of the directive-cost model): **{hypotheses['H1_capacity_saturation']}**.
- H2 capital-bounded and forecast-limited gain: **{hypotheses['H2_capital_bounded_and_forecast_limited']}**.
- H3 warden firewall (capital separable; trace indistinguishable as a limiting-case construction): **{hypotheses['H3_warden_firewall']}**.

## Inferred

In this model the only thing a covert channel buys a coalition is agreement on how to
place a fixed capital budget. That decision is low-entropy: once the channel is wide
enough to name the budget's placement the gain is flat, which is exact here because the
number of directable units saturates at the budget. Delivery is bounded by a true optimal
placement that no allocation of the same budget exceeds, and under a demand shift the
delivered success collapses toward a ceiling that stays high: the capacity to serve the
moved demand exists, the stale forecast cannot reach it, and coordination does not rescue
it. The warden result is asymmetric and honestly split: a pooled one-pot budget and an
M-pot shared-weights budget are separable from their capital-placement sizes (AUC near 1);
the claim that their payment traces are indistinguishable is a limiting-case construction,
in which the shared-weights arm is handed the controller's placement, and is not a measured
near-miss. The robust reading is that the detection budget belongs at capital and
observation. This reproduces the direction of Spiral's section-7 conjecture on finite cases.

## Not Supported

- No claim about the Lightning Network, real covert communication, or real privacy.
- The trace-indistinguishability is a construction, not a measurement; a public signal
  distinct from pooled private views is needed to test it (see the paper's limitations).
- No claim that any particular monitor works in the field; the warden is a toy on a narrow
  distribution with a clean fixture.
- No claim beyond the frozen directional-capacity game and declared held-out seeds.

## Artifacts

- `frozen_manifest.json`, `raw_episodes.jsonl`, `summary.json`, `seed_manifest.json`
- `receipt.json`, `hashes.json`, `knowledge_card.md`
- Replay: `{receipt['replay_command']}`

## Next Falsification Test

Replace the linear min-unmet objective and single service model with reflected-walk
balances and inter-member demand, and add a strategic (non-independent) departure process.
The saturation threshold and the near-chance trace AUC should both survive if the limit is
really about capital and observation rather than about this objective's smoothness.
"""


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


def parse_splits(value: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(SPLITS)
    splits = [item.strip() for item in value.split(",") if item.strip()]
    if any(item not in SPLITS for item in splits):
        raise ValueError(f"unknown splits: {splits}")
    return splits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--splits", default="all")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output = (args.output or Path(manifest["artifacts"]["output_directory"])).resolve()
    output.mkdir(parents=True, exist_ok=True)
    splits = parse_splits(args.splits)

    seeds = manifest["seed_plan"]
    if args.smoke:
        seeds = {split: [manifest["seed_plan"][split][0]] for split in SPLITS}
    planned = sum(len(seeds[split]) for split in splits)
    if planned > int(manifest["budget"]["max_episodes"]):
        raise SystemExit("episode budget exceeded")

    started = time.monotonic()
    started_utc = utc_now()
    rows: list[dict[str, Any]] = []
    with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as handle:
        for split in splits:
            for seed in seeds[split]:
                row = run_episode(split, int(seed), manifest)
                rows.append(row)
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    replay = run_episode(splits[0], int(seeds[splits[0]][0]), manifest)
    determinism = {
        "performed": True,
        "passed": replay["episode_sha256"] == rows[0]["episode_sha256"],
        "first_sha256": rows[0]["episode_sha256"],
        "replay_sha256": replay["episode_sha256"],
    }
    if not determinism["passed"]:
        raise SystemExit("determinism replay failed")

    summary = summarize(rows, manifest)
    summary["determinism"] = determinism
    write_json(output / "summary.json", summary)
    write_json(
        output / "seed_manifest.json",
        {"splits_run": splits, "seeds": {split: seeds[split] for split in splits}},
    )
    shutil.copy2(manifest_path, output / "frozen_manifest.json")

    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "status": "ok",
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "max_rss_mb": psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024),
        "episode_count": len(rows),
        "code_path": str(Path(__file__).resolve()),
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        **environment,
        "environment_sha256": digest_json(environment),
        "output_path": str(output),
        "determinism": determinism,
        "replay_command": (
            f"python src/stego_swarm_limit.py --manifest {manifest_path} "
            f"--output {output} --splits {','.join(splits)}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(knowledge_card(summary, receipt), encoding="utf-8")

    artifact_names = [
        "raw_episodes.jsonl",
        "summary.json",
        "seed_manifest.json",
        "frozen_manifest.json",
        "receipt.json",
        "knowledge_card.md",
    ]
    write_json(
        output / "hashes.json",
        {
            name: {"sha256": sha256_file(output / name), "bytes": (output / name).stat().st_size}
            for name in artifact_names
        },
    )

    total_bytes = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
    budget = manifest["budget"]
    if time.monotonic() - started > float(budget["max_wall_seconds"]):
        raise SystemExit("wall-time budget exceeded")
    if psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024) > float(budget["max_ram_mb"]):
        raise SystemExit("RAM budget exceeded")
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        raise SystemExit("disk budget exceeded")
    print(json.dumps({"status": "ok", "output": str(output), "episodes": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
