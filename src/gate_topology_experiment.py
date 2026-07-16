#!/usr/bin/env python3
"""Bounded causal experiment for ALife gate destination topology."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from alife import ALIVE, LifeUniverse
from gate_fixtures import BROKEN_DESTINATIONS, install_treated_gate_fixtures


CONDITIONS = ("native", "broken_feedback", "gate_off")
GATE_EVENT_KEYS = (
    "gate_checks",
    "gate_shape_matches",
    "gate_transfers",
    "gate_placements",
    "gate_target_occupied",
    "gate_rescued_placements",
    "gate_source_consumed",
    "gate_effects_suppressed",
    "gate_rejections",
)
HARD_LIMITS = {
    "steps": 500,
    "episodes": 64,
    "cells_per_plane": 8192,
    "wall_seconds": 7200.0,
    "bootstrap_samples": 50000,
}


try:
    import psutil
except ImportError:
    psutil = None


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / max(1, len(values))


def quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def hill_diversity(counts: Mapping[str, int]) -> float:
    total = sum(max(0, count) for count in counts.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * math.log(probability)
    return math.exp(entropy)


def bray_curtis(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    keys = set(left) | set(right)
    denominator = sum(left.get(key, 0) + right.get(key, 0) for key in keys)
    if denominator <= 0:
        return 0.0
    return sum(abs(left.get(key, 0) - right.get(key, 0)) for key in keys) / denominator


def parse_seeds(text: str) -> List[int]:
    seeds = [int(value.strip()) for value in text.split(",") if value.strip()]
    if not seeds:
        raise argparse.ArgumentTypeError("seed list cannot be empty")
    if len(seeds) != len(set(seeds)):
        raise argparse.ArgumentTypeError("seed list contains duplicates")
    return seeds


def topology_signature(universe: LifeUniverse) -> Dict[str, Any]:
    source_degree = Counter(gate.from_plane for gate in universe.gates)
    target_degree = Counter(gate.to_plane for gate in universe.gates)
    adjacency: Dict[str, set[str]] = defaultdict(set)
    nodes = set(universe.planes)
    for gate in universe.gates:
        adjacency[gate.from_plane].add(gate.to_plane)

    unseen = set(nodes)
    components: List[List[str]] = []
    while unseen:
        seed = min(unseen)
        forward = reachable(seed, adjacency)
        reverse_adjacency: Dict[str, set[str]] = defaultdict(set)
        for source, targets in adjacency.items():
            for target in targets:
                reverse_adjacency[target].add(source)
        backward = reachable(seed, reverse_adjacency)
        component = sorted(forward & backward)
        components.append(component)
        unseen -= set(component)

    return {
        "gate_count": len(universe.gates),
        "source_degree": dict(sorted(source_degree.items())),
        "target_degree": dict(sorted(target_degree.items())),
        "edges": sorted({(gate.from_plane, gate.to_plane) for gate in universe.gates}),
        "strong_components": sorted(components),
    }


def reachable(start: str, adjacency: Mapping[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(sorted(adjacency.get(node, set()) - seen))
    return seen


def configure_condition(universe: LifeUniverse, condition: str) -> None:
    if condition == "native":
        return
    if condition == "broken_feedback":
        found = set()
        for gate in universe.gates:
            if gate.name in BROKEN_DESTINATIONS:
                gate.to_plane = BROKEN_DESTINATIONS[gate.name]
                found.add(gate.name)
        missing = set(BROKEN_DESTINATIONS) - found
        if missing:
            raise RuntimeError(f"missing gates for broken topology: {sorted(missing)}")
        return
    if condition == "gate_off":
        for gate in universe.gates:
            # Preserve eligibility, queue, cooldown, and target-drift RNG draws
            # while suppressing cell removal and cross-plane placement effects.
            gate.effects_enabled = False
        return
    if condition in {"activation_x4", "collision_rescue", "activation_x4_collision_rescue"}:
        for gate in universe.gates:
            if condition in {"activation_x4", "activation_x4_collision_rescue"}:
                gate.chance = min(1.0, gate.chance * 4.0)
            if condition in {"collision_rescue", "activation_x4_collision_rescue"}:
                gate.placement_search_radius = 2
        return
    raise ValueError(f"unknown condition: {condition}")


def pooled_alive_counts(stats: Mapping[str, Mapping[str, int]]) -> Dict[str, int]:
    counts = {kind: 0 for kind in sorted(ALIVE)}
    for plane_counts in stats.values():
        for kind in counts:
            counts[kind] += int(plane_counts.get(kind, 0))
    return {kind: count for kind, count in counts.items() if count > 0}


def state_digest(universe: LifeUniverse, trajectory: Sequence[Mapping[str, Any]]) -> str:
    cells = []
    for plane, grid in sorted(universe.grids.items()):
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell is None:
                    continue
                cells.append(
                    {
                        "plane": plane,
                        "x": x,
                        "y": y,
                        "state": dict(sorted(vars(cell).items())),
                    }
                )
    payload = {"trajectory": trajectory, "cells": cells}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def current_rss_mb() -> float | None:
    if psutil is None:
        return None
    return psutil.Process().memory_info().rss / (1024.0 * 1024.0)


def check_runtime(deadline: float, max_ram_mb: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("wall-time budget reached")
    rss = current_rss_mb()
    if rss is not None and rss > max_ram_mb:
        raise MemoryError(f"RSS {rss:.1f} MB exceeded --max-ram-mb {max_ram_mb:.1f}")


def run_episode(
    condition: str,
    split: str,
    seed: int,
    width: int,
    height: int,
    density: float,
    steps: int,
    burn_in: int,
    deadline: float,
    max_ram_mb: float,
    gate_scale: float = 1.0,
    placement_search_radius: int = 0,
    fixture_regime: str = "none",
    fixture_single_pulse: bool = False,
) -> Dict[str, Any]:
    universe = LifeUniverse(
        width,
        height,
        seed=seed,
        seed_density=density,
        rule_modifiers={"gate_scale": gate_scale},
    )
    configure_condition(universe, condition)
    fixture_receipt = None
    if fixture_regime == "none":
        for gate in universe.gates:
            gate.placement_search_radius = max(
                gate.placement_search_radius,
                placement_search_radius,
            )
    else:
        fixture_receipt = install_treated_gate_fixtures(
            universe,
            fixture_regime,
            placement_search_radius=max(2, placement_search_radius),
        )
    trajectory: List[Dict[str, Any]] = []
    event_totals = {key: 0 for key in GATE_EVENT_KEYS}
    gate_rule_totals: Counter[str] = Counter()
    previous_counts: Dict[str, int] | None = None
    turnovers: List[float] = []
    capacity = width * height * len(universe.planes)

    for tick in range(1, steps + 1):
        check_runtime(deadline, max_ram_mb)
        stats = universe.step()
        if fixture_single_pulse and tick == 1:
            for gate in universe.gates:
                gate.chance = 0.0
        counts = pooled_alive_counts(stats)
        total = sum(counts.values())
        within = [
            hill_diversity(
                {
                    kind: int(plane_counts.get(kind, 0))
                    for kind in ALIVE
                    if plane_counts.get(kind, 0) > 0
                }
            )
            for plane_counts in stats.values()
        ]
        pooled = hill_diversity(counts)
        mean_within = mean(within)
        turnover = 0.0 if previous_counts is None else bray_curtis(previous_counts, counts)
        turnovers.append(turnover)
        previous_counts = counts
        events = universe.event_counts()
        for key in event_totals:
            event_totals[key] += int(events.get(key, 0))
        gate_rule_totals.update(
            {
                key: int(value)
                for key, value in events.items()
                if key.startswith("gate_rule_")
            }
        )
        trajectory.append(
            {
                "tick": tick,
                "total_alive": total,
                "density": total / max(1, capacity),
                "hill1": pooled,
                "mean_within_hill1": mean_within,
                "beta_hill1": pooled / mean_within if mean_within > 0 else 0.0,
                "turnover": turnover,
                "kind_counts": counts,
                "gate_events": {key: int(events.get(key, 0)) for key in GATE_EVENT_KEYS},
            }
        )

    late = [row for row in trajectory if row["tick"] > burn_in]
    if not late:
        raise ValueError("burn-in leaves no late-window observations")
    late_hill = [float(row["hill1"]) for row in late]
    persistence_threshold = math.ceil(0.80 * len(late))
    kind_presence = Counter()
    for row in late:
        for kind, count in row["kind_counts"].items():
            if count >= 3:
                kind_presence[kind] += 1
    persistent_kind_count = sum(
        1 for count in kind_presence.values() if count >= persistence_threshold
    )
    shape_matches = event_totals["gate_shape_matches"]
    transfers = event_totals["gate_transfers"]
    placements = event_totals["gate_placements"]

    return {
        "schema": "alife.gate_topology.episode.v1",
        "condition": condition,
        "split": split,
        "seed": seed,
        "width": width,
        "height": height,
        "density": density,
        "steps": steps,
        "burn_in": burn_in,
        "pd20": quantile(late_hill, 0.20),
        "late_mean_hill1": mean(late_hill),
        "persistent_kind_count": persistent_kind_count,
        "late_mean_density": mean(float(row["density"]) for row in late),
        "late_mean_within_hill1": mean(float(row["mean_within_hill1"]) for row in late),
        "late_mean_beta_hill1": mean(float(row["beta_hill1"]) for row in late),
        "late_mean_turnover": mean(float(row["turnover"]) for row in late),
        "extinct": any(int(row["total_alive"]) == 0 for row in late),
        "event_totals": event_totals,
        "gate_rule_totals": dict(sorted(gate_rule_totals.items())),
        "fixture_receipt": fixture_receipt,
        "event_rates": {
            "shape_match_per_check": shape_matches / max(1, event_totals["gate_checks"]),
            "queued_per_shape_match": transfers / max(1, shape_matches),
            "placement_per_shape_match": placements / max(1, shape_matches),
            "placement_per_queue": placements / max(1, transfers),
            "occupied_per_queue": event_totals["gate_target_occupied"] / max(1, transfers),
        },
        "trajectory": trajectory,
        "state_digest": state_digest(universe, trajectory),
        "peak_rss_mb_observed": current_rss_mb(),
    }


def bootstrap_interval(
    deltas: Sequence[float],
    samples: int,
    seed: int,
) -> Tuple[float, float]:
    if not deltas:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        means.append(mean(draw))
    return (quantile(means, 0.025), quantile(means, 0.975))


def condition_mean(
    rows: Sequence[Mapping[str, Any]],
    condition: str,
    split: str,
    field: str,
) -> float:
    return mean(
        float(row[field])
        for row in rows
        if row["condition"] == condition and row["split"] == split
    )


def paired_deltas(
    rows: Sequence[Mapping[str, Any]],
    split: str,
    field: str,
) -> List[Dict[str, float]]:
    by_key = {(row["split"], row["condition"], row["seed"]): row for row in rows}
    seeds = sorted(
        row["seed"] for row in rows
        if row["split"] == split and row["condition"] == "native"
    )
    result = []
    for seed in seeds:
        native = by_key[(split, "native", seed)]
        broken = by_key[(split, "broken_feedback", seed)]
        result.append(
            {
                "seed": seed,
                "native": float(native[field]),
                "broken_feedback": float(broken[field]),
                "delta": float(native[field]) - float(broken[field]),
            }
        )
    return result


def aggregate_rule_total(
    rows: Sequence[Mapping[str, Any]],
    condition: str,
    split: str,
    event: str,
    gate_names: Iterable[str],
) -> int:
    keys = {f"gate_rule_{event}::{name}" for name in gate_names}
    return sum(
        int(value)
        for row in rows
        if row["condition"] == condition and row["split"] == split
        for key, value in row.get("gate_rule_totals", {}).items()
        if key in keys
    )


def analyze(
    rows: Sequence[Mapping[str, Any]],
    bootstrap_samples: int,
    analysis_seed: int,
    min_effect: float,
    confirm_positive_fraction: float,
    holdout_positive_fraction: float,
    min_shape_matches: int,
    min_gate_placements: int,
) -> Dict[str, Any]:
    confirm = paired_deltas(rows, "confirmatory", "pd20")
    holdout = paired_deltas(rows, "holdout", "pd20")
    confirm_values = [row["delta"] for row in confirm]
    holdout_values = [row["delta"] for row in holdout]
    interval = bootstrap_interval(confirm_values, bootstrap_samples, analysis_seed)
    confirm_required = math.ceil(confirm_positive_fraction * len(confirm_values))
    holdout_required = math.ceil(holdout_positive_fraction * len(holdout_values))
    confirm_positive = sum(value > 0 for value in confirm_values)
    holdout_positive = sum(value > 0 for value in holdout_values)

    treated_gate_names = tuple(sorted(BROKEN_DESTINATIONS))
    treated_shapes_by_rule = {
        condition: {
            name: aggregate_rule_total(
                rows, condition, "confirmatory", "shape_match", (name,)
            )
            for name in treated_gate_names
        }
        for condition in ("native", "broken_feedback")
    }
    treated_placements_by_rule = {
        condition: {
            name: aggregate_rule_total(
                rows, condition, "confirmatory", "placement", (name,)
            )
            for name in treated_gate_names
        }
        for condition in ("native", "broken_feedback")
    }
    treated_shapes = {
        condition: aggregate_rule_total(
            rows, condition, "confirmatory", "shape_match", treated_gate_names
        )
        for condition in ("native", "broken_feedback")
    }
    treated_placements = {
        condition: aggregate_rule_total(
            rows, condition, "confirmatory", "placement", treated_gate_names
        )
        for condition in ("native", "broken_feedback")
    }
    native_rate = treated_placements["native"] / max(1, treated_shapes["native"])
    broken_rate = treated_placements["broken_feedback"] / max(1, treated_shapes["broken_feedback"])
    rate_midpoint = (native_rate + broken_rate) / 2.0
    rate_difference = (
        abs(native_rate - broken_rate) / rate_midpoint
        if rate_midpoint > 0
        else 0.0
    )
    all_shape_totals = {
        condition: sum(
            int(row["event_totals"]["gate_shape_matches"])
            for row in rows
            if row["condition"] == condition and row["split"] == "confirmatory"
        )
        for condition in ("native", "broken_feedback")
    }
    all_placement_totals = {
        condition: sum(
            int(row["event_totals"]["gate_placements"])
            for row in rows
            if row["condition"] == condition and row["split"] == "confirmatory"
        )
        for condition in ("native", "broken_feedback")
    }
    evidence_sufficient = (
        all(
            value >= min_shape_matches
            for condition_values in treated_shapes_by_rule.values()
            for value in condition_values.values()
        )
        and all(
            value >= min_gate_placements
            for condition_values in treated_placements_by_rule.values()
            for value in condition_values.values()
        )
    )

    native_density = condition_mean(rows, "native", "confirmatory", "late_mean_density")
    broken_density = condition_mean(rows, "broken_feedback", "confirmatory", "late_mean_density")
    native_extinctions = sum(
        bool(row["extinct"]) for row in rows
        if row["condition"] == "native" and row["split"] == "confirmatory"
    )
    broken_extinctions = sum(
        bool(row["extinct"]) for row in rows
        if row["condition"] == "broken_feedback" and row["split"] == "confirmatory"
    )
    density_guard = native_density >= 0.80 * broken_density
    extinction_guard = native_extinctions <= broken_extinctions

    complete_wiring_support = all(
        (
            evidence_sufficient,
            mean(confirm_values) >= min_effect,
            confirm_positive >= confirm_required,
            interval[0] > 0.0,
            mean(holdout_values) > 0.0,
            holdout_positive >= holdout_required,
            density_guard,
            extinction_guard,
        )
    )
    connectivity_support = complete_wiring_support and rate_difference <= 0.10

    return {
        "primary_contrast": "native - broken_feedback on PD20",
        "confirmatory": {
            "paired_rows": confirm,
            "mean_delta": mean(confirm_values),
            "positive": confirm_positive,
            "required_positive": confirm_required,
            "bootstrap_95": list(interval),
        },
        "holdout": {
            "paired_rows": holdout,
            "mean_delta": mean(holdout_values),
            "positive": holdout_positive,
            "required_positive": holdout_required,
        },
        "evidence_sufficiency": {
            "minimum_shape_matches_per_condition": min_shape_matches,
            "minimum_gate_placements_per_condition": min_gate_placements,
            "treated_gate_names": treated_gate_names,
            "confirmatory_treated_shape_matches": treated_shapes,
            "confirmatory_treated_gate_placements": treated_placements,
            "confirmatory_treated_shape_matches_by_rule": treated_shapes_by_rule,
            "confirmatory_treated_gate_placements_by_rule": treated_placements_by_rule,
            "confirmatory_all_shape_matches": all_shape_totals,
            "confirmatory_all_gate_placements": all_placement_totals,
            "passed": evidence_sufficient,
        },
        "exposure": {
            "scope": "six destination-rewired gate rules only",
            "native_placement_per_treated_shape_match": native_rate,
            "broken_placement_per_treated_shape_match": broken_rate,
            "relative_difference": rate_difference,
            "within_10_percent": rate_difference <= 0.10,
        },
        "hazard_guards": {
            "native_late_density": native_density,
            "broken_late_density": broken_density,
            "density_guard": density_guard,
            "native_extinctions": native_extinctions,
            "broken_extinctions": broken_extinctions,
            "extinction_guard": extinction_guard,
        },
        "supports_complete_wiring_effect": complete_wiring_support,
        "supports_connectivity_mechanism": connectivity_support,
    }


def write_report(
    path: Path,
    config: Mapping[str, Any],
    topology: Mapping[str, Any],
    determinism: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> None:
    confirm = analysis["confirmatory"]
    holdout = analysis["holdout"]
    sufficiency = analysis["evidence_sufficiency"]
    exposure = analysis["exposure"]
    hazards = analysis["hazard_guards"]
    observed = (
        f"Confirmatory mean native-broken PD20 delta was {confirm['mean_delta']:.4f} "
        f"with {confirm['positive']}/{len(confirm['paired_rows'])} positive seeds and "
        f"bootstrap 95% interval [{confirm['bootstrap_95'][0]:.4f}, "
        f"{confirm['bootstrap_95'][1]:.4f}]. Holdout mean delta was "
        f"{holdout['mean_delta']:.4f} with {holdout['positive']}/"
        f"{len(holdout['paired_rows'])} positive seeds."
    )
    if analysis["supports_connectivity_mechanism"]:
        inferred = (
            "The frozen result supports a connectivity-topology mechanism within this "
            "simulator and tested initialization, horizon, and world size."
        )
    elif analysis["supports_complete_wiring_effect"]:
        caveat = analysis.get(
            "connectivity_caveat",
            "Unequal successful-placement exposure blocks the narrower connectivity claim.",
        )
        inferred = (
            "The complete destination-wiring package affected persistent diversity, "
            f"but {caveat}"
        )
    else:
        inferred = (
            "The preregistered evidence threshold was not met; retain the result as a "
            "null, boundary, or underpowered finding."
        )

    text = f"""# Gate Topology Experiment

