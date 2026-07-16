#!/usr/bin/env python3
"""Bounded deterministic atlas of alternative lattice physics for ALife.

The experiment compares binary totalistic cellular automata, Gray-Scott
reaction-diffusion, and cyclic cellular automata on periodic lattices.  The
experimental unit is one independently initialized world.  Cells and ticks
are repeated observations, never replicates.
"""

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
import subprocess
import sys
import time
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import psutil

from geometry_averaging_experiment import degree_matched_offsets, neighbor_counts


SCHEMA_EPISODE = "alife.alt_physics_atlas.episode.v1"
SCHEMA_SUMMARY = "alife.alt_physics_atlas.summary.v1"
SCHEMA_RECEIPT = "alife.alt_physics_atlas.receipt.v1"
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


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


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


def mean_or_zero(values: Iterable[float]) -> float:
    materialized = list(values)
    return float(statistics.mean(materialized)) if materialized else 0.0


def state_digest(categories: np.ndarray) -> str:
    header = ",".join(str(value) for value in categories.shape).encode("ascii")
    return sha256_bytes(header + b":" + np.ascontiguousarray(categories).tobytes())


def normalized_entropy(categories: np.ndarray, category_count: int) -> float:
    counts = np.bincount(categories.reshape(-1), minlength=category_count).astype(np.float64)
    probabilities = counts[counts > 0] / counts.sum()
    if category_count <= 1 or probabilities.size <= 1:
        return 0.0
    return float(-np.sum(probabilities * np.log2(probabilities)) / math.log2(category_count))


def normalized_mutual_information_from_counts(
    joint: np.ndarray, category_count: int
) -> float:
    total = float(joint.sum())
    if total <= 0.0 or category_count <= 1:
        return 0.0
    matrix = joint.reshape(category_count, category_count).astype(np.float64) / total
    left = matrix.sum(axis=1)
    right = matrix.sum(axis=0)
    expected = left[:, None] * right[None, :]
    mask = matrix > 0
    information = float(np.sum(matrix[mask] * np.log2(matrix[mask] / expected[mask])))
    return information / math.log2(category_count)


