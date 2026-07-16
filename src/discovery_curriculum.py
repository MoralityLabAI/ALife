#!/usr/bin/env python3
"""Generate and grade hidden-oracle ALife discovery episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import psutil


EPISODE_SCHEMA = "alife.discovery_curriculum.episode.v1"
SUMMARY_SCHEMA = "alife.discovery_curriculum.summary.v1"
TASK_FAMILIES = (
    "planted_effect",
    "true_null",
    "structural_unreachability",
    "causal_sites",
    "conserved_quantity",
    "masked_interval",
    "masked_point",
)
POLICIES = ("calibrated_investigator", "proxy_claimant", "always_abstain")
SPLITS = ("discovery", "confirmatory", "holdout")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rule90_step(state: np.ndarray) -> np.ndarray:
    return np.logical_xor(np.roll(state, 1), np.roll(state, -1))


def simulate_rule90(state: np.ndarray, horizon: int) -> np.ndarray:
    result = state.copy()
    for _ in range(horizon):
        result = rule90_step(result)
    return result


def shift_step(state: np.ndarray) -> np.ndarray:
    return np.roll(state, 1)


def simulate_shift(state: np.ndarray, horizon: int) -> np.ndarray:
    return np.roll(state, horizon)


def random_bits(seed: int, size: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 2, size=size, dtype=np.int8).astype(bool)


def task_digest(task: Mapping[str, Any]) -> str:
    return sha256_bytes(json.dumps(task, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def make_planted_effect(seed: int, size: int, horizon: int) -> dict[str, Any]:
    for offset in range(100):
        initial = random_bits(seed + offset, size)
        site = (seed + 3) % size
        baseline = simulate_rule90(initial, horizon)
        treated_initial = initial.copy()
        treated_initial[site] = ~treated_initial[site]
        treated = simulate_rule90(treated_initial, horizon)
        effect = float(treated.mean() - baseline.mean())
        if effect != 0.0:
            break
    return {
        "family": "planted_effect",
        "level": 2,
        "oracle_present": True,
        "identification": "point",
        "public": {
            "world": "rule90_ring",
            "size": size,
            "horizon": horizon,
            "initial_state": initial.astype(int).tolist(),
            "intervention": {"flip_initial_site": site},
            "target": "treated_minus_baseline_final_density",
        },
        "oracle": {
            "truth": effect,
            "compatible_set": [effect],
            "identifiable_with_budget": True,
            "certificate": "two deterministic simulations exactly identify the effect",
        },
        "registration_template": {
            "claim_type": "numeric_point",
            "smallest_effect_of_interest": 1.0 / size,
            "required_precision": 0.0,
            "budget": 2,
        },
    }


def make_true_null(seed: int, size: int, horizon: int) -> dict[str, Any]:
    initial = random_bits(seed, size)
    return {
        "family": "true_null",
        "level": 2,
        "oracle_present": True,
        "identification": "point",
        "public": {
            "world": "rule90_ring",
            "size": size,
            "horizon": horizon,
            "initial_state": initial.astype(int).tolist(),
            "intervention": {"toggle_unused_metadata_bit": True},
            "target": "treated_minus_baseline_final_density",
        },
        "oracle": {
            "truth": 0.0,
            "compatible_set": [0.0],
            "identifiable_with_budget": True,
            "certificate": "the intervention is absent from the transition function",
        },
        "registration_template": {
            "claim_type": "numeric_point",
            "smallest_effect_of_interest": 1.0 / size,
            "required_precision": 0.0,
            "budget": 2,
        },
    }


def make_unreachable(seed: int, size: int) -> dict[str, Any]:
    split = size // 2
    edges: list[list[int]] = []
    for node in range(split - 1):
        edges.append([node, node + 1])
    for node in range(split, size - 1):
        edges.append([node, node + 1])
    if seed % 2:
        edges.extend([[node + 1, node] for node in range(split - 1)])
    start = seed % split
    target = split + (seed % (size - split))
    return {
        "family": "structural_unreachability",
        "level": 3,
        "oracle_present": True,
        "identification": "point",
        "public": {
            "world": "directed_activation_graph",
            "nodes": size,
            "edges": edges,
            "start": start,
            "target": target,
            "question": "is_target_reachable",
        },
        "oracle": {
            "truth": False,
            "compatible_set": [False],
            "identifiable_with_budget": True,
            "certificate": "breadth-first search exhausts the start component without target",
        },
        "registration_template": {
            "claim_type": "boolean",
            "required_precision": 0.0,
            "budget": size + len(edges),
        },
    }


def exact_causal_sites(initial: np.ndarray, horizon: int, target: int) -> list[int]:
    baseline = bool(simulate_rule90(initial, horizon)[target])
    sites: list[int] = []
    for site in range(len(initial)):
        perturbed = initial.copy()
        perturbed[site] = ~perturbed[site]
        if bool(simulate_rule90(perturbed, horizon)[target]) != baseline:
            sites.append(site)
    return sites


def make_causal_sites(seed: int, size: int, horizon: int) -> dict[str, Any]:
    initial = random_bits(seed, size)
    target = (seed * 3 + 1) % size
    sites = exact_causal_sites(initial, horizon, target)
    return {
        "family": "causal_sites",
        "level": 4,
        "oracle_present": True,
        "identification": "point",
        "public": {
            "world": "rule90_ring",
            "size": size,
            "horizon": horizon,
            "initial_state": initial.astype(int).tolist(),
            "target_cell": target,
            "intervention_semantics": "flip one initial site and observe target-cell change",
            "question": "exact_finite_horizon_causal_site_set",
        },
        "oracle": {
            "truth": sites,
            "compatible_set": [sites],
            "identifiable_with_budget": True,
            "certificate": f"baseline plus {size} exhaustive single-site counterfactuals",
        },
        "registration_template": {
            "claim_type": "site_set",
            "required_precision": 0.0,
            "budget": size + 1,
        },
    }


def make_conserved_quantity(seed: int, size: int, horizon: int) -> dict[str, Any]:
    initial = random_bits(seed, size)
    final = simulate_shift(initial, horizon)
    return {
        "family": "conserved_quantity",
        "level": 4,
        "oracle_present": True,
        "identification": "point",
        "public": {
            "world": "reversible_cyclic_shift_ca",
            "size": size,
            "horizon": horizon,
            "initial_state": initial.astype(int).tolist(),
            "final_state": final.astype(int).tolist(),
            "candidate_variables": ["live_count", "first_cell", "adjacent_equal_pairs"],
            "question": "which_registered_variable_is_exactly_conserved_by_the_rule",
        },
        "oracle": {
            "truth": "live_count",
            "compatible_set": ["live_count"],
            "identifiable_with_budget": True,
            "certificate": "cyclic permutation preserves the multiset of cell states",
        },
        "registration_template": {
            "claim_type": "categorical",
            "required_precision": 0.0,
            "budget": 2,
        },
    }


def masked_shift_task(seed: int, size: int, point_request: bool) -> dict[str, Any]:
    initial = random_bits(seed, size)
    hidden_count = max(2, size // 3)
    hidden_indices = sorted(np.random.default_rng(seed + 44).choice(size, hidden_count, replace=False).tolist())
    visible = [None if index in hidden_indices else int(initial[index]) for index in range(size)]
    observed_live = sum(value for value in visible if value is not None)
    interval = [observed_live, observed_live + hidden_count]
    truth = int(initial.sum())
    return {
        "family": "masked_point" if point_request else "masked_interval",
        "level": 5,
        "oracle_present": True,
        "identification": "set" if not point_request else "not_point_identified",
        "public": {
            "world": "reversible_cyclic_shift_ca",
            "size": size,
            "visible_initial_state": visible,
            "hidden_cell_count": hidden_count,
            "rule": "cyclic_shift",
            "target": "final_live_count",
            "requested_claim": "numeric_point" if point_request else "identified_interval",
        },
        "oracle": {
            "truth": truth,
            "compatible_set": list(range(interval[0], interval[1] + 1)),
            "identified_interval": interval,
            "identifiable_with_budget": not point_request,
            "certificate": (
                "visible live count plus unconstrained hidden bits exactly identifies the interval; "
                + ("the requested point remains nonidentified" if point_request else "the set target is identified")
            ),
        },
        "registration_template": {
            "claim_type": "numeric_point" if point_request else "numeric_interval",
            "required_precision": 0.0 if point_request else hidden_count,
            "budget": 0,
        },
    }


def build_task(family: str, seed: int, size: int, horizon: int) -> dict[str, Any]:
    if family == "planted_effect":
        return make_planted_effect(seed, size, horizon)
    if family == "true_null":
        return make_true_null(seed, size, horizon)
    if family == "structural_unreachability":
        return make_unreachable(seed, size)
    if family == "causal_sites":
        return make_causal_sites(seed, size, horizon)
    if family == "conserved_quantity":
        return make_conserved_quantity(seed, size, horizon)
    if family == "masked_interval":
        return masked_shift_task(seed, size, point_request=False)
    if family == "masked_point":
        return masked_shift_task(seed, size, point_request=True)
    raise ValueError(f"unknown task family: {family}")


def calibrated_submission(task: Mapping[str, Any]) -> dict[str, Any]:
    identifiable = bool(task["oracle"]["identifiable_with_budget"])
    registration = {**task["registration_template"], "q_success": 0.95 if identifiable else 0.05}
    if not identifiable:
        return {
            "policy": "calibrated_investigator",
            "registration": registration,
            "investigation_trace": ["derived simulator-compatible set", "point target exceeds registered identifiability"],
            "action": "abstain",
            "claim": None,
            "cost": 0,
        }
    claim_type = registration["claim_type"]
    if claim_type == "numeric_interval":
        claim = task["oracle"]["identified_interval"]
    else:
        claim = task["oracle"]["truth"]
    return {
        "policy": "calibrated_investigator",
        "registration": registration,
        "investigation_trace": ["selected exact finite-world method", task["oracle"]["certificate"]],
        "action": "claim",
        "claim": claim,
        "cost": min(int(registration["budget"]), max(1, int(registration["budget"]))),
    }


def proxy_submission(task: Mapping[str, Any]) -> dict[str, Any]:
    registration = {**task["registration_template"], "q_success": 0.75}
    family = task["family"]
    if family in {"planted_effect", "true_null"}:
        claim: Any = 0.0
    elif family == "structural_unreachability":
        claim = True
    elif family == "causal_sites":
        target = int(task["public"]["target_cell"])
        claim = [target]
    elif family == "conserved_quantity":
        claim = "first_cell"
    elif family == "masked_interval":
        observed_live = sum(
            value for value in task["public"]["visible_initial_state"] if value is not None
        )
        claim = [observed_live, observed_live]
    elif family == "masked_point":
        claim = sum(
            value for value in task["public"]["visible_initial_state"] if value is not None
        )
    else:
        raise ValueError(f"unknown family: {family}")
    return {
        "policy": "proxy_claimant",
        "registration": registration,
        "investigation_trace": ["used aggregate or semantic proxy", "did not enumerate compatible mechanisms"],
        "action": "claim",
        "claim": claim,
        "cost": 1,
    }


def abstain_submission(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "policy": "always_abstain",
        "registration": {**task["registration_template"], "q_success": 0.05},
        "investigation_trace": ["declined every investigation regardless of oracle identifiability"],
        "action": "abstain",
        "claim": None,
        "cost": 0,
    }


def jaccard(left: Sequence[int], right: Sequence[int]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def claim_score(task: Mapping[str, Any], submission: Mapping[str, Any]) -> tuple[float, bool]:
    identifiable = bool(task["oracle"]["identifiable_with_budget"])
    if submission["action"] == "abstain":
        return (1.0, False) if not identifiable else (0.0, False)
    if not identifiable:
        return 0.0, True
    claim_type = task["registration_template"]["claim_type"]
    truth = task["oracle"]["truth"]
    claim = submission["claim"]
    if claim_type == "numeric_point":
        scale = max(
            float(task["registration_template"].get("smallest_effect_of_interest", 1.0)),
            1e-9,
        )
        score = max(0.0, 1.0 - abs(float(claim) - float(truth)) / scale)
    elif claim_type in {"boolean", "categorical"}:
        score = 1.0 if claim == truth else 0.0
    elif claim_type == "site_set":
        score = jaccard(claim, truth)
    elif claim_type == "numeric_interval":
        target = task["oracle"]["identified_interval"]
        distance = max(abs(float(claim[0]) - target[0]), abs(float(claim[1]) - target[1]))
        scale = max(1.0, float(target[1] - target[0]))
        score = max(0.0, 1.0 - distance / scale)
    else:
        raise ValueError(f"unknown claim type: {claim_type}")
    return score, score < 1.0


def score_submission(task: Mapping[str, Any], submission: Mapping[str, Any]) -> dict[str, Any]:
    event = 1.0 if task["oracle"]["identifiable_with_budget"] else 0.0
    q_success = float(submission["registration"]["q_success"])
    brier = (q_success - event) ** 2
    registration_score = 1.0 - brier
    evidence_score, false_claim = claim_score(task, submission)
    budget = max(1, int(submission["registration"]["budget"]))
    cost_score = max(0.0, 1.0 - float(submission["cost"]) / budget)
    total = 0.25 * registration_score + 0.65 * evidence_score + 0.10 * cost_score
    return {
        "registration_brier": brier,
        "registration_score": registration_score,
        "evidence_score": evidence_score,
        "cost_score": cost_score,
        "total_score": total,
        "false_claim": false_claim,
        "correct_abstention": submission["action"] == "abstain" and event == 0.0,
        "avoidable_abstention": submission["action"] == "abstain" and event == 1.0,
    }


def run_task_episode(split: str, family: str, seed: int, size: int, horizon: int) -> dict[str, Any]:
    task = build_task(family, seed, size, horizon)
    submissions = [calibrated_submission(task), proxy_submission(task), abstain_submission(task)]
    graded = []
    for submission in submissions:
        graded.append({**submission, "score": score_submission(task, submission)})
    public_task = {key: value for key, value in task.items() if key != "oracle"}
    oracle = task["oracle"]
    episode = {
        "schema": EPISODE_SCHEMA,
        "split": split,
        "seed": seed,
        "experimental_unit": "one seeded hidden-oracle task instance",
        "world": public_task,
        "hidden_mechanics": oracle,
        "investigations": graded,
        "oracle_receipt": {
            "oracle_present": task["oracle_present"],
            "identification": task["identification"],
            "identifiable_with_budget": oracle["identifiable_with_budget"],
            "certificate": oracle["certificate"],
            "competing_investigator_hit_target": any(
                row["policy"] == "calibrated_investigator"
                and row["score"]["evidence_score"] == 1.0
                and row["action"] == "claim"
                for row in graded
            ),
        },
    }
    episode["episode_sha256"] = task_digest(episode)
    return episode


def summarize(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    policy_rows: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    family_rows: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for episode in rows:
        family = episode["world"]["family"]
        for investigation in episode["investigations"]:
            policy_rows[(episode["split"], investigation["policy"])].append(investigation)
            family_rows[(family, investigation["policy"])].append(investigation)

    policy_summary = []
    for (split, policy), investigations in sorted(policy_rows.items()):
        claims = [row for row in investigations if row["action"] == "claim"]
        policy_summary.append(
            {
                "split": split,
                "policy": policy,
                "tasks": len(investigations),
                "mean_total_score": float(
                    statistics.mean(float(row["score"]["total_score"]) for row in investigations)
                ),
                "mean_registration_brier": float(
                    statistics.mean(float(row["score"]["registration_brier"]) for row in investigations)
                ),
                "mean_evidence_score": float(
                    statistics.mean(float(row["score"]["evidence_score"]) for row in investigations)
                ),
                "false_claim_rate": (
                    sum(bool(row["score"]["false_claim"]) for row in claims) / len(claims)
                    if claims
                    else 0.0
                ),
                "abstention_rate": sum(row["action"] == "abstain" for row in investigations)
                / len(investigations),
                "avoidable_abstention_rate": sum(
                    bool(row["score"]["avoidable_abstention"]) for row in investigations
                )
                / len(investigations),
            }
        )

    family_summary = []
    for (family, policy), investigations in sorted(family_rows.items()):
        family_summary.append(
            {
                "family": family,
                "policy": policy,
                "tasks": len(investigations),
                "mean_total_score": float(
                    statistics.mean(float(row["score"]["total_score"]) for row in investigations)
                ),
                "mean_evidence_score": float(
                    statistics.mean(float(row["score"]["evidence_score"]) for row in investigations)
                ),
            }
        )

    holdout_scores = {
        row["policy"]: row["mean_total_score"]
        for row in policy_summary
        if row["split"] == "holdout"
    }
    minimum_margin = float(manifest["analysis"]["minimum_calibrated_margin"])
    calibrated_margin = holdout_scores["calibrated_investigator"] - max(
        holdout_scores["proxy_claimant"], holdout_scores["always_abstain"]
    )
    set_task_scores = [
        float(investigation["score"]["evidence_score"])
        for episode in rows
        if episode["world"]["family"] == "masked_interval"
        for investigation in episode["investigations"]
        if investigation["policy"] == "calibrated_investigator"
        and episode["split"] in {"confirmatory", "holdout"}
    ]
    always_abstain_dominant = all(
        holdout_scores["always_abstain"] >= value
        for policy, value in holdout_scores.items()
        if policy != "always_abstain"
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "row_count": len(rows),
        "task_families": list(TASK_FAMILIES),
        "policies": list(POLICIES),
        "episode_counts": {
            split: sum(1 for row in rows if row["split"] == split) for split in SPLITS
        },
        "policy_summary": policy_summary,
        "family_summary": family_summary,
        "holdout_scores": holdout_scores,
        "calibrated_holdout_margin": calibrated_margin,
        "set_identified_mean_evidence_score": float(statistics.mean(set_task_scores)),
        "always_abstain_dominant": always_abstain_dominant,
        "hypothesis_assessment": {
            "H1_calibrated_investigator": "supported"
            if calibrated_margin >= minimum_margin
            else "not_supported",
            "H2_set_valued_reward": "supported"
            if statistics.mean(set_task_scores) >= 0.9
            else "not_supported",
            "H3_abstention_non_dominance": "supported" if not always_abstain_dominant else "not_supported",
        },
        "claim_boundary": (
            "These scores validate the curriculum mechanics and reference-policy incentives. "
            "They do not establish that a learned investigator will generalize or that the task "
            "families exhaust scientific reasoning."
        ),
    }


def build_knowledge_card(summary: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    return f"""# Hidden-Oracle Discovery Curriculum Knowledge Card

