#!/usr/bin/env python3
"""Verify folded-cavern schemas, mechanics coverage, hashes, and exact replay."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from artifact_verification import (
    audit_runtime_environment,
    project_search_roots,
    resolve_recorded_file,
    sha256_file,
)
from pixie_folded_cavern import (
    SCHEMA_EPISODE,
    SCHEMA_EVENT,
    SCHEMA_RECEIPT,
    SCHEMA_SUMMARY,
    canonical_sha256,
    deterministic_projection,
    neighborhood_offsets,
    run_episode,
    summarize,
    world_shape,
)


REQUIRED = {
    "raw_episodes.jsonl",
    "summary.json",
    "mechanics_matrix.csv",
    "seed_manifest.json",
    "frozen_manifest.json",
    "world_mechanics_taxonomy.json",
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
            errors.extend(find_nonfinite(item, f"{path}[{index}]."))
    elif isinstance(value, dict):
        for key, item in value.items():
            errors.extend(find_nonfinite(item, f"{path}{key}."))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--replay-samples", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.artifact_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(name for name in REQUIRED if not (root / name).is_file())
    if missing:
        print(json.dumps({"valid": False, "errors": [f"missing: {missing}"]}, indent=2))
        raise SystemExit(1)

    manifest = load_json(root / "frozen_manifest.json")
    taxonomy = load_json(root / "world_mechanics_taxonomy.json")
    summary = load_json(root / "summary.json")
    receipt = load_json(root / "receipt.json")
    seed_manifest = load_json(root / "seed_manifest.json")
    recorded_hashes = load_json(root / "hashes.json")

    for name, record in recorded_hashes.items():
        path = root / name
        if not path.is_file():
            errors.append(f"hashed artifact missing: {name}")
        elif sha256_file(path) != record.get("sha256"):
            errors.append(f"hash mismatch: {name}")
        elif path.stat().st_size != int(record.get("bytes", -1)):
            errors.append(f"byte-size mismatch: {name}")

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        (root / "raw_episodes.jsonl").read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"raw line {line_number} invalid JSON: {exc}")
            continue
        if not isinstance(row, dict) or row.get("schema") != SCHEMA_EPISODE:
            errors.append(f"raw line {line_number} has wrong schema")
            continue
        errors.extend(find_nonfinite(row, f"raw[{line_number}].")[:5])
        rows.append(row)

    if summary.get("schema") != SCHEMA_SUMMARY:
        errors.append("summary has wrong schema")
    if receipt.get("schema") != SCHEMA_RECEIPT:
        errors.append("receipt has wrong schema")
    if taxonomy.get("schema") != "alife.pixie.world_mechanics_taxonomy.v1":
        errors.append("taxonomy has wrong schema")
    if summary.get("status") != "ok" or receipt.get("status") != "ok":
        errors.append("summary or receipt status is not ok")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("stored determinism audit did not pass")
    expected_counts = (
        summary.get("row_count"),
        receipt.get("episode_count"),
        seed_manifest.get("completed_episodes"),
    )
    if any(len(rows) != int(value if value is not None else -1) for value in expected_counts):
        errors.append("artifact episode counts disagree")

    matrix_rows = list(csv.DictReader((root / "mechanics_matrix.csv").open(encoding="utf-8")))
    expected_cells = {
        (split, neighborhood, str(dimension), critter, depth)
        for split in seed_manifest.get("splits_run", [])
        for neighborhood, dimensions in manifest["design"]["neighborhoods"].items()
        for dimension in dimensions
        for critter in manifest["design"]["critters"]
        for depth in manifest["design"]["intervention_depths"]
    }
    actual_cells = {
        (
            row.get("split", ""),
            row.get("neighborhood", ""),
            row.get("dimension", ""),
            row.get("critter", ""),
            row.get("intervention_depth", ""),
        )
        for row in matrix_rows
    }
    if actual_cells != expected_cells:
        errors.append("mechanics CSV does not cover the declared matrix")

    identifiers: set[tuple[Any, ...]] = set()
    trajectory_hash_failures = 0
    event_hash_failures = 0
    event_schema_failures = 0
    cause_failures = 0
    exposure_failures = 0
    geometry_failures = 0
    for index, row in enumerate(rows, 1):
        condition = row["condition"]
        identifier = (
            row["split"],
            row["seed"],
            condition["neighborhood"],
            condition["dimension"],
            condition["critter"],
            condition["intervention_depth"],
        )
        if identifier in identifiers:
            errors.append(f"duplicate experimental unit: {identifier}")
        identifiers.add(identifier)
        expected_shape = world_shape(
            int(condition["dimension"]), int(condition["surface_side"])
        )
        expected_degree = len(
            neighborhood_offsets(
                int(condition["dimension"]),
                str(condition["neighborhood"]),
                int(manifest["design"]["fixed_degree"]),
            )
        )
        if tuple(condition["shape"]) != expected_shape:
            geometry_failures += 1
        if int(condition["cell_count"]) != math.prod(expected_shape):
            geometry_failures += 1
        if int(condition["neighborhood_degree"]) != expected_degree:
            geometry_failures += 1
        if len(row["trajectory"]) != int(condition["steps"]):
            errors.append(f"trajectory length mismatch at row {index}")
        if canonical_sha256(row["trajectory"]) != row["provenance"]["trajectory_sha256"]:
            trajectory_hash_failures += 1
        if canonical_sha256(row["events"]) != row["provenance"]["events_sha256"]:
            event_hash_failures += 1
        event_ids = {item.get("event_id") for item in row["events"]}
        event_ticks = {item.get("event_id"): item.get("tick") for item in row["events"]}
        if len(event_ids) != len(row["events"]):
            event_schema_failures += 1
        for item in row["events"]:
            if (
                item.get("schema") != SCHEMA_EVENT
                or item.get("episode_id") != row["episode_id"]
                or not isinstance(item.get("details"), dict)
                or not isinstance(item.get("cause"), list)
            ):
                event_schema_failures += 1
            if any(cause not in event_ids for cause in item.get("cause", [])):
                cause_failures += 1
            if any(
                int(event_ticks[cause]) > int(item.get("tick", -1))
                for cause in item.get("cause", [])
                if cause in event_ticks
            ):
                cause_failures += 1
        if int(row["exposure"]["action_attempts"]) != len(condition["action_ticks"]):
            exposure_failures += 1
        if int(row["exposure"]["successful_action_ticks"]) == 0:
            exposure_failures += 1
        if int(row["exposure"]["immediate_exact_changed_sites"]) == 0:
            exposure_failures += 1
    for count, label in (
        (trajectory_hash_failures, "trajectory hash failures"),
        (event_hash_failures, "event hash failures"),
        (event_schema_failures, "event schema/ID failures"),
        (cause_failures, "event cause failures"),
        (exposure_failures, "exposure failures"),
        (geometry_failures, "geometry failures"),
    ):
        if count:
            errors.append(f"{label}: {count}")

    observed_splits = Counter(str(row["split"]) for row in rows)
    for split, expected in summary.get("episode_counts", {}).items():
        if observed_splits[split] != int(expected):
            errors.append(f"split count mismatch: {split}")
    recomputed = summarize(rows, manifest, taxonomy)
    for key in (
        "row_count",
        "condition_count",
        "episode_counts",
        "condition_summaries",
        "split_analysis",
        "hypothesis_assessment",
        "exposure_audit",
    ):
        if canonical_sha256(recomputed.get(key)) != canonical_sha256(summary.get(key)):
            errors.append(f"recomputed summary mismatch: {key}")

    if sha256_file(root / "frozen_manifest.json") != receipt.get("manifest_sha256"):
        errors.append("frozen manifest hash does not match receipt")
    if sha256_file(root / "world_mechanics_taxonomy.json") != receipt.get("taxonomy_sha256"):
        errors.append("taxonomy hash does not match receipt")
    search_roots = project_search_roots(Path(__file__), root)
    resolutions: dict[str, Any] = {}
    for key, path_key, hash_key in (
        ("runner", "code_path", "code_sha256"),
        ("atlas", "atlas_dependency_path", "atlas_dependency_sha256"),
        ("sanctuary", "sanctuary_dependency_path", "sanctuary_dependency_sha256"),
    ):
        resolutions[key] = resolve_recorded_file(
            str(receipt.get(path_key, "")),
            str(receipt.get(hash_key, "")),
            search_roots=search_roots,
            suffix_parts=2,
            allow_recorded_path=not args.portable,
        )
        if resolutions[key]["status"] != "resolved":
            errors.append(f"{key} code provenance did not resolve")
    environment_audit = audit_runtime_environment(receipt, ["numpy", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("receipt environment fingerprint is inconsistent")
    if not environment_audit["runtime_exact_match"]:
        warnings.append("runtime environment differs from the recorded run")

    replay_results: list[dict[str, Any]] = []
    selected: list[Mapping[str, Any]] = []
    for dimension in (2, 6, 11):
        match = next(
            (
                row
                for row in rows
                if int(row["condition"]["dimension"]) == dimension
                and row["condition"]["neighborhood"] == "fixed_degree_16"
                and row["condition"]["intervention_depth"] == "axis_probe"
            ),
            None,
        )
        if match is not None:
            selected.append(match)
    selected = selected[: max(0, args.replay_samples)]
    deadline = time.monotonic() + min(180.0, float(manifest["budget"]["max_wall_seconds"]))
    design = manifest["design"]
    for original in selected:
        condition = original["condition"]
        replay = run_episode(
            split=str(original["split"]),
            seed=int(original["seed"]),
            critter=str(condition["critter"]),
            action=str(condition["action"]),
            profile=condition["profile_parameters"],
            dimension=int(condition["dimension"]),
            neighborhood=str(condition["neighborhood"]),
            intervention_depth=str(condition["intervention_depth"]),
            surface_side=int(condition["surface_side"]),
            fixed_degree=int(design["fixed_degree"]),
            steps=int(condition["steps"]),
            solver_steps_per_record=int(condition["solver_steps_per_record"]),
            action_ticks=condition["action_ticks"],
            tail_ticks=min(int(design["tail_ticks"]), int(condition["steps"])),
            thresholds=manifest["analysis"]["thresholds"],
            pixie=design["pixie"],
            deadline=deadline,
            max_ram_mb=float(manifest["budget"]["max_ram_mb"]),
        )
        expected = canonical_sha256(deterministic_projection(original))
        actual = canonical_sha256(deterministic_projection(replay))
        replay_results.append(
            {
                "dimension": condition["dimension"],
                "passed": expected == actual,
                "expected_sha256": expected,
                "actual_sha256": actual,
            }
        )
    if not all(item["passed"] for item in replay_results):
        errors.append("one or more verifier-triggered exact replays failed")

    budget = manifest["budget"]
    total_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    if float(receipt.get("wall_seconds", math.inf)) > float(budget["max_wall_seconds"]):
        errors.append("wall-time budget exceeded")
    if float(receipt.get("max_rss_mb", math.inf)) > float(budget["max_ram_mb"]):
        errors.append("RAM budget exceeded")
    if len(rows) > int(budget["max_episodes"]):
        errors.append("episode budget exceeded")
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        errors.append("artifact disk budget exceeded")

    result = {
        "valid": not errors,
        "artifact_dir": str(root),
        "errors": errors,
        "warnings": warnings,
        "evidence": {
            "raw_rows": len(rows),
            "matrix_cells": len(actual_cells),
            "split_counts": dict(observed_splits),
            "artifact_hashes_checked": len(recorded_hashes),
            "replay_samples": replay_results,
            "total_bytes": total_bytes,
        },
        "provenance": {"code": resolutions, "environment": environment_audit},
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
