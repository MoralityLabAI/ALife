#!/usr/bin/env python3
"""Verify geometry-averaging artifacts against their frozen manifest and hashes."""

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
    "phase_map.csv",
    "seed_manifest.json",
    "frozen_manifest.json",
    "receipt.json",
    "knowledge_card.md",
    "hashes.json",
}


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
        errors.append(f"missing required artifacts: {missing}")
        print(json.dumps({"valid": False, "artifact_dir": str(root), "errors": errors}, indent=2))
        raise SystemExit(1)

    manifest = load_json(root / "frozen_manifest.json")
    summary = load_json(root / "summary.json")
    receipt = load_json(root / "receipt.json")
    seeds = load_json(root / "seed_manifest.json")
    recorded_hashes = load_json(root / "hashes.json")

    for name, record in recorded_hashes.items():
        path = root / name
        if not path.is_file():
            errors.append(f"hashed artifact missing: {name}")
            continue
        actual_hash = sha256_file(path)
        actual_bytes = path.stat().st_size
        if actual_hash != record.get("sha256"):
            errors.append(f"hash mismatch: {name}")
        if actual_bytes != record.get("bytes"):
            errors.append(f"byte-size mismatch: {name}")

    rows: list[dict[str, Any]] = []
    with (root / "raw_episodes.jsonl").open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"raw line {line_number} is invalid JSON: {exc}")
                continue
            if row.get("schema") != "alife.geometry_averaging.episode.v1":
                errors.append(f"raw line {line_number} has wrong schema")
            rows.append(row)

    if len(rows) != summary.get("row_count"):
        errors.append("raw row count does not match summary")
    if len(rows) != receipt.get("episode_count"):
        errors.append("raw row count does not match receipt")
    if summary.get("status") != "ok" or receipt.get("status") != "ok":
        errors.append("summary or receipt status is not ok")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("determinism receipt did not pass")

    observed_split_counts = Counter(str(row.get("split")) for row in rows)
    for split, expected in summary.get("episode_counts", {}).items():
        if observed_split_counts[split] != expected:
            errors.append(f"split count mismatch for {split}")

    identifiers: set[tuple[Any, ...]] = set()
    for index, row in enumerate(rows):
        condition = row.get("condition", {})
        identifier = (
            row.get("split"),
            row.get("seed"),
            condition.get("dimension"),
            condition.get("side"),
            condition.get("initial_density"),
            condition.get("neighborhood"),
            condition.get("rule_profile"),
        )
        if identifier in identifiers:
            errors.append(f"duplicate experimental unit: {identifier}")
        identifiers.add(identifier)
        expected_ticks = int(condition.get("cell_count", 0)) * len(row.get("trajectory", []))
        if int(row.get("exposure", {}).get("cell_ticks", -1)) != expected_ticks:
            errors.append(f"cell-tick exposure mismatch at raw row {index + 1}")

    seed_sets = {
        split: set(values)
        for split, values in manifest.get("seed_plan", {}).items()
        if split in {"discovery", "confirmatory", "holdout"} and isinstance(values, list)
    }
    for left, right in (
        ("discovery", "confirmatory"),
        ("discovery", "holdout"),
        ("confirmatory", "holdout"),
    ):
        if seed_sets.get(left, set()) & seed_sets.get(right, set()):
            errors.append(f"frozen seed splits overlap: {left}/{right}")

    manifest_hash = sha256_file(root / "frozen_manifest.json")
    if manifest_hash != receipt.get("manifest_sha256"):
        errors.append("frozen manifest hash does not match receipt")
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

    budget = manifest.get("budget", {})
    if float(receipt.get("wall_seconds", float("inf"))) > float(budget.get("max_wall_seconds", 0)):
        errors.append("wall-time budget exceeded")
    if float(receipt.get("max_rss_mb", float("inf"))) > float(budget.get("max_ram_mb", 0)):
        errors.append("RAM budget exceeded")
    if len(rows) > int(budget.get("max_episodes", 0)):
        errors.append("episode budget exceeded")
    total_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
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
            "split_counts": dict(observed_split_counts),
            "hashes_checked": len(recorded_hashes),
            "total_bytes": total_bytes,
            "determinism_passed": summary.get("determinism", {}).get("passed"),
            "status": summary.get("status"),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
