from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from adventure_verifiers import (  # noqa: E402
    adapt_chronicle_events,
    build_chronicle_gate_adventure,
    canonical_sha256,
    verify_adventure,
)
from adventure_verifiers.chronicle_campaign import (  # noqa: E402
    SCENARIOS,
    fixture_stream,
)
from chronicle.events import validate_stream  # noqa: E402


@pytest.fixture(scope="module")
def reference_gate_adventure() -> tuple[dict, dict, dict]:
    events = fixture_stream(split="confirmatory", seed=6201)
    return build_chronicle_gate_adventure(
        events, replay_receipt=canonical_sha256(events)
    )


def test_chronicle_gate_fixture_has_exact_exposure_and_replay() -> None:
    first = fixture_stream(split="holdout", seed=9902)
    second = fixture_stream(split="holdout", seed=9902)
    assert validate_stream(first) == []
    assert canonical_sha256(first) == canonical_sha256(second)
    counts = {kind: 0 for kind in ("gate_transfer", "gate_transfer_attempt", "meme_attachment", "insight_drift")}
    for event in first:
        if event["event_type"] in counts:
            counts[event["event_type"]] += 1
    assert counts == {
        "gate_transfer": 2,
        "gate_transfer_attempt": 1,
        "meme_attachment": 1,
        "insight_drift": 1,
    }


def test_reference_chronicle_round_trip_passes_all_hard_verifiers(
    reference_gate_adventure: tuple[dict, dict, dict]
) -> None:
    task, trace, environment = reference_gate_adventure
    result = verify_adventure(task, trace, environment)
    assert result["accepted"] is True
    assert result["configuration_errors"] == []
    assert result["failed_required_verifiers"] == []
    hard = [item for item in result["results"] if item["acceptance_eligible"]]
    assert len(hard) == 10
    assert all(item["passed"] for item in result["results"])
    gate = next(item for item in result["results"] if item["verifier_id"] == "gate_travel")
    assert gate["facts"][0]["start_plane"] == "GENESIS"
    assert gate["facts"][0]["final_plane"] == "GENESIS"
    assert gate["facts"][0]["transfer_count"] == 2
    assert gate["facts"][0]["cooldown_rejection_count"] == 1


@pytest.mark.parametrize(
    ("scenario", "expected_failure", "mutator"),
    [
        (name, failure, mutator)
        for name, _, failure, mutator in SCENARIOS
        if name != "valid"
    ],
)
def test_each_chronicle_tamper_is_rejected_by_its_target(
    reference_gate_adventure: tuple[dict, dict, dict],
    scenario: str,
    expected_failure: str,
    mutator,
) -> None:
    task, trace, environment = copy.deepcopy(reference_gate_adventure)
    mutator(task, trace, environment)
    result = verify_adventure(task, trace, environment)
    assert result["accepted"] is False, scenario
    if expected_failure == "configuration":
        assert result["configuration_errors"]
    else:
        assert expected_failure in result["failed_required_verifiers"]


def test_witness_scope_distinguishes_event_truth_from_adventurer_knowledge(
    reference_gate_adventure: tuple[dict, dict, dict]
) -> None:
    task, trace, environment = copy.deepcopy(reference_gate_adventure)
    meme_claim = next(
        claim for claim in trace["claims"] if claim["claim_id"] == "claim-meme-attachment"
    )
    evidence_id = meme_claim["evidence_event_ids"][0]
    assert any(event["event_id"] == evidence_id for event in environment["events"])
    for step in trace["steps"]:
        step["observation_event_ids"] = [
            value for value in step["observation_event_ids"] if value != evidence_id
        ]
    result = verify_adventure(task, trace, environment)
    assert "claim_grounding" not in result["failed_required_verifiers"]
    assert "witness_scope" in result["failed_required_verifiers"]


def test_chronicle_adapter_rejects_invalid_source_order() -> None:
    events = fixture_stream(split="discovery", seed=5201)
    events[1]["sequence"] = 99
    with pytest.raises(ValueError, match="invalid chronicle stream"):
        adapt_chronicle_events(events, replay_receipt="invalid")
