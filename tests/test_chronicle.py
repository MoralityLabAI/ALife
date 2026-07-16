from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alife import LifeUniverse  # noqa: E402
from chronicle.campaign import (  # noqa: E402
    _moore_counts_side_two,
    condition_matrix,
    episode_config,
    run_episode_events,
)
from chronicle.events import (  # noqa: E402
    EventBuilder,
    ChronicleRecorder,
    canonical_jsonl,
    validate_event,
    validate_stream,
)
from chronicle.export_sft import export_sft_records, validate_sft_record  # noqa: E402
from chronicle.legends import compile_legends, validate_legends  # noqa: E402
from geometry_averaging_experiment import (  # noqa: E402
    neighbor_counts,
    neighborhood_offsets,
)


@pytest.fixture()
def chronicle_manifest() -> dict:
    return json.loads(
        (ROOT / "experiments" / "chronicle_v1" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture()
def tiny_native_config(chronicle_manifest: dict) -> dict:
    manifest = copy.deepcopy(chronicle_manifest)
    manifest["design"]["native"].update({"width": 10, "height": 8, "density": 0.18})
    return episode_config(manifest, 0, steps=2)


def _aggregate_trace_digest(seed: int) -> str:
    universe = LifeUniverse(16, 12, seed=seed, seed_density=0.22)
    trace = []
    for _ in range(8):
        trace.append({"stats": universe.step(), "events": universe.event_counts()})
    return hashlib.sha256(
        json.dumps(trace, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    ("seed", "expected"),
    # Frozen from the committed pre-chronicle src/alife.py aggregate traces.
    [
        (7, "d22e6e4d178f8d29547a0d10aa7ab2aeebfde31333fd15267bae25edca9f5ac5"),
        (42, "1c844c81fc40cbd17128759ae9a03778622823fe1ed22c787dbd0ef064f2449e"),
        (1337, "3751a2d7cebcb96a6f8b76bf554cd9c0defc3205a1fd5e3b633c68c655077e69"),
    ],
)
def test_entity_ids_do_not_change_aggregate_dynamics(seed: int, expected: str) -> None:
    assert _aggregate_trace_digest(seed) == expected


def test_tiny_native_event_stream_replays_and_compiles(
    tiny_native_config: dict, tmp_path: Path
) -> None:
    first, diagnostics = run_episode_events(
        tiny_native_config, deadline=time.monotonic() + 30, max_ram_mb=1024
    )
    second, replay_diagnostics = run_episode_events(
        tiny_native_config, deadline=time.monotonic() + 30, max_ram_mb=1024
    )
    assert canonical_jsonl(first) == canonical_jsonl(second)
    assert diagnostics["final_state_sha256"] == replay_diagnostics["final_state_sha256"]
    assert validate_stream(first) == []

    event_path = tmp_path / "events.jsonl"
    event_path.write_bytes(canonical_jsonl(first))
    legends = compile_legends(event_path)
    assert validate_legends(legends) == []
    assert legends["event_count"] == len(first)
    assert legends["biographies"]
    assert legends["cast_index"][0]["rank"] == 1

    records = export_sft_records(
        event_path,
        seed=tiny_native_config["seed"],
        replay_receipt="test-receipt",
        legends=legends,
        max_window_events=32,
        max_biographies=3,
    )
    assert records
    assert all(validate_sft_record(record) == [] for record in records)
    assert all(record["narration"] is None for record in records)


def test_specialized_native_events_have_stable_entities() -> None:
    universe = LifeUniverse(16, 12, seed=42, seed_density=0.22)
    recorder = ChronicleRecorder(
        universe, episode_id="fixture-42", world_id="fixture-world-42"
    )
    for _ in range(8):
        recorder.step()
    event_types = {event["event_type"] for event in recorder.events}
    assert {
        "goblin_love",
        "goblin_rage",
        "goblin_romance",
        "goblin_pair",
        "goblin_conversion",
        "echo_bloom",
        "meme_attachment",
        "insight_drift",
    }.issubset(event_types)
    assert all(entity["id"].startswith("e") for event in recorder.events for entity in event["entities"])
    living_ids = [
        cell.entity_id
        for grid in universe.grids.values()
        for row in grid
        for cell in row
        if cell is not None
    ]
    assert len(living_ids) == len(set(living_ids))


def test_side_two_moore_optimization_matches_geometry_machinery() -> None:
    rng = np.random.default_rng(123)
    state = rng.random((2, 2, 2, 2)) < 0.35
    expected = neighbor_counts(state, neighborhood_offsets(4, "moore", 22))
    actual = _moore_counts_side_two(state)
    np.testing.assert_array_equal(actual, expected.astype(np.uint64))


def test_dimension_eleven_both_arms_are_bounded_and_deterministic(
    chronicle_manifest: dict,
) -> None:
    # Matrix indices 18 and 19 are dimension-11 Moore and fixed-degree worlds.
    for index in (18, 19):
        config = episode_config(chronicle_manifest, index, steps=2)
        first, _ = run_episode_events(
            config, deadline=time.monotonic() + 30, max_ram_mb=1024
        )
        second, _ = run_episode_events(
            config, deadline=time.monotonic() + 30, max_ram_mb=1024
        )
        assert canonical_jsonl(first) == canonical_jsonl(second)
        assert validate_stream(first) == []


def test_condition_matrix_tags_every_world_with_plane_dimension_and_degree(
    chronicle_manifest: dict,
) -> None:
    conditions = condition_matrix(chronicle_manifest)
    assert len(conditions) == 20
    assert all(
        isinstance(condition["plane"], str)
        and isinstance(condition["dimension"], int)
        and isinstance(condition["degree"], int)
        for condition in conditions
    )
    assert {condition["plane"] for condition in conditions} == {
        "GENESIS",
        "FORGE",
        "ECHOSPHERE",
        "MIRAGE",
    }
    assert {
        condition["dimension"]
        for condition in conditions
        if condition["family"] == "high_dimensional_lattice"
    } == set(range(4, 12))


def test_gate_event_requires_anchor_cooldown_and_success_semantics() -> None:
    builder = EventBuilder("gate-fixture", "gate-world")
    event = builder.emit(
        tick=1,
        event_type="gate_transfer",
        plane="GENESIS",
        region="x_low_y_low",
        position=[1, 2],
        entities=[
            {"id": "e00000001", "role": "source", "kind": "life", "species": None},
            {"id": "e00000002", "role": "created", "kind": "echo", "species": None},
        ],
        cause_chain=[{"type": "gate_rule", "entity_ids": ["e00000001"]}],
        details={
            "gate": "fixture_gate",
            "outcome": "placed",
            "target_plane": "ECHOSPHERE",
            "target_position": [3, 4],
            "anchor_offset": [1, 0],
            "anchor_position": [2, 2],
            "cooldown_before": 0,
            "cooldown_after": 7,
        },
    )
    assert validate_event(event) == []
    invalid = copy.deepcopy(event)
    invalid["event_type"] = "gate_transfer_attempt"
    assert "successful gate placement must use gate_transfer" in validate_event(invalid)


def test_sft_fact_contract_rejects_tampered_claim(tiny_native_config: dict) -> None:
    events, _ = run_episode_events(
        tiny_native_config, deadline=time.monotonic() + 30, max_ram_mb=1024
    )
    records = export_sft_records(
        events,
        seed=tiny_native_config["seed"],
        replay_receipt="fixture-receipt",
        max_window_events=32,
        max_biographies=1,
    )
    tampered = copy.deepcopy(records[0])
    tampered["fact_list"][0]["value"] = "not-derived-from-events"
    assert any(
        "does not exactly match" in error for error in validate_sft_record(tampered)
    )


def test_portable_verifier_accepts_relocated_tiny_corpus(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    relocated = tmp_path / "relocated"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "src" / "chronicle" / "campaign.py"),
            "--output",
            str(generated),
            "--episodes",
            "1",
            "--steps",
            "1",
            "--max-cells-per-world",
            "4096",
            "--wall-seconds",
            "30",
            "--episode-wall-seconds",
            "20",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    shutil.move(str(generated), str(relocated))
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "src" / "chronicle" / "verify_chronicle.py"),
            str(relocated),
            "--sample",
            "1",
            "--portable",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    receipt = json.loads(
        (relocated / "verification_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "passed"
    assert receipt["exact_event_byte_replays_passed"] == 1


def test_empty_lattice_still_has_a_compilable_initialization_fact(
    chronicle_manifest: dict,
) -> None:
    # Production episode 304 is a known zero-population initialization edge case.
    config = episode_config(chronicle_manifest, 304, steps=8)
    events, _ = run_episode_events(
        config, deadline=time.monotonic() + 30, max_ram_mb=1024
    )
    assert len(events) == 1
    assert events[0]["event_type"] == "world_initialized"
    assert events[0]["details"]["initial_living"] == 0
    legends = compile_legends(events)
    assert validate_legends(legends) == []
    records = export_sft_records(
        events,
        seed=config["seed"],
        replay_receipt="empty-fixture",
        legends=legends,
    )
    assert records
    assert all(validate_sft_record(record) == [] for record in records)


def test_native_replay_is_independent_of_python_hash_salt() -> None:
    script = (
        "import hashlib,sys,time;"
        "sys.path.insert(0,'src');"
        "from chronicle.campaign import episode_config,run_episode_events;"
        "from chronicle.events import canonical_jsonl;"
        "import json;"
        "m=json.load(open('experiments/chronicle_v1/manifest.json',encoding='utf-8'));"
        "e,_=run_episode_events(episode_config(m,1,steps=8),"
        "deadline=time.monotonic()+60,max_ram_mb=1024);"
        "print(hashlib.sha256(canonical_jsonl(e)).hexdigest())"
    )
    digests = []
    for hash_seed in ("1", "987654"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = hash_seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        digests.append(completed.stdout.strip())
    assert digests[0] == digests[1]