def spatial_information(
    categories: np.ndarray,
    offsets: Sequence[Sequence[int]],
    category_count: int,
) -> tuple[float, float, float]:
    axes = tuple(range(categories.ndim))
    flat = categories.reshape(-1).astype(np.int64, copy=False)
    bins = category_count * category_count
    local_joint = np.zeros(bins, dtype=np.int64)
    baseline_joint = np.zeros(bins, dtype=np.int64)
    indices = np.arange(flat.size, dtype=np.int64)
    for index, offset in enumerate(offsets):
        local = np.roll(categories, shift=tuple(offset), axis=axes).reshape(-1)
        local_joint += np.bincount(
            flat * category_count + local.astype(np.int64, copy=False), minlength=bins
        )
        multiplier = max(3, int(round(flat.size * (0.381966 + 0.037 * index))))
        if multiplier % 2 == 0:
            multiplier += 1
        while math.gcd(multiplier, flat.size) != 1:
            multiplier += 2
        increment = (flat.size // 3 + (index + 1) * 104729) % flat.size
        permuted = flat[(multiplier * indices + increment) % flat.size]
        baseline_joint += np.bincount(
            flat * category_count + permuted, minlength=bins
        )
    local_mi = normalized_mutual_information_from_counts(local_joint, category_count)
    baseline_mi = normalized_mutual_information_from_counts(baseline_joint, category_count)
    return local_mi, baseline_mi, local_mi - baseline_mi


def compressibility_ratio(categories: np.ndarray) -> float:
    payload = np.ascontiguousarray(categories).tobytes()
    if not payload:
        return 0.0
    return len(zlib.compress(payload, level=9)) / len(payload)


def fraction_rule_counts(profile: Mapping[str, Any], degree: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if profile["name"] == "literal_b3s23":
        return tuple(int(value) for value in profile["birth_counts"]), tuple(
            int(value) for value in profile["survival_counts"]
        )
    birth_low, birth_high = (float(value) for value in profile["birth_fraction"])
    survival_low, survival_high = (float(value) for value in profile["survival_fraction"])
    births = tuple(
        count for count in range(degree + 1) if birth_low <= count / degree <= birth_high
    )
    survivals = tuple(
        count for count in range(degree + 1) if survival_low <= count / degree <= survival_high
    )
    return births, survivals


def binary_advance(
    state: np.ndarray,
    profile: Mapping[str, Any],
    offsets: Sequence[Sequence[int]],
) -> np.ndarray:
    name = str(profile["name"])
    if name == "static_identity":
        return state.copy()
    if name == "global_toggle":
        return ~state
    counts = neighbor_counts(state, offsets)
    births, survivals = fraction_rule_counts(profile, len(offsets))
    return ((~state) & np.isin(counts, births)) | (state & np.isin(counts, survivals))


def cyclic_advance(
    state: np.ndarray,
    profile: Mapping[str, Any],
    offsets: Sequence[Sequence[int]],
) -> np.ndarray:
    states = int(profile["states"])
    threshold = int(profile["successor_threshold"])
    successor = (state + 1) % states
    if threshold <= 0:
        return successor.astype(np.uint8, copy=False)
    if threshold > len(offsets):
        return state.copy()
    axes = tuple(range(state.ndim))
    contact_count = np.zeros(state.shape, dtype=np.uint16)
    for offset in offsets:
        neighbor = np.roll(state, shift=tuple(offset), axis=axes)
        contact_count += neighbor == successor
    return np.where(contact_count >= threshold, successor, state).astype(np.uint8, copy=False)


def gray_laplacian(
    field: np.ndarray, offsets: Sequence[Sequence[int]]
) -> np.ndarray:
    axes = tuple(range(field.ndim))
    total = np.zeros(field.shape, dtype=np.float32)
    for offset in offsets:
        total += np.roll(field, shift=tuple(offset), axis=axes)
    return total / np.float32(len(offsets)) - field


def gray_advance(
    state: tuple[np.ndarray, np.ndarray],
    profile: Mapping[str, Any],
    offsets: Sequence[Sequence[int]],
) -> tuple[np.ndarray, np.ndarray]:
    u, v = state
    du = np.float32(profile["diffusion_u"])
    dv = np.float32(profile["diffusion_v"])
    lap_u = gray_laplacian(u, offsets)
    lap_v = gray_laplacian(v, offsets)
    if bool(profile["reaction_enabled"]):
        feed = np.float32(profile["feed"])
        kill = np.float32(profile["kill"])
        uvv = u * v * v
        delta_u = du * lap_u - uvv + feed * (np.float32(1.0) - u)
        delta_v = dv * lap_v + uvv - (feed + kill) * v
    else:
        delta_u = du * lap_u
        delta_v = dv * lap_v
    next_u = np.clip(u + delta_u, 0.0, 1.0).astype(np.float32, copy=False)
    next_v = np.clip(v + delta_v, 0.0, 1.0).astype(np.float32, copy=False)
    return next_u, next_v


def categories_for(family: str, state: Any, profile: Mapping[str, Any]) -> tuple[np.ndarray, int]:
    if family == "binary_ca":
        return np.asarray(state, dtype=np.uint8), 2
    if family == "cyclic_ca":
        return np.asarray(state, dtype=np.uint8), int(profile["states"])
    u, v = state
    u_bin = np.minimum((u * np.float32(8.0)).astype(np.uint8), np.uint8(7))
    v_bin = np.minimum((v * np.float32(8.0)).astype(np.uint8), np.uint8(7))
    return (u_bin * np.uint8(8) + v_bin).astype(np.uint8, copy=False), 64


def initialize_states(
    family: str,
    profile: Mapping[str, Any],
    shape: tuple[int, ...],
    seed: int,
) -> tuple[Any, Any, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    center = tuple(side // 2 for side in shape)
    if family == "binary_ca":
        density = float(profile["initial_alive_probability"])
        state = rng.random(shape) < density
        perturbed = state.copy()
        perturbed[center] = ~perturbed[center]
        return state, perturbed, {"initial_alive_probability": density}
    if family == "cyclic_ca":
        states = int(profile["states"])
        state = rng.integers(0, states, size=shape, dtype=np.uint8)
        perturbed = state.copy()
        perturbed[center] = np.uint8((int(perturbed[center]) + 1) % states)
        return state, perturbed, {"initial_distribution": "uniform_over_states"}

    u = np.ones(shape, dtype=np.float32)
    v = np.zeros(shape, dtype=np.float32)
    target_fraction = 0.0625
    fraction_per_axis = target_fraction ** (1.0 / len(shape))
    widths = [max(2, min(side, int(round(side * fraction_per_axis)))) for side in shape]
    slices = tuple(
        slice((side - width) // 2, (side - width) // 2 + width)
        for side, width in zip(shape, widths)
    )
    u[slices] = np.float32(0.50)
    v[slices] = np.float32(0.25)
    u += rng.uniform(-0.01, 0.01, size=shape).astype(np.float32)
    v += rng.uniform(-0.01, 0.01, size=shape).astype(np.float32)
    np.clip(u, 0.0, 1.0, out=u)
    np.clip(v, 0.0, 1.0, out=v)
    perturbed_u = u.copy()
    perturbed_v = v.copy()
    original_v_bin = min(7, int(float(perturbed_v[center]) * 8.0))
    target_v_bin = original_v_bin + 1 if original_v_bin < 7 else original_v_bin - 1
    perturbed_v[center] = np.float32((target_v_bin + 0.5) / 8.0)
    seeded_cells = int(np.prod(widths))
    return (u, v), (perturbed_u, perturbed_v), {
        "central_seed_widths": widths,
        "central_seed_cells": seeded_cells,
        "central_seed_fraction": seeded_cells / int(np.prod(shape)),
        "noise_half_width": 0.01,
        "paired_perturbation": "center V moved to center of adjacent 1/8 concentration bin",
    }


def advance_state(
    family: str,
    state: Any,
    profile: Mapping[str, Any],
    offsets: Sequence[Sequence[int]],
) -> Any:
    if family == "binary_ca":
        return binary_advance(state, profile, offsets)
    if family == "cyclic_ca":
        return cyclic_advance(state, profile, offsets)
    return gray_advance(state, profile, offsets)


def persistence_ratio(turnovers: Sequence[float]) -> float:
    if not turnovers:
        return 0.0
    width = max(1, len(turnovers) // 4)
    early = mean_or_zero(turnovers[:width])
    late = mean_or_zero(turnovers[-width:])
    if early <= 1e-12:
        return 0.0 if late <= 1e-12 else 1.0
    return late / early


def classify_regime(outcomes: Mapping[str, Any], classifier: Mapping[str, Any]) -> str:
    thresholds = classifier["active_structured_candidate"]
    entropy = float(outcomes["normalized_state_entropy_post_burn"])
    turnover = float(outcomes["categorical_turnover_post_burn"])
    unique_fraction = float(outcomes["unique_state_fraction"])
    repeated_tick = outcomes["repeated_state_tick"]
    if entropy < float(thresholds["entropy_min_inclusive"]):
        return "uniform_collapse"
    if repeated_tick is not None and unique_fraction < float(
        thresholds["unique_state_fraction_min_inclusive"]
    ):
        return "short_cycle"
    if turnover > float(thresholds["turnover_max_inclusive"]):
        return "global_churn"
    if turnover < float(thresholds["turnover_min_inclusive"]):
        return "static_structured"
    if float(outcomes["activity_persistence_ratio"]) < float(
        thresholds["activity_persistence_ratio_min_inclusive"]
    ):
        return "transient_decay"
    candidate = (
        entropy <= float(thresholds["entropy_max_inclusive"])
        and float(outcomes["excess_neighbor_mutual_information_post_burn"])
        >= float(thresholds["excess_neighbor_mi_min_inclusive"])
        and float(outcomes["perturbation_response_gain"])
        >= float(thresholds["perturbation_response_gain_min_inclusive"])
        and float(outcomes["perturbation_peak_fraction"])
        <= float(thresholds["perturbation_peak_fraction_max_inclusive"])
        and unique_fraction >= float(thresholds["unique_state_fraction_min_inclusive"])
    )
    return "active_structured_candidate" if candidate else "active_unstructured"


def run_episode(
    *,
    split: str,
    seed: int,
    family: str,
    profile: Mapping[str, Any],
    dimension: int,
    side: int,
    matched_degree: int,
    recorded_steps: int,
    solver_steps_per_record: int,
    burn_in: int,
    spatial_every: int,
    classifier: Mapping[str, Any],
    deadline: float,
    max_ram_mb: float,
) -> dict[str, Any]:
    started = time.monotonic()
    shape = (side,) * dimension
    cell_count = int(side**dimension)
    offsets = degree_matched_offsets(dimension, matched_degree)
    state, perturbed, initialization = initialize_states(family, profile, shape, seed)
    categories, category_count = categories_for(family, state, profile)
    perturbed_categories, _ = categories_for(family, perturbed, profile)
    initial_digest = state_digest(categories)
    initial_perturbation_fraction = float(np.mean(categories != perturbed_categories))
    if initial_perturbation_fraction <= 0.0:
        raise RuntimeError("paired perturbation is invisible under the frozen categorization")

    seen: dict[str, int] = {initial_digest: 0}
    repeated_state_tick: int | None = None
    previous_categories = categories
    perturbation_peak_fraction = initial_perturbation_fraction
    perturbation_final_fraction = initial_perturbation_fraction
    max_rss = current_rss_mb()
    trajectory: list[dict[str, Any]] = []
    exposure = {
        "solver_site_evaluations": 0,
        "recorded_site_observations": 0,
        "categorical_changed_site_steps": 0,
        "records_with_state_change": 0,
        "paired_solver_site_evaluations": 0,
    }

    for tick in range(1, recorded_steps + 1):
        check_budget(deadline, max_ram_mb)
        for _ in range(solver_steps_per_record):
            before, _ = categories_for(family, state, profile)
            state = advance_state(family, state, profile, offsets)
            perturbed = advance_state(family, perturbed, profile, offsets)
            after, _ = categories_for(family, state, profile)
            changed = int(np.count_nonzero(before != after))
            exposure["solver_site_evaluations"] += cell_count
            exposure["paired_solver_site_evaluations"] += cell_count
            exposure["categorical_changed_site_steps"] += changed

        categories, category_count = categories_for(family, state, profile)
        perturbed_categories, _ = categories_for(family, perturbed, profile)
        turnover = float(np.mean(categories != previous_categories))
        if turnover > 0.0:
            exposure["records_with_state_change"] += 1
        exposure["recorded_site_observations"] += cell_count
        entropy = normalized_entropy(categories, category_count)
        perturbation_fraction = float(np.mean(categories != perturbed_categories))
        perturbation_peak_fraction = max(perturbation_peak_fraction, perturbation_fraction)
        perturbation_final_fraction = perturbation_fraction
        digest = state_digest(categories)
        if repeated_state_tick is None and digest in seen:
            repeated_state_tick = tick
        seen.setdefault(digest, tick)

        spatial_sample = tick % spatial_every == 0 or tick == recorded_steps
        if spatial_sample:
            local_mi, baseline_mi, excess_mi = spatial_information(
                categories, offsets, category_count
            )
            compression = compressibility_ratio(categories)
        else:
            local_mi = baseline_mi = excess_mi = compression = None
        trajectory.append(
            {
                "tick": tick,
                "normalized_state_entropy": entropy,
                "categorical_turnover": turnover,
                "neighbor_mutual_information": local_mi,
                "permuted_baseline_mutual_information": baseline_mi,
                "excess_neighbor_mutual_information": excess_mi,
                "compressibility_ratio": compression,
                "perturbation_fraction": perturbation_fraction,
                "active_categories": int(np.unique(categories).size),
                "state_sha256": digest,
            }
        )
        previous_categories = categories
        max_rss = max(max_rss, current_rss_mb())

    post = trajectory[min(burn_in, len(trajectory)) :]
    turnovers = [float(row["categorical_turnover"]) for row in post]
    sampled_post = [
        row for row in post if row["excess_neighbor_mutual_information"] is not None
    ]
    outcomes: dict[str, Any] = {
        "normalized_state_entropy_post_burn": mean_or_zero(
            float(row["normalized_state_entropy"]) for row in post
        ),
        "categorical_turnover_post_burn": mean_or_zero(turnovers),
        "neighbor_mutual_information_post_burn": mean_or_zero(
            float(row["neighbor_mutual_information"]) for row in sampled_post
        ),
        "permuted_baseline_mutual_information_post_burn": mean_or_zero(
            float(row["permuted_baseline_mutual_information"]) for row in sampled_post
        ),
        "excess_neighbor_mutual_information_post_burn": mean_or_zero(
            float(row["excess_neighbor_mutual_information"]) for row in sampled_post
        ),
        "compressibility_ratio_post_burn": mean_or_zero(
            float(row["compressibility_ratio"]) for row in sampled_post
        ),
        "activity_persistence_ratio": persistence_ratio(turnovers),
        "perturbation_initial_fraction": initial_perturbation_fraction,
        "perturbation_peak_fraction": perturbation_peak_fraction,
        "perturbation_final_fraction": perturbation_final_fraction,
        "perturbation_response_gain": perturbation_peak_fraction
        / initial_perturbation_fraction,
        "unique_state_fraction": len(seen) / (recorded_steps + 1),
        "repeated_state_tick": repeated_state_tick,
    }
    outcomes["regime"] = classify_regime(outcomes, classifier)
    outcomes["candidate_regime"] = outcomes["regime"] == "active_structured_candidate"

    return {
        "schema": SCHEMA_EPISODE,
        "split": split,
        "seed": seed,
        "experimental_unit": "one independently initialized periodic lattice world",
        "condition": {
            "family": family,
            "profile": str(profile["name"]),
            "profile_kind": str(profile["kind"]),
            "profile_parameters": dict(profile),
            "dimension": dimension,
            "side": side,
            "cell_count": cell_count,
            "boundary": "periodic_torus",
            "neighborhood": "degree_matched_12",
            "degree": len(offsets),
            "recorded_steps": recorded_steps,
            "solver_steps_per_record": solver_steps_per_record,
            "solver_steps": recorded_steps * solver_steps_per_record,
            "burn_in_recorded_steps": burn_in,
            "category_count": category_count,
            "initialization": initialization,
        },
        "exposure": exposure,
        "outcomes": outcomes,
        "trajectory": trajectory,
        "provenance": {
            "initial_state_sha256": initial_digest,
            "final_state_sha256": state_digest(categories),
            "trajectory_sha256": canonical_sha256(trajectory),
            "rng": "numpy.default_rng(seed) at initialization only; synchronous updates deterministic",
            "runtime_seconds": time.monotonic() - started,
            "max_rss_mb": max_rss,
        },
    }


def parse_splits(value: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(SPLITS)
    result = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in result if item not in SPLITS]
    if not result or unknown:
        raise ValueError(f"unknown or empty split selection: {unknown}")
    return result


def condition_specs(
    manifest: Mapping[str, Any], split: str, smoke: bool = False
) -> list[dict[str, Any]]:
    design = manifest["design"]
    dimensions = [int(value) for value in design["dimensions"]]
    if smoke:
        dimensions = dimensions[:1]
    specs: list[dict[str, Any]] = []
    for family, profiles in design["profiles"].items():
        for profile in profiles:
            for dimension in dimensions:
                specs.append(
                    {
                        "family": str(family),
                        "profile": dict(profile),
                        "dimension": dimension,
                        "side": int(design["sides_by_split"][split][str(dimension)]),
                    }
                )
    return specs


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    maximum_iterations = 200
    epsilon = 3.0e-14
    tiny = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    result = d
    for iteration in range(1, maximum_iterations + 1):
        twice = 2 * iteration
        coefficient = iteration * (b - iteration) * x / (
            (qam + twice) * (a + twice)
        )
        d = 1.0 + coefficient * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        result *= d * c
        coefficient = -(a + iteration) * (qab + iteration) * x / (
            (a + twice) * (qap + twice)
        )
        d = 1.0 + coefficient * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) < epsilon:
            break
    return result


def regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def beta_quantile(probability: float, a: float, b: float) -> float:
    low, high = 0.0, 1.0
    for _ in range(80):
        middle = (low + high) / 2.0
        if regularized_beta(middle, a, b) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def jeffreys_interval(successes: int, trials: int) -> list[float]:
    if trials <= 0:
        return [0.0, 1.0]
    a = successes + 0.5
    b = trials - successes + 0.5
    return [beta_quantile(0.025, a, b), beta_quantile(0.975, a, b)]


def bootstrap_mean_interval(values: Sequence[float], seed: int) -> list[float | None]:
    if not values:
        return [None, None]
    if len(values) == 1:
        return [float(values[0]), float(values[0])]
    array = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    estimates = np.mean(rng.choice(array, size=(2000, len(array)), replace=True), axis=1)
    return [float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))]


def family_regime_mutual_information(rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    joint = Counter(
        (str(row["condition"]["family"]), str(row["outcomes"]["regime"])) for row in rows
    )
    family_counts = Counter(str(row["condition"]["family"]) for row in rows)
    regime_counts = Counter(str(row["outcomes"]["regime"]) for row in rows)
    total = float(len(rows))
    information = 0.0
    for (family, regime), count in joint.items():
        probability = count / total
        expected = family_counts[family] * regime_counts[regime] / (total * total)
        information += probability * math.log2(probability / expected)
    return information


def ranges_overlap(left: Sequence[float], right: Sequence[float]) -> bool | None:
    if not left or not right:
        return None
    return max(min(left), min(right)) <= min(max(left), max(right))


def summarize(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        condition = row["condition"]
        key = (
            row["split"],
            condition["family"],
            condition["profile"],
            condition["profile_kind"],
            condition["dimension"],
            condition["side"],
        )
        groups[key].append(row)

    metric_names = [
        "normalized_state_entropy_post_burn",
        "categorical_turnover_post_burn",
        "excess_neighbor_mutual_information_post_burn",
        "activity_persistence_ratio",
        "perturbation_response_gain",
        "compressibility_ratio_post_burn",
    ]
    condition_summaries: list[dict[str, Any]] = []
    for group_index, (key, group) in enumerate(sorted(groups.items())):
        split, family, profile, kind, dimension, side = key
        successes = sum(bool(row["outcomes"]["candidate_regime"]) for row in group)
        regime_counts = Counter(str(row["outcomes"]["regime"]) for row in group)
        metric_summary: dict[str, Any] = {}
        for metric_index, metric in enumerate(metric_names):
            values = [float(row["outcomes"][metric]) for row in group]
            metric_summary[metric] = {
                "mean": float(statistics.mean(values)),
                "median": float(statistics.median(values)),
                "bootstrap_95": bootstrap_mean_interval(
                    values, 370001 + 97 * group_index + metric_index
                ),
            }
        condition_summaries.append(
            {
                "split": split,
                "family": family,
                "profile": profile,
                "profile_kind": kind,
                "dimension": int(dimension),
                "side": int(side),
                "cell_count": int(side) ** int(dimension),
                "episodes": len(group),
                "candidate_count": successes,
                "candidate_occupancy": successes / len(group),
                "candidate_occupancy_jeffreys_95": jeffreys_interval(successes, len(group)),
                "regime_counts": dict(sorted(regime_counts.items())),
                "metrics": metric_summary,
                "runtime_seconds_mean": float(
                    statistics.mean(float(row["provenance"]["runtime_seconds"]) for row in group)
                ),
                "max_rss_mb": max(float(row["provenance"]["max_rss_mb"]) for row in group),
            }
        )

    split_analysis: dict[str, Any] = {}
    for split in SPLITS:
        split_rows = [row for row in rows if row["split"] == split]
        cells = [row for row in condition_summaries if row["split"] == split]
        by_profile: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for cell in cells:
            by_profile[(cell["family"], cell["profile"])].append(cell)
        aggregated_profile_occupancies = [
            sum(cell["candidate_count"] for cell in profile_cells)
            / sum(cell["episodes"] for cell in profile_cells)
            for profile_cells in by_profile.values()
        ]
        dimension_ranges = [
            max(cell["candidate_occupancy"] for cell in profile_cells)
            - min(cell["candidate_occupancy"] for cell in profile_cells)
            for profile_cells in by_profile.values()
            if len(profile_cells) > 1
        ]
        profile_range = (
            max(aggregated_profile_occupancies) - min(aggregated_profile_occupancies)
            if aggregated_profile_occupancies
            else 0.0
        )
        dimension_range_mean = mean_or_zero(dimension_ranges)
        prior_rows = [
            row for row in split_rows if row["condition"]["profile_kind"] == "literature_informed"
        ]
        control_rows = [
            row
            for row in split_rows
            if row["condition"]["profile_kind"]
            in {"null_static", "null_churn", "mechanism_limit", "simple_limit"}
        ]
        prior_successes = sum(bool(row["outcomes"]["candidate_regime"]) for row in prior_rows)
        control_successes = sum(
            bool(row["outcomes"]["candidate_regime"]) for row in control_rows
        )
        split_analysis[split] = {
            "family_regime_mutual_information_bits": family_regime_mutual_information(split_rows),
            "profile_candidate_occupancy_range": profile_range,
            "mean_within_profile_dimension_occupancy_range": dimension_range_mean,
            "profile_vs_dimension_occupancy_range_ratio": (
                profile_range / max(dimension_range_mean, 1.0e-9)
                if profile_range > 0.0
                else 0.0
            ),
            "literature_prior_candidate_occupancy": (
                prior_successes / len(prior_rows) if prior_rows else 0.0
            ),
            "literature_prior_candidate_jeffreys_95": jeffreys_interval(
                prior_successes, len(prior_rows)
            ),
            "control_candidate_occupancy": (
                control_successes / len(control_rows) if control_rows else 0.0
            ),
            "control_candidate_jeffreys_95": jeffreys_interval(
                control_successes, len(control_rows)
            ),
            "literature_prior_minus_control": (
                prior_successes / len(prior_rows) if prior_rows else 0.0
            )
            - (control_successes / len(control_rows) if control_rows else 0.0),
        }

    confirmatory_holdout = [
        row for row in rows if row["split"] in {"confirmatory", "holdout"}
    ]
    candidate_rows = [row for row in confirmatory_holdout if row["outcomes"]["candidate_regime"]]
    negative_rows = [
        row
        for row in confirmatory_holdout
        if row["condition"]["profile_kind"] in {"null_static", "null_churn"}
    ]
    goodhart_audit = {
        "candidate_vs_negative_entropy_ranges_overlap": ranges_overlap(
            [float(row["outcomes"]["normalized_state_entropy_post_burn"]) for row in candidate_rows],
            [float(row["outcomes"]["normalized_state_entropy_post_burn"]) for row in negative_rows],
        ),
        "candidate_vs_negative_turnover_ranges_overlap": ranges_overlap(
            [float(row["outcomes"]["categorical_turnover_post_burn"]) for row in candidate_rows],
            [float(row["outcomes"]["categorical_turnover_post_burn"]) for row in negative_rows],
        ),
        "static_controls_with_diversity": sum(
            row["condition"]["profile_kind"] == "null_static"
            and float(row["outcomes"]["normalized_state_entropy_post_burn"]) >= 0.08
            for row in confirmatory_holdout
        ),
        "churn_controls_with_high_entropy_and_turnover": sum(
            row["condition"]["profile_kind"] == "null_churn"
            and float(row["outcomes"]["normalized_state_entropy_post_burn"]) >= 0.50
            and float(row["outcomes"]["categorical_turnover_post_burn"]) >= 0.80
            for row in confirmatory_holdout
        ),
        "negative_controls_passing_conjunction": sum(
            row["condition"]["profile_kind"] in {"null_static", "null_churn"}
            and bool(row["outcomes"]["candidate_regime"])
            for row in confirmatory_holdout
        ),
    }

    confirm = split_analysis.get("confirmatory", {})
    holdout = split_analysis.get("holdout", {})
    h1_supported = bool(confirm and holdout) and all(
        part["literature_prior_minus_control"] > 0.0
        and part["control_candidate_occupancy"] == 0.0
        for part in (confirm, holdout)
    )
    h2_supported = bool(confirm and holdout) and all(
        part["family_regime_mutual_information_bits"] > 0.05 for part in (confirm, holdout)
    )
    h3_supported = bool(confirm and holdout) and all(
        part["profile_vs_dimension_occupancy_range_ratio"] > 1.0
        for part in (confirm, holdout)
    )
    h4_supported = (
        goodhart_audit["static_controls_with_diversity"] > 0
        and goodhart_audit["churn_controls_with_high_entropy_and_turnover"] > 0
        and goodhart_audit["negative_controls_passing_conjunction"] == 0
    )
    hypothesis_assessment = {
        "H1_literature_prior_enrichment": {
            "status": "supported_within_sample" if h1_supported else "not_supported",
            "evidence": {
                split: {
                    "prior": split_analysis.get(split, {}).get(
                        "literature_prior_candidate_occupancy"
                    ),
                    "control": split_analysis.get(split, {}).get(
                        "control_candidate_occupancy"
                    ),
                }
                for split in ("confirmatory", "holdout")
            },
        },
        "H2_substrate_specific_distribution": {
            "status": "supported_within_sample" if h2_supported else "not_supported",
            "evidence": {
                split: split_analysis.get(split, {}).get(
                    "family_regime_mutual_information_bits"
                )
                for split in ("confirmatory", "holdout")
            },
        },
        "H3_dimension_below_physics": {
            "status": "supported_within_sample" if h3_supported else "not_supported",
            "evidence": {
                split: split_analysis.get(split, {}).get(
                    "profile_vs_dimension_occupancy_range_ratio"
                )
                for split in ("confirmatory", "holdout")
            },
        },
        "H4_metric_goodhart_controls": {
            "status": "supported_within_sample" if h4_supported else "not_supported",
            "evidence": goodhart_audit,
        },
    }
    exposure_audit = {
        "episodes": len(rows),
        "episodes_with_full_solver_exposure": sum(
            int(row["exposure"]["solver_site_evaluations"])
            == int(row["condition"]["cell_count"]) * int(row["condition"]["solver_steps"])
            for row in rows
        ),
        "episodes_with_recorded_state_change": sum(
            int(row["exposure"]["records_with_state_change"]) > 0 for row in rows
        ),
        "episodes_with_visible_initial_perturbation": sum(
            float(row["outcomes"]["perturbation_initial_fraction"]) > 0.0 for row in rows
        ),
    }
    return {
        "schema": SCHEMA_SUMMARY,
        "row_count": len(rows),
        "condition_count": len(condition_summaries),
        "episode_counts": {
            split: sum(row["split"] == split for row in rows) for split in SPLITS
        },
        "regime_classifier": manifest["analysis"]["regime_classifier"],
        "condition_summaries": condition_summaries,
        "split_analysis": split_analysis,
        "goodhart_audit": goodhart_audit,
        "hypothesis_assessment": hypothesis_assessment,
        "exposure_audit": exposure_audit,
        "claim_boundary": (
            "Regime labels are operational descriptions of the declared deterministic lattice "
            "families, parameter points, sizes, categorizations, horizons, and thresholds. "
            "They are not organism detections, open-endedness evidence, biological claims, or "
            "a universal complexity law."
        ),
    }


def write_phase_map(path: Path, summary: Mapping[str, Any]) -> None:
    fieldnames = [
        "split",
        "family",
        "profile",
        "profile_kind",
        "dimension",
        "side",
        "cell_count",
        "episodes",
        "candidate_count",
        "candidate_occupancy",
        "candidate_occupancy_jeffreys_95",
        "entropy_mean",
        "turnover_mean",
        "excess_mi_mean",
        "persistence_mean",
        "perturbation_gain_mean",
        "compressibility_mean",
        "regime_counts",
        "runtime_seconds_mean",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["condition_summaries"]:
            metrics = row["metrics"]
            writer.writerow(
                {
                    **{key: row[key] for key in fieldnames[:11]},
                    "entropy_mean": metrics["normalized_state_entropy_post_burn"]["mean"],
                    "turnover_mean": metrics["categorical_turnover_post_burn"]["mean"],
                    "excess_mi_mean": metrics[
                        "excess_neighbor_mutual_information_post_burn"
                    ]["mean"],
                    "persistence_mean": metrics["activity_persistence_ratio"]["mean"],
                    "perturbation_gain_mean": metrics["perturbation_response_gain"]["mean"],
                    "compressibility_mean": metrics["compressibility_ratio_post_burn"]["mean"],
                    "regime_counts": json.dumps(row["regime_counts"], sort_keys=True),
                    "runtime_seconds_mean": row["runtime_seconds_mean"],
                }
            )


def build_knowledge_card(summary: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    regime_counts = Counter()
    for row in summary["condition_summaries"]:
        regime_counts.update(row["regime_counts"])
    split_lines = []
    for split in SPLITS:
        analysis = summary["split_analysis"].get(split, {})
        split_lines.append(
            f"- {split}: prior occupancy {analysis.get('literature_prior_candidate_occupancy', 0):.3f}, "
            f"control occupancy {analysis.get('control_candidate_occupancy', 0):.3f}, "
            f"I(family; regime) {analysis.get('family_regime_mutual_information_bits', 0):.3f} bits, "
            f"profile/dimension range ratio {analysis.get('profile_vs_dimension_occupancy_range_ratio', 0):.3f}."
        )
    hypothesis_lines = [
        f"- {name}: **{assessment['status']}**."
        for name, assessment in summary["hypothesis_assessment"].items()
    ]
    return f"""# Alternative-Physics ALife Atlas Knowledge Card

## Observed

- {summary['row_count']} independently initialized episodes populated {summary['condition_count']} split-condition cells.
- Regime counts were: {json.dumps(dict(sorted(regime_counts.items())), sort_keys=True)}.
{chr(10).join(split_lines)}
- The exposure audit found {summary['exposure_audit']['episodes_with_full_solver_exposure']} / {summary['row_count']} episodes with the exact declared site-step denominator.
- Exact sampled replay passed: {summary['determinism']['passed']}. Wall time was {receipt['wall_seconds']:.2f} seconds and maximum process RSS was {receipt['max_rss_mb']:.2f} MB.

## Hypothesis Assessment

{chr(10).join(hypothesis_lines)}

## Inferred

Within this bounded atlas, the empirical distribution is a discrete measure over the six-axis episode vector (entropy, turnover, excess spatial mutual information, activity persistence, perturbation gain, and regime occupancy). Family and parameter profile are useful coordinates only where their fresh-seed occupancy and uncertainty support the distinction. Dimension is interpreted under the fixed-degree-12 construction and approximately matched cell counts, not as a universal geometric law.

## Not Supported

- The candidate label does not identify organisms, agency, evolution, adaptation, or open-endedness.
- No scalar "complexity" score is accepted. Entropy, turnover, and compression remain diagnostics when viewed alone.
- No biological, chemical-laboratory, cognitive, or external validity is claimed.
- Absence from one sampled condition is not proof of impossibility elsewhere in parameter space.

## Goodhart Audit

`{json.dumps(summary['goodhart_audit'], sort_keys=True)}`

Static and global-churn controls were retained specifically to test whether state diversity, entropy, or turnover can manufacture a false candidate pass. The multi-axis conjunction was frozen before execution.

## Confounds

- Fixed degree requires longer-range and anisotropic offsets in lower dimensions.
- Equal cell counts are exact for the discovery/confirmatory shapes and approximate in holdout.
- Gray-Scott fields are discretized into 64 joint concentration bins for cross-family metrics; this can hide sub-bin dynamics.
- The finite horizons can classify slowly developing patterns as static or transient.
- Only two literature-informed profiles per physics family were sampled; this is an atlas slice, not an exhaustive phase diagram.

## Artifacts and Replay

- `frozen_manifest.json`
- `raw_episodes.jsonl`
- `summary.json`
- `phase_map.csv`
- `seed_manifest.json`
- `receipt.json`
- `hashes.json`
- Replay: `{receipt['replay_command']}`

## Next Experiment

Refine only reproducible transitions in the phase map with fresh seeds and intermediate parameters. Add a second fixed-degree offset construction before attributing a difference to dimension, and extend horizon before declaring a slow chemistry regime absent.
"""


def deterministic_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    projected = json.loads(json.dumps(row))
    projected["provenance"].pop("runtime_seconds", None)
    projected["provenance"].pop("max_rss_mb", None)
    return projected


def git_commit(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


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
    geometry_path = code_path.with_name("geometry_averaging_experiment.py")
    root = code_path.parents[1]
    budget = manifest["budget"]
    deadline = time.monotonic() + float(budget["max_wall_seconds"])
    max_ram_mb = float(budget["max_ram_mb"])
    splits = parse_splits(args.splits)
    started_utc = utc_now()
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    status = "ok"
    stop_reason = "completed_declared_splits"
    max_rss = current_rss_mb()
    seeds_by_split = {
        split: ([manifest["seed_plan"][split][0]] if args.smoke else manifest["seed_plan"][split])
        for split in splits
    }
    planned = sum(
        len(seeds_by_split[split]) * len(condition_specs(manifest, split, args.smoke))
        for split in splits
    )
    if planned > int(budget["max_episodes"]):
        raise SystemExit(
            f"planned episodes {planned} exceed max_episodes {budget['max_episodes']}"
        )

    design = manifest["design"]
    classifier = manifest["analysis"]["regime_classifier"]
    determinism: dict[str, Any] = {"performed": False, "passed": None, "samples": []}
    try:
        with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as raw_handle:
            for split in splits:
                recorded_steps = int(design["recorded_steps_by_split"][split])
                if args.smoke:
                    recorded_steps = min(8, recorded_steps)
                burn_in = min(int(design["burn_in_recorded_steps"]), max(1, recorded_steps // 3))
                for seed in seeds_by_split[split]:
                    for spec in condition_specs(manifest, split, args.smoke):
                        cells = int(spec["side"] ** spec["dimension"])
                        family = str(spec["family"])
                        solver_steps_per_record = int(
                            design["solver_steps_per_record_by_family"][family]
                        )
                        solver_steps = recorded_steps * solver_steps_per_record
                        if cells > int(budget["max_cells_per_world"]):
                            raise RuntimeError(f"cell cap exceeded: {spec}")
                        if solver_steps > int(budget["max_steps_per_episode"]):
                            raise RuntimeError(f"solver-step cap exceeded: {spec}")
                        row = run_episode(
                            split=split,
                            seed=int(seed),
                            **spec,
                            matched_degree=int(design["matched_degree"]),
                            recorded_steps=recorded_steps,
                            solver_steps_per_record=solver_steps_per_record,
                            burn_in=burn_in,
                            spatial_every=int(design["spatial_metric_every_recorded_steps"]),
                            classifier=classifier,
                            deadline=deadline,
                            max_ram_mb=max_ram_mb,
                        )
                        rows.append(row)
                        raw_handle.write(json.dumps(row, sort_keys=True) + "\n")
                        raw_handle.flush()
                        max_rss = max(max_rss, float(row["provenance"]["max_rss_mb"]))

        if not args.skip_determinism:
            samples: list[dict[str, Any]] = []
            for family in ("binary_ca", "gray_scott", "cyclic_ca"):
                original = next(row for row in rows if row["condition"]["family"] == family)
                condition = original["condition"]
                replay = run_episode(
                    split=str(original["split"]),
                    seed=int(original["seed"]),
                    family=family,
                    profile=condition["profile_parameters"],
                    dimension=int(condition["dimension"]),
                    side=int(condition["side"]),
                    matched_degree=int(design["matched_degree"]),
                    recorded_steps=int(condition["recorded_steps"]),
                    solver_steps_per_record=int(condition["solver_steps_per_record"]),
                    burn_in=int(condition["burn_in_recorded_steps"]),
                    spatial_every=int(design["spatial_metric_every_recorded_steps"]),
                    classifier=classifier,
                    deadline=deadline,
                    max_ram_mb=max_ram_mb,
                )
                original_hash = canonical_sha256(deterministic_projection(original))
                replay_hash = canonical_sha256(deterministic_projection(replay))
                samples.append(
                    {
                        "family": family,
                        "split": original["split"],
                        "seed": original["seed"],
                        "original_sha256": original_hash,
                        "replay_sha256": replay_hash,
                        "passed": original_hash == replay_hash,
                    }
                )
            determinism = {
                "performed": True,
                "passed": all(sample["passed"] for sample in samples),
                "samples": samples,
            }
            if not determinism["passed"]:
                raise RuntimeError("sampled exact replay failed")
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
            "planned_episodes": planned,
            "completed_episodes": len(rows),
        },
    )
    shutil.copy2(manifest_path, output / "frozen_manifest.json")

    wall_seconds = time.monotonic() - started
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "schema": SCHEMA_RECEIPT,
        "status": status,
        "stop_reason": stop_reason,
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": wall_seconds,
        "max_rss_mb": max_rss,
        "episode_count": len(rows),
        "condition_count": summary["condition_count"],
        "code_path": str(code_path),
        "code_sha256": sha256_file(code_path),
        "geometry_dependency_path": str(geometry_path),
        "geometry_dependency_sha256": sha256_file(geometry_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        **environment,
        "environment_sha256": canonical_sha256(environment),
        "git_commit_at_run": git_commit(root),
        "output_path": str(output),
        "determinism": determinism,
        "replay_command": (
            f"python src/alt_physics_atlas.py --manifest {manifest_path} "
            f"--output {output} --splits {','.join(splits)}"
        ),
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(
        build_knowledge_card(summary, receipt), encoding="utf-8"
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
            name: {
                "sha256": sha256_file(output / name),
                "bytes": (output / name).stat().st_size,
            }
            for name in artifact_names
            if (output / name).is_file()
        },
    )
    total_bytes = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        raise SystemExit("artifact directory exceeded declared disk budget")
    print(
        json.dumps(
            {
                "output": str(output),
                "status": status,
                "episodes": len(rows),
                "conditions": summary["condition_count"],
                "wall_seconds": wall_seconds,
                "determinism": determinism["passed"],
            },
            indent=2,
        )
    )
    raise SystemExit(0 if status == "ok" else 1)


if __name__ == "__main__":
    main()
