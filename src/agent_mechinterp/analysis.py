"""Pure mechanistic-evidence analyses over captured decision records."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping, Sequence

import numpy as np

from .core import CRITTERS, CanaryPolicy


def _fit_probe(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    x = np.asarray([row["activations"]["hidden_1"] for row in rows], dtype=np.float64)
    y_index = [CRITTERS.index(str(row["critter"])) for row in rows]
    y = np.eye(len(CRITTERS), dtype=np.float64)[y_index]
    design = np.column_stack([x, np.ones(len(x), dtype=np.float64)])
    penalty = np.eye(design.shape[1], dtype=np.float64) * 1e-8
    penalty[-1, -1] = 0.0
    return np.linalg.solve(design.T @ design + penalty, design.T @ y)


def _probe_accuracy(weights: np.ndarray, rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    x = np.asarray([row["activations"]["hidden_1"] for row in rows], dtype=np.float64)
    design = np.column_stack([x, np.ones(len(x), dtype=np.float64)])
    predicted = np.argmax(design @ weights, axis=1)
    actual = np.asarray([CRITTERS.index(str(row["critter"])) for row in rows])
    return float(np.mean(predicted == actual))


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / denominator) if denominator else 0.0


def analyze_decisions(
    decisions: Sequence[Mapping[str, Any]], policy: CanaryPolicy
) -> dict[str, Any]:
    """Probe, ablate, and patch without participating in any authorization path."""

    by_mode: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in decisions:
        by_mode[str(row["mode"])].append(row)
    mode_results: dict[str, Any] = {}
    for mode, rows in sorted(by_mode.items()):
        discovery = [row for row in rows if row["split"] == "discovery"]
        weights = _fit_probe(discovery)
        probe = {
            split: _probe_accuracy(weights, [row for row in rows if row["split"] == split])
            for split in ("discovery", "confirmatory", "holdout")
        }
        ablations: list[dict[str, Any]] = []
        patches: list[dict[str, Any]] = []
        lookup = {
            (row["split"], int(row["seed"]), row["critter"]): row for row in rows
        }
        for row in rows:
            critter_index = CRITTERS.index(str(row["critter"]))
            baseline_logits = row["logits"]
            selected = int(row["selected_index"])
            ablated = policy.forward(
                row["observation"]["vector"], mode=mode, zero_units=[critter_index]
            )
            ablations.append(
                {
                    "decision_id": row["decision_id"],
                    "unit": critter_index,
                    "chosen_logit_before": float(baseline_logits[selected]),
                    "chosen_logit_after": float(ablated["logits"][selected]),
                    "chosen_logit_drop": float(
                        baseline_logits[selected] - ablated["logits"][selected]
                    ),
                }
            )
            donor_critter = CRITTERS[(critter_index + 1) % len(CRITTERS)]
            donor = lookup[(row["split"], int(row["seed"]), donor_critter)]
            patched = policy.forward(
                row["observation"]["vector"],
                mode=mode,
                patch_identity=donor["activations"]["hidden_1"][:3],
            )
            patched_index = int(np.argmax(np.asarray(patched["logits"])))
            patches.append(
                {
                    "decision_id": row["decision_id"],
                    "donor_decision_id": donor["decision_id"],
                    "selected_before": row["selected_action"],
                    "selected_after": policy.actions(mode)[patched_index],
                    "action_changed": patched_index != selected,
                    "representation_cosine": _cosine(
                        row["activations"]["hidden_1"], patched["hidden_1"]
                    ),
                }
            )
        drops = [float(item["chosen_logit_drop"]) for item in ablations]
        mode_results[mode] = {
            "probe_accuracy": probe,
            "probe_fit_split": "discovery",
            "mean_chosen_logit_drop": float(np.mean(drops)) if drops else 0.0,
            "patch_action_change_fraction": float(
                np.mean([item["action_changed"] for item in patches])
            )
            if patches
            else 0.0,
            "ablations": ablations,
            "patches": patches,
        }
    return {
        "claim_scope": "model_only",
        "interpretation": (
            "Canary wiring evidence only; it is not evidence of cognition, consciousness, "
            "feature completeness, or edit safety."
        ),
        "authorization_eligible": False,
        "modes": mode_results,
    }
