#!/usr/bin/env python3
"""Deterministic Pixie sanctuary prototype over three physics-native critters."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import psutil

from alt_physics_atlas import (
    advance_state,
    bootstrap_mean_interval,
    canonical_sha256,
    categories_for,
    check_budget,
    current_rss_mb,
    git_commit,
    initialize_states,
    jeffreys_interval,
    normalized_entropy,
    sha256_file,
    state_digest,
    utc_now,
    write_json,
)
from geometry_averaging_experiment import degree_matched_offsets, neighbor_counts


SCHEMA_EPISODE = "alife.pixie_sanctuary.episode.v1"
SCHEMA_EVENT = "alife.pixie_sanctuary.event.v1"
SCHEMA_SUMMARY = "alife.pixie_sanctuary.summary.v1"
SCHEMA_RECEIPT = "alife.pixie_sanctuary.receipt.v1"
SPLITS = ("discovery", "confirmatory", "holdout")


def mean_or_zero(values: Iterable[float]) -> float:
    materialized = list(values)
    return float(statistics.mean(materialized)) if materialized else 0.0


def copy_state(family: str, state: Any) -> Any:
    if family == "gray_scott":
        return tuple(field.copy() for field in state)
    return state.copy()


def assign_mask(family: str, target: Any, source: Any, mask: np.ndarray) -> None:
    if family == "gray_scott":
        for target_field, source_field in zip(target, source):
            target_field[mask] = source_field[mask]
    else:
        target[mask] = source[mask]


def differing_sites(family: str, left: Any, right: Any) -> np.ndarray:
    """Return exact per-site substrate differences, before display binning."""

    if family == "gray_scott":
        return np.logical_or.reduce(
            [left_field != right_field for left_field, right_field in zip(left, right)]
        )
    return left != right


def torus_manhattan(shape: Sequence[int], center: Sequence[int]) -> np.ndarray:
    distance = np.zeros(tuple(shape), dtype=np.int16)
    for axis, (side, origin) in enumerate(zip(shape, center)):
        coordinate_shape = [1] * len(shape)
        coordinate_shape[axis] = side
        coordinates = np.arange(side, dtype=np.int16).reshape(coordinate_shape)
        delta = np.abs(coordinates - int(origin))
        distance += np.minimum(delta, side - delta)
    return distance


def action_mask(
    shape: Sequence[int], center: Sequence[int], action: str
) -> np.ndarray:
    distance = torus_manhattan(shape, center)
    if action == "observe":
        return distance == 0
    if action == "touch":
        return distance <= 1
    if action == "sing":
        return distance == 2
    if action in {"feed", "cool", "shield"}:
        return distance <= 2
    raise ValueError(f"unknown Pixie action: {action}")


def gray_neighbor_average(
    field: np.ndarray, offsets: Sequence[Sequence[int]]
) -> np.ndarray:
    axes = tuple(range(field.ndim))
    result = np.zeros(field.shape, dtype=np.float32)
    for offset in offsets:
        result += np.roll(field, shift=tuple(offset), axis=axes)
    return result / np.float32(len(offsets))


def apply_pixie_action(
    *,
    family: str,
    state: Any,
    profile: Mapping[str, Any],
    action: str,
    mask: np.ndarray,
    offsets: Sequence[Sequence[int]],
) -> tuple[Any, int, dict[str, Any]]:
    before_categories, _ = categories_for(family, state, profile)
    next_state = copy_state(family, state)
    details: dict[str, Any] = {"mask_sites": int(mask.sum())}
    if action in {"observe", "shield"}:
        details["operation"] = "no_immediate_state_change"
    elif family == "binary_ca":
        if action in {"touch", "sing"}:
            next_state[mask] = ~next_state[mask]
            details["operation"] = "toggle"
        elif action == "feed":
            next_state[mask] = True
            details["operation"] = "set_alive"
        elif action == "cool":
            counts = neighbor_counts(next_state, offsets)
            next_state[mask] = counts[mask] >= math.ceil(len(offsets) / 2)
            details["operation"] = "local_majority"
    elif family == "cyclic_ca":
        states = int(profile["states"])
        if action in {"touch", "sing", "feed"}:
            amount = 2 if action == "feed" else 1
            next_state[mask] = (next_state[mask] + amount) % states
            details.update({"operation": "phase_advance", "phase_steps": amount})
        elif action == "cool":
            values = next_state[mask]
            mode = int(np.argmax(np.bincount(values, minlength=states)))
            next_state[mask] = mode
            details.update({"operation": "phase_consensus", "target_phase": mode})
    else:
        u, v = next_state
        if action == "touch":
            bins = np.minimum((v[mask] * np.float32(8.0)).astype(np.int16), 7)
            target_bins = np.minimum(bins + 1, 7)
            v[mask] = ((target_bins.astype(np.float32) + 0.5) / 8.0).astype(
                np.float32
            )
            details["operation"] = "v_next_bin"
        elif action == "sing":
            v[mask] = np.clip(v[mask] + np.float32(0.0625), 0.0, 1.0)
            details["operation"] = "v_ring_pulse"
        elif action == "feed":
            u[mask] = np.clip(u[mask] + np.float32(0.25), 0.0, 1.0)
            v[mask] = np.clip(v[mask] + np.float32(0.05), 0.0, 1.0)
            details["operation"] = "uv_feed_injection"
        elif action == "cool":
            mean_u = gray_neighbor_average(u, offsets)
            mean_v = gray_neighbor_average(v, offsets)
            u[mask] = mean_u[mask]
            v[mask] = mean_v[mask]
            details["operation"] = "local_diffusive_average"
    after_categories, _ = categories_for(family, next_state, profile)
    changed = int(np.count_nonzero(before_categories != after_categories))
    return next_state, changed, details


def neighbor_agreement(
    categories: np.ndarray, offsets: Sequence[Sequence[int]]
) -> float:
    axes = tuple(range(categories.ndim))
    return mean_or_zero(
        float(np.mean(categories == np.roll(categories, shift=tuple(offset), axis=axes)))
        for offset in offsets
    )


def component_count(mask: np.ndarray) -> int:
    if mask.ndim != 2:
        raise ValueError("the Pixie sanctuary v1 component diagnostic is two-dimensional")
    side_y, side_x = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    count = 0
    for y, x in np.argwhere(mask):
        y = int(y)
        x = int(x)
        if visited[y, x]:
            continue
        count += 1
        stack = [(y, x)]
        visited[y, x] = True
        while stack:
            cy, cx = stack.pop()
            for ny, nx in (
                ((cy - 1) % side_y, cx),
                ((cy + 1) % side_y, cx),
                (cy, (cx - 1) % side_x),
                (cy, (cx + 1) % side_x),
            ):
                if mask[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    stack.append((ny, nx))
    return count


def active_mask(critter: str, categories: np.ndarray) -> np.ndarray:
    if critter == "bitlichen":
        return categories == 1
    if critter == "mitosis_moss":
        return categories % 8 >= 1
    # Prism components are color-domain components; phase zero is an arbitrary
    # but deterministic slice used only as a morphology diagnostic.
    return categories == 0


def render_categories(critter: str, categories: np.ndarray) -> str:
    palettes = {
        "bitlichen": " #",
        "prism_wyrm": "012345",
        "mitosis_moss": " .,:;ox%#",
    }
    palette = palettes[critter]
    if critter == "mitosis_moss":
        display = categories % 8
    else:
        display = categories
    return "\n".join(
        "".join(palette[min(int(value), len(palette) - 1)] for value in row)
        for row in display
    )


def response_class(
    *,
    peak: float,
    tail: float,
    localization: float,
    reach: int,
    side: int,
    component_delta: int,
    treated_final_entropy: float,
    comparator_final_entropy: float,
    thresholds: Mapping[str, Any],
) -> str:
    if peak < float(thresholds["visible_peak_min"]):
        return "no_visible_response"
    if peak >= float(thresholds["globalized_peak_min"]):
        return "globalized_response"
    if treated_final_entropy < 0.02 <= comparator_final_entropy:
        return "collapse"
    if tail / max(peak, 1e-12) <= float(thresholds["recovered_tail_over_peak_max"]):
        return "transient_recovery"
    if abs(component_delta) >= 2:
        return "morphology_change"
    if localization >= float(thresholds["localized_fraction_min"]):
        return "localized_memory"
    if reach >= max(2, side // 4):
        return "propagating_wave"
    return "morphology_change"


def event(
    *,
    episode_id: str,
    tick: int,
    event_type: str,
    pixie: Mapping[str, Any],
    critter: str,
    action: str,
    center: Sequence[int],
    details: Mapping[str, Any],
    cause: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_EVENT,
        "event_id": f"{episode_id}:event:{tick:04d}:{event_type}",
        "episode_id": episode_id,
        "tick": tick,
        "event_type": event_type,
        "pixie": {"id": pixie["id"], "display_name": pixie["display_name"]},
        "critter": {"id": f"{episode_id}:critter", "species": critter},
        "action": action,
        "position": [int(value) for value in center],
        "details": dict(details),
        "cause": list(cause or []),
    }


def run_episode(
    *,
    split: str,
    seed: int,
    critter: str,
    action: str,
    profile: Mapping[str, Any],
    side: int,
    steps: int,
    solver_steps_per_record: int,
    action_ticks: Sequence[int],
    shield_duration: int,
    matched_degree: int,
    tail_ticks: int,
    thresholds: Mapping[str, Any],
    pixie: Mapping[str, Any],
    deadline: float,
    max_ram_mb: float,
    render_every: int = 0,
) -> dict[str, Any]:
    started = time.monotonic()
    family = str(profile["family"])
    shape = (side, side)
    center = (side // 2, side // 2)
    offsets = degree_matched_offsets(2, matched_degree)
    initialized, _, initialization = initialize_states(
        family, profile, shape, seed
    )
    treated = copy_state(family, initialized)
    comparator = copy_state(family, initialized)
    initial_categories, category_count = categories_for(family, initialized, profile)
    initial_digest = state_digest(initial_categories)
    episode_id = f"pixie-{split}-{seed}-{critter}-{action}"
    action_ticks_set = {int(value) for value in action_ticks}
    action_mask_value = action_mask(shape, center, action)
    local_mask = torus_manhattan(shape, center) <= 6
    shield_mask = action_mask(shape, center, "shield")
    shield_until = -1
    shield_origin = -1
    successful_action_ticks: set[int] = set()
    events: list[dict[str, Any]] = []
    trajectory: list[dict[str, Any]] = []
    treated_seen = {initial_digest}
    max_rss = current_rss_mb()
    exposure = {
        "eligible_action_opportunities": len(action_ticks),
        "action_attempts": 0,
        "action_activations": 0,
        "successful_action_ticks": 0,
        "immediate_action_changed_sites": 0,
        "shield_prevented_site_steps": 0,
        "treated_solver_site_evaluations": 0,
        "comparator_solver_site_evaluations": 0,
    }
    if render_every:
        print(f"\n{episode_id} tick=0")
        print(render_categories(critter, initial_categories))

    for tick in range(1, steps + 1):
        check_budget(deadline, max_ram_mb)
        action_applied = tick in action_ticks_set
        immediate_changed = 0
        if action_applied:
            exposure["action_attempts"] += 1
            exposure["action_activations"] += 1
            treated, immediate_changed, action_details = apply_pixie_action(
                family=family,
                state=treated,
                profile=profile,
                action=action,
                mask=action_mask_value,
                offsets=offsets,
            )
            exposure["immediate_action_changed_sites"] += immediate_changed
            if immediate_changed > 0:
                successful_action_ticks.add(tick)
            if action == "shield":
                shield_until = tick + shield_duration - 1
                shield_origin = tick
                action_details["active_through_tick"] = shield_until
            events.append(
                event(
                    episode_id=episode_id,
                    tick=tick,
                    event_type="pixie_action",
                    pixie=pixie,
                    critter=critter,
                    action=action,
                    center=center,
                    details={
                        **action_details,
                        "changed_sites": immediate_changed,
                        "scheduled_opportunity": True,
                    },
                )
            )

        shield_prevented_this_tick = 0
        for _ in range(solver_steps_per_record):
            treated_before = copy_state(family, treated)
            treated_advanced = advance_state(family, treated, profile, offsets)
            comparator = advance_state(family, comparator, profile, offsets)
            if action == "shield" and tick <= shield_until:
                shield_prevented_this_tick += int(
                    np.count_nonzero(
                        differing_sites(family, treated_advanced, treated_before)
                        & shield_mask
                    )
                )
                assign_mask(family, treated_advanced, treated_before, shield_mask)
            treated = treated_advanced
            exposure["treated_solver_site_evaluations"] += side * side
            exposure["comparator_solver_site_evaluations"] += side * side
        if shield_prevented_this_tick:
            successful_action_ticks.add(shield_origin)
            exposure["shield_prevented_site_steps"] += shield_prevented_this_tick

        treated_categories, category_count = categories_for(family, treated, profile)
        comparator_categories, _ = categories_for(family, comparator, profile)
        divergence = treated_categories != comparator_categories
        divergent_sites = int(divergence.sum())
        divergent_fraction = divergent_sites / (side * side)
        if divergent_sites:
            localization = float(np.count_nonzero(divergence & local_mask) / divergent_sites)
            reach = int(torus_manhattan(shape, center)[divergence].max())
        else:
            localization = 0.0
            reach = 0
        treated_hash = state_digest(treated_categories)
        treated_seen.add(treated_hash)
        trajectory.append(
            {
                "tick": tick,
                "action_applied": action_applied,
                "immediate_action_changed_sites": immediate_changed,
                "shield_prevented_sites": shield_prevented_this_tick,
                "divergent_sites": divergent_sites,
                "divergent_fraction": divergent_fraction,
                "response_localization": localization,
                "response_reach_radius": reach,
                "treated_entropy": normalized_entropy(
                    treated_categories, category_count
                ),
                "comparator_entropy": normalized_entropy(
                    comparator_categories, category_count
                ),
                "neighbor_agreement_delta": neighbor_agreement(
                    treated_categories, offsets
                )
                - neighbor_agreement(comparator_categories, offsets),
                "treated_state_sha256": treated_hash,
                "comparator_state_sha256": state_digest(comparator_categories),
            }
        )
        if render_every and (tick % render_every == 0 or action_applied or tick == steps):
            print(
                f"\n{episode_id} tick={tick} divergence={divergent_fraction:.3f} "
                f"reach={reach}"
            )
            print(render_categories(critter, treated_categories))
        max_rss = max(max_rss, current_rss_mb())

    exposure["successful_action_ticks"] = len(successful_action_ticks)
    divergence_values = [float(row["divergent_fraction"]) for row in trajectory]
    peak_index = int(np.argmax(divergence_values)) if divergence_values else 0
    peak_row = trajectory[peak_index]
    peak = float(peak_row["divergent_fraction"])
    tail = mean_or_zero(divergence_values[-tail_ticks:])
    treated_final_categories, _ = categories_for(family, treated, profile)
    comparator_final_categories, _ = categories_for(family, comparator, profile)
    treated_components = component_count(active_mask(critter, treated_final_categories))
    comparator_components = component_count(
        active_mask(critter, comparator_final_categories)
    )
    component_delta = treated_components - comparator_components
    treated_final_entropy = normalized_entropy(treated_final_categories, category_count)
    comparator_final_entropy = normalized_entropy(
        comparator_final_categories, category_count
    )
    classification = response_class(
        peak=peak,
        tail=tail,
        localization=float(peak_row["response_localization"]),
        reach=int(peak_row["response_reach_radius"]),
        side=side,
        component_delta=component_delta,
        treated_final_entropy=treated_final_entropy,
        comparator_final_entropy=comparator_final_entropy,
        thresholds=thresholds,
    )
    visible_bounded = (
        peak >= float(thresholds["visible_peak_min"])
        and peak < float(thresholds["globalized_peak_min"])
    )
    persistent = visible_bounded and tail >= float(thresholds["persistent_tail_min"])
    globalized = peak >= float(thresholds["globalized_peak_min"])
    events.extend(
        [
            event(
                episode_id=episode_id,
                tick=int(peak_row["tick"]),
                event_type="response_peak",
                pixie=pixie,
                critter=critter,
                action=action,
                center=center,
                details={
                    "divergent_fraction": peak,
                    "localization": peak_row["response_localization"],
                    "reach_radius": peak_row["response_reach_radius"],
                },
                cause=[
                    item["event_id"]
                    for item in events
                    if item["event_type"] == "pixie_action"
                ],
            ),
            event(
                episode_id=episode_id,
                tick=steps,
                event_type="response_classified",
                pixie=pixie,
                critter=critter,
                action=action,
                center=center,
                details={
                    "response_class": classification,
                    "visible_bounded": visible_bounded,
                    "persistent": persistent,
                    "globalized": globalized,
                    "tail_divergent_fraction": tail,
                    "component_count_delta": component_delta,
                },
                cause=[f"{episode_id}:event:{int(peak_row['tick']):04d}:response_peak"],
            ),
        ]
    )
    outcomes = {
        "peak_divergent_fraction": peak,
        "peak_tick": int(peak_row["tick"]),
        "tail_divergent_fraction": tail,
        "response_persistence_ratio": tail / max(peak, 1e-12),
        "response_localization_at_peak": float(peak_row["response_localization"]),
        "response_reach_radius_at_peak": int(peak_row["response_reach_radius"]),
        "component_count_delta": component_delta,
        "neighbor_agreement_delta_at_peak": float(
            peak_row["neighbor_agreement_delta"]
        ),
        "treated_final_entropy": treated_final_entropy,
        "comparator_final_entropy": comparator_final_entropy,
        "treated_unique_state_fraction": len(treated_seen) / (steps + 1),
        "response_class": classification,
        "visible_bounded_response": visible_bounded,
        "persistent_response": persistent,
        "globalized_response": globalized,
        "observe_divergence": action == "observe" and peak > 0.0,
    }
    return {
        "schema": SCHEMA_EPISODE,
        "episode_id": episode_id,
        "split": split,
        "seed": seed,
        "experimental_unit": "one independently seeded paired sanctuary episode",
        "condition": {
            "critter": critter,
            "family": family,
            "profile": str(profile["name"]),
            "action": action,
            "preferred_action": False,
            "side": side,
            "cell_count": side * side,
            "steps": steps,
            "solver_steps_per_record": solver_steps_per_record,
            "matched_degree": matched_degree,
            "boundary": "periodic_sanctuary",
            "action_ticks": list(action_ticks),
            "action_mask_sites": int(action_mask_value.sum()),
            "profile_parameters": dict(profile),
            "initialization": initialization,
        },
        "pixie": dict(pixie),
        "exposure": exposure,
        "outcomes": outcomes,
        "events": events,
        "trajectory": trajectory,
        "provenance": {
            "initial_state_sha256": initial_digest,
            "treated_final_state_sha256": state_digest(treated_final_categories),
            "comparator_final_state_sha256": state_digest(
                comparator_final_categories
            ),
            "trajectory_sha256": canonical_sha256(trajectory),
            "events_sha256": canonical_sha256(events),
            "runtime_seconds": time.monotonic() - started,
            "max_rss_mb": max_rss,
            "rng": "numpy.default_rng(seed) at shared initialization only",
        },
    }


def parse_splits(value: str) -> list[str]:
    if value.lower().strip() == "all":
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
    critters = list(design["critters"])
    actions = list(design["actions"])
    if smoke:
        actions = actions
    return [
        {
            "critter": critter,
            "action": action,
            "profile": dict(design["species_profiles"][critter]),
            "side": int(design["side_by_split"][split]),
            "steps": int(design["steps_by_split"][split]),
            "solver_steps_per_record": int(
                design["solver_steps_per_record"][critter]
            ),
        }
        for critter in critters
        for action in actions
    ]


def mutual_information(rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    joint = Counter(
        (str(row["condition"]["critter"]), str(row["outcomes"]["response_class"]))
        for row in rows
    )
    left = Counter(str(row["condition"]["critter"]) for row in rows)
    right = Counter(str(row["outcomes"]["response_class"]) for row in rows)
    total = float(len(rows))
    return sum(
        count / total
        * math.log2(
            (count / total)
            / ((left[critter] / total) * (right[response] / total))
        )
        for (critter, response), count in joint.items()
    )


def summarize(
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> dict[str, Any]:
    preferred = manifest["design"]["preferred_actions"]
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[
            (
                str(row["split"]),
                str(row["condition"]["critter"]),
                str(row["condition"]["action"]),
            )
        ].append(row)
    condition_summaries: list[dict[str, Any]] = []
    metric_names = [
        "peak_divergent_fraction",
        "tail_divergent_fraction",
        "response_persistence_ratio",
        "response_localization_at_peak",
        "response_reach_radius_at_peak",
        "component_count_delta",
        "neighbor_agreement_delta_at_peak",
    ]
    for index, ((split, critter, action), group) in enumerate(sorted(groups.items())):
        visible = sum(bool(row["outcomes"]["visible_bounded_response"]) for row in group)
        persistent = sum(bool(row["outcomes"]["persistent_response"]) for row in group)
        globalized = sum(bool(row["outcomes"]["globalized_response"]) for row in group)
        metrics: dict[str, Any] = {}
        for metric_index, name in enumerate(metric_names):
            values = [float(row["outcomes"][name]) for row in group]
            metrics[name] = {
                "mean": float(statistics.mean(values)),
                "median": float(statistics.median(values)),
                "bootstrap_95": bootstrap_mean_interval(
                    values, 510001 + index * 31 + metric_index
                ),
            }
        condition_summaries.append(
            {
                "split": split,
                "critter": critter,
                "family": group[0]["condition"]["family"],
                "action": action,
                "preferred_action": preferred[critter] == action,
                "episodes": len(group),
                "visible_bounded_count": visible,
                "visible_bounded_occupancy": visible / len(group),
                "visible_bounded_jeffreys_95": jeffreys_interval(visible, len(group)),
                "persistent_count": persistent,
                "persistent_occupancy": persistent / len(group),
                "persistent_jeffreys_95": jeffreys_interval(persistent, len(group)),
                "globalized_count": globalized,
                "response_class_counts": dict(
                    sorted(Counter(row["outcomes"]["response_class"] for row in group).items())
                ),
                "metrics": metrics,
                "action_attempts": sum(int(row["exposure"]["action_attempts"]) for row in group),
                "successful_action_ticks": sum(
                    int(row["exposure"]["successful_action_ticks"]) for row in group
                ),
            }
        )

    split_analysis: dict[str, Any] = {}
    for split in SPLITS:
        split_rows = [row for row in rows if row["split"] == split]
        preferred_rows = [
            row
            for row in split_rows
            if row["condition"]["action"]
            == preferred[row["condition"]["critter"]]
        ]
        observe_rows = [
            row for row in split_rows if row["condition"]["action"] == "observe"
        ]
        preferred_by_critter: dict[str, Any] = {}
        for critter in preferred:
            critter_rows = [
                row
                for row in preferred_rows
                if row["condition"]["critter"] == critter
            ]
            preferred_by_critter[critter] = {
                "action": preferred[critter],
                "episodes": len(critter_rows),
                "visible_bounded_occupancy": mean_or_zero(
                    1.0 if row["outcomes"]["visible_bounded_response"] else 0.0
                    for row in critter_rows
                ),
                "persistent_occupancy": mean_or_zero(
                    1.0 if row["outcomes"]["persistent_response"] else 0.0
                    for row in critter_rows
                ),
                "response_class_counts": dict(
                    sorted(
                        Counter(
                            row["outcomes"]["response_class"]
                            for row in critter_rows
                        ).items()
                    )
                ),
            }
        split_analysis[split] = {
            "preferred_episode_count": len(preferred_rows),
            "preferred_visible_bounded_occupancy": mean_or_zero(
                1.0 if row["outcomes"]["visible_bounded_response"] else 0.0
                for row in preferred_rows
            ),
            "preferred_persistent_occupancy": mean_or_zero(
                1.0 if row["outcomes"]["persistent_response"] else 0.0
                for row in preferred_rows
            ),
            "preferred_globalized_count": sum(
                bool(row["outcomes"]["globalized_response"])
                for row in preferred_rows
            ),
            "preferred_response_class_mutual_information_bits": mutual_information(
                preferred_rows
            ),
            "observe_divergence_count": sum(
                float(row["outcomes"]["peak_divergent_fraction"]) > 0.0
                for row in observe_rows
            ),
            "preferred_by_critter": preferred_by_critter,
        }

    fresh = [split_analysis[split] for split in ("confirmatory", "holdout")]
    h1 = all(
        part["observe_divergence_count"] == 0
        and all(
            row["visible_bounded_occupancy"] >= 0.75
            for row in part["preferred_by_critter"].values()
        )
        for part in fresh
    )
    h2 = all(
        sum(
            row["persistent_occupancy"] >= 0.75
            for row in part["preferred_by_critter"].values()
        )
        >= 2
        for part in fresh
    )
    h3 = all(
        part["preferred_response_class_mutual_information_bits"] > 0.10
        for part in fresh
    )
    h4 = all(part["preferred_globalized_count"] == 0 for part in fresh)
    hypothesis_assessment = {
        "H1_preferred_action_control": {
            "status": "supported_within_sample" if h1 else "not_supported",
            "evidence": {
                split: split_analysis[split]["preferred_by_critter"]
                for split in ("confirmatory", "holdout")
            },
        },
        "H2_persistent_memory": {
            "status": "supported_within_sample" if h2 else "not_supported",
            "evidence": {
                split: {
                    critter: values["persistent_occupancy"]
                    for critter, values in split_analysis[split][
                        "preferred_by_critter"
                    ].items()
                }
                for split in ("confirmatory", "holdout")
            },
        },
        "H3_substrate_specific_signatures": {
            "status": "supported_within_sample" if h3 else "not_supported",
            "evidence": {
                split: split_analysis[split][
                    "preferred_response_class_mutual_information_bits"
                ]
                for split in ("confirmatory", "holdout")
            },
        },
        "H4_no_globalized_preferred_response": {
            "status": "supported_within_sample" if h4 else "not_supported",
            "evidence": {
                split: split_analysis[split]["preferred_globalized_count"]
                for split in ("confirmatory", "holdout")
            },
        },
    }
    return {
        "schema": SCHEMA_SUMMARY,
        "row_count": len(rows),
        "condition_count": len(condition_summaries),
        "episode_counts": {
            split: sum(row["split"] == split for row in rows) for split in SPLITS
        },
        "taxonomy_schema": taxonomy["schema"],
        "condition_summaries": condition_summaries,
        "split_analysis": split_analysis,
        "hypothesis_assessment": hypothesis_assessment,
        "exposure_audit": {
            "episodes": len(rows),
            "episodes_with_all_attempts": sum(
                int(row["exposure"]["action_attempts"])
                == len(manifest["design"]["action_ticks"])
                for row in rows
            ),
            "nonobserve_episodes_with_state_change": sum(
                row["condition"]["action"] != "observe"
                and int(row["exposure"]["successful_action_ticks"]) > 0
                for row in rows
            ),
            "nonobserve_episode_count": sum(
                row["condition"]["action"] != "observe" for row in rows
            ),
            "observe_divergence_count": sum(
                bool(row["outcomes"]["observe_divergence"]) for row in rows
            ),
        },
        "claim_boundary": (
            "Response classes describe paired deterministic field differences. They do not "
            "establish emotion, preference, learning, sentience, or biological life."
        ),
    }


def taxonomy_lookup(taxonomy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["id"]): row for row in taxonomy["critters"]}


def write_taxonomy_matrix(
    path: Path,
    summary: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> None:
    critters = taxonomy_lookup(taxonomy)
    fields = [
        "split",
        "critter",
        "display_name",
        "substrate",
        "action",
        "preferred_action",
        "coupling_shape",
        "memory_carrier",
        "episodes",
        "visible_bounded_occupancy",
        "persistent_occupancy",
        "globalized_count",
        "peak_divergence_mean",
        "tail_divergence_mean",
        "localization_mean",
        "reach_mean",
        "component_delta_mean",
        "response_class_counts",
    ]
    action_semantics = {
        row["id"]: row for row in taxonomy["action_semantics"]
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in summary["condition_summaries"]:
            critter = critters[row["critter"]]
            metrics = row["metrics"]
            writer.writerow(
                {
                    "split": row["split"],
                    "critter": row["critter"],
                    "display_name": critter["display_name"],
                    "substrate": critter["substrate"],
                    "action": row["action"],
                    "preferred_action": row["preferred_action"],
                    "coupling_shape": action_semantics[row["action"]][
                        "coupling_shape"
                    ],
                    "memory_carrier": critter["memory_carrier"],
                    "episodes": row["episodes"],
                    "visible_bounded_occupancy": row[
                        "visible_bounded_occupancy"
                    ],
                    "persistent_occupancy": row["persistent_occupancy"],
                    "globalized_count": row["globalized_count"],
                    "peak_divergence_mean": metrics["peak_divergent_fraction"][
                        "mean"
                    ],
                    "tail_divergence_mean": metrics["tail_divergent_fraction"][
                        "mean"
                    ],
                    "localization_mean": metrics[
                        "response_localization_at_peak"
                    ]["mean"],
                    "reach_mean": metrics["response_reach_radius_at_peak"][
                        "mean"
                    ],
                    "component_delta_mean": metrics["component_count_delta"][
                        "mean"
                    ],
                    "response_class_counts": json.dumps(
                        row["response_class_counts"], sort_keys=True
                    ),
                }
            )


def build_knowledge_card(
    summary: Mapping[str, Any], receipt: Mapping[str, Any]
) -> str:
    fresh_lines: list[str] = []
    for split in ("confirmatory", "holdout"):
        for critter, values in summary["split_analysis"][split][
            "preferred_by_critter"
        ].items():
            fresh_lines.append(
                f"- {split} {critter}/{values['action']}: visible-bounded "
                f"{values['visible_bounded_occupancy']:.3f}, persistent "
                f"{values['persistent_occupancy']:.3f}, classes "
                f"{json.dumps(values['response_class_counts'], sort_keys=True)}."
            )
    hypothesis_lines = [
        f"- {name}: **{value['status']}**."
        for name, value in summary["hypothesis_assessment"].items()
    ]
    return f"""# Pixie Sanctuary v1 Knowledge Card

