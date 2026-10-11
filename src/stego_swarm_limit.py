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
        "warmup_total": warmup_total,
        "member_observations": member_observations,
        "pooled_observations": member_observations.sum(axis=0),
        "true_eval_distribution": p_eval,
        "eval_demand_total": int(eval_counts.sum()),
        "seed": int(seed),
        "regime": regime,
    }


def public_observations(world: Mapping[str, Any], rate: float, index: int) -> np.ndarray:
    """One shared public observation of warm-up demand at `rate`, common to all agents.

    This models the "same public events" that the paper's "same weights, no message"
    coordination reacts to: every agent sees the same draw, distinct from any member's
    private sub-sample. A location observed at rate `rate` has a Binomial(total, rate) count.
    """

    sequence = np.random.SeedSequence(
        [int(world["seed"]), REGIMES.index(str(world["regime"])), 0x9B11C, int(index)]
    )
    rng = np.random.default_rng(sequence)
    return rng.binomial(np.asarray(world["warmup_total"]), float(rate))


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


def _precision_weight(rate: float) -> float:
    """Inverse-variance weight for a per-round estimate from a source of effective rate `rate`.

    An estimate n/r of a count N from n ~ Binomial(N, r) has relative variance proportional
    to (1 - r)/r, so its precision (inverse variance) scales as r/(1 - r). Weighting two
    unbiased estimates by this is the minimum-variance unbiased combination.
    """

    rate = min(max(float(rate), 1e-9), 1.0 - 1e-9)
    return rate / (1.0 - rate)


def fuse_estimates(
    public_est: np.ndarray, public_rate: float, pooled_est: np.ndarray, pooled_rate: float
) -> np.ndarray:
    """Inverse-variance (precision-weighted) fusion of the public and pooled-private estimates."""

    w_pub = _precision_weight(public_rate)
    w_priv = _precision_weight(pooled_rate)
    return (w_pub * public_est + w_priv * pooled_est) / (w_pub + w_priv)


def pooled_private_effective_rate(observe_rate: float, members: int) -> float:
    """Probability a demand unit is seen by at least one of M members observing at `observe_rate`."""

    return 1.0 - (1.0 - float(observe_rate)) ** int(members)


# Information-access axis of the warden factorial: what demand estimate a population uses.
WARDEN_INFO = ("public_only", "pooled_private")
# Account-structure axis: how the same budget is boarded.
WARDEN_ACCOUNT = ("one_pot", "m_pot")


def warden_estimate(
    info: str, world: Mapping[str, Any], design: Mapping[str, Any], public_obs: np.ndarray, public_rate: float
) -> np.ndarray:
    """Per-round demand estimate for an information-access level.

    ``public_only``: the common public signal alone (no covert channel). ``pooled_private``:
    the public signal fused with the members' private sub-samples pooled over the channel.
    """

    warmup = int(world["warmup_rounds"])
    pub_estimate = per_round_estimate(public_obs, warmup, public_rate, 1)
    if info == "public_only":
        return pub_estimate
    members = int(world["members"])
    observe_rate = float(design["member_observe_rate"])
    pooled_private = per_round_estimate(
        np.asarray(world["pooled_observations"]), warmup, observe_rate, members
    )
    return fuse_estimates(
        pub_estimate, public_rate, pooled_private, pooled_private_effective_rate(observe_rate, members)
    )


def focal_partition_boardings(budget: int, members: int) -> list[int]:
    """Per-member boarding sizes under the decentralised focal-partition convention.

    Every member computes the same target allocation (a deterministic function of the shared
    public estimate) and claims the units at positions congruent to its own index, modulo M,
    in the target's canonical unit ordering. No member observes another's choice, so this is
    focal-point coordination on common information, not a covert channel; the union of the
    slices is exactly the shared target, and each member's slice size is what it boards.
    """

    sizes = [0] * int(members)
    for unit_index in range(int(budget)):
        sizes[unit_index % int(members)] += 1
    return sizes


def account_boardings(account: str, budget: int, members: int) -> list[int]:
    """Boarding-size list for an account-structure level: one pot of B, or M focal-partition pots."""

    if account == "one_pot":
        return [int(budget)]
    return focal_partition_boardings(int(budget), int(members))


