#!/usr/bin/env python3
"""Cultivate a graph-state ALife investigator with bounded active search.

The investigator sees structural deltas for a sealed bank of graph-pair
experiments. It may query only a frozen subset of outcomes. A full-bank
Bayesian posterior is computed afterward as a finite-task grading oracle.

The constitutional layer in this v1 campaign is deliberately audit-only:
typed lattice proposals are applied to the public trace while a shadow
membrane records what a strict Hybrid LDT/TRM policy would have blocked.
Operational integrity checks (budget, graph invariants, hashes, and replay)
remain fail-closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx
import numpy as np
import psutil

from graph_state_lab import (
    advance,
    build_graph,
    channel_matrix,
    check_budget,
    current_rss_mb,
    graph_receipt,
    neighbor_table,
    state_digest,
)


TASK_SCHEMA = "alife.graph_investigator.task.v1"
GRAPH_ARM_SCHEMA = "alife.graph_investigator.graph_arm.v1"
POLICY_SCHEMA = "alife.graph_investigator.policy_freeze.v1"
SUMMARY_SCHEMA = "alife.graph_investigator.summary.v1"
RECEIPT_SCHEMA = "alife.graph_investigator.receipt.v1"
VERIFICATION_SCHEMA = "alife.graph_investigator.verification.v1"
SPLITS = ("discovery", "confirmatory", "holdout")
DESCRIPTORS = ("spectral_gap", "average_clustering", "average_shortest_path")
MODELS: dict[str, tuple[int, ...]] = {
    "null": (),
    "spectral_gap": (0,),
    "clustering": (1,),
    "path_length": (2,),
    "joint": (0, 1, 2),
}
MODEL_NAMES = tuple(MODELS)
EIG_POLICIES = ("sheaf_eig", "local_eig", "global_eig")
RANDOM_REPLICATES = 4
GAUSS_HERMITE_NODES, GAUSS_HERMITE_WEIGHTS = np.polynomial.hermite.hermgauss(9)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def stable_int(*parts: Any, modulus: int = 2**31 - 1) -> int:
    digest = hashlib.sha256(canonical_bytes(list(parts))).digest()
    return int.from_bytes(digest[:8], "big") % modulus


def logsumexp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + math.log(float(np.exp(values - maximum).sum()))


def softmax_log(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return np.exp(array - logsumexp(array))


def normal_logpdf(value: float, mean: float, variance: float) -> float:
    variance = max(float(variance), 1e-12)
    return -0.5 * (
        math.log(2.0 * math.pi * variance) + (float(value) - mean) ** 2 / variance
    )


def entropy(probabilities: Sequence[float]) -> float:
    values = np.asarray(probabilities, dtype=float)
    values = values[values > 0.0]
    return -float(np.sum(values * np.log(values))) if values.size else 0.0


def js_divergence(left: Sequence[float], right: Sequence[float]) -> float:
    p = np.asarray(left, dtype=float)
    q = np.asarray(right, dtype=float)
    midpoint = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0.0
        return float(np.sum(a[mask] * np.log(a[mask] / np.maximum(b[mask], 1e-15))))

    return 0.5 * kl(p, midpoint) + 0.5 * kl(q, midpoint)


def patch_edges(patches: Sequence[Mapping[str, Any]]) -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = []
    for left in range(len(patches)):
        for right in range(left + 1, len(patches)):
            differences = sum(
                patches[left][key] != patches[right][key]
                for key in ("degree", "coupling")
            )
            if differences == 1:
                edges.append((left, right))
    return edges


def normalized_patch_laplacian(
    patches: Sequence[Mapping[str, Any]],
    priors: Mapping[str, Sequence[float]],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    count = len(patches)
    adjacency = np.zeros((count, count), dtype=float)
    raw_edges: list[tuple[int, int, float, float]] = []
    divergences = [
        js_divergence(priors[patches[left]["id"]], priors[patches[right]["id"]])
        for left, right in patch_edges(patches)
    ]
    positive = [value for value in divergences if value > 1e-12]
    scale = statistics.median(positive) if positive else 1.0
    for (left, right), divergence in zip(patch_edges(patches), divergences):
        weight = max(0.05, min(1.0, math.exp(-divergence / max(scale, 1e-12))))
        adjacency[left, right] = weight
        adjacency[right, left] = weight
        raw_edges.append((left, right, weight, divergence))
    degrees = adjacency.sum(axis=1)
    if np.any(degrees <= 0.0):
        raise ValueError("context patch graph contains an isolated patch")
    inverse = np.diag(1.0 / np.sqrt(degrees))
    laplacian = np.eye(count) - inverse @ adjacency @ inverse
    laplacian = 0.5 * (laplacian + laplacian.T)
    edge_rows = [
        {
            "left": patches[left]["id"],
            "right": patches[right]["id"],
            "weight": weight,
            "prior_js_divergence": divergence,
            "restriction": "identity_on_shared_hypothesis_coordinates",
        }
        for left, right, weight, divergence in raw_edges
    ]
    return laplacian, edge_rows


def smooth_patch_priors(
    patches: Sequence[Mapping[str, Any]],
    local_priors: Mapping[str, Sequence[float]],
    regularization: float,
) -> tuple[dict[str, list[float]], dict[str, Any]]:
    laplacian, edges = normalized_patch_laplacian(patches, local_priors)
    ordered = np.asarray(
        [
            np.log(np.maximum(np.asarray(local_priors[patch["id"]], dtype=float), 1e-12))
            for patch in patches
        ]
    )
    smoothed = np.linalg.solve(
        np.eye(len(patches)) + float(regularization) * laplacian,
        ordered,
    )
    priors = {
        patch["id"]: softmax_log(smoothed[index]).tolist()
        for index, patch in enumerate(patches)
    }
    eigenvalues = np.linalg.eigvalsh(laplacian)
    return priors, {
        "schema": "alife.graph_investigator.context_sheaf.v1",
        "patches": [patch["id"] for patch in patches],
        "edges": edges,
        "normalized_laplacian": laplacian.tolist(),
        "eigenvalues": eigenvalues.tolist(),
        "spectral_gap": float(
            next((value for value in eigenvalues if value > 1e-10), 0.0)
        ),
        "regularization": float(regularization),
        "restriction_maps": "identity",
        "holonomy": "trivial_by_construction_not_an_empirical_transport_claim",
    }


def graph_with_retry(
    nodes: int,
    degree: int,
    seed: int,
    rewires: int,
) -> nx.Graph:
    topology = "ring_regular" if rewires == 0 else "rewired_regular"
    last_error: Exception | None = None
    for attempt in range(20):
        try:
            return build_graph(
                topology,
                nodes=nodes,
                degree=degree,
                seed=seed + attempt,
                rewires=rewires,
            )
        except (RuntimeError, nx.NetworkXException) as exc:
            last_error = exc
    raise RuntimeError(
        f"could not build connected graph after 20 attempts: {last_error}"
    )


def build_candidate_pool(
    task_id: str,
    nodes: int,
    degree: int,
    pool_seeds: int,
    rewire_doses: Sequence[int],
    deadline: float,
    max_ram_mb: float,
) -> tuple[list[dict[str, Any]], dict[str, nx.Graph]]:
    records: list[dict[str, Any]] = []
    graphs: dict[str, nx.Graph] = {}
    for seed_index in range(pool_seeds):
        for dose_index, rewires in enumerate(rewire_doses):
            check_budget(deadline, max_ram_mb)
            graph_seed = stable_int(task_id, "graph", seed_index, dose_index, rewires)
            graph = graph_with_retry(nodes, degree, graph_seed, int(rewires))
            receipt = graph_receipt(graph, degree)
            graph_id = f"g{seed_index:02d}-r{int(rewires):03d}"
            record = {
                "graph_id": graph_id,
                "graph_seed": graph_seed,
                "rewires": int(rewires),
                "edge_sha256": receipt["edge_sha256"],
                "descriptors": {
                    key: float(receipt[key]) for key in DESCRIPTORS
                },
                "invariants": {
                    "connected": bool(receipt["connected"]),
                    "degree_min": int(receipt["degree_min"]),
                    "degree_max": int(receipt["degree_max"]),
                    "nodes": int(receipt["nodes"]),
                    "edges": int(receipt["edges"]),
                },
            }
            records.append(record)
            graphs[graph_id] = graph
    return records, graphs


def construct_pair_bank(
    task_id: str,
    records: Sequence[Mapping[str, Any]],
    pairs_per_descriptor: int,
) -> list[dict[str, Any]]:
    raw = np.asarray(
        [
            [float(record["descriptors"][key]) for key in DESCRIPTORS]
            for record in records
        ],
        dtype=float,
    )
    means = raw.mean(axis=0)
    scales = raw.std(axis=0)
    scales[scales <= 1e-12] = 1.0
    standardized = (raw - means) / scales
    ranked: dict[int, list[tuple[float, str, int, int, np.ndarray]]] = {}
    for target in range(len(DESCRIPTORS)):
        rows: list[tuple[float, str, int, int, np.ndarray]] = []
        for left in range(len(records)):
            for right in range(left + 1, len(records)):
                if records[left]["edge_sha256"] == records[right]["edge_sha256"]:
                    continue
                delta = standardized[right] - standardized[left]
                if delta[target] < 0.0:
                    oriented_left, oriented_right = right, left
                    delta = -delta
                else:
                    oriented_left, oriented_right = left, right
                score = float(delta[target]) / (
                    0.25
                    + sum(abs(float(delta[index])) for index in range(3) if index != target)
                )
                pair_key = (
                    f"{records[oriented_left]['graph_id']}--"
                    f"{records[oriented_right]['graph_id']}"
                )
                rows.append(
                    (score, pair_key, oriented_left, oriented_right, delta.copy())
                )
        ranked[target] = sorted(rows, key=lambda row: (-row[0], row[1]))

    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_hashes: set[str] = set()
    for round_index in range(pairs_per_descriptor):
        for target in range(len(DESCRIPTORS)):
            winner = None
            for row in ranked[target]:
                _, _, left_index, right_index, _ = row
                left = records[left_index]
                right = records[right_index]
                ids = {str(left["graph_id"]), str(right["graph_id"])}
                hashes = {str(left["edge_sha256"]), str(right["edge_sha256"])}
                if ids & used_ids or hashes & used_hashes:
                    continue
                winner = row
                break
            if winner is None:
                raise RuntimeError(
                    f"candidate pool could not supply disjoint {DESCRIPTORS[target]} pair"
                )
            score, _, left_index, right_index, delta = winner
            left = records[left_index]
            right = records[right_index]
            used_ids.update((str(left["graph_id"]), str(right["graph_id"])))
            used_hashes.update((str(left["edge_sha256"]), str(right["edge_sha256"])))
            pair_id = (
                f"{DESCRIPTORS[target]}-{round_index + 1}-"
                f"{canonical_sha256([task_id, left['graph_id'], right['graph_id']])[:10]}"
            )
            nuisance = [
                abs(float(delta[index])) for index in range(3) if index != target
            ]
            selected.append(
                {
                    "pair_id": pair_id,
                    "target_descriptor": DESCRIPTORS[target],
                    "left_graph_id": left["graph_id"],
                    "right_graph_id": right["graph_id"],
                    "left_edge_sha256": left["edge_sha256"],
                    "right_edge_sha256": right["edge_sha256"],
                    "x": [float(value) for value in delta],
                    "target_separation_z": float(delta[target]),
                    "maximum_nuisance_z": max(nuisance),
                    "pair_score": float(score),
                    "balanced_for_single_descriptor_claim": (
                        float(delta[target]) >= 0.5 and max(nuisance) <= 0.25
                    ),
                }
            )
    return sorted(selected, key=lambda row: row["pair_id"])


def simulate_graph_arm(
    *,
    task_id: str,
    graph_id: str,
    graph: nx.Graph,
    graph_metadata: Mapping[str, Any],
    split: str,
    seed: int,
    patch: Mapping[str, Any],
    state_dimension: int,
    steps: int,
    burn_in: int,
    perturbation_channel: int,
    perturbation_magnitude: float,
    initial_state: np.ndarray,
    deadline: float,
    max_ram_mb: float,
) -> dict[str, Any]:
    started = time.monotonic()
    neighbors = neighbor_table(graph)
    matrix = channel_matrix(state_dimension)
    baseline = initial_state.copy()
    perturbed = initial_state.copy()
    intervention_node = int(seed) % graph.number_of_nodes()
    perturbation_channel = int(perturbation_channel) % state_dimension
    perturbed[intervention_node, perturbation_channel] = np.clip(
        perturbed[intervention_node, perturbation_channel] + perturbation_magnitude,
        -1.0,
        1.0,
    )
    initial_difference = float(np.linalg.norm(perturbed - baseline))
    half_life: int | None = None
    post_ratios: list[float] = []
    max_rss = current_rss_mb()
    for tick in range(1, steps + 1):
        check_budget(deadline, max_ram_mb)
        baseline = advance(baseline, neighbors, matrix, float(patch["coupling"]))
        perturbed = advance(perturbed, neighbors, matrix, float(patch["coupling"]))
        ratio = float(np.linalg.norm(perturbed - baseline)) / max(
            initial_difference, 1e-12
        )
        if half_life is None and ratio <= 0.5:
            half_life = tick
        if tick >= burn_in:
            post_ratios.append(ratio)
        max_rss = max(max_rss, current_rss_mb())
    final_ratio = post_ratios[-1]
    return {
        "schema": GRAPH_ARM_SCHEMA,
        "task_id": task_id,
        "graph_id": graph_id,
        "split": split,
        "seed": int(seed),
        "patch_id": patch["id"],
        "condition": {
            "nodes": graph.number_of_nodes(),
            "degree": int(patch["degree"]),
            "coupling": float(patch["coupling"]),
            "state_dimension": int(state_dimension),
            "steps": int(steps),
            "burn_in": int(burn_in),
        },
        "graph": {
            "edge_sha256": graph_metadata["edge_sha256"],
            "rewires": int(graph_metadata["rewires"]),
            **graph_metadata["descriptors"],
        },
        "intervention": {
            "node": intervention_node,
            "channel": perturbation_channel,
            "magnitude": float(perturbation_magnitude),
            "initial_difference_norm": initial_difference,
            "eligible": True,
            "activated": True,
            "executed": initial_difference > 0.0,
        },
        "outcomes": {
            "final_perturbation_ratio": final_ratio,
            "log_final_perturbation_ratio": math.log10(max(final_ratio, 1e-12)),
            "post_burn_mean_perturbation_ratio": float(
                statistics.mean(post_ratios)
            ),
            "recovery_half_life": half_life,
            "recovery_censored": half_life is None,
        },
        "provenance": {
            "initial_state_sha256": state_digest(initial_state),
            "final_state_sha256": state_digest(baseline),
            "final_perturbed_state_sha256": state_digest(perturbed),
            "runtime_seconds": time.monotonic() - started,
            "max_rss_mb": max_rss,
        },
    }


def deterministic_bank_projection(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "split": task["split"],
        "seed": task["seed"],
        "patch": task["patch"],
        "world": task["world"],
        "candidate_pool_receipt": task["candidate_pool_receipt"],
        "candidates": [
            {
                key: candidate[key]
                for key in (
                    "pair_id",
                    "target_descriptor",
                    "left_graph_id",
                    "right_graph_id",
                    "left_edge_sha256",
                    "right_edge_sha256",
                    "x",
                    "target_separation_z",
                    "maximum_nuisance_z",
                    "pair_score",
                    "balanced_for_single_descriptor_claim",
                    "y",
                    "left_log_recovery",
                    "right_log_recovery",
                )
            }
            for candidate in task["candidates"]
        ],
    }


def build_task_bank(
    manifest: Mapping[str, Any],
    split: str,
    seed: int,
    patch: Mapping[str, Any],
    deadline: float,
    max_ram_mb: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    design = manifest["design"]
    split_design = design["split_design"][split]
    task_id = f"{split}-{int(seed)}-{patch['id']}"
    pool, graphs = build_candidate_pool(
        task_id,
        nodes=int(split_design["nodes"]),
        degree=int(patch["degree"]),
        pool_seeds=int(design["pool_seeds"]),
        rewire_doses=[int(value) for value in design["rewire_doses"]],
        deadline=deadline,
        max_ram_mb=max_ram_mb,
    )
    pairs = construct_pair_bank(
        task_id,
        pool,
        pairs_per_descriptor=int(design["pairs_per_descriptor"]),
    )
    state_dimension = int(split_design["state_dimension"])
    rng = np.random.default_rng(stable_int(task_id, "initial_state"))
    initial_state = np.clip(
        rng.normal(
            0.0,
            0.25,
            size=(int(split_design["nodes"]), state_dimension),
        ),
        -1.0,
        1.0,
    )
    magnitude_values = [
        float(value) for value in split_design["perturbation_magnitudes"]
    ]
    magnitude = magnitude_values[int(seed) % len(magnitude_values)]
    channel = (
        0
        if split != "holdout"
        else stable_int(task_id, "channel", modulus=state_dimension)
    )
    by_id = {record["graph_id"]: record for record in pool}
    graph_rows: list[dict[str, Any]] = []
    simulated: dict[str, dict[str, Any]] = {}
    for pair in pairs:
        for graph_id in (pair["left_graph_id"], pair["right_graph_id"]):
            if graph_id in simulated:
                continue
            row = simulate_graph_arm(
                task_id=task_id,
                graph_id=graph_id,
                graph=graphs[graph_id],
                graph_metadata=by_id[graph_id],
                split=split,
                seed=int(seed),
                patch=patch,
                state_dimension=state_dimension,
                steps=int(split_design["steps"]),
                burn_in=int(split_design["burn_in"]),
                perturbation_channel=channel,
                perturbation_magnitude=magnitude,
                initial_state=initial_state,
                deadline=deadline,
                max_ram_mb=max_ram_mb,
            )
            simulated[graph_id] = row
            graph_rows.append(row)
    candidates: list[dict[str, Any]] = []
    for pair in pairs:
        left = simulated[pair["left_graph_id"]]
        right = simulated[pair["right_graph_id"]]
        left_log = float(left["outcomes"]["log_final_perturbation_ratio"])
        right_log = float(right["outcomes"]["log_final_perturbation_ratio"])
        candidates.append(
            {
                **pair,
                "y": right_log - left_log,
                "left_log_recovery": left_log,
                "right_log_recovery": right_log,
                "exposure": {
                    "eligible_graph_arms": 2,
                    "activated_perturbations": 2,
                    "executed_perturbations": sum(
                        bool(row["intervention"]["executed"])
                        for row in (left, right)
                    ),
                    "downstream_outcomes": 2,
                },
            }
        )
    task = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "split": split,
        "seed": int(seed),
        "experimental_unit": (
            "one sealed graph-pair bank; policies are paired repeated views"
        ),
        "patch": {
            "id": patch["id"],
            "degree": int(patch["degree"]),
            "coupling": float(patch["coupling"]),
        },
        "world": {
            "nodes": int(split_design["nodes"]),
            "state_dimension": state_dimension,
            "steps": int(split_design["steps"]),
            "burn_in": int(split_design["burn_in"]),
            "perturbation_channel": int(channel),
            "perturbation_magnitude": float(magnitude),
        },
        "candidate_pool_receipt": {
            "declared_candidates": len(pool),
            "unique_edge_hashes": len(
                {str(record["edge_sha256"]) for record in pool}
            ),
            "selected_pairs": len(candidates),
            "selected_unique_graphs": len(
                {
                    candidate[key]
                    for candidate in candidates
                    for key in ("left_graph_id", "right_graph_id")
                }
            ),
            "pool_sha256": canonical_sha256(
                [
                    {
                        key: record[key]
                        for key in (
                            "graph_id",
                            "graph_seed",
                            "rewires",
                            "edge_sha256",
                            "descriptors",
                        )
                    }
                    for record in pool
                ]
            ),
        },
        "candidates": candidates,
    }
    task["task_bank_sha256"] = canonical_sha256(deterministic_bank_projection(task))
    return task, graph_rows


@dataclass
class LinearBelief:
    indices: tuple[int, ...]
    mean: np.ndarray
    covariance: np.ndarray

    @classmethod
    def create(cls, indices: tuple[int, ...], tau2: float) -> "LinearBelief":
        return cls(
            indices=indices,
            mean=np.zeros(len(indices), dtype=float),
            covariance=np.eye(len(indices), dtype=float) * float(tau2),
        )

    def predictive(self, x_full: Sequence[float], noise_variance: float) -> tuple[float, float]:
        if not self.indices:
            return 0.0, float(noise_variance)
        x = np.asarray([x_full[index] for index in self.indices], dtype=float)
        return (
            float(x @ self.mean),
            float(noise_variance + x @ self.covariance @ x),
        )

    def update(self, x_full: Sequence[float], y: float, noise_variance: float) -> None:
        if not self.indices:
            return
        x = np.asarray([x_full[index] for index in self.indices], dtype=float)
        predictive_variance = float(
            noise_variance + x @ self.covariance @ x
        )
        gain = self.covariance @ x / max(predictive_variance, 1e-12)
        prediction = float(x @ self.mean)
        self.mean = self.mean + gain * (float(y) - prediction)
        self.covariance = self.covariance - np.outer(gain, x) @ self.covariance
        self.covariance = 0.5 * (self.covariance + self.covariance.T)


class BayesianInvestigator:
    """Model-posterior state with outcome-blind action selection."""

    def __init__(
        self,
        prior: Sequence[float],
        *,
        noise_std: float,
        tau2: float,
    ) -> None:
        probabilities = np.asarray(prior, dtype=float)
        probabilities = probabilities / probabilities.sum()
        self.log_weights = np.log(np.maximum(probabilities, 1e-15))
        self.noise_variance = float(noise_std) ** 2
        self.models = {
            name: LinearBelief.create(indices, tau2)
            for name, indices in MODELS.items()
        }

    @property
    def probabilities(self) -> np.ndarray:
        return softmax_log(self.log_weights)

    def predict_model(
        self, name: str, x: Sequence[float]
    ) -> tuple[float, float]:
        return self.models[name].predictive(x, self.noise_variance)

    def mixture_mean(self, x: Sequence[float]) -> float:
        return float(
            sum(
                probability * self.predict_model(name, x)[0]
                for probability, name in zip(self.probabilities, MODEL_NAMES)
            )
        )

    def update(self, x: Sequence[float], y: float) -> None:
        predictive = {
            name: self.predict_model(name, x) for name in MODEL_NAMES
        }
        self.log_weights = self.log_weights + np.asarray(
            [
                normal_logpdf(y, predictive[name][0], predictive[name][1])
                for name in MODEL_NAMES
            ]
        )
        self.log_weights = self.log_weights - logsumexp(self.log_weights)
        for model in self.models.values():
            model.update(x, y, self.noise_variance)

    def expected_information_gain(self, x: Sequence[float]) -> float:
        probabilities = self.probabilities
        current_entropy = entropy(probabilities)
        predictive = [self.predict_model(name, x) for name in MODEL_NAMES]
        expected_entropy = 0.0
        normalizer = math.sqrt(math.pi)
        for source_index, source_probability in enumerate(probabilities):
            source_mean, source_variance = predictive[source_index]
            for node, weight in zip(GAUSS_HERMITE_NODES, GAUSS_HERMITE_WEIGHTS):
                y = source_mean + math.sqrt(2.0 * source_variance) * float(node)
                hypothetical = self.log_weights + np.asarray(
                    [
                        normal_logpdf(y, mean, variance)
                        for mean, variance in predictive
                    ]
                )
                posterior = softmax_log(hypothetical)
                expected_entropy += (
                    float(source_probability)
                    * float(weight)
                    / normalizer
                    * entropy(posterior)
                )
        return max(0.0, current_entropy - expected_entropy)

    def jsonable(self) -> dict[str, Any]:
        return {
            "model_order": list(MODEL_NAMES),
            "model_probabilities": self.probabilities.tolist(),
            "noise_variance": self.noise_variance,
            "models": {
                name: {
                    "feature_indices": list(model.indices),
                    "mean": model.mean.tolist(),
                    "covariance": model.covariance.tolist(),
                }
                for name, model in self.models.items()
            },
        }


def credible_set(probabilities: Sequence[float], mass: float = 0.9) -> list[str]:
    ordered = sorted(
        zip(probabilities, MODEL_NAMES),
        key=lambda row: (-float(row[0]), row[1]),
    )
    result: list[str] = []
    cumulative = 0.0
    for probability, name in ordered:
        result.append(name)
        cumulative += float(probability)
        if cumulative >= mass:
            break
    return sorted(result)


def candidate_public(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: candidate[key]
        for key in (
            "pair_id",
            "target_descriptor",
            "x",
            "target_separation_z",
            "maximum_nuisance_z",
            "pair_score",
            "balanced_for_single_descriptor_claim",
        )
    }


def audit_lattice_step(
    *,
    before: Mapping[str, Sequence[str]],
    after: Mapping[str, Sequence[str]],
    proposal: Mapping[str, Any],
    final_claim: Mapping[str, Any] | None = None,
    queried: Sequence[Mapping[str, Any]] = (),
    verified_soundness: str = "model_sound_dead",
    audit_enabled: bool = True,
) -> dict[str, Any]:
    if not audit_enabled:
        return {"enabled": False, "violations": [], "would_block": False}
    violations: list[dict[str, str]] = []
    claimed = str(proposal["soundness"])
    if claimed != "env_sound_dead" or verified_soundness != "env_sound_dead":
        violations.append(
            {
                "article": "EPISTEMIC_PROVENANCE",
                "reason": "non-environment-sound elimination would be soft-stored",
            }
        )
    if any(len(values) == 0 for values in after.values()):
        violations.append(
            {
                "article": "EXPLICIT_BOTTOM",
                "reason": "proposal reaches bottom under audit-only application",
            }
        )
    if final_claim and final_claim["mode"] == "single":
        if float(final_claim["posterior"]) < 0.9:
            violations.append(
                {
                    "article": "CALIBRATED_CLAIM",
                    "reason": "single explanation below frozen posterior threshold",
                }
            )
        name = str(final_claim["models"][0])
        descriptor = {
            "spectral_gap": "spectral_gap",
            "clustering": "average_clustering",
            "path_length": "average_shortest_path",
        }.get(name)
        if descriptor is not None:
            balanced = sum(
                row["target_descriptor"] == descriptor
                and bool(row["balanced_for_single_descriptor_claim"])
                for row in queried
            )
            if balanced < 2:
                violations.append(
                    {
                        "article": "MATCHED_EXPOSURE",
                        "reason": "single explanation lacks two balanced target queries",
                    }
                )
    return {
        "enabled": True,
        "enforcement": "audit_only",
        "violations": violations,
        "would_block": bool(violations),
        "normative_provenance": "authorized_article_v1",
        "before_bottom": any(len(values) == 0 for values in before.values()),
        "after_bottom": any(len(values) == 0 for values in after.values()),
    }


def lattice_step(
    before: Mapping[str, Sequence[str]],
    proposed: Mapping[str, Sequence[str]],
    *,
    conflict_score: float,
    final_claim: Mapping[str, Any] | None = None,
    queried: Sequence[Mapping[str, Any]] = (),
    claimed_soundness: str = "model_sound_dead",
    verified_soundness: str = "model_sound_dead",
    audit_enabled: bool = True,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    keys = set(before) | set(proposed)
    if keys != set(before) or keys != set(proposed):
        raise KeyError("CandidateState key mismatch")
    after = {
        key: sorted(set(before[key]) & set(proposed[key])) for key in sorted(keys)
    }
    proposal = {
        "proposed_state": {key: sorted(proposed[key]) for key in sorted(proposed)},
        "soundness": claimed_soundness,
        "mode": "deduce",
        "conflict_score": float(conflict_score),
        "soft_store": True,
        "metadata": {
            "epistemic_provenance": claimed_soundness,
            "normative_provenance": "authorized_article_v1",
            "audit_enforcement": "disabled_for_selection",
        },
    }
    audit = audit_lattice_step(
        before=before,
        after=after,
        proposal=proposal,
        final_claim=final_claim,
        queried=queried,
        verified_soundness=verified_soundness,
        audit_enabled=audit_enabled,
    )
    receipt = {
        "accepted": True,
        "before": {key: sorted(before[key]) for key in sorted(before)},
        "after": after,
        "proposal": proposal,
        "reason": "audit_only_applied_monotone_meet",
        "soft_store": proposal if audit.get("would_block") else None,
        "claimed_soundness": claimed_soundness,
        "verified_soundness": verified_soundness,
        "provenance_disagreed": claimed_soundness != verified_soundness,
        "audit": audit,
    }
    return after, receipt


class SealedTaskEnvironment:
    """Expose structural candidates and reveal outcomes only through query()."""

    def __init__(self, task: Mapping[str, Any]) -> None:
        self.public = {
            candidate["pair_id"]: candidate_public(candidate)
            for candidate in task["candidates"]
        }
        self.__outcomes = {
            candidate["pair_id"]: float(candidate["y"])
            for candidate in task["candidates"]
        }

    def candidates(self) -> list[dict[str, Any]]:
        return [dict(self.public[key]) for key in sorted(self.public)]

    def query(self, pair_id: str) -> float:
        if pair_id not in self.public:
            raise KeyError(pair_id)
        return self.__outcomes[pair_id]


def select_action(
    policy: str,
    investigator: BayesianInvestigator,
    remaining: Sequence[Mapping[str, Any]],
    *,
    random_order: Sequence[str] | None = None,
) -> tuple[str, float | None]:
    if policy.startswith("random_"):
        if random_order is None:
            raise ValueError("random policy requires a frozen random order")
        remaining_ids = {str(row["pair_id"]) for row in remaining}
        winner = next(pair_id for pair_id in random_order if pair_id in remaining_ids)
        return winner, None
    if policy == "spectral_proxy":
        winner = min(
            remaining,
            key=lambda row: (-abs(float(row["x"][0])), str(row["pair_id"])),
        )
        return str(winner["pair_id"]), abs(float(winner["x"][0]))
    scored = [
        (
            investigator.expected_information_gain(row["x"]),
            str(row["pair_id"]),
        )
        for row in remaining
    ]
    score, winner = min(scored, key=lambda row: (-row[0], row[1]))
    return winner, float(score)


def evaluate_policy(
    task: Mapping[str, Any],
    policy: str,
    prior: Sequence[float],
    *,
    noise_std: float,
    tau2: float,
    query_budget: int,
    audit_enabled: bool = True,
) -> dict[str, Any]:
    environment = SealedTaskEnvironment(task)
    investigator = BayesianInvestigator(prior, noise_std=noise_std, tau2=tau2)
    public_candidates = environment.candidates()
    by_id = {row["pair_id"]: row for row in public_candidates}
    random_order: list[str] | None = None
    if policy.startswith("random_"):
        random_index = int(policy.rsplit("_", 1)[1])
        random_order = sorted(by_id)
        rng = np.random.default_rng(
            stable_int(task["task_id"], "random_policy", random_index)
        )
        rng.shuffle(random_order)
    queried_ids: list[str] = []
    query_trace: list[dict[str, Any]] = []
    lattice: dict[str, list[str]] = {
        "explanation": list(MODEL_NAMES),
        "claim_mode": ["abstain", "set", "single"],
    }
    lattice_trace: list[dict[str, Any]] = []
    for step in range(query_budget):
        remaining = [
            row for row in public_candidates if row["pair_id"] not in queried_ids
        ]
        pair_id, selection_score = select_action(
            policy,
            investigator,
            remaining,
            random_order=random_order,
        )
        candidate = by_id[pair_id]
        outcome = environment.query(pair_id)
        before_probabilities = investigator.probabilities.tolist()
        investigator.update(candidate["x"], outcome)
        queried_ids.append(pair_id)
        query_trace.append(
            {
                "step": step + 1,
                "pair_id": pair_id,
                "selection_metric": (
                    "expected_model_information_gain"
                    if policy in EIG_POLICIES
                    else "absolute_spectral_gap_separation"
                    if policy == "spectral_proxy"
                    else "frozen_random_order"
                ),
                "selection_score": selection_score,
                "observed_y": outcome,
                "probabilities_before": before_probabilities,
                "probabilities_after": investigator.probabilities.tolist(),
            }
        )
        if step + 1 >= 3:
            probabilities = investigator.probabilities
            maximum = float(np.max(probabilities))
            surviving = [
                name
                for name, probability in zip(MODEL_NAMES, probabilities)
                if float(probability) >= maximum * 0.01
            ]
            proposed = {
                "explanation": surviving,
                "claim_mode": list(lattice["claim_mode"]),
            }
            lattice, receipt = lattice_step(
                lattice,
                proposed,
                conflict_score=1.0 - maximum,
                queried=[by_id[value] for value in queried_ids],
                audit_enabled=audit_enabled,
            )
            lattice_trace.append(receipt)
    probabilities = investigator.probabilities
    maximum_index = int(np.argmax(probabilities))
    final_set = credible_set(probabilities)
    if float(probabilities[maximum_index]) >= 0.9:
        claim = {
            "mode": "single",
            "models": [MODEL_NAMES[maximum_index]],
            "posterior": float(probabilities[maximum_index]),
        }
    elif len(final_set) < len(MODEL_NAMES):
        claim = {
            "mode": "set",
            "models": final_set,
            "posterior": float(sum(probabilities[MODEL_NAMES.index(v)] for v in final_set)),
        }
    else:
        claim = {
            "mode": "abstain",
            "models": [],
            "posterior": float(probabilities[maximum_index]),
        }
    proposed_final = {
        "explanation": claim["models"] or list(lattice["explanation"]),
        "claim_mode": [claim["mode"]],
    }
    lattice, final_receipt = lattice_step(
        lattice,
        proposed_final,
        conflict_score=1.0 - float(probabilities[maximum_index]),
        final_claim=claim,
        queried=[by_id[value] for value in queried_ids],
        audit_enabled=audit_enabled,
    )
    lattice_trace.append(final_receipt)
    unqueried = [
        candidate
        for candidate in task["candidates"]
        if candidate["pair_id"] not in queried_ids
    ]
    squared_errors = [
        (
            investigator.mixture_mean(candidate["x"]) - float(candidate["y"])
        )
        ** 2
        for candidate in unqueried
    ]
    return {
        "policy": policy,
        "query_budget": int(query_budget),
        "queried_pair_ids": queried_ids,
        "query_trace": query_trace,
        "final_belief": investigator.jsonable(),
        "final_claim": claim,
        "public_lattice": lattice,
        "lattice_trace": lattice_trace,
        "unqueried_pair_count": len(unqueried),
        "unqueried_rmse": math.sqrt(statistics.mean(squared_errors)),
        "audit_would_block_count": sum(
            bool(row["audit"].get("would_block")) for row in lattice_trace
        ),
        "audit_violation_count": sum(
            len(row["audit"].get("violations", [])) for row in lattice_trace
        ),
    }


def full_bank_oracle(
    task: Mapping[str, Any],
    *,
    noise_std: float,
    tau2: float,
) -> dict[str, Any]:
    investigator = BayesianInvestigator(
        [1.0 / len(MODEL_NAMES)] * len(MODEL_NAMES),
        noise_std=noise_std,
        tau2=tau2,
    )
    for candidate in sorted(task["candidates"], key=lambda row: row["pair_id"]):
        investigator.update(candidate["x"], candidate["y"])
    probabilities = investigator.probabilities
    return {
        "scope": "finite_full_bank_model_posterior_not_ground_truth",
        "model_order": list(MODEL_NAMES),
        "probabilities": probabilities.tolist(),
        "credible_set_90": credible_set(probabilities),
        "top_model": MODEL_NAMES[int(np.argmax(probabilities))],
        "top_probability": float(np.max(probabilities)),
    }


def score_against_oracle(
    result: dict[str, Any], oracle: Mapping[str, Any]
) -> None:
    predicted = np.asarray(
        result["final_belief"]["model_probabilities"], dtype=float
    )
    target = np.asarray(oracle["probabilities"], dtype=float)
    result["oracle_kl"] = float(
        np.sum(target * np.log(np.maximum(target, 1e-15) / np.maximum(predicted, 1e-15)))
    )
    predicted_set = set(credible_set(predicted))
    oracle_set = set(oracle["credible_set_90"])
    result["credible_set_jaccard"] = len(predicted_set & oracle_set) / max(
        1, len(predicted_set | oracle_set)
    )
    result["posterior_brier"] = float(np.sum((predicted - target) ** 2))
    claim = result["final_claim"]
    result["false_single_explanation"] = bool(
        claim["mode"] == "single"
        and (
            claim["models"][0] != oracle["top_model"]
            or float(oracle["top_probability"]) < 0.9
        )
    )


def discovery_noise_std(
    banks: Sequence[Mapping[str, Any]],
    minimum: float,
    maximum: float,
) -> float:
    x = np.asarray(
        [candidate["x"] for bank in banks for candidate in bank["candidates"]],
        dtype=float,
    )
    y = np.asarray(
        [candidate["y"] for bank in banks for candidate in bank["candidates"]],
        dtype=float,
    )
    penalty = np.eye(x.shape[1]) * 1e-3
    beta = np.linalg.solve(x.T @ x + penalty, x.T @ y)
    residual = y - x @ beta
    estimate = float(np.sqrt(np.mean(residual**2)))
    return max(float(minimum), min(float(maximum), estimate))


def mean_priors(
    banks: Sequence[Mapping[str, Any]],
    patches: Sequence[Mapping[str, Any]],
    noise_std: float,
    tau2: float,
) -> tuple[dict[str, list[float]], list[float]]:
    by_patch: dict[str, list[np.ndarray]] = {patch["id"]: [] for patch in patches}
    all_rows: list[np.ndarray] = []
    for bank in banks:
        posterior = np.asarray(
            full_bank_oracle(bank, noise_std=noise_std, tau2=tau2)[
                "probabilities"
            ],
            dtype=float,
        )
        by_patch[bank["patch"]["id"]].append(posterior)
        all_rows.append(posterior)
    uniform = np.ones(len(MODEL_NAMES), dtype=float) / len(MODEL_NAMES)
    local = {
        patch_id: (
            np.mean(rows, axis=0) if rows else uniform
        ).tolist()
        for patch_id, rows in by_patch.items()
    }
    global_prior = np.mean(all_rows, axis=0).tolist() if all_rows else uniform.tolist()
    return local, global_prior


def select_sheaf_regularization(
    banks: Sequence[Mapping[str, Any]],
    patches: Sequence[Mapping[str, Any]],
    candidates: Sequence[float],
    *,
    noise_std: float,
    tau2: float,
    query_budget: int,
) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for regularization in candidates:
        losses: list[float] = []
        for heldout in banks:
            training = [
                bank for bank in banks if bank["task_id"] != heldout["task_id"]
            ]
            local, _ = mean_priors(training, patches, noise_std, tau2)
            smoothed, _ = smooth_patch_priors(
                patches, local, float(regularization)
            )
            result = evaluate_policy(
                heldout,
                "sheaf_eig",
                smoothed[heldout["patch"]["id"]],
                noise_std=noise_std,
                tau2=tau2,
                query_budget=query_budget,
                audit_enabled=False,
            )
            losses.append(float(result["unqueried_rmse"]))
        rows.append(
            {
                "regularization": float(regularization),
                "leave_one_task_out_mean_unqueried_rmse": float(
                    statistics.mean(losses)
                ),
                "tasks": len(losses),
            }
        )
    winner = min(
        rows,
        key=lambda row: (
            row["leave_one_task_out_mean_unqueried_rmse"],
            row["regularization"],
        ),
    )
    return float(winner["regularization"]), rows


def fit_policy_freeze(
    discovery_banks: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    design = manifest["design"]
    patches = list(design["patches"])
    bayes = design["bayesian_models"]
    noise_std = discovery_noise_std(
        discovery_banks,
        float(bayes["noise_std_bounds"][0]),
        float(bayes["noise_std_bounds"][1]),
    )
    tau2 = float(bayes["coefficient_prior_variance"])
    local, global_prior = mean_priors(
        discovery_banks, patches, noise_std, tau2
    )
    regularization, cv = select_sheaf_regularization(
        discovery_banks,
        patches,
        [float(value) for value in design["sheaf_regularization_candidates"]],
        noise_std=noise_std,
        tau2=tau2,
        query_budget=int(design["query_budget"]),
    )
    sheaf, sheaf_receipt = smooth_patch_priors(
        patches, local, regularization
    )
    policy = {
        "schema": POLICY_SCHEMA,
        "model_order": list(MODEL_NAMES),
        "model_features": {
            name: [DESCRIPTORS[index] for index in indices]
            for name, indices in MODELS.items()
        },
        "noise_std": noise_std,
        "coefficient_prior_variance": tau2,
        "local_patch_priors": local,
        "global_prior": global_prior,
        "sheaf_patch_priors": sheaf,
        "sheaf": sheaf_receipt,
        "regularization_selection": cv,
        "query_budget": int(design["query_budget"]),
        "single_claim_posterior_min": 0.9,
        "lattice_elimination_relative_probability_min": 0.01,
        "discovery_task_hashes": {
            bank["task_id"]: bank["task_bank_sha256"]
            for bank in discovery_banks
        },
        "freeze_boundary": (
            "All fields are fit from discovery banks only. Confirmation and "
            "holdout outcomes are not available at this point."
        ),
    }
    policy["policy_sha256"] = canonical_sha256(policy)
    return policy


def policy_prior(
    policy: str,
    patch_id: str,
    freeze: Mapping[str, Any],
) -> Sequence[float]:
    if policy == "sheaf_eig":
        return freeze["sheaf_patch_priors"][patch_id]
    if policy == "local_eig":
        return freeze["local_patch_priors"][patch_id]
    if policy == "global_eig":
        return freeze["global_prior"]
    return [1.0 / len(MODEL_NAMES)] * len(MODEL_NAMES)


def evaluate_task(
    task: dict[str, Any],
    freeze: Mapping[str, Any],
    *,
    audit_enabled: bool = True,
) -> dict[str, Any]:
    policies = [
        "sheaf_eig",
        "local_eig",
        "global_eig",
        "spectral_proxy",
        *[f"random_{index}" for index in range(RANDOM_REPLICATES)],
    ]
    results: dict[str, Any] = {}
    for policy in policies:
        result = evaluate_policy(
            task,
            policy,
            policy_prior(policy, task["patch"]["id"], freeze),
            noise_std=float(freeze["noise_std"]),
            tau2=float(freeze["coefficient_prior_variance"]),
            query_budget=int(freeze["query_budget"]),
            audit_enabled=audit_enabled,
        )
        results[policy] = result
    oracle = full_bank_oracle(
        task,
        noise_std=float(freeze["noise_std"]),
        tau2=float(freeze["coefficient_prior_variance"]),
    )
    for result in results.values():
        score_against_oracle(result, oracle)
    task["policy_freeze_sha256"] = freeze["policy_sha256"]
    task["oracle"] = oracle
    task["policy_results"] = results
    return task


def random_mean(task: Mapping[str, Any], metric: str) -> float:
    return float(
        statistics.mean(
            float(task["policy_results"][f"random_{index}"][metric])
            for index in range(RANDOM_REPLICATES)
        )
    )


def seed_block_effects(
    tasks: Sequence[Mapping[str, Any]],
    *,
    treatment: str,
    comparator: str,
) -> list[dict[str, Any]]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for task in tasks:
        grouped.setdefault(int(task["seed"]), []).append(task)
    rows: list[dict[str, Any]] = []
    for seed, group in sorted(grouped.items()):
        treatment_rmse = statistics.mean(
            float(task["policy_results"][treatment]["unqueried_rmse"])
            for task in group
        )
        comparator_rmse = statistics.mean(
            random_mean(task, "unqueried_rmse")
            if comparator == "random_mean"
            else float(task["policy_results"][comparator]["unqueried_rmse"])
            for task in group
        )
        rows.append(
            {
                "seed": seed,
                "patches": len(group),
                "treatment_rmse": float(treatment_rmse),
                "comparator_rmse": float(comparator_rmse),
                "relative_improvement": (
                    float(comparator_rmse) - float(treatment_rmse)
                )
                / max(float(comparator_rmse), 1e-12),
            }
        )
    return rows


def bootstrap_seed_block_mean(
    values: Sequence[float],
    *,
    seed: int,
    replicates: int = 10_000,
) -> list[float]:
    if not values:
        return [float("nan"), float("nan")]
    if len(values) == 1:
        return [float(values[0]), float(values[0])]
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    estimates = np.mean(
        rng.choice(array, size=(replicates, len(array)), replace=True),
        axis=1,
    )
    return [
        float(np.quantile(estimates, 0.025)),
        float(np.quantile(estimates, 0.975)),
    ]


def summarize_policy(
    tasks: Sequence[Mapping[str, Any]], policy: str
) -> dict[str, Any]:
    metrics = (
        "unqueried_rmse",
        "oracle_kl",
        "credible_set_jaccard",
        "posterior_brier",
        "audit_would_block_count",
        "audit_violation_count",
    )
    if policy == "random_mean":
        return {
            metric: float(
                statistics.mean(random_mean(task, metric) for task in tasks)
            )
            for metric in metrics
        }
    return {
        **{
            metric: float(
                statistics.mean(
                    float(task["policy_results"][policy][metric])
                    for task in tasks
                )
            )
            for metric in metrics
        },
        "false_single_explanation_rate": float(
            statistics.mean(
                bool(
                    task["policy_results"][policy][
                        "false_single_explanation"
                    ]
                )
                for task in tasks
            )
        ),
        "single_claim_rate": float(
            statistics.mean(
                task["policy_results"][policy]["final_claim"]["mode"] == "single"
                for task in tasks
            )
        ),
    }


def split_summary(
    tasks: Sequence[Mapping[str, Any]],
    split: str,
) -> dict[str, Any]:
    selected = [task for task in tasks if task["split"] == split]
    policies = [
        "sheaf_eig",
        "local_eig",
        "global_eig",
        "spectral_proxy",
        "random_mean",
    ]
    primary_blocks = seed_block_effects(
        selected, treatment="sheaf_eig", comparator="random_mean"
    )
    topology_blocks = seed_block_effects(
        selected, treatment="sheaf_eig", comparator="local_eig"
    )
    primary_values = [row["relative_improvement"] for row in primary_blocks]
    topology_values = [row["relative_improvement"] for row in topology_blocks]
    return {
        "tasks": len(selected),
        "seed_blocks": len(primary_blocks),
        "patch_counts": {
            patch_id: sum(task["patch"]["id"] == patch_id for task in selected)
            for patch_id in sorted({task["patch"]["id"] for task in selected})
        },
        "policy_metrics": {
            policy: summarize_policy(selected, policy) for policy in policies
        },
        "sheaf_vs_random": {
            "seed_blocks": primary_blocks,
            "mean_relative_unqueried_rmse_improvement": float(
                statistics.mean(primary_values)
            ),
            "bootstrap_95": bootstrap_seed_block_mean(
                primary_values, seed=stable_int(split, "primary_bootstrap")
            ),
            "direction_fraction": float(
                statistics.mean(value > 0.0 for value in primary_values)
            ),
        },
        "sheaf_vs_local": {
            "seed_blocks": topology_blocks,
            "mean_relative_unqueried_rmse_improvement": float(
                statistics.mean(topology_values)
            ),
            "bootstrap_95": bootstrap_seed_block_mean(
                topology_values, seed=stable_int(split, "topology_bootstrap")
            ),
            "direction_fraction": float(
                statistics.mean(value > 0.0 for value in topology_values)
            ),
        },
    }


def run_audit_fixtures() -> dict[str, Any]:
    base = {
        "explanation": list(MODEL_NAMES),
        "claim_mode": ["abstain", "set", "single"],
    }
    fixtures: list[dict[str, Any]] = []

    def append_fixture(
        fixture_id: str,
        proposed: Mapping[str, Sequence[str]],
        expected_article: str,
        **kwargs: Any,
    ) -> None:
        _, receipt = lattice_step(
            base,
            proposed,
            conflict_score=float(kwargs.pop("conflict_score", 1.0)),
            audit_enabled=True,
            **kwargs,
        )
        articles = {
            row["article"] for row in receipt["audit"]["violations"]
        }
        fixtures.append(
            {
                "fixture_id": fixture_id,
                "expected_article": expected_article,
                "observed_articles": sorted(articles),
                "passed": expected_article in articles
                and bool(receipt["audit"]["would_block"]),
            }
        )

    append_fixture(
        "model_claimed_environment_sound",
        {"explanation": ["spectral_gap"], "claim_mode": base["claim_mode"]},
        "EPISTEMIC_PROVENANCE",
        claimed_soundness="env_sound_dead",
        verified_soundness="model_sound_dead",
    )
    append_fixture(
        "low_confidence_single_claim",
        {"explanation": ["spectral_gap"], "claim_mode": ["single"]},
        "CALIBRATED_CLAIM",
        final_claim={
            "mode": "single",
            "models": ["spectral_gap"],
            "posterior": 0.6,
        },
    )
    append_fixture(
        "unbalanced_single_claim",
        {"explanation": ["spectral_gap"], "claim_mode": ["single"]},
        "MATCHED_EXPOSURE",
        final_claim={
            "mode": "single",
            "models": ["spectral_gap"],
            "posterior": 0.95,
        },
        queried=[],
    )
    append_fixture(
        "hidden_bottom_bypass",
        {"explanation": [], "claim_mode": ["single"]},
        "EXPLICIT_BOTTOM",
    )
    return {
        "fixtures": fixtures,
        "passed": all(row["passed"] for row in fixtures),
        "passed_count": sum(row["passed"] for row in fixtures),
        "fixture_count": len(fixtures),
    }


def summarize_campaign(
    tasks: Sequence[Mapping[str, Any]],
    graph_arm_count: int,
    freeze: Mapping[str, Any],
    manifest: Mapping[str, Any],
    audit_fixtures: Mapping[str, Any],
) -> dict[str, Any]:
    splits = {split: split_summary(tasks, split) for split in SPLITS}
    primary_threshold = float(
        manifest["analysis"]["minimum_relative_rmse_improvement"]
    )
    topology_threshold = float(
        manifest["analysis"]["minimum_sheaf_incremental_improvement"]
    )
    primary_pass = all(
        splits[split]["sheaf_vs_random"][
            "mean_relative_unqueried_rmse_improvement"
        ]
        >= primary_threshold
        and splits[split]["sheaf_vs_random"]["bootstrap_95"][0] > 0.0
        for split in ("confirmatory", "holdout")
    )
    topology_pass = primary_pass and all(
        splits[split]["sheaf_vs_local"][
            "mean_relative_unqueried_rmse_improvement"
        ]
        >= topology_threshold
        and splits[split]["sheaf_vs_local"]["bootstrap_95"][0] > 0.0
        for split in ("confirmatory", "holdout")
    )
    holdout_sheaf = splits["holdout"]["policy_metrics"]["sheaf_eig"]
    calibrated_pass = (
        holdout_sheaf["credible_set_jaccard"] >= 0.8
        and holdout_sheaf["false_single_explanation_rate"] <= 0.05
    )
    exposure_failures = sum(
        candidate["exposure"]["executed_perturbations"] != 2
        for task in tasks
        for candidate in task["candidates"]
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "claim_scope": "model_only",
        "status": "ok",
        "task_count": len(tasks),
        "graph_arm_count": int(graph_arm_count),
        "pair_observation_count": sum(len(task["candidates"]) for task in tasks),
        "policy_freeze_sha256": freeze["policy_sha256"],
        "selected_sheaf_regularization": freeze["sheaf"]["regularization"],
        "noise_std": freeze["noise_std"],
        "exposure_audit": {
            "eligible_pair_count": sum(
                len(task["candidates"]) for task in tasks
            ),
            "failed_pair_count": exposure_failures,
            "passed": exposure_failures == 0,
        },
        "metric_firewall": {
            "selection": list(manifest["metrics"]["selection"]),
            "evidence": list(manifest["metrics"]["evidence"]),
            "overlap": sorted(
                set(manifest["metrics"]["selection"])
                & set(manifest["metrics"]["evidence"])
            ),
            "passed": not (
                set(manifest["metrics"]["selection"])
                & set(manifest["metrics"]["evidence"])
            ),
        },
        "audit_fixtures": audit_fixtures,
        "splits": splits,
        "hypothesis_assessment": {
            "H1_active_investigation": {
                "status": "supported" if primary_pass else "not_supported",
                "minimum_relative_improvement": primary_threshold,
            },
            "H2_patchwise_topology": {
                "status": "supported" if topology_pass else "not_supported",
                "gatekept_by_H1": True,
                "minimum_incremental_improvement": topology_threshold,
            },
            "H3_calibrated_claiming": {
                "status": "supported" if calibrated_pass else "not_supported",
                "minimum_credible_set_jaccard": 0.8,
                "maximum_false_single_explanation_rate": 0.05,
            },
            "H4_shadow_constitution": {
                "status": "instrument_pass"
                if audit_fixtures["passed"]
                else "instrument_failure",
                "enforcement": "audit_only",
            },
        },
        "claim_boundary": (
            "The full-bank oracle is a finite Bayesian grading target, not causal "
            "ground truth. Matched graph interventions test local structural "
            "explanations within this simulator only."
        ),
    }


def build_knowledge_card(
    summary: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> str:
    confirmation = summary["splits"]["confirmatory"]
    holdout = summary["splits"]["holdout"]
    hypotheses = summary["hypothesis_assessment"]
    return f"""# Graph-State Investigator Cultivation v1 — Knowledge Card

