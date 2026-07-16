from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alt_physics_atlas import canonical_sha256  # noqa: E402
from pixie_sanctuary import (  # noqa: E402
    SCHEMA_EPISODE,
    SCHEMA_EVENT,
    action_mask,
    deterministic_projection,
    run_episode,
)


EXPERIMENT = ROOT / "experiments" / "pixie_sanctuary_v1"
MANIFEST = json.loads((EXPERIMENT / "manifest.json").read_text(encoding="utf-8"))
TAXONOMY = json.loads(
    (EXPERIMENT / "mechanics_taxonomy.json").read_text(encoding="utf-8")
)


def tiny_episode(critter: str, action: str, seed: int = 1201) -> dict:
    design = MANIFEST["design"]
    return run_episode(
        split="discovery",
        seed=seed,
        critter=critter,
        action=action,
        profile=design["species_profiles"][critter],
        side=16,
        steps=12,
        solver_steps_per_record=design["solver_steps_per_record"][critter],
        action_ticks=[4, 8],
        shield_duration=design["shield_duration_ticks"],
        matched_degree=design["matched_degree"],
        tail_ticks=4,
        thresholds=MANIFEST["analysis"]["response_thresholds"],
        pixie=design["pixie"],
        deadline=time.monotonic() + 30.0,
        max_ram_mb=2048.0,
    )


def test_taxonomy_declares_a_complete_three_by_six_matrix() -> None:
    matrix = TAXONOMY["implemented_matrix"]
    critters = matrix["critters"]
    actions = matrix["actions"]
    assert len(critters) == len(set(critters)) == 3
    assert len(actions) == len(set(actions)) == 6
    assert matrix["cell_count"] == len(critters) * len(actions) == 18
    assert {row["id"] for row in TAXONOMY["critters"]} == set(critters)
    assert {row["id"] for row in TAXONOMY["action_semantics"]} == set(actions)


def test_every_action_has_a_nonempty_periodic_target_mask() -> None:
    for action in TAXONOMY["implemented_matrix"]["actions"]:
        mask = action_mask((16, 16), (8, 8), action)
        assert mask.shape == (16, 16)
        assert 0 < int(mask.sum()) < mask.size


def test_observe_is_an_exact_no_op_for_every_critter() -> None:
    for critter in MANIFEST["design"]["critters"]:
        row = tiny_episode(critter, "observe")
        assert row["schema"] == SCHEMA_EPISODE
        assert row["outcomes"]["peak_divergent_fraction"] == 0.0
        assert row["provenance"]["treated_final_state_sha256"] == row["provenance"][
            "comparator_final_state_sha256"
        ]
        assert row["exposure"]["successful_action_ticks"] == 0


def test_every_nonobserve_matrix_cell_executes_a_state_coupling() -> None:
    for critter in MANIFEST["design"]["critters"]:
        for action in MANIFEST["design"]["actions"]:
            if action == "observe":
                continue
            row = tiny_episode(critter, action)
            assert row["exposure"]["action_attempts"] == 2
            assert row["exposure"]["successful_action_ticks"] > 0, (critter, action)


def test_episode_replay_and_factual_event_causes_are_exact() -> None:
    first = tiny_episode("prism_wyrm", "sing", seed=881)
    second = tiny_episode("prism_wyrm", "sing", seed=881)
    assert canonical_sha256(deterministic_projection(first)) == canonical_sha256(
        deterministic_projection(second)
    )
    event_ids = {item["event_id"] for item in first["events"]}
    assert len(event_ids) == len(first["events"])
    assert all(item["schema"] == SCHEMA_EVENT for item in first["events"])
    assert all(cause in event_ids for item in first["events"] for cause in item["cause"])
    assert [item["event_type"] for item in first["events"]].count("pixie_action") == 2