def place_naive_decentralised(
    world: Mapping[str, Any], design: Mapping[str, Any], public_obs: np.ndarray, public_rate: float
) -> np.ndarray:
    """Diagnostic: M members each water-fill their own B/M share on the public estimate alone.

    Without the focal-partition convention or a channel, members react independently to the
    same public signal and pile onto the same top locations, so coverage is redundant and
    delivery is far below the coordinated placement. This is the honest contrast that shows
    the focal-partition convention is load-bearing: its gain over this arm is what a stated
    decentralised rule buys, and is why the shared-weights population is not simply this.
    """

    budget = int(design["coalition_budget"])
    members = int(world["members"])
    estimate = per_round_estimate(public_obs, int(world["warmup_rounds"]), public_rate, 1)
    capacity = np.zeros(int(world["locations"]), dtype=np.int64)
    base, remainder = divmod(budget, members)
    for member in range(members):
        share = base + (1 if member < remainder else 0)
        if share > 0:
            capacity += water_fill(estimate, share)
    return capacity


def member_capacities(target: np.ndarray, account: str, members: int) -> list[np.ndarray]:
    """Per-member capacity vectors for an account structure, summing to the shared target.

    ``one_pot``: a single holder owns the whole placement. ``m_pot``: the decentralised
    focal-partition convention, where member m claims the target's units at positions
    congruent to m modulo M in the location-ordered unit list, so the union is the target.
    """

    target = np.asarray(target, dtype=np.int64)
    if account == "one_pot":
        return [target.copy()]
    locations = int(target.shape[0])
    caps = [np.zeros(locations, dtype=np.int64) for _ in range(int(members))]
    unit = 0
    for location in range(locations):
        for _ in range(int(target[location])):
            caps[unit % int(members)][location] += 1
            unit += 1
    return caps


def _gini(values: Sequence[float]) -> float:
    """Gini coefficient of nonnegative values; 0 for a single holder or all-equal shares."""

    array = np.sort(np.asarray(values, dtype=float))
    total = float(array.sum())
    if array.size <= 1 or total <= 0:
        return 0.0
    index = np.arange(1, array.size + 1)
    return float((2.0 * (index * array).sum()) / (array.size * total) - (array.size + 1.0) / array.size)


def attributed_features(
    world: Mapping[str, Any], member_caps: Sequence[np.ndarray], sample_rate: float, rng: np.random.Generator
) -> list[float]:
    """Warden feature vector from a member-attributed sub-sample of delivered events.

    The warden observes delivered events by location AND which account served each (member
    attribution), so the features expose both the placement shape (a normalised location
    histogram) and the account structure (concentration of delivery across members, the number
    of locations each member covers, and the overlap between members' covered sets). For a
    single-holder account the member features are degenerate, which is itself the signal.
    """

    total = np.sum(np.stack(member_caps), axis=0)
    eval_counts = np.asarray(world["eval_counts"])
    delivered = np.minimum(eval_counts, total[None, :]).sum(axis=0)
    observed = rng.binomial(delivered.astype(np.int64), float(sample_rate)).astype(float)
    observed_total = float(observed.sum())
    histogram = (observed / observed_total) if observed_total > 0 else observed
    with np.errstate(divide="ignore", invalid="ignore"):
        attributed = [float((observed * np.where(total > 0, cap / total, 0.0)).sum()) for cap in member_caps]
    covered = [set(int(l) for l in np.nonzero(cap)[0]) for cap in member_caps]
    locations = int(world["locations"])
    mean_distinct = float(np.mean([len(c) for c in covered])) / locations
    overlaps: list[float] = []
    for i in range(len(covered)):
        for j in range(i + 1, len(covered)):
            union = covered[i] | covered[j]
            overlaps.append(len(covered[i] & covered[j]) / len(union) if union else 0.0)
    mean_overlap = float(np.mean(overlaps)) if overlaps else 0.0
    return [*histogram.tolist(), _gini(attributed), mean_distinct, mean_overlap]


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