## Observed

- Retained {summary['task_count']} sealed task banks and {summary['graph_arm_count']} graph-arm simulations.
- Discovery selected sheaf regularization {summary['selected_sheaf_regularization']}; the frozen policy hash is `{summary['policy_freeze_sha256']}`.
- Confirmatory sheaf-vs-random unqueried-RMSE improvement was {confirmation['sheaf_vs_random']['mean_relative_unqueried_rmse_improvement']:.3%}, interval {confirmation['sheaf_vs_random']['bootstrap_95']}.
- Holdout sheaf-vs-random unqueried-RMSE improvement was {holdout['sheaf_vs_random']['mean_relative_unqueried_rmse_improvement']:.3%}, interval {holdout['sheaf_vs_random']['bootstrap_95']}.
- Holdout sheaf-vs-local improvement was {holdout['sheaf_vs_local']['mean_relative_unqueried_rmse_improvement']:.3%}, interval {holdout['sheaf_vs_local']['bootstrap_95']}.
- Exposure, metric-firewall, and audit-fixture checks passed: {summary['exposure_audit']['passed']}, {summary['metric_firewall']['passed']}, {summary['audit_fixtures']['passed']}.

## Hypothesis assessment

- H1 active investigation: **{hypotheses['H1_active_investigation']['status']}**.
- H2 patchwise topology: **{hypotheses['H2_patchwise_topology']['status']}**.
- H3 calibrated claiming: **{hypotheses['H3_calibrated_claiming']['status']}**.
- H4 shadow constitution: **{hypotheses['H4_shadow_constitution']['status']}**.

