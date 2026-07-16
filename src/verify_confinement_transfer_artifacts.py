#!/usr/bin/env python3
"""Verify compute-matched Confinement Width transfer artifacts."""

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
METHODS = {"compute_matched_random_search", "evolutionary_schedule_search"}


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
            if row.get("schema") != "alife.confinement_transfer.episode.v1":
                errors.append(f"wrong schema at line {line_number}")
            rows.append(row)
    if len(rows) != summary.get("row_count") or len(rows) != receipt.get("episode_count"):
        errors.append("raw, summary, and receipt counts disagree")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("determinism failed")
    split_counts = Counter(str(row.get("split")) for row in rows)
    identifiers: set[tuple[Any, ...]] = set()
    valid_rows = 0
    positive_holdout = 0
    design = manifest["design"]
    expected_evals = int(design["candidate_evaluations_per_method"])
    expected_actions = int(design["action_budget"])
    for index, row in enumerate(rows, 1):
        identifier = (row.get("split"), row.get("search_seed"))
        if identifier in identifiers:
            errors.append(f"duplicate paired seed: {identifier}")
        identifiers.add(identifier)
        methods = row.get("methods", [])
        if {method.get("method") for method in methods} != METHODS or len(methods) != 2:
            errors.append(f"method exposure failure at row {index}")
            continue
        for method in methods:
            if method.get("candidate_evaluations") != expected_evals:
                errors.append(f"compute mismatch at row {index}")
            if method.get("action_budget") != expected_actions or len(method.get("selected_schedule", [])) != expected_actions:
                errors.append(f"action budget mismatch at row {index}")
            if method.get("proxy_failure_steps") != 0 or method.get("max_abs_closure_defect_eta") != 0.0:
                errors.append(f"consumer validity gate failure at row {index}")
            if method.get("action_budget_mismatch"):
                errors.append(f"execution action mismatch at row {index}")
        if row.get("validity_gate_pass"):
            valid_rows += 1
        if row.get("split") == "holdout" and float(row.get("paired_kernel_escape_improvement", 0)) > 0:
            positive_holdout += 1

    for split, expected in summary.get("episode_counts", {}).items():
        if split_counts[split] != expected:
            errors.append(f"split count mismatch: {split}")
    seed_plan = manifest["seed_plan"]
    seed_sets = [set(seed_plan[split]) for split in ("discovery", "confirmatory", "holdout")]
    if seed_sets[0] & seed_sets[1] or seed_sets[0] & seed_sets[2] or seed_sets[1] & seed_sets[2]:
        errors.append("seed splits overlap")

    holdout = summary.get("holdout", {})
    if float(holdout.get("mean_paired_improvement", -1)) < float(manifest["analysis"]["minimum_holdout_improvement"]):
        errors.append("holdout improvement missed frozen gate")
    if float(holdout.get("positive_pair_fraction", -1)) < float(manifest["analysis"]["minimum_positive_pair_fraction"]):
        errors.append("directional robustness missed frozen gate")
    if holdout.get("validity_gate_pass") is not True:
        errors.append("holdout validity gate failed")

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
        errors.append("current transfer code does not match receipt")
    consumer = design["consumer_baseline"]
    consumer_resolutions: dict[str, Any] = {}
    for path_key, hash_key in (("source_path", "source_sha256"), ("baseline_summary_path", "baseline_summary_sha256")):
        resolution = resolve_recorded_file(
            str(consumer[path_key]),
            str(consumer[hash_key]),
            search_roots=search_roots,
            suffix_parts=3,
            allow_recorded_path=not args.portable,
        )
        consumer_resolutions[path_key] = resolution
        if resolution["status"] != "resolved":
            errors.append(
                f"consumer provenance failure: {path_key} ({resolution['status']})"
            )
    environment_audit = audit_runtime_environment(receipt, ["numpy", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("recorded environment fields do not match their receipt fingerprint")
    if not environment_audit["runtime_exact_match"]:
        warnings.append(
            "runtime environment differs from recorded run: "
            + ", ".join(sorted(environment_audit["differences"]))
        )

    budget = manifest["budget"]
    total_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    if float(receipt.get("wall_seconds", float("inf"))) > float(budget["max_wall_seconds"]):
        errors.append("wall budget exceeded")
    if float(receipt.get("max_rss_mb", float("inf"))) > float(budget["max_ram_mb"]):
        errors.append("RAM budget exceeded")
    if len(rows) > int(budget["max_episodes"]):
        errors.append("episode budget exceeded")
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        errors.append("disk budget exceeded")
    storage_location_check = {
        "expected_prefix": "D:\\",
        "actual_path": str(root),
        "matches_intended_drive": str(root).lower().startswith("d:\\"),
        "affects_validity": False,
    }
    if not storage_location_check["matches_intended_drive"]:
        warnings.append("artifact directory does not resolve to D drive")

    result = {
        "valid": not errors,
        "artifact_dir": str(root),
        "errors": errors,
        "warnings": warnings,
        "provenance": {
            "code_resolution": code_resolution,
            "consumer_resolutions": consumer_resolutions,
            "environment": environment_audit,
            "storage_location": storage_location_check,
        },
        "evidence": {
            "raw_rows": len(rows),
            "split_counts": dict(split_counts),
            "validity_gate_rows": valid_rows,
            "positive_holdout_pairs": positive_holdout,
            "hashes_checked": len(hashes),
            "total_bytes": total_bytes,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
