#!/usr/bin/env python3
"""Bounded-degree vector-state graph cellular-automaton laboratory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx
import numpy as np
import psutil


EPISODE_SCHEMA = "alife.graph_state.episode.v1"
SUMMARY_SCHEMA = "alife.graph_state.summary.v1"
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


def current_rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def check_budget(deadline: float, max_ram_mb: float) -> None:
    if time.monotonic() > deadline:
        raise TimeoutError("declared wall-time budget exceeded")
    rss = current_rss_mb()
    if rss > max_ram_mb:
        raise MemoryError(f"declared RAM budget exceeded: {rss:.1f} MB > {max_ram_mb:.1f} MB")


def edge_digest(graph: nx.Graph) -> str:
    edges = sorted((min(int(a), int(b)), max(int(a), int(b))) for a, b in graph.edges())
    return sha256_bytes(json.dumps(edges, separators=(",", ":")).encode("ascii"))


def state_digest(state: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(state, dtype="<f8").tobytes())


def build_graph(topology: str, nodes: int, degree: int, seed: int, rewires: int) -> nx.Graph:
    if degree <= 0 or degree >= nodes or degree % 2:
        raise ValueError("degree must be positive, even, and smaller than node count")
    if topology == "ring_regular":
        graph = nx.watts_strogatz_graph(nodes, degree, 0.0, seed=seed)
    elif topology == "rewired_regular":
        graph = nx.watts_strogatz_graph(nodes, degree, 0.0, seed=seed)
        nx.double_edge_swap(
            graph,
            nswap=rewires,
            max_tries=max(rewires * 20, nodes * 20),
            seed=seed,
        )
        if not nx.is_connected(graph):
            raise RuntimeError("degree-preserving rewiring disconnected the graph")
    elif topology == "random_regular":
        graph = None
        for attempt in range(20):
            candidate = nx.random_regular_graph(degree, nodes, seed=seed + attempt)
            if nx.is_connected(candidate):
                graph = candidate
                break
        if graph is None:
            raise RuntimeError("could not construct a connected random regular graph")
    elif topology == "circulant_skip_regular":
        pair_count = degree // 2
        offsets = [1]
        for index in range(1, pair_count):
            candidate = max(2, round(index * nodes / (2 * pair_count + 1)))
            while candidate in offsets or candidate >= nodes / 2:
                candidate -= 1
            if candidate <= 1:
                raise RuntimeError("could not construct distinct circulant skip offsets")
            offsets.append(candidate)
        graph = nx.Graph()
        graph.add_nodes_from(range(nodes))
        for node in range(nodes):
            for offset in offsets:
                graph.add_edge(node, (node + offset) % nodes)
                graph.add_edge(node, (node - offset) % nodes)
    else:
        raise ValueError(f"unknown topology: {topology}")
    graph = nx.convert_node_labels_to_integers(graph, ordering="sorted")
    degrees = [value for _, value in graph.degree()]
    if min(degrees) != degree or max(degrees) != degree:
        raise RuntimeError("graph failed exact-degree invariant")
    return graph


def graph_receipt(graph: nx.Graph, degree: int) -> dict[str, Any]:
    nodes = graph.number_of_nodes()
    adjacency = nx.to_numpy_array(graph, nodelist=range(nodes), dtype=float)
    normalized_laplacian = np.eye(nodes) - adjacency / degree
    eigenvalues = np.linalg.eigvalsh(normalized_laplacian)
    return {
        "nodes": nodes,
        "edges": graph.number_of_edges(),
        "degree_min": min(value for _, value in graph.degree()),
        "degree_max": max(value for _, value in graph.degree()),
        "connected": nx.is_connected(graph),
        "edge_sha256": edge_digest(graph),
        "spectral_gap": float(eigenvalues[1]),
        "spectral_radius_normalized_laplacian": float(eigenvalues[-1]),
        "average_clustering": float(nx.average_clustering(graph)),
        "average_shortest_path": float(nx.average_shortest_path_length(graph)),
    }


def neighbor_table(graph: nx.Graph) -> np.ndarray:
    return np.asarray(
        [sorted(int(value) for value in graph.neighbors(node)) for node in range(graph.number_of_nodes())],
        dtype=np.int64,
    )


def channel_matrix(state_dimension: int) -> np.ndarray:
    identity = np.eye(state_dimension)
    forward = np.roll(identity, 1, axis=1)
    backward = np.roll(identity, -1, axis=1)
    matrix = 1.08 * identity + 0.24 * forward - 0.18 * backward
    spectral_radius = max(abs(np.linalg.eigvals(matrix)))
    return matrix / float(spectral_radius) * 1.12


def advance(
    state: np.ndarray,
    neighbors: np.ndarray,
    matrix: np.ndarray,
    coupling: float,
) -> np.ndarray:
    local_reaction = np.tanh(state @ matrix.T)
    neighbor_mean = np.mean(state[neighbors], axis=1)
    return np.tanh((1.0 - coupling) * local_reaction + coupling * neighbor_mean)


def dirichlet_energy(state: np.ndarray, neighbors: np.ndarray) -> float:
    differences = state[:, None, :] - state[neighbors]
    numerator = float(np.mean(differences * differences))
    denominator = float(np.mean(state * state))
    return numerator / max(denominator, 1e-12)


def effective_state_dimension(state: np.ndarray) -> float:
    centered = state - np.mean(state, axis=0, keepdims=True)
    covariance = centered.T @ centered / max(1, state.shape[0] - 1)
    eigenvalues = np.maximum(np.linalg.eigvalsh(covariance), 0.0)
    total = float(eigenvalues.sum())
    if total <= 1e-15:
        return 0.0
    probabilities = eigenvalues / total
    nonzero = probabilities[probabilities > 0]
    return float(math.exp(-float(np.sum(nonzero * np.log(nonzero)))))


def classify_regime(activity: float, synchronization_error: float, dirichlet: float) -> str:
    if activity < 1e-4:
        return "quiescent"
    if synchronization_error < 1e-4:
        return "synchronized"
    if dirichlet >= 0.75:
        return "high_gradient"
    return "coherent_active"


def mean_or_none(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return float(statistics.mean(materialized)) if materialized else None


def run_episode(
    *,
    split: str,
    seed: int,
    nodes: int,
    degree: int,
    topology: str,
    state_dimension: int,
    coupling: float,
    rewires: int,
    steps: int,
    burn_in: int,
    perturbation_magnitude: float,
    deadline: float,
    max_ram_mb: float,
) -> dict[str, Any]:
    started = time.monotonic()
    graph_seed = seed * 1009 + 17
    graph = build_graph(topology, nodes, degree, graph_seed, rewires)
    graph_info = graph_receipt(graph, degree)
    neighbors = neighbor_table(graph)
    matrix = channel_matrix(state_dimension)
    rng = np.random.default_rng(seed)
    state = rng.normal(0.0, 0.25, size=(nodes, state_dimension))
    state = np.clip(state, -1.0, 1.0)
    perturbed = state.copy()
    intervention_node = seed % nodes
    intervention_vector = np.zeros(state_dimension, dtype=float)
    intervention_vector[0] = perturbation_magnitude
    perturbed[intervention_node] = np.clip(
        perturbed[intervention_node] + intervention_vector, -1.0, 1.0
    )
    initial_difference = float(np.linalg.norm(perturbed - state))
    initial_hash = state_digest(state)
    trajectory: list[dict[str, Any]] = []
    recovery_half_life: int | None = None
    max_rss = current_rss_mb()

    for tick in range(1, steps + 1):
        check_budget(deadline, max_ram_mb)
        state = advance(state, neighbors, matrix, coupling)
        perturbed = advance(perturbed, neighbors, matrix, coupling)
        difference_norm = float(np.linalg.norm(perturbed - state))
        difference_ratio = difference_norm / max(initial_difference, 1e-12)
        if recovery_half_life is None and difference_ratio <= 0.5:
            recovery_half_life = tick
        node_mean = np.mean(state, axis=0, keepdims=True)
        synchronization_error = float(np.mean((state - node_mean) ** 2))
        activity = float(np.mean(state * state))
        gradient = dirichlet_energy(state, neighbors)
        trajectory.append(
            {
                "tick": tick,
                "activity": activity,
                "synchronization_error": synchronization_error,
                "dirichlet_energy": gradient,
                "effective_state_dimension": effective_state_dimension(state),
                "perturbation_norm": difference_norm,
                "perturbation_ratio": difference_ratio,
            }
        )
        max_rss = max(max_rss, current_rss_mb())

    post = trajectory[max(0, burn_in - 1) :]
    final = trajectory[-1]
    return {
        "schema": EPISODE_SCHEMA,
        "split": split,
        "seed": seed,
        "experimental_unit": "one independently seeded regular graph plus vector-state world",
        "condition": {
            "nodes": nodes,
            "degree": degree,
            "topology": topology,
            "state_dimension": state_dimension,
            "coupling": coupling,
            "steps": steps,
            "burn_in": burn_in,
            "rewires": rewires if topology == "rewired_regular" else 0,
            "update": "shared nonlinear channel reaction plus neighbor-mean coupling",
        },
        "graph": graph_info,
        "intervention": {
            "type": "single_node_channel_addition",
            "node": intervention_node,
            "channel": 0,
            "magnitude": perturbation_magnitude,
            "initial_difference_norm": initial_difference,
            "executed": initial_difference > 0,
        },
        "exposure": {
            "node_ticks": nodes * steps,
            "directed_edge_channel_reads": nodes * degree * state_dimension * steps,
            "update_executions": nodes * steps,
            "perturbation_executions": 1 if initial_difference > 0 else 0,
        },
        "outcomes": {
            "recovery_half_life": recovery_half_life,
            "recovery_censored": recovery_half_life is None,
            "final_perturbation_ratio": float(final["perturbation_ratio"]),
            "log_final_perturbation_ratio": math.log10(
                max(float(final["perturbation_ratio"]), 1e-12)
            ),
            "synchronization_error_post_burn": mean_or_none(
                float(row["synchronization_error"]) for row in post
            ),
            "dirichlet_energy_post_burn": mean_or_none(
                float(row["dirichlet_energy"]) for row in post
            ),
            "effective_state_dimension_post_burn": mean_or_none(
                float(row["effective_state_dimension"]) for row in post
            ),
            "activity_post_burn": mean_or_none(float(row["activity"]) for row in post),
            "regime": classify_regime(
                float(final["activity"]),
                float(final["synchronization_error"]),
                float(final["dirichlet_energy"]),
            ),
        },
        "trajectory": trajectory,
        "provenance": {
            "initial_state_sha256": initial_hash,
            "final_state_sha256": state_digest(state),
            "final_perturbed_state_sha256": state_digest(perturbed),
            "channel_matrix_sha256": sha256_bytes(
                np.ascontiguousarray(matrix, dtype="<f8").tobytes()
            ),
            "runtime_seconds": time.monotonic() - started,
            "max_rss_mb": max_rss,
            "rng": "network topology and initial state are deterministic functions of the episode seed",
        },
    }


def condition_specs(manifest: Mapping[str, Any], split: str, smoke: bool) -> list[dict[str, Any]]:
    design = manifest["design"]
    topologies = list(design["topologies"])
    dimensions = [int(value) for value in design["state_dimensions"]]
    couplings = [float(value) for value in design["couplings"]]
    degrees = [int(value) for value in design.get("degrees", [design["degree"]])]
    if smoke:
        topologies = topologies[:2]
        dimensions = dimensions[:1]
        couplings = couplings[:1]
        degrees = degrees[:1]
    return [
        {
            "nodes": int(design["nodes_by_split"][split]),
            "degree": degree,
            "topology": topology,
            "state_dimension": state_dimension,
            "coupling": coupling,
            "rewires": int(design["rewires_by_split"][split]),
        }
        for topology in topologies
        for degree in degrees
        for state_dimension in dimensions
        for coupling in couplings
    ]


def bootstrap_mean_interval(values: Sequence[float], seed: int = 260714) -> list[float | None]:
    if not values:
        return [None, None]
    if len(values) == 1:
        return [float(values[0]), float(values[0])]
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    estimates = np.mean(rng.choice(array, size=(2000, len(array)), replace=True), axis=1)
    return [float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))]


def design_matrix(rows: Sequence[Mapping[str, Any]], spectral: bool) -> np.ndarray:
    columns = [
        np.ones(len(rows)),
        np.asarray([float(row["condition"]["coupling"]) for row in rows]),
        np.asarray([math.log2(float(row["condition"]["state_dimension"])) for row in rows]),
    ]
    if spectral:
        columns.append(np.asarray([float(row["graph"]["spectral_gap"]) for row in rows]))
    return np.column_stack(columns)


def predictive_comparison(
    rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    frozen = manifest["analysis"].get("frozen_predictor")
    if isinstance(frozen, dict):
        evaluation = [row for row in rows if row["split"] in {"confirmatory", "holdout"}]
        if not evaluation:
            return {
                "status": "not_evaluated",
                "reason": "frozen confirmation requires confirmatory or holdout rows",
                "target": "log10_final_perturbation_ratio",
                "train_rows": 0,
                "holdout_rows": 0,
                "baseline_holdout_rmse": None,
                "spectral_holdout_rmse": None,
                "relative_rmse_improvement": None,
            }
        target = np.asarray(
            [float(row["outcomes"]["log_final_perturbation_ratio"]) for row in evaluation]
        )
        baseline_coefficients = np.asarray(frozen["baseline_coefficients"], dtype=float)
        spectral_coefficients = np.asarray(frozen["spectral_coefficients"], dtype=float)
        baseline_prediction = design_matrix(evaluation, spectral=False) @ baseline_coefficients
        spectral_prediction = design_matrix(evaluation, spectral=True) @ spectral_coefficients
        baseline_rmse = float(np.sqrt(np.mean((baseline_prediction - target) ** 2)))
        spectral_rmse = float(np.sqrt(np.mean((spectral_prediction - target) ** 2)))
        improvement = (baseline_rmse - spectral_rmse) / max(baseline_rmse, 1e-12)
        return {
            "status": "evaluated",
            "mode": "frozen_external_confirmation",
            "source_summary_sha256": frozen["source_summary_sha256"],
            "target": "log10_final_perturbation_ratio",
            "train_rows": 0,
            "holdout_rows": len(evaluation),
            "baseline_features": ["intercept", "coupling", "log2_state_dimension"],
            "spectral_features": [
                "intercept",
                "coupling",
                "log2_state_dimension",
                "normalized_laplacian_spectral_gap",
            ],
            "baseline_coefficients": baseline_coefficients.tolist(),
            "spectral_coefficients": spectral_coefficients.tolist(),
            "baseline_holdout_rmse": baseline_rmse,
            "spectral_holdout_rmse": spectral_rmse,
            "relative_rmse_improvement": improvement,
        }
    train = [row for row in rows if row["split"] in {"discovery", "confirmatory"}]
    holdout = [row for row in rows if row["split"] == "holdout"]
    if not train or not holdout:
        return {
            "status": "not_evaluated",
            "reason": "predictive comparison requires training and holdout rows",
            "target": "log10_final_perturbation_ratio",
            "train_rows": len(train),
            "holdout_rows": len(holdout),
            "baseline_holdout_rmse": None,
            "spectral_holdout_rmse": None,
            "relative_rmse_improvement": None,
        }
    target_train = np.asarray(
        [float(row["outcomes"]["log_final_perturbation_ratio"]) for row in train]
    )
    target_holdout = np.asarray(
        [float(row["outcomes"]["log_final_perturbation_ratio"]) for row in holdout]
    )
    baseline_train = design_matrix(train, spectral=False)
    spectral_train = design_matrix(train, spectral=True)
    baseline_coefficients = np.linalg.lstsq(baseline_train, target_train, rcond=None)[0]
    spectral_coefficients = np.linalg.lstsq(spectral_train, target_train, rcond=None)[0]
    baseline_prediction = design_matrix(holdout, spectral=False) @ baseline_coefficients
    spectral_prediction = design_matrix(holdout, spectral=True) @ spectral_coefficients
    baseline_rmse = float(np.sqrt(np.mean((baseline_prediction - target_holdout) ** 2)))
    spectral_rmse = float(np.sqrt(np.mean((spectral_prediction - target_holdout) ** 2)))
    improvement = (baseline_rmse - spectral_rmse) / max(baseline_rmse, 1e-12)
    return {
        "status": "evaluated",
        "mode": "fit_train_evaluate_holdout",
        "target": "log10_final_perturbation_ratio",
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "baseline_features": ["intercept", "coupling", "log2_state_dimension"],
        "spectral_features": [
            "intercept",
            "coupling",
            "log2_state_dimension",
            "normalized_laplacian_spectral_gap",
        ],
        "baseline_coefficients": baseline_coefficients.tolist(),
        "spectral_coefficients": spectral_coefficients.tolist(),
        "baseline_holdout_rmse": baseline_rmse,
        "spectral_holdout_rmse": spectral_rmse,
        "relative_rmse_improvement": improvement,
    }


def summarize(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        condition = row["condition"]
        key = (
            row["split"],
            condition["nodes"],
            condition["topology"],
            condition["state_dimension"],
            condition["coupling"],
        )
        groups[key].append(row)
    group_summaries: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        split, nodes, topology, state_dimension, coupling = key
        ratios = [float(row["outcomes"]["final_perturbation_ratio"]) for row in group]
        gaps = [float(row["graph"]["spectral_gap"]) for row in group]
        half_lives = [
            int(row["outcomes"]["recovery_half_life"])
            for row in group
            if row["outcomes"]["recovery_half_life"] is not None
        ]
        regimes: dict[str, int] = defaultdict(int)
        for row in group:
            regimes[str(row["outcomes"]["regime"])] += 1
        group_summaries.append(
            {
                "split": split,
                "nodes": nodes,
                "topology": topology,
                "degree": int(group[0]["condition"]["degree"]),
                "state_dimension": state_dimension,
                "coupling": coupling,
                "episodes": len(group),
                "spectral_gap_mean": float(statistics.mean(gaps)),
                "final_perturbation_ratio_mean": float(statistics.mean(ratios)),
                "final_perturbation_ratio_bootstrap_95": bootstrap_mean_interval(ratios),
                "recovery_half_life_median": float(statistics.median(half_lives))
                if half_lives
                else None,
                "recovery_fraction": len(half_lives) / len(group),
                "synchronization_error_mean": float(
                    statistics.mean(
                        float(row["outcomes"]["synchronization_error_post_burn"])
                        for row in group
                    )
                ),
                "dirichlet_energy_mean": float(
                    statistics.mean(
                        float(row["outcomes"]["dirichlet_energy_post_burn"]) for row in group
                    )
                ),
                "effective_state_dimension_mean": float(
                    statistics.mean(
                        float(row["outcomes"]["effective_state_dimension_post_burn"])
                        for row in group
                    )
                ),
                "regime_counts": dict(sorted(regimes.items())),
            }
        )

    comparisons: list[dict[str, Any]] = []
    paired: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        condition = row["condition"]
        key = (
            row["split"],
            row["seed"],
            condition["nodes"],
            condition["state_dimension"],
            condition["coupling"],
        )
        paired[key][condition["topology"]] = row
    comparison_topologies = list(
        manifest["analysis"].get(
            "comparison_topologies", ["rewired_regular", "random_regular"]
        )
    )
    for target in comparison_topologies:
        deltas: list[float] = []
        gap_deltas: list[float] = []
        split_counts: dict[str, int] = defaultdict(int)
        for key, by_topology in paired.items():
            if "ring_regular" not in by_topology or target not in by_topology:
                continue
            ring = by_topology["ring_regular"]
            treated = by_topology[target]
            deltas.append(
                float(treated["outcomes"]["log_final_perturbation_ratio"])
                - float(ring["outcomes"]["log_final_perturbation_ratio"])
            )
            gap_deltas.append(
                float(treated["graph"]["spectral_gap"])
                - float(ring["graph"]["spectral_gap"])
            )
            split_counts[str(key[0])] += 1
        if not deltas:
            continue
        comparisons.append(
            {
                "target_topology": target,
                "paired_units": len(deltas),
                "split_counts": dict(split_counts),
                "mean_log10_recovery_ratio_delta_vs_ring": float(statistics.mean(deltas)),
                "bootstrap_95": bootstrap_mean_interval(deltas),
                "direction_fraction_faster": sum(value < 0 for value in deltas) / len(deltas),
                "mean_spectral_gap_delta_vs_ring": float(statistics.mean(gap_deltas)),
            }
        )

    predictive = predictive_comparison(rows, manifest)
    threshold = float(manifest["analysis"]["minimum_relative_rmse_improvement"])
    return {
        "schema": SUMMARY_SCHEMA,
        "row_count": len(rows),
        "condition_count": len(group_summaries),
        "episode_counts": {
            split: sum(1 for row in rows if row["split"] == split) for split in SPLITS
        },
        "condition_summaries": group_summaries,
        "paired_topology_comparisons": comparisons,
        "predictive_comparison": predictive,
        "hypothesis_assessment": {
            "H1_topology_recovery": {
                "status": "supported_within_model"
                if len(comparisons) == len(comparison_topologies) and all(
                    row["mean_spectral_gap_delta_vs_ring"] > 0
                    and row["mean_log10_recovery_ratio_delta_vs_ring"] < 0
                    and row["direction_fraction_faster"] >= 0.8
                    for row in comparisons
                )
                else "not_supported"
            },
            "H2_spectral_prediction": {
                "status": (
                    "confirmed_ontology_gain"
                    if predictive.get("mode") == "frozen_external_confirmation"
                    else "candidate_ontology_gain"
                )
                if predictive["relative_rmse_improvement"] is not None
                and predictive["relative_rmse_improvement"] >= threshold
                else "not_supported",
                "minimum_relative_rmse_improvement": threshold,
                "observed_relative_rmse_improvement": predictive["relative_rmse_improvement"],
            },
        },
        "claim_boundary": (
            "All claims are model-only. Spectral gap is a registered candidate macrovariable; "
            "it becomes an accepted ontology gain only if the held-out improvement threshold "
            "passes and a fresh independent campaign confirms it."
        ),
    }


def write_phase_map(path: Path, summary: Mapping[str, Any]) -> None:
    rows = summary["condition_summaries"]
    fieldnames = [
        "split",
        "nodes",
        "topology",
        "degree",
        "state_dimension",
        "coupling",
        "episodes",
        "spectral_gap_mean",
        "final_perturbation_ratio_mean",
        "recovery_half_life_median",
        "recovery_fraction",
        "synchronization_error_mean",
        "dirichlet_energy_mean",
        "effective_state_dimension_mean",
        "regime_counts",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            emitted = {key: row[key] for key in fieldnames}
            emitted["regime_counts"] = json.dumps(emitted["regime_counts"], sort_keys=True)
            writer.writerow(emitted)


def build_knowledge_card(summary: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    predictive = summary["predictive_comparison"]
    h1 = summary["hypothesis_assessment"]["H1_topology_recovery"]
    h2 = summary["hypothesis_assessment"]["H2_spectral_prediction"]
    comparisons = "; ".join(
        f"{row['target_topology']} delta={row['mean_log10_recovery_ratio_delta_vs_ring']:.4f}, faster={row['direction_fraction_faster']:.3f}"
        for row in summary["paired_topology_comparisons"]
    )
    baseline_rmse = (
        f"{predictive['baseline_holdout_rmse']:.6f}"
        if predictive["baseline_holdout_rmse"] is not None
        else "not evaluated"
    )
    spectral_rmse = (
        f"{predictive['spectral_holdout_rmse']:.6f}"
        if predictive["spectral_holdout_rmse"] is not None
        else "not evaluated"
    )
    improvement = (
        f"{predictive['relative_rmse_improvement']:.3%}"
        if predictive["relative_rmse_improvement"] is not None
        else "not evaluated"
    )
    confirmed = h2["status"] == "confirmed_ontology_gain"
    inference_text = (
        "The independently frozen v1 spectral-gap predictor retained its registered advantage "
        "under the v2 distribution shift. This supports accepting spectral gap as a model-only "
        "predictive macrovariable for perturbation recovery in this graph-CA family."
        if confirmed
        else "Within this explicit graph CA, degree-preserving topology changes alter "
        "perturbation propagation and recovery. Spectral gap is evaluated as a compact "
        "macrovariable rather than treated as explanatory by definition."
    )
    next_experiment = (
        "Test necessity and mediation rather than prediction alone: construct graph pairs with "
        "similar spectral gap but different clustering/path length, and pairs with similar "
        "clustering but separated spectral gaps. Keep the v1/v2 data closed to model selection."
        if confirmed
        else "If H2 passes, freeze a new confirmation campaign using unseen degree values and a "
        "fourth topology family, with edge-shuffled spectral controls. If it fails, compare path "
        "length and clustering as alternative registered macrovariables without reusing this "
        "holdout as confirmation."
    )
    return f"""# Vector-State Graph Laboratory Knowledge Card