## Inferred

The campaign measures whether a recurrent Bayesian selector can spend a fixed six-query budget more effectively than query-matched controls when approximating a sealed finite graph-experiment bank. Any supported patchwise result concerns the registered constant-stalk context sheaf only.

## Not supported

- The full-bank posterior is not causal ground truth, biological evidence, cognition, or general scientific understanding.
- Spectral gap, clustering, and path length remain correlated summaries of graph interventions.
- Identity restrictions make holonomy trivial; no learned RSITopology transport claim is tested.
- The audit-only constitution does not establish that a hard membrane improves safety or utility.
- Query budgets are matched; FLOPs are not.

## Robustness and confounds

Confirmation and holdout use fresh seed blocks. Holdout changes graph size, horizon, state dimension, perturbation channel, and magnitude. Policies share one sealed bank within each task, so policies are paired views rather than independent experimental units. The four graph patches are fixed strata; uncertainty resamples the seed blocks.

## Artifacts

Receipt schema: `{receipt['schema']}`. Raw task and graph-arm rows, frozen policy, summary, seed manifest, hashes, and exact replay command are retained under the output directory.

## Next experiment

Compare this audit-only investigator with an enforcing Hybrid-compatible membrane on the same sealed banks. Keep the query policy frozen and measure false eliminations, abstention, and unqueried predictive loss rather than presuming enforcement helps.
"""


def version_control_receipt(repo: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(
                ["git", "-C", str(repo), *args],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    return {
        "commit": run("rev-parse", "HEAD") or None,
        "branch": run("branch", "--show-current") or None,
        "dirty": bool(run("status", "--short")),
    }


def copy_compact_evidence(output: Path, evidence_dir: Path) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "summary.json",
        "policy_freeze.json",
        "seed_manifest.json",
        "receipt.json",
        "hashes.json",
        "knowledge_card.md",
        "frozen_manifest.json",
        "audit_fixtures.json",
    ):
        shutil.copy2(output / name, evidence_dir / name)


def run_campaign(
    manifest_path: Path,
    output: Path,
    *,
    smoke: bool,
    evidence_dir: Path | None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    started_utc = utc_now()
    budget = manifest["budget"]
    deadline = started + float(budget["max_wall_seconds"])
    max_ram_mb = float(budget["max_ram_mb"])
    design = manifest["design"]
    patches = list(design["patches"])
    seeds_by_split = {
        split: [int(value) for value in manifest["seed_plan"][split]]
        for split in SPLITS
    }
    if smoke:
        patches = patches[:2]
        seeds_by_split = {
            split: values[:1] for split, values in seeds_by_split.items()
        }
    planned_tasks = sum(len(seeds_by_split[split]) * len(patches) for split in SPLITS)
    pairs_per_task = int(design["pairs_per_descriptor"]) * len(DESCRIPTORS)
    planned_graph_arms = planned_tasks * pairs_per_task * 2
    if planned_tasks > int(budget["max_episodes"]):
        raise RuntimeError("planned task count exceeds max_episodes")
    if planned_graph_arms > int(budget["max_graph_arms"]):
        raise RuntimeError("planned graph-arm count exceeds max_graph_arms")

    all_tasks: list[dict[str, Any]] = []
    graph_arm_count = 0
    max_rss = current_rss_mb()
    status = "ok"
    stop_reason = "completed_discovery_freeze_confirmation_holdout"
    raw_graph_path = output / "raw_graph_episodes.jsonl"
    raw_task_path = output / "raw_tasks.jsonl"
    try:
        with raw_graph_path.open("w", encoding="utf-8") as graph_handle:
            discovery_banks: list[dict[str, Any]] = []
            for seed in seeds_by_split["discovery"]:
                for patch in patches:
                    task, graph_rows = build_task_bank(
                        manifest,
                        "discovery",
                        seed,
                        patch,
                        deadline,
                        max_ram_mb,
                    )
                    discovery_banks.append(task)
                    for row in graph_rows:
                        graph_handle.write(json.dumps(row, sort_keys=True) + "\n")
                    graph_handle.flush()
                    graph_arm_count += len(graph_rows)
                    max_rss = max(
                        max_rss,
                        max(
                            float(row["provenance"]["max_rss_mb"])
                            for row in graph_rows
                        ),
                    )
                    print(f"bank={task['task_id']} arms={len(graph_rows)}")
            freeze = fit_policy_freeze(discovery_banks, manifest)
            write_json(output / "policy_freeze.json", freeze)
            # Serialize and reload at the boundary so later phases consume only
            # the hash-bound frozen representation.
            freeze = json.loads(
                (output / "policy_freeze.json").read_text(encoding="utf-8")
            )
            if canonical_sha256(
                {key: value for key, value in freeze.items() if key != "policy_sha256"}
            ) != freeze["policy_sha256"]:
                # policy_sha256 was calculated before adding itself.
                expected = dict(freeze)
                recorded = expected.pop("policy_sha256")
                if canonical_sha256(expected) != recorded:
                    raise RuntimeError("policy freeze hash mismatch")
            for task in discovery_banks:
                all_tasks.append(evaluate_task(task, freeze))

            for split in ("confirmatory", "holdout"):
                for seed in seeds_by_split[split]:
                    for patch in patches:
                        task, graph_rows = build_task_bank(
                            manifest,
                            split,
                            seed,
                            patch,
                            deadline,
                            max_ram_mb,
                        )
                        for row in graph_rows:
                            graph_handle.write(
                                json.dumps(row, sort_keys=True) + "\n"
                            )
                        graph_handle.flush()
                        graph_arm_count += len(graph_rows)
                        max_rss = max(
                            max_rss,
                            max(
                                float(row["provenance"]["max_rss_mb"])
                                for row in graph_rows
                            ),
                        )
                        all_tasks.append(evaluate_task(task, freeze))
                        print(f"bank={task['task_id']} arms={len(graph_rows)}")
        with raw_task_path.open("w", encoding="utf-8") as task_handle:
            for task in all_tasks:
                task_handle.write(json.dumps(task, sort_keys=True) + "\n")
    except (MemoryError, TimeoutError, RuntimeError, ValueError, nx.NetworkXException) as exc:
        status = "stopped"
        stop_reason = f"{type(exc).__name__}: {exc}"
        if "freeze" not in locals():
            freeze = {
                "schema": POLICY_SCHEMA,
                "policy_sha256": None,
                "status": "not_frozen",
            }

    audit_fixtures = run_audit_fixtures()
    write_json(output / "audit_fixtures.json", audit_fixtures)
    if all_tasks and freeze.get("policy_sha256"):
        summary = summarize_campaign(
            all_tasks,
            graph_arm_count,
            freeze,
            manifest,
            audit_fixtures,
        )
    else:
        summary = {
            "schema": SUMMARY_SCHEMA,
            "claim_scope": "model_only",
            "status": status,
            "task_count": len(all_tasks),
            "graph_arm_count": graph_arm_count,
        }
    summary["status"] = status
    summary["stop_reason"] = stop_reason
    write_json(output / "summary.json", summary)
    seed_manifest = {
        "schema": "alife.graph_investigator.seeds.v1",
        "seed_blocks": seeds_by_split,
        "patches": [patch["id"] for patch in patches],
        "experimental_units": {
            split: len(seeds_by_split[split]) * len(patches) for split in SPLITS
        },
        "pairing": manifest["seed_plan"]["pairing"],
    }
    write_json(output / "seed_manifest.json", seed_manifest)
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "stop_reason": stop_reason,
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "max_rss_mb": max_rss,
        "task_count": len(all_tasks),
        "graph_arm_count": graph_arm_count,
        "code_path": str(Path(__file__).resolve()),
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": sha256_file(manifest_path),
        "policy_freeze_sha256": freeze.get("policy_sha256"),
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "networkx": nx.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
        "version_control": version_control_receipt(manifest_path.parents[2]),
        "output_path": str(output.resolve()),
        "replay_command": (
            f"python src/graph_investigator_gym.py --manifest {manifest_path} "
            f"--output {output}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(
        build_knowledge_card(summary, receipt)
        if all_tasks and freeze.get("policy_sha256")
        else "# Graph Investigator Campaign Stopped Before Complete Evidence\n",
        encoding="utf-8",
    )
    hash_names = [
        "raw_graph_episodes.jsonl",
        "raw_tasks.jsonl",
        "summary.json",
        "policy_freeze.json",
        "seed_manifest.json",
        "receipt.json",
        "frozen_manifest.json",
        "audit_fixtures.json",
        "knowledge_card.md",
    ]
    hashes = {
        name: {
            "sha256": sha256_file(output / name),
            "bytes": (output / name).stat().st_size,
        }
        for name in hash_names
        if (output / name).is_file()
    }
    write_json(output / "hashes.json", hashes)
    disk_mb = sum(
        path.stat().st_size for path in output.iterdir() if path.is_file()
    ) / (1024 * 1024)
    if disk_mb > float(budget["max_disk_mb"]):
        raise RuntimeError(
            f"retained artifacts exceed disk budget: {disk_mb:.1f} MB"
        )
    if evidence_dir is not None and not smoke and status == "ok":
        copy_compact_evidence(output, evidence_dir)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--evidence-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output = (
        args.output or Path(manifest["artifacts"]["output_directory"])
    ).resolve()
    summary = run_campaign(
        manifest_path,
        output,
        smoke=args.smoke,
        evidence_dir=args.evidence_dir.resolve() if args.evidence_dir else None,
    )
    print(
        f"status={summary['status']} tasks={summary.get('task_count', 0)} "
        f"graph_arms={summary.get('graph_arm_count', 0)} output={output}"
    )
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
