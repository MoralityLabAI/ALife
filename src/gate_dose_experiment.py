#!/usr/bin/env python3
"""Matched-sham discovery map for ALife destination-routing pulse dose."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

from alife import ALIVE, LifeUniverse
from gate_fixtures import BROKEN_DESTINATIONS, install_treated_gate_fixtures
from gate_topology_experiment import (
    GATE_EVENT_KEYS,
    bray_curtis,
    check_runtime,
    current_rss_mb,
    hill_diversity,
    mean,
    parse_seeds,
    pooled_alive_counts,
    quantile,
    state_digest,
    configure_condition,
)


ARMS: Mapping[str, tuple[str, int]] = {
    "off_0": ("native", 0),
    "broken_off_0": ("broken_feedback", 0),
    "native_1": ("native", 1),
    "broken_1": ("broken_feedback", 1),
    "native_4": ("native", 4),
    "broken_4": ("broken_feedback", 4),
}
PULSE_TICKS = (1, 41, 81, 121)
ACTIVE_PULSE_INDICES: Mapping[str, frozenset[int]] = {
    "off_0": frozenset(),
    "broken_off_0": frozenset(),
    "native_1": frozenset({4}),
    "broken_1": frozenset({4}),
    "native_4": frozenset({1, 2, 3, 4}),
    "broken_4": frozenset({1, 2, 3, 4}),
}


def initial_receipt(universe: LifeUniverse) -> Dict[str, Any]:
    stats = universe.stats()
    totals = {plane: sum(int(v) for k, v in counts.items() if k in ALIVE) for plane, counts in stats.items()}
    total = sum(totals.values())
    return {
        "plane_alive": totals,
        "plane_shares": {plane: value / max(1, total) for plane, value in totals.items()},
        "total_alive": total,
        "pooled_hill1": hill_diversity(pooled_alive_counts(stats)),
    }


def run_episode(
    arm: str,
    seed: int,
    width: int,
    height: int,
    density: float,
    steps: int,
    burn_in: int,
    deadline: float,
    max_ram_mb: float,
) -> Dict[str, Any]:
    topology, active_pulses = ARMS[arm]
    universe = LifeUniverse(width, height, seed=seed, seed_density=density)
    configure_condition(universe, topology)
    initial = initial_receipt(universe)
    trajectory: list[Dict[str, Any]] = []
    event_totals = {key: 0 for key in GATE_EVENT_KEYS}
    gate_rule_totals: Counter[str] = Counter()
    fixture_receipts = []
    previous_counts: Dict[str, int] | None = None
    capacity = width * height * len(universe.planes)

    for tick in range(1, steps + 1):
        check_runtime(deadline, max_ram_mb)
        if tick in PULSE_TICKS:
            pulse_index = PULSE_TICKS.index(tick) + 1
            receipt = install_treated_gate_fixtures(
                universe,
                "forge_survive6",
                placement_search_radius=4,
                target_clear_radius=None,
            )
            active = pulse_index in ACTIVE_PULSE_INDICES[arm]
            for gate in universe.gates:
                if gate.name in BROKEN_DESTINATIONS:
                    gate.effects_enabled = active
            fixture_receipts.append(
                {"tick": tick, "pulse_index": pulse_index, "active": active, **receipt}
            )

        stats = universe.step()
        if tick in PULSE_TICKS:
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
        if tick in PULSE_TICKS:
            expected_target = None
            if active:
                expected_target = (
                    BROKEN_DESTINATIONS
                    if topology == "broken_feedback"
                    else {
                        rule.name: rule.to_plane
                        for rule in universe.gates
                        if rule.name in BROKEN_DESTINATIONS
                    }
                )
            fixture_receipts[-1]["per_rule_events"] = {
                name: {
                    "shape_matches": int(events.get(f"gate_rule_shape_match::{name}", 0)),
                    "attempts": int(events.get(f"gate_rule_transfer::{name}", 0)),
                    "placements": int(events.get(f"gate_rule_placement::{name}", 0)),
                    "consumed": int(events.get(f"gate_rule_source_consumed::{name}", 0)),
                    "suppressed": int(events.get(f"gate_rule_suppressed::{name}", 0)),
                    "failed_occupied": int(events.get(f"gate_rule_target_occupied::{name}", 0)),
                    "expected_target": expected_target[name] if expected_target else None,
                    "target_placements": (
                        int(events.get(f"gate_rule_placement_target::{name}::{expected_target[name]}", 0))
                        if expected_target else 0
                    ),
                }
                for name in sorted(BROKEN_DESTINATIONS)
            }
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
        raise ValueError("burn-in leaves no late window")
    late_hill = [float(row["hill1"]) for row in late]
    return {
        "schema": "alife.gate_dose.episode.v1",
        "split": "discovery",
        "arm": arm,
        "topology": topology if active_pulses else "effects_off",
        "active_pulses": active_pulses,
        "scheduled_fixture_installs": len(PULSE_TICKS),
        "seed": seed,
        "width": width,
        "height": height,
        "density": density,
        "steps": steps,
        "burn_in": burn_in,
        "initial": initial,
        "pd20": quantile(late_hill, 0.20),
        "late_mean_hill1": mean(late_hill),
        "late_mean_density": mean(float(row["density"]) for row in late),
        "late_mean_beta_hill1": mean(float(row["beta_hill1"]) for row in late),
        "late_mean_turnover": mean(float(row["turnover"]) for row in late),
        "extinct": any(int(row["total_alive"]) == 0 for row in late),
        "event_totals": event_totals,
        "gate_rule_totals": dict(sorted(gate_rule_totals.items())),
        "fixture_receipts": fixture_receipts,
        "trajectory": trajectory,
        "state_digest": state_digest(universe, trajectory),
        "peak_rss_mb_observed": current_rss_mb(),
    }


def paired_values(rows: Sequence[Mapping[str, Any]], left: str, right: str) -> list[Dict[str, float]]:
    by_key = {(row["arm"], row["seed"]): row for row in rows}
    seeds = sorted({int(row["seed"]) for row in rows})
    return [
        {
            "seed": seed,
            "left": float(by_key[(left, seed)]["pd20"]),
            "right": float(by_key[(right, seed)]["pd20"]),
            "delta": float(by_key[(left, seed)]["pd20"] - by_key[(right, seed)]["pd20"]),
        }
        for seed in seeds
    ]


def describe(pairs: Sequence[Mapping[str, float]]) -> Dict[str, Any]:
    values = [float(row["delta"]) for row in pairs]
    return {
        "paired_rows": list(pairs),
        "mean_delta": mean(values),
        "median_delta": statistics.median(values),
        "positive": sum(value > 0 for value in values),
        "negative": sum(value < 0 for value in values),
    }


def pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    lm, rm = mean(left), mean(right)
    numerator = sum((x - lm) * (y - rm) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - lm) ** 2 for x in left) * sum((y - rm) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 0 else None


def exposure_audit(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    violations = []
    names = sorted(BROKEN_DESTINATIONS)
    for row in rows:
        expected_active = int(row["active_pulses"])
        for name in names:
            totals = row["gate_rule_totals"]
            observed = {
                "attempts": int(totals.get(f"gate_rule_transfer::{name}", 0)),
                "placements": int(totals.get(f"gate_rule_placement::{name}", 0)),
                "consumed": int(totals.get(f"gate_rule_source_consumed::{name}", 0)),
                "suppressed": int(totals.get(f"gate_rule_suppressed::{name}", 0)),
            }
            expected = {
                "attempts": len(PULSE_TICKS),
                "placements": expected_active,
                "consumed": expected_active,
                "suppressed": len(PULSE_TICKS) - expected_active,
            }
            if observed != expected:
                violations.append(
                    {"seed": row["seed"], "arm": row["arm"], "rule": name, "observed": observed, "expected": expected}
                )
        for receipt in row["fixture_receipts"]:
            fixtures = {item["rule"]: item for item in receipt["fixtures"]}
            for name in names:
                fixture = fixtures[name]
                pulse_events = receipt["per_rule_events"][name]
                active = bool(receipt["active"])
                valid_fixture = (
                    fixture["precheck_matches"]
                    and fixture["survival_eligible"]
                    and fixture["matching_rules_at_anchor"] == [name]
                )
                valid_events = (
                    pulse_events["shape_matches"] >= 1
                    and pulse_events["attempts"] == 1
                    and pulse_events["failed_occupied"] == 0
                    and (
                        active
                        and pulse_events["placements"] == 1
                        and pulse_events["consumed"] == 1
                        and pulse_events["suppressed"] == 0
                        and pulse_events["target_placements"] == 1
                        or not active
                        and pulse_events["placements"] == 0
                        and pulse_events["consumed"] == 0
                        and pulse_events["suppressed"] == 1
                        and pulse_events["target_placements"] == 0
                    )
                )
                if not valid_fixture or not valid_events:
                    violations.append(
                        {
                            "seed": row["seed"],
                            "arm": row["arm"],
                            "pulse": receipt["pulse_index"],
                            "rule": name,
                            "fixture_valid": valid_fixture,
                            "events": pulse_events,
                        }
                    )
    return {"passed": not violations, "violations": violations}


def analyze(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    dose1 = describe(paired_values(rows, "native_1", "broken_1"))
    dose4 = describe(paired_values(rows, "native_4", "broken_4"))
    by_seed_1 = {int(row["seed"]): float(row["delta"]) for row in dose1["paired_rows"]}
    by_seed_4 = {int(row["seed"]): float(row["delta"]) for row in dose4["paired_rows"]}
    amplification_rows = [
        {"seed": seed, "dose1_delta": by_seed_1[seed], "dose4_delta": by_seed_4[seed], "amplification": by_seed_4[seed] - by_seed_1[seed]}
        for seed in sorted(by_seed_1)
    ]
    amplification_values = [row["amplification"] for row in amplification_rows]
    ordered_count = sum(
        0.0 <= row["dose1_delta"] <= row["dose4_delta"]
        for row in amplification_rows
    )
    rng = random.Random(20260712)
    bootstrap = []
    for _ in range(5000):
        draw = [amplification_rows[rng.randrange(len(amplification_rows))] for _ in amplification_rows]
        bootstrap.append(
            (
                mean(float(row["dose1_delta"]) for row in draw),
                mean(float(row["amplification"]) for row in draw),
            )
        )
    off_native1 = describe(paired_values(rows, "native_1", "off_0"))
    off_broken1 = describe(paired_values(rows, "broken_1", "off_0"))
    off_native4 = describe(paired_values(rows, "native_4", "off_0"))
    off_broken4 = describe(paired_values(rows, "broken_4", "off_0"))
    arm_means = {
        arm: mean(float(row["pd20"]) for row in rows if row["arm"] == arm)
        for arm in ARMS
    }
    initial_rows = {
        int(row["seed"]): row["initial"]
        for row in rows
        if row["arm"] == "off_0"
    }
    seeds = sorted(initial_rows)
    moderator_correlations = {}
    for plane in ("GENESIS", "FORGE", "ECHOSPHERE", "MIRAGE"):
        moderator_correlations[f"initial_{plane.lower()}_share_vs_dose4_delta"] = pearson(
            [float(initial_rows[seed]["plane_shares"][plane]) for seed in seeds],
            [by_seed_4[seed] for seed in seeds],
        )
    exposure = exposure_audit(rows)
    by_key = {(row["arm"], int(row["seed"])): row for row in rows}
    zero_equivalence_rows = [
        {
            "seed": seed,
            "state_equal": by_key[("off_0", seed)]["state_digest"]
            == by_key[("broken_off_0", seed)]["state_digest"],
            "pd20_delta": float(
                by_key[("off_0", seed)]["pd20"]
                - by_key[("broken_off_0", seed)]["pd20"]
            ),
        }
        for seed in sorted({int(row["seed"]) for row in rows})
    ]
    zero_equivalence = all(row["state_equal"] for row in zero_equivalence_rows)
    candidate = (
        exposure["passed"]
        and zero_equivalence
        and dose1["mean_delta"] >= 0.05
        and dose1["positive"] >= math.ceil(0.8 * len(dose1["paired_rows"]))
        and mean(amplification_values) >= 0.05
        and sum(value > 0 for value in amplification_values) >= math.ceil(0.8 * len(amplification_values))
        and dose4["positive"] >= math.ceil(0.8 * len(dose4["paired_rows"]))
        and ordered_count >= math.ceil(0.8 * len(amplification_rows))
    )
    return {
        "arm_mean_pd20": arm_means,
        "native_minus_broken": {"dose1": dose1, "dose4": dose4},
        "dose_amplification": {
            "paired_rows": amplification_rows,
            "mean": mean(amplification_values),
            "median": statistics.median(amplification_values),
            "positive": sum(value > 0 for value in amplification_values),
            "ordered_zero_le_dose1_le_dose4": ordered_count,
            "bootstrap_95": {
                "dose1_increment": [
                    quantile([row[0] for row in bootstrap], 0.025),
                    quantile([row[0] for row in bootstrap], 0.975),
                ],
                "dose4_minus_dose1_increment": [
                    quantile([row[1] for row in bootstrap], 0.025),
                    quantile([row[1] for row in bootstrap], 0.975),
                ],
            },
        },
        "relative_to_matched_sham": {
            "native_1_minus_off": off_native1,
            "broken_1_minus_off": off_broken1,
            "native_4_minus_off": off_native4,
            "broken_4_minus_off": off_broken4,
        },
        "moderator_correlations_exploratory": moderator_correlations,
        "exposure": exposure,
        "zero_dose_topology_equivalence": {
            "passed": zero_equivalence,
            "paired_rows": zero_equivalence_rows,
        },
        "hazards": {
            arm: {
                "mean_late_density": mean(float(row["late_mean_density"]) for row in rows if row["arm"] == arm),
                "extinctions": sum(bool(row["extinct"]) for row in rows if row["arm"] == arm),
            }
            for arm in ARMS
        },
        "meets_predeclared_confirmation_candidate_gate": candidate,
    }


def render_report(summary: Mapping[str, Any]) -> str:
    analysis = summary["analysis"]
    d1 = analysis["native_minus_broken"]["dose1"]
    d4 = analysis["native_minus_broken"]["dose4"]
    amp = analysis["dose_amplification"]
    return f"""# Gate Routing Dose Discovery