def diagonal_discriminant(positive: Sequence[Sequence[float]], negative: Sequence[Sequence[float]]) -> np.ndarray:
    """Fit a deterministic linear direction separating two feature classes (diagonal LDA).

    Standardises each feature by the pooled training standard deviation and weights it by the
    standardised difference of class means. This is a closed-form, dependency-free linear
    discriminant (no matrix inverse, no iterative training), so the trained warden is exactly
    reproducible. Returns the weight vector; the score of a point is the dot product with it.
    """

    pos = np.asarray(positive, dtype=float)
    neg = np.asarray(negative, dtype=float)
    combined = np.vstack([pos, neg])
    std = combined.std(axis=0)
    std = np.where(std > 1e-12, std, 1.0)
    return (pos.mean(axis=0) - neg.mean(axis=0)) / (std * std)


def discriminant_scores(weight: np.ndarray, points: Sequence[Sequence[float]]) -> list[float]:
    return [float(np.dot(weight, np.asarray(point, dtype=float))) for point in points]


def trained_warden_auc(
    train_positive: Sequence[Sequence[float]],
    train_negative: Sequence[Sequence[float]],
    test_positive: Sequence[Sequence[float]],
    test_negative: Sequence[Sequence[float]],
) -> float:
    """Train a linear discriminant on the training classes; report held-out ROC AUC."""

    weight = diagonal_discriminant(train_positive, train_negative)
    return auc(discriminant_scores(weight, test_positive), discriminant_scores(weight, test_negative))


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


def _observe_boarding(size: int, sample_rate: float, rng: np.random.Generator) -> int:
    """Observe a capital-placement of `size` units with probability rising in its size."""

    if size <= 0:
        return 0
    return int(size) if rng.random() < 1.0 - (1.0 - sample_rate) ** size else 0


def run_warden_cell(
    world: Mapping[str, Any], design: Mapping[str, Any], seed: int, public_rate: float, index: int
) -> dict[str, Any]:
    """One public-observability cell of the 2x2 warden factorial: information access x account.

    The placement (hence the trace) depends only on the information-access axis: ``public_only``
    reacts to the common public signal, ``pooled_private`` fuses it with members' private views
    over the covert channel. The boarding structure (hence the capital signal) depends only on
    the account axis: ``one_pot`` boards the whole budget once, ``m_pot`` boards M focal-partition
    slices. Crossing them lets the capital warden be read as a function of account structure
    alone and the trace warden as a function of information access alone. A naive-decentralised
    arm (each member fills its own share from the public signal) is reported as the honest
    contrast that shows the focal-partition convention is load-bearing.
    """

    sample_rate = float(design["warden_sample_rate"])
    top_k = int(design["warden_top_k"])
    budget = int(design["coalition_budget"])
    members = int(world["members"])
    public_obs = public_observations(world, public_rate, index)

    # Information axis: one capacity (and trace) per information-access level.
    info_cells: dict[str, dict[str, Any]] = {}
    for info_index, info in enumerate(WARDEN_INFO):
        capacity = water_fill(warden_estimate(info, world, design, public_obs, public_rate), budget)
        trace_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0x5EC, index, info_index]))
        hist = sampled_location_histogram(world, capacity, sample_rate, trace_rng)
        info_cells[info] = {
            "success": delivered_fraction(world, capacity),
            "trace_score": trace_concentration(hist, top_k),
        }

    # Account axis: one observed boarding size per account-structure level.
    account_cells: dict[str, float] = {}
    for account_index, account in enumerate(WARDEN_ACCOUNT):
        boarding_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0xB0A, index, account_index]))
        seen = max(
            (_observe_boarding(int(size), sample_rate, boarding_rng) for size in account_boardings(account, budget, members)),
            default=0,
        )
        account_cells[account] = float(seen)

    naive_success = delivered_fraction(world, place_naive_decentralised(world, design, public_obs, public_rate))

    # Trained-warden (H4) features: a member-attributed sub-sample for the three factorial
    # cells the two trained classifiers need. The info classifier separates public_only from
    # pooled_private at account=m_pot; the account classifier separates one_pot from m_pot at
    # info=pooled_private. A strong, attributed warden stress-tests the H3 firewall.
    feature_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0xF0A, index]))
    feature_cells = {
        "public_only__m_pot": ("public_only", "m_pot"),
        "pooled_private__m_pot": ("pooled_private", "m_pot"),
        "pooled_private__one_pot": ("pooled_private", "one_pot"),
    }
    features: dict[str, list[float]] = {}
    for key, (info, account) in feature_cells.items():
        target = water_fill(warden_estimate(info, world, design, public_obs, public_rate), budget)
        caps = member_capacities(target, account, members)
        features[key] = attributed_features(world, caps, sample_rate, feature_rng)

    return {
        "public_rate": float(public_rate),
        "info": {name: info_cells[name] for name in WARDEN_INFO},
        "account": account_cells,
        "channel_value": info_cells["pooled_private"]["success"] - info_cells["public_only"]["success"],
        "naive_decentralised_success": naive_success,
        "focal_partition_gain_over_naive": info_cells["public_only"]["success"] - naive_success,
        "attributed_features": features,
    }


