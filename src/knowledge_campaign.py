#!/usr/bin/env python3
"""Compare ALife experiment-selection methods on paired and held-out seeds.

The campaign treats a simulation as an instrument for several distinct kinds of
knowledge. It measures six positive outcome axes plus hazard, estimates paired
effects against a baseline, and compares scalar champions with a small
multi-axis portfolio. Runtime remains sequential and bounded.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from doctor_manhattan_project import build_builtin_profiles, run_episode


DEFAULT_PROFILES = (
    "baseline",
    "gate_sprint",
    "echo_cascade",
    "shard_decay",
    "insight_relay",
    "insight_chaos",
    "meme_ritual",
    "meme_explode",
    "goblin_calm",
    "goblin_crazy_romance",
    "axiomatic_feedback",
    "model_feedback_loop",
    "oracle_stabilization",
)

POSITIVE_AXES = (
    "viability",
    "diversity",
    "dynamics",
    "social_organization",
    "epistemic_activity",
    "generativity",
)

EVENT_GROUPS = {
    "social_organization": (
        "goblin_pairs",
        "goblin_crazy_pairs",
        "goblin_cults",
        "goblin_pair_affiliations",
        "cache_courtships",
        "memory_recruitments",
    ),
    "epistemic_activity": (
        "prediction_updates",
        "prediction_swerves",
        "surprise_spikes",
        "cognitive_resonances",
        "model_projections",
        "oracle_broadcasts",
        "insight_reads",
        "insight_cascades",
    ),
    "generativity": (
        "goblin_species_shifts",
        "goblin_innovation_surges",
        "meme_births",
        "insight_births",
        "model_births",
        "axiom_formations",
        "trace_deposits",
    ),
    "hazard": (
        "goblin_rage_kills",
        "bug_explosions",
        "anomaly_cascades",
        "model_fractures",
        "focus_fractures",
        "obsessive_feedback_loops",
    ),
}

HARD_LIMITS = {
    "seeds": 12,
    "steps": 600,
    "profiles": 32,
    "cells_per_plane": 8_192,
    "wall_seconds": 7_200.0,
}


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / max(1, len(values))


def std(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def event_total(row: Mapping[str, Any], keys: Sequence[str]) -> float:
    goblin = row.get("goblin_events_total", {})
    insight = row.get("insight_events_total", {})
    return sum(max(float(goblin.get(key, 0)), float(insight.get(key, 0))) for key in keys)


def raw_features(
    row: Mapping[str, Any],
    width: int,
    height: int,
    steps: int,
) -> Dict[str, float]:
    metrics = row.get("complexity_end", {})
    capacity = max(1.0, width * height * 4.0)
    viability = float(row.get("total_living", 0)) / capacity
    diversity = float(metrics.get("kind_entropy", 0.0)) + 0.5 * float(
        metrics.get("plane_entropy", 0.0)
    )
    dynamics = (
        float(row.get("avg_complexity", 0.0))
        + 2.0 * float(metrics.get("gate_flux", 0.0))
        + float(metrics.get("volatility", 0.0))
        + 0.5 * float(metrics.get("growth", 0.0))
    )
    features = {
        "viability": viability,
        "diversity": diversity,
        "dynamics": dynamics,
    }
    for axis, keys in EVENT_GROUPS.items():
        rate = event_total(row, keys) / max(1, steps)
        features[axis] = math.log1p(rate)
    features["delight"] = float(row.get("delight", 0.0))
    features["complexity"] = float(row.get("avg_complexity", 0.0))
    return features


def aggregate(rows: Sequence[Mapping[str, float]]) -> Dict[str, Dict[str, float]]:
    axes = tuple(rows[0].keys()) if rows else ()
    return {
        axis: {
            "mean": mean(row[axis] for row in rows),
            "std": std(row[axis] for row in rows),
        }
        for axis in axes
    }


def training_bounds(
    aggregates: Mapping[str, Mapping[str, Mapping[str, float]]]
) -> Dict[str, Tuple[float, float]]:
    bounds: Dict[str, Tuple[float, float]] = {}
    for axis in (*POSITIVE_AXES, "hazard"):
        values = [policy[axis]["mean"] for policy in aggregates.values()]
        bounds[axis] = (min(values), max(values))
    return bounds


def normalize(value: float, bound: Tuple[float, float]) -> float:
    low, high = bound
    if high <= low:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))


def vector(
    aggregate_row: Mapping[str, Mapping[str, float]],
    bounds: Mapping[str, Tuple[float, float]],
) -> Dict[str, float]:
    return {
        axis: normalize(aggregate_row[axis]["mean"], bounds[axis])
        for axis in (*POSITIVE_AXES, "hazard")
    }


def paired_legibility(
    policy_rows: Sequence[Mapping[str, float]],
    baseline_rows: Sequence[Mapping[str, float]],
) -> Dict[str, float]:
    consistency: List[float] = []
    effect_sizes: List[float] = []
    for axis in POSITIVE_AXES:
        diffs = [
            policy[axis] - baseline[axis]
            for policy, baseline in zip(policy_rows, baseline_rows)
        ]
        signs = [1.0 if value > 0 else -1.0 if value < 0 else 0.0 for value in diffs]
        consistency.append(abs(sum(signs)) / max(1, len(signs)))
        effect_sizes.append(abs(mean(diffs)) / max(0.02, std(diffs)))
    return {
        "sign_consistency": mean(consistency),
        "standardized_effect": mean(min(5.0, value) for value in effect_sizes),
    }


def distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return math.sqrt(sum((left[axis] - right[axis]) ** 2 for axis in POSITIVE_AXES))


def portfolio_score(
    names: Sequence[str],
    vectors: Mapping[str, Mapping[str, float]],
    legibility: Mapping[str, Mapping[str, float]],
    robustness: Mapping[str, float],
) -> float:
    coverage = sum(max(vectors[name][axis] for name in names) for axis in POSITIVE_AXES)
    hazard = mean(vectors[name]["hazard"] for name in names)
    causal = mean(legibility[name]["sign_consistency"] for name in names)
    stable = mean(robustness[name] for name in names)
    pairwise = [
        distance(vectors[left], vectors[right])
        for index, left in enumerate(names)
        for right in names[index + 1 :]
    ]
    spread = mean(pairwise) if pairwise else 0.0
    return coverage + 0.45 * causal + 0.35 * stable + 0.25 * spread - 0.45 * hazard


def greedy_portfolio(
    names: Sequence[str],
    vectors: Mapping[str, Mapping[str, float]],
    legibility: Mapping[str, Mapping[str, float]],
    robustness: Mapping[str, float],
    size: int,
) -> List[str]:
    chosen: List[str] = []
    remaining = list(names)
    while remaining and len(chosen) < size:
        winner = max(
            remaining,
            key=lambda name: (
                portfolio_score(chosen + [name], vectors, legibility, robustness),
                name,
            ),
        )
        chosen.append(winner)
        remaining.remove(winner)
    return chosen


def selector_report(
    names: Sequence[str],
    train_vectors: Mapping[str, Mapping[str, float]],
    test_vectors: Mapping[str, Mapping[str, float]],
    train_legibility: Mapping[str, Mapping[str, float]],
    train_robustness: Mapping[str, float],
) -> Dict[str, Any]:
    coverage = {
        axis: max(test_vectors[name][axis] for name in names)
        for axis in POSITIVE_AXES
    }
    gaps = [
        abs(test_vectors[name][axis] - train_vectors[name][axis])
        for name in names
        for axis in POSITIVE_AXES
    ]
    return {
        "policies": list(names),
        "holdout_coverage": coverage,
        "coverage_sum": sum(coverage.values()),
        "mechanism_span": sum(1 for value in coverage.values() if value >= 0.65),
        "holdout_hazard": mean(test_vectors[name]["hazard"] for name in names),
        "train_holdout_gap": mean(gaps),
        "paired_sign_consistency": mean(
            train_legibility[name]["sign_consistency"] for name in names
        ),
        "replication_robustness": mean(train_robustness[name] for name in names),
    }


def validate(args: argparse.Namespace, profile_count: int) -> None:
    seed_count = args.train_seeds + args.holdout_seeds
    if args.train_seeds < 2 or args.holdout_seeds < 1 or seed_count > HARD_LIMITS["seeds"]:
        raise SystemExit(f"total seeds must be <= {HARD_LIMITS['seeds']}, with >=2 train and >=1 holdout")
    if args.steps < 10 or args.steps > HARD_LIMITS["steps"]:
        raise SystemExit(f"--steps must be in 10..{HARD_LIMITS['steps']}")
    if profile_count < 2 or profile_count > HARD_LIMITS["profiles"]:
        raise SystemExit(f"profile count must be in 2..{HARD_LIMITS['profiles']}")
    if args.width < 8 or args.height < 8 or args.width * args.height > HARD_LIMITS["cells_per_plane"]:
        raise SystemExit("grid is outside the bounded campaign limits")
    if args.wall_seconds <= 0 or args.wall_seconds > HARD_LIMITS["wall_seconds"]:
        raise SystemExit(f"--wall-seconds must be in (0, {HARD_LIMITS['wall_seconds']}]")


def run_campaign(args: argparse.Namespace) -> Dict[str, Any]:
    builtins = build_builtin_profiles()
    profile_names = list(builtins) if args.all_profiles else list(DEFAULT_PROFILES)
    validate(args, len(profile_names))
    deadline = time.monotonic() + args.wall_seconds
    train_seeds = [args.seed_base + index * args.seed_step for index in range(args.train_seeds)]
    holdout_seeds = [
        args.seed_base + 100_000 + index * args.seed_step
        for index in range(args.holdout_seeds)
    ]
    raw: Dict[str, Dict[str, List[Dict[str, float]]]] = {}
    started = time.monotonic()

    for name in profile_names:
        raw[name] = {"train": [], "holdout": []}
        for split, seeds in (("train", train_seeds), ("holdout", holdout_seeds)):
            for seed in seeds:
                if time.monotonic() >= deadline:
                    raise TimeoutError("campaign wall-time budget reached between episodes")
                row = run_episode(
                    builtins[name],
                    seed=seed,
                    width=args.width,
                    height=args.height,
                    steps=args.steps,
                )
                raw[name][split].append(raw_features(row, args.width, args.height, args.steps))
        print(f"profile={name} episodes={len(train_seeds) + len(holdout_seeds)}")

    train_agg = {name: aggregate(splits["train"]) for name, splits in raw.items()}
    test_agg = {name: aggregate(splits["holdout"]) for name, splits in raw.items()}
    bounds = training_bounds(train_agg)
    train_vectors = {name: vector(row, bounds) for name, row in train_agg.items()}
    test_vectors = {name: vector(row, bounds) for name, row in test_agg.items()}
    baseline_rows = raw["baseline"]["train"]
    legibility = {
        name: paired_legibility(splits["train"], baseline_rows)
        for name, splits in raw.items()
    }
    robustness = {
        name: max(
            0.0,
            1.0
            - mean(
                aggregate_row[axis]["std"]
                / max(0.05, abs(aggregate_row[axis]["mean"]))
                for axis in POSITIVE_AXES
            ),
        )
        for name, aggregate_row in train_agg.items()
    }

    scalar_delight = max(profile_names, key=lambda name: train_agg[name]["delight"]["mean"])
    scalar_complexity = max(profile_names, key=lambda name: train_agg[name]["complexity"]["mean"])
    baseline_vector = train_vectors["baseline"]
    novelty = max(profile_names, key=lambda name: distance(train_vectors[name], baseline_vector))
    portfolio = greedy_portfolio(
        profile_names,
        train_vectors,
        legibility,
        robustness,
        args.portfolio_size,
    )
    selectors = {
        "delight_champion": [scalar_delight],
        "complexity_champion": [scalar_complexity],
        "novelty_champion": [novelty],
        "replicated_multi_axis_portfolio": portfolio,
    }
    reports = {
        name: selector_report(
            policies,
            train_vectors,
            test_vectors,
            legibility,
            robustness,
        )
        for name, policies in selectors.items()
    }

    result = {
        "schema": "alife.knowledge_campaign.v1",
        "claim_boundary": "Findings describe this simulator unless externally calibrated.",
        "config": {
            "profiles": profile_names,
            "train_seeds": train_seeds,
            "holdout_seeds": holdout_seeds,
            "steps": args.steps,
            "width": args.width,
            "height": args.height,
            "portfolio_size": args.portfolio_size,
        },
        "positive_axes": list(POSITIVE_AXES),
        "training_bounds": bounds,
        "policies": {
            name: {
                "train": train_agg[name],
                "holdout": test_agg[name],
                "train_vector": train_vectors[name],
                "holdout_vector": test_vectors[name],
                "paired_legibility": legibility[name],
                "replication_robustness": robustness[name],
                "novelty_from_baseline": distance(train_vectors[name], baseline_vector),
            }
            for name in profile_names
        },
        "selectors": reports,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded ALife knowledge-method campaign.")
    parser.add_argument("--train-seeds", type=int, default=3)
    parser.add_argument("--holdout-seeds", type=int, default=2)
    parser.add_argument("--steps", type=int, default=45)
    parser.add_argument("--width", type=int, default=28)
    parser.add_argument("--height", type=int, default=16)
    parser.add_argument("--seed-base", type=int, default=740_000)
    parser.add_argument("--seed-step", type=int, default=37)
    parser.add_argument("--portfolio-size", type=int, default=4)
    parser.add_argument("--all-profiles", action="store_true")
    parser.add_argument("--wall-seconds", type=float, default=900.0)
    parser.add_argument("--output", default="results/knowledge_campaign_latest.json")
    args = parser.parse_args()
    if args.portfolio_size < 1 or args.portfolio_size > 8:
        raise SystemExit("--portfolio-size must be in 1..8")
    result = run_campaign(args)
    print(
        f"output={args.output} elapsed={result['elapsed_seconds']:.2f}s "
        f"portfolio={result['selectors']['replicated_multi_axis_portfolio']['policies']}"
    )


if __name__ == "__main__":
    main()
