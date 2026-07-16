#!/usr/bin/env python3
"""Verify schemas, metric firewall, hashes, hard checks, and sampled replay."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Mapping

from agent_mechinterp.analysis import analyze_decisions
from agent_mechinterp.campaign import _episode, load_object, summarize, tamper_audit
from agent_mechinterp.core import (
    RECEIPT_SCHEMA,
    ROW_SCHEMA,
    SUMMARY_SCHEMA,
    CanaryPolicy,
    canonical_sha256,
    verify_harness_row,
)
from artifact_verification import (
    audit_runtime_environment,
    project_search_roots,
    resolve_recorded_file,
    sha256_file,
)
from pixie_sanctuary import deterministic_projection


REQUIRED = {
    "decisions.jsonl",
    "summary.json",
    "seed_manifest.json",
    "frozen_manifest.json",
    "mechinterp_taxonomy.json",
    "source_pixie_manifest.json",
    "receipt.json",
    "knowledge_card.md",
    "hashes.json",
}


def _rows(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON at decisions line {number}: {exc}")
            continue
        if not isinstance(row, dict) or row.get("schema") != ROW_SCHEMA:
            errors.append(f"wrong row schema at decisions line {number}")
            continue
        rows.append(row)
    return rows


def verify_artifacts(
    root: Path, *, portable: bool = False, replay_samples: int = 6
) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(name for name in REQUIRED if not (root / name).is_file())
    if missing:
        return {"valid": False, "errors": [f"missing artifacts: {missing}"]}
    manifest = load_object(root / "frozen_manifest.json")
    taxonomy = load_object(root / "mechinterp_taxonomy.json")
    source_manifest = load_object(root / "source_pixie_manifest.json")
    summary = load_object(root / "summary.json")
    receipt = load_object(root / "receipt.json")
    hashes = load_object(root / "hashes.json")
    if summary.get("schema") != SUMMARY_SCHEMA:
        errors.append("wrong summary schema")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        errors.append("wrong receipt schema")
    if summary.get("cognition_claim") is not False:
        errors.append("artifact must not make a cognition claim")
    for name, record in hashes.items():
        path = root / name
        if not path.is_file():
            errors.append(f"hashed artifact missing: {name}")
        elif sha256_file(path) != record.get("sha256"):
            errors.append(f"hash mismatch: {name}")
        elif path.stat().st_size != int(record.get("bytes", -1)):
            errors.append(f"byte count mismatch: {name}")
    if sha256_file(root / "frozen_manifest.json") != receipt.get("manifest_sha256"):
        errors.append("manifest receipt hash mismatch")
    if sha256_file(root / "mechinterp_taxonomy.json") != receipt.get("taxonomy_sha256"):
        errors.append("taxonomy receipt hash mismatch")
    if sha256_file(root / "decisions.jsonl") != receipt.get("raw_rows_sha256"):
        errors.append("raw-row receipt hash mismatch")
    if sha256_file(root / "summary.json") != receipt.get("summary_sha256"):
        errors.append("summary receipt hash mismatch")

    rows = _rows(root / "decisions.jsonl", errors)
    if len(rows) != int(receipt.get("row_count", -1)):
        errors.append("row count differs from receipt")
    if len(rows) != int(summary.get("row_count", -1)):
        errors.append("row count differs from summary")
    expected_ids = {
        (mode, split, int(seed), critter)
        for mode in manifest["design"]["modes"]
        for split in ("discovery", "confirmatory", "holdout")
        for seed in manifest["seed_plan"][split]
        for critter in manifest["design"]["critters"]
    }
    actual_ids = {
        (row["mode"], row["split"], int(row["seed"]), row["critter"])
        for row in rows
    }
    if actual_ids != expected_ids:
        errors.append("decision matrix does not match frozen seed/mode/critter design")
    policy = CanaryPolicy()
    hard_failures = []
    for row in rows:
        report = verify_harness_row(row, policy=policy, taxonomy=taxonomy)
        if not report["passed"]:
            hard_failures.append({"row_id": row.get("row_id"), "report": report})
        if canonical_sha256(report) != canonical_sha256(row.get("hard_verification")):
            errors.append(f"stored hard verification differs: {row.get('row_id')}")
    if hard_failures:
        errors.append(f"hard-check failures: {len(hard_failures)}")

    analysis = analyze_decisions([row["decision"] for row in rows], policy)
    tampers = tamper_audit(rows, taxonomy) if rows else []
    recomputed = summarize(rows, analysis, tampers, manifest) if rows else {}
    if canonical_sha256(recomputed) != canonical_sha256(summary):
        errors.append("summary does not re-derive from retained rows")
    if not all(item.get("passed") is True for item in tampers):
        errors.append("recomputed tamper audit did not reject every case")

    search_roots = project_search_roots(Path(__file__), root)
    resolutions: list[dict[str, Any]] = []
    for code in receipt.get("code", []):
        resolution = resolve_recorded_file(
            str(code.get("path", "")),
            str(code.get("sha256", "")),
            search_roots=search_roots,
            suffix_parts=2,
            allow_recorded_path=not portable,
        )
        resolutions.append(resolution)
        if resolution.get("status") != "resolved":
            errors.append(f"code provenance did not resolve: {code.get('path')}")
    environment_audit = audit_runtime_environment(receipt, ["numpy", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("receipt environment fingerprint is inconsistent")
    if not environment_audit["runtime_exact_match"]:
        warnings.append("verifier runtime differs from campaign runtime")

    replay_results: list[dict[str, Any]] = []
    chosen: list[Mapping[str, Any]] = []
    for mode in manifest["design"]["modes"]:
        for critter in manifest["design"]["critters"]:
            row = next(
                (
                    item
                    for item in rows
                    if item["mode"] == mode and item["critter"] == critter
                ),
                None,
            )
            if row is not None:
                chosen.append(row)
    chosen = chosen[: max(0, int(replay_samples))]
    deadline = time.monotonic() + min(
        120.0, float(manifest["budget"]["max_wall_seconds"])
    )
    source_design = source_manifest["design"]
    side = int(manifest["design"]["episode"]["side"])
    steps = int(manifest["design"]["episode"]["steps"])
    for row in chosen:
        execution = row["execution"]
        if row["mode"] == "play":
            profile = source_design["species_profiles"][row["critter"]]
            action = row["decision"]["selected_action"]
        else:
            profile = execution["edited_profile"]
            action = execution["evaluation_action"]
        replay = _episode(
            source_manifest=source_manifest,
            split=str(row["split"]),
            seed=int(row["seed"]),
            critter=str(row["critter"]),
            action=str(action),
            profile=profile,
            side=side,
            steps=steps,
            deadline=deadline,
            max_ram_mb=float(manifest["budget"]["max_ram_mb"]),
        )
        digest = canonical_sha256(deterministic_projection(replay))
        expected = execution["executed_projection_sha256"]
        passed = digest == expected
        replay_results.append(
            {"row_id": row["row_id"], "expected": expected, "actual": digest, "passed": passed}
        )
        if not passed:
            errors.append(f"source replay mismatch: {row['row_id']}")
    return {
        "schema": "alife.agent_mechinterp.artifact_verification.v1",
        "valid": not errors,
        "portable": portable,
        "errors": errors,
        "warnings": warnings,
        "row_count": len(rows),
        "hard_failure_count": len(hard_failures),
        "tamper_case_count": len(tampers),
        "replay_results": replay_results,
        "code_resolutions": resolutions,
        "environment_audit": environment_audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--replay-samples", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_artifacts(
        args.artifact_dir,
        portable=args.portable,
        replay_samples=args.replay_samples,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
