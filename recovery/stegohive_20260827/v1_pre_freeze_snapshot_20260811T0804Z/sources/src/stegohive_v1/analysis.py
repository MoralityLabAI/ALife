"""Frozen-probe analysis for the StegoHive v1 signaling ecology.

This module never participates in selection.  It consumes evaluator-visible
probe rows after mutation, learning, reproduction, and resource rewards have
all been disabled.  Keeping these functions out of the environment is a small
but important metric firewall: an evidence score cannot become evolutionary
fitness by accident.
"""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence


QUALIFICATION_THRESHOLDS: dict[str, float | int] = {
    "nmi_need_signal_corrected": 0.35,
    "nmi_signal_action_corrected": 0.35,
    "intact_accuracy": 0.55,
    "class_coverage": 3,
    "causal_redirect_rate": 0.40,
    "permutation_advantage": 0.20,
    "receiver_knockout_drop": 0.15,
    "add_back_rescue_fraction": 0.75,
    "global_relabel_retention": 0.90,
    "minimum_transition_alignment": 0.75,
    "minimum_aligned_transitions": 3,
    "ood_retention": 0.80,
}


def _paired(values_a: Sequence[Any], values_b: Sequence[Any]) -> None:
    if len(values_a) != len(values_b):
        raise ValueError("paired samples must have equal lengths")
    if not values_a:
        raise ValueError("paired samples must be non-empty")


def entropy(values: Sequence[Any]) -> float:
    """Return empirical Shannon entropy in nats."""

    if not values:
        return 0.0
    counts = Counter(values)
    total = float(len(values))
    return -sum(
        (count / total) * math.log(count / total)
        for count in counts.values()
        if count
    )


def mutual_information(values_a: Sequence[Any], values_b: Sequence[Any]) -> float:
    """Return empirical mutual information in nats."""

    _paired(values_a, values_b)
    count_a = Counter(values_a)
    count_b = Counter(values_b)
    joint = Counter(zip(values_a, values_b))
    total = float(len(values_a))
    result = 0.0
    for (value_a, value_b), count in joint.items():
        p_joint = count / total
        p_a = count_a[value_a] / total
        p_b = count_b[value_b] / total
        result += p_joint * math.log(p_joint / (p_a * p_b))
    return max(0.0, result)


def normalized_mutual_information(
    values_a: Sequence[Any], values_b: Sequence[Any]
) -> float:
    """Symmetric NMI using ``sqrt(H(A) H(B))`` as the denominator."""

    _paired(values_a, values_b)
    denominator = math.sqrt(entropy(values_a) * entropy(values_b))
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, mutual_information(values_a, values_b) / denominator))


def permutation_nmi(
    values_a: Sequence[Any],
    values_b: Sequence[Any],
    *,
    seed: int,
    permutations: int = 199,
) -> dict[str, float | int | bool]:
    """Measure NMI against a deterministic within-episode permutation null.

    The corrected statistic scales the observed excess over the mean null to
    the remaining unit interval.  This makes the pre-registered ``0.35``
    threshold comparable across finite probe sizes while retaining a separate
    requirement that observed NMI exceed the empirical 99th percentile.
    """

    _paired(values_a, values_b)
    if permutations < 19:
        raise ValueError("at least 19 permutations are required")
    observed = normalized_mutual_information(values_a, values_b)
    rng = random.Random(int(seed))
    permuted = list(values_b)
    null_values: list[float] = []
    for _ in range(int(permutations)):
        rng.shuffle(permuted)
        null_values.append(normalized_mutual_information(values_a, permuted))
    null_values.sort()
    null_mean = statistics.fmean(null_values)
    quantile_index = max(
        0,
        min(len(null_values) - 1, math.ceil(0.99 * len(null_values)) - 1),
    )
    null_q99 = null_values[quantile_index]
    remaining = max(1e-12, 1.0 - null_mean)
    corrected = max(0.0, min(1.0, (observed - null_mean) / remaining))
    return {
        "observed": observed,
        "null_mean": null_mean,
        "null_q99": null_q99,
        "bias_corrected": corrected,
        "above_q99": bool(observed > null_q99),
        "permutations": int(permutations),
    }


def accuracy(trials: Sequence[Mapping[str, Any]]) -> float:
    if not trials:
        return 0.0
    return sum(bool(trial.get("correct_outcome")) for trial in trials) / len(trials)


