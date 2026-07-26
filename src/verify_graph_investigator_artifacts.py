#!/usr/bin/env python3
"""Verify graph-investigator campaign artifacts and sampled deterministic replay."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from graph_investigator_gym import (
    POLICY_SCHEMA,
    RECEIPT_SCHEMA,
    SPLITS,
    SUMMARY_SCHEMA,
    TASK_SCHEMA,
    VERIFICATION_SCHEMA,
    build_task_bank,
    canonical_sha256,
    deterministic_bank_projection,
    sha256_file,
    utc_now,
    write_json,
)


REQUIRED_FILES = (
    "raw_graph_episodes.jsonl",
    "raw_tasks.jsonl",
    "summary.json",
    "policy_freeze.json",
    "seed_manifest.json",
    "receipt.json",
    "frozen_manifest.json",
    "audit_fixtures.json",
    "knowledge_card.md",
    "hashes.json",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number} is not an object")
            rows.append(value)
    return rows


def verify_hash_manifest(output: Path, errors: list[str]) -> None:
    hashes = load_json(output / "hashes.json")
    for name, expected in hashes.items():
        path = output / name
        if not path.is_file():
            errors.append(f"hashed artifact is missing: {name}")
            continue
        observed = sha256_file(path)
        if observed != expected.get("sha256"):
            errors.append(f"artifact hash mismatch: {name}")
        if path.stat().st_size != int(expected.get("bytes", -1)):
            errors.append(f"artifact byte-count mismatch: {name}")


def select_replay_rows(
    tasks: list[dict[str, Any]], count: int
) -> list[dict[str, Any]]:
    if count <= 0 or not tasks:
        return []
    ordered = sorted(tasks, key=lambda row: row["task_id"])
    if count >= len(ordered):
        return ordered
    indices = {
        round(index * (len(ordered) - 1) / max(1, count - 1))
        for index in range(count)
    }
    return [ordered[index] for index in sorted(indices)]


def replay_tasks(
    rows: list[dict[str, Any]],
    manifest: Mapping[str, Any],
    *,
    max_ram_mb: float,
    wall_seconds: float,
) -> list[dict[str, Any]]:
    patches = {
        patch["id"]: patch for patch in manifest["design"]["patches"]
    }
    deadline = time.monotonic() + wall_seconds
    results: list[dict[str, Any]] = []
    for row in rows:
        replay, _ = build_task_bank(
            manifest,
            str(row["split"]),
            int(row["seed"]),
            patches[row["patch"]["id"]],
            deadline,
            max_ram_mb,
        )
        observed = replay["task_bank_sha256"]
        expected = row["task_bank_sha256"]
        results.append(
            {
                "task_id": row["task_id"],
                "expected_task_bank_sha256": expected,
                "observed_task_bank_sha256": observed,
                "passed": observed == expected,
            }
        )
    return results


def copy_evidence(output: Path, evidence_dir: Path) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "summary.json",
        "policy_freeze.json",
        "seed_manifest.json",
        "receipt.json",
        "hashes.json",
        "knowledge_card.md",
        "frozen_manifest.json",
        "audit_fixtures.json",
        "verification.json",
    ):
        shutil.copy2(output / name, evidence_dir / name)


def verify(
    output: Path,
    *,
    replay_samples: int,
    portable: bool,
    evidence_dir: Path | None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED_FILES:
        if not (output / name).is_file():
            errors.append(f"missing required artifact: {name}")
    if errors:
        result = {
            "schema": VERIFICATION_SCHEMA,
            "verified_utc": utc_now(),
            "passed": False,
            "errors": errors,
            "warnings": warnings,
        }
        write_json(output / "verification.json", result)
        return result

    summary = load_json(output / "summary.json")
    freeze = load_json(output / "policy_freeze.json")
    receipt = load_json(output / "receipt.json")
    manifest = load_json(output / "frozen_manifest.json")
    audit = load_json(output / "audit_fixtures.json")
    tasks = load_jsonl(output / "raw_tasks.jsonl")
    graph_rows = load_jsonl(output / "raw_graph_episodes.jsonl")
    verify_hash_manifest(output, errors)

    if summary.get("schema") != SUMMARY_SCHEMA:
        errors.append("summary schema mismatch")
    if freeze.get("schema") != POLICY_SCHEMA:
        errors.append("policy-freeze schema mismatch")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        errors.append("receipt schema mismatch")
    if summary.get("status") != "ok" or receipt.get("status") != "ok":
        errors.append("campaign or receipt status is not ok")
    if len(tasks) != int(summary.get("task_count", -1)):
        errors.append("raw task count does not match summary")
    if len(graph_rows) != int(summary.get("graph_arm_count", -1)):
        errors.append("raw graph-arm count does not match summary")
    if len(tasks) != int(manifest["budget"]["max_episodes"]):
        errors.append("full campaign did not retain the declared task count")
    if len(graph_rows) != int(manifest["budget"]["max_graph_arms"]):
        errors.append("full campaign did not retain the declared graph-arm count")
    if not audit.get("passed"):
        errors.append("audit fixture suite failed")
    if not summary.get("metric_firewall", {}).get("passed"):
        errors.append("metric firewall failed")
    if not summary.get("exposure_audit", {}).get("passed"):
        errors.append("treatment exposure audit failed")

    freeze_material = dict(freeze)
    recorded_freeze_hash = freeze_material.pop("policy_sha256", None)
    observed_freeze_hash = canonical_sha256(freeze_material)
    if recorded_freeze_hash != observed_freeze_hash:
        errors.append("policy-freeze self hash mismatch")
    if summary.get("policy_freeze_sha256") != recorded_freeze_hash:
        errors.append("summary policy-freeze hash mismatch")
    if receipt.get("policy_freeze_sha256") != recorded_freeze_hash:
        errors.append("receipt policy-freeze hash mismatch")

    expected_splits = {
        split: set(int(value) for value in manifest["seed_plan"][split])
        for split in SPLITS
    }
    for split in SPLITS:
        observed_seeds = {
            int(row["seed"]) for row in tasks if row["split"] == split
        }
        if observed_seeds != expected_splits[split]:
            errors.append(f"{split} seed set mismatch")
    if (
        expected_splits["discovery"] & expected_splits["confirmatory"]
        or expected_splits["discovery"] & expected_splits["holdout"]
        or expected_splits["confirmatory"] & expected_splits["holdout"]
    ):
        errors.append("seed splits overlap")

    seen_task_ids: set[str] = set()
    for task in tasks:
        if task.get("schema") != TASK_SCHEMA:
            errors.append(f"task schema mismatch: {task.get('task_id')}")
        task_id = str(task.get("task_id"))
        if task_id in seen_task_ids:
            errors.append(f"duplicate task id: {task_id}")
        seen_task_ids.add(task_id)
        observed_task_hash = canonical_sha256(
            deterministic_bank_projection(task)
        )
        if observed_task_hash != task.get("task_bank_sha256"):
            errors.append(f"task-bank projection hash mismatch: {task_id}")
        if task.get("policy_freeze_sha256") != recorded_freeze_hash:
            errors.append(f"task policy-freeze hash mismatch: {task_id}")
        if len(task.get("candidates", [])) != 12:
            errors.append(f"task candidate count mismatch: {task_id}")
        policies = task.get("policy_results", {})
        for policy, result in policies.items():
            if len(result.get("queried_pair_ids", [])) != 6:
                errors.append(f"query budget mismatch: {task_id}:{policy}")
            if len(set(result.get("queried_pair_ids", []))) != 6:
                errors.append(f"duplicate query: {task_id}:{policy}")
    if portable:
        absolute = [
            name
            for name, value in manifest.get("artifacts", {}).items()
            if isinstance(value, str) and (":\\" in value or value.startswith("/"))
        ]
        if absolute:
            warnings.append(
                "manifest contains absolute artifact values: " + ", ".join(absolute)
            )

    replay_rows = select_replay_rows(tasks, replay_samples)
    replay = replay_tasks(
        replay_rows,
        manifest,
        max_ram_mb=float(manifest["budget"]["max_ram_mb"]),
        wall_seconds=min(
            300.0, float(manifest["budget"]["max_wall_seconds"])
        ),
    )
    if any(not row["passed"] for row in replay):
        errors.append("sampled deterministic task-bank replay failed")

    result = {
        "schema": VERIFICATION_SCHEMA,
        "verified_utc": utc_now(),
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "required_files": len(REQUIRED_FILES),
            "task_rows": len(tasks),
            "graph_arm_rows": len(graph_rows),
            "policy_freeze_sha256": recorded_freeze_hash,
            "sampled_replays": replay,
            "portable_mode": portable,
        },
    }
    write_json(output / "verification.json", result)
    if evidence_dir is not None and result["passed"]:
        copy_evidence(output, evidence_dir)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--replay-samples", type=int, default=4)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    if args.replay_samples < 0 or args.replay_samples > 16:
        raise SystemExit("--replay-samples must be in 0..16")
    result = verify(
        args.output.resolve(),
        replay_samples=args.replay_samples,
        portable=args.portable,
        evidence_dir=args.evidence_dir.resolve() if args.evidence_dir else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
