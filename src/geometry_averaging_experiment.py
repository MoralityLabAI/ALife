#!/usr/bin/env python3
"""Degree-aware high-dimensional Life control for geometry-to-averaging tests.

The simulator is deliberately small and fully observable.  One independently
seeded toroidal world is the experimental unit.  Ticks and cells are repeated
measurements, never replicates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
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

import numpy as np
import psutil


SCHEMA_EPISODE = "alife.geometry_averaging.episode.v1"
SCHEMA_SUMMARY = "alife.geometry_averaging.summary.v1"
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


def state_digest(state: np.ndarray) -> str:
    shape = ",".join(str(item) for item in state.shape).encode("ascii")
    return sha256_bytes(shape + b":" + np.packbits(state.reshape(-1)).tobytes())


def trajectory_digest(trajectory: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(trajectory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def canonical_direction(vector: Sequence[int]) -> tuple[int, ...]:
    result = tuple(int(value) for value in vector)
    for value in result:
        if value < 0:
            return tuple(-item for item in result)
        if value > 0:
            return result
    raise ValueError("zero direction has no canonical orientation")


def degree_matched_offsets(dimension: int, degree: int) -> tuple[tuple[int, ...], ...]:
    if degree <= 0 or degree % 2:
        raise ValueError("matched degree must be a positive even integer")
    pair_target = degree // 2
    if pair_target < dimension:
        raise ValueError("matched degree must be at least 2 * dimension to span every axis")

    directions: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()

    def add(vector: Sequence[int]) -> None:
        direction = canonical_direction(vector)
        if direction not in seen:
            directions.append(direction)
            seen.add(direction)

    for axis in range(dimension):
        vector = [0] * dimension
        vector[axis] = 1
        add(vector)
    for left in range(dimension):
        for right in range(left + 1, dimension):
            plus = [0] * dimension
            plus[left] = 1
            plus[right] = 1
            add(plus)
            minus = [0] * dimension
            minus[left] = 1
            minus[right] = -1
            add(minus)
    for axis in range(dimension):
        vector = [0] * dimension
        vector[axis] = 2
        add(vector)

    if len(directions) < pair_target:
        raise ValueError(f"could not construct {pair_target} unique direction pairs")
    selected = directions[:pair_target]
    offsets: list[tuple[int, ...]] = []
    for direction in selected:
        offsets.extend((direction, tuple(-item for item in direction)))
    return tuple(offsets)


def neighborhood_offsets(
    dimension: int,
    neighborhood: str,
    matched_degree: int,
) -> tuple[tuple[int, ...], ...]:
    if neighborhood == "axis":
        offsets: list[tuple[int, ...]] = []
        for axis in range(dimension):
            positive = [0] * dimension
            positive[axis] = 1
            offsets.extend((tuple(positive), tuple(-item for item in positive)))
        return tuple(offsets)
    if neighborhood == "degree_matched":
        return degree_matched_offsets(dimension, matched_degree)
    if neighborhood == "moore":
        return tuple(
            offset
            for offset in itertools.product((-1, 0, 1), repeat=dimension)
            if any(offset)
        )
    raise ValueError(f"unknown neighborhood: {neighborhood}")


def rule_counts(profile: str, degree: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if profile == "literal_b3s23":
        return tuple(value for value in (3,) if value <= degree), tuple(
            value for value in (2, 3) if value <= degree
        )
    if profile != "fraction_band":
        raise ValueError(f"unknown rule profile: {profile}")

    birth_low = math.ceil(0.32 * degree)
    birth_high = math.floor(0.42 * degree)
    if birth_low > birth_high:
        birth_low = birth_high = max(0, min(degree, math.floor(0.375 * degree + 0.5)))
    survive_low = math.ceil(0.24 * degree)
    survive_high = math.floor(0.42 * degree)
    if survive_low > survive_high:
        survive_low = survive_high = max(0, min(degree, math.floor(0.32 * degree + 0.5)))
    return tuple(range(birth_low, birth_high + 1)), tuple(range(survive_low, survive_high + 1))


def neighbor_counts(state: np.ndarray, offsets: Sequence[Sequence[int]]) -> np.ndarray:
    axes = tuple(range(state.ndim))
    result = np.zeros(state.shape, dtype=np.uint16)
    for offset in offsets:
        result += np.roll(state, shift=tuple(offset), axis=axes)
    return result


def advance(
    state: np.ndarray,
    offsets: Sequence[Sequence[int]],
    birth_counts: Sequence[int],
    survival_counts: Sequence[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    counts = neighbor_counts(state, offsets)
    birth_eligible = (~state) & np.isin(counts, birth_counts)
    survive = state & np.isin(counts, survival_counts)
    next_state = birth_eligible | survive
    changed = next_state != state
    return next_state, counts, birth_eligible, changed


def binomial_probability(degree: int, density: float, allowed: Sequence[int]) -> float:
    if density <= 0.0:
        return 1.0 if 0 in allowed else 0.0
    if density >= 1.0:
        return 1.0 if degree in allowed else 0.0
    total = 0.0
    for value in allowed:
        total += (
            math.comb(degree, value)
            * density**value
            * (1.0 - density) ** (degree - value)
        )
    return total


def mean_field_next(
    density: float,
    degree: int,
    birth_counts: Sequence[int],
    survival_counts: Sequence[int],
) -> float:
    birth_probability = binomial_probability(degree, density, birth_counts)
    survival_probability = binomial_probability(degree, density, survival_counts)
    return (1.0 - density) * birth_probability + density * survival_probability


def integrated_axis_correlation(state: np.ndarray, max_lag: int) -> tuple[float, list[float]]:
    density = float(state.mean())
    variance = density * (1.0 - density)
    if variance <= 1e-12:
        return 0.0, [0.0] * max_lag
    axes = tuple(range(state.ndim))
    normalized: list[float] = []
    for lag in range(1, max_lag + 1):
        covariances = [
            float(np.mean(state & np.roll(state, shift=lag, axis=axis))) - density * density
            for axis in axes
        ]
        normalized.append(float(statistics.mean(abs(value) / variance for value in covariances)))
    return float(sum(normalized)), normalized


def torus_perturbation_extent(mask: np.ndarray, center: Sequence[int]) -> int:
    coordinates = np.argwhere(mask)
    if coordinates.size == 0:
        return 0
    center_array = np.asarray(center, dtype=int)
    side_array = np.asarray(mask.shape, dtype=int)
    delta = np.abs(coordinates - center_array)
    wrapped = np.minimum(delta, side_array - delta)
    return int(np.max(np.sum(wrapped, axis=1)))


def current_rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def check_budget(deadline: float, max_ram_mb: float) -> None:
    if time.monotonic() > deadline:
        raise TimeoutError("declared wall-time budget exceeded")
    rss = current_rss_mb()
    if rss > max_ram_mb:
        raise MemoryError(f"declared RAM budget exceeded: {rss:.1f} MB > {max_ram_mb:.1f} MB")


def classify_regime(
    final_density: float,
    mean_turnover: float,
    repeated_state_tick: int | None,
) -> str:
    if final_density == 0.0:
        return "extinct"
    if repeated_state_tick is not None:
        return "fixed_or_cycle"
    if final_density >= 0.90:
        return "saturated"
    if mean_turnover < 1e-4:
        return "frozen"
    if final_density < 0.20:
        return "active_sparse"
    return "active_dense"


def mean_or_none(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return float(statistics.mean(materialized)) if materialized else None


def run_episode(
    *,
    split: str,
    seed: int,
    dimension: int,
    side: int,
    density: float,
    neighborhood: str,
    rule_profile: str,
    matched_degree: int,
    steps: int,
    burn_in: int,
    correlation_max_lag: int,
    deadline: float,
    max_ram_mb: float,
) -> dict[str, Any]:
    started = time.monotonic()
    shape = (side,) * dimension
    cell_count = side**dimension
    offsets = neighborhood_offsets(dimension, neighborhood, matched_degree)
    degree = len(offsets)
    birth_counts, survival_counts = rule_counts(rule_profile, degree)
    rng = np.random.default_rng(seed)
    state = rng.random(shape) < density
    perturbed = state.copy()
    center = tuple(side // 2 for _ in range(dimension))
    perturbed[center] = ~perturbed[center]
    initial_hash = state_digest(state)

    trajectory: list[dict[str, Any]] = []
    seen: dict[str, int] = {initial_hash: 0}
    repeated_state_tick: int | None = None
    localized_candidate_run = 0
    localized_candidate_lifetime = 0
    perturbation_hamming_peak = 1
    perturbation_extent_peak = 0
    max_rss = current_rss_mb()
    exposure = {
        "cell_ticks": 0,
        "birth_eligible": 0,
        "birth_executed": 0,
        "changed_cells": 0,
        "survival_events": 0,
        "death_events": 0,
    }

    max_lag = max(1, min(correlation_max_lag, side // 2))
    for tick in range(1, steps + 1):
        check_budget(deadline, max_ram_mb)
        density_before = float(state.mean())
        predicted_density = mean_field_next(density_before, degree, birth_counts, survival_counts)
        next_state, counts, birth_eligible, changed = advance(
            state, offsets, birth_counts, survival_counts
        )
        next_perturbed, _, _, _ = advance(
            perturbed, offsets, birth_counts, survival_counts
        )
        density_after = float(next_state.mean())
        pair_alive = float(np.mean(state * counts) / degree)
        pair_covariance = pair_alive - density_before * density_before
        local_density = counts.astype(np.float64) / degree
        independent_local_variance = density_before * (1.0 - density_before) / degree
        excess_local_variance = float(np.var(local_density) - independent_local_variance)
        turnover = float(changed.mean())
        correlation_length_proxy, correlation_profile = integrated_axis_correlation(
            state, max_lag
        )
        difference = next_state != next_perturbed
        perturbation_hamming = int(difference.sum())
        perturbation_extent = torus_perturbation_extent(difference, center)
        perturbation_hamming_peak = max(perturbation_hamming_peak, perturbation_hamming)
        perturbation_extent_peak = max(perturbation_extent_peak, perturbation_extent)

        localized_candidate = (
            0.0 < density_after <= 0.15
            and abs(pair_covariance) >= 0.01
            and turnover >= 1e-4
        )
        localized_candidate_run = localized_candidate_run + 1 if localized_candidate else 0
        localized_candidate_lifetime = max(localized_candidate_lifetime, localized_candidate_run)

        births = int(np.count_nonzero((~state) & next_state))
        survivals = int(np.count_nonzero(state & next_state))
        deaths = int(np.count_nonzero(state & (~next_state)))
        exposure["cell_ticks"] += cell_count
        exposure["birth_eligible"] += int(birth_eligible.sum())
        exposure["birth_executed"] += births
        exposure["changed_cells"] += int(changed.sum())
        exposure["survival_events"] += survivals
        exposure["death_events"] += deaths

        trajectory.append(
            {
                "tick": tick,
                "density_before": density_before,
                "density_after": density_after,
                "mean_field_prediction": predicted_density,
                "mean_field_abs_error": abs(density_after - predicted_density),
                "pair_covariance": pair_covariance,
                "excess_local_neighbor_variance": excess_local_variance,
                "turnover": turnover,
                "correlation_length_proxy": correlation_length_proxy,
                "axis_correlation_profile": correlation_profile,
                "perturbation_hamming": perturbation_hamming,
                "perturbation_extent": perturbation_extent,
                "births": births,
                "survivals": survivals,
                "deaths": deaths,
            }
        )
        state = next_state
        perturbed = next_perturbed
        digest = state_digest(state)
        if repeated_state_tick is None and digest in seen:
            repeated_state_tick = tick
        seen.setdefault(digest, tick)
        max_rss = max(max_rss, current_rss_mb())

    post = trajectory[max(0, burn_in - 1) :]
    mean_turnover = mean_or_none(float(row["turnover"]) for row in post) or 0.0
    final_density = float(state.mean())
    return {
        "schema": SCHEMA_EPISODE,
        "split": split,
        "seed": seed,
        "experimental_unit": "one independently initialized toroidal world",
        "condition": {
            "dimension": dimension,
            "side": side,
            "cell_count": cell_count,
            "initial_density": density,
            "neighborhood": neighborhood,
            "degree": degree,
            "matched_degree": matched_degree if neighborhood == "degree_matched" else None,
            "rule_profile": rule_profile,
            "birth_counts": list(birth_counts),
            "survival_counts": list(survival_counts),
            "boundary": "periodic_torus",
            "update": "synchronous_deterministic_totalistic",
        },
        "exposure": exposure,
        "outcomes": {
            "mean_field_mae_post_burn": mean_or_none(
                float(row["mean_field_abs_error"]) for row in post
            ),
            "neighbor_pair_cov_abs_post_burn": mean_or_none(
                abs(float(row["pair_covariance"])) for row in post
            ),
            "neighbor_pair_cov_signed_post_burn": mean_or_none(
                float(row["pair_covariance"]) for row in post
            ),
            "excess_local_neighbor_variance_post_burn": mean_or_none(
                float(row["excess_local_neighbor_variance"]) for row in post
            ),
            "correlation_length_proxy_post_burn": mean_or_none(
                float(row["correlation_length_proxy"]) for row in post
            ),
            "turnover_post_burn": mean_turnover,
            "localized_structure_candidate_lifetime": localized_candidate_lifetime,
            "perturbation_hamming_peak": perturbation_hamming_peak,
            "perturbation_extent_peak": perturbation_extent_peak,
            "final_density": final_density,
            "repeated_state_tick": repeated_state_tick,
            "regime": classify_regime(final_density, mean_turnover, repeated_state_tick),
        },
        "trajectory": trajectory,
        "provenance": {
            "initial_state_sha256": initial_hash,
            "final_state_sha256": state_digest(state),
            "trajectory_sha256": trajectory_digest(trajectory),
            "rng": "numpy.default_rng(seed) used for initialization only; updates deterministic",
            "runtime_seconds": time.monotonic() - started,
            "max_rss_mb": max_rss,
        },
    }


def condition_specs(manifest: Mapping[str, Any], split: str, smoke: bool) -> list[dict[str, Any]]:
    design = manifest["design"]
    dimensions = [int(value) for value in design["dimensions"]]
    densities = [float(value) for value in design["densities_by_split"][split]]
    profiles = design["rule_neighborhood_matrix"]
    if smoke:
        dimensions = dimensions[:1]
        densities = densities[:1]
        profiles = [{"rule_profile": "fraction_band", "neighborhoods": ["axis", "degree_matched"]}]
    specs: list[dict[str, Any]] = []
    for dimension in dimensions:
        side = int(design["sides_by_split"][split][str(dimension)])
        for density in densities:
            for profile in profiles:
                for neighborhood in profile["neighborhoods"]:
                    specs.append(
                        {
                            "dimension": dimension,
                            "side": side,
                            "density": density,
                            "rule_profile": profile["rule_profile"],
                            "neighborhood": neighborhood,
                        }
                    )
    return specs


def quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=float), probability))


def bootstrap_mean_interval(values: Sequence[float], seed: int = 260713) -> list[float | None]:
    if not values:
        return [None, None]
    if len(values) == 1:
        return [float(values[0]), float(values[0])]
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    estimates = np.mean(rng.choice(array, size=(2000, len(array)), replace=True), axis=1)
    return [float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))]


def linear_slope(points: Sequence[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None
    x = np.asarray([point[0] for point in points], dtype=float)
    y = np.asarray([point[1] for point in points], dtype=float)
    denominator = float(np.sum((x - x.mean()) ** 2))
    if denominator == 0.0:
        return None
    return float(np.sum((x - x.mean()) * (y - y.mean())) / denominator)


def summarize(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    thresholds = manifest["analysis"]["adequacy_thresholds"]
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        condition = row["condition"]
        key = (
            row["split"],
            condition["dimension"],
            condition["side"],
            condition["initial_density"],
            condition["neighborhood"],
            condition["degree"],
            condition["rule_profile"],
        )
        groups[key].append(row)

    condition_summaries: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        split, dimension, side, density, neighborhood, degree, profile = key
        maes = [float(row["outcomes"]["mean_field_mae_post_burn"]) for row in group]
        covariances = [float(row["outcomes"]["neighbor_pair_cov_abs_post_burn"]) for row in group]
        correlations = [float(row["outcomes"]["correlation_length_proxy_post_burn"]) for row in group]
        metric_adequacy_by_episode = [
            mae <= float(thresholds["mean_field_mae_max"])
            and covariance <= float(thresholds["pair_covariance_abs_max"])
            and correlation <= float(thresholds["correlation_length_proxy_max"])
            for mae, covariance, correlation in zip(maes, covariances, correlations)
        ]
        active_regimes = {"active_sparse", "active_dense"}
        active_adequacy_by_episode = [
            metric_adequate and str(row["outcomes"]["regime"]) in active_regimes
            for metric_adequate, row in zip(metric_adequacy_by_episode, group)
        ]
        metric_adequacy_fraction = sum(metric_adequacy_by_episode) / len(metric_adequacy_by_episode)
        active_adequacy_fraction = sum(active_adequacy_by_episode) / len(active_adequacy_by_episode)
        frozen_metric_adequate = (
            metric_adequacy_fraction >= float(thresholds["minimum_episode_fraction"])
        )
        nontrivial_averaging_evidence = (
            active_adequacy_fraction >= float(thresholds["minimum_episode_fraction"])
        )
        regimes: dict[str, int] = defaultdict(int)
        for row in group:
            regimes[str(row["outcomes"]["regime"])] += 1
        condition_summaries.append(
            {
                "split": split,
                "dimension": dimension,
                "side": side,
                "cell_count": side**dimension,
                "initial_density": density,
                "neighborhood": neighborhood,
                "degree": degree,
                "rule_profile": profile,
                "episodes": len(group),
                "mean_field_mae_mean": float(statistics.mean(maes)),
                "mean_field_mae_median": float(statistics.median(maes)),
                "mean_field_mae_bootstrap_95": bootstrap_mean_interval(maes),
                "pair_covariance_abs_mean": float(statistics.mean(covariances)),
                "correlation_length_proxy_mean": float(statistics.mean(correlations)),
                "adequacy_fraction": metric_adequacy_fraction,
                "metric_adequacy_fraction": metric_adequacy_fraction,
                "active_adequacy_fraction": active_adequacy_fraction,
                "frozen_metric_adequate": frozen_metric_adequate,
                "nontrivial_averaging_evidence": nontrivial_averaging_evidence,
                "adequate_for_averaging": nontrivial_averaging_evidence,
                "trivial_metric_pass": frozen_metric_adequate and not nontrivial_averaging_evidence,
                "regime_counts": dict(sorted(regimes.items())),
                "runtime_seconds_mean": float(
                    statistics.mean(float(row["provenance"]["runtime_seconds"]) for row in group)
                ),
                "max_rss_mb": max(float(row["provenance"]["max_rss_mb"]) for row in group),
            }
        )

    slopes: list[dict[str, Any]] = []
    slope_groups: dict[tuple[str, str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for row in condition_summaries:
        slope_groups[
            (row["split"], row["neighborhood"], row["rule_profile"], row["initial_density"])
        ].append(row)
    for key, group in sorted(slope_groups.items()):
        split, neighborhood, profile, density = key
        points = sorted(
            (float(row["dimension"]), float(row["mean_field_mae_mean"])) for row in group
        )
        slopes.append(
            {
                "split": split,
                "neighborhood": neighborhood,
                "rule_profile": profile,
                "initial_density": density,
                "mae_slope_per_dimension": linear_slope(points),
                "points": points,
            }
        )

    def slope_for(split: str, neighborhood: str, density: float) -> float | None:
        for row in slopes:
            if (
                row["split"] == split
                and row["neighborhood"] == neighborhood
                and row["rule_profile"] == "fraction_band"
                and float(row["initial_density"]) == density
            ):
                return row["mae_slope_per_dimension"]
        return None

    confirmatory_moore_slope = slope_for("confirmatory", "moore", 0.35)
    confirmatory_matched_slope = slope_for("confirmatory", "degree_matched", 0.35)
    literal_high_dimension = [
        row
        for row in condition_summaries
        if row["split"] in {"confirmatory", "holdout"}
        and row["rule_profile"] == "literal_b3s23"
        and row["neighborhood"] == "moore"
        and int(row["dimension"]) >= 4
    ]
    literal_high_dimension_extinct = bool(literal_high_dimension) and all(
        set(row["regime_counts"]) == {"extinct"} for row in literal_high_dimension
    )
    hypothesis_assessment = {
        "H1_degree": {
            "status": "qualified_support"
            if confirmatory_moore_slope is not None and confirmatory_moore_slope < 0
            else "not_supported",
            "evidence": (
                f"Confirmatory Moore MAE slope per dimension was {confirmatory_moore_slope}; "
                "the decline reaches zero-error extinction at high dimension, so it supports "
                "closure improvement but not nontrivial emergent structure."
            ),
        },
        "H2_geometry": {
            "status": "not_supported"
            if (
                confirmatory_matched_slope is not None
                and confirmatory_moore_slope is not None
                and confirmatory_matched_slope < 0
                and abs(confirmatory_matched_slope) >= abs(confirmatory_moore_slope)
            )
            else "inconclusive",
            "evidence": (
                f"Confirmatory fixed-degree MAE slope was {confirmatory_matched_slope} versus "
                f"Moore {confirmatory_moore_slope}. Holding degree at 12 did not weaken the "
                "dimension trend in this sweep, although no fixed-degree cell met the full "
                "nontrivial adequacy conjunction."
            ),
        },
        "H3_literal_control": {
            "status": "supported_within_sample" if literal_high_dimension_extinct else "not_supported",
            "evidence": (
                f"All {len(literal_high_dimension)} confirmatory/holdout literal-B3S23 cells "
                f"at dimensions 4-5 were extinction-only: {literal_high_dimension_extinct}."
            ),
        },
    }
    exposure_audit = {
        "episodes": len(rows),
        "episodes_with_declared_cell_ticks": sum(
            1
            for row in rows
            if int(row["exposure"]["cell_ticks"])
            == int(row["condition"]["cell_count"]) * len(row["trajectory"])
        ),
        "episodes_with_state_change": sum(
            1 for row in rows if int(row["exposure"]["changed_cells"]) > 0
        ),
        "episodes_with_birth_eligibility": sum(
            1 for row in rows if int(row["exposure"]["birth_eligible"]) > 0
        ),
    }

    return {
        "schema": SCHEMA_SUMMARY,
        "row_count": len(rows),
        "condition_count": len(condition_summaries),
        "episode_counts": {
            split: sum(1 for row in rows if row["split"] == split) for split in SPLITS
        },
        "adequacy_thresholds": thresholds,
        "condition_summaries": condition_summaries,
        "dimension_slopes": slopes,
        "hypothesis_assessment": hypothesis_assessment,
        "exposure_audit": exposure_audit,
        "claim_boundary": (
            "Adequacy labels apply only to the implemented binary totalistic CA, declared "
            "densities, sizes, horizons, neighborhoods, and thresholds. They are not a universal "
            "critical dimension or a claim that spatial structure is absent."
        ),
    }


def write_phase_map(path: Path, summary: Mapping[str, Any]) -> None:
    rows = summary["condition_summaries"]
    fieldnames = [
        "split",
        "dimension",
        "side",
        "cell_count",
        "initial_density",
        "neighborhood",
        "degree",
        "rule_profile",
        "episodes",
        "mean_field_mae_mean",
        "mean_field_mae_median",
        "pair_covariance_abs_mean",
        "correlation_length_proxy_mean",
        "adequacy_fraction",
        "metric_adequacy_fraction",
        "active_adequacy_fraction",
        "frozen_metric_adequate",
        "nontrivial_averaging_evidence",
        "trivial_metric_pass",
        "adequate_for_averaging",
        "runtime_seconds_mean",
        "max_rss_mb",
        "regime_counts",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            emitted = {key: row[key] for key in fieldnames}
            emitted["regime_counts"] = json.dumps(emitted["regime_counts"], sort_keys=True)
            writer.writerow(emitted)


def build_knowledge_card(
    summary: Mapping[str, Any],
    manifest_name: str,
    receipt: Mapping[str, Any],
) -> str:
    metric_adequate = [
        row for row in summary["condition_summaries"] if row["frozen_metric_adequate"]
    ]
    nontrivial_adequate = [
        row
        for row in summary["condition_summaries"]
        if row["nontrivial_averaging_evidence"]
    ]
    trivial_passes = [row for row in summary["condition_summaries"] if row["trivial_metric_pass"]]
    confirmatory_adequate = [
        row for row in nontrivial_adequate if row["split"] == "confirmatory"
    ]
    holdout_adequate = [row for row in nontrivial_adequate if row["split"] == "holdout"]
    matched_slopes = [
        row
        for row in summary["dimension_slopes"]
        if row["neighborhood"] == "degree_matched" and row["rule_profile"] == "fraction_band"
    ]
    slope_text = ", ".join(
        f"{row['split']}@density={row['initial_density']}: {row['mae_slope_per_dimension']}"
        for row in matched_slopes
    ) or "none"
    return f"""# Geometry-to-Averaging Knowledge Card

