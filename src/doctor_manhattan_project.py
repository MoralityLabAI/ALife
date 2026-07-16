#!/usr/bin/env python3
"""Episode harness for model-driven ALife exploration.

Each policy is a JSON object that defines rule modifiers. The script runs a short
bundle and returns a compact "delight" score for each policy.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List

from alife import LifeUniverse


def run_episode(
    policy: Dict[str, Any],
    seed: int,
    width: int,
    height: int,
    steps: int,
) -> Dict[str, Any]:
    universe = LifeUniverse(
        width=width,
        height=height,
        seed=seed,
        seed_density=float(policy.get("seed_density", 0.22)),
        rule_modifiers=policy.get("modifiers", {}),
    )

    complexity_series: List[float] = []
    tracked_event_keys = (
        "rituals",
        "goblin_frenzies",
        "ritual_stimuli",
        "love_spikes",
        "obsession_flares",
        "cognitive_spills",
        "insight_overloads",
        "focus_fractures",
        "obsessive_feedback_loops",
        "imprint_growths",
        "imprint_hives",
        "prediction_updates",
        "prediction_swerves",
        "surprise_spikes",
        "cognitive_resonances",
        "trace_deposits",
        "trace_decay",
        "model_births",
        "model_projections",
        "model_fractures",
        "oracle_awakenings",
        "oracle_broadcasts",
        "model_coherence_decay",
        "cache_stimuli",
        "cache_depletion",
        "cache_loyalty",
        "cache_births",
        "proof_stabilizations",
        "proof_radiance",
        "proof_cascades",
        "bug_births",
        "bug_infests",
        "bug_swarm",
        "bug_explosions",
        "goblin_loves",
        "goblin_rages",
        "goblin_rage_kills",
        "goblin_feeds",
        "goblin_conversions",
        "goblin_breeds",
        "goblin_cults",
        "goblin_cult_births",
        "goblin_cult_conversions",
        "goblin_romances",
        "goblin_species_shifts",
        "goblin_innovation_surges",
        "axiom_formations",
        "axiom_sparks",
        "axiom_decay",
        "imprint_growths",
        "imprint_hives",
        "insight_births",
        "insight_reads",
        "insight_cascades",
        "insight_stabilizations",
        "anomaly_ticks",
        "anomaly_cascades",
        "meme_births",
        "meme_broadcasts",
        "meme_attunements",
        "meme_parasites",
        "goblin_pairs",
        "goblin_romances",
        "goblin_pairing_frenzies",
        "goblin_pair_breaks",
        "goblin_crazy_pairs",
        "goblin_pair_lock_surges",
        "goblin_pair_affiliations",
        "cache_courtships",
        "memory_recruitments",
        "goblin_species_shifts",
        "goblin_innovation_surges",
    )
    # Preserve declaration order while preventing duplicate tuple entries from
    # double-counting per-tick events in the accumulated episode totals.
    tracked_event_keys = tuple(dict.fromkeys(tracked_event_keys))
    event_totals: Dict[str, int] = {key: 0 for key in tracked_event_keys}
    goblin_event_totals: Dict[str, int] = {
        key: 0
        for key in tracked_event_keys
        if key.startswith("goblin_")
        or key
        in {
            "cache_courtships",
            "memory_recruitments",
            "imprint_growths",
            "imprint_hives",
            "prediction_updates",
            "prediction_swerves",
            "surprise_spikes",
            "cognitive_resonances",
            "trace_deposits",
            "trace_decay",
        }
    }
    for _ in range(steps):
        universe.step()
        complexity_series.append(universe.last_complexity())
        events = universe.event_counts()
        for key in tracked_event_keys:
            event_totals[key] += events.get(key, 0)
        for key in goblin_event_totals:
            goblin_event_totals[key] += events.get(key, 0)

    final_stats = universe.stats()
    totals = {plane: final_stats[plane].get("total", 0) for plane in final_stats}
    total_living = sum(totals.values())
    dominant = max(final_stats.items(), key=lambda item: item[1].get("total", 0))[0]
    final_metrics = universe.latest_metrics()
    final_events = universe.event_counts()

    final_goblin_events = {
        key: final_events.get(key, 0)
        for key in (
        "goblin_loves",
        "goblin_rages",
        "goblin_rage_kills",
        "goblin_pairs",
        "goblin_romances",
        "goblin_feeds",
        "goblin_conversions",
        "goblin_breeds",
        "goblin_cults",
        "goblin_cult_births",
        "goblin_cult_conversions",
        "rituals",
        "goblin_frenzies",
        "ritual_stimuli",
        "love_spikes",
        "obsession_flares",
        "cognitive_spills",
        "insight_overloads",
        "focus_fractures",
        "obsessive_feedback_loops",
        "model_births",
        "model_projections",
        "model_fractures",
        "oracle_awakenings",
        "oracle_broadcasts",
        "model_coherence_decay",
        "cache_births",
        "cache_stimuli",
        "cache_depletion",
        "cache_loyalty",
        "proof_stabilizations",
        "proof_radiance",
        "proof_cascades",
        "bug_births",
        "bug_infests",
        "bug_swarm",
        "bug_explosions",
        "imprint_growths",
        "imprint_hives",
        "prediction_updates",
        "prediction_swerves",
        "surprise_spikes",
        "cognitive_resonances",
        "trace_deposits",
        "trace_decay",
        "cache_courtships",
        "memory_recruitments",
        )
    }
    final_insight_events = {
        key: final_events.get(key, 0)
        for key in (
            "insight_births",
            "insight_reads",
            "insight_cascades",
            "insight_stabilizations",
            "anomaly_ticks",
            "anomaly_cascades",
            "meme_births",
            "meme_broadcasts",
            "meme_attunements",
            "meme_parasites",
            "goblin_pairs",
        "goblin_romances",
        "goblin_species_shifts",
        "goblin_innovation_surges",
        "goblin_cults",
        "goblin_cult_births",
        "goblin_cult_conversions",
        "axiom_formations",
        "axiom_sparks",
        "axiom_decay",
        "rituals",
        "goblin_frenzies",
        "ritual_stimuli",
        "love_spikes",
        "obsession_flares",
        "cognitive_spills",
        "insight_overloads",
        "focus_fractures",
        "obsessive_feedback_loops",
        "model_births",
        "model_projections",
        "model_fractures",
        "oracle_awakenings",
        "oracle_broadcasts",
        "model_coherence_decay",
        "cache_stimuli",
        "cache_depletion",
        "cache_loyalty",
        "cache_births",
        "proof_stabilizations",
        "proof_radiance",
        "proof_cascades",
        "bug_births",
        "bug_infests",
        "bug_swarm",
        "bug_explosions",
        "prediction_updates",
        "prediction_swerves",
        "surprise_spikes",
        "cognitive_resonances",
        "trace_deposits",
        "trace_decay",
        "cache_courtships",
        "memory_recruitments",
        )
    }
    insight_events_total = {
        key: event_totals[key]
        for key in event_totals
        if (
            key.startswith("insight_")
            or key.startswith("anomaly_")
            or key.startswith("meme_")
            or key.startswith("goblin_cult")
            or key.startswith("imprint_")
            or key.startswith("axiom_")
            or key.startswith("goblin_frenzies")
            or key.startswith("model_")
            or key.startswith("oracle_")
            or key in {"love_spikes", "obsession_flares", "cognitive_spills", "insight_overloads", "focus_fractures", "obsessive_feedback_loops"}
            or key == "rituals"
            or key == "ritual_stimuli"
            or key.startswith("cache_")
            or key.startswith("proof_")
            or key.startswith("bug_")
            or key
            in {
                "cache_courtships",
                "memory_recruitments",
                "prediction_updates",
                "prediction_swerves",
                "surprise_spikes",
                "cognitive_resonances",
                "trace_deposits",
                "trace_decay",
            }
        )
    }
    avg_goblin_events = {
        key: total / max(1, steps)
        for key, total in goblin_event_totals.items()
    }
    avg_insight_events = {
        key: total / max(1, steps)
        for key, total in insight_events_total.items()
    }

    avg_complexity = sum(complexity_series) / max(1, len(complexity_series))
    peak_complexity = max(complexity_series) if complexity_series else 0.0
    diversity = len([plane for plane, value in totals.items() if value > 0]) / max(1, len(totals))
    gate_flux = final_metrics.get("gate_flux", 0.0)
    delight = avg_complexity + (gate_flux * 2.0) + (diversity * 0.6) + (final_metrics.get("plane_entropy", 0.0) * 0.35)

    return {
        "seed": seed,
        "policy": policy.get("name", "unnamed"),
        "total_living": total_living,
        "dominant_plane": dominant,
        "avg_complexity": avg_complexity,
        "peak_complexity": peak_complexity,
        "delight": delight,
        "goblin_events_last_tick": final_goblin_events,
        "insight_events_last_tick": final_insight_events,
        "goblin_events_total": goblin_event_totals,
        "goblin_events_per_step": avg_goblin_events,
        "insight_events_total": insight_events_total,
        "insight_events_per_step": avg_insight_events,
        "complexity_end": final_metrics,
        "final_totals": final_stats,
    }


def build_builtin_profiles() -> Dict[str, Dict[str, float]]:
    return {
        "baseline": {
            "name": "baseline",
            "seed_density": 0.22,
            "modifiers": {},
        },
        "goblin_calm": {
            "name": "goblin_calm",
            "seed_density": 0.20,
            "modifiers": {
                "goblin_love_probability_scale": 0.42,
                "goblin_feed_probability_scale": 0.55,
                "goblin_mania_gain_scale": 0.45,
                "goblin_mania_decay_scale": 1.45,
                "goblin_pressure_scale": 0.58,
                "goblin_conversion_scale": 0.52,
                "goblin_mania_attack_scale": 0.66,
            },
        },
        "goblin_wild": {
            "name": "goblin_wild",
            "seed_density": 0.24,
            "modifiers": {
                "goblin_love_probability_scale": 1.85,
                "goblin_feed_probability_scale": 1.45,
                "goblin_mania_gain_scale": 1.7,
                "goblin_mania_decay_scale": 0.55,
                "goblin_pressure_scale": 1.75,
                "goblin_conversion_scale": 1.5,
                "goblin_mania_attack_scale": 1.55,
            },
        },
        "goblin_hysteria": {
            "name": "goblin_hysteria",
            "seed_density": 0.23,
            "modifiers": {
                "goblin_love_probability_scale": 2.35,
                "goblin_feed_probability_scale": 1.55,
                "goblin_mania_gain_scale": 2.0,
                "goblin_mania_decay_scale": 0.42,
                "goblin_pressure_scale": 2.1,
                "goblin_conversion_scale": 1.7,
                "goblin_mania_attack_scale": 1.8,
            },
        },
        "insight_relay": {
            "name": "insight_relay",
            "seed_density": 0.21,
            "modifiers": {
                "goblin_pressure_scale": 0.9,
                "goblin_conversion_scale": 1.05,
                "insight_spawn_scale": 1.9,
                "insight_learn_scale": 1.5,
                "insight_decay_scale": 0.9,
                "insight_transmute_scale": 1.2,
                "insight_paradox_scale": 0.8,
                "insight_cascade_scale": 1.1,
            },
        },
        "insight_chaos": {
            "name": "insight_chaos",
            "seed_density": 0.22,
            "modifiers": {
                "goblin_pressure_scale": 1.4,
                "goblin_conversion_scale": 0.95,
                "goblin_mania_attack_scale": 1.0,
                "insight_spawn_scale": 2.6,
                "insight_learn_scale": 2.0,
                "insight_decay_scale": 1.2,
                "insight_transmute_scale": 2.0,
                "insight_paradox_scale": 1.5,
                "insight_cascade_scale": 2.1,
            },
        },
        "echo_cascade": {
            "name": "echo_cascade",
            "seed_density": 0.22,
            "modifiers": {
                "echo_scale": 1.6,
                "mutation_scale": 1.1,
                "drone_dribble_scale": 0.8,
            },
        },
        "gate_sprint": {
            "name": "gate_sprint",
            "seed_density": 0.20,
            "modifiers": {
                "gate_scale": 1.5,
                "norn_scale": 1.3,
                "shard_penalty_scale": 0.9,
            },
        },
        "shard_decay": {
            "name": "shard_decay",
            "seed_density": 0.19,
            "modifiers": {
                "shard_penalty_scale": 2.0,
                "life_cost_scale": 1.1,
                "norn_scale": 0.6,
            },
        },
        "meme_ritual": {
            "name": "meme_ritual",
            "seed_density": 0.22,
            "modifiers": {
                "meme_spawn_scale": 1.8,
                "meme_broadcast_scale": 1.7,
                "meme_conversion_scale": 1.35,
                "meme_pressure_scale": 1.4,
                "insight_spawn_scale": 1.1,
                "insight_learn_scale": 1.2,
                "goblin_pressure_scale": 0.95,
            },
        },
        "meme_explode": {
            "name": "meme_explode",
            "seed_density": 0.24,
            "modifiers": {
                "meme_spawn_scale": 2.2,
                "meme_broadcast_scale": 2.3,
                "meme_conversion_scale": 1.7,
                "insight_paradox_scale": 1.5,
                "insight_cascade_scale": 1.8,
                "goblin_mania_gain_scale": 1.3,
                "goblin_mania_attack_scale": 1.4,
            },
        },
        "goblin_species_bloom": {
            "name": "goblin_species_bloom",
            "seed_density": 0.22,
            "modifiers": {
                "goblin_romance_scale": 1.55,
                "goblin_species_romance_scale": 1.6,
                "goblin_species_carry_scale": 1.35,
                "goblin_species_mutation_scale": 1.1,
                "goblin_conversion_scale": 1.1,
                "goblin_pressure_scale": 1.05,
            },
        },
        "goblin_cults": {
            "name": "goblin_cults",
            "seed_density": 0.23,
            "modifiers": {
                "goblin_species_mutation_scale": 1.75,
                "goblin_species_romance_scale": 1.8,
                "insight_spawn_scale": 1.35,
                "insight_learn_scale": 1.3,
                "meme_spawn_scale": 1.25,
                "meme_conversion_scale": 1.4,
                "goblin_mania_gain_scale": 1.35,
                "goblin_mania_attack_scale": 1.15,
            },
        },
        "goblin_cabal": {
            "name": "goblin_cabal",
            "seed_density": 0.23,
            "modifiers": {
                "goblin_cult_scale": 1.8,
                "goblin_romance_scale": 1.3,
                "goblin_species_romance_scale": 1.4,
                "insight_spawn_scale": 1.2,
                "meme_spawn_scale": 1.25,
                "meme_conversion_scale": 1.15,
                "insight_learn_scale": 1.2,
                "goblin_mania_attack_scale": 1.05,
            },
        },
        "goblin_crazy_romance": {
            "name": "goblin_crazy_romance",
            "seed_density": 0.24,
            "modifiers": {
                "goblin_romance_scale": 2.35,
                "goblin_species_romance_scale": 2.1,
                "goblin_pair_crazy_scale": 2.8,
                "goblin_pair_pressure_scale": 1.6,
                "goblin_pairing_lock_threshold": 0.38,
                "goblin_obsession_scale": 1.65,
                "goblin_overclock_scale": 1.45,
                "goblin_overflow_scale": 1.35,
                "goblin_focus_scale": 1.5,
                "goblin_fervor_scale": 1.4,
                "goblin_pair_lock_scale": 1.3,
                "goblin_pair_lock_decay_scale": 0.55,
                "goblin_pressure_scale": 1.2,
                "goblin_feed_probability_scale": 1.1,
                "goblin_conversion_scale": 1.25,
                "goblin_mania_gain_scale": 1.35,
                "meme_conversion_scale": 1.15,
                "meme_spawn_scale": 1.12,
                "insight_spawn_scale": 1.25,
                "insight_learn_scale": 1.2,
            },
        },
        "goblin_ritual": {
            "name": "goblin_ritual",
            "seed_density": 0.23,
            "modifiers": {
                "goblin_fervor_scale": 2.2,
                "goblin_romance_scale": 1.35,
                "goblin_species_romance_scale": 1.4,
                "goblin_mania_gain_scale": 1.2,
                "goblin_pressure_scale": 1.05,
                "insight_learn_scale": 1.25,
                "meme_spawn_scale": 1.2,
                "meme_broadcast_scale": 1.2,
                "goblin_mania_attack_scale": 1.12,
            },
        },
        "axiomatic_feedback": {
            "name": "axiomatic_feedback",
            "seed_density": 0.22,
            "modifiers": {
                "goblin_cult_scale": 1.4,
                "goblin_axiom_scale": 2.0,
                "insight_spawn_scale": 1.45,
                "insight_learn_scale": 1.4,
                "insight_transmute_scale": 1.3,
                "insight_cascade_scale": 1.35,
                "meme_broadcast_scale": 1.2,
                "goblin_pressure_scale": 1.1,
            },
        },
        "model_feedback_loop": {
            "name": "model_feedback_loop",
            "seed_density": 0.23,
            "modifiers": {
                "model_projection_scale": 1.8,
                "oracle_projection_scale": 1.5,
                "cognition_decay_scale": 0.9,
                "insight_spawn_scale": 1.35,
                "insight_learn_scale": 1.45,
                "goblin_pressure_scale": 1.12,
                "meme_spawn_scale": 1.22,
                "meme_pressure_scale": 1.12,
            },
        },
        "model_obsessive_feedback": {
            "name": "model_obsessive_feedback",
            "seed_density": 0.23,
            "modifiers": {
                "model_projection_scale": 1.9,
                "oracle_projection_scale": 1.6,
                "cognition_decay_scale": 0.85,
                "insight_spawn_scale": 1.3,
                "insight_learn_scale": 1.35,
                "goblin_pressure_scale": 1.12,
                "goblin_fervor_scale": 1.2,
                "goblin_focus_scale": 1.5,
                "goblin_obsession_scale": 1.8,
                "goblin_romance_scale": 1.35,
                "meme_spawn_scale": 1.3,
                "meme_conversion_scale": 1.2,
            },
        },
        "model_obsessive_overclock": {
            "name": "model_obsessive_overclock",
            "seed_density": 0.24,
            "modifiers": {
                "model_projection_scale": 2.1,
                "oracle_projection_scale": 1.8,
                "cognition_decay_scale": 0.8,
                "insight_spawn_scale": 1.45,
                "insight_learn_scale": 1.45,
                "goblin_pressure_scale": 1.08,
                "goblin_fervor_scale": 1.15,
                "goblin_focus_scale": 1.8,
                "goblin_obsession_scale": 2.2,
                "goblin_overclock_scale": 1.6,
                "goblin_overflow_scale": 1.5,
                "meme_spawn_scale": 1.25,
                "meme_conversion_scale": 1.2,
            },
        },
        "ai_cognitive_trace": {
            "name": "ai_cognitive_trace",
            "seed_density": 0.22,
            "modifiers": {
                "goblin_prediction_scale": 1.0,
                "goblin_surprise_scale": 1.5,
                "goblin_trace_scale": 1.6,
                "goblin_imprint_scale": 1.18,
                "goblin_attention_scale": 1.12,
                "goblin_obsession_scale": 1.15,
                "insight_spawn_scale": 1.25,
                "meme_conversion_scale": 1.18,
            },
        },
        "oracle_stabilization": {
            "name": "oracle_stabilization",
            "seed_density": 0.21,
            "modifiers": {
                "model_projection_scale": 1.2,
                "oracle_projection_scale": 2.0,
                "cognition_decay_scale": 0.75,
                "insight_learn_scale": 1.2,
                "goblin_fervor_scale": 1.25,
                "goblin_pressure_scale": 0.95,
                "insight_cascade_scale": 1.2,
            },
        },
    }


def load_profiles(path: str) -> List[Dict[str, float]]:
    policies: List[Dict[str, float]] = []
    with open(path, "r", encoding="utf-8-sig") as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"line {idx + 1} in {path} is not a JSON object")
            if "name" not in item:
                item["name"] = f"profile_{idx + 1}"
            policies.append(item)
    return policies


def main() -> None:
    parser = argparse.ArgumentParser(description="Doctor Manhattan Project ALife gym harness.")
    builtin_profiles = build_builtin_profiles()
    parser.add_argument("--width", type=int, default=52)
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--seed-base", type=int, default=1337)
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--seed-step", type=int, default=11)
    parser.add_argument("--output", type=str, default="", help="Optional JSONL output path.")
    parser.add_argument("--policy-file", type=str, default="", help="Optional JSONL with policy rows.")
    parser.add_argument(
        "--policy",
        type=str,
        default="",
        choices=sorted(builtin_profiles.keys()),
        help="Run a single built-in profile.",
    )
    parser.add_argument("--all-builtins", action="store_true", help="Run all built-in profiles.")
    args = parser.parse_args()

    if args.policy_file:
        policies = load_profiles(args.policy_file)
    elif args.all_builtins or not args.policy:
        policies = list(builtin_profiles.values())
    else:
        policies = [builtin_profiles[args.policy]]

    random.seed(args.seed_base)
    output_rows: List[Dict[str, float]] = []
    for policy in policies:
        rows = []
        for i in range(args.episodes):
            seed = args.seed_base + i * args.seed_step
            row = run_episode(policy, seed=seed, width=args.width, height=args.height, steps=args.steps)
            row["policy"] = policy["name"]
            rows.append(row)
            print(
                f"policy={policy['name']} seed={seed} "
                f"total={row['total_living']} delight={row['delight']:.3f} "
                f"avg_complexity={row['avg_complexity']:.3f} dominant={row['dominant_plane']} "
                f"goblin_events_last={row['goblin_events_last_tick']} "
                f"goblin_events_total={row['goblin_events_total']} "
                f"insight_events_last={row['insight_events_last_tick']}"
            )
        avg_delight = sum(row["delight"] for row in rows) / max(1, len(rows))
        print(f"summary policy={policy['name']} avg_delight={avg_delight:.3f} episodes={len(rows)}")
        output_rows.extend(rows)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            for row in output_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
