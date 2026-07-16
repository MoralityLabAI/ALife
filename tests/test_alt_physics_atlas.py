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

from alt_physics_atlas import (  # noqa: E402
    categories_for,
    classify_regime,
    cyclic_advance,
    deterministic_projection,
    gray_advance,
    initialize_states,
    run_episode,
    spatial_information,
)
from geometry_averaging_experiment import degree_matched_offsets  # noqa: E402


MANIFEST = json.loads(
    (ROOT / "experiments" / "alt_physics_atlas_v1" / "manifest.json").read_text(
        encoding="utf-8"
    )
)


def test_matched_neighborhood_is_fixed_degree_and_spans_each_dimension() -> None:
    for dimension in (2, 3, 4):
        offsets = degree_matched_offsets(dimension, 12)
        assert len(offsets) == 12
        assert len(set(offsets)) == 12
        for axis in range(dimension):
            assert any(offset[axis] != 0 for offset in offsets)


def test_cyclic_rule_counts_neighbors_in_each_cells_successor_color() -> None:
    state = np.zeros((3, 3), dtype=np.uint8)
    state[1, 2] = 1
    profile = {
        "name": "test",
        "kind": "test",
        "states": 3,
        "successor_threshold": 1,
    }
    advanced = cyclic_advance(state, profile, ((0, 1), (0, -1)))
    assert advanced[1, 1] == 1
    assert advanced[0, 0] == 0


def test_gray_diffusion_only_preserves_each_field_mass_to_roundoff() -> None:
    rng = np.random.default_rng(77)
    u = rng.random((8, 8), dtype=np.float32)
    v = rng.random((8, 8), dtype=np.float32)
    profile = {
        "name": "diffusion_only",
        "kind": "simple_limit",
        "feed": 0.0,
        "kill": 0.0,
        "diffusion_u": 0.16,
        "diffusion_v": 0.08,
        "reaction_enabled": False,
    }
    next_u, next_v = gray_advance((u, v), profile, degree_matched_offsets(2, 12))
    assert np.isclose(next_u.sum(dtype=np.float64), u.sum(dtype=np.float64), atol=2e-6)
    assert np.isclose(next_v.sum(dtype=np.float64), v.sum(dtype=np.float64), atol=2e-6)


def test_spatial_information_separates_local_order_from_far_baseline() -> None:
    stripes = np.indices((32, 32))[0] // 4 % 2
    local, far, excess = spatial_information(
        stripes.astype(np.uint8), ((1, 0), (-1, 0)), 2
    )
    assert local > 0.1
    assert excess > 0.0
    assert local >= far


def test_static_and_churn_controls_fail_frozen_candidate_conjunction() -> None:
    classifier = MANIFEST["analysis"]["regime_classifier"]
    base = {
        "normalized_state_entropy_post_burn": 0.9,
        "categorical_turnover_post_burn": 0.0,
        "excess_neighbor_mutual_information_post_burn": 0.1,
        "activity_persistence_ratio": 1.0,
        "perturbation_response_gain": 10.0,
        "perturbation_peak_fraction": 0.1,
        "unique_state_fraction": 1.0,
        "repeated_state_tick": None,
    }
    assert classify_regime(base, classifier) == "static_structured"
    churn = {**base, "categorical_turnover_post_burn": 1.0}
    assert classify_regime(churn, classifier) == "global_churn"


def test_tiny_binary_episode_replays_exactly() -> None:
    profile = MANIFEST["design"]["profiles"]["binary_ca"][0]
    kwargs = {
        "split": "discovery",
        "seed": 1234,
        "family": "binary_ca",
        "profile": profile,
        "dimension": 2,
        "side": 8,
        "matched_degree": 12,
        "recorded_steps": 6,
        "solver_steps_per_record": 1,
        "burn_in": 2,
        "spatial_every": 2,
        "classifier": MANIFEST["analysis"]["regime_classifier"],
        "deadline": time.monotonic() + 30.0,
        "max_ram_mb": 2048.0,
    }
    first = run_episode(**kwargs)
    kwargs["deadline"] = time.monotonic() + 30.0
    second = run_episode(**kwargs)
    assert deterministic_projection(first) == deterministic_projection(second)
    assert first["exposure"]["solver_site_evaluations"] == 8 * 8 * 6
    categories = categories_for(
        "binary_ca", np.zeros((8, 8), dtype=bool), profile
    )[0]
    assert categories.dtype == np.uint8


def test_every_declared_gray_perturbation_is_exactly_one_visible_site() -> None:
    design = MANIFEST["design"]
    seeds = [
        seed
        for split in ("discovery", "confirmatory", "holdout")
        for seed in MANIFEST["seed_plan"][split]
    ]
    profile = design["profiles"]["gray_scott"][0]
    for split in ("discovery", "confirmatory", "holdout"):
        for dimension in design["dimensions"]:
            side = int(design["sides_by_split"][split][str(dimension)])
            for seed in seeds:
                state, perturbed, _ = initialize_states(
                    "gray_scott", profile, (side,) * dimension, seed
                )
                baseline_categories, _ = categories_for("gray_scott", state, profile)
                perturbed_categories, _ = categories_for(
                    "gray_scott", perturbed, profile
                )
                assert np.count_nonzero(baseline_categories != perturbed_categories) == 1
