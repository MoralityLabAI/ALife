"""Deterministic adversarial fixture campaign for the adventure verifier library."""

from __future__ import annotations

import copy
import json
import platform
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
import psutil

from alt_physics_atlas import git_commit, sha256_file, utc_now, write_json
from pixie_folded_cavern import deterministic_projection, run_episode

from .adapters import build_pixie_adventure
from .core import canonical_sha256
from .verifiers import VERIFIER_SPECS, verify_adventure


CASE_SCHEMA = "alife.adventure.verifier_case.v1"
SUMMARY_SCHEMA = "alife.adventure.verifier_campaign_summary.v1"
RECEIPT_SCHEMA = "alife.adventure.verifier_campaign_receipt.v1"


def _load_source_manifest(manifest: Mapping[str, Any], manifest_path: Path) -> dict[str, Any]:
    path = (manifest_path.parent / manifest["design"]["source_manifest"]).resolve()
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fixture_episode(
    source: Mapping[str, Any], *, split: str, seed: int, deadline: float
) -> dict[str, Any]:
    design = source["design"]
    critter = "mitosis_moss"
    return run_episode(
        split=split,
        seed=seed,
        critter=critter,
        action=design["preferred_actions"][critter],
        profile=design["species_profiles"][critter],
        dimension=6,
        neighborhood="fixed_degree_16",
        intervention_depth="axis_probe",
        surface_side=int(design["surface_side"]),
        fixed_degree=int(design["fixed_degree"]),
        steps=int(design["steps_by_split"][split]),
        solver_steps_per_record=int(design["solver_steps_per_record"][critter]),
        action_ticks=design["action_ticks"],
        tail_ticks=int(design["tail_ticks"]),
        thresholds=source["analysis"]["thresholds"],
        pixie=design["pixie"],
        deadline=deadline,
        max_ram_mb=float(source["budget"]["max_ram_mb"]),
    )


Mutator = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any]], None
]


def _no_tamper(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, trace, environment


def _forged_reference(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, environment
    trace["steps"][0]["observation_event_ids"].append("fabricated:event:9999")


def _future_evidence(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, environment
    trace["claims"][-1]["tick"] -= 1


def _missing_receipt(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, environment
    trace["steps"][0]["action"]["receipt_event_id"] = "missing:action:receipt"


def _illegal_route(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, environment
    trace["steps"][1]["location"] = [7, 7]


def _resource_tamper(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, environment
    trace["steps"][0]["action"]["cost"]["focus"] = 3


def _false_claim(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, environment
    trace["claims"][0]["value"] = "fabricated_response_class"


def _event_stream_tamper(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del task, trace
    environment["events"][0]["details"]["tampered"] = True


def _impossible_goal(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del trace, environment
    task["goals"].append(
        {
            "goal_id": "impossible",
            "kind": "event_count",
            "match": {"event_type": "event_that_did_not_happen"},
            "minimum": 1,
        }
    )


def _diagnostic_gate(
    task: dict[str, Any], trace: dict[str, Any], environment: dict[str, Any]
) -> None:
    del trace, environment
    task["diagnostic_verifiers"].remove("exploration_coverage")
    task["required_verifiers"].append("exploration_coverage")


SCENARIOS: tuple[tuple[str, bool, str | None, Mutator], ...] = (
    ("valid", True, None, _no_tamper),
    ("forged_reference", False, "causal_grounding", _forged_reference),
    ("future_evidence", False, "causal_grounding", _future_evidence),
    ("missing_receipt", False, "action_receipts", _missing_receipt),
    ("illegal_route", False, "route_continuity", _illegal_route),
    ("resource_tamper", False, "resource_ledger", _resource_tamper),
    ("false_claim", False, "claim_grounding", _false_claim),
    ("event_stream_tamper", False, "event_stream_integrity", _event_stream_tamper),
    ("impossible_goal", False, "goal_completion", _impossible_goal),
    ("diagnostic_gate", False, "configuration", _diagnostic_gate),
)


def run_cases(
    manifest: Mapping[str, Any], manifest_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = _load_source_manifest(manifest, manifest_path)
    deadline = time.monotonic() + float(manifest["budget"]["max_wall_seconds"])
    rows: list[dict[str, Any]] = []
    replay_results: list[dict[str, Any]] = []
    for split in ("discovery", "confirmatory", "holdout"):
        for seed in manifest["seed_plan"][split]:
            base = fixture_episode(source, split=split, seed=int(seed), deadline=deadline)
            replay = fixture_episode(source, split=split, seed=int(seed), deadline=deadline)
            expected_replay = canonical_sha256(deterministic_projection(base))
            actual_replay = canonical_sha256(deterministic_projection(replay))
            replay_results.append(
                {
                    "split": split,
                    "seed": int(seed),
                    "expected_sha256": expected_replay,
                    "actual_sha256": actual_replay,
                    "passed": expected_replay == actual_replay,
                }
            )
            task_base, trace_base, environment_base = build_pixie_adventure(base)
            for scenario, expected_accept, expected_failure, mutator in SCENARIOS:
                task = copy.deepcopy(task_base)
                trace = copy.deepcopy(trace_base)
                environment = copy.deepcopy(environment_base)
                mutator(task, trace, environment)
                suite = verify_adventure(task, trace, environment)
                targeted_failure_observed = (
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
                        "seed": int(seed),
                        "scenario": scenario,
                        "expected_accept": expected_accept,
                        "expected_failure": expected_failure,
                        "actual_accept": bool(suite["accepted"]),
                        "targeted_failure_observed": targeted_failure_observed,
                        "expectation_matched": (
                            bool(suite["accepted"]) == expected_accept
                            and targeted_failure_observed
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
            "expected_accept_count": sum(bool(row["expected_accept"]) for row in group),
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
        "replay_results": [dict(row) for row in replay_results],
        "replay_passed": all(bool(row["passed"]) for row in replay_results),
        "hypothesis_assessment": {
            "H1_valid_adventures_pass": {
                "status": "supported_within_fixture_suite" if h1 else "not_supported"
            },
            "H2_tampered_adventures_fail": {
                "status": "supported_within_fixture_suite" if h2 else "not_supported"
            },
            "H3_targeted_verifiers_detect_tamper": {
                "status": "supported_within_fixture_suite" if h3 else "not_supported"
            },
        },
        "claim_boundary": (
            "This validates deterministic fixture discrimination and library wiring. It does "
            "not establish adventurer competence, game quality, or resistance to every exploit."
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
    source_path = (manifest_path.parent / manifest["design"]["source_manifest"]).resolve()
    shutil.copy2(source_path, output / "frozen_source_manifest.json")
    code_path = Path(__file__).resolve()
    package_root = code_path.parent
    project_root = code_path.parents[2]
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "ok" if summary["expectation_match_count"] == len(rows) else "failed",
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
        "source_manifest_sha256": sha256_file(source_path),
        **environment,
        "environment_sha256": canonical_sha256(environment),
        "git_commit_at_run": git_commit(project_root),
        "output_path": str(output),
        "replay_command": (
            f"python src/run_adventure_verifier_campaign.py --manifest {manifest_path} "
            f"--output {output}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    artifact_names = [
        "cases.jsonl",
        "summary.json",
        "verifier_catalog.json",
        "frozen_manifest.json",
        "verifier_taxonomy.json",
        "frozen_source_manifest.json",
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
            },
            indent=2,
        )
    )
    raise SystemExit(0 if receipt["status"] == "ok" else 1)