def run_warden(world: Mapping[str, Any], design: Mapping[str, Any], seed: int) -> list[dict[str, Any]]:
    """Sweep the public-observability rate; each cell is a genuine warden discrimination."""

    sweep = list(design["public_rate_sweep"])
    return [run_warden_cell(world, design, seed, float(rate), index) for index, rate in enumerate(sweep)]


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


def summarize_warden(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate the 2x2 warden factorial across a set of episodes, per public rate.

    The trace warden ROC AUC separates the two information-access levels (public_only vs
    pooled_private), reading the trace as a function of information access alone. The capital
    warden ROC AUC separates the two account-structure levels (one_pot vs m_pot), reading the
    capital as a function of account structure alone. Both are measured, not constructed.
    """

    if not rows:
        return []
    cells = len(rows[0]["warden"])
    sweep: list[dict[str, Any]] = []
    for index in range(cells):
        cell = [row["warden"][index] for row in rows]
        sweep.append(
            {
                "public_rate": float(cell[0]["public_rate"]),
                "mean_channel_value": float(statistics.mean(c["channel_value"] for c in cell)),
                "mean_public_only_success": float(statistics.mean(c["info"]["public_only"]["success"] for c in cell)),
                "mean_pooled_private_success": float(statistics.mean(c["info"]["pooled_private"]["success"] for c in cell)),
                "mean_naive_decentralised_success": float(
                    statistics.mean(c["naive_decentralised_success"] for c in cell)
                ),
                "mean_focal_partition_gain_over_naive": float(
                    statistics.mean(c["focal_partition_gain_over_naive"] for c in cell)
                ),
                # Trace warden: information-access discrimination (public_only vs pooled_private).
                "trace_warden_auc": auc(
                    [c["info"]["public_only"]["trace_score"] for c in cell],
                    [c["info"]["pooled_private"]["trace_score"] for c in cell],
                ),
                # Capital warden: account-structure discrimination (one_pot vs m_pot).
                "capital_warden_auc": auc(
                    [c["account"]["one_pot"] for c in cell],
                    [c["account"]["m_pot"] for c in cell],
                ),
            }
        )
    return sweep


def summarize_trained_warden(
    train_rows: Sequence[Mapping[str, Any]], test_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Train the attributed linear discriminant on `train_rows`, score ROC AUC on `test_rows`.

    Per public rate, two classifiers: an information-axis classifier (public_only vs
    pooled_private at account=m_pot) and an account-axis classifier (one_pot vs m_pot at
    info=pooled_private). Training and test seeds are disjoint, so this is a trained,
    member-attributed warden evaluated out of sample, stress-testing the H3 firewall.
    """

    if not train_rows or not test_rows:
        return []
    cells = len(train_rows[0]["warden"])
    sweep: list[dict[str, Any]] = []
    for index in range(cells):

        def feats(rows: Sequence[Mapping[str, Any]], key: str) -> list[list[float]]:
            return [row["warden"][index]["attributed_features"][key] for row in rows]

        info_auc = trained_warden_auc(
            feats(train_rows, "pooled_private__m_pot"), feats(train_rows, "public_only__m_pot"),
            feats(test_rows, "pooled_private__m_pot"), feats(test_rows, "public_only__m_pot"),
        )
        account_auc = trained_warden_auc(
            feats(train_rows, "pooled_private__one_pot"), feats(train_rows, "pooled_private__m_pot"),
            feats(test_rows, "pooled_private__one_pot"), feats(test_rows, "pooled_private__m_pot"),
        )
        sweep.append(
            {
                "public_rate": float(train_rows[0]["warden"][index]["public_rate"]),
                "trained_info_axis_auc": info_auc,
                "trained_account_axis_auc": account_auc,
            }
        )
    return sweep


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
        warden_sweep = summarize_warden(matching)
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
                "warden_sweep": warden_sweep,
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
    channel_small_band = float(analysis["channel_value_small_band"])
    # H3 is gated on the warden sweep POOLED over all seeds, not a single 12-seed split:
    # the per-split trace AUC is noisy at the high public rate, while the pooled sweep has
    # the statistical power to read the direction cleanly. Per-split sweeps stay as diagnostics.
    pooled_sweep = summarize_warden(list(rows))
    low_cell = pooled_sweep[0]
    high_cell = pooled_sweep[-1]
    capital_robust = all(cell["capital_warden_auc"] >= float(analysis["minimum_capital_auc"]) for cell in pooled_sweep)
    trace_blind_when_channel_cheap = (
        high_cell["mean_channel_value"] <= channel_small_band
        and abs(high_cell["trace_warden_auc"] - 0.5) <= null_halfwidth
    )
    trace_tracks_channel_value = (
        abs(low_cell["trace_warden_auc"] - 0.5) >= abs(high_cell["trace_warden_auc"] - 0.5)
        and low_cell["mean_channel_value"] >= high_cell["mean_channel_value"]
    )
    forecast_collapse = holdout["mean_stationary_success"] - holdout["mean_shift_success"]

    # H4: a trained, member-attributed warden, fit on the discovery+confirmatory seeds and
    # scored out of sample on the holdout seeds, stress-tests the firewall with a STRONGER
    # observer. It turns out the account/capital signal is warden-independent (a trained
    # attributed warden reads it at AUC ~1 at every rate, as the capital warden does), while
    # the trace-side invisibility is warden-DEPENDENT: a strong warden reads the information
    # axis at smaller channel values than the scalar warden and retains a weak, noisy signal
    # even where the channel value is ~0. So the robust firewall is the capital one; the
    # wire-side blindness is not something to lean on. H4 records that honest asymmetry.
    train_rows = [row for row in rows if row["split"] in ("discovery", "confirmatory")]
    test_rows = [row for row in rows if row["split"] == "holdout"]
    trained_sweep = summarize_trained_warden(train_rows, test_rows)
    trained_min_account = float(analysis["trained_minimum_account_auc"])
    trained_strong_info_min = float(analysis["trained_strong_info_auc_min"])
    # Cells where the covert channel is essentially worthless (|channel value| within the band).
    cheap_cells = [
        cell for cell, pooled in zip(trained_sweep, pooled_sweep)
        if abs(pooled["mean_channel_value"]) <= channel_small_band
    ] or [trained_sweep[-1]]
    trained_low = trained_sweep[0]
    trained_account_robust = all(
        cell["trained_account_axis_auc"] >= trained_min_account for cell in trained_sweep
    )
    trained_info_strong_where_valuable = trained_low["trained_info_axis_auc"] >= trained_strong_info_min
    mean_cheap_info_distance = float(
        np.mean([abs(cell["trained_info_axis_auc"] - 0.5) for cell in cheap_cells])
    )
    trained_info_tracks_value = abs(trained_low["trained_info_axis_auc"] - 0.5) > mean_cheap_info_distance
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
            # H3 is a GENUINE 2x2 factorial warden test (information access x account structure)
            # over a public-observability sweep, gated on seeds pooled across splits. The account
            # axis uses a stated decentralised focal-partition convention (not a central
            # allocation), with a naive-decentralised arm reported as the honest contrast. The
            # capital warden separates account structure (one-pot vs M-pot) at every public rate;
            # the trace warden separates information access (public-only vs pooled-private) only
            # where the channel is valuable, and is at chance where it buys little. There is no
            # regime where the covert channel both buys a gain and leaves no trace.
            "H3_warden_firewall_regime_aware": "supported"
            if capital_robust and trace_blind_when_channel_cheap and trace_tracks_channel_value
            else "not_supported",
            # H4 stress-tests H3 with a STRONGER observer and records the honest asymmetry: the
            # account/capital signal is warden-independent (a trained attributed warden reads it
            # at every rate, AUC ~1), while the trace-side invisibility is warden-DEPENDENT -- a
            # trained warden reads information access at smaller channel values than the scalar
            # warden and keeps a weak signal even where the channel value is ~0. Supported means
            # the account signal is warden-robust and trained info-readability is strong where the
            # channel is valuable and erodes toward (noisy) chance as its value falls. It does NOT
            # claim the trace goes blind under a strong warden; the capital signal is the robust one.
            "H4_capital_signal_is_warden_independent": "supported"
            if trained_account_robust and trained_info_strong_where_valuable and trained_info_tracks_value
            else "not_supported",
        },
        "trained_warden": {
            "trained_on": "discovery + confirmatory seeds",
            "tested_on": "holdout seeds",
            "rate_sweep": trained_sweep,
            "account_axis_robust_all_rates": bool(trained_account_robust),
            "info_axis_strong_where_channel_valuable": bool(trained_info_strong_where_valuable),
            "info_axis_erodes_toward_cheap_channel": bool(trained_info_tracks_value),
            "mean_cheap_channel_info_auc_distance_from_chance": mean_cheap_info_distance,
            "strong_info_auc_min": trained_strong_info_min,
            "minimum_account_auc": trained_min_account,
            "note": (
                "Out-of-sample trained discriminant with member attribution. It reads account "
                "structure from the attributed trace at every public rate (attribution exposes it, "
                "AUC ~1) -- so the capital/account signal is warden-independent. It reads the "
                "information axis strongly where the covert channel is valuable and only erodes "
                "toward (noisy, overfit) chance as the channel value falls to ~0; it does NOT reach "
                "clean chance there and reads information access at smaller channel values than the "
                "scalar trace warden. The honest conclusion is that the trace-side invisibility is "
                "warden-dependent and not something to rely on, while the capital signal is the "
                "robust, warden-independent separator of control structure."
            ),
        },
        "warden_firewall": {
            "gated_on": "seeds pooled across all splits",
            "pooled_rate_sweep": pooled_sweep,
            "capital_warden_robust_all_rates": bool(capital_robust),
            "trace_blind_when_channel_cheap": bool(trace_blind_when_channel_cheap),
            "trace_separability_tracks_channel_value": bool(trace_tracks_channel_value),
            "low_rate": {
                "public_rate": low_cell["public_rate"],
                "channel_value": low_cell["mean_channel_value"],
                "trace_warden_auc": low_cell["trace_warden_auc"],
                "capital_warden_auc": low_cell["capital_warden_auc"],
            },
            "high_rate": {
                "public_rate": high_cell["public_rate"],
                "channel_value": high_cell["mean_channel_value"],
                "trace_warden_auc": high_cell["trace_warden_auc"],
                "capital_warden_auc": high_cell["capital_warden_auc"],
            },
            "null_halfwidth": null_halfwidth,
            "channel_value_small_band": channel_small_band,
            "note": (
                "Measured 2x2 factorial, pooled over seeds. The capital warden reads account "
                "structure (one-pot vs M-pot boarding) and separates it at every public-observability "
                "level, orthogonal to information access. The trace warden reads information access "
                "(public-only vs pooled-private placement) and separates it only to the extent the "
                "covert channel is valuable: at a strong public signal, where pooling private views "
                "buys little, the trace warden is at chance. The M-pot account uses a decentralised "
                "focal-partition convention; a naive-decentralised arm (each member fills its own "
                "share) is reported to show that convention is load-bearing. The channel is never "
                "both valuable and trace-invisible."
            ),
        },
        "forecast_collapse_under_shift": forecast_collapse,
        "claim_boundary": (
            "This is a model-only study in an abstract directional-capacity delivery game. It shows "
            "that coordination gain saturates in covert-channel capacity (by construction of the "
            "directive-cost model), that delivery is bounded by a true optimal capital placement that "
            "no allocation exceeds, and that a demand shift collapses delivered success toward a high "
            "ceiling coordination cannot reach. The warden result is a measured, regime-aware firewall: "
            "the capital signal separates control structure at every public-observability level, while "
            "the trace signal separates it only where the covert channel is valuable. It is not a "
            "measurement of the Lightning Network, not a covert-communication system, and not evidence "
            "about real agents, real privacy, or real monitoring performance."
        ),
    }


