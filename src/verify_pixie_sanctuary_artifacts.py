#!/usr/bin/env python3
"""Verify Pixie sanctuary schemas, taxonomy coverage, hashes, and exact replay."""

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
from pixie_sanctuary import (
    SCHEMA_EPISODE,
    SCHEMA_EVENT,
    SCHEMA_RECEIPT,
    SCHEMA_SUMMARY,
    canonical_sha256,
    deterministic_projection,
    run_episode,
    summarize,
)


REQUIRED = {
    "raw_episodes.jsonl",
    "summary.json",
    "taxonomy_matrix.csv",
    "seed_manifest.json",
    "frozen_manifest.json",
    "mechanics_taxonomy.json",
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
    taxonomy = load_json(root / "mechanics_taxonomy.json")
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
    if taxonomy.get("schema") != "alife.pixie.mechanics_taxonomy.v1":
        errors.append("taxonomy has wrong schema")
    if summary.get("status") != "ok" or receipt.get("status") != "ok":
        errors.append("summary or receipt status is not ok")
    if not summary.get("determinism", {}).get("passed"):
        errors.append("stored determinism audit did not pass")
    for expected in (
        summary.get("row_count"),
        receipt.get("episode_count"),
        seed_manifest.get("completed_episodes"),
    ):
        if len(rows) != int(expected if expected is not None else -1):
            errors.append("artifact episode counts disagree")
            break

    critters = list(taxonomy.get("implemented_matrix", {}).get("critters", []))
    actions = list(taxonomy.get("implemented_matrix", {}).get("actions", []))
    if len(critters) * len(actions) != taxonomy.get("implemented_matrix", {}).get(
        "cell_count"
    ):
        errors.append("taxonomy matrix cell count is inconsistent")
    matrix_rows = list(csv.DictReader((root / "taxonomy_matrix.csv").open(encoding="utf-8")))
    expected_matrix_cells = {
        (split, critter, action)
        for split in seed_manifest.get("splits_run", [])
        for critter in critters
        for action in actions
    }
    actual_matrix_cells = {
        (row.get("split", ""), row.get("critter", ""), row.get("action", ""))
        for row in matrix_rows
    }
    if actual_matrix_cells != expected_matrix_cells:
        errors.append("taxonomy CSV does not cover the declared matrix")

    identifiers: set[tuple[Any, ...]] = set()
    trajectory_hash_failures = 0
    event_hash_failures = 0
    event_schema_failures = 0
    cause_failures = 0
    exposure_failures = 0
    for index, row in enumerate(rows, 1):
        condition = row["condition"]
        identifier = (
            row["split"],
            row["seed"],
            condition["critter"],
            condition["action"],
        )
        if identifier in identifiers:
            errors.append(f"duplicate experimental unit: {identifier}")
        identifiers.add(identifier)
        if len(row["trajectory"]) != int(condition["steps"]):
            errors.append(f"trajectory length mismatch at row {index}")
        if canonical_sha256(row["trajectory"]) != row["provenance"]["trajectory_sha256"]:
            trajectory_hash_failures += 1
        if canonical_sha256(row["events"]) != row["provenance"]["events_sha256"]:
            event_hash_failures += 1
        event_ids = {item.get("event_id") for item in row["events"]}
        if len(event_ids) != len(row["events"]):
            event_schema_failures += 1
        for item in row["events"]:
            if (
                item.get("schema") != SCHEMA_EVENT
                or item.get("episode_id") != row["episode_id"]
                or not isinstance(item.get("tick"), int)
                or not isinstance(item.get("details"), dict)
                or not isinstance(item.get("cause"), list)
            ):
                event_schema_failures += 1
            if any(cause not in event_ids for cause in item.get("cause", [])):
                cause_failures += 1
        expected_attempts = len(condition["action_ticks"])
        if int(row["exposure"]["action_attempts"]) != expected_attempts:
            exposure_failures += 1
        if condition["action"] == "observe":
            if row["outcomes"]["peak_divergent_fraction"] != 0.0:
                exposure_failures += 1
        elif int(row["exposure"]["successful_action_ticks"]) == 0:
            exposure_failures += 1
    if trajectory_hash_failures:
        errors.append(f"trajectory hash failures: {trajectory_hash_failures}")
    if event_hash_failures:
        errors.append(f"event hash failures: {event_hash_failures}")
    if event_schema_failures:
        errors.append(f"event schema/ID failures: {event_schema_failures}")
    if cause_failures:
        errors.append(f"event cause failures: {cause_failures}")
    if exposure_failures:
        errors.append(f"exposure failures: {exposure_failures}")

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
    if sha256_file(root / "mechanics_taxonomy.json") != receipt.get("taxonomy_sha256"):
        errors.append("taxonomy hash does not match receipt")
    search_roots = project_search_roots(Path(__file__), root)
    resolutions: dict[str, Any] = {}
    for key, path_key, hash_key in (
        ("runner", "code_path", "code_sha256"),
        ("atlas", "alt_dependency_path", "alt_dependency_sha256"),
        ("geometry", "geometry_dependency_path", "geometry_dependency_sha256"),
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
    for critter in critters:
        match = next((row for row in rows if row["condition"]["critter"] == critter), None)
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
            side=int(condition["side"]),
            steps=int(condition["steps"]),
            solver_steps_per_record=int(condition["solver_steps_per_record"]),
            action_ticks=condition["action_ticks"],
            shield_duration=int(design["shield_duration_ticks"]),
            matched_degree=int(condition["matched_degree"]),
            tail_ticks=min(int(design["response_tail_ticks"]), int(condition["steps"])),
            thresholds=manifest["analysis"]["response_thresholds"],
            pixie=design["pixie"],
            deadline=deadline,
            max_ram_mb=float(manifest["budget"]["max_ram_mb"]),
        )
        replay["condition"]["preferred_action"] = bool(condition["preferred_action"])
        expected = canonical_sha256(deterministic_projection(original))
        actual = canonical_sha256(deterministic_projection(replay))
        replay_results.append(
            {
                "critter": condition["critter"],
                "seed": original["seed"],
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
            "matrix_cells": len(actual_matrix_cells),
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