## Observed

- {summary['row_count']} independently seeded graph-state episodes were retained across {summary['condition_count']} split-condition cells.
- Paired topology results versus the equal-degree ring were: {comparisons}.
- Baseline holdout RMSE was {baseline_rmse}; adding normalized-Laplacian spectral gap produced RMSE {spectral_rmse}, a relative improvement of {improvement}.
- Determinism passed: {receipt['determinism']['passed']}; maximum RSS was {receipt['max_rss_mb']:.2f} MB and wall time was {receipt['wall_seconds']:.2f} seconds.

## Hypothesis Assessment

- H1 topology/recovery: **{h1['status']}**.
- H2 spectral prediction: **{h2['status']}** against a frozen minimum relative RMSE improvement of {h2['minimum_relative_rmse_improvement']:.1%}.

## Inferred

{inference_text}

## Not Supported

- No biological morphogenesis, intelligence, open-endedness, or external network claim is established.
- A predictive improvement does not prove spectral gap is the unique mechanism.
- State dimension is channel count, not ambient spatial dimension.
- No holonomy or curvature claim is made because this rule has no edge-specific transport maps.

## Robustness

All graphs are connected and exactly regular at the frozen degree. Discovery, confirmatory, and holdout seeds are disjoint. Holdout changes node count and graph instances while preserving the registered topology families.

