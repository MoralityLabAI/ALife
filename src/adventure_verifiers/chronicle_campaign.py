"""Deterministic Chronicle gate-travel verifier campaign."""

from __future__ import annotations

import copy
import json
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping

import psutil

from alt_physics_atlas import git_commit, sha256_file, utc_now, write_json
from chronicle.events import EventBuilder, validate_stream

from .adapters import build_chronicle_gate_adventure
from .core import canonical_sha256
from .verifiers import VERIFIER_SPECS, verify_adventure


CASE_SCHEMA = "alife.adventure.chronicle_gate_case.v1"
SUMMARY_SCHEMA = "alife.adventure.chronicle_gate_summary.v1"
RECEIPT_SCHEMA = "alife.adventure.chronicle_gate_receipt.v1"


def _git_dirty(root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return bool(result.stdout.strip())


def _entity(entity_id: str, role: str, kind: str) -> dict[str, Any]:
    return {"id": entity_id, "role": role, "kind": kind, "species": None}


def fixture_stream(*, split: str, seed: int) -> list[dict[str, Any]]:
    """Create a small exact Chronicle with travel, cooldown, meme, and insight facts."""

    episode_id = f"chronicle-gate-{split}-{seed}"
    builder = EventBuilder(episode_id, f"chronicle-gate-world-{seed}")
    initialized = builder.emit(
        tick=0,
        event_type="world_initialized",
        plane="GENESIS",
        region="x_low_y_low",
        position=[0, 0],
        entities=[],
        details={"width": 8, "height": 8, "seed": seed, "split": split},
    )
    destination = "ECHOSPHERE" if seed % 2 == 0 else "FORGE"
    x = 1 + seed % 3
    y = 1 + (seed // 3) % 3
    outbound_anchor = [x, y]
    arrival = [5 + seed % 2, 4 + (seed // 2) % 2]
    return_anchor = [(arrival[0] + 1) % 8, arrival[1]]
    traveler_before = f"e{seed * 10 + 1:08d}"
    traveler_abroad = f"e{seed * 10 + 2:08d}"
    traveler_returned = f"e{seed * 10 + 3:08d}"
    blocked_traveler = f"e{seed * 10 + 4:08d}"
    meme_id = f"e{seed * 10 + 5:08d}"

    outbound = builder.emit(
        tick=1,
        event_type="gate_transfer",
        plane="GENESIS",
        region="x_low_y_low",
        position=outbound_anchor,
        entities=[
            _entity(traveler_before, "source", "goblin"),
            _entity(traveler_abroad, "created", "goblin"),
        ],
        cause_chain=[
            {
                "type": "gate_rule",
                "entity_ids": [traveler_before, traveler_abroad],
                "event_sequence": initialized["sequence"],
            }
        ],
        details={
            "gate": "seed_vault",
            "outcome": "placed",
            "target_plane": destination,
            "target_position": arrival,
            "anchor_offset": [1, 0],
            "anchor_position": outbound_anchor,
            "cooldown_before": 0,
            "cooldown_after": 2,
        },
    )
    builder.emit(
        tick=1,
        event_type="birth",
        plane=destination,
        region="x_high_y_high",
        position=arrival,
        entities=[_entity(traveler_abroad, "subject", "goblin")],
        cause_chain=[
            {
                "type": "gate_transfer",
                "entity_ids": [traveler_abroad],
                "event_sequence": outbound["sequence"],
            }
        ],
        details={"kind": "goblin", "species": "sage", "flavor": "gate_arrival"},
    )
    builder.emit(
        tick=2,
        event_type="gate_transfer_attempt",
        plane="GENESIS",
        region="x_low_y_low",
        position=outbound_anchor,
        entities=[_entity(blocked_traveler, "source", "goblin")],
        cause_chain=[
            {
                "type": "anchor_cooldown",
                "entity_ids": [blocked_traveler],
                "event_sequence": outbound["sequence"],
            }
        ],
        details={
            "gate": "seed_vault",
            "outcome": "cooldown_active",
            "target_plane": destination,
            "target_position": arrival,
            "anchor_offset": [1, 0],
            "anchor_position": outbound_anchor,
            "cooldown_before": 1,
            "cooldown_after": 1,
        },
    )
    meme = builder.emit(
        tick=2,
        event_type="meme_attachment",
        plane=destination,
        region="x_high_y_high",
        position=arrival,
        entities=[
            _entity(traveler_abroad, "subject", "goblin"),
            _entity(meme_id, "meme_source", "meme"),
        ],
        cause_chain=[
            {
                "type": "adjacent_meme",
                "entity_ids": [traveler_abroad, meme_id],
            }
        ],
        details={"meme_before": 0.1, "meme_after": 0.46},
    )
    insight = builder.emit(
        tick=3,
        event_type="insight_drift",
        plane=destination,
        region="x_high_y_high",
        position=arrival,
        entities=[_entity(traveler_abroad, "subject", "insight")],
        cause_chain=[
            {
                "type": "meme_drift",
                "entity_ids": [traveler_abroad, meme_id],
                "event_sequence": meme["sequence"],
            }
        ],
        details={"from_kind": "goblin", "to_kind": "insight", "flavor": "meme_drift"},
    )
    returned = builder.emit(
        tick=4,
        event_type="gate_transfer",
        plane=destination,
        region="x_high_y_high",
        position=return_anchor,
        entities=[
            _entity(traveler_abroad, "source", "insight"),
            _entity(traveler_returned, "created", "insight"),
        ],
        cause_chain=[
            {
                "type": "gate_rule",
                "entity_ids": [traveler_abroad, traveler_returned],
                "event_sequence": insight["sequence"],
            }
        ],
        details={
            "gate": "homeward_axiom",
            "outcome": "placed",
            "target_plane": "GENESIS",
            "target_position": outbound_anchor,
            "anchor_offset": [-1, 0],
            "anchor_position": return_anchor,
            "cooldown_before": 0,
            "cooldown_after": 3,
        },
    )
    builder.emit(
        tick=4,
        event_type="birth",
        plane="GENESIS",
        region="x_low_y_low",
        position=outbound_anchor,
        entities=[_entity(traveler_returned, "subject", "insight")],
        cause_chain=[
            {
                "type": "gate_transfer",
                "entity_ids": [traveler_returned],
                "event_sequence": returned["sequence"],
            }
        ],
        details={"kind": "insight", "species": None, "flavor": "gate_return"},
    )
    errors = validate_stream(builder.events)
    if errors:
        raise RuntimeError("fixture Chronicle stream is invalid: " + "; ".join(errors))
    return [dict(event) for event in builder.events]


Mutator = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None]


def _no_tamper(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, trace, environment


def _claim(trace: dict[str, Any], claim_id: str) -> dict[str, Any]:
    return next(claim for claim in trace["claims"] if claim["claim_id"] == claim_id)


def _unwitnessed_claim(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, environment
    event_id = _claim(trace, "claim-meme-attachment")["evidence_event_ids"][0]
    for step in trace["steps"]:
        step["observation_event_ids"] = [
            value for value in step["observation_event_ids"] if value != event_id
        ]
        step["outcome_event_ids"] = [
            value for value in step["outcome_event_ids"] if value != event_id
        ]


def _late_witness_claim(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, environment
    _claim(trace, "claim-meme-attachment")["tick"] = 2


def _forged_gate_target(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, environment
    trace["steps"][-1]["action"]["parameters"]["target_plane"] = "MIRAGE"


def _active_cooldown_transfer(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task
    gate = next(event for event in environment["events"] if event["event_type"] == "gate_transfer")
    gate["details"]["cooldown_before"] = 1
    environment["events_sha256"] = canonical_sha256(environment["events"])
    trace["event_stream_sha256"] = environment["events_sha256"]


def _missing_return(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, environment
    trace["steps"].pop()
    trace["final_resources"] = {"focus": 2, "waystone": 1}


def _resource_tamper(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, environment
    trace["steps"][0]["action"]["cost"]["waystone"] = 0


def _false_meme_claim(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, environment
    _claim(trace, "claim-meme-attachment")["value"] = 0.99


def _event_stream_tamper(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del task, trace
    environment["events"][0]["details"]["fabricated"] = True


def _diagnostic_gate(task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]) -> None:
    del trace, environment
    task["diagnostic_verifiers"].remove("response_diversity")
    task["required_verifiers"].append("response_diversity")


SCENARIOS: tuple[tuple[str, bool, str | None, Mutator], ...] = (
    ("valid", True, None, _no_tamper),
    ("unwitnessed_claim", False, "witness_scope", _unwitnessed_claim),
    ("late_witness_claim", False, "witness_scope", _late_witness_claim),
    ("forged_gate_target", False, "gate_travel", _forged_gate_target),
    ("active_cooldown_transfer", False, "gate_travel", _active_cooldown_transfer),
    ("missing_return", False, "gate_travel", _missing_return),
    ("resource_tamper", False, "resource_ledger", _resource_tamper),
    ("false_meme_claim", False, "claim_grounding", _false_meme_claim),
    ("event_stream_tamper", False, "event_stream_integrity", _event_stream_tamper),
    ("diagnostic_gate", False, "configuration", _diagnostic_gate),
)


def run_cases(
    manifest: Mapping[str, Any], manifest_path: Path | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del manifest_path
    deadline = time.monotonic() + float(manifest["budget"]["max_wall_seconds"])
    rows: list[dict[str, Any]] = []
    replay_results: list[dict[str, Any]] = []
    required_types = set(manifest["design"]["required_event_types"])
    for split in ("discovery", "confirmatory", "holdout"):
        for seed_value in manifest["seed_plan"][split]:
            if time.monotonic() > deadline:
                raise TimeoutError("Chronicle gate campaign exceeded its wall-time budget")
            seed = int(seed_value)
            source = fixture_stream(split=split, seed=seed)
            replay = fixture_stream(split=split, seed=seed)
            expected = canonical_sha256(source)
            actual = canonical_sha256(replay)
            types = Counter(event["event_type"] for event in source)
            missing = sorted(required_types - set(types))
            successful_transfers = types["gate_transfer"]
            exposure_passed = not missing and successful_transfers >= 2
            replay_results.append(
                {
                    "split": split,
                    "seed": seed,
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                    "passed": expected == actual,
                    "event_type_counts": dict(sorted(types.items())),
                    "exposure_passed": exposure_passed,
                    "missing_required_event_types": missing,
                }
            )
            if expected != actual or not exposure_passed:
                raise RuntimeError("source replay or treatment exposure gate failed")
            task_base, trace_base, environment_base = build_chronicle_gate_adventure(
                source, replay_receipt=expected
            )
            for scenario, expected_accept, expected_failure, mutator in SCENARIOS:
                task = copy.deepcopy(task_base)
                trace = copy.deepcopy(trace_base)
                environment = copy.deepcopy(environment_base)
                mutator(task, trace, environment)
                suite = verify_adventure(task, trace, environment)
                targeted = (
                    True
                    if expected_failure is None
                    else bool(suite["configuration_errors"])
                    if expected_failure == "configuration"
                    else expected_failure in suite["failed_required_verifiers"]
                )
                rows.append(
                    {
                        "schema": CASE_SCHEMA,
                        "case_id": f"{split}-{seed}-{scenario}",
                        "split": split,
                        "seed": seed,
                        "scenario": scenario,
                        "expected_accept": expected_accept,
                        "expected_failure": expected_failure,
                        "actual_accept": bool(suite["accepted"]),
                        "targeted_failure_observed": targeted,
                        "expectation_matched": (
                            bool(suite["accepted"]) == expected_accept and targeted
                        ),
                        "task": task,
                        "trace": trace,
                        "environment": environment,
                        "verification": suite,
                        "verification_sha256": canonical_sha256(suite),
                    }
                )
    return rows, replay_results


def summarize(
    rows: list[Mapping[str, Any]], replay_results: list[Mapping[str, Any]]
) -> dict[str, Any]:
    by_scenario: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[str(row["scenario"])].append(row)
    scenario_summary = {
        scenario: {
            "cases": len(group),
            "actual_accept_count": sum(bool(row["actual_accept"]) for row in group),
            "expectation_match_count": sum(bool(row["expectation_matched"]) for row in group),
            "targeted_failure_count": sum(
                bool(row["targeted_failure_observed"]) for row in group
            ),
            "failed_verifier_counts": dict(
                sorted(
                    Counter(
                        verifier
                        for row in group
                        for verifier in row["verification"]["failed_required_verifiers"]
                    ).items()
                )
            ),
        }
        for scenario, group in sorted(by_scenario.items())
    }
    valid = by_scenario["valid"]
    tampered = [row for row in rows if row["scenario"] != "valid"]
    h1 = all(bool(row["actual_accept"]) for row in valid)
    h2 = all(not bool(row["actual_accept"]) for row in tampered)
    h3 = all(bool(row["targeted_failure_observed"]) for row in tampered)
    return {
        "schema": SUMMARY_SCHEMA,
        "case_count": len(rows),
        "split_counts": dict(sorted(Counter(str(row["split"]) for row in rows).items())),
        "scenario_count": len(scenario_summary),
        "scenario_summary": scenario_summary,
        "expectation_match_count": sum(bool(row["expectation_matched"]) for row in rows),
        "valid_acceptance_count": sum(bool(row["actual_accept"]) for row in valid),
        "tamper_rejection_count": sum(not bool(row["actual_accept"]) for row in tampered),
        "targeted_failure_count": sum(bool(row["targeted_failure_observed"]) for row in tampered),
        "replay_results": [dict(row) for row in replay_results],
        "replay_passed": all(bool(row["passed"]) for row in replay_results),
        "exposure_passed": all(bool(row["exposure_passed"]) for row in replay_results),
        "hypothesis_assessment": {
            "H1_valid_round_trips_pass": {
                "status": "supported_within_fixture_suite" if h1 else "not_supported"
            },
            "H2_tampered_round_trips_fail": {
                "status": "supported_within_fixture_suite" if h2 else "not_supported"
            },
            "H3_targeted_verifiers_detect_tamper": {
                "status": "supported_within_fixture_suite" if h3 else "not_supported"
            },
        },
        "claim_boundary": (
            "This validates the declared deterministic Chronicle fixtures and library wiring. "
            "It does not establish adventurer intelligence, meme cognition, game quality, or "
            "resistance to every exploit."
        ),
    }


def verifier_catalog() -> dict[str, Any]:
    return {
        "schema": "alife.adventure.verifier_catalog.v1",
        "verifiers": [
            {
                "verifier_id": spec.verifier_id,
                "version": "1",
                "acceptance_eligible": spec.acceptance_eligible,
                "description": spec.description,
            }
            for spec in VERIFIER_SPECS.values()
        ],
        "acceptance_rule": "all declared hard verifiers pass; diagnostics are ineligible",
    }


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output = (args.output or Path(manifest["artifacts"]["output_directory"])).resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    started_utc = utc_now()
    rows, replay_results = run_cases(manifest, manifest_path)
    summary = summarize(rows, replay_results)
    with (output / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    write_json(output / "summary.json", summary)
    write_json(output / "verifier_catalog.json", verifier_catalog())
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    taxonomy_path = manifest_path.parent / manifest["design"]["taxonomy_path"]
    shutil.copy2(taxonomy_path, output / "verifier_taxonomy.json")

    code_path = Path(__file__).resolve()
    package_root = code_path.parent
    project_root = code_path.parents[2]
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": (
            "ok"
            if summary["expectation_match_count"] == len(rows)
            and summary["replay_passed"]
            and summary["exposure_passed"]
            else "failed"
        ),
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "max_rss_mb": psutil.Process().memory_info().rss / (1024 * 1024),
        "case_count": len(rows),
        "code_path": str(code_path),
        "code_sha256": sha256_file(code_path),
        "core_path": str(package_root / "core.py"),
        "core_sha256": sha256_file(package_root / "core.py"),
        "verifiers_path": str(package_root / "verifiers.py"),
        "verifiers_sha256": sha256_file(package_root / "verifiers.py"),
        "adapters_path": str(package_root / "adapters.py"),
        "adapters_sha256": sha256_file(package_root / "adapters.py"),
        "manifest_sha256": sha256_file(manifest_path),
        "taxonomy_sha256": sha256_file(taxonomy_path),
        **environment,
        "environment_sha256": canonical_sha256(environment),
        "git_commit_at_run": git_commit(project_root),
        "git_dirty_at_run": _git_dirty(project_root),
        "stop_reason": "completed_declared_fixture_matrix",
        "output_path": str(output),
        "replay_command": (
            "python src/run_chronicle_gate_adventure_campaign.py "
            f"--manifest {manifest_path} --output {output}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    artifact_names = [
        "cases.jsonl",
        "summary.json",
        "verifier_catalog.json",
        "frozen_manifest.json",
        "verifier_taxonomy.json",
        "receipt.json",
    ]
    write_json(
        output / "hashes.json",
        {
            name: {
                "sha256": sha256_file(output / name),
                "bytes": (output / name).stat().st_size,
            }
            for name in artifact_names
        },
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "status": receipt["status"],
                "cases": len(rows),
                "expectation_matches": summary["expectation_match_count"],
                "replay_passed": summary["replay_passed"],
                "exposure_passed": summary["exposure_passed"],
            },
            indent=2,
        )
    )
    raise SystemExit(0 if receipt["status"] == "ok" else 1)
