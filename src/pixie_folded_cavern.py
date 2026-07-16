#!/usr/bin/env python3
"""Deterministic higher-dimensional folded-cavern Pixie mechanics prototype."""

from __future__ import annotations

import argparse
import csv
import itertools
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
    canonical_sha256,
    categories_for,
    check_budget,
    current_rss_mb,
    git_commit,
    initialize_states,
    jeffreys_interval,
    sha256_file,
    state_digest,
    utc_now,
    write_json,
)
from pixie_sanctuary import (
    apply_pixie_action,
    copy_state,
    differing_sites,
    mean_or_zero,
    mutual_information,
    render_categories,
)


SCHEMA_EPISODE = "alife.pixie.folded_cavern.episode.v1"
SCHEMA_EVENT = "alife.pixie.folded_cavern.event.v1"
SCHEMA_SUMMARY = "alife.pixie.folded_cavern.summary.v1"
SCHEMA_RECEIPT = "alife.pixie.folded_cavern.receipt.v1"
SPLITS = ("discovery", "confirmatory", "holdout")


def world_shape(dimension: int, surface_side: int) -> tuple[int, ...]:
    if dimension < 2:
        raise ValueError("folded caverns require at least two visible dimensions")
    return (surface_side, surface_side) + (2,) * (dimension - 2)


def visible_slice(dimension: int) -> tuple[Any, ...]:
    return (slice(None), slice(None)) + (0,) * (dimension - 2)


def fixed_degree_offsets(dimension: int, degree: int = 16) -> tuple[tuple[int, ...], ...]:
    """Construct unique product-graph routes while representing every axis."""

    if degree < dimension + 2:
        raise ValueError("degree is too small to span both surface directions and every hidden axis")
    offsets: list[tuple[int, ...]] = []
    for axis in (0, 1):
        for direction in (-1, 1):
            value = [0] * dimension
            value[axis] = direction
            offsets.append(tuple(value))
    for axis in range(2, dimension):
        value = [0] * dimension
        value[axis] = 1
        offsets.append(tuple(value))

    candidates: list[tuple[int, ...]] = []
    for surface in itertools.product(range(-2, 3), repeat=2):
        for hidden in itertools.product((0, 1), repeat=dimension - 2):
            candidate = tuple(surface) + tuple(hidden)
            if not any(candidate) or candidate in offsets:
                continue
            candidates.append(candidate)
    candidates.sort(
        key=lambda value: (
            sum(abs(item) for item in value),
            sum(item != 0 for item in value),
            value,
        )
    )
    for candidate in candidates:
        if candidate not in offsets:
            offsets.append(candidate)
        if len(offsets) == degree:
            break
    if len(offsets) != degree or len(set(offsets)) != degree:
        raise RuntimeError("could not construct the declared fixed-degree neighborhood")
    return tuple(offsets)


def product_moore_offsets(dimension: int) -> tuple[tuple[int, ...], ...]:
    offsets = [
        tuple(surface) + tuple(hidden)
        for surface in itertools.product((-1, 0, 1), repeat=2)
        for hidden in itertools.product((0, 1), repeat=dimension - 2)
        if any(surface) or any(hidden)
    ]
    return tuple(offsets)


def neighborhood_offsets(
    dimension: int, neighborhood: str, fixed_degree: int
) -> tuple[tuple[int, ...], ...]:
    if neighborhood == "fixed_degree_16":
        return fixed_degree_offsets(dimension, fixed_degree)
    if neighborhood == "product_moore":
        return product_moore_offsets(dimension)
    raise ValueError(f"unknown folded-cavern neighborhood: {neighborhood}")


def surface_disc(surface_side: int, radius: int) -> np.ndarray:
    center = surface_side // 2
    y, x = np.indices((surface_side, surface_side))
    dy = np.minimum(np.abs(y - center), surface_side - np.abs(y - center))
    dx = np.minimum(np.abs(x - center), surface_side - np.abs(x - center))
    return dy + dx <= radius


def intervention_mask(
    shape: Sequence[int], depth: str
) -> tuple[np.ndarray, dict[str, Any]]:
    dimension = len(shape)
    full = np.zeros(tuple(shape), dtype=bool)
    if depth == "surface_local":
        full[visible_slice(dimension)] = surface_disc(shape[0], 2)
        details = {"visible_radius": 2, "hidden_target": "coordinate_zero"}
    elif depth == "fiber_column":
        base = surface_disc(shape[0], 1).reshape(
            (shape[0], shape[1]) + (1,) * (dimension - 2)
        )
        full = np.broadcast_to(base, tuple(shape)).copy()
        details = {"visible_radius": 1, "hidden_target": "all_coordinates"}
    elif depth == "axis_probe":
        if dimension == 2:
            full[visible_slice(dimension)] = surface_disc(shape[0], 2)
            details = {
                "visible_radius": 2,
                "hidden_target": "unavailable_dimension_2_surface_fallback",
            }
        else:
            index: list[Any] = [slice(None), slice(None), 1]
            index.extend([0] * (dimension - 3))
            full[tuple(index)] = surface_disc(shape[0], 2)
            details = {
                "visible_radius": 2,
                "hidden_target": "first_axis_coordinate_one",
            }
    else:
        raise ValueError(f"unknown intervention depth: {depth}")
    return full, {**details, "mask_sites": int(full.sum())}


