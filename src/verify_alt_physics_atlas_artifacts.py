#!/usr/bin/env python3
"""Verify alternative-physics atlas artifacts, schemas, hashes, and replay."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from alt_physics_atlas import (
    SCHEMA_EPISODE,
    SCHEMA_RECEIPT,
    SCHEMA_SUMMARY,
    canonical_sha256,
    classify_regime,
    deterministic_projection,
    run_episode,
    summarize,
)
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
        raise ValueError(f"expected a JSON object in {path}")
    return value


def find_nonfinite(value: Any, path: str = "$.") -> list[str]:
    errors: list[str] = []
    if isinstance(value, float) and not math.isfinite(value):
        errors.append(f"non-finite number at {path}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(find_nonfinite(item, f"{path}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            errors.extend(find_nonfinite(item, f"{path}{key}."))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Resolve code by unique project-relative suffix, not recorded absolute path.",
    )
    parser.add_argument(
        "--replay-samples",
        type=int,
        default=3,
        help="Maximum exact episode replays, selected across physics families.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optionally write the verification result as JSON.",
    )
    args = parser.parse_args()
    root = args.artifact_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(name for name in REQUIRED if not (root / name).is_file())
    if missing:
        print(
            json.dumps(
                {
                    "valid": False,
                    "artifact_dir": str(root),
                    "errors": [f"missing required artifacts: {missing}"],
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    manifest = load_json(root / "frozen_manifest.json")
    summary = load_json(root / "summary.json")
    receipt = load_json(root / "receipt.json")
    seed_manifest = load_json(root / "seed_manifest.json")
    recorded_hashes = load_json(root / "hashes.json")

    for name, record in recorded_hashes.items():
        path = root / name
        if not path.is_file():
            errors.append(f"hashed artifact missing: {name}")
            continue
        if sha256_file(path) != record.get("sha256"):
            errors.append(f"hash mismatch: {name}")
        if path.stat().st_size != int(record.get("bytes", -1)):
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
            if not isinstance(row, dict) or row.get("schema") != SCHEMA_EPISODE:
                errors.append(f"raw line {line_number} has the wrong episode schema")
                continue
            nonfinite = find_nonfinite(row, f"raw[{line_number}].")
            errors.extend(nonfinite[:5])
            rows.append(row)

    if summary.get("schema") != SCHEMA_SUMMARY:
        errors.append("summary has the wrong schema")
    if receipt.get("schema") != SCHEMA_RECEIPT:
        errors.append("receipt has the wrong schema")
    errors.extend(find_nonfinite(summary, "summary.")[:10])
    errors.extend(find_nonfinite(receipt, "receipt.")[:10])
    if summary.get("status") != "ok" or receipt.get("status") != "ok":
        errors.append("summary or receipt status is not ok")
    if len(rows) != int(summary.get("row_count", -1)):
        errors.append("raw row count does not match summary")
    if len(rows) != int(receipt.get("episode_count", -1)):
        errors.append("raw row count does not match receipt")
    if len(rows) != int(seed_manifest.get("completed_episodes", -1)):
        errors.append("raw row count does not match seed manifest")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("stored determinism audit did not pass")

    identifiers: set[tuple[Any, ...]] = set()
    classifier = manifest.get("analysis", {}).get("regime_classifier", {})
    trajectory_hash_failures = 0
    for index, row in enumerate(rows, start=1):
        condition = row["condition"]
        identifier = (
            row["split"],
            row["seed"],
            condition["family"],
            condition["profile"],
            condition["dimension"],
            condition["side"],
        )
        if identifier in identifiers:
            errors.append(f"duplicate experimental unit: {identifier}")
        identifiers.add(identifier)
        expected_solver_exposure = int(condition["cell_count"]) * int(
            condition["solver_steps"]
        )
        if int(row["exposure"]["solver_site_evaluations"]) != expected_solver_exposure:
            errors.append(f"solver exposure mismatch at row {index}")
        expected_record_exposure = int(condition["cell_count"]) * int(
            condition["recorded_steps"]
        )
        if int(row["exposure"]["recorded_site_observations"]) != expected_record_exposure:
            errors.append(f"record exposure mismatch at row {index}")
        if len(row["trajectory"]) != int(condition["recorded_steps"]):
            errors.append(f"trajectory length mismatch at row {index}")
        if canonical_sha256(row["trajectory"]) != row["provenance"]["trajectory_sha256"]:
            trajectory_hash_failures += 1
        expected_regime = classify_regime(row["outcomes"], classifier)
        if expected_regime != row["outcomes"]["regime"]:
            errors.append(f"classifier mismatch at row {index}")
        if bool(row["outcomes"]["candidate_regime"]) != (
            expected_regime == "active_structured_candidate"
        ):
            errors.append(f"candidate flag mismatch at row {index}")
    if trajectory_hash_failures:
        errors.append(f"trajectory hash failures: {trajectory_hash_failures}")

    observed_splits = Counter(str(row["split"]) for row in rows)
    for split, expected in summary.get("episode_counts", {}).items():
        if observed_splits[split] != int(expected):
            errors.append(f"split count mismatch: {split}")
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

    recomputed = summarize(rows, manifest)
    for key in (
        "row_count",
        "condition_count",
        "episode_counts",
        "condition_summaries",
        "split_analysis",
        "goodhart_audit",
        "hypothesis_assessment",
        "exposure_audit",
    ):
        if canonical_sha256(recomputed.get(key)) != canonical_sha256(summary.get(key)):
            errors.append(f"recomputed summary mismatch: {key}")

    manifest_hash = sha256_file(root / "frozen_manifest.json")
    if manifest_hash != receipt.get("manifest_sha256"):
        errors.append("frozen manifest hash does not match receipt")
    search_roots = project_search_roots(Path(__file__), root)
    code_resolution = resolve_recorded_file(
        str(receipt.get("code_path", "")),
        str(receipt.get("code_sha256", "")),
        search_roots=search_roots,
        suffix_parts=3,
        allow_recorded_path=not args.portable,
    )
    if code_resolution["status"] != "resolved":
        errors.append("current atlas runner does not match receipt")
    dependency_resolution = resolve_recorded_file(
        str(receipt.get("geometry_dependency_path", "")),
        str(receipt.get("geometry_dependency_sha256", "")),
        search_roots=search_roots,
        suffix_parts=3,
        allow_recorded_path=not args.portable,
    )
    if dependency_resolution["status"] != "resolved":
        errors.append("geometry dependency does not match receipt")
    environment_audit = audit_runtime_environment(receipt, ["numpy", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("receipt environment fingerprint is internally inconsistent")
    if not environment_audit["runtime_exact_match"]:
        warnings.append(
            "runtime environment differs from recorded run: "
            + ", ".join(sorted(environment_audit["differences"]))
        )

    replay_results: list[dict[str, Any]] = []
    if args.replay_samples > 0 and rows:
        selected: list[Mapping[str, Any]] = []
        for family in ("binary_ca", "gray_scott", "cyclic_ca"):
            match = next(
                (row for row in rows if row["condition"]["family"] == family), None
            )
            if match is not None and match not in selected:
                selected.append(match)
        if len(selected) < args.replay_samples:
            selected.extend(row for row in rows if row not in selected)
        selected = selected[: args.replay_samples]
        design = manifest["design"]
        deadline = time.monotonic() + min(180.0, float(manifest["budget"]["max_wall_seconds"]))
        for original in selected:
            condition = original["condition"]
            replay = run_episode(
                split=str(original["split"]),
                seed=int(original["seed"]),
                family=str(condition["family"]),
                profile=condition["profile_parameters"],
                dimension=int(condition["dimension"]),
                side=int(condition["side"]),
                matched_degree=int(design["matched_degree"]),
                recorded_steps=int(condition["recorded_steps"]),
                solver_steps_per_record=int(condition["solver_steps_per_record"]),
                burn_in=int(condition["burn_in_recorded_steps"]),
                spatial_every=int(design["spatial_metric_every_recorded_steps"]),
                classifier=classifier,
                deadline=deadline,
                max_ram_mb=float(manifest["budget"]["max_ram_mb"]),
            )
            expected = canonical_sha256(deterministic_projection(original))
            actual = canonical_sha256(deterministic_projection(replay))
            replay_results.append(
                {
                    "family": condition["family"],
                    "split": original["split"],
                    "seed": original["seed"],
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                    "passed": expected == actual,
                }
            )
        if not all(row["passed"] for row in replay_results):
            errors.append("one or more verifier-triggered exact replays failed")

    budget = manifest["budget"]
    if float(receipt.get("wall_seconds", float("inf"))) > float(budget["max_wall_seconds"]):
        errors.append("wall-time budget exceeded")
    if float(receipt.get("max_rss_mb", float("inf"))) > float(budget["max_ram_mb"]):
        errors.append("RAM budget exceeded")
    if len(rows) > int(budget["max_episodes"]):
        errors.append("episode budget exceeded")
    total_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        errors.append("artifact disk budget exceeded")
    storage_check = {
        "intended_prefix": "D:\\",
        "actual_path": str(root),
        "matches": str(root).lower().startswith("d:\\"),
        "affects_validity": False,
    }
    if not storage_check["matches"]:
        warnings.append("artifact directory does not resolve to the intended D drive")

    result = {
        "valid": not errors,
        "artifact_dir": str(root),
        "errors": errors,
        "warnings": warnings,
        "evidence": {
            "raw_rows": len(rows),
            "condition_count": summary.get("condition_count"),
            "split_counts": dict(observed_splits),
            "trajectory_hash_failures": trajectory_hash_failures,
            "artifact_hashes_checked": len(recorded_hashes),
            "replay_samples": replay_results,
            "total_bytes": total_bytes,
        },
        "provenance": {
            "code_resolution": code_resolution,
            "geometry_dependency_resolution": dependency_resolution,
            "environment": environment_audit,
            "storage": storage_check,
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
