#!/usr/bin/env python3
"""Exploratory 2x2 calibration of ALife gate activation and collision rescue."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

from gate_topology_experiment import (
    GATE_EVENT_KEYS,
    check_runtime,
    current_rss_mb,
    parse_seeds,
    run_episode,
)


CONDITIONS = (
    "native",
    "activation_x4",
    "collision_rescue",
    "activation_x4_collision_rescue",
)


def total(rows: Iterable[Mapping[str, Any]], condition: str, key: str) -> int:
    return sum(
        int(row["event_totals"].get(key, 0))
        for row in rows
        if row["condition"] == condition
    )


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / max(1, len(values))


def summarize(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    pipeline: Dict[str, Dict[str, Any]] = {}
    outcomes: Dict[str, Dict[str, Any]] = {}
    for condition in CONDITIONS:
        shapes = total(rows, condition, "gate_shape_matches")
        queues = total(rows, condition, "gate_transfers")
        placements = total(rows, condition, "gate_placements")
        failures = total(rows, condition, "gate_target_occupied")
        rescues = total(rows, condition, "gate_rescued_placements")
        pipeline[condition] = {
            "checks": total(rows, condition, "gate_checks"),
            "shape_matches": shapes,
            "queued_attempts": queues,
            "placements": placements,
            "failed_occupied_targets": failures,
            "rescued_placements": rescues,
            "queue_per_shape": queues / max(1, shapes),
            "placement_per_queue": placements / max(1, queues),
            "rescue_per_queue": rescues / max(1, queues),
        }
        condition_rows = [row for row in rows if row["condition"] == condition]
        outcomes[condition] = {
            "mean_pd20": mean(float(row["pd20"]) for row in condition_rows),
            "mean_late_density": mean(float(row["late_mean_density"]) for row in condition_rows),
            "extinctions": sum(bool(row["extinct"]) for row in condition_rows),
        }

    native = pipeline["native"]
    boosted = pipeline["activation_x4"]
    rescued = pipeline["collision_rescue"]
    combined = pipeline["activation_x4_collision_rescue"]
    activation_increases_attempts = boosted["queued_attempts"] > native["queued_attempts"]
    rescue_converts_collisions = (
        rescued["rescued_placements"] + combined["rescued_placements"] > 0
    )
    feasible_for_topology_study = combined["placements"] >= 5
    return {
        "pipeline": pipeline,
        "outcomes_exploratory": outcomes,
        "diagnosis": {
            "activation_increases_attempts": activation_increases_attempts,
            "rescue_converts_collisions": rescue_converts_collisions,
            "combined_has_at_least_five_placements": feasible_for_topology_study,
            "recommended_next_step": (
                "repeat the topology contrast under explicitly calibrated gate mechanics"
                if feasible_for_topology_study
                else "calibrate shape availability or a wider placement policy before topology testing"
            ),
        },
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Gate pipeline calibration",
        "",
        "Exploratory, model-only calibration. These inspected seeds are not confirmatory evidence.",
        "",
        "## Contract",
        "",
        "A 2x2 intervention separates gate activation probability (native vs. x4) from a deterministic radius-2 search for an empty destination after the native target collides. Defaults remain unchanged.",
        "",
        "## Observed",
        "",
        "| condition | shapes | attempts | placements | failed collisions | rescued | attempt/shape | placement/attempt |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition, row in summary["analysis"]["pipeline"].items():
        lines.append(
            f"| {condition} | {row['shape_matches']} | {row['queued_attempts']} | "
            f"{row['placements']} | {row['failed_occupied_targets']} | "
            f"{row['rescued_placements']} | {row['queue_per_shape']:.3f} | "
            f"{row['placement_per_queue']:.3f} |"
        )
    diagnosis = summary["analysis"]["diagnosis"]
    lines.extend(
        [
            "",
            "## Inferred",
            "",
            f"- Boosting activation increased attempts: {diagnosis['activation_increases_attempts']}.",
            f"- Deterministic empty-cell search converted collisions: {diagnosis['rescue_converts_collisions']}.",
            f"- The combined condition produced at least five placements: {diagnosis['combined_has_at_least_five_placements']}.",
            "",
            "## Not supported",
            "",
            "This calibration does not establish a diversity benefit, a topology mechanism, or behavior outside this simulator. Outcome metrics are diagnostic only because interventions alter exposure and the seeds were inspected.",
            "",
            "## Decision",
            "",
            diagnosis["recommended_next_step"] + ".",
            "",
        ]
    )
    return "\n".join(lines)


def validate(args: argparse.Namespace) -> None:
    episodes = len(CONDITIONS) * len(args.seeds) + 1
    if not (8 <= args.width <= 64 and 8 <= args.height <= 64):
        raise SystemExit("width and height must be in [8, 64]")
    if not (1 <= args.steps <= 300):
        raise SystemExit("steps must be in [1, 300]")
    if not (0 <= args.burn_in < args.steps):
        raise SystemExit("burn-in must be smaller than steps")
    if episodes > 25:
        raise SystemExit("episode hard limit exceeded")
    if args.max_ram_mb < 64 or args.wall_seconds > 1800:
        raise SystemExit("resource limits are invalid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=18)
    parser.add_argument("--density", type=float, default=0.22)
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--burn-in", type=int, default=50)
    parser.add_argument("--seeds", type=parse_seeds, default=parse_seeds("101,1101,1103,1117"))
    parser.add_argument("--wall-seconds", type=float, default=900.0)
    parser.add_argument("--max-ram-mb", type=float, default=512.0)
    parser.add_argument("--output", type=Path, default=Path("results/gate_pipeline_calibration"))
    args = parser.parse_args()
    validate(args)

    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.wall_seconds
    started = time.monotonic()
    rows = []
    raw_path = output / "episodes.jsonl"
    with raw_path.open("w", encoding="utf-8", buffering=1) as handle:
        for seed in args.seeds:
            for condition in CONDITIONS:
                check_runtime(deadline, args.max_ram_mb)
                row = run_episode(
                    condition, "exploratory", seed, args.width, args.height,
                    args.density, args.steps, args.burn_in, deadline, args.max_ram_mb,
                )
                rows.append(row)
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
                events = row["event_totals"]
                print(
                    f"seed={seed} condition={condition} shapes={events['gate_shape_matches']} "
                    f"attempts={events['gate_transfers']} placements={events['gate_placements']} "
                    f"rescued={events['gate_rescued_placements']}"
                )

        repeat = run_episode(
            "activation_x4_collision_rescue", "determinism", args.seeds[0],
            args.width, args.height, args.density, args.steps, args.burn_in,
            deadline, args.max_ram_mb,
        )
        handle.write(json.dumps(repeat, separators=(",", ":")) + "\n")

    reference = next(
        row for row in rows
        if row["seed"] == args.seeds[0]
        and row["condition"] == "activation_x4_collision_rescue"
    )
    deterministic = reference["state_digest"] == repeat["state_digest"]
    if not deterministic:
        raise RuntimeError("duplicate-run determinism check failed")

    config = {
        "width": args.width,
        "height": args.height,
        "density": args.density,
        "steps": args.steps,
        "burn_in": args.burn_in,
        "seeds": args.seeds,
        "conditions": CONDITIONS,
        "wall_seconds": args.wall_seconds,
        "max_ram_mb": args.max_ram_mb,
    }
    summary = {
        "schema": "alife.gate_pipeline_calibration.summary.v1",
        "claim_scope": "model_only_exploratory",
        "config": config,
        "analysis": summarize(rows),
        "determinism": {"passed": deterministic, "seed": args.seeds[0]},
        "episode_count": len(rows) + 1,
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_mb_observed": current_rss_mb(),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "report.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary["analysis"], indent=2))
    print(f"determinism={deterministic} elapsed={summary['elapsed_seconds']:.2f}s output={output}")


if __name__ == "__main__":
    main()