## Observed

- {summary['row_count']} paired deterministic episodes populated {summary['condition_count']} split/crititter/action cells.
{chr(10).join(fresh_lines)}
- Exposure: {summary['exposure_audit']['episodes_with_all_attempts']} / {summary['row_count']} episodes executed all declared action attempts; {summary['exposure_audit']['nonobserve_episodes_with_state_change']} / {summary['exposure_audit']['nonobserve_episode_count']} non-observe episodes changed state through their action coupling.
- Observe divergence occurred in {summary['exposure_audit']['observe_divergence_count']} episodes.
- The production run used {receipt['wall_seconds']:.2f} seconds and peaked at {receipt['max_rss_mb']:.2f} MB RSS; sampled exact replay passed: {summary['determinism']['passed']}.

## Hypothesis Assessment

{chr(10).join(hypothesis_lines)}

## Inferred

The matrix identifies implemented local affordances that can steer each deterministic substrate and records whether their effects remain local, propagate, alter morphology, recover, or globalize. This is a mechanics prototype for encounter design, not a scalar ranking of fun.

## Not Supported

- Critters do not feel, prefer, bond, learn, or understand Pixies.
- A persistent field scar is not memory in a cognitive sense.
- Response classes do not establish life, agency, or player enjoyment.
- The taxonomy is an exploration index, not an ontology registry change.