## Contract

Discovery-only, model-only dose map. Every arm receives four exact source-fixture installations at ticks {list(PULSE_TICKS)} without clearing destination state. Native and broken all-sham arms verify zero-dose equivalence. Dose one shams the first three and activates the final pulse; dose four activates all four. Native and broken destinations are compared within dose using the common post-final window.

## Observed

- Exact-rule exposure passed: {analysis['exposure']['passed']}.
- Native-minus-broken dose-one mean PD20 delta: {d1['mean_delta']:.4f} ({d1['positive']}/{len(d1['paired_rows'])} positive).
- Native-minus-broken dose-four mean PD20 delta: {d4['mean_delta']:.4f} ({d4['positive']}/{len(d4['paired_rows'])} positive).
- Dose amplification mean: {amp['mean']:.4f} ({amp['positive']}/{len(amp['paired_rows'])} positive).
- Per-seed order `0 <= dose1 <= dose4`: {amp['ordered_zero_le_dose1_le_dose4']}/{len(amp['paired_rows'])}.
- Zero-dose topology equivalence passed: {analysis['zero_dose_topology_equivalence']['passed']}.
- Confirmation-candidate gate passed: {analysis['meets_predeclared_confirmation_candidate_gate']}.
- Deterministic duplicate replay passed: {summary['determinism']['passed']}.

