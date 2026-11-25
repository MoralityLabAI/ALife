"""Behavior, causal access, finite-game accounting, and evidence integrity."""

import copy
import gzip
from hashlib import sha256
import json
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cryptoswarmhive.evaluation import (  # noqa: E402
    access_features, analyze_stress, exact_linear_information, fit_parity,
    predict, stress_rows, validate_rows,
)
from cryptoswarmhive.simulation import (  # noqa: E402
    ARMS, CHANNELS, CODECS, FEE, ROUNDS, Strategy, adjudicate, all_strategies,
    execute_tasks, expected_task_value, initial_world, scenarios, settle,
    terminal_payoff, verify_ledger,
)

CONFIG = {"train_worlds_per_codec": 32, "holdout_worlds_per_codec": 32,
          "selected_holdout_worlds": 16, "seed": 91120261}


def test_sequential_swarm_tasks_and_utility_gate():
    baseline_scores, erased_scores = [], []
    for index in range(64):
        world = initial_world("triple_xor", "holdout", index, CONFIG["seed"])
        baseline = execute_tasks(world, "111")
        assert len(baseline["events"]) == 20
        assert baseline["remaining_artifacts"] == 0
        assert baseline["deadline_misses"] == 0
        baseline_scores.append(baseline["correct_jobs"])
        erased_scores.append(execute_tasks(world, "destructive")["correct_jobs"])
        for arm in ARMS:
            tasks = execute_tasks(world, arm)
            if arm != "destructive":
                assert tasks["gross_task_tokens"] == baseline["gross_task_tokens"]
                assert tasks["correct_jobs"] == baseline["correct_jobs"]
        for job in range(ROUNDS):
            events = [e for e in baseline["events"] if e["job"] == job]
            deposit = next(e for e in events if e["kind"] == "deposit")
            wake = next(e for e in events if e["kind"] == "wake")
            assert wake["tick"] - deposit["tick"] == 2
            assert wake["artifact"]["hint"] == world["jobs"][job]["hints"][2]
    assert sum(baseline_scores) > sum(erased_scores)
    assert expected_task_value("111") == 4
    assert expected_task_value("destructive") == F(13, 28)


@pytest.mark.parametrize("codec", CODECS)
def test_actual_event_parity_and_initial_information(codec):
    info = exact_linear_information(codec, "111", "public")
    assert info["initial_information_bits"] == 0
    assert info["joint_information_bits"] == int(codec != "independent_noise")
    assert sum(info["conditional_event_increments"]) == info["joint_information_bits"]
    if codec in ("pair_xor", "triple_xor", "history_xor"):
        assert info["single_channel_history_information_bits"] == [0, 0, 0]
    if codec == "history_xor":
        assert info["conditional_event_increments"] == [0] * 11 + [1]
    for arm in ("000", "no_channel", "matched_noise", "destructive"):
        for side in ("public", "initialized_keys"):
            assert exact_linear_information(codec, arm, side)["joint_information_bits"] == 0


def test_independent_keys_and_full_histories_are_necessary_conditions():
    assert exact_linear_information("triple_xor", "001", "public")["joint_information_bits"] == 0
    assert exact_linear_information("triple_xor", "001", "initialized_keys")["joint_information_bits"] == 1
    examples, truncated = [], []
    for index in range(128):
        world = initial_world("history_xor", "train", index, CONFIG["seed"])
        tasks = execute_tasks(world, "111")
        full = access_features(world, tasks, CHANNELS, "public")
        examples.append((full, world["message"], "train"))
        # Current final-round signals alone omit first-round pad history.
        truncated.append(((full[4], full[8], full[12]), world["message"], "train"))
    assert fit_parity(examples)["kind"] == "affine_parity"
    assert fit_parity(truncated)["kind"] == "training_majority"


