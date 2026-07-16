#!/usr/bin/env python3
"""Run many ALife runs and emit compact summaries."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict

from alife import LifeUniverse


def format_summary(seed: int, final_stats: Dict[str, Dict[str, int]], events: Dict[str, int]) -> str:
    totals = {plane: final_stats[plane].get("total", 0) for plane in sorted(final_stats)}
    total_life = sum(totals.values())
    max_plane = max(final_stats.items(), key=lambda item: item[1].get("total", 0))
    return (
        f"seed={seed} total={total_life} "
        f"dominant={max_plane[0]}({max_plane[1].get('total', 0)}) "
        f"totals={totals} events={events}"
    )


def run_batch(args: argparse.Namespace) -> None:
    results = []
    event_agg = Counter()
    plane_totals_agg = Counter()
    complexity_scores: List[float] = []
    delight_scores: List[float] = []
    dominant_plane_counts: Counter = Counter()

    for idx in range(args.batch):
        seed = args.seed_base + idx * args.seed_step
        universe = LifeUniverse(args.width, args.height, seed=seed, seed_density=args.density)
        run_event_totals = Counter()
        run_complexity: List[float] = []
        for _ in range(args.steps):
            universe.step()
            step_events = universe.event_counts()
            event_agg.update(step_events)
            run_event_totals.update(step_events)
            run_complexity.append(universe.last_complexity())
        final_stats = universe.stats()
        line_totals = {plane: final_stats[plane].get("total", 0) for plane in final_stats}
        dominant_plane = max(final_stats.items(), key=lambda item: item[1].get("total", 0))[0]
        plane_totals_agg.update(line_totals)
        last_metrics = universe.latest_metrics()
        avg_complexity = sum(run_complexity) / max(1, len(run_complexity))
        peak_complexity = max(run_complexity) if run_complexity else 0.0
        plane_entropy = last_metrics.get("plane_entropy", 0.0)
        diversity = len([plane for plane, total in line_totals.items() if total > 0]) / max(1, len(final_stats))
        gate_flux = last_metrics.get("gate_flux", 0.0)
        delight = avg_complexity + (gate_flux * 2.0) + (diversity * 0.6) + (plane_entropy * 0.35)
        complexity_scores.append(avg_complexity)
        delight_scores.append(delight)
        dominant_plane_counts[dominant_plane] += 1
        results.append({
            "seed": seed,
            "final_totals": final_stats,
            "total_living": sum(line_totals.values()),
            "events": dict(run_event_totals),
            "dominant_plane": dominant_plane,
            "complexity": {
                "avg": avg_complexity,
                "peak": peak_complexity,
                "plane_entropy": plane_entropy,
                "kind_entropy": last_metrics.get("kind_entropy", 0.0),
                "diversity": diversity,
                "gate_flux": gate_flux,
            },
            "delight": delight,
        })
        print(f"{format_summary(seed, final_stats, dict(run_event_totals))} avg_complexity={avg_complexity:.3f} peak={peak_complexity:.3f} delight={delight:.3f} dominant={dominant_plane}")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            for item in results:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    if args.summary:
        average_living = sum(r["total_living"] for r in results) / max(1, len(results))
        avg_planes = {plane: plane_totals_agg[plane] / max(1, len(results)) for plane in sorted(plane_totals_agg)}
        avg_events = {k: v / max(1, len(results)) for k, v in event_agg.items()}
        avg_complexity = sum(complexity_scores) / max(1, len(complexity_scores))
        avg_delight = sum(delight_scores) / max(1, len(delight_scores))
        print(f"runs={len(results)} avg_total={average_living:.2f} avg_complexity={avg_complexity:.3f} avg_delight={avg_delight:.3f} avg_plane_totals={avg_planes} avg_events={avg_events} dominant_share={dict(dominant_plane_counts)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact batch runner for ALife experiments.")
    parser.add_argument("--width", type=int, default=52)
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--seed-base", type=int, default=1337)
    parser.add_argument("--seed-step", type=int, default=1)
    parser.add_argument("--batch", type=int, default=5)
    parser.add_argument("--density", type=float, default=0.22)
    parser.add_argument("--output", type=str, default="", help="Optional JSONL output path.")
    parser.add_argument("--summary", action="store_true", help="Print aggregate summary.")
    args = parser.parse_args()
    run_batch(args)


if __name__ == "__main__":
    main()
