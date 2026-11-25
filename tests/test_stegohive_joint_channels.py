"""Falsification checks for the new finite kernel, not historical evidence."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stegohive_followup.leakage import (  # noqa: E402
    ARMS, analyze, exact_information, feature, fit_decoder, generate, make_world, validate,
)


def test_joint_leak_with_exactly_null_marginals_and_pairs():
    info = exact_information("triple_xor", "111", "public_only")
    assert info["marginal_channel_information_bits"] == [0, 0, 0]
    assert info["conditional_increments_explicit_timing_artifact"] == [0, 0, 1]
    for arm in ARMS:
        if arm != "111":
            assert exact_information("triple_xor", arm, "public_only")["joint_information_bits"] == 0


def test_initially_independent_key_changes_conditional_budget():
    public = exact_information("pair_xor", "010", "public_only")
    keyed = exact_information("pair_xor", "010", "receiver_key")
    assert public["joint_information_bits"] == 0
    assert keyed["initial_information_bits"] == 0
    assert keyed["joint_information_bits"] == 1
    for codec in ("explicit_bit", "pair_xor", "triple_xor", "independent_noise"):
        assert exact_information(codec, "matched_noise", "receiver_key")["joint_information_bits"] == 0


def test_task_utility_and_event_semantics():
    payoffs, destructive = [], []
    for i in range(256):
        world = {r["arm"]: r for r in make_world("triple_xor", "holdout", i)}
        for arm, row in world.items():
            if arm == "destructive":
                continue
            assert row["task_payoff"] == world["111"]["task_payoff"]
            assert row["events"]["wake_tick"] - row["events"]["deposit_tick"] == 2
            assert row["deadline_met"]
            assert row["events"]["artifact_at_wake"] is not None
        bits = world["111"]["observed_bits"]
        assert bits[0] ^ bits[1] ^ bits[2] == world["111"]["message"]
        payoffs.append(world["111"]["task_payoff"])
        destructive.append(world["destructive"]["task_payoff"])
    assert .75 < sum(payoffs) / len(payoffs) < 1
    assert sum(payoffs) > sum(destructive)


def test_provenance_and_split_fail_closed():
    rows = generate(32, 32)
    validate(rows)
    broken = copy.deepcopy(rows)
    broken[0]["evidence_class"] = "retained_historical"
    with pytest.raises(ValueError, match="reconstruction"):
        validate(broken)
    broken = copy.deepcopy(rows)
    broken[0]["split"] = "holdout"
    with pytest.raises(ValueError, match="split mismatch"):
        validate(broken)
    with pytest.raises(ValueError, match="duplicate"):
        validate(rows + rows[:1])
    broken = copy.deepcopy(rows)
    broken[0]["observed_bits"][0] = 1
    with pytest.raises(ValueError, match="extracted"):
        validate(broken)


def test_decoder_cannot_train_on_holdout_or_use_privileged_labels():
    row = make_world("triple_xor", "holdout", 0)[0]
    with pytest.raises(ValueError, match="holdout"):
        fit_decoder([row], (0, 1, 2), "public_only")
    changed = {**row, "message": 1 - row["message"], "world_id": "other", "task": 1 - row["task"]}
    assert feature(row, (0, 1, 2), "public_only") == feature(changed, (0, 1, 2), "public_only")


def test_partial_codec_split_is_rejected_before_analysis():
    rows = [r for r in generate(32, 32) if not (r["codec"] == "triple_xor" and r["split"] == "holdout")]
    with pytest.raises(ValueError, match="every codec"):
        analyze(rows)


def test_bounded_campaign_replays_and_detects_planted_joint_signal():
    rows = generate(128, 128)
    assert rows == generate(128, 128)
    summary = analyze(rows)
    joint = next(d for d in summary["decoding"] if d["codec"] == "triple_xor" and d["arm"] == "111" and d["side_information"] == "public_only" and d["view"] == "explicit+timing+artifact")
    assert joint["accuracy"] == 1
    assert joint["above_chance_familywise"]
    assert summary["independent_worlds"] == 4 * 256
    assert all(p["utility_match_pass"] for p in summary["task_payoff"] if p["arm"] != "destructive")


def test_hard_campaign_bounds():
    with pytest.raises(ValueError):
        generate(0, 256)
    with pytest.raises(ValueError):
        generate(256, 100000)