def event(
    *,
    episode_id: str,
    tick: int,
    event_type: str,
    critter: str,
    action: str,
    depth: str,
    dimension: int,
    pixie: Mapping[str, Any],
    details: Mapping[str, Any],
    cause: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_EVENT,
        "event_id": f"{episode_id}:event:{tick:04d}:{event_type}",
        "episode_id": episode_id,
        "tick": int(tick),
        "event_type": event_type,
        "pixie": {"id": pixie["id"], "display_name": pixie["display_name"]},
        "critter": {"id": f"{episode_id}:critter", "species": critter},
        "action": action,
        "intervention_depth": depth,
        "dimension": dimension,
        "visible_position": list(pixie["visible_position"]),
        "details": dict(details),
        "cause": list(cause or []),
    }


def response_class(
    *,
    dimension: int,
    depth: str,
    peak_full: float,
    peak_visible: float,
    peak_hidden: float,
    hidden_share: float,
    first_visible_tick: int | None,
    thresholds: Mapping[str, Any],
) -> str:
    if peak_full < float(thresholds["full_response_min"]):
        return "no_response"
    if peak_full >= float(thresholds["globalized_full_min"]):
        return "globalized"
    if dimension > 2 and depth == "axis_probe" and first_visible_tick is not None:
        return "burrow_and_resurface"
    if peak_visible < float(thresholds["visible_response_min"]) and peak_hidden >= float(
        thresholds["full_response_min"]
    ):
        return "hidden_only"
    if dimension > 2 and hidden_share >= float(
        thresholds["fiber_wide_hidden_share_min"]
    ):
        return "fiber_wide"
    return "surface_confined"


def render_hidden_shadow(critter: str, categories: np.ndarray) -> str:
    if categories.ndim == 2:
        return "(no hidden chambers in 2-D)"
    if critter == "bitlichen":
        active = categories == 1
    elif critter == "prism_wyrm":
        active = categories != 0
    else:
        active = categories % 8 >= 1
    hidden_axes = tuple(range(2, categories.ndim))
    density = active.mean(axis=hidden_axes)
    palette = " .:-=+*#%@"
    return "\n".join(
        "".join(palette[min(int(value * len(palette)), len(palette) - 1)] for value in row)
        for row in density
    )


