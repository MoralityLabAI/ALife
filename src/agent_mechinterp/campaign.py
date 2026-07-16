"""Deterministic play/editor campaign for the ALife mechinterp harness."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import psutil

from adventure_verifiers.adapters import build_pixie_adventure
from adventure_verifiers.verifiers import verify_adventure
from alt_physics_atlas import git_commit, sha256_file, utc_now
from pixie_sanctuary import deterministic_projection, run_episode

from .analysis import analyze_decisions
from .core import (
    RECEIPT_SCHEMA,
    ROW_SCHEMA,
    SUMMARY_SCHEMA,
    CanaryPolicy,
    canonical_sha256,
    capture_decision,
    completed_editor_proposal,
    apply_authorized_edit,
    authorize_edit,
    extract_observation,
    verify_harness_row,
)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def _episode(
    *,
    source_manifest: Mapping[str, Any],
    split: str,
    seed: int,
    critter: str,
    action: str,
    profile: Mapping[str, Any],
    side: int,
    steps: int,
    deadline: float,
    max_ram_mb: float,
) -> dict[str, Any]:
    design = source_manifest["design"]
    return run_episode(
        split=split,
        seed=seed,
        critter=critter,
        action=action,
        profile=profile,
        side=side,
        steps=steps,
        solver_steps_per_record=int(design["solver_steps_per_record"][critter]),
        action_ticks=[tick for tick in (4, 8) if tick <= steps],
        shield_duration=int(design["shield_duration_ticks"]),
        matched_degree=int(design["matched_degree"]),
        tail_ticks=min(4, steps),
        thresholds=source_manifest["analysis"]["response_thresholds"],
        pixie=design["pixie"],
        deadline=deadline,
        max_ram_mb=max_ram_mb,
    )


def _adventure_suite(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Use the existing adventure verifier with goals present in this episode."""

    task, trace, environment = build_pixie_adventure(episode)
    event_types = {str(event["event_type"]) for event in episode["events"]}
    task["goals"] = [
        goal
        for goal in task["goals"]
        if goal.get("match", {}).get("event_type") in event_types
    ]
    side = int(episode["condition"]["side"])
    task["rules"]["movement"]["shape"] = [side, side]
    return verify_adventure(task, trace, environment)


def _projection_pair(
    episode: Mapping[str, Any], replay: Mapping[str, Any]
) -> dict[str, Any]:
    projected = deterministic_projection(episode)
    replayed = deterministic_projection(replay)
    return {
        "executed_projection": projected,
        "executed_projection_sha256": canonical_sha256(projected),
        "replay_projection": replayed,
        "replay_projection_sha256": canonical_sha256(replayed),
    }


