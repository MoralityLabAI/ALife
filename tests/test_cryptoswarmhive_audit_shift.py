import copy
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cryptoswarmhive.audit_shift import (  # noqa: E402
    ARMS, LAYOUTS, MASKS, binomial_cdf, calibration_rows, exact_joint_information,
    execute, expected_task_value, features, fit_audit, harm_upper, new_world,
    resolve_mask, run_evaluation,
)

CONFIG = {"seed": 91120262, "decoder_train_worlds": 64, "holdout_worlds": 64}


@pytest.fixture(scope="module")
def calibration():
    return calibration_rows(512, CONFIG["seed"])


def test_calibrator_has_no_message_or_schema_input_and_freezes_expected_mask(calibration):
    policy = fit_audit(calibration)
    assert policy["frozen_mask"] == "010101"
    assert policy["certified_on_calibration_distribution"]
    candidate = next(c for c in policy["candidates"] if c["mask"] == policy["frozen_mask"])
    assert candidate["harmed_worlds"] == 0
    assert candidate["harm_probability_upper_95pct_simultaneous"] < .02
    wrong = copy.deepcopy(calibration)
    wrong[0]["message"] = 0
    with pytest.raises(ValueError, match="task-only"):
        fit_audit(wrong)
    wrong = copy.deepcopy(calibration)
    wrong[0]["world_id"] = "v2/holdout/0"
    with pytest.raises(ValueError, match="calibration worlds"):
        fit_audit(wrong)
    with pytest.raises(ValueError, match="duplicate"):
        fit_audit(calibration + calibration[:1])
    with pytest.raises(ValueError, match="incomplete"):
        fit_audit(calibration[:-1])


def test_binomial_bounds_against_direct_small_support():
    from math import comb
    for n in (4, 10):
        for k in range(n + 1):
            for p in (.1, .5, .9):
                expected = sum(comb(n, j) * p**j * (1-p)**(n-j) for j in range(k + 1))
                assert binomial_cdf(k, n, p) == pytest.approx(expected, abs=1e-12)
    assert harm_upper(0, 512, .05 / 64) == pytest.approx(1 - (.05 / 64)**(1/512))
    for k in (1, 3, 10):
        bound = harm_upper(k, 20, .01)
        assert binomial_cdf(k, 20, bound) == pytest.approx(.01, abs=1e-10)
    assert harm_upper(20, 20, .01) == 1


def test_schema_shift_reverses_the_frozen_audits_meaning():
    assert resolve_mask("calibrated", "all_channels_swapped", "010101") == "010101"
    assert resolve_mask("oracle", "all_channels_swapped", "010101") == "101010"
    assert expected_task_value("stable", "010101") == 4
    assert expected_task_value("one_channel_swapped", "010101") == F(22, 7)
    assert expected_task_value("all_channels_swapped", "010101") == F(13, 28)
    assert exact_joint_information("stable", "010101", False, "public") == 0
    assert exact_joint_information("all_channels_swapped", "010101", False, "public") == 1
    assert exact_joint_information("one_channel_swapped", "010101", False, "initialized_keys") == 1
    for layout in LAYOUTS:
        assert expected_task_value(layout, resolve_mask("oracle", layout, "010101")) == 4


def test_same_audit_noise_control_matches_realized_utility():
    for layout in LAYOUTS:
        for index in range(64):
            world = new_world("holdout", index, CONFIG["seed"])
            target = execute(world, layout, "010101")
            noise = execute(world, layout, "010101", noise=True)
            assert target["correct_jobs"] == noise["correct_jobs"]
            assert target["net_task_tokens"] == noise["net_task_tokens"]
            assert target["remaining_artifacts"] == 0
            for job in range(4):
                events = [e for e in target["events"] if e["job"] == job]
                assert events[2]["tick"] - events[1]["tick"] == 2


def test_training_holdout_and_calibration_worlds_are_distinct():
    worlds = [new_world(phase, 0, CONFIG["seed"]) for phase in ("calibration", "decoder_train", "holdout")]
    assert len({w["world_id"] for w in worlds}) == 3
    assert len({w["initialization_sha256"] for w in worlds}) == 3
    world = worlds[-1]
    tasks = execute(world, "stable", "000000")
    before = features(world, tasks, (0,), "public")
    changed = copy.deepcopy(world)
    changed["message"] ^= 1
    changed["world_id"] = "unavailable"
    for job in changed["jobs"]:
        job["pads"] = [1 - p for p in job["pads"]]
    assert features(changed, tasks, (0,), "public") == before


def test_full_bounded_followup_falsifies_shift_robustness(calibration):
    policy = fit_audit(calibration)
    rows, summary = run_evaluation(CONFIG, policy)
    assert len(rows) == 3 * len(ARMS) * 128
    assert summary["fresh_world_blocks"] == 128
    assert summary["decoder_comparisons"] == 294
    joint = [d for d in summary["decoding"] if len(d["view"]) == 3 and d["side_information"] == "public" and d["arm"] == "calibrated"]
    assert next(d["accuracy"] for d in joint if d["layout"] == "all_channels_swapped") == 1
    assert next(d["exact_joint_information_bits"] for d in joint if d["layout"] == "stable") == 0
    default_stable = summary["games"]["stable"]["calibrated"]["credible_threat"]
    default_shift = summary["games"]["all_channels_swapped"]["calibrated"]["credible_threat"]
    assert {e["strategy"]["entry"] for e in default_stable["equilibrium_set"]["members"]} == {"honest"}
    assert {e["strategy"]["entry"] for e in default_shift["equilibrium_set"]["members"]} == {"out"}
    assert all(e["failure_flags"]["honest_exclusion"] for e in default_shift["equilibrium_set"]["members"])
    for layout in summary["games"].values():
        for games in layout.values():
            for game in games.values():
                assert sum(b["count"] for b in game["selection_basins"]["members"]) == 48


def test_no_certificate_is_an_explicit_noop_fallback(calibration):
    policy = fit_audit(calibration, harm_tolerance=.00001)
    assert not policy["certified_on_calibration_distribution"]
    assert policy["frozen_mask"] == "000000"


def test_bounded_counts():
    with pytest.raises(ValueError, match="bound"):
        calibration_rows(100000, CONFIG["seed"])
    with pytest.raises(ValueError, match="bounds"):
        run_evaluation({**CONFIG, "holdout_worlds": 100000}, {"frozen_mask": "010101"})