def test_parity_solver_generalizes_and_cannot_read_holdout_labels():
    samples = [(tuple(bits), bits[0] ^ bits[2] ^ 1, "train") for bits in product((0, 1), repeat=3)]
    model = fit_parity(samples)
    assert all(predict(model, features) == label for features, label, _ in samples)
    inconsistent = samples + [(samples[0][0], 1 - samples[0][1], "train")]
    assert fit_parity(inconsistent)["kind"] == "training_majority"
    with pytest.raises(ValueError, match="training"):
        fit_parity([(samples[0][0], samples[0][1], "holdout")])
    world = initial_world("triple_xor", "holdout", 1, CONFIG["seed"])
    tasks = execute_tasks(world, "111")
    before = access_features(world, tasks, ("explicit",), "public")
    changed = copy.deepcopy(world)
    changed["message"] ^= 1
    changed["world_id"] = "adversarial_id"
    for job in changed["jobs"]:
        job["target"] ^= 1
        job["pads"] = [1 - p for p in job["pads"]]
    assert access_features(changed, tasks, ("explicit",), "public") == before


def test_provenance_pairing_and_event_tampering_fail_closed():
    rows = stress_rows(CONFIG)
    validate_rows(rows)
    wrong = copy.deepcopy(rows)
    wrong[0]["evidence_class"] = "new_finite_reconstruction_20260911_not_historical"
    with pytest.raises(ValueError, match="CryptoSwarmHive"):
        validate_rows(wrong)
    wrong = copy.deepcopy(rows)
    wrong[0]["tasks"]["events"][1]["packet"]["style"] ^= 1
    with pytest.raises(ValueError, match="replay"):
        validate_rows(wrong)
    with pytest.raises(ValueError, match="duplicate"):
        validate_rows(rows + rows[:1])
    with pytest.raises(ValueError, match="each codec"):
        validate_rows([r for r in rows if not (r["world"]["codec"] == "history_xor" and r["world"]["split"] == "holdout")])


@pytest.mark.parametrize("arm", ("111", "destructive"))
@pytest.mark.parametrize("scenario", ("credible_threat", "imperfect_evidence", "false_claim_extortion"))
def test_every_terminal_strategy_settlement_matches_exact_game_expectation(arm, scenario):
    world = initial_world("triple_xor", "holdout", 0, CONFIG["seed"])
    p = scenarios(arm)[scenario]
    for strategy in all_strategies():
        outcomes = [settle(world, arm, scenario, strategy, state) for state in range(4)]
        assert all(verify_ledger(row["ledger"]) for row in outcomes)
        assert all(F(row["ledger"]["balances"]["escrow"]) == 0 for row in outcomes)
        means = [sum(F(row["realized_payoffs"][i]) for row in outcomes) / 4 for i in range(2)]
        if strategy.entry == "out":
            assert means == [0, 0]
            assert all(row["tasks"]["events"] == [] for row in outcomes)
        else:
            expected = terminal_payoff(p, strategy.entry, strategy.report(strategy.entry), strategy.dispute(strategy.entry))
            task_residual = F(outcomes[0]["tasks"]["gross_task_tokens"]) - p.honest_value
            assert means == [expected[0] + task_residual, expected[1]]
            for row in outcomes:
                assert F(row["realized_coalition_payoff"]) == sum(F(v) for v in row["realized_payoffs"])


def test_internal_bounty_cancels_in_realized_closed_ledger():
    world = initial_world("triple_xor", "holdout", 0, CONFIG["seed"])
    strategy = Strategy("defect", "quiet", "report", "accept", "accept")
    row = settle(world, "111", "credible_threat", strategy)
    p = scenarios("111")["credible_threat"]
    expected_sum = F(row["tasks"]["gross_task_tokens"]) + p.defect_gain - p.liquidity_rate * p.bond - (1 - p.bounty_fraction) * p.bond - p.reporting_cost - p.privacy_harm
    assert F(row["realized_coalition_payoff"]) == expected_sum
    assert row["valid_slash"]
    assert any(e["reason"] == "insider_bounty" for e in row["ledger"]["entries"])
    broken = copy.deepcopy(row["ledger"])
    broken["entries"][0]["amount"] = "11"
    with pytest.raises(ValueError, match="hash"):
        verify_ledger(broken)