## Contract

- Claim scope: model-only.
- Experimental unit: one independently seeded four-plane episode.
- Primary contrast: native minus degree-matched broken-feedback wiring.
- Primary evidence: PD20, the 20th percentile of late-window Hill diversity.
- Gate activation scale: {config['gate_scale']}; placement-search radius: {config['placement_search_radius']}.
- Fixture regime: {config['fixture_regime']}; single pulse: {config['fixture_single_pulse']}.
- Steps: {config['steps']}; burn-in: {config['burn_in']}.
- Confirmatory seeds: {config['confirmatory_seeds']}.
- Holdout seeds: {config['holdout_seeds']}.

## Determinism

- Passed: {determinism['passed']}.
- Duplicate seeds: {determinism['seeds']}.
- Digests: {determinism['digests']}.

## Topology

- Native SCCs: {topology['native']['strong_components']}.
- Broken SCCs: {topology['broken_feedback']['strong_components']}.
- Source degree preserved: {topology['source_degree_preserved']}.
- Target degree preserved: {topology['target_degree_preserved']}.

## Observed

{observed}

- Treated-gate evidence sufficiency passed: {sufficiency['passed']}.
- Treated-gate shape matches: {sufficiency['confirmatory_treated_shape_matches']}.
- Treated-gate successful placements: {sufficiency['confirmatory_treated_gate_placements']}.
- Treated-gate placements by exact rule: {sufficiency['confirmatory_treated_gate_placements_by_rule']}.
- All-gate successful placements (diagnostic): {sufficiency['confirmatory_all_gate_placements']}.
- Successful placement exposure relative difference: {exposure['relative_difference']:.4f}.
- Density guard passed: {hazards['density_guard']}.
- Extinction guard passed: {hazards['extinction_guard']}.