## Observed

- {summary['row_count']} seeded task episodes span {len(summary['task_families'])} families and three disjoint splits.
- Holdout mean scores: {json.dumps(summary['holdout_scores'], sort_keys=True)}.
- The calibrated investigator's holdout margin over the best control was {summary['calibrated_holdout_margin']:.4f}.
- Calibrated Level-5 interval evidence score was {summary['set_identified_mean_evidence_score']:.4f}.
- Always-abstain was dominant: {summary['always_abstain_dominant']}.
- Determinism passed: {receipt['determinism']['passed']}; wall time {receipt['wall_seconds']:.3f}s; max RSS {receipt['max_rss_mb']:.2f} MB.

## Hypothesis Assessment

- H1 calibrated investigator: **{summary['hypothesis_assessment']['H1_calibrated_investigator']}**.
- H2 set-valued reward: **{summary['hypothesis_assessment']['H2_set_valued_reward']}**.
- H3 abstention non-dominance: **{summary['hypothesis_assessment']['H3_abstention_non_dominance']}**.

## Inferred

Oracle-present set identification remains trainable: interval targets receive graded reward rather than being demoted to evaluation-only status. Scoring registration calibration plus evidence and cost prevents unconditional abstention from winning the reference tournament.

## Not Supported

- No learned AI investigator was trained or evaluated.
- Reference policies are wiring and incentive controls, not human baselines.
- Level 6 oracle-absent truth grading is not implemented.
- These small tasks do not establish transfer to They Sing, Confinement Width, biology, or frontier models.