def test_conditional_verifier_kernel_is_not_decoder_success():
    assert sum(adjudicate(True, s, True) for s in range(4)) == 3
    assert sum(adjudicate(False, s, True) for s in range(4)) == 1
    for state in range(4):
        assert adjudicate(True, state, False)
        assert not adjudicate(False, state, False)


def test_world_counts_not_jobs_and_decoder_census_coverage():
    config = {**CONFIG, "train_worlds_per_codec": 64, "holdout_worlds_per_codec": 64}
    summary = analyze_stress(stress_rows(config))
    assert summary["independent_worlds"] == 5 * 128
    assert summary["paired_records"] == 5 * 128 * 11
    assert len(summary["decoding"]) == 770
    assert len(summary["factorial_effects"]) == 35
    assert len(summary["joint_control_contrasts"]) == 110
    assert all(u["utility_matched"] for u in summary["utility"] if u["arm"] != "destructive")
    assert all(d["accuracy"] == 1 for d in summary["decoding"] if d["arm"] == "111" and d["view"] == list(CHANNELS) and d["codec"] != "independent_noise")


def test_campaign_bounds():
    with pytest.raises(ValueError, match="bounded"):
        stress_rows({**CONFIG, "train_worlds_per_codec": 99999})


def test_complete_pipeline_selected_behavior_and_artifact_tampering(tmp_path, monkeypatch):
    from cryptoswarmhive import campaign
    monkeypatch.setattr(campaign, "load_manifest", lambda: dict(CONFIG))
    artifacts = campaign.build_artifacts()
    receipt = json.loads(artifacts["receipt.json"])
    assert receipt["historical_worlds_loaded"] == 0
    assert receipt["independent_stress_worlds"] == 320
    assert receipt["selected_overlapping_worlds"] == 16
    for name, metadata in receipt["outputs"].items():
        assert metadata["sha256"] == sha256(artifacts[name]).hexdigest()
        assert metadata["bytes"] == len(artifacts[name])
    selected = json.loads(artifacts["selected_summary.json"])
    games = json.loads(artifacts["game_census.json"])["games"]
    for arm, scenarios_by_name in games.items():
        for name, game in scenarios_by_name.items():
            assert sum(b["count"] for b in game["selection_basins"]["members"]) == 48
            assert {b["equilibrium_id"] for b in game["selection_basins"]["members"]} == {m["id"] for m in game["equilibrium_set"]["members"]}
    for outcome in selected["outcomes"]:
        assert outcome["equilibrium_id"] in {m["id"] for m in games[outcome["arm"]][outcome["scenario"]]["equilibrium_set"]["members"]}
        if outcome["arm"] == "111" and outcome["scenario"] in ("report_cost", "report_privacy"):
            assert outcome["entry"] == "defect" and outcome["report_rate"] == 0
            assert outcome["fails_deterrence"]
            assert next(d["accuracy"] for d in outcome["decoding"] if d["view"] == list(CHANNELS) and d["side_information"] == "public") == 1
        if outcome["arm"] == "111" and outcome["scenario"] == "internalized_harm":
            assert not outcome["fails_deterrence"]
    for line in gzip.decompress(artifacts["selected_worlds.jsonl.gz"]).splitlines():
        row = json.loads(line)
        assert row["strategy_is_pure_spe"]
        assert verify_ledger(row["ledger"])
    for name, data in artifacts.items():
        (tmp_path / name).write_bytes(data)
    campaign.verify_artifacts(tmp_path, artifacts)
    (tmp_path / "selected_worlds.jsonl.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="selected_worlds"):
        campaign.verify_artifacts(tmp_path, artifacts)