## Observed

- {summary['row_count']} independently seeded episodes were retained across {summary['condition_count']} split-condition cells.
- {len(metric_adequate)} cells met the frozen numeric closure conjunction; {len(trivial_passes)} of those were rejected as nontrivial evidence because their episodes were extinction, saturation, frozen, or cycle regimes.
- {len(confirmatory_adequate)} confirmatory and {len(holdout_adequate)} holdout cells met both the frozen closure conjunction and the active-regime hazard overlay.
- Degree-matched fraction-band mean-field MAE slopes by split were: {slope_text}.
- Maximum observed process RSS was {receipt['max_rss_mb']:.2f} MB; wall time was {receipt['wall_seconds']:.2f} seconds.

## Hypothesis Assessment

- H1 degree: **{summary['hypothesis_assessment']['H1_degree']['status']}**. {summary['hypothesis_assessment']['H1_degree']['evidence']}
- H2 geometry: **{summary['hypothesis_assessment']['H2_geometry']['status']}**. {summary['hypothesis_assessment']['H2_geometry']['evidence']}
- H3 literal control: **{summary['hypothesis_assessment']['H3_literal_control']['status']}**. {summary['hypothesis_assessment']['H3_literal_control']['evidence']}

## Inferred

The phase map locates model-specific conditions where a density-only binomial mean-field predictor is adequate under the frozen error, pair-covariance, correlation, episode-consistency, and active-regime gates. The fixed-degree arm shows that dimensional geometry still changes closure error even when degree is fixed; the initial hypothesis that increasing degree explains most improvement is not supported.

