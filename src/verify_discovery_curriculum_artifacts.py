#!/usr/bin/env python3
"""Verify hidden-oracle discovery-curriculum artifacts and incentives."""

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
EXPECTED_POLICIES = {"calibrated_investigator", "proxy_claimant", "always_abstain"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
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
        if not path.is_file():
            errors.append(f"hashed artifact missing: {name}")
        elif sha256_file(path) != record.get("sha256") or path.stat().st_size != record.get("bytes"):
            errors.append(f"hash or size mismatch: {name}")

    rows: list[dict[str, Any]] = []
    with (root / "raw_episodes.jsonl").open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("schema") != "alife.discovery_curriculum.episode.v1":
                errors.append(f"wrong schema at line {line_number}")
            rows.append(row)

    if len(rows) != summary.get("row_count") or len(rows) != receipt.get("episode_count"):
        errors.append("raw, summary, and receipt counts disagree")
    if summary.get("status") != "ok" or receipt.get("status") != "ok":
        errors.append("campaign status is not ok")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("determinism did not pass")

    identifiers: set[tuple[Any, ...]] = set()
    split_counts = Counter(str(row.get("split")) for row in rows)
    set_tasks = 0
    correct_abstentions = 0
    calibrated_claim_hits = 0
    for index, row in enumerate(rows, 1):
        family = row.get("world", {}).get("family")
        identifier = (row.get("split"), row.get("seed"), family)
        if identifier in identifiers:
            errors.append(f"duplicate experimental unit: {identifier}")
        identifiers.add(identifier)
        investigations = row.get("investigations", [])
        policies = {item.get("policy") for item in investigations}
        if policies != EXPECTED_POLICIES or len(investigations) != 3:
            errors.append(f"policy exposure failure at row {index}")
        receipt_row = row.get("oracle_receipt", {})
        if not receipt_row.get("oracle_present"):
            errors.append(f"missing oracle at row {index}")
        if not receipt_row.get("certificate"):
            errors.append(f"missing oracle certificate at row {index}")
        if family == "masked_interval":
            set_tasks += 1
            if receipt_row.get("identification") != "set" or not receipt_row.get("identifiable_with_budget"):
                errors.append(f"set-identification receipt failure at row {index}")
        if family == "masked_point":
            calibrated = next(item for item in investigations if item["policy"] == "calibrated_investigator")
            if calibrated["score"]["correct_abstention"]:
                correct_abstentions += 1
            if receipt_row.get("identifiable_with_budget"):
                errors.append(f"masked point unexpectedly identifiable at row {index}")
        calibrated = next(item for item in investigations if item["policy"] == "calibrated_investigator")
        if calibrated["action"] == "claim" and calibrated["score"]["evidence_score"] == 1.0:
            calibrated_claim_hits += 1

    for split, expected in summary.get("episode_counts", {}).items():
        if split_counts[split] != expected:
            errors.append(f"split count mismatch: {split}")
    seed_plan = manifest.get("seed_plan", {})
    seed_sets = [set(seed_plan.get(split, [])) for split in ("discovery", "confirmatory", "holdout")]
    if seed_sets[0] & seed_sets[1] or seed_sets[0] & seed_sets[2] or seed_sets[1] & seed_sets[2]:
        errors.append("seed splits overlap")

    if summary.get("always_abstain_dominant") is not False:
        errors.append("always-abstain control is dominant")
    if float(summary.get("calibrated_holdout_margin", -1)) < float(manifest["analysis"]["minimum_calibrated_margin"]):
        errors.append("calibrated holdout margin missed gate")
    if float(summary.get("set_identified_mean_evidence_score", -1)) < float(manifest["analysis"]["minimum_set_evidence_score"]):
        errors.append("set-valued reward missed gate")

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
        errors.append("current curriculum code does not match receipt")
    environment_audit = audit_runtime_environment(receipt, ["numpy", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("recorded environment fields do not match their receipt fingerprint")
    if not environment_audit["runtime_exact_match"]:
        warnings.append(
            "runtime environment differs from recorded run: "
            + ", ".join(sorted(environment_audit["differences"]))
        )

    budget = manifest.get("budget", {})
    total_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    if float(receipt.get("wall_seconds", float("inf"))) > float(budget.get("max_wall_seconds", 0)):
        errors.append("wall budget exceeded")
    if float(receipt.get("max_rss_mb", float("inf"))) > float(budget.get("max_ram_mb", 0)):
        errors.append("RAM budget exceeded")
    if len(rows) > int(budget.get("max_episodes", 0)):
        errors.append("episode budget exceeded")
    if total_bytes > float(budget.get("max_disk_mb", 0)) * 1024 * 1024:
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
            "environment": environment_audit,
            "storage_location": storage_location_check,
        },
        "evidence": {
            "raw_rows": len(rows),
            "split_counts": dict(split_counts),
            "hashes_checked": len(hashes),
            "set_identified_tasks": set_tasks,
            "correct_registered_abstentions": correct_abstentions,
            "calibrated_exact_claims": calibrated_claim_hits,
            "total_bytes": total_bytes,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
