#!/usr/bin/env python3
"""Deterministic exposure audit for the six destination-rewired ALife gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from alife import LifeUniverse
from gate_fixtures import (
    BROKEN_DESTINATIONS,
    FIXTURE_ANCHORS,
    FIXTURE_REGIMES as REGIMES,
    install_treated_gate_fixtures,
)
from gate_topology_experiment import configure_condition, current_rss_mb


TOPOLOGIES = ("native", "broken_feedback")


def locate_gate_products(universe: LifeUniverse) -> Dict[str, list[Dict[str, Any]]]:
    products: Dict[str, list[Dict[str, Any]]] = {name: [] for name in FIXTURE_ANCHORS}
    for plane, grid in universe.grids.items():
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell is None:
                    continue
                for name in products:
                    if cell.flavor.startswith(f"{name}_from_"):
                        products[name].append(
                            {
                                "plane": plane,
                                "x": x,
                                "y": y,
                                "kind": cell.kind,
                                "flavor": cell.flavor,
                            }
                        )
    return products


def digest(universe: LifeUniverse, events: Mapping[str, int]) -> str:
    cells = []
    for plane, grid in sorted(universe.grids.items()):
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell is not None:
                    cells.append((plane, x, y, tuple(sorted(vars(cell).items()))))
    payload = json.dumps(
        {"cells": cells, "events": dict(sorted(events.items()))},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_audit(topology: str, regime: str, seed: int, width: int, height: int) -> Dict[str, Any]:
    universe = LifeUniverse(width, height, seed=seed, seed_density=0.22)
    configure_condition(universe, topology)
    fixture_receipt = install_treated_gate_fixtures(universe, regime)
    universe.step()
    events = universe.event_counts()
    products = locate_gate_products(universe)
    per_rule = {}
    for name in FIXTURE_ANCHORS:
        per_rule[name] = {
            "shape_matches": int(events.get(f"gate_rule_shape_match::{name}", 0)),
            "attempts": int(events.get(f"gate_rule_transfer::{name}", 0)),
            "placements": int(events.get(f"gate_rule_placement::{name}", 0)),
            "failed_occupied": int(events.get(f"gate_rule_target_occupied::{name}", 0)),
            "rescued": int(events.get(f"gate_rule_rescue::{name}", 0)),
            "products": products[name],
        }
    return {
        "schema": "alife.gate_fixture_audit.v1",
        "topology": topology,
        "regime": regime,
        "seed": seed,
        "fixture_receipt": fixture_receipt,
        "per_rule": per_rule,
        "aggregate_events": {
            key: int(events.get(key, 0))
            for key in (
                "gate_shape_matches",
                "gate_transfers",
                "gate_placements",
                "gate_target_occupied",
                "gate_rescued_placements",
                "gate_source_consumed",
            )
        },
        "state_digest": digest(universe, events),
        "rss_mb": current_rss_mb(),
    }


def all_rules_exposed(row: Mapping[str, Any]) -> bool:
    return all(
        receipt["shape_matches"] >= 1
        and receipt["attempts"] >= 1
        and receipt["placements"] >= 1
        and len(receipt["products"]) >= 1
        for receipt in row["per_rule"].values()
    )


def expected_target(topology: str, name: str, native_targets: Mapping[str, str]) -> str:
    if topology == "broken_feedback":
        return BROKEN_DESTINATIONS[name]
    return native_targets[name]


def analyze(rows: Sequence[Mapping[str, Any]], native_targets: Mapping[str, str]) -> Dict[str, Any]:
    by_key = {(row["topology"], row["regime"]): row for row in rows}
    routing_checks = []
    for row in rows:
        for name, receipt in row["per_rule"].items():
            expected = expected_target(row["topology"], name, native_targets)
            actual = sorted({product["plane"] for product in receipt["products"]})
            routing_checks.append(
                {
                    "topology": row["topology"],
                    "regime": row["regime"],
                    "rule": name,
                    "expected": expected,
                    "actual": actual,
                    "passed": actual == [expected],
                }
            )
    return {
        "native_survival_all_rules_exposed": all_rules_exposed(
            by_key[("native", "native_survival")]
        ),
        "forge_survive6_all_rules_exposed": {
            topology: all_rules_exposed(by_key[(topology, "forge_survive6")])
            for topology in TOPOLOGIES
        },
        "routing_checks": routing_checks,
        "routing_passed_for_exposed_rules": all(
            check["passed"]
            for check in routing_checks
            if by_key[(check["topology"], check["regime"])]["per_rule"][check["rule"]]["placements"]
        ),
        "fixture_regime_clears_exposure_gate": all(
            all_rules_exposed(by_key[(topology, "forge_survive6")])
            for topology in TOPOLOGIES
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    analysis = summary["analysis"]
    return f"""# Treated Gate Fixture Audit