## Robustness and Confounds

- Seeds are disjoint across discovery, confirmation, and larger/longer holdout worlds.
- Every treated world has an exact paired untreated comparator.
- The sanctuary is two-dimensional and periodic; no moving Pixie, gates, mixed ecology, or bounded terrain is implemented yet.
- Actions have substrate-specific low-level meanings and are not energy-matched physical interventions.
- Component count is a coarse diagnostic; Prism Wyrm uses phase-zero domains only.

## Artifacts

- `frozen_manifest.json`
- `mechanics_taxonomy.json`
- `raw_episodes.jsonl`
- `summary.json`
- `taxonomy_matrix.csv`
- `seed_manifest.json`
- `receipt.json`
- `hashes.json`
- Replay: `{receipt['replay_command']}`

## Next Experiment

Take the most legible non-globalizing response for each critter into a bounded cavern with a moving Pixie. Test whether the response remains visible when action position, timing, and terrain boundaries vary, then add one mixed-critter resource coupling as a separate factorial experiment.
"""


def deterministic_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    projected = json.loads(json.dumps(row))
    projected["provenance"].pop("runtime_seconds", None)
    projected["provenance"].pop("max_rss_mb", None)
    return projected


def run_demo(args: argparse.Namespace, manifest: Mapping[str, Any]) -> None:
    design = manifest["design"]
    critter = args.critter or "prism_wyrm"
    action = args.action or design["preferred_actions"][critter]
    profile = dict(design["species_profiles"][critter])
    side = args.side or 24
    steps = args.steps or 32
    row = run_episode(
        split="discovery",
        seed=args.seed,
        critter=critter,
        action=action,
        profile=profile,
        side=side,
        steps=steps,
        solver_steps_per_record=int(design["solver_steps_per_record"][critter]),
        action_ticks=[tick for tick in design["action_ticks"] if tick <= steps],
        shield_duration=int(design["shield_duration_ticks"]),
        matched_degree=int(design["matched_degree"]),
        tail_ticks=min(int(design["response_tail_ticks"]), steps),
        thresholds=manifest["analysis"]["response_thresholds"],
        pixie=design["pixie"],
        deadline=time.monotonic() + 60.0,
        max_ram_mb=float(manifest["budget"]["max_ram_mb"]),
        render_every=max(1, args.render_every),
    )
    print(
        json.dumps(
            {
                "episode_id": row["episode_id"],
                "critter": critter,
                "action": action,
                "outcomes": row["outcomes"],
                "events": row["events"],
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--splits", default="all")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--skip-determinism", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--critter", choices=("bitlichen", "prism_wyrm", "mitosis_moss"))
    parser.add_argument("--action", choices=("observe", "touch", "sing", "feed", "cool", "shield"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--side", type=int)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--render-every", type=int, default=8)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if args.demo:
        run_demo(args, manifest)
        return
    taxonomy_path = manifest_path.parent / manifest["design"]["taxonomy_path"]
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8-sig"))
    output = (args.output or Path(manifest["artifacts"]["output_directory"])).resolve()
    output.mkdir(parents=True, exist_ok=True)
    splits = parse_splits(args.splits)
    budget = manifest["budget"]
    design = manifest["design"]
    deadline = time.monotonic() + float(budget["max_wall_seconds"])
    seeds = {
        split: ([manifest["seed_plan"][split][0]] if args.smoke else manifest["seed_plan"][split])
        for split in splits
    }
    planned = sum(
        len(seeds[split]) * len(condition_specs(manifest, split, args.smoke))
        for split in splits
    )
    if planned > int(budget["max_episodes"]):
        raise SystemExit(f"planned episode count {planned} exceeds budget")
    started = time.monotonic()
    started_utc = utc_now()
    rows: list[dict[str, Any]] = []
    max_rss = current_rss_mb()
    status = "ok"
    stop_reason = "completed_declared_splits"
    determinism: dict[str, Any] = {"performed": False, "passed": None, "samples": []}
    try:
        with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as handle:
            for split in splits:
                for seed in seeds[split]:
                    for spec in condition_specs(manifest, split, args.smoke):
                        steps = min(12, spec["steps"]) if args.smoke else spec["steps"]
                        action_ticks = [
                            tick for tick in design["action_ticks"] if tick <= steps
                        ]
                        row = run_episode(
                            split=split,
                            seed=int(seed),
                            **{**spec, "steps": steps},
                            action_ticks=action_ticks,
                            shield_duration=int(design["shield_duration_ticks"]),
                            matched_degree=int(design["matched_degree"]),
                            tail_ticks=min(int(design["response_tail_ticks"]), steps),
                            thresholds=manifest["analysis"]["response_thresholds"],
                            pixie=design["pixie"],
                            deadline=deadline,
                            max_ram_mb=float(budget["max_ram_mb"]),
                        )
                        row["condition"]["preferred_action"] = (
                            design["preferred_actions"][spec["critter"]]
                            == spec["action"]
                        )
                        rows.append(row)
                        handle.write(json.dumps(row, sort_keys=True) + "\n")
                        handle.flush()
                        max_rss = max(max_rss, row["provenance"]["max_rss_mb"])
        if not args.skip_determinism:
            samples = []
            for critter in design["critters"]:
                original = next(
                    row
                    for row in rows
                    if row["condition"]["critter"] == critter
                    and row["condition"]["action"]
                    == design["preferred_actions"][critter]
                )
                condition = original["condition"]
                replay = run_episode(
                    split=original["split"],
                    seed=int(original["seed"]),
                    critter=critter,
                    action=condition["action"],
                    profile=condition["profile_parameters"],
                    side=int(condition["side"]),
                    steps=int(condition["steps"]),
                    solver_steps_per_record=int(
                        condition["solver_steps_per_record"]
                    ),
                    action_ticks=condition["action_ticks"],
                    shield_duration=int(design["shield_duration_ticks"]),
                    matched_degree=int(condition["matched_degree"]),
                    tail_ticks=min(
                        int(design["response_tail_ticks"]), int(condition["steps"])
                    ),
                    thresholds=manifest["analysis"]["response_thresholds"],
                    pixie=design["pixie"],
                    deadline=deadline,
                    max_ram_mb=float(budget["max_ram_mb"]),
                )
                replay["condition"]["preferred_action"] = True
                expected = canonical_sha256(deterministic_projection(original))
                actual = canonical_sha256(deterministic_projection(replay))
                samples.append(
                    {
                        "critter": critter,
                        "seed": original["seed"],
                        "expected_sha256": expected,
                        "actual_sha256": actual,
                        "passed": expected == actual,
                    }
                )
            determinism = {
                "performed": True,
                "passed": all(row["passed"] for row in samples),
                "samples": samples,
            }
            if not determinism["passed"]:
                raise RuntimeError("sampled exact replay failed")
    except (MemoryError, TimeoutError, RuntimeError, ValueError) as exc:
        status = "stopped"
        stop_reason = f"{type(exc).__name__}: {exc}"

    summary = summarize(rows, manifest, taxonomy)
    summary["status"] = status
    summary["stop_reason"] = stop_reason
    summary["determinism"] = determinism
    write_json(output / "summary.json", summary)
    write_taxonomy_matrix(output / "taxonomy_matrix.csv", summary, taxonomy)
    write_json(
        output / "seed_manifest.json",
        {
            "splits_run": splits,
            "seeds": {split: list(seeds[split]) for split in splits},
            "pairing": manifest["seed_plan"]["pairing"],
            "planned_episodes": planned,
            "completed_episodes": len(rows),
        },
    )
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    shutil.copy2(taxonomy_path, output / "mechanics_taxonomy.json")
    code_path = Path(__file__).resolve()
    root = code_path.parents[1]
    alt_path = code_path.with_name("alt_physics_atlas.py")
    geometry_path = code_path.with_name("geometry_averaging_experiment.py")
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
        "alt_dependency_path": str(alt_path),
        "alt_dependency_sha256": sha256_file(alt_path),
        "geometry_dependency_path": str(geometry_path),
        "geometry_dependency_sha256": sha256_file(geometry_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "taxonomy_path": str(taxonomy_path),
        "taxonomy_sha256": sha256_file(taxonomy_path),
        **environment,
        "environment_sha256": canonical_sha256(environment),
        "git_commit_at_run": git_commit(root),
        "output_path": str(output),
        "determinism": determinism,
        "replay_command": (
            f"python src/pixie_sanctuary.py --manifest {manifest_path} "
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
        "taxonomy_matrix.csv",
        "seed_manifest.json",
        "frozen_manifest.json",
        "mechanics_taxonomy.json",
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