def run_episode(
    *,
    split: str,
    seed: int,
    critter: str,
    action: str,
    profile: Mapping[str, Any],
    dimension: int,
    neighborhood: str,
    intervention_depth: str,
    surface_side: int,
    fixed_degree: int,
    steps: int,
    solver_steps_per_record: int,
    action_ticks: Sequence[int],
    tail_ticks: int,
    thresholds: Mapping[str, Any],
    pixie: Mapping[str, Any],
    deadline: float,
    max_ram_mb: float,
    render_every: int = 0,
) -> dict[str, Any]:
    started = time.monotonic()
    family = str(profile["family"])
    shape = world_shape(dimension, surface_side)
    cell_count = int(math.prod(shape))
    surface_cells = surface_side * surface_side
    hidden_cells = cell_count - surface_cells
    offsets = neighborhood_offsets(dimension, neighborhood, fixed_degree)
    initialized, _, initialization = initialize_states(family, profile, shape, seed)
    treated = copy_state(family, initialized)
    comparator = copy_state(family, initialized)
    initial_categories, category_count = categories_for(family, initialized, profile)
    mask, mask_details = intervention_mask(shape, intervention_depth)
    episode_id = (
        f"folded-{split}-{seed}-{critter}-{intervention_depth}-"
        f"d{dimension}-{neighborhood}"
    )
    action_tick_set = {int(value) for value in action_ticks}
    action_events: list[str] = []
    events: list[dict[str, Any]] = []
    trajectory: list[dict[str, Any]] = []
    first_visible_tick: int | None = None
    first_visible_event_written = False
    max_rss = current_rss_mb()
    exposure = {
        "eligible_action_opportunities": len(action_ticks),
        "action_attempts": 0,
        "action_activations": 0,
        "successful_action_ticks": 0,
        "immediate_exact_changed_sites": 0,
        "treated_solver_site_evaluations": 0,
        "comparator_solver_site_evaluations": 0,
    }
    successful_ticks: set[int] = set()
    if render_every:
        print(f"\n{episode_id} tick=0 visible slice")
        print(render_categories(critter, initial_categories[visible_slice(dimension)]))
        print("hidden activity shadow")
        print(render_hidden_shadow(critter, initial_categories))

    for tick in range(1, steps + 1):
        check_budget(deadline, max_ram_mb)
        action_applied = tick in action_tick_set
        immediate_exact_changed = 0
        if action_applied:
            exposure["action_attempts"] += 1
            exposure["action_activations"] += 1
            before = copy_state(family, treated)
            treated, display_changed, action_details = apply_pixie_action(
                family=family,
                state=treated,
                profile=profile,
                action=action,
                mask=mask,
                offsets=offsets,
            )
            immediate_exact_changed = int(
                np.count_nonzero(differing_sites(family, treated, before))
            )
            exposure["immediate_exact_changed_sites"] += immediate_exact_changed
            if immediate_exact_changed:
                successful_ticks.add(tick)
            item = event(
                episode_id=episode_id,
                tick=tick,
                event_type="pixie_action",
                critter=critter,
                action=action,
                depth=intervention_depth,
                dimension=dimension,
                pixie=pixie,
                details={
                    **mask_details,
                    **action_details,
                    "exact_changed_sites": immediate_exact_changed,
                    "display_changed_sites": display_changed,
                },
            )
            events.append(item)
            action_events.append(item["event_id"])

        for _ in range(solver_steps_per_record):
            treated = advance_state(family, treated, profile, offsets)
            comparator = advance_state(family, comparator, profile, offsets)
            exposure["treated_solver_site_evaluations"] += cell_count
            exposure["comparator_solver_site_evaluations"] += cell_count

        treated_categories, category_count = categories_for(family, treated, profile)
        comparator_categories, _ = categories_for(family, comparator, profile)
        divergence = treated_categories != comparator_categories
        visible_divergence = divergence[visible_slice(dimension)]
        full_sites = int(divergence.sum())
        visible_sites = int(visible_divergence.sum())
        hidden_divergent_sites = full_sites - visible_sites
        full_fraction = full_sites / cell_count
        visible_fraction = visible_sites / surface_cells
        hidden_fraction = (
            hidden_divergent_sites / hidden_cells if hidden_cells else 0.0
        )
        hidden_share = hidden_divergent_sites / full_sites if full_sites else 0.0
        if visible_sites and first_visible_tick is None:
            first_visible_tick = tick
        if (
            intervention_depth == "axis_probe"
            and dimension > 2
            and first_visible_tick is not None
            and not first_visible_event_written
        ):
            events.append(
                event(
                    episode_id=episode_id,
                    tick=tick,
                    event_type="response_resurfaced",
                    critter=critter,
                    action=action,
                    depth=intervention_depth,
                    dimension=dimension,
                    pixie=pixie,
                    details={
                        "visible_divergent_sites": visible_sites,
                        "visible_divergent_fraction": visible_fraction,
                    },
                    cause=action_events,
                )
            )
            first_visible_event_written = True
        trajectory.append(
            {
                "tick": tick,
                "action_applied": action_applied,
                "immediate_exact_changed_sites": immediate_exact_changed,
                "full_divergent_sites": full_sites,
                "full_divergent_fraction": full_fraction,
                "visible_divergent_sites": visible_sites,
                "visible_divergent_fraction": visible_fraction,
                "hidden_divergent_sites": hidden_divergent_sites,
                "hidden_divergent_fraction": hidden_fraction,
                "hidden_response_share": hidden_share,
                "treated_state_sha256": state_digest(treated_categories),
                "comparator_state_sha256": state_digest(comparator_categories),
            }
        )
        if render_every and (tick % render_every == 0 or action_applied or tick == steps):
            print(
                f"\n{episode_id} tick={tick} visible={visible_fraction:.3f} "
                f"hidden_share={hidden_share:.3f}"
            )
            print(render_categories(critter, treated_categories[visible_slice(dimension)]))
            print("hidden activity shadow")
            print(render_hidden_shadow(critter, treated_categories))
        max_rss = max(max_rss, current_rss_mb())

    exposure["successful_action_ticks"] = len(successful_ticks)
    full_values = [float(row["full_divergent_fraction"]) for row in trajectory]
    visible_values = [float(row["visible_divergent_fraction"]) for row in trajectory]
    hidden_values = [float(row["hidden_divergent_fraction"]) for row in trajectory]
    full_peak_index = int(np.argmax(full_values))
    full_peak_row = trajectory[full_peak_index]
    peak_full = float(full_peak_row["full_divergent_fraction"])
    peak_visible = max(visible_values, default=0.0)
    peak_hidden = max(hidden_values, default=0.0)
    tail_full = mean_or_zero(full_values[-tail_ticks:])
    classification = response_class(
        dimension=dimension,
        depth=intervention_depth,
        peak_full=peak_full,
        peak_visible=peak_visible,
        peak_hidden=peak_hidden,
        hidden_share=float(full_peak_row["hidden_response_share"]),
        first_visible_tick=first_visible_tick,
        thresholds=thresholds,
    )
    globalized = peak_full >= float(thresholds["globalized_full_min"])
    resurfaced = intervention_depth == "axis_probe" and dimension > 2 and first_visible_tick is not None
    projection_aliasing = (
        tail_full >= float(thresholds["tail_response_min"])
        and visible_values[-1] < float(thresholds["visible_response_min"])
    )
    peak_event = event(
        episode_id=episode_id,
        tick=int(full_peak_row["tick"]),
        event_type="full_response_peak",
        critter=critter,
        action=action,
        depth=intervention_depth,
        dimension=dimension,
        pixie=pixie,
        details={
            "full_divergent_fraction": peak_full,
            "visible_divergent_fraction": full_peak_row["visible_divergent_fraction"],
            "hidden_divergent_fraction": full_peak_row["hidden_divergent_fraction"],
            "hidden_response_share": full_peak_row["hidden_response_share"],
        },
        cause=[
            item["event_id"]
            for item in events
            if item["event_type"] == "pixie_action"
            and int(item["tick"]) <= int(full_peak_row["tick"])
        ],
    )
    events.append(peak_event)
    events.append(
        event(
            episode_id=episode_id,
            tick=steps,
            event_type="response_classified",
            critter=critter,
            action=action,
            depth=intervention_depth,
            dimension=dimension,
            pixie=pixie,
            details={
                "response_class": classification,
                "resurfaced": resurfaced,
                "globalized": globalized,
                "projection_aliasing": projection_aliasing,
                "tail_full_divergent_fraction": tail_full,
            },
            cause=[peak_event["event_id"]],
        )
    )
    final_treated, _ = categories_for(family, treated, profile)
    final_comparator, _ = categories_for(family, comparator, profile)
    return {
        "schema": SCHEMA_EPISODE,
        "episode_id": episode_id,
        "split": split,
        "seed": seed,
        "experimental_unit": "one independently seeded paired folded-cavern episode",
        "condition": {
            "critter": critter,
            "family": family,
            "profile": str(profile["name"]),
            "action": action,
            "intervention_depth": intervention_depth,
            "dimension": dimension,
            "neighborhood": neighborhood,
            "neighborhood_degree": len(offsets),
            "shape": list(shape),
            "surface_side": surface_side,
            "surface_cells": surface_cells,
            "hidden_cells": hidden_cells,
            "cell_count": cell_count,
            "steps": steps,
            "solver_steps_per_record": solver_steps_per_record,
            "action_ticks": list(action_ticks),
            "action_mask_sites": int(mask.sum()),
            "profile_parameters": dict(profile),
            "initialization": initialization,
        },
        "pixie": dict(pixie),
        "exposure": exposure,
        "outcomes": {
            "peak_full_divergent_fraction": peak_full,
            "peak_full_tick": int(full_peak_row["tick"]),
            "peak_visible_divergent_fraction": peak_visible,
            "peak_hidden_divergent_fraction": peak_hidden,
            "hidden_response_share_at_full_peak": float(
                full_peak_row["hidden_response_share"]
            ),
            "tail_full_divergent_fraction": tail_full,
            "first_visible_response_tick": first_visible_tick,
            "resurfaced": resurfaced,
            "projection_aliasing": projection_aliasing,
            "globalized_response": globalized,
            "response_class": classification,
        },
        "events": events,
        "trajectory": trajectory,
        "provenance": {
            "initial_state_sha256": state_digest(initial_categories),
            "treated_final_state_sha256": state_digest(final_treated),
            "comparator_final_state_sha256": state_digest(final_comparator),
            "trajectory_sha256": canonical_sha256(trajectory),
            "events_sha256": canonical_sha256(events),
            "runtime_seconds": time.monotonic() - started,
            "max_rss_mb": max_rss,
            "rng": "numpy.default_rng(seed) at shared initialization only",
        },
    }