## Confounds

- The same nonlinear channel matrix family is rescaled across state dimensions.
- A single registered node/channel perturbation does not characterize all interventions.
- Graph families differ in clustering and path length as well as spectral gap.
- Predictive rows share topology families even though graph instances and sizes are held out.

## Artifacts

- `frozen_manifest.json`, `raw_episodes.jsonl`, `summary.json`, `phase_map.csv`
- `seed_manifest.json`, `receipt.json`, `hashes.json`
- Replay: `{receipt['replay_command']}`

## Next Experiment

{next_experiment}
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
    parser.add_argument("--skip-determinism", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output = (args.output or Path(manifest["artifacts"]["output_directory"])).resolve()
    output.mkdir(parents=True, exist_ok=True)
    code_path = Path(__file__).resolve()
    budget = manifest["budget"]
    design = manifest["design"]
    deadline = time.monotonic() + float(budget["max_wall_seconds"])
    max_ram_mb = float(budget["max_ram_mb"])
    steps = min(int(design["steps"]), int(budget["max_steps_per_episode"]))
    burn_in = int(design["burn_in"])
    if args.smoke:
        steps = min(8, steps)
        burn_in = min(3, burn_in)
    splits = parse_splits(args.splits)
    seeds_by_split = manifest["seed_plan"]
    if args.smoke:
        seeds_by_split = {split: [manifest["seed_plan"][split][0]] for split in SPLITS}
    started = time.monotonic()
    started_utc = utc_now()
    rows: list[dict[str, Any]] = []
    max_rss = current_rss_mb()
    status = "ok"
    stop_reason = "completed_declared_splits"
    determinism: dict[str, Any] = {"performed": False, "passed": None}

    try:
        frozen_predictor = manifest["analysis"].get("frozen_predictor")
        if isinstance(frozen_predictor, dict):
            source_path = Path(frozen_predictor["source_summary_path"])
            if not source_path.is_absolute():
                source_path = (manifest_path.parent / source_path).resolve()
            if not source_path.is_file():
                raise RuntimeError(f"frozen predictor source missing: {source_path}")
            if sha256_file(source_path) != frozen_predictor["source_summary_sha256"]:
                raise RuntimeError("frozen predictor source hash mismatch")
        if not args.skip_determinism:
            split = splits[0]
            spec = condition_specs(manifest, split, True)[0]
            seed = int(seeds_by_split[split][0])
            kwargs = {
                "split": split,
                "seed": seed,
                **spec,
                "steps": min(8, steps),
                "burn_in": min(3, burn_in),
                "perturbation_magnitude": float(design["perturbation_magnitude"]),
                "deadline": deadline,
                "max_ram_mb": max_ram_mb,
            }
            first = run_episode(**kwargs)
            second = run_episode(**kwargs)
            determinism = {
                "performed": True,
                "passed": (
                    first["provenance"]["final_state_sha256"]
                    == second["provenance"]["final_state_sha256"]
                    and first["provenance"]["final_perturbed_state_sha256"]
                    == second["provenance"]["final_perturbed_state_sha256"]
                    and first["graph"]["edge_sha256"] == second["graph"]["edge_sha256"]
                ),
                "condition": first["condition"],
                "seed": seed,
                "first_final_state_sha256": first["provenance"]["final_state_sha256"],
                "second_final_state_sha256": second["provenance"]["final_state_sha256"],
                "first_edge_sha256": first["graph"]["edge_sha256"],
                "second_edge_sha256": second["graph"]["edge_sha256"],
            }
            if not determinism["passed"]:
                raise RuntimeError("determinism replay failed")

        planned = sum(
            len(seeds_by_split[split]) * len(condition_specs(manifest, split, args.smoke))
            for split in splits
        )
        if planned > int(budget["max_episodes"]):
            raise RuntimeError("planned episode count exceeds budget")
        with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as raw:
            for split in splits:
                for seed in seeds_by_split[split]:
                    for spec in condition_specs(manifest, split, args.smoke):
                        if int(spec["nodes"]) > int(budget["max_cells_per_world"]):
                            raise RuntimeError(f"node cap exceeded by condition: {spec}")
                        row = run_episode(
                            split=split,
                            seed=int(seed),
                            **spec,
                            steps=steps,
                            burn_in=burn_in,
                            perturbation_magnitude=float(design["perturbation_magnitude"]),
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        rows.append(row)
                        raw.write(json.dumps(row, sort_keys=True) + "\n")
                        raw.flush()
                        max_rss = max(max_rss, float(row["provenance"]["max_rss_mb"]))
    except (MemoryError, TimeoutError, RuntimeError, ValueError, nx.NetworkXException) as exc:
        status = "stopped"
        stop_reason = f"{type(exc).__name__}: {exc}"

    summary = summarize(rows, manifest) if rows else {
        "schema": SUMMARY_SCHEMA,
        "row_count": 0,
        "condition_count": 0,
        "episode_counts": {split: 0 for split in SPLITS},
    }
    summary["status"] = status
    summary["stop_reason"] = stop_reason
    summary["determinism"] = determinism
    write_json(output / "summary.json", summary)
    if rows:
        write_phase_map(output / "phase_map.csv", summary)
    else:
        (output / "phase_map.csv").write_text("", encoding="utf-8")
    write_json(
        output / "seed_manifest.json",
        {
            "splits_run": splits,
            "seeds": {split: list(seeds_by_split[split]) for split in splits},
            "pairing": manifest["seed_plan"]["pairing"],
        },
    )
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "networkx": nx.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "status": status,
        "stop_reason": stop_reason,
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "max_rss_mb": max_rss,
        "episode_count": len(rows),
        "code_path": str(code_path),
        "code_sha256": sha256_file(code_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        **environment,
        "environment_sha256": sha256_bytes(
            json.dumps(environment, sort_keys=True).encode("utf-8")
        ),
        "version_control": "not_a_git_repository",
        "output_path": str(output),
        "determinism": determinism,
        "frozen_predictor_source": manifest["analysis"].get("frozen_predictor"),
        "replay_command": (
            f"python src/graph_state_lab.py --manifest {manifest_path} --output {output} "
            f"--splits {','.join(splits)}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(
        build_knowledge_card(summary, receipt) if rows else "# Graph Lab Failed Before Evidence\n",
        encoding="utf-8",
    )
    artifact_names = [
        "raw_episodes.jsonl",
        "summary.json",
        "phase_map.csv",
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
        raise SystemExit("artifact directory exceeded declared disk budget")
    print(json.dumps({"output": str(output), "status": status, "episodes": len(rows)}, indent=2))
    raise SystemExit(0 if status == "ok" else 1)


if __name__ == "__main__":
    main()