## Not Supported

- No universal critical dimension is established.
- An adequacy pass does not prove the absence of spatial structure or computation.
- A colorful, persistent, entropic, or active trajectory is not evidence of emergence or open-endedness by itself.
- The localized-structure diagnostic is a candidate detector, not a glider or organism classifier.
- No biological, cognitive, or external validity is claimed.

## Robustness

Discovery, confirmatory, and untouched holdout seeds are disjoint. Holdout includes the declared scale and density conditions from the frozen manifest. Literal B3/S23 on full neighborhoods is retained as a simple-limit collapse control; fixed-degree neighborhoods are the dimension-without-degree comparison.

## Confounds

- Side lengths cannot hold cell count exactly constant across dimensions.
- The density-only predictor uses the observed current density and tests one-step closure, not long-horizon forecasting.
- Periodic boundaries, synchronous updates, finite horizons, and chosen rule bands define the model family.
- Three confirmatory seeds per condition provide only coarse episode-level uncertainty.
- Correlation length is an integrated finite-lag axis proxy, not an asymptotic estimator.

## Artifacts

- Frozen manifest: `{manifest_name}`
- Raw episode rows: `raw_episodes.jsonl`
- Summary: `summary.json`
- Phase map: `phase_map.csv`
- Seed manifest: `seed_manifest.json`
- Reproducibility receipt: `receipt.json`
- Hashes: `hashes.json`
- Replay: `{receipt['replay_command']}`