## Inferred

{inferred}

## Not Supported

- Biological or lineage diversity.
- Open-ended evolution.
- Universal superiority of strongly connected graphs.
- Effects outside these gate rules, seeded motifs, heterogeneous planes, and tested horizon.
- A connectivity mechanism if placement exposure differs by more than 10%.

## Replay

    python src/gate_topology_experiment.py --output {config['output']}

## Artifacts

- episodes.jsonl: per-episode trajectories and raw gate counters.
- summary.json: frozen paired analysis and decision gates.
- determinism.json: duplicate replay receipt.
"""
    path.write_text(text, encoding="utf-8")


def validate_args(args: argparse.Namespace, conditions: Sequence[str]) -> None:
    episode_count = (len(args.confirmatory_seeds) + len(args.holdout_seeds)) * len(conditions)
    if args.steps < 20 or args.steps > HARD_LIMITS["steps"]:
        raise SystemExit(f"--steps must be in 20..{HARD_LIMITS['steps']}")
    if args.burn_in < 0 or args.burn_in >= args.steps:
        raise SystemExit("--burn-in must be >=0 and less than --steps")
    if episode_count < 4 or episode_count > HARD_LIMITS["episodes"]:
        raise SystemExit(f"substantive episode count must be in 4..{HARD_LIMITS['episodes']}")
    if args.width < 8 or args.height < 8 or args.width * args.height > HARD_LIMITS["cells_per_plane"]:
        raise SystemExit("grid is outside bounded limits")
    if not 0.0 <= args.density <= 1.0:
        raise SystemExit("--density must be in [0,1]")
    if args.wall_seconds <= 0 or args.wall_seconds > HARD_LIMITS["wall_seconds"]:
        raise SystemExit(f"--wall-seconds must be in (0,{HARD_LIMITS['wall_seconds']}]")
    if args.bootstrap_samples < 100 or args.bootstrap_samples > HARD_LIMITS["bootstrap_samples"]:
        raise SystemExit("--bootstrap-samples is outside bounded limits")
    if args.max_ram_mb < 64:
        raise SystemExit("--max-ram-mb must be at least 64")
    if not 0.0 <= args.gate_scale <= 10.0:
        raise SystemExit("--gate-scale must be in [0,10]")
    if args.placement_search_radius < 0 or args.placement_search_radius > 4:
        raise SystemExit("--placement-search-radius must be in [0,4]")
    if args.fixture_regime != "none" and (args.width < 32 or args.height < 18):
        raise SystemExit("fixture regime requires a grid of at least 32x18")
    if "native" not in conditions or "broken_feedback" not in conditions:
        raise SystemExit("conditions must include native and broken_feedback")
    if set(args.confirmatory_seeds) & set(args.holdout_seeds):
        raise SystemExit("confirmatory and holdout seeds overlap")


def main() -> None:
    parser = argparse.ArgumentParser(description="Causal ALife gate-topology experiment.")
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=18)
    parser.add_argument("--density", type=float, default=0.22)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--burn-in", type=int, default=100)
    parser.add_argument("--conditions", default="native,broken_feedback,gate_off")
    parser.add_argument("--confirmatory-seeds", type=parse_seeds, default=parse_seeds("2101,2111,2129,2141,2153,2161,2179,2203,2221,2237,2267,2293"))
    parser.add_argument("--holdout-seeds", type=parse_seeds, default=parse_seeds("9101,9127,9151,9173,9203,9239"))
    parser.add_argument("--determinism-seeds", type=parse_seeds, default=parse_seeds("101,103"))
    parser.add_argument("--determinism-steps", type=int, default=40)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--analysis-seed", type=int, default=20260712)
    parser.add_argument("--min-effect", type=float, default=0.5)
    parser.add_argument("--confirm-positive-fraction", type=float, default=0.75)
    parser.add_argument("--holdout-positive-fraction", type=float, default=2.0 / 3.0)
    parser.add_argument("--min-shape-matches", type=int, default=10)
    parser.add_argument("--min-gate-placements", type=int, default=5)
    parser.add_argument("--gate-scale", type=float, default=1.0)
    parser.add_argument("--placement-search-radius", type=int, default=0)
    parser.add_argument(
        "--fixture-regime",
        choices=("none", "native_survival", "forge_survive6"),
        default="none",
    )
    parser.add_argument("--fixture-single-pulse", action="store_true")
    parser.add_argument("--wall-seconds", type=float, default=2700.0)
    parser.add_argument("--max-ram-mb", type=float, default=1024.0)
    parser.add_argument("--output", type=Path, default=Path("results/gate_topology_v1"))
    args = parser.parse_args()

    conditions = tuple(value.strip() for value in args.conditions.split(",") if value.strip())
    unknown = set(conditions) - set(CONDITIONS)
    if unknown:
        raise SystemExit(f"unknown conditions: {sorted(unknown)}")
    validate_args(args, conditions)

    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.wall_seconds
    started = time.monotonic()

    native_topology_universe = LifeUniverse(args.width, args.height, 0, args.density)
    native_topology = topology_signature(native_topology_universe)
    broken_topology_universe = LifeUniverse(args.width, args.height, 0, args.density)
    configure_condition(broken_topology_universe, "broken_feedback")
    broken_topology = topology_signature(broken_topology_universe)
    topology = {
        "native": native_topology,
        "broken_feedback": broken_topology,
        "source_degree_preserved": native_topology["source_degree"] == broken_topology["source_degree"],
        "target_degree_preserved": native_topology["target_degree"] == broken_topology["target_degree"],
    }
    if not topology["source_degree_preserved"] or not topology["target_degree_preserved"]:
        raise RuntimeError("broken topology did not preserve gate degree sequences")

    determinism_rows = []
    for seed in args.determinism_seeds:
        first = run_episode(
            "native", "determinism", seed, args.width, args.height, args.density,
            args.determinism_steps, min(args.burn_in, args.determinism_steps - 1),
            deadline, args.max_ram_mb, args.gate_scale, args.placement_search_radius,
            args.fixture_regime, args.fixture_single_pulse,
        )
        second = run_episode(
            "native", "determinism", seed, args.width, args.height, args.density,
            args.determinism_steps, min(args.burn_in, args.determinism_steps - 1),
            deadline, args.max_ram_mb, args.gate_scale, args.placement_search_radius,
            args.fixture_regime, args.fixture_single_pulse,
        )
        determinism_rows.append(
            {
                "seed": seed,
                "first": first["state_digest"],
                "second": second["state_digest"],
                "equal": first["state_digest"] == second["state_digest"],
            }
        )
    determinism = {
        "passed": all(row["equal"] for row in determinism_rows),
        "seeds": list(args.determinism_seeds),
        "digests": determinism_rows,
    }
    (output / "determinism.json").write_text(
        json.dumps(determinism, indent=2) + "\n", encoding="utf-8"
    )
    if not determinism["passed"]:
        raise RuntimeError("determinism gate failed")

    rows: List[Dict[str, Any]] = []
    episode_path = output / "episodes.jsonl"
    with episode_path.open("w", encoding="utf-8") as handle:
        for split, seeds in (
            ("confirmatory", args.confirmatory_seeds),
            ("holdout", args.holdout_seeds),
        ):
            for seed in seeds:
                for condition in conditions:
                    row = run_episode(
                        condition, split, seed, args.width, args.height, args.density,
                        args.steps, args.burn_in, deadline, args.max_ram_mb,
                        args.gate_scale, args.placement_search_radius,
                        args.fixture_regime, args.fixture_single_pulse,
                    )
                    rows.append(row)
                    handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
                    handle.flush()
                    print(
                        f"split={split} seed={seed} condition={condition} "
                        f"pd20={row['pd20']:.3f} placements={row['event_totals']['gate_placements']} "
                        f"shape_matches={row['event_totals']['gate_shape_matches']}"
                    )

    analysis = analyze(
        rows,
        args.bootstrap_samples,
        args.analysis_seed,
        args.min_effect,
        args.confirm_positive_fraction,
        args.holdout_positive_fraction,
        args.min_shape_matches,
        args.min_gate_placements,
    )
    if args.fixture_regime != "none":
        analysis["supports_connectivity_mechanism"] = False
        analysis["connectivity_caveat"] = (
            "a fixture-conditioned pulse tests destination routing, not recurrent graph traversal."
        )
    config = {
        "output": str(output),
        "width": args.width,
        "height": args.height,
        "density": args.density,
        "steps": args.steps,
        "burn_in": args.burn_in,
        "conditions": list(conditions),
        "confirmatory_seeds": list(args.confirmatory_seeds),
        "holdout_seeds": list(args.holdout_seeds),
        "determinism_seeds": list(args.determinism_seeds),
        "bootstrap_samples": args.bootstrap_samples,
        "analysis_seed": args.analysis_seed,
        "min_effect": args.min_effect,
        "min_shape_matches": args.min_shape_matches,
        "min_gate_placements": args.min_gate_placements,
        "gate_scale": args.gate_scale,
        "placement_search_radius": args.placement_search_radius,
        "fixture_regime": args.fixture_regime,
        "fixture_single_pulse": args.fixture_single_pulse,
        "wall_seconds": args.wall_seconds,
        "max_ram_mb": args.max_ram_mb,
    }
    summary = {
        "schema": "alife.gate_topology.summary.v1",
        "claim_scope": "model_only",
        "config": config,
        "topology": topology,
        "determinism": determinism,
        "analysis": analysis,
        "episode_count": len(rows),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_mb_observed": max(
            (float(row["peak_rss_mb_observed"]) for row in rows if row["peak_rss_mb_observed"] is not None),
            default=None,
        ),
        "psutil_available": psutil is not None,
        "stop_status": "completed",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_report(output / "report.md", config, topology, determinism, analysis)
    print(
        f"output={output} episodes={len(rows)} elapsed={summary['elapsed_seconds']:.2f}s "
        f"complete_wiring_support={analysis['supports_complete_wiring_effect']} "
        f"connectivity_support={analysis['supports_connectivity_mechanism']}"
    )


if __name__ == "__main__":
    main()