## Inferred

This discovery {'supports freezing a fresh dose-response confirmation protocol' if analysis['meets_predeclared_confirmation_candidate_gate'] else 'does not support spending a fresh confirmation budget on monotonic native-routing amplification'}.

## Not Supported

These inspected discovery seeds do not establish a causal dose response, recurrent connectivity, or external validity. Scheduled fixture overwrites and target clearing are part of the calibrated regime.
"""


def validate(args: argparse.Namespace) -> None:
    if args.width < 32 or args.height < 18:
        raise SystemExit("fixture layout requires at least 32x18")
    if args.steps != 160 or args.burn_in != 121:
        raise SystemExit("this frozen discovery harness requires 160 steps and burn-in 121")
    if len(args.seeds) > 8:
        raise SystemExit("discovery seed hard limit is eight")
    if args.wall_seconds <= 0 or args.wall_seconds > 1200 or args.max_ram_mb < 64:
        raise SystemExit("resource limits are invalid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=18)
    parser.add_argument("--density", type=float, default=0.22)
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--burn-in", type=int, default=121)
    parser.add_argument("--seeds", type=parse_seeds, default=parse_seeds("4101,4127,4153,4177,4201"))
    parser.add_argument("--wall-seconds", type=float, default=900.0)
    parser.add_argument("--max-ram-mb", type=float, default=512.0)
    parser.add_argument("--output", type=Path, default=Path(r"D:\ALife\gate_dose_discovery_v1"))
    args = parser.parse_args()
    validate(args)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.wall_seconds
    started = time.monotonic()
    rows = []
    with (output / "episodes.jsonl").open("w", encoding="utf-8", buffering=1) as handle:
        for seed in args.seeds:
            for arm in ARMS:
                row = run_episode(
                    arm, seed, args.width, args.height, args.density,
                    args.steps, args.burn_in, deadline, args.max_ram_mb,
                )
                rows.append(row)
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
                print(
                    f"seed={seed} arm={arm} pd20={row['pd20']:.3f} "
                    f"placements={row['event_totals']['gate_placements']} "
                    f"suppressed={row['event_totals']['gate_effects_suppressed']}"
                )

        repeat = run_episode(
            "native_4", args.seeds[0], args.width, args.height, args.density,
            args.steps, args.burn_in, deadline, args.max_ram_mb,
        )
        handle.write(json.dumps(repeat, separators=(",", ":")) + "\n")

    reference = next(row for row in rows if row["arm"] == "native_4" and row["seed"] == args.seeds[0])
    determinism = {
        "passed": reference["state_digest"] == repeat["state_digest"],
        "seed": args.seeds[0],
        "first": reference["state_digest"],
        "second": repeat["state_digest"],
    }
    if not determinism["passed"]:
        raise RuntimeError("dose discovery determinism failed")
    analysis = analyze(rows)
    summary = {
        "schema": "alife.gate_dose.summary.v1",
        "claim_scope": "model_only_discovery",
        "config": {
            "width": args.width,
            "height": args.height,
            "density": args.density,
            "steps": args.steps,
            "burn_in": args.burn_in,
            "seeds": args.seeds,
            "arms": ARMS,
            "pulse_ticks": PULSE_TICKS,
            "active_pulse_indices": {
                arm: sorted(indices)
                for arm, indices in ACTIVE_PULSE_INDICES.items()
            },
            "wall_seconds": args.wall_seconds,
            "max_ram_mb": args.max_ram_mb,
            "output": str(output),
        },
        "analysis": analysis,
        "determinism": determinism,
        "episode_count": len(rows) + 1,
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_mb_observed": max(
            (float(row["peak_rss_mb_observed"]) for row in rows if row["peak_rss_mb_observed"] is not None),
            default=None,
        ),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "report.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(analysis, indent=2))
    print(f"output={output} elapsed={summary['elapsed_seconds']:.2f}s")


if __name__ == "__main__":
    main()