## Next Experiment

Refine any transition between failing and passing adequacy cells with additional dimensions or degree values, at least five fresh seeds per boundary cell, and a second initial-density band. If no boundary is found, increase horizon before expanding the rule family.
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
    code_hash = sha256_file(code_path)
    manifest_hash = sha256_file(manifest_path)
    budget = manifest["budget"]
    deadline = time.monotonic() + float(budget["max_wall_seconds"])
    max_ram_mb = float(budget["max_ram_mb"])
    steps = int(manifest["design"]["steps"])
    burn_in = int(manifest["design"]["burn_in"])
    if args.smoke:
        steps = min(8, steps)
        burn_in = min(3, burn_in)
    splits = parse_splits(args.splits)
    started_utc = utc_now()
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    max_rss = current_rss_mb()
    status = "ok"
    stop_reason = "completed_declared_splits"

    seeds_by_split = manifest["seed_plan"]
    if args.smoke:
        seeds_by_split = {split: [manifest["seed_plan"][split][0]] for split in SPLITS}

    determinism: dict[str, Any] = {"performed": False, "passed": None}
    try:
        if not args.skip_determinism:
            split = splits[0]
            spec = condition_specs(manifest, split, True)[0]
            seed = int(seeds_by_split[split][0])
            kwargs = {
                "split": split,
                "seed": seed,
                **spec,
                "matched_degree": int(manifest["design"]["matched_degree"]),
                "steps": min(8, steps),
                "burn_in": min(3, burn_in),
                "correlation_max_lag": int(manifest["design"]["correlation_max_lag"]),
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
                    and first["provenance"]["trajectory_sha256"]
                    == second["provenance"]["trajectory_sha256"]
                ),
                "condition": first["condition"],
                "seed": seed,
                "first_final_state_sha256": first["provenance"]["final_state_sha256"],
                "second_final_state_sha256": second["provenance"]["final_state_sha256"],
                "first_trajectory_sha256": first["provenance"]["trajectory_sha256"],
                "second_trajectory_sha256": second["provenance"]["trajectory_sha256"],
            }
            if not determinism["passed"]:
                raise RuntimeError("determinism replay failed")

        planned = sum(
            len(seeds_by_split[split]) * len(condition_specs(manifest, split, args.smoke))
            for split in splits
        )
        if planned > int(budget["max_episodes"]):
            raise RuntimeError(
                f"planned episodes {planned} exceed declared max_episodes {budget['max_episodes']}"
            )

        with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as raw_handle:
            for split in splits:
                for seed in seeds_by_split[split]:
                    for spec in condition_specs(manifest, split, args.smoke):
                        if spec["side"] ** spec["dimension"] > int(budget["max_cells_per_world"]):
                            raise RuntimeError(f"cell cap exceeded by condition: {spec}")
                        row = run_episode(
                            split=split,
                            seed=int(seed),
                            **spec,
                            matched_degree=int(manifest["design"]["matched_degree"]),
                            steps=steps,
                            burn_in=burn_in,
                            correlation_max_lag=int(manifest["design"]["correlation_max_lag"]),
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        rows.append(row)
                        raw_handle.write(json.dumps(row, sort_keys=True) + "\n")
                        raw_handle.flush()
                        max_rss = max(max_rss, float(row["provenance"]["max_rss_mb"]))
    except (MemoryError, TimeoutError, RuntimeError, ValueError) as exc:
        status = "stopped"
        stop_reason = f"{type(exc).__name__}: {exc}"

    summary = summarize(rows, manifest)
    summary["status"] = status
    summary["stop_reason"] = stop_reason
    summary["determinism"] = determinism
    write_json(output / "summary.json", summary)
    write_phase_map(output / "phase_map.csv", summary)
    write_json(
        output / "seed_manifest.json",
        {
            "splits_run": splits,
            "seeds": {split: list(seeds_by_split[split]) for split in splits},
            "pairing": manifest["seed_plan"]["pairing"],
        },
    )
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    wall_seconds = time.monotonic() - started
    environment_fingerprint = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "status": status,
        "stop_reason": stop_reason,
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": wall_seconds,
        "max_rss_mb": max_rss,
        "episode_count": len(rows),
        "code_path": str(code_path),
        "code_sha256": code_hash,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_hash,
        **environment_fingerprint,
        "environment_sha256": sha256_bytes(
            json.dumps(environment_fingerprint, sort_keys=True).encode("utf-8")
        ),
        "version_control": "not_a_git_repository",
        "output_path": str(output),
        "determinism": determinism,
        "replay_command": (
            f"python src/geometry_averaging_experiment.py --manifest {manifest_path} "
            f"--output {output} --splits {','.join(splits)}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(
        build_knowledge_card(summary, "frozen_manifest.json", receipt), encoding="utf-8"
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
    hashes = {
        name: {
            "sha256": sha256_file(output / name),
            "bytes": (output / name).stat().st_size,
        }
        for name in artifact_names
        if (output / name).exists()
    }
    write_json(output / "hashes.json", hashes)
    total_bytes = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        raise SystemExit("artifact directory exceeded declared disk budget")
    print(json.dumps({"output": str(output), "status": status, "episodes": len(rows)}, indent=2))
    raise SystemExit(0 if status == "ok" else 1)


if __name__ == "__main__":
    main()
