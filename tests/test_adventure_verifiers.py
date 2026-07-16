from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from adventure_verifiers import (  # noqa: E402
    VerifierSpec,
    adapt_chronicle_events,
    build_pixie_adventure,
    make_result,
    verify_adventure,
)
from adventure_verifiers.campaign import SCENARIOS, fixture_episode  # noqa: E402
from adventure_verifiers.core import TASK_SCHEMA, TRACE_SCHEMA  # noqa: E402
from chronicle.events import EventBuilder  # noqa: E402


ADVENTURE_MANIFEST_PATH = ROOT / "experiments" / "adventure_verifiers_v1" / "manifest.json"
ADVENTURE_MANIFEST = json.loads(ADVENTURE_MANIFEST_PATH.read_text(encoding="utf-8"))
SOURCE_MANIFEST = json.loads(
    (ROOT / "experiments" / "pixie_folded_cavern_v1" / "manifest.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture(scope="module")
def reference_adventure() -> tuple[dict, dict, dict]:
    row = fixture_episode(
        SOURCE_MANIFEST,
        split="confirmatory",
        seed=4101,
        deadline=time.monotonic() + 30.0,
    )
    return build_pixie_adventure(row)


def test_reference_folded_cavern_adventure_passes_vector_contract(
    reference_adventure: tuple[dict, dict, dict]
) -> None:
    task, trace, environment = reference_adventure
    result = verify_adventure(task, trace, environment)
    assert result["accepted"] is True
    assert result["configuration_errors"] == []
    assert result["failed_required_verifiers"] == []
    hard = [item for item in result["results"] if item["acceptance_eligible"]]
    diagnostics = [item for item in result["results"] if not item["acceptance_eligible"]]
    assert len(hard) == 8
    assert len(diagnostics) == 2
    assert all(item["passed"] for item in result["results"])


@pytest.mark.parametrize(
    ("scenario", "expected_failure", "mutator"),
    [(name, failure, mutator) for name, _, failure, mutator in SCENARIOS if name != "valid"],
)
def test_each_adversarial_fixture_is_rejected_by_target(
    reference_adventure: tuple[dict, dict, dict],
    scenario: str,
    expected_failure: str,
    mutator,
) -> None:
    task, trace, environment = copy.deepcopy(reference_adventure)
    mutator(task, trace, environment)
    result = verify_adventure(task, trace, environment)
    assert result["accepted"] is False, scenario
    if expected_failure == "configuration":
        assert result["configuration_errors"]
    else:
        assert expected_failure in result["failed_required_verifiers"]


def test_chronicle_adapter_supports_event_grounded_quest() -> None:
    builder = EventBuilder("chronicle-adventure", "chronicle-world")
    initialized = builder.emit(
        tick=0,
        event_type="world_initialized",
        plane="GENESIS",
        region="x_low_y_low",
        position=[0, 0],
        entities=[],
        details={"width": 8, "height": 8},
    )
    builder.emit(
        tick=1,
        event_type="birth",
        plane="GENESIS",
        region="x_low_y_low",
        position=[1, 0],
        entities=[{"id": "e00000001", "role": "subject", "kind": "seed", "species": None}],
        cause_chain=[{"type": "world_seed", "entity_ids": [], "event_sequence": initialized["sequence"]}],
        details={"kind": "seed"},
    )
    environment = adapt_chronicle_events(builder.events, replay_receipt="chronicle-replay-1")
    task = {
        "schema": TASK_SCHEMA,
        "task_id": "witness-birth",
        "environment_kind": "alife.chronicle",
        "required_verifiers": ["trace_schema", "event_stream_integrity", "goal_completion"],
        "diagnostic_verifiers": ["response_diversity"],
        "goals": [
            {
                "goal_id": "witness-one-birth",
                "kind": "event_count",
                "match": {"event_type": "birth", "details.kind": "seed"},
                "minimum": 1,
            }
        ],
        "rules": {
            "action_costs": {"wait": {}},
            "initial_resources": {"focus": 0},
            "action_receipt_event_types": ["world_initialized"],
            "movement": {
                "shape": [8, 8],
                "start_location": [0, 0],
                "max_torus_manhattan_step": 1,
            },
        },
    }
    trace = {
        "schema": TRACE_SCHEMA,
        "adventure_id": "witness-birth-trace",
        "task_id": task["task_id"],
        "episode_id": environment["episode_id"],
        "environment_kind": environment["environment_kind"],
        "event_stream_sha256": environment["events_sha256"],
        "replay_receipt": environment["replay_receipt"],
        "steps": [],
        "claims": [],
        "final_resources": {"focus": 0},
    }
    result = verify_adventure(task, trace, environment)
    assert result["accepted"] is True


def test_diagnostics_cannot_be_promoted_to_acceptance_gate(
    reference_adventure: tuple[dict, dict, dict]
) -> None:
    task, trace, environment = copy.deepcopy(reference_adventure)
    task["diagnostic_verifiers"].remove("response_diversity")
    task["required_verifiers"].append("response_diversity")
    result = verify_adventure(task, trace, environment)
    assert result["accepted"] is False
    assert any("diagnostic verifier cannot be an acceptance gate" in error for error in result["configuration_errors"])


def test_malformed_nonfinite_event_fails_without_throwing(
    reference_adventure: tuple[dict, dict, dict]
) -> None:
    task, trace, environment = copy.deepcopy(reference_adventure)
    environment["events"][0]["details"]["bad_number"] = float("nan")
    result = verify_adventure(task, trace, environment)
    assert result["accepted"] is False
    integrity = next(
        item for item in result["results"] if item["verifier_id"] == "event_stream_integrity"
    )
    assert integrity["passed"] is False
    assert any("finite JSON" in failure for failure in integrity["failures"])


def test_third_party_hard_verifier_can_extend_without_overriding_builtins(
    reference_adventure: tuple[dict, dict, dict]
) -> None:
    task, trace, environment = copy.deepcopy(reference_adventure)
    task["required_verifiers"].append("guild_badge")

    def guild_badge(task, trace, environment):
        del task, environment
        passed = trace["adventure_id"].startswith("adventure-")
        return make_result(
            "guild_badge",
            passed=passed,
            acceptance_eligible=True,
            failures=[] if passed else ["missing guild badge"],
        )

    extra = {
        "guild_badge": VerifierSpec(
            "guild_badge", True, "Example downstream guild contract.", guild_badge
        )
    }
    result = verify_adventure(task, trace, environment, extra_verifiers=extra)
    assert result["accepted"] is True

    result = verify_adventure(
        task,
        trace,
        environment,
        extra_verifiers={"trace_schema": extra["guild_badge"]},
    )
    assert result["accepted"] is False
    assert any("cannot override built-in" in error for error in result["configuration_errors"])