def deterministic_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    projected = json.loads(json.dumps(row))
    projected["provenance"].pop("runtime_seconds", None)
    projected["provenance"].pop("max_rss_mb", None)
    return projected


def parse_splits(value: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(SPLITS)
    result = [item.strip() for item in value.split(",") if item.strip()]
    if not result or any(item not in SPLITS for item in result):
        raise ValueError(f"invalid split selection: {value}")
    return result


def condition_specs(manifest: Mapping[str, Any], split: str) -> list[dict[str, Any]]:
    design = manifest["design"]
    result: list[dict[str, Any]] = []
    for neighborhood, dimensions in design["neighborhoods"].items():
        for dimension in dimensions:
            for critter in design["critters"]:
                for depth in design["intervention_depths"]:
                    result.append(
                        {
                            "critter": critter,
                            "action": design["preferred_actions"][critter],
                            "profile": dict(design["species_profiles"][critter]),
                            "dimension": int(dimension),
                            "neighborhood": neighborhood,
                            "intervention_depth": depth,
                            "surface_side": int(design["surface_side"]),
                            "fixed_degree": int(design["fixed_degree"]),
                            "steps": int(design["steps_by_split"][split]),
                            "solver_steps_per_record": int(
                                design["solver_steps_per_record"][critter]
                            ),
                        }
                    )
    return result


def summarize(
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> dict[str, Any]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        condition = row["condition"]
        groups[
            (
                row["split"],
                condition["neighborhood"],
                condition["dimension"],
                condition["critter"],
                condition["intervention_depth"],
            )
        ].append(row)
    metrics = (
        "peak_full_divergent_fraction",
        "peak_visible_divergent_fraction",
        "peak_hidden_divergent_fraction",
        "hidden_response_share_at_full_peak",
        "tail_full_divergent_fraction",
    )
    cells: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        split, neighborhood, dimension, critter, depth = key
        cells.append(
            {
                "split": split,
                "neighborhood": neighborhood,
                "dimension": dimension,
                "critter": critter,
                "intervention_depth": depth,
                "episodes": len(group),
                "action_mask_sites": int(group[0]["condition"]["action_mask_sites"]),
                "neighborhood_degree": int(group[0]["condition"]["neighborhood_degree"]),
                "successful_episode_count": sum(
                    int(row["exposure"]["successful_action_ticks"]) > 0 for row in group
                ),
                "resurfaced_count": sum(bool(row["outcomes"]["resurfaced"]) for row in group),
                "resurfaced_occupancy": mean_or_zero(
                    1.0 if row["outcomes"]["resurfaced"] else 0.0 for row in group
                ),
                "resurfaced_jeffreys_95": jeffreys_interval(
                    sum(bool(row["outcomes"]["resurfaced"]) for row in group), len(group)
                ),
                "globalized_count": sum(
                    bool(row["outcomes"]["globalized_response"]) for row in group
                ),
                "projection_aliasing_count": sum(
                    bool(row["outcomes"]["projection_aliasing"]) for row in group
                ),
                "response_class_counts": dict(
                    sorted(Counter(row["outcomes"]["response_class"] for row in group).items())
                ),
                "metric_means": {
                    name: mean_or_zero(float(row["outcomes"][name]) for row in group)
                    for name in metrics
                },
            }
        )

    split_analysis: dict[str, Any] = {}
    for split in SPLITS:
        split_rows = [row for row in rows if row["split"] == split]
        fixed = [
            row for row in split_rows if row["condition"]["neighborhood"] == "fixed_degree_16"
        ]
        axis_eligible = [
            row
            for row in fixed
            if row["condition"]["intervention_depth"] == "axis_probe"
            and int(row["condition"]["dimension"]) >= 4
        ]
        resurfacing_by_critter: dict[str, Any] = {}
        column_contrast_by_critter: dict[str, Any] = {}
        for critter in manifest["design"]["critters"]:
            critter_axis = [
                row for row in axis_eligible if row["condition"]["critter"] == critter
            ]
            surface = [
                row
                for row in fixed
                if row["condition"]["critter"] == critter
                and row["condition"]["intervention_depth"] == "surface_local"
            ]
            column = [
                row
                for row in fixed
                if row["condition"]["critter"] == critter
                and row["condition"]["intervention_depth"] == "fiber_column"
            ]
            surface_mean = mean_or_zero(
                float(row["outcomes"]["peak_visible_divergent_fraction"])
                for row in surface
            )
            column_mean = mean_or_zero(
                float(row["outcomes"]["peak_visible_divergent_fraction"])
                for row in column
            )
            resurfacing_by_critter[critter] = {
                "episodes": len(critter_axis),
                "count": sum(bool(row["outcomes"]["resurfaced"]) for row in critter_axis),
                "occupancy": mean_or_zero(
                    1.0 if row["outcomes"]["resurfaced"] else 0.0 for row in critter_axis
                ),
            }
            column_contrast_by_critter[critter] = {
                "surface_mean_peak_visible": surface_mean,
                "column_mean_peak_visible": column_mean,
                "column_minus_surface": column_mean - surface_mean,
            }
        depth_rows = [
            {
                "condition": {"critter": row["condition"]["intervention_depth"]},
                "outcomes": {"response_class": row["outcomes"]["response_class"]},
            }
            for row in split_rows
        ]
        split_analysis[split] = {
            "episode_count": len(split_rows),
            "axis_probe_resurfacing_by_critter": resurfacing_by_critter,
            "column_surface_contrast_by_critter": column_contrast_by_critter,
            "fixed_degree_globalized_count": sum(
                bool(row["outcomes"]["globalized_response"]) for row in fixed
            ),
            "depth_response_class_mutual_information_bits": mutual_information(depth_rows),
            "response_class_counts": dict(
                sorted(Counter(row["outcomes"]["response_class"] for row in split_rows).items())
            ),
        }

    fresh = [split_analysis[name] for name in ("confirmatory", "holdout")]
    h1 = all(
        sum(
            values["occupancy"] >= 0.75
            for values in part["axis_probe_resurfacing_by_critter"].values()
        )
        >= 2
        for part in fresh
    )
    h2 = all(
        all(
            values["column_minus_surface"] >= 0.0
            for values in part["column_surface_contrast_by_critter"].values()
        )
        for part in fresh
    )
    h3 = all(part["fixed_degree_globalized_count"] == 0 for part in fresh)
    h4 = all(
        part["depth_response_class_mutual_information_bits"] > 0.10 for part in fresh
    )
    return {
        "schema": SCHEMA_SUMMARY,
        "row_count": len(rows),
        "condition_count": len(cells),
        "episode_counts": {
            split: sum(row["split"] == split for row in rows) for split in SPLITS
        },
        "taxonomy_schema": taxonomy["schema"],
        "condition_summaries": cells,
        "split_analysis": split_analysis,
        "hypothesis_assessment": {
            "H1_axis_probe_resurfacing": {
                "status": "supported_within_sample" if h1 else "not_supported"
            },
            "H2_column_surface_control": {
                "status": "supported_within_sample" if h2 else "not_supported"
            },
            "H3_fixed_degree_avoids_globalization": {
                "status": "supported_within_sample" if h3 else "not_supported"
            },
            "H4_depth_specific_signatures": {
                "status": "supported_within_sample" if h4 else "not_supported"
            },
        },
        "exposure_audit": {
            "episodes": len(rows),
            "episodes_with_all_attempts": sum(
                int(row["exposure"]["action_attempts"])
                == len(row["condition"]["action_ticks"])
                for row in rows
            ),
            "episodes_with_exact_state_change": sum(
                int(row["exposure"]["successful_action_ticks"]) > 0 for row in rows
            ),
        },
        "claim_boundary": taxonomy["claim_boundary"],
    }


def write_mechanics_matrix(path: Path, summary: Mapping[str, Any]) -> None:
    fields = [
        "split",
        "neighborhood",
        "dimension",
        "neighborhood_degree",
        "critter",
        "intervention_depth",
        "episodes",
        "action_mask_sites",
        "successful_episode_count",
        "resurfaced_occupancy",
        "globalized_count",
        "projection_aliasing_count",
        "peak_full_mean",
        "peak_visible_mean",
        "peak_hidden_mean",
        "hidden_share_mean",
        "tail_full_mean",
        "response_class_counts",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in summary["condition_summaries"]:
            metric = row["metric_means"]
            writer.writerow(
                {
                    **{name: row[name] for name in fields[:12]},
                    "peak_full_mean": metric["peak_full_divergent_fraction"],
                    "peak_visible_mean": metric["peak_visible_divergent_fraction"],
                    "peak_hidden_mean": metric["peak_hidden_divergent_fraction"],
                    "hidden_share_mean": metric["hidden_response_share_at_full_peak"],
                    "tail_full_mean": metric["tail_full_divergent_fraction"],
                    "response_class_counts": json.dumps(
                        row["response_class_counts"], sort_keys=True
                    ),
                }
            )


def build_knowledge_card(summary: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    findings: list[str] = []
    for split in ("confirmatory", "holdout"):
        analysis = summary["split_analysis"][split]
        for critter, values in analysis["axis_probe_resurfacing_by_critter"].items():
            findings.append(
                f"- {split} {critter} deep-probe resurfacing: {values['count']} / "
                f"{values['episodes']} ({values['occupancy']:.3f})."
            )
        findings.append(
            f"- {split} depth/response-class mutual information: "
            f"{analysis['depth_response_class_mutual_information_bits']:.5f} bits; "
            f"fixed-degree globalizations: {analysis['fixed_degree_globalized_count']}."
        )
    hypotheses = "\n".join(
        f"- {name}: **{value['status']}**."
        for name, value in summary["hypothesis_assessment"].items()
    )
    return f"""# Pixie Folded Cavern v1 Knowledge Card

## Observed

- {summary['row_count']} paired deterministic episodes populated {summary['condition_count']} split-aware mechanics cells.
- Exact action execution occurred in {summary['exposure_audit']['episodes_with_exact_state_change']} / {summary['row_count']} episodes.
{chr(10).join(findings)}
- Three dimension-spanning exact replays passed: {summary['determinism']['passed']}.

## Hypothesis Assessment

{hypotheses}

## Inferred

Hidden binary axes can function as deterministic burrows, reservoirs, and parallel routes when their effects are projected back to a stable two-dimensional viewport. Intervention depth is a world-mechanics axis, not a scalar quality ranking.

## Not Supported

- The run does not establish physical extra dimensions, emotion, preference, learning, life, sentience, or player enjoyment.
- A hidden persistent field difference is not cognitive memory.
- The constant 8x8 viewport intentionally increases total habitat capacity with dimension, so this is not a pure dimension-only causal estimate.

## Robustness and Confounds

- Fixed-degree-16 spans dimensions 2, 4, 6, 8, and 11; product-Moore is capped at dimension 6 because degree grows exponentially.
- Every treated world has an exact untreated comparator and no post-initialization randomness.
- Binary hidden axes are a product graph, not a dense Euclidean lattice; hidden-axis flips are their own inverse.
- Fiber-column dosage grows with hidden capacity and is recorded explicitly rather than treated as energy matched.
- The activity shadow aliases many hidden configurations into the same two-dimensional projection.

## Resources and Artifacts

- Wall time: {receipt['wall_seconds']:.2f} seconds; peak RSS: {receipt['max_rss_mb']:.2f} MB.
- `world_mechanics_taxonomy.json`, `mechanics_matrix.csv`, `raw_episodes.jsonl`, `summary.json`, `receipt.json`, and `hashes.json`.
- Replay: `{receipt['replay_command']}`

## Next Experiment

Add axis-selective notes and two-view tomography in a bounded cavern. Hold action dosage constant while varying hidden capacity, then test whether players can infer and shepherd a hidden critter state without receiving the underlying array.
"""


def run_demo(args: argparse.Namespace, manifest: Mapping[str, Any]) -> None:
    design = manifest["design"]
    critter = args.critter
    dimension = args.dimension
    neighborhood = args.neighborhood
    if dimension not in design["neighborhoods"][neighborhood]:
        raise SystemExit(f"{neighborhood} is not declared at dimension {dimension}")
    row = run_episode(
        split="discovery",
        seed=args.seed,
        critter=critter,
        action=design["preferred_actions"][critter],
        profile=design["species_profiles"][critter],
        dimension=dimension,
        neighborhood=neighborhood,
        intervention_depth=args.intervention_depth,
        surface_side=int(design["surface_side"]),
        fixed_degree=int(design["fixed_degree"]),
        steps=args.steps,
        solver_steps_per_record=int(design["solver_steps_per_record"][critter]),
        action_ticks=[tick for tick in design["action_ticks"] if tick <= args.steps],
        tail_ticks=min(int(design["tail_ticks"]), args.steps),
        thresholds=manifest["analysis"]["thresholds"],
        pixie=design["pixie"],
        deadline=time.monotonic() + 60.0,
        max_ram_mb=float(manifest["budget"]["max_ram_mb"]),
        render_every=max(1, args.render_every),
    )
    print(json.dumps({"outcomes": row["outcomes"], "events": row["events"]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--splits", default="all")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--skip-determinism", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--critter", choices=("bitlichen", "prism_wyrm", "mitosis_moss"), default="prism_wyrm")
    parser.add_argument("--dimension", type=int, choices=(2, 4, 6, 8, 11), default=6)
    parser.add_argument("--neighborhood", choices=("fixed_degree_16", "product_moore"), default="fixed_degree_16")
    parser.add_argument("--intervention-depth", choices=("surface_local", "fiber_column", "axis_probe"), default="axis_probe")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--render-every", type=int, default=6)
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
    design = manifest["design"]
    budget = manifest["budget"]
    deadline = time.monotonic() + float(budget["max_wall_seconds"])
    seeds = {
        split: ([manifest["seed_plan"][split][0]] if args.smoke else manifest["seed_plan"][split])
        for split in splits
    }
    planned = sum(len(seeds[split]) * len(condition_specs(manifest, split)) for split in splits)
    if planned > int(budget["max_episodes"]):
        raise SystemExit(f"planned episode count {planned} exceeds budget")
    started = time.monotonic()
    started_utc = utc_now()
    max_rss = current_rss_mb()
    rows: list[dict[str, Any]] = []
    status = "ok"
    stop_reason = "completed_declared_splits"
    determinism: dict[str, Any] = {"performed": False, "passed": None, "samples": []}
    try:
        with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as handle:
            for split in splits:
                for seed in seeds[split]:
                    for spec in condition_specs(manifest, split):
                        steps = min(12, int(spec["steps"])) if args.smoke else int(spec["steps"])
                        action_ticks = [tick for tick in design["action_ticks"] if tick <= steps]
                        shape = world_shape(int(spec["dimension"]), int(spec["surface_side"]))
                        if math.prod(shape) > int(budget["max_cells_per_world"]):
                            raise ValueError(f"world exceeds cell cap: {shape}")
                        degree = len(
                            neighborhood_offsets(
                                int(spec["dimension"]),
                                str(spec["neighborhood"]),
                                int(spec["fixed_degree"]),
                            )
                        )
                        if degree > int(budget["max_neighborhood_degree"]):
                            raise ValueError(f"neighborhood degree exceeds cap: {degree}")
                        row = run_episode(
                            split=split,
                            seed=int(seed),
                            **{**spec, "steps": steps},
                            action_ticks=action_ticks,
                            tail_ticks=min(int(design["tail_ticks"]), steps),
                            thresholds=manifest["analysis"]["thresholds"],
                            pixie=design["pixie"],
                            deadline=deadline,
                            max_ram_mb=float(budget["max_ram_mb"]),
                        )
                        rows.append(row)
                        handle.write(json.dumps(row, sort_keys=True) + "\n")
                        handle.flush()
                        max_rss = max(max_rss, float(row["provenance"]["max_rss_mb"]))
        if not args.skip_determinism:
            samples: list[dict[str, Any]] = []
            for dimension in (2, 6, 11):
                original = next(
                    row
                    for row in rows
                    if int(row["condition"]["dimension"]) == dimension
                    and row["condition"]["neighborhood"] == "fixed_degree_16"
                    and row["condition"]["intervention_depth"] == "axis_probe"
                    and row["condition"]["critter"] == "prism_wyrm"
                )
                condition = original["condition"]
                replay = run_episode(
                    split=original["split"],
                    seed=int(original["seed"]),
                    critter=condition["critter"],
                    action=condition["action"],
                    profile=condition["profile_parameters"],
                    dimension=int(condition["dimension"]),
                    neighborhood=condition["neighborhood"],
                    intervention_depth=condition["intervention_depth"],
                    surface_side=int(condition["surface_side"]),
                    fixed_degree=int(design["fixed_degree"]),
                    steps=int(condition["steps"]),
                    solver_steps_per_record=int(condition["solver_steps_per_record"]),
                    action_ticks=condition["action_ticks"],
                    tail_ticks=min(int(design["tail_ticks"]), int(condition["steps"])),
                    thresholds=manifest["analysis"]["thresholds"],
                    pixie=design["pixie"],
                    deadline=deadline,
                    max_ram_mb=float(budget["max_ram_mb"]),
                )
                expected = canonical_sha256(deterministic_projection(original))
                actual = canonical_sha256(deterministic_projection(replay))
                samples.append(
                    {
                        "dimension": dimension,
                        "expected_sha256": expected,
                        "actual_sha256": actual,
                        "passed": expected == actual,
                    }
                )
            determinism = {
                "performed": True,
                "passed": all(item["passed"] for item in samples),
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
    write_mechanics_matrix(output / "mechanics_matrix.csv", summary)
    write_json(
        output / "seed_manifest.json",
        {
            "splits_run": splits,
            "seeds": {split: list(seeds[split]) for split in splits},
            "planned_episodes": planned,
            "completed_episodes": len(rows),
            "pairing": manifest["seed_plan"]["pairing"],
        },
    )
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    shutil.copy2(taxonomy_path, output / "world_mechanics_taxonomy.json")
    code_path = Path(__file__).resolve()
    root = code_path.parents[1]
    dependencies = {
        "atlas": code_path.with_name("alt_physics_atlas.py"),
        "sanctuary": code_path.with_name("pixie_sanctuary.py"),
    }
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
        "atlas_dependency_path": str(dependencies["atlas"]),
        "atlas_dependency_sha256": sha256_file(dependencies["atlas"]),
        "sanctuary_dependency_path": str(dependencies["sanctuary"]),
        "sanctuary_dependency_sha256": sha256_file(dependencies["sanctuary"]),
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
            f"python src/pixie_folded_cavern.py --manifest {manifest_path} "
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
        "mechanics_matrix.csv",
        "seed_manifest.json",
        "frozen_manifest.json",
        "world_mechanics_taxonomy.json",
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
        },
    )
    total_bytes = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        raise SystemExit("artifact directory exceeded disk budget")
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