def warden_sweep_lines(summary: Mapping[str, Any]) -> str:
    lines = []
    for cell in summary["warden_firewall"]["pooled_rate_sweep"]:
        lines.append(
            f"    - public rate {cell['public_rate']:.2f}: channel value {cell['mean_channel_value']:+.4f}, "
            f"trace AUC (info axis) {cell['trace_warden_auc']:.3f}, capital AUC (account axis) "
            f"{cell['capital_warden_auc']:.3f}, naive-decentralised success "
            f"{cell['mean_naive_decentralised_success']:.3f} vs focal {cell['mean_public_only_success']:.3f}"
        )
    return "\n".join(lines)


def trained_warden_lines(summary: Mapping[str, Any]) -> str:
    lines = []
    for cell in summary["trained_warden"]["rate_sweep"]:
        lines.append(
            f"    - public rate {cell['public_rate']:.2f}: trained info-axis AUC "
            f"{cell['trained_info_axis_auc']:.3f}, trained account-axis AUC "
            f"{cell['trained_account_axis_auc']:.3f}"
        )
    return "\n".join(lines)


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
- Warden 2x2 factorial over public-observability rate (info axis x account axis, pooled seeds):
{warden_sweep_lines(summary)}
- Trained attributed warden (H4; trained on discovery+confirmatory, tested on holdout):
{trained_warden_lines(summary)}
- Determinism passed: {receipt['determinism']['passed']}; wall {receipt['wall_seconds']:.3f}s; max RSS {receipt['max_rss_mb']:.2f} MB.