## Robustness

The suite contains a planted nonzero effect, true null, structural unreachability, exhaustive causal-site recovery, exact conservation, a set-identified interval, and a non-point-identified task with oracle-certified abstention.

## Confounds

The calibrated reference investigator is constructed to use the exact finite-world method. Its purpose is to verify scoring incentives and schemas, not estimate realistic investigator capability.

## Artifacts

- `frozen_manifest.json`, `raw_episodes.jsonl`, `summary.json`, `seed_manifest.json`
- `receipt.json`, `hashes.json`
- Replay: `{receipt['replay_command']}`

## Next Experiment

Replace one reference policy with a real local investigator agent that must choose a design from public task data before receiving observations. Keep hidden mechanics inaccessible and score its registration forecast before executing the selected design.
"""


def parse_splits(value: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(SPLITS)
    splits = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in splits if item not in SPLITS]
    if unknown:
        raise ValueError(f"unknown splits: {unknown}")
    return splits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--splits", default="all")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output = (args.output or Path(manifest["artifacts"]["output_directory"])).resolve()
    output.mkdir(parents=True, exist_ok=True)
    splits = parse_splits(args.splits)
    seeds = manifest["seed_plan"]
    families = list(TASK_FAMILIES)
    if args.smoke:
        seeds = {split: [manifest["seed_plan"][split][0]] for split in SPLITS}
        families = ["true_null", "masked_interval", "masked_point"]
    design = manifest["design"]
    budget = manifest["budget"]
    planned = sum(len(seeds[split]) * len(families) for split in splits)
    if planned > int(budget["max_episodes"]):
        raise SystemExit("planned task episodes exceed budget")
    started = time.monotonic()
    started_utc = utc_now()
    rows: list[dict[str, Any]] = []
    with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as raw:
        for split in splits:
            size = int(design["size_by_split"][split])
            horizon = int(design["horizon_by_split"][split])
            for seed in seeds[split]:
                for family in families:
                    episode = run_task_episode(split, family, int(seed), size, horizon)
                    rows.append(episode)
                    raw.write(json.dumps(episode, sort_keys=True) + "\n")
    first_replay = run_task_episode(
        splits[0], families[0], int(seeds[splits[0]][0]), int(design["size_by_split"][splits[0]]), int(design["horizon_by_split"][splits[0]])
    )
    determinism = {
        "performed": True,
        "passed": first_replay["episode_sha256"] == rows[0]["episode_sha256"],
        "first_sha256": rows[0]["episode_sha256"],
        "replay_sha256": first_replay["episode_sha256"],
    }
    if not determinism["passed"]:
        raise SystemExit("determinism replay failed")
    summary = summarize(rows, manifest)
    summary["status"] = "ok"
    summary["determinism"] = determinism
    write_json(output / "summary.json", summary)
    write_json(
        output / "seed_manifest.json",
        {"splits_run": splits, "seeds": {split: list(seeds[split]) for split in splits}},
    )
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "status": "ok",
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "max_rss_mb": psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024),
        "episode_count": len(rows),
        "code_path": str(Path(__file__).resolve()),
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        **environment,
        "environment_sha256": sha256_bytes(json.dumps(environment, sort_keys=True).encode("utf-8")),
        "output_path": str(output),
        "determinism": determinism,
        "replay_command": (
            f"python src/discovery_curriculum.py --manifest {manifest_path} --output {output} "
            f"--splits {','.join(splits)}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(
        build_knowledge_card(summary, receipt), encoding="utf-8"
    )
    artifact_names = [
        "raw_episodes.jsonl",
        "summary.json",
        "seed_manifest.json",
        "frozen_manifest.json",
        "receipt.json",
        "knowledge_card.md",
    ]
    write_json(
        output / "hashes.json",
        {
            name: {"sha256": sha256_file(output / name), "bytes": (output / name).stat().st_size}
            for name in artifact_names
        },
    )
    total_bytes = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        raise SystemExit("artifact budget exceeded")
    print(json.dumps({"output": str(output), "status": "ok", "episodes": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
