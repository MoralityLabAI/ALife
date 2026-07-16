#!/usr/bin/env python3
"""Verify Chronicle gate-adventure artifacts and replay every fixture case."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from adventure_verifiers.chronicle_campaign import (
    CASE_SCHEMA,
    RECEIPT_SCHEMA,
    SUMMARY_SCHEMA,
    run_cases,
    summarize,
    verifier_catalog,
)
from adventure_verifiers.core import canonical_sha256
from adventure_verifiers.verifiers import verify_adventure
from artifact_verification import (
    audit_runtime_environment,
    project_search_roots,
    resolve_recorded_file,
    sha256_file,
)


REQUIRED = {
    "cases.jsonl",
    "summary.json",
    "verifier_catalog.json",
    "frozen_manifest.json",
    "verifier_taxonomy.json",
    "receipt.json",
    "hashes.json",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--skip-source-replay", action="store_true")
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
    taxonomy = load_json(root / "verifier_taxonomy.json")
    summary = load_json(root / "summary.json")
    catalog = load_json(root / "verifier_catalog.json")
    receipt = load_json(root / "receipt.json")
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
        (root / "cases.jsonl").read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"case line {line_number} invalid JSON: {exc}")
            continue
        if not isinstance(row, dict) or row.get("schema") != CASE_SCHEMA:
            errors.append(f"case line {line_number} has wrong schema")
            continue
        rows.append(row)

    if summary.get("schema") != SUMMARY_SCHEMA:
        errors.append("summary has wrong schema")
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") != "ok":
        errors.append("receipt schema or status is invalid")
    if taxonomy.get("schema") != "alife.adventure.verifier_taxonomy.v2":
        errors.append("verifier taxonomy has wrong schema")
    if catalog != verifier_catalog():
        errors.append("stored verifier catalog differs from current registry")
    if len(rows) != int(summary.get("case_count", -1)) or len(rows) != int(
        receipt.get("case_count", -1)
    ):
        errors.append("case counts disagree")

    suite_mismatches = 0
    expectation_mismatches = 0
    targeted_mismatches = 0
    for row in rows:
        suite = verify_adventure(row["task"], row["trace"], row["environment"])
        if canonical_sha256(suite) != row.get("verification_sha256"):
            suite_mismatches += 1
        if canonical_sha256(suite) != canonical_sha256(row.get("verification")):
            suite_mismatches += 1
        if bool(suite["accepted"]) != bool(row["expected_accept"]):
            expectation_mismatches += 1
        expected_failure = row.get("expected_failure")
        targeted = (
            True
            if expected_failure is None
            else bool(suite["configuration_errors"])
            if expected_failure == "configuration"
            else expected_failure in suite["failed_required_verifiers"]
        )
        if not targeted:
            targeted_mismatches += 1
    if suite_mismatches:
        errors.append(f"stored suite re-verification mismatches: {suite_mismatches}")
    if expectation_mismatches:
        errors.append(f"case acceptance expectation mismatches: {expectation_mismatches}")
    if targeted_mismatches:
        errors.append(f"targeted failure mismatches: {targeted_mismatches}")

    recomputed = summarize(rows, summary.get("replay_results", []))
    for key in (
        "case_count",
        "split_counts",
        "scenario_count",
        "scenario_summary",
        "expectation_match_count",
        "valid_acceptance_count",
        "tamper_rejection_count",
        "targeted_failure_count",
        "hypothesis_assessment",
    ):
        if canonical_sha256(recomputed.get(key)) != canonical_sha256(summary.get(key)):
            errors.append(f"recomputed summary mismatch: {key}")

    source_replay: dict[str, Any] = {"performed": False, "passed": None}
    if not args.skip_source_replay:
        replay_rows, replay_results = run_cases(manifest, root / "frozen_manifest.json")
        passed = canonical_sha256(replay_rows) == canonical_sha256(rows)
        passed = passed and canonical_sha256(replay_results) == canonical_sha256(
            summary.get("replay_results", [])
        )
        source_replay = {
            "performed": True,
            "passed": passed,
            "case_sha256": canonical_sha256(replay_rows),
        }
        if not passed:
            errors.append("Chronicle stream and case replay did not project exactly")

    if sha256_file(root / "frozen_manifest.json") != receipt.get("manifest_sha256"):
        errors.append("manifest hash does not match receipt")
    if sha256_file(root / "verifier_taxonomy.json") != receipt.get("taxonomy_sha256"):
        errors.append("taxonomy hash does not match receipt")

    search_roots = project_search_roots(Path(__file__), root)
    resolutions: dict[str, Any] = {}
    for key, path_key, hash_key in (
        ("campaign", "code_path", "code_sha256"),
        ("core", "core_path", "core_sha256"),
        ("verifiers", "verifiers_path", "verifiers_sha256"),
        ("adapters", "adapters_path", "adapters_sha256"),
    ):
        resolutions[key] = resolve_recorded_file(
            str(receipt.get(path_key, "")),
            str(receipt.get(hash_key, "")),
            search_roots=search_roots,
            suffix_parts=3,
            allow_recorded_path=not args.portable,
        )
        if resolutions[key]["status"] != "resolved":
            errors.append(f"{key} code provenance did not resolve")
    environment_audit = audit_runtime_environment(receipt, ["psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("receipt environment fingerprint is inconsistent")
    if not environment_audit["runtime_exact_match"]:
        warnings.append("runtime environment differs from the recorded run")

    budget = manifest["budget"]
    total_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    if float(receipt.get("wall_seconds", math.inf)) > float(budget["max_wall_seconds"]):
        errors.append("wall-time budget exceeded")
    if float(receipt.get("max_rss_mb", math.inf)) > float(budget["max_ram_mb"]):
        errors.append("RAM budget exceeded")
    if len(rows) > int(budget["max_episodes"]):
        errors.append("case budget exceeded")
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        errors.append("disk budget exceeded")

    result = {
        "valid": not errors,
        "artifact_dir": str(root),
        "errors": errors,
        "warnings": warnings,
        "evidence": {
            "case_count": len(rows),
            "scenario_counts": dict(sorted(Counter(row["scenario"] for row in rows).items())),
            "suite_mismatches": suite_mismatches,
            "expectation_mismatches": expectation_mismatches,
            "targeted_failure_mismatches": targeted_mismatches,
            "artifact_hashes_checked": len(recorded_hashes),
            "source_replay": source_replay,
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