def class_coverage(trials: Sequence[Mapping[str, Any]]) -> int:
    """Number of need classes represented by at least one correct response."""

    return len(
        {
            trial.get("hidden_need")
            for trial in trials
            if trial.get("correct_outcome") is True
        }
    )


def mapping_alignment(left: Mapping[Any, Any], right: Mapping[Any, Any]) -> float:
    """Direct agreement for one persistent alphabet across two cohorts."""

    keys = sorted(set(left) & set(right), key=repr)
    if not keys:
        return 0.0
    return sum(left[key] == right[key] for key in keys) / len(keys)


def _branch_trials(
    evaluations: Mapping[str, Any], name: str
) -> list[Mapping[str, Any]]:
    branch = evaluations.get(name, {})
    if not isinstance(branch, Mapping):
        return []
    rows = branch.get("trials", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _counterfactual_redirect_rate(trials: Sequence[Mapping[str, Any]]) -> float:
    eligible = [
        row
        for row in trials
        if row.get("forced_signal") != row.get("emitted_signal")
        and row.get("decoded_action_for_forced_signal") is not None
    ]
    if not eligible:
        return 0.0
    redirected = 0
    for row in eligible:
        if isinstance(row.get("redirect_toward_forced_signal"), bool):
            redirected += int(row["redirect_toward_forced_signal"])
            continue
        expected = row.get("learned_action_for_forced_signal")
        actual = row.get("decoded_action_for_forced_signal")
        original = row.get("receiver_action")
        if expected is not None and actual == expected and actual != original:
            redirected += 1
    return redirected / len(eligible)


def derive_probe_evidence(
    episode: Mapping[str, Any],
    *,
    permutation_seed: int | None = None,
    permutations: int = 199,
) -> dict[str, Any]:
    """Independently derive all pre-registered frozen-probe evidence."""

    evaluations = episode.get("evaluations", {})
    if not isinstance(evaluations, Mapping):
        evaluations = {}
    intact = _branch_trials(evaluations, "intact")
    needs = [row.get("hidden_need") for row in intact]
    signals = [row.get("emitted_signal") for row in intact]
    actions = [row.get("receiver_action") for row in intact]
    seed = int(episode.get("seed", 0) if permutation_seed is None else permutation_seed)
    if intact:
        need_signal = permutation_nmi(
            needs, signals, seed=seed * 2 + 1, permutations=permutations
        )
        signal_action = permutation_nmi(
            signals, actions, seed=seed * 2 + 2, permutations=permutations
        )
    else:
        empty = {
            "observed": 0.0,
            "null_mean": 0.0,
            "null_q99": 0.0,
            "bias_corrected": 0.0,
            "above_q99": False,
            "permutations": int(permutations),
        }
        need_signal = dict(empty)
        signal_action = dict(empty)

    intact_accuracy = accuracy(intact)
    cross_lineage = [
        row
        for row in intact
        if row.get("sender_lineage_id") is not None
        and row.get("receiver_lineage_id") is not None
        and row.get("sender_lineage_id") != row.get("receiver_lineage_id")
    ]
    permutation_accuracy = accuracy(
        _branch_trials(evaluations, "per_message_permutation")
    )
    knockout_accuracy = accuracy(_branch_trials(evaluations, "receiver_knockout"))
    add_back_accuracy = accuracy(_branch_trials(evaluations, "add_back"))
    global_relabel_accuracy = accuracy(
        _branch_trials(evaluations, "global_relabel")
    )
    ood_accuracy = accuracy(_branch_trials(evaluations, "ood_topology"))
    delayed_archive_accuracy = accuracy(
        _branch_trials(evaluations, "delayed_archive")
    )
    loss = max(0.0, intact_accuracy - knockout_accuracy)
    rescue = max(0.0, add_back_accuracy - knockout_accuracy)

    mappings = episode.get("cohort_mappings", [])
    if not isinstance(mappings, list) or not mappings:
        mappings = []
        turnover_rows = episode.get("cohort_turnovers", [])
        if isinstance(turnover_rows, list):
            for row in turnover_rows:
                if not isinstance(row, Mapping):
                    continue
                mapping = row.get("need_to_signal")
                if not isinstance(mapping, Mapping):
                    nested = row.get("mapping")
                    if isinstance(nested, Mapping):
                        mapping = nested.get("need_to_signal", nested)
                if isinstance(mapping, Mapping):
                    mappings.append({"need_to_signal": mapping})
    transition_alignments: list[float] = []
    if isinstance(mappings, list):
        for left, right in zip(mappings, mappings[1:]):
            if isinstance(left, Mapping) and isinstance(right, Mapping):
                left_map = left.get("need_to_signal", left)
                right_map = right.get("need_to_signal", right)
                if isinstance(left_map, Mapping) and isinstance(right_map, Mapping):
                    transition_alignments.append(mapping_alignment(left_map, right_map))

    return {
        "nmi_need_signal": need_signal,
        "nmi_signal_action": signal_action,
        "intact_accuracy": intact_accuracy,
        "class_coverage": class_coverage(intact),
        "cross_lineage_trials": len(cross_lineage),
        "cross_lineage_accuracy": accuracy(cross_lineage),
        "permutation_accuracy": permutation_accuracy,
        "permutation_advantage": intact_accuracy - permutation_accuracy,
        "causal_redirect_rate": _counterfactual_redirect_rate(
            _branch_trials(evaluations, "symbol_swap")
        ),
        "receiver_knockout_accuracy": knockout_accuracy,
        "receiver_knockout_drop": loss,
        "add_back_accuracy": add_back_accuracy,
        "add_back_rescue_fraction": rescue / loss if loss > 0.0 else 0.0,
        "global_relabel_accuracy": global_relabel_accuracy,
        "global_relabel_retention": (
            global_relabel_accuracy / intact_accuracy if intact_accuracy > 0.0 else 0.0
        ),
        "transition_alignments": transition_alignments,
        "minimum_transition_alignment": (
            min(transition_alignments[-3:]) if len(transition_alignments) >= 3 else 0.0
        ),
        "aligned_transition_count": len(transition_alignments),
        "ood_accuracy": ood_accuracy,
        "ood_retention": ood_accuracy / intact_accuracy if intact_accuracy > 0.0 else 0.0,
        "delayed_archive_accuracy": delayed_archive_accuracy,
        "delayed_archive_advantage_over_no_channel": (
            delayed_archive_accuracy
            - accuracy(_branch_trials(evaluations, "no_channel"))
        ),
        "probe_trials": len(intact),
    }


def qualify_emergence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the frozen conjunctive definition; never infer from fitness."""

    nmi_need_signal = evidence.get("nmi_need_signal", {})
    nmi_signal_action = evidence.get("nmi_signal_action", {})
    checks = {
        "need_signal_structure": bool(
            isinstance(nmi_need_signal, Mapping)
            and float(nmi_need_signal.get("bias_corrected", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["nmi_need_signal_corrected"])
            and nmi_need_signal.get("above_q99") is True
        ),
        "signal_action_structure": bool(
            isinstance(nmi_signal_action, Mapping)
            and float(nmi_signal_action.get("bias_corrected", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["nmi_signal_action_corrected"])
            and nmi_signal_action.get("above_q99") is True
        ),
        "functional_decoding": bool(
            float(evidence.get("intact_accuracy", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["intact_accuracy"])
            and int(evidence.get("class_coverage", 0))
            >= int(QUALIFICATION_THRESHOLDS["class_coverage"])
        ),
        "causal_transfer": bool(
            float(evidence.get("causal_redirect_rate", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["causal_redirect_rate"])
            and float(evidence.get("permutation_advantage", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["permutation_advantage"])
        ),
        "receiver_necessity_and_rescue": bool(
            float(evidence.get("receiver_knockout_drop", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["receiver_knockout_drop"])
            and float(evidence.get("add_back_rescue_fraction", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["add_back_rescue_fraction"])
        ),
        "global_label_isomorphism": bool(
            float(evidence.get("global_relabel_retention", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["global_relabel_retention"])
        ),
        "temporal_convention": bool(
            int(evidence.get("aligned_transition_count", 0))
            >= int(QUALIFICATION_THRESHOLDS["minimum_aligned_transitions"])
            and float(evidence.get("minimum_transition_alignment", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["minimum_transition_alignment"])
        ),
        "ood_abstraction": bool(
            float(evidence.get("ood_retention", 0.0))
            >= float(QUALIFICATION_THRESHOLDS["ood_retention"])
        ),
    }
    return {
        "qualified": all(checks.values()),
        "checks": checks,
        "thresholds": dict(QUALIFICATION_THRESHOLDS),
        "metric_firewall": "frozen_nonrewarding_probes_only",
    }


def qualification_frequency(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = [bool(row.get("qualification", {}).get("qualified")) for row in rows]
    return {
        "episodes": len(values),
        "qualified": sum(values),
        "frequency": sum(values) / len(values) if values else 0.0,
    }
