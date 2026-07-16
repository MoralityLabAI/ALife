#!/usr/bin/env python3
"""Verify vector-state graph-lab artifacts and graph invariants."""

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
        errors.append(f"missing required artifacts: {missing}")
        print(json.dumps({"valid": False, "artifact_dir": str(root), "errors": errors}, indent=2))
        raise SystemExit(1)

    manifest = load_json(root / "frozen_manifest.json")
    summary = load_json(root / "summary.json")
    receipt = load_json(root / "receipt.json")
    hashes = load_json(root / "hashes.json")
    for name, record in hashes.items():
        path = root / name
        if not path.is_file():
            errors.append(f"hashed artifact missing: {name}")
            continue
        if sha256_file(path) != record.get("sha256"):
            errors.append(f"hash mismatch: {name}")
        if path.stat().st_size != record.get("bytes"):
            errors.append(f"byte-size mismatch: {name}")

    rows: list[dict[str, Any]] = []
    with (root / "raw_episodes.jsonl").open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSONL line {line_number}: {exc}")
                continue
            if row.get("schema") != "alife.graph_state.episode.v1":
                errors.append(f"wrong episode schema at line {line_number}")
            rows.append(row)

    if len(rows) != summary.get("row_count") or len(rows) != receipt.get("episode_count"):
        errors.append("raw, summary, and receipt episode counts do not agree")
    if summary.get("status") != "ok" or receipt.get("status") != "ok":
        errors.append("campaign status is not ok")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("determinism did not pass")

    split_counts = Counter(str(row.get("split")) for row in rows)
    for split, expected in summary.get("episode_counts", {}).items():
        if split_counts[split] != expected:
            errors.append(f"split count mismatch: {split}")

    identifiers: set[tuple[Any, ...]] = set()
    for index, row in enumerate(rows, start=1):
        condition = row.get("condition", {})
        graph = row.get("graph", {})
        intervention = row.get("intervention", {})
        exposure = row.get("exposure", {})
        identifier = (
            row.get("split"),
            row.get("seed"),
            condition.get("nodes"),
            condition.get("topology"),
            condition.get("degree"),
            condition.get("state_dimension"),
            condition.get("coupling"),
        )
        if identifier in identifiers:
            errors.append(f"duplicate experimental unit: {identifier}")
        identifiers.add(identifier)
        if not graph.get("connected"):
            errors.append(f"disconnected graph at row {index}")
        if graph.get("degree_min") != condition.get("degree") or graph.get("degree_max") != condition.get("degree"):
            errors.append(f"degree invariant failure at row {index}")
        if not intervention.get("executed") or exposure.get("perturbation_executions") != 1:
            errors.append(f"perturbation exposure failure at row {index}")
        expected_node_ticks = int(condition.get("nodes", 0)) * len(row.get("trajectory", []))
        if exposure.get("node_ticks") != expected_node_ticks:
            errors.append(f"node-tick exposure mismatch at row {index}")

    seed_plan = manifest.get("seed_plan", {})
    sets = {split: set(seed_plan.get(split, [])) for split in ("discovery", "confirmatory", "holdout")}
    if sets["discovery"] & sets["confirmatory"] or sets["discovery"] & sets["holdout"] or sets["confirmatory"] & sets["holdout"]:
        errors.append("seed splits overlap")

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
        errors.append("current graph-lab code does not match receipt")
    environment_audit = audit_runtime_environment(receipt, ["numpy", "networkx", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("recorded environment fields do not match their receipt fingerprint")
    if not environment_audit["runtime_exact_match"]:
        warnings.append(
            "runtime environment differs from recorded run: "
            + ", ".join(sorted(environment_audit["differences"]))
        )

    frozen_predictor = manifest.get("analysis", {}).get("frozen_predictor")
    predictor_resolution: dict[str, Any] | None = None
    if isinstance(frozen_predictor, dict):
        original_manifest_path = Path(str(receipt.get("manifest_path", "")))
        source_path = Path(str(frozen_predictor.get("source_summary_path", "")))
        if not source_path.is_absolute():
            source_path = original_manifest_path.parent / source_path
        predictor_resolution = resolve_recorded_file(
            source_path,
            str(frozen_predictor.get("source_summary_sha256", "")),
            search_roots=search_roots,
            suffix_parts=3,
            allow_recorded_path=not args.portable,
        )
        if predictor_resolution["status"] != "resolved":
            errors.append(
                "frozen predictor source resolution failed: "
                + str(predictor_resolution["status"])
            )
        predictive = summary.get("predictive_comparison", {})
        if predictive.get("baseline_coefficients") != frozen_predictor.get("baseline_coefficients"):
            errors.append("evaluated baseline coefficients differ from frozen manifest")
        if predictive.get("spectral_coefficients") != frozen_predictor.get("spectral_coefficients"):
            errors.append("evaluated spectral coefficients differ from frozen manifest")

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
            "frozen_predictor_resolution": predictor_resolution,
            "environment": environment_audit,
            "storage_location": storage_location_check,
        },
        "evidence": {
            "raw_rows": len(rows),
            "split_counts": dict(split_counts),
            "hashes_checked": len(hashes),
            "connected_exact_degree_rows": sum(
                1
                for row in rows
                if row["graph"]["connected"]
                and row["graph"]["degree_min"] == row["condition"]["degree"]
                and row["graph"]["degree_max"] == row["condition"]["degree"]
            ),
            "perturbation_exposed_rows": sum(
                1 for row in rows if row["intervention"]["executed"]
            ),
            "total_bytes": total_bytes,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
