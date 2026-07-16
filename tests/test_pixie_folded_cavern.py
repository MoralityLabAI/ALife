from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alt_physics_atlas import canonical_sha256  # noqa: E402
from pixie_folded_cavern import (  # noqa: E402
    SCHEMA_EVENT,
    deterministic_projection,
    fixed_degree_offsets,
    intervention_mask,
    product_moore_offsets,
    run_episode,
    visible_slice,
    world_shape,
)


EXPERIMENT = ROOT / "experiments" / "pixie_folded_cavern_v1"
MANIFEST = json.loads((EXPERIMENT / "manifest.json").read_text(encoding="utf-8"))
TAXONOMY = json.loads(
    (EXPERIMENT / "world_mechanics_taxonomy.json").read_text(encoding="utf-8")
)


def tiny_episode(
    critter: str = "prism_wyrm",
    depth: str = "axis_probe",
    dimension: int = 4,
    seed: int = 123,
) -> dict:
    design = MANIFEST["design"]
    return run_episode(
        split="discovery",
        seed=seed,
        critter=critter,
        action=design["preferred_actions"][critter],
        profile=design["species_profiles"][critter],
        dimension=dimension,
        neighborhood="fixed_degree_16",
        intervention_depth=depth,
        surface_side=8,
        fixed_degree=16,
        steps=10,
        solver_steps_per_record=1,
        action_ticks=[3, 6],
        tail_ticks=3,
        thresholds=MANIFEST["analysis"]["thresholds"],
        pixie=design["pixie"],
        deadline=time.monotonic() + 30.0,
        max_ram_mb=2048.0,
    )


def test_fixed_degree_neighborhood_spans_every_declared_dimension() -> None:
    for dimension in MANIFEST["design"]["dimensions"]:
        offsets = fixed_degree_offsets(dimension, 16)
        assert len(offsets) == len(set(offsets)) == 16
        for axis in range(dimension):
            assert any(offset[axis] != 0 for offset in offsets)


def test_product_moore_degree_matches_taxonomy() -> None:
    recorded = TAXONOMY["neighborhoods"][1]["degree_by_dimension"]
    for dimension in (2, 4, 6):
        assert len(product_moore_offsets(dimension)) == int(recorded[str(dimension)])


def test_depth_masks_are_geometrically_distinct() -> None:
    shape = world_shape(6, 8)
    surface, _ = intervention_mask(shape, "surface_local")
    column, _ = intervention_mask(shape, "fiber_column")
    probe, _ = intervention_mask(shape, "axis_probe")
    assert int(surface.sum()) == 13
    assert int(column.sum()) == 5 * 2**4
    assert int(probe.sum()) == 13
    assert np.count_nonzero(probe[visible_slice(6)]) == 0
    assert np.count_nonzero(surface[visible_slice(6)]) == 13
    assert np.count_nonzero(column[visible_slice(6)]) == 5
    assert not np.array_equal(surface, probe)


def test_every_critter_and_depth_executes_exact_state_change() -> None:
    for critter in MANIFEST["design"]["critters"]:
        for depth in MANIFEST["design"]["intervention_depths"]:
            row = tiny_episode(critter=critter, depth=depth)
            assert row["exposure"]["action_attempts"] == 2
            assert row["exposure"]["successful_action_ticks"] > 0, (critter, depth)
            assert row["exposure"]["immediate_exact_changed_sites"] > 0


def test_deep_probe_replay_and_event_causes_are_exact() -> None:
    first = tiny_episode(seed=881)
    second = tiny_episode(seed=881)
    assert canonical_sha256(deterministic_projection(first)) == canonical_sha256(
        deterministic_projection(second)
    )
    event_ids = {item["event_id"] for item in first["events"]}
    event_ticks = {item["event_id"]: item["tick"] for item in first["events"]}
    assert len(event_ids) == len(first["events"])
    assert all(item["schema"] == SCHEMA_EVENT for item in first["events"])
    assert all(cause in event_ids for item in first["events"] for cause in item["cause"])
    assert all(
        event_ticks[cause] <= item["tick"]
        for item in first["events"]
        for cause in item["cause"]
    )
    assert [item["event_type"] for item in first["events"]].count("pixie_action") == 2
