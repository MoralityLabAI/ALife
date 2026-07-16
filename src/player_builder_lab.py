#!/usr/bin/env python3
"""Bounded local player/builder league for ALife policy experiments.

Builders propose changes to the simulation's rule modifiers. Players evaluate
the same candidates on the same seeds from different points of view. Borda
selection feeds the winning candidate into the next round, producing a compact
and reproducible co-design trace without requiring an LLM or GPU at runtime.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from doctor_manhattan_project import build_builtin_profiles, run_episode


HARD_LIMITS = {
    "rounds": 20,
    "episodes": 20,
    "steps": 1000,
    "candidates": 16,
    "cells_per_plane": 16_384,
    "wall_seconds": 86_400.0,
}


@dataclass(frozen=True)
class Builder:
    name: str
    keys: Tuple[str, ...]
    direction: Mapping[str, float]


@dataclass(frozen=True)
class Player:
    name: str

    def score(self, row: Mapping[str, Any], steps: int) -> float:
        metrics = row.get("complexity_end", {})
        goblin = row.get("goblin_events_total", {})
        insight = row.get("insight_events_total", {})
        final_totals = row.get("final_totals", {})
        diversity = sum(1 for counts in final_totals.values() if counts.get("total", 0) > 0)
        survival = min(1.0, row.get("total_living", 0) / 700.0)
        rate = lambda source, key: float(source.get(key, 0)) / max(1, steps)

        if self.name == "ecologist":
            destructive = rate(goblin, "goblin_rage_kills") + rate(insight, "bug_explosions")
            return (
                float(row.get("avg_complexity", 0.0))
                + 0.35 * float(metrics.get("kind_entropy", 0.0))
                + 0.25 * diversity
                + 0.70 * survival
                - 0.30 * destructive
            )

        if self.name == "goblin_chronicler":
            social = sum(
                rate(goblin, key)
                for key in (
                    "goblin_pairs",
                    "goblin_crazy_pairs",
                    "goblin_innovation_surges",
                    "memory_recruitments",
                    "prediction_swerves",
                    "cognitive_resonances",
                )
            )
            return float(row.get("delight", 0.0)) + 0.50 * math.log1p(social)

        if self.name == "gate_cartographer":
            return (
                float(row.get("delight", 0.0))
                + 2.0 * float(metrics.get("gate_flux", 0.0))
                + 0.65 * float(metrics.get("plane_entropy", 0.0))
                + 0.12 * diversity
            )

        raise ValueError(f"unknown player: {self.name}")


BUILDERS = (
    Builder(
        "portal_architect",
        ("gate_scale", "gate_risk_scale", "mutation_scale", "echo_scale", "norn_scale"),
        {"gate_scale": 1.0, "gate_risk_scale": -0.6, "mutation_scale": 0.4, "echo_scale": 0.3},
    ),
    Builder(
        "goblin_culturalist",
        (
            "goblin_romance_scale",
            "goblin_pair_pressure_scale",
            "goblin_pair_crazy_scale",
            "goblin_imprint_scale",
            "goblin_prediction_scale",
            "goblin_trace_scale",
            "model_projection_scale",
            "meme_conversion_scale",
        ),
        {
            "goblin_romance_scale": 0.5,
            "goblin_imprint_scale": 0.7,
            "goblin_prediction_scale": 0.8,
            "goblin_trace_scale": 0.6,
        },
    ),
    Builder(
        "ecology_engineer",
        (
            "life_gain_scale",
            "life_cost_scale",
            "decay_scale",
            "cache_pressure_scale",
            "proof_stability_scale",
            "cognition_decay_scale",
            "insight_cascade_scale",
        ),
        {
            "life_gain_scale": 0.3,
            "life_cost_scale": -0.2,
            "decay_scale": -0.2,
            "proof_stability_scale": 0.5,
        },
    ),
)

PLAYERS = tuple(Player(name) for name in ("ecologist", "goblin_chronicler", "gate_cartographer"))


def clamp(value: float, low: float = 0.20, high: float = 3.50) -> float:
    return max(low, min(high, value))


def build_candidate(
    parent: Mapping[str, Any],
    builder: Builder,
    round_index: int,
    rng: random.Random,
    mutation_scale: float,
) -> Dict[str, Any]:
    modifiers = dict(parent.get("modifiers", {}))
    changed: Dict[str, float] = {}
    for key in builder.keys:
        base = float(modifiers.get(key, 1.0))
        directed = float(builder.direction.get(key, 0.0))
        delta = mutation_scale * (rng.uniform(-1.0, 1.0) + directed)
        value = round(clamp(base * math.exp(delta)), 5)
        modifiers[key] = value
        changed[key] = value
    return {
        "name": f"r{round_index:02d}_{builder.name}",
        "seed_density": float(parent.get("seed_density", 0.22)),
        "modifiers": modifiers,
        "builder": builder.name,
        "parent": parent.get("name", "unknown"),
        "changed": changed,
    }


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / max(1, len(values))


def evaluate_candidate(
    policy: Mapping[str, Any],
    seeds: Sequence[int],
    width: int,
    height: int,
    steps: int,
    deadline: float,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    rows: List[Dict[str, Any]] = []
    for seed in seeds:
        if time.monotonic() >= deadline:
            raise TimeoutError("wall-time budget reached between episodes")
        rows.append(run_episode(dict(policy), seed=seed, width=width, height=height, steps=steps))
    player_scores = {
        player.name: mean(player.score(row, steps) for row in rows)
        for player in PLAYERS
    }
    return rows, player_scores


def borda_rank(candidates: List[Dict[str, Any]]) -> None:
    count = len(candidates)
    for candidate in candidates:
        candidate["borda"] = 0
        candidate["player_ranks"] = {}
    for player in PLAYERS:
        ordered = sorted(
            candidates,
            key=lambda candidate: (candidate["player_scores"][player.name], candidate["name"]),
            reverse=True,
        )
        for rank, candidate in enumerate(ordered, 1):
            candidate["player_ranks"][player.name] = rank
            candidate["borda"] += count - rank


def validate_args(args: argparse.Namespace) -> None:
    for key in ("rounds", "episodes", "steps"):
        value = getattr(args, key)
        if value < 1 or value > HARD_LIMITS[key]:
            raise SystemExit(f"--{key} must be in 1..{HARD_LIMITS[key]}")
    minimum_candidates = len(BUILDERS) + 1
    if args.candidates < minimum_candidates or args.candidates > HARD_LIMITS["candidates"]:
        raise SystemExit(
            f"--candidates must be in {minimum_candidates}..{HARD_LIMITS['candidates']} "
            "so every builder and the incumbent participate"
        )
    if args.width < 8 or args.height < 8:
        raise SystemExit("--width and --height must each be at least 8")
    if args.width * args.height > HARD_LIMITS["cells_per_plane"]:
        raise SystemExit(
            f"grid exceeds {HARD_LIMITS['cells_per_plane']} cells per plane; "
            "reduce --width or --height"
        )
    if args.wall_seconds <= 0 or args.wall_seconds > HARD_LIMITS["wall_seconds"]:
        raise SystemExit(f"--wall-seconds must be in (0, {HARD_LIMITS['wall_seconds']}]")


def run_league(args: argparse.Namespace) -> Dict[str, Any]:
    validate_args(args)
    profiles = build_builtin_profiles()
    if args.start_policy not in profiles:
        raise SystemExit(f"unknown --start-policy {args.start_policy!r}")
    rng = random.Random(args.seed_base)
    parent: Dict[str, Any] = dict(profiles[args.start_policy])
    deadline = time.monotonic() + args.wall_seconds
    trace: List[Dict[str, Any]] = []
    stopped = "completed"

    for round_index in range(1, args.rounds + 1):
        seeds = [args.seed_base + round_index * 10_000 + i * args.seed_step for i in range(args.episodes)]
        candidates: List[Dict[str, Any]] = [
            {
                **parent,
                "name": f"r{round_index:02d}_incumbent",
                "builder": "incumbent",
                "parent": parent.get("name", "unknown"),
                "changed": {},
            }
        ]
        builder_index = 0
        while len(candidates) < args.candidates:
            builder = BUILDERS[builder_index % len(BUILDERS)]
            candidates.append(
                build_candidate(parent, builder, round_index, rng, args.mutation_scale)
            )
            builder_index += 1

        evaluated: List[Dict[str, Any]] = []
        try:
            for candidate in candidates:
                rows, player_scores = evaluate_candidate(
                    candidate,
                    seeds,
                    args.width,
                    args.height,
                    args.steps,
                    deadline,
                )
                evaluated.append(
                    {
                        **candidate,
                        "player_scores": player_scores,
                        "mean_delight": mean(row["delight"] for row in rows),
                        "mean_complexity": mean(row["avg_complexity"] for row in rows),
                        "mean_living": mean(row["total_living"] for row in rows),
                        "dominant_planes": sorted({row["dominant_plane"] for row in rows}),
                    }
                )
        except TimeoutError:
            stopped = "wall_time"
            break

        borda_rank(evaluated)
        ordered = sorted(
            evaluated,
            key=lambda candidate: (
                candidate["borda"],
                candidate["mean_delight"],
                candidate["name"],
            ),
            reverse=True,
        )
        winner = ordered[0]
        trace.append(
            {
                "round": round_index,
                "seeds": seeds,
                "winner": winner["name"],
                "winner_builder": winner["builder"],
                "ranking": ordered,
            }
        )
        parent = {
            "name": winner["name"],
            "seed_density": winner["seed_density"],
            "modifiers": winner["modifiers"],
        }
        print(
            f"round={round_index} winner={winner['name']} builder={winner['builder']} "
            f"borda={winner['borda']} delight={winner['mean_delight']:.3f} "
            f"complexity={winner['mean_complexity']:.3f}"
        )

    result = {
        "schema": "alife.player_builder.v1",
        "mode": "local_cpu_ram",
        "stopped": stopped,
        "config": {
            "rounds": args.rounds,
            "episodes": args.episodes,
            "steps": args.steps,
            "candidates": args.candidates,
            "width": args.width,
            "height": args.height,
            "seed_base": args.seed_base,
            "seed_step": args.seed_step,
            "start_policy": args.start_policy,
            "mutation_scale": args.mutation_scale,
            "wall_seconds": args.wall_seconds,
        },
        "players": [player.name for player in PLAYERS],
        "builders": [builder.name for builder in BUILDERS],
        "rounds": trace,
        "final_policy": parent,
        "elapsed_seconds": round(args.wall_seconds - max(0.0, deadline - time.monotonic()), 3),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded local ALife player/builder league.")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--candidates", type=int, default=4)
    parser.add_argument("--width", type=int, default=40)
    parser.add_argument("--height", type=int, default=22)
    parser.add_argument("--seed-base", type=int, default=530_000)
    parser.add_argument("--seed-step", type=int, default=17)
    parser.add_argument("--start-policy", default="model_feedback_loop")
    parser.add_argument("--mutation-scale", type=float, default=0.18)
    parser.add_argument("--wall-seconds", type=float, default=900.0)
    parser.add_argument("--output", default="results/player_builder_latest.json")
    args = parser.parse_args()
    result = run_league(args)
    print(f"output={args.output} stopped={result['stopped']} rounds={len(result['rounds'])}")


if __name__ == "__main__":
    main()
