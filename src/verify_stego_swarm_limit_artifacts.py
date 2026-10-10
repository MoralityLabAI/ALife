#!/usr/bin/env python3
"""Verify steganographic-swarm coordination-limit artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from artifact_verification import (
    audit_runtime_environment,
    project_search_roots,
    resolve_recorded_file,
    sha256_file,
)


REQUIRED = {
    "raw_episodes.jsonl",
    "summary.json",
    "seed_manifest.json",
    "frozen_manifest.json",
    "receipt.json",
    "knowledge_card.md",
    "hashes.json",
}
EPISODE_SCHEMA = "alife.stego_swarm_limit.episode.v1"
REGIMES = ("stationary", "shift")
INF_BITS = 1_000_000_000


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Ignore original-machine absolute paths and require bundle-relative suffix resolution.",
    )
    args = parser.parse_args()
    root = args.artifact_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(name for name in REQUIRED if not (root / name).is_file())
    if missing:
        print(json.dumps({"valid": False, "errors": [f"missing: {missing}"]}, indent=2))
        raise SystemExit(1)

    manifest = load_json(root / "frozen_manifest.json")
    summary = load_json(root / "summary.json")
    receipt = load_json(root / "receipt.json")
    hashes = load_json(root / "hashes.json")
    analysis = manifest["analysis"]
    design = manifest["design"]

    for name, record in hashes.items():
        path = root / name
        if not path.is_file() or sha256_file(path) != record.get("sha256") or path.stat().st_size != record.get("bytes"):
            errors.append(f"artifact hash/size failure: {name}")

    rows: list[dict[str, Any]] = []
    with (root / "raw_episodes.jsonl").open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("schema") != EPISODE_SCHEMA:
                errors.append(f"wrong schema at line {line_number}")
            rows.append(row)
    if len(rows) != summary.get("row_count") or len(rows) != receipt.get("episode_count"):
        errors.append("raw, summary, and receipt counts disagree")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("determinism failed")

    # Per-row structural and non-operational invariants.
    split_counts = Counter(str(row.get("split")) for row in rows)
    identifiers: set[tuple[Any, ...]] = set()
    budget = int(design["coalition_budget"])
    sweep = list(design["capacity_bits_sweep"])
    for index, row in enumerate(rows, 1):
        identifier = (row.get("split"), row.get("seed"))
        if identifier in identifiers:
            errors.append(f"duplicate seed: {identifier}")
        identifiers.add(identifier)
        regimes = row.get("regimes", {})
        if set(regimes) != set(REGIMES):
            errors.append(f"regime set mismatch at row {index}")
            continue
        for regime, result in regimes.items():
            curve = result.get("capacity_curve", [])
            if [entry["bits"] for entry in curve] != sweep:
                errors.append(f"capacity sweep mismatch at row {index} ({regime})")
            if not all(bool(entry["budget_conserved"]) for entry in curve):
                errors.append(f"budget not conserved at row {index} ({regime})")
            # Saturation must be exact: unbounded capacity adds nothing past threshold.
            if abs(float(result["post_saturation_excess"])) > float(analysis["capacity_saturation_band"]):
                errors.append(f"saturation excess exceeds band at row {index} ({regime})")
            # Covert channel carries no content: Q is bounded by the budget.
            if any(int(entry["coordinated_units"]) > budget for entry in curve):
                errors.append(f"coordinated units exceed budget at row {index} ({regime})")
            inf_entry = next(entry for entry in curve if int(entry["bits"]) >= INF_BITS)
            if int(inf_entry["coordinated_units"]) != budget:
                errors.append(f"unbounded capacity did not reach budget at row {index} ({regime})")
        if not row.get("validity_gate_pass"):
            warnings.append(f"row {index} did not pass its own validity gate")

    for split, expected in summary.get("episode_counts", {}).items():
        if split_counts[split] != expected:
            errors.append(f"split count mismatch: {split}")
    seed_plan = manifest["seed_plan"]
    seed_sets = [set(seed_plan[split]) for split in ("discovery", "confirmatory", "holdout")]
    if seed_sets[0] & seed_sets[1] or seed_sets[0] & seed_sets[2] or seed_sets[1] & seed_sets[2]:
        errors.append("seed splits overlap")

    # Holdout gates recomputed against the frozen manifest thresholds.
    holdout = summary.get("holdout", {})
    if abs(float(holdout.get("max_abs_post_saturation_excess", 1.0))) > float(analysis["capacity_saturation_band"]):
        errors.append("holdout saturation excess exceeds band")
    if float(holdout.get("mean_stationary_saturated_gain", -1.0)) < float(analysis["minimum_stationary_gain"]):
        errors.append("holdout stationary gain below frozen minimum")
    if abs(float(holdout.get("mean_shift_gain", 1.0))) > float(analysis["shift_gain_band"]):
        errors.append("holdout shift gain exceeds band")
    if float(holdout.get("capital_warden_auc", 0.0)) < float(analysis["minimum_capital_auc"]):
        errors.append("capital warden AUC below frozen minimum")
    if abs(float(holdout.get("trace_warden_auc", 1.0)) - 0.5) > float(analysis["trace_auc_null_halfwidth"]):
        errors.append("trace warden AUC outside chance null")
    gap = float(holdout.get("capital_warden_auc", 0.0)) - float(holdout.get("trace_warden_auc", 1.0))
    if gap < float(analysis["warden_firewall_margin"]):
        errors.append("warden firewall gap below frozen margin")

    assessment = summary.get("hypothesis_assessment", {})
    for key in ("H1_capacity_saturation", "H2_capital_bounded_and_forecast_limited", "H3_warden_firewall"):
        if assessment.get(key) != "supported":
            warnings.append(f"hypothesis not supported in summary: {key} ({assessment.get(key)})")

    if sha256_file(root / "frozen_manifest.json") != receipt.get("manifest_sha256"):
        errors.append("manifest hash mismatch")
    search_roots = project_search_roots(Path(__file__), root)
    code_resolution = resolve_recorded_file(
        str(receipt.get("code_path", "")),
        str(receipt.get("code_sha256", "")),
        search_roots=search_roots,
        suffix_parts=2,
        allow_recorded_path=not args.portable,
    )
    if code_resolution["status"] != "resolved":
        errors.append("current experiment code does not match receipt")

    environment_audit = audit_runtime_environment(receipt, ["numpy", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("recorded environment fields do not match their receipt fingerprint")
    if not environment_audit["runtime_exact_match"]:
        warnings.append(
            "runtime environment differs from recorded run: "
            + ", ".join(sorted(environment_audit["differences"]))
        )

    budget_plan = manifest["budget"]
    total_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    if float(receipt.get("wall_seconds", float("inf"))) > float(budget_plan["max_wall_seconds"]):
        errors.append("wall budget exceeded")
    if float(receipt.get("max_rss_mb", float("inf"))) > float(budget_plan["max_ram_mb"]):
        errors.append("RAM budget exceeded")
    if len(rows) > int(budget_plan["max_episodes"]):
        errors.append("episode budget exceeded")
    if total_bytes > float(budget_plan["max_disk_mb"]) * 1024 * 1024:
        errors.append("disk budget exceeded")

    result = {
        "valid": not errors,
        "artifact_dir": str(root),
        "errors": errors,
        "warnings": warnings,
        "provenance": {
            "code_resolution": code_resolution,
            "environment": environment_audit,
        },
        "evidence": {
            "raw_rows": len(rows),
            "split_counts": dict(split_counts),
            "hashes_checked": len(hashes),
            "total_bytes": total_bytes,
            "holdout_stationary_gain": holdout.get("mean_stationary_saturated_gain"),
            "holdout_shift_gain": holdout.get("mean_shift_gain"),
            "holdout_trace_auc": holdout.get("trace_warden_auc"),
            "holdout_capital_auc": holdout.get("capital_warden_auc"),
            "hypothesis_assessment": assessment,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
