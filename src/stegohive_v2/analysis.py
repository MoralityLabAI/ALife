"""Reconstructed pure analysis for archived StegoHive v2 episodes.

The formulas and schemas are derived from the retained raw episodes, analysis
rows, and the surviving V2--V9 detached verifier bytecode.  They intentionally
consume completed episode data only and cannot affect ecological selection.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any, Mapping

from stegohive_v1.analysis import permutation_nmi


CLASSES = ("C0", "C1", "C2", "C3")
SIGNALS = ("S0", "S1", "S2", "S3")
SKILLS = ("K0", "K1", "K2", "K3")

THRESHOLDS: dict[str, float] = {
    "bias_corrected_nmi": 0.35,
    "causal_redirect": 0.40,
    "global_relabel_retention": 0.90,
    "macro_accuracy": 0.70,
    "minimum_class_accuracy": 0.55,
    "permutation_advantage": 0.20,
    "receiver_add_back_rescue": 0.75,
    "receiver_knockout_drop": 0.15,
}
TRAINING_GATE_THRESHOLD = 0.60


def _ratio(correct: Any, total: Any) -> float:
    denominator = int(total)
    return int(correct) / denominator if denominator else 0.0


def _expanded_pairs(
    counts: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    left: list[str] = []
    right: list[str] = []
    for left_value in sorted(counts):
        for right_value in sorted(counts[left_value]):
            count = int(counts[left_value][right_value])
            left.extend([left_value] * count)
            right.extend([right_value] * count)
    return left, right


def _permutation_stat(
    counts: Mapping[str, Mapping[str, Any]], seed: int
) -> dict[str, Any]:
    left, right = _expanded_pairs(counts)
    result = permutation_nmi(left, right, seed=seed, permutations=199)
    result["permutation_seed"] = seed
    return result


def _majority_sender_mapping(checkpoint: Mapping[str, Any]) -> dict[str, str]:
    policies = checkpoint.get("slot_policies", {})
    result: dict[str, str] = {}
    for context in CLASSES:
        counts = Counter(
            policy.get("sender_map", {}).get(context)
            for policy in policies.values()
            if isinstance(policy, Mapping)
        )
        counts.pop(None, None)
        result[context] = sorted(counts, key=lambda value: (-counts[value], value))[0]
    return result


def _mapping_alignment(left: Mapping[str, str], right: Mapping[str, str]) -> float:
    return sum(left[key] == right[key] for key in CLASSES) / len(CLASSES)


def _checkpoint_analysis(
    checkpoint: Mapping[str, Any], episode_seed: int, index: int
) -> dict[str, Any]:
    metrics = checkpoint["metrics"]
    intact = metrics["intact"]
    class_accuracy = {
        key: _ratio(intact["class_correct"][key], intact["class_total"][key])
        for key in CLASSES
    }
    training = metrics["training"]
    training_class_accuracy = {
        key: _ratio(training["class_correct"][key], training["class_total"][key])
        for key in CLASSES
    }
    intact_accuracy = _ratio(intact["correct"], intact["total"])
    permutation_accuracy = _ratio(
        metrics["histogram_preserving_message_permutation"]["correct"],
        metrics["histogram_preserving_message_permutation"]["total"],
    )
    knockout_accuracy = _ratio(
        metrics["receiver_knockout"]["correct"],
        metrics["receiver_knockout"]["total"],
    )
    add_back_accuracy = _ratio(
        metrics["receiver_add_back"]["correct"],
        metrics["receiver_add_back"]["total"],
    )
    relabel_accuracy = _ratio(
        metrics["global_signal_relabel"]["correct"],
        metrics["global_signal_relabel"]["total"],
    )
    loss = max(0.0, intact_accuracy - knockout_accuracy)
    rescue = max(0.0, add_back_accuracy - knockout_accuracy)
    need_signal = _permutation_stat(
        intact["context_signal_counts"], episode_seed * 20 + index * 2 + 1
    )
    signal_skill = _permutation_stat(
        intact["signal_skill_counts"], episode_seed * 20 + index * 2 + 2
    )
    evidence = {
        "causal_symbol_swap_redirect_rate": _ratio(
            metrics["symbol_swap"]["redirected"],
            metrics["symbol_swap"]["eligible"],
        ),
        "class_accuracy": class_accuracy,
        "cross_lineage_accuracy": _ratio(
            intact["cross_lineage_correct"], intact["cross_lineage_total"]
        ),
        "global_relabel_accuracy": relabel_accuracy,
        "global_relabel_retention": (
            relabel_accuracy / intact_accuracy if intact_accuracy else 0.0
        ),
        "histogram_permutation_accuracy": permutation_accuracy,
        "histogram_permutation_advantage": intact_accuracy - permutation_accuracy,
        "intact_accuracy": intact_accuracy,
        "intact_trials": int(intact["total"]),
        "macro_accuracy": statistics.fmean(class_accuracy.values()),
        "minimum_class_accuracy": min(class_accuracy.values()),
        "nmi_need_signal": need_signal,
        "nmi_signal_skill": signal_skill,
        "receiver_add_back_accuracy": add_back_accuracy,
        "receiver_add_back_rescue_fraction": rescue / loss if loss else 0.0,
        "receiver_knockout_accuracy": knockout_accuracy,
        "receiver_knockout_drop": loss,
    }
    checks = {
        "all_four_classes_functional": evidence["minimum_class_accuracy"]
        >= THRESHOLDS["minimum_class_accuracy"],
        "causal_redirect": evidence["causal_symbol_swap_redirect_rate"]
        >= THRESHOLDS["causal_redirect"],
        "global_label_isomorphism": evidence["global_relabel_retention"]
        >= THRESHOLDS["global_relabel_retention"],
        "histogram_permutation": evidence["histogram_permutation_advantage"]
        >= THRESHOLDS["permutation_advantage"],
        "macro_functional": evidence["macro_accuracy"]
        >= THRESHOLDS["macro_accuracy"],
        "need_signal_structure": need_signal["bias_corrected"]
        >= THRESHOLDS["bias_corrected_nmi"]
        and need_signal["above_q99"],
        "receiver_necessity": evidence["receiver_knockout_drop"]
        >= THRESHOLDS["receiver_knockout_drop"],
        "receiver_rescue": evidence["receiver_add_back_rescue_fraction"]
        >= THRESHOLDS["receiver_add_back_rescue"],
        "signal_skill_structure": signal_skill["bias_corrected"]
        >= THRESHOLDS["bias_corrected_nmi"]
        and signal_skill["above_q99"],
    }
    return {
        "checkpoint_id": checkpoint["checkpoint_id"],
        "evidence": evidence,
        "metric_firewall": {
            "evidence_used_for_nomination": False,
            "fitness_feedback": bool(checkpoint["fitness_feedback_enabled"]),
            "reproduction_enabled": bool(checkpoint["reproduction_enabled"]),
        },
        "qualification": {
            "checks": checks,
            "full4": all(checks.values()),
            "thresholds": dict(THRESHOLDS),
        },
        "schema": "alife.stegohive.checkpoint_analysis.v2",
        "selection": {
            "training_class_accuracy": training_class_accuracy,
            "training_minimum_class_accuracy": min(training_class_accuracy.values()),
        },
    }


def derive_episode_analysis(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the frozen V2 analysis row from a completed episode."""

    checkpoints = list(episode["checkpoints"])
    rows = [
        _checkpoint_analysis(checkpoint, int(episode["seed"]), index)
        for index, checkpoint in enumerate(checkpoints)
    ]
    mappings = [_majority_sender_mapping(checkpoint) for checkpoint in checkpoints]
    alignments = [
        _mapping_alignment(left, right) for left, right in zip(mappings, mappings[1:])
    ]
    training_score = statistics.median(
        row["selection"]["training_minimum_class_accuracy"] for row in rows
    )
    return {
        "claim_scope": episode["claim_scope"],
        "condition_id": episode["condition"]["id"],
        "episode_id": episode["episode_id"],
        "evidence": {
            "checkpoint_count": len(rows),
            "checkpoint_rows": rows,
            "cross_cohort_mapping_alignment": (
                statistics.fmean(alignments) if alignments else 0.0
            ),
            "cross_cohort_mapping_alignments": alignments,
            "exploratory_only": True,
            "heldout_minimum_class_accuracy": min(
                row["evidence"]["minimum_class_accuracy"] for row in rows
            ),
            "persistent_full4": all(row["qualification"]["full4"] for row in rows),
        },
        "hazards": dict(episode["hazards"]),
        "metric_firewall": {
            "evidence_used_for_fitness": False,
            "evidence_used_for_nomination": False,
            "future_claim_authorized": False,
            "selection_inputs": [
                "training_repertoire_score",
                "hard_exposure_receipts",
            ],
        },
        "schema": "alife.stegohive.discovery_analysis_row.v2",
        "seed": int(episode["seed"]),
        "selection": {
            "source": "all_pairs_training_assay_only",
            "training_gate": training_score >= TRAINING_GATE_THRESHOLD,
            "training_repertoire_score": training_score,
        },
    }