def build_rows(
    manifest: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    *,
    deadline: float,
) -> list[dict[str, Any]]:
    policy = CanaryPolicy()
    design = manifest["design"]
    source_design = source_manifest["design"]
    side = int(design["episode"]["side"])
    steps = int(design["episode"]["steps"])
    max_ram_mb = float(manifest["budget"]["max_ram_mb"])
    decisions: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    seed_plan = manifest["seed_plan"]
    for split in ("discovery", "confirmatory", "holdout"):
        for seed in seed_plan[split]:
            for critter in design["critters"]:
                if time.monotonic() >= deadline:
                    raise TimeoutError("campaign wall-time cap reached")
                parent_profile = copy.deepcopy(source_design["species_profiles"][critter])
                observation = extract_observation(
                    seed=int(seed),
                    critter=str(critter),
                    profile=parent_profile,
                    side=side,
                    matched_degree=int(source_design["matched_degree"]),
                    parameter_bounds=taxonomy["editor_allowlist"],
                )
                for mode in design["modes"]:
                    decision = capture_decision(
                        policy=policy,
                        mode=str(mode),
                        split=split,
                        seed=int(seed),
                        critter=str(critter),
                        observation=observation,
                    )
                    decisions.append(decision)
                    row: dict[str, Any] = {
                        "schema": ROW_SCHEMA,
                        "row_id": f"row-{mode}-{split}-{seed}-{critter}",
                        "mode": mode,
                        "split": split,
                        "seed": int(seed),
                        "critter": critter,
                        "decision": decision,
                    }
                    if mode == "play":
                        episode = _episode(
                            source_manifest=source_manifest,
                            split=split,
                            seed=int(seed),
                            critter=str(critter),
                            action=str(decision["selected_action"]),
                            profile=parent_profile,
                            side=side,
                            steps=steps,
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        replay = _episode(
                            source_manifest=source_manifest,
                            split=split,
                            seed=int(seed),
                            critter=str(critter),
                            action=str(decision["selected_action"]),
                            profile=parent_profile,
                            side=side,
                            steps=steps,
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        row["execution"] = {
                            **_projection_pair(episode, replay),
                            "action_receipts": [
                                str(event["action"])
                                for event in episode["events"]
                                if event["event_type"] == "pixie_action"
                            ],
                            "adventure_verification": _adventure_suite(episode),
                            "response_class": episode["outcomes"]["response_class"],
                        }
                    else:
                        proposal = completed_editor_proposal(decision, parent_profile)
                        authorization = authorize_edit(
                            proposal,
                            parent_profile=parent_profile,
                            observed_critter=str(critter),
                            taxonomy=taxonomy,
                        )
                        edited_profile, edit_receipt = apply_authorized_edit(
                            proposal, authorization, parent_profile
                        )
                        evaluation_action = str(source_design["preferred_actions"][critter])
                        baseline = _episode(
                            source_manifest=source_manifest,
                            split=split,
                            seed=int(seed),
                            critter=str(critter),
                            action=evaluation_action,
                            profile=parent_profile,
                            side=side,
                            steps=steps,
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        edited = _episode(
                            source_manifest=source_manifest,
                            split=split,
                            seed=int(seed),
                            critter=str(critter),
                            action=evaluation_action,
                            profile=edited_profile,
                            side=side,
                            steps=steps,
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        replay = _episode(
                            source_manifest=source_manifest,
                            split=split,
                            seed=int(seed),
                            critter=str(critter),
                            action=evaluation_action,
                            profile=edited_profile,
                            side=side,
                            steps=steps,
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        hazards = {
                            "globalized_response": bool(
                                edited["outcomes"]["globalized_response"]
                            ),
                            "collapse": edited["outcomes"]["response_class"] == "collapse",
                        }
                        row["execution"] = {
                            **_projection_pair(edited, replay),
                            "proposal": proposal,
                            "authorization": authorization,
                            "parent_profile": parent_profile,
                            "edited_profile": edited_profile,
                            "edit_receipt": edit_receipt,
                            "baseline_projection_sha256": canonical_sha256(
                                deterministic_projection(baseline)
                            ),
                            "evaluation_action": evaluation_action,
                            "outcome_delta": {
                                key: float(edited["outcomes"][key])
                                - float(baseline["outcomes"][key])
                                for key in (
                                    "peak_divergent_fraction",
                                    "tail_divergent_fraction",
                                    "treated_final_entropy",
                                )
                            },
                            "hazards": hazards,
                            "promotion_eligible": not any(hazards.values()),
                            "promotion_gate_ids": [
                                "editor_firewall",
                                "edit_receipt",
                                "episode_replay",
                                "globalized_or_collapsed_editor_result",
                            ],
                        }
                    row["hard_verification"] = verify_harness_row(
                        row, policy=policy, taxonomy=taxonomy
                    )
                    if not row["hard_verification"]["passed"]:
                        raise RuntimeError(
                            f"valid row failed hard checks: {row['row_id']} "
                            f"{row['hard_verification']['failures']}"
                        )
                    rows.append(row)
    simulator_episode_count = sum(2 if row["mode"] == "play" else 3 for row in rows)
    if simulator_episode_count > int(manifest["budget"]["max_episodes"]):
        raise RuntimeError("campaign exceeded simulator-episode cap")
    return rows


def tamper_audit(
    rows: Sequence[Mapping[str, Any]], taxonomy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Apply one-at-a-time attacks and require the registered check to fail."""

    policy = CanaryPolicy()
    play = next(copy.deepcopy(row) for row in rows if row["mode"] == "play")
    editor = next(copy.deepcopy(row) for row in rows if row["mode"] == "editor")
    cases: list[tuple[str, str, dict[str, Any]]] = []

    row = copy.deepcopy(play)
    row["decision"]["activations_sha256"] = "0" * 64
    cases.append(("activation_hash", "decision_integrity", row))

    row = copy.deepcopy(play)
    row["decision"]["selected_action"] = "observe"
    cases.append(("selected_action", "decision_integrity", row))

    row = copy.deepcopy(play)
    row["execution"]["action_receipts"][0] = "observe"
    cases.append(("play_action_link", "action_link", row))

    row = copy.deepcopy(editor)
    row["execution"]["proposal"]["target_critter"] = "not-the-observed-critter"
    cases.append(("editor_wrong_critter", "editor_firewall", row))

    row = copy.deepcopy(editor)
    proposal = row["execution"]["proposal"]
    proposal["delta"] = 999
    proposal["new_value"] = proposal["old_value"] + 999
    cases.append(("editor_out_of_bounds", "editor_firewall", row))

    row = copy.deepcopy(editor)
    row["execution"]["proposal"]["parent_profile_sha256"] = "0" * 64
    cases.append(("editor_parent_hash", "editor_firewall", row))

    row = copy.deepcopy(editor)
    row["execution"]["edit_receipt"]["edited_profile_sha256"] = "0" * 64
    cases.append(("edit_receipt", "edit_receipt", row))

    row = copy.deepcopy(play)
    row["execution"]["replay_projection_sha256"] = "0" * 64
    cases.append(("replay_digest", "episode_replay", row))

    row = copy.deepcopy(editor)
    row["execution"]["authorization"]["gate_ids"].append("identity_probe")
    row["execution"]["authorization"]["authorization_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in row["execution"]["authorization"].items()
            if key != "authorization_sha256"
        }
    )
    cases.append(("diagnostic_authorization", "authorization_firewall", row))

    results: list[dict[str, Any]] = []
    for tamper_class, expected_check, row in cases:
        report = verify_harness_row(row, policy=policy, taxonomy=taxonomy)
        targeted = report["checks"].get(expected_check) is False
        results.append(
            {
                "tamper_class": tamper_class,
                "expected_check": expected_check,
                "accepted": report["passed"],
                "targeted_check_failed": targeted,
                "passed": not report["passed"] and targeted,
                "hard_verification": report,
            }
        )
    return results


def summarize(
    rows: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
    tamper_results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    thresholds = manifest["analysis"]["thresholds"]
    hypotheses = {
        "H1_linked_replay": all(row["hard_verification"]["passed"] for row in rows),
        "H2_probe_recovery": all(
            float(result["probe_accuracy"]["holdout"])
            >= float(thresholds["holdout_probe_accuracy_min"])
            for result in analysis["modes"].values()
        ),
        "H3_causal_use": all(
            float(result["mean_chosen_logit_drop"])
            >= float(thresholds["mean_chosen_logit_drop_min"])
            and float(result["patch_action_change_fraction"])
            >= float(thresholds["patch_action_change_fraction_min"])
            for result in analysis["modes"].values()
        ),
        "H4_firewall": all(result["passed"] for result in tamper_results),
    }
    return {
        "schema": SUMMARY_SCHEMA,
        "status": "ok" if all(hypotheses.values()) else "falsified",
        "claim_scope": "model_only",
        "cognition_claim": False,
        "row_count": len(rows),
        "simulator_episode_count": sum(
            2 if row["mode"] == "play" else 3 for row in rows
        ),
        "counts_by_mode": dict(Counter(str(row["mode"]) for row in rows)),
        "counts_by_split": dict(Counter(str(row["split"]) for row in rows)),
        "hard_check_pass_count": sum(
            bool(row["hard_verification"]["passed"]) for row in rows
        ),
        "editor_promotion_eligible_count": sum(
            bool(row["execution"].get("promotion_eligible"))
            for row in rows
            if row["mode"] == "editor"
        ),
        "mechanistic_analysis": analysis,
        "tamper_audit": list(tamper_results),
        "hypothesis_assessment": hypotheses,
        "metric_firewall": {
            "selection_metrics": [],
            "authorization_eligible": [
                "editor_firewall",
                "edit_receipt",
                "episode_replay",
                "hazard_checks",
            ],
            "authorization_ineligible": [
                "identity_probe",
                "dominant_unit_ablation",
                "cross_critter_patch",
                "activation_norm",
                "representation_drift_cosine",
                "complexity",
                "delight",
            ],
        },
    }


def _knowledge_card(summary: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    modes = summary["mechanistic_analysis"]["modes"]
    return f"""# Agent Mechinterp Harness v1 — Knowledge Card

## Result

The deterministic canary campaign retained {summary['row_count']} paired play/editor
decision rows. All structural checks passed, and all declared one-at-a-time tamper
classes were rejected by their registered hard check.

## Mechanistic evidence (model only)

- Play holdout identity-probe accuracy: {modes['play']['probe_accuracy']['holdout']:.3f}
- Editor holdout identity-probe accuracy: {modes['editor']['probe_accuracy']['holdout']:.3f}
- Play mean chosen-logit drop under registered-unit ablation: {modes['play']['mean_chosen_logit_drop']:.3f}
- Editor mean chosen-logit drop under registered-unit ablation: {modes['editor']['mean_chosen_logit_drop']:.3f}
- Play/editor cross-critter patch action-change fractions: {modes['play']['patch_action_change_fraction']:.3f} / {modes['editor']['patch_action_change_fraction']:.3f}

These results validate harness wiring against a fixed NumPy policy whose identity
channels are known by construction. They do not establish cognition, consciousness,
learned feature semantics, causal completeness, or safety of an arbitrary agent.

## Editor firewall

Edits target one allowlisted scalar on a copied profile. Bounds, maximum delta,
integer constraints, immutable parent hash, exact change receipt, replay, and response
hazards are checked. Probe, attribution, activation, drift, complexity, delight, and
response-diversity metrics cannot authorize or promote an edit.

## Replay

Receipt schema: `{receipt['schema']}`. Run `{receipt['replay_command']}`.
"""


def run_campaign(manifest_path: Path, output: Path) -> dict[str, Any]:
    started = time.monotonic()
    manifest_path = manifest_path.resolve()
    manifest = load_object(manifest_path)
    experiment_dir = manifest_path.parent
    taxonomy_path = (experiment_dir / manifest["design"]["taxonomy_path"]).resolve()
    source_manifest_path = (
        experiment_dir / manifest["design"]["source_manifest"]
    ).resolve()
    taxonomy = load_object(taxonomy_path)
    source_manifest = load_object(source_manifest_path)
    max_wall = float(manifest["budget"]["max_wall_seconds"])
    deadline = started + max_wall
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    frozen_manifest = output / "frozen_manifest.json"
    frozen_taxonomy = output / "mechinterp_taxonomy.json"
    shutil.copy2(manifest_path, frozen_manifest)
    shutil.copy2(taxonomy_path, frozen_taxonomy)
    shutil.copy2(source_manifest_path, output / "source_pixie_manifest.json")

    rows = build_rows(
        manifest, taxonomy, source_manifest, deadline=deadline
    )
    policy = CanaryPolicy()
    analysis = analyze_decisions([row["decision"] for row in rows], policy)
    tamper_results = tamper_audit(rows, taxonomy)
    summary = summarize(rows, analysis, tamper_results, manifest)
    if summary["status"] != "ok":
        raise RuntimeError("predeclared mechinterp campaign hypotheses were falsified")

    raw_path = output / "decisions.jsonl"
    summary_path = output / "summary.json"
    write_jsonl(raw_path, rows)
    write_json(summary_path, summary)
    write_json(
        output / "seed_manifest.json",
        {
            "schema": "alife.agent_mechinterp.seed_manifest.v1",
            "seeds": manifest["seed_plan"],
            "completed_rows": len(rows),
        },
    )
    root = Path(__file__).resolve().parents[2]
    code_paths = [
        Path(__file__).resolve(),
        (Path(__file__).parent / "core.py").resolve(),
        (Path(__file__).parent / "analysis.py").resolve(),
        (root / "src" / "pixie_sanctuary.py").resolve(),
    ]
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": "ok",
        "created_utc": utc_now(),
        "row_count": len(rows),
        "manifest_sha256": sha256_file(frozen_manifest),
        "taxonomy_sha256": sha256_file(frozen_taxonomy),
        "raw_rows_sha256": sha256_file(raw_path),
        "summary_sha256": sha256_file(summary_path),
        "code": [
            {"path": str(path), "sha256": sha256_file(path)} for path in code_paths
        ],
        "git_commit": git_commit(root),
        **environment,
        "environment_sha256": canonical_sha256(environment),
        "runtime_seconds": time.monotonic() - started,
        "replay_command": (
            "python src/run_agent_mechinterp_campaign.py --manifest "
            "experiments/agent_mechinterp_harness_v1/manifest.json --output "
            "results/agent_mechinterp_harness_v1"
        ),
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(
        _knowledge_card(summary, receipt), encoding="utf-8"
    )
    hash_names = [
        "decisions.jsonl",
        "summary.json",
        "seed_manifest.json",
        "frozen_manifest.json",
        "mechinterp_taxonomy.json",
        "source_pixie_manifest.json",
        "receipt.json",
        "knowledge_card.md",
    ]
    write_json(
        output / "hashes.json",
        {
            name: {
                "sha256": sha256_file(output / name),
                "bytes": (output / name).stat().st_size,
            }
            for name in hash_names
        },
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/agent_mechinterp_harness_v1/manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/agent_mechinterp_harness_v1"),
    )
    args = parser.parse_args()
    receipt = run_campaign(args.manifest, args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