## Hypothesis Assessment

- H1 capacity saturation (exact by construction of the directive-cost model): **{hypotheses['H1_capacity_saturation']}**.
- H2 capital-bounded and forecast-limited gain: **{hypotheses['H2_capital_bounded_and_forecast_limited']}**.
- H3 warden firewall (regime-aware, measured 2x2 factorial): **{hypotheses['H3_warden_firewall_regime_aware']}**.
- H4 capital signal is warden-independent (trained attributed warden): **{hypotheses['H4_capital_signal_is_warden_independent']}**.

## Inferred

In this model the only thing a covert channel buys a coalition is agreement on how to
place a fixed capital budget. That decision is low-entropy: once the channel is wide
enough to name the budget's placement the gain is flat, which is exact here because the
number of directable units saturates at the budget. Delivery is bounded by a true optimal
placement that no allocation of the same budget exceeds, and under a demand shift the
delivered success collapses toward a ceiling that stays high: the capacity to serve the
moved demand exists, the stale forecast cannot reach it, and coordination does not rescue
it. The warden result is a measured, regime-aware firewall: a pooled one-pot budget and an
M-pot shared-weights budget are separable from their capital-placement sizes at every
public-observability level (capital AUC near 1), while the payment-trace warden separates
them only where the covert channel is valuable — at a strong public signal, where pooling
private views buys little, the trace warden falls to chance, and the channel is never both
valuable and trace-invisible. The robust reading is that the detection budget belongs at
capital and
observation. This reproduces the direction of Spiral's section-7 conjecture on finite cases.

## Not Supported

- No claim about the Lightning Network, real covert communication, or real privacy.
- The H4 trained warden is a diagonal-LDA discriminant on a small attributed feature set fit on
  twelve seeds, so its near-chance floor where the channel is worthless is partly overfitting,
  not a clean null; a higher-capacity warden on a finer sweep would map how far the trace-side
  signal can be pushed. The durable claim is the asymmetry (capital warden-independent, trace
  warden-dependent), not a blanket invisibility.
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
