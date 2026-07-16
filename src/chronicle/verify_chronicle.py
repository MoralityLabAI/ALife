"""Validate and exactly replay sampled ALife chronicle corpus episodes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from chronicle.campaign import (  # type: ignore[no-redef]
        REPLAY_SCHEMA,
        SOURCE_FILES,
        canonical_hash,
        create_bundle,
        run_episode_events,
        sha256_bytes,
        sha256_file,
        source_receipt,
        write_json,
        write_manifest_md,
    )
    from chronicle.events import canonical_jsonl, read_events, validate_stream  # type: ignore[no-redef]
    from chronicle.export_sft import (  # type: ignore[no-redef]
        export_sft_records,
        validate_sft_record,
    )
    from chronicle.legends import (  # type: ignore[no-redef]
        compile_legends,
        validate_legends,
    )
else:
    from .campaign import (
        REPLAY_SCHEMA,
        SOURCE_FILES,
        canonical_hash,
        create_bundle,
        run_episode_events,
        sha256_bytes,
        sha256_file,
        source_receipt,
        write_json,
        write_manifest_md,
    )
    from .events import canonical_jsonl, read_events, validate_stream
    from .export_sft import export_sft_records, validate_sft_record
    from .legends import compile_legends, validate_legends

from artifact_verification import audit_runtime_environment


VERIFICATION_SCHEMA = "alife.chronicle.verification.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sample_rows(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count <= 0:
        raise ValueError("sample count must be positive")
    if count >= len(rows):
        return rows
    ranked = sorted(
        rows,
        key=lambda row: sha256_bytes(
            f"chronicle-replay-sample:{row['episode_id']}".encode("utf-8")
        ),
    )
    return sorted(ranked[:count], key=lambda row: row["episode_id"])


def _replay_receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema",
        "episode_id",
        "seed",
        "config_sha256",
        "code_sha256",
        "event_sha256",
        "final_state_sha256",
        "receipt_id",
    )
    return {key: row[key] for key in keys}


def verify(root: Path, *, sample: int, portable: bool) -> dict[str, Any]:
    started_utc = utc_now()
    started = time.monotonic()
    errors: list[str] = []
    warnings: list[str] = []
    replay_failures: list[dict[str, Any]] = []
    required = (
        "campaign_receipt.json",
        "episodes.jsonl",
        "frozen_manifest.json",
        "seed_manifest.json",
        "summary.json",
    )
    for name in required:
        if not (root / name).is_file():
            errors.append(f"missing required artifact: {name}")
    if errors:
        return {
            "schema": VERIFICATION_SCHEMA,
            "status": "failed",
            "started_utc": started_utc,
            "ended_utc": utc_now(),
            "wall_seconds": time.monotonic() - started,
            "portable": portable,
            "sampled_episodes": 0,
            "validated_event_streams": 0,
            "validated_legends": 0,
            "validated_sft_files": 0,
            "replay_failures": replay_failures,
            "errors": errors,
            "warnings": warnings,
        }

    campaign = _read_json(root / "campaign_receipt.json")
    manifest = _read_json(root / "frozen_manifest.json")
    summary = _read_json(root / "summary.json")
    rows = read_events(root / "episodes.jsonl")
    if campaign.get("status") != "ok" or summary.get("status") != "ok":
        errors.append("campaign receipt or summary status is not ok")
    if len(rows) != campaign.get("episode_count") or len(rows) != summary.get("episode_count"):
        errors.append("episode index, campaign receipt, and summary counts disagree")
    if sha256_file(root / "frozen_manifest.json") != campaign.get("manifest_sha256"):
        errors.append("frozen manifest hash does not match campaign receipt")

    snapshot_hashes: dict[str, str] = {}
    for relative in SOURCE_FILES:
        snapshot = root / "source" / relative
        if not snapshot.is_file():
            errors.append(f"missing portable source snapshot: source/{relative}")
            continue
        actual = sha256_file(snapshot)
        snapshot_hashes[relative] = actual
        expected = campaign.get("files", {}).get(relative)
        if actual != expected:
            errors.append(f"source snapshot hash mismatch: {relative}")
    if snapshot_hashes and canonical_hash(snapshot_hashes) != campaign.get("code_sha256"):
        errors.append("portable source aggregate code hash mismatch")

    project_root = Path(__file__).resolve().parents[2]
    try:
        current_code = source_receipt(project_root)
        code_matches = current_code["code_sha256"] == campaign.get("code_sha256")
    except (FileNotFoundError, OSError) as exc:
        code_matches = False
        current_code = {"error": str(exc)}
    if not code_matches:
        errors.append("current replay implementation does not match recorded code hash")

    environment_audit = audit_runtime_environment(campaign, ["numpy", "psutil"])
    if not environment_audit["receipt_environment_hash_valid"]:
        errors.append("campaign environment receipt hash is internally inconsistent")
    if not environment_audit["runtime_exact_match"]:
        warnings.append(
            "runtime environment differs from generation receipt: "
            + ", ".join(sorted(environment_audit["differences"]))
        )

    budget = manifest["budget"]
    if float(campaign.get("wall_seconds", float("inf"))) > float(budget["max_wall_seconds"]):
        errors.append("campaign exceeded wall-time budget")
    if float(campaign.get("max_rss_mb", float("inf"))) > float(budget["max_ram_mb"]):
        errors.append("campaign exceeded RAM budget")
    if int(campaign.get("artifact_bytes", 2**63 - 1)) > int(float(budget["max_disk_mb"]) * 1024 * 1024):
        errors.append("campaign exceeded disk budget")
    if not portable:
        recorded_output = Path(str(campaign.get("output_path", "")))
        if recorded_output.resolve() != root.resolve():
            errors.append("artifact root differs from recorded output path; use --portable")

    validated_event_streams = 0
    validated_legends = 0
    validated_sft_files = 0
    rederived_legends = 0
    rederived_sft_files = 0
    aggregate_types: Counter[str] = Counter()
    total_events = 0
    row_by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        episode_id = str(row.get("episode_id", ""))
        if not episode_id:
            errors.append(f"episode index row {index} lacks episode_id")
            continue
        if episode_id in row_by_id:
            errors.append(f"duplicate episode_id: {episode_id}")
            continue
        row_by_id[episode_id] = row
        episode_root = root / "episodes" / episode_id
        for name in ("config.json", "events.jsonl", "legends.json", "sft.jsonl", "receipt.json"):
            if not (episode_root / name).is_file():
                errors.append(f"{episode_id}: missing {name}")
        if errors and not (episode_root / "events.jsonl").is_file():
            continue
        stored_receipt = _read_json(episode_root / "receipt.json")
        if stored_receipt != row:
            errors.append(f"{episode_id}: index row differs from receipt.json")
        for name, expected in row.get("artifact_hashes", {}).items():
            path = episode_root / name
            if path.is_file() and sha256_file(path) != expected:
                errors.append(f"{episode_id}: artifact hash mismatch for {name}")
        config = _read_json(episode_root / "config.json")
        if canonical_hash(config) != row.get("config_sha256"):
            errors.append(f"{episode_id}: config hash mismatch")
        event_bytes = (episode_root / "events.jsonl").read_bytes()
        if sha256_bytes(event_bytes) != row.get("event_sha256"):
            errors.append(f"{episode_id}: event hash mismatch")
        events = read_events(episode_root / "events.jsonl")
        stream_errors = validate_stream(events)
        if stream_errors:
            errors.extend(f"{episode_id}: {error}" for error in stream_errors[:10])
        else:
            validated_event_streams += 1
        if len(events) != row.get("event_count"):
            errors.append(f"{episode_id}: receipt event count mismatch")
        total_events += len(events)
        aggregate_types.update(event["event_type"] for event in events)
        legends = _read_json(episode_root / "legends.json")
        legend_errors = validate_legends(legends)
        if legend_errors:
            errors.extend(f"{episode_id}: legends: {error}" for error in legend_errors)
        elif legends.get("event_count") != len(events):
            errors.append(f"{episode_id}: legends event count mismatch")
        else:
            validated_legends += 1
            if not stream_errors:
                expected_legends = compile_legends(events)
                if legends != expected_legends:
                    errors.append(f"{episode_id}: legends differ from compiler output")
                else:
                    rederived_legends += 1
        sft_records = read_events(episode_root / "sft.jsonl")
        sft_errors = [
            error
            for record in sft_records
            for error in validate_sft_record(record)
        ]
        if not sft_records:
            sft_errors.append("SFT file must contain at least one record")
        if sft_errors:
            errors.extend(f"{episode_id}: SFT: {error}" for error in sft_errors[:10])
        else:
            validated_sft_files += 1
            if not stream_errors and not legend_errors:
                expected_sft = export_sft_records(
                    events,
                    seed=int(config["seed"]),
                    replay_receipt=_replay_receipt(row),
                    legends=legends,
                    max_window_events=int(
                        manifest["design"]["sft"]["max_window_events"]
                    ),
                    max_biographies=int(
                        manifest["design"]["sft"]["max_biographies_per_episode"]
                    ),
                )
                if canonical_jsonl(expected_sft) != (episode_root / "sft.jsonl").read_bytes():
                    errors.append(f"{episode_id}: SFT differs from fact compiler output")
                else:
                    rederived_sft_files += 1

    if total_events != summary.get("total_events"):
        errors.append("recomputed total event count differs from summary")
    if dict(sorted(aggregate_types.items())) != summary.get("event_type_counts"):
        errors.append("recomputed event-type counts differ from summary")
    # Accept either the original v1 summary projection (native focus + lattice
    # dimensions) or the later uniform plane/dimension/degree projection.  The
    # episode configs remain the source of truth in both layouts.
    if "counts_by_native_plane_focus" in summary:
        native_plane_counts = Counter(
            str(row["world"]["plane_focus"])
            for row in rows
            if row["world"]["family"] == "native_multiplane"
        )
        dimension_counts = Counter(
            str(row["world"]["dimension"])
            for row in rows
            if row["world"]["family"] != "native_multiplane"
        )
        neighborhood_counts = Counter(
            str(row["world"]["neighborhood"])
            for row in rows
            if row["world"]["family"] != "native_multiplane"
        )
        if dict(sorted(native_plane_counts.items())) != summary.get(
            "counts_by_native_plane_focus"
        ):
            errors.append("recomputed native plane-focus counts differ from summary")
        if dict(sorted(dimension_counts.items(), key=lambda item: int(item[0]))) != summary.get(
            "counts_by_dimension"
        ):
            errors.append("recomputed lattice dimension counts differ from summary")
        if dict(sorted(neighborhood_counts.items())) != summary.get(
            "counts_by_neighborhood"
        ):
            errors.append("recomputed neighborhood counts differ from summary")
    else:
        plane_counts = Counter(str(row["world"]["plane"]) for row in rows)
        dimension_counts = Counter(str(row["world"]["dimension"]) for row in rows)
        degree_counts = Counter(str(row["world"]["degree"]) for row in rows)
        if dict(sorted(plane_counts.items())) != summary.get("counts_by_plane"):
            errors.append("recomputed plane counts differ from summary")
        if dict(sorted(dimension_counts.items(), key=lambda item: int(item[0]))) != summary.get(
            "counts_by_dimension"
        ):
            errors.append("recomputed dimension counts differ from summary")
        if dict(sorted(degree_counts.items(), key=lambda item: int(item[0]))) != summary.get(
            "counts_by_degree"
        ):
            errors.append("recomputed degree counts differ from summary")

    selected = _sample_rows(rows, min(sample, len(rows))) if rows else []
    max_episode_seconds = min(
        float(budget.get("max_episode_wall_seconds", 300)), 300.0
    )
    for row in selected:
        episode_id = str(row["episode_id"])
        episode_root = root / "episodes" / episode_id
        try:
            config = _read_json(episode_root / "config.json")
            replayed_events, diagnostics = run_episode_events(
                config,
                deadline=time.monotonic() + max_episode_seconds,
                max_ram_mb=float(budget["max_ram_mb"]),
            )
            replayed_bytes = canonical_jsonl(replayed_events)
            stored_bytes = (episode_root / "events.jsonl").read_bytes()
            if replayed_bytes != stored_bytes:
                replay_failures.append(
                    {
                        "episode_id": episode_id,
                        "component": "events.jsonl",
                        "expected_sha256": sha256_bytes(stored_bytes),
                        "actual_sha256": sha256_bytes(replayed_bytes),
                    }
                )
                continue
            if diagnostics["final_state_sha256"] != row.get("final_state_sha256"):
                replay_failures.append(
                    {"episode_id": episode_id, "component": "final_state_sha256"}
                )
                continue
            replayed_legends = compile_legends(replayed_events)
            if replayed_legends != _read_json(episode_root / "legends.json"):
                replay_failures.append(
                    {"episode_id": episode_id, "component": "legends.json"}
                )
                continue
            replayed_sft = export_sft_records(
                replayed_events,
                seed=int(config["seed"]),
                replay_receipt=_replay_receipt(row),
                legends=replayed_legends,
                max_window_events=int(manifest["design"]["sft"]["max_window_events"]),
                max_biographies=int(
                    manifest["design"]["sft"]["max_biographies_per_episode"]
                ),
            )
            if canonical_jsonl(replayed_sft) != (episode_root / "sft.jsonl").read_bytes():
                replay_failures.append(
                    {"episode_id": episode_id, "component": "sft.jsonl"}
                )
        except (MemoryError, TimeoutError, RuntimeError, ValueError, OSError) as exc:
            replay_failures.append(
                {
                    "episode_id": episode_id,
                    "component": "exception",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    if replay_failures:
        errors.append(f"{len(replay_failures)} sampled episode replay(s) failed")

    receipt = {
        "schema": VERIFICATION_SCHEMA,
        "status": "passed" if not errors else "failed",
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "portable": portable,
        "episode_count": len(rows),
        "sampled_episodes": len(selected),
        "sampled_episode_ids": [row["episode_id"] for row in selected],
        "validated_event_streams": validated_event_streams,
        "validated_legends": validated_legends,
        "validated_sft_files": validated_sft_files,
        "rederived_legends": rederived_legends,
        "rederived_sft_files": rederived_sft_files,
        "exact_event_byte_replays_passed": len(selected) - len(replay_failures),
        "replay_failures": replay_failures,
        "code_hash_matches": code_matches,
        "recorded_code_sha256": campaign.get("code_sha256"),
        "current_code": current_code,
        "environment": environment_audit,
        "errors": errors,
        "warnings": warnings,
    }
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--sample", type=int, default=24)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    receipt = verify(root, sample=args.sample, portable=args.portable)
    write_json(root / "verification_receipt.json", receipt)
    write_manifest_md(root)
    if receipt["status"] == "passed" and args.bundle is not None:
        create_bundle(root, args.bundle.resolve())
    print(json.dumps(receipt, indent=2, sort_keys=True))
    raise SystemExit(0 if receipt["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