## Contract

Model-only operational/measurement audit. Exact fixtures are installed for all six destination-rewired rules. Gate chance is 1.0, unrelated gates are disabled, and both possible target neighborhoods are cleared symmetrically.

## Observed

- Native survival rules exposed all six gates: {analysis['native_survival_all_rules_exposed']}.
- Adding survival-at-six in FORGE exposed all six gates under native wiring: {analysis['forge_survive6_all_rules_exposed']['native']}.
- Adding survival-at-six in FORGE exposed all six gates under broken wiring: {analysis['forge_survive6_all_rules_exposed']['broken_feedback']}.
- Products followed their expected topology destinations: {analysis['routing_passed_for_exposed_rules']}.
- Duplicate replay passed: {summary['determinism']['passed']}.

## Inferred

The fixture regime clears the exact-rule treatment-exposure gate: {analysis['fixture_regime_clears_exposure_gate']}. The survival-at-six addition is an explicit calibrated model regime, not native behavior.

## Not Supported

This one-tick audit does not establish a persistent-diversity effect or validate spontaneous reachability. It only tests eligibility, activation, execution, and destination routing.

## Decision

{'Freeze a fresh, fixture-conditioned topology protocol.' if analysis['fixture_regime_clears_exposure_gate'] else 'Repair fixture reachability before any topology outcome ensemble.'}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1801)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=18)
    parser.add_argument("--output", type=Path, default=Path("results/gate_fixture_audit"))
    args = parser.parse_args()
    if args.width < 32 or args.height < 18:
        raise SystemExit("fixture layout requires at least 32x18")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    native_universe = LifeUniverse(args.width, args.height, seed=0, seed_density=0.0)
    native_targets = {
        rule.name: rule.to_plane
        for rule in native_universe.gates
        if rule.name in BROKEN_DESTINATIONS
    }
    rows = [
        run_audit(topology, regime, args.seed, args.width, args.height)
        for regime in REGIMES
        for topology in TOPOLOGIES
    ]
    repeat = run_audit("native", "forge_survive6", args.seed, args.width, args.height)
    reference = next(
        row for row in rows
        if row["topology"] == "native" and row["regime"] == "forge_survive6"
    )
    determinism = {
        "passed": reference["state_digest"] == repeat["state_digest"],
        "first": reference["state_digest"],
        "second": repeat["state_digest"],
    }
    if not determinism["passed"]:
        raise RuntimeError("fixture audit determinism failed")
    analysis = analyze(rows, native_targets)
    summary = {
        "schema": "alife.gate_fixture_audit.summary.v1",
        "claim_scope": "model_only",
        "config": vars(args) | {"output": str(output)},
        "native_targets": native_targets,
        "rows": rows,
        "analysis": analysis,
        "determinism": determinism,
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_mb_observed": current_rss_mb(),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (output / "report.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(analysis, indent=2))
    print(f"output={output} elapsed={summary['elapsed_seconds']:.2f}s")


if __name__ == "__main__":
    main()
