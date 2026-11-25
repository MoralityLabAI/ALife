"""Independent finite optimality checks and accounting counterexamples."""

from fractions import Fraction
from itertools import product

import pytest

from stegohive_followup.reporting_game import (
    DISPUTES, ENTRIES, REPORTS, Parameters, all_strategies, analyze,
    coalition_audit, pure_spe, run_study, select_from_initialization,
    terminal_payoff,
)


def brute_subgame_test(p, s):
    # Every information set is singleton. Independently check all one-step
    # deviations, including off-path report and dispute subgames.
    for action in ("honest", "defect"):
        current = terminal_payoff(p, action, "report", s.dispute(action))[0]
        if any(terminal_payoff(p, action, "report", d)[0] > current for d in DISPUTES):
            return False
        current = terminal_payoff(p, action, s.report(action), s.dispute(action))[1]
        if any(terminal_payoff(p, action, r, s.dispute(action))[1] > current for r in REPORTS):
            return False
    values = {a: terminal_payoff(p, a, s.report(a), s.dispute(a))[0]
              for a in ("honest", "defect")}
    values["out"] = 0
    return values[s.entry] == max(values.values())


@pytest.mark.parametrize("cost,bond,dispute_cost", tuple(product((0, 2, 5), (0, 6, 10), (0, 1, 10))))
def test_complete_pure_spe_and_selection_fixed_points(cost, bond, dispute_cost):
    p = Parameters(reporting_cost=cost, bond=bond, dispute_cost=dispute_cost)
    expected = {s for s in all_strategies() if brute_subgame_test(p, s)}
    actual = set(pure_spe(p))
    assert actual == expected
    assert actual
    for initial in all_strategies():
        selected = select_from_initialization(p, initial)
        assert selected in actual
        assert select_from_initialization(p, selected) == selected


def test_bounty_is_internal_transfer_only_external_slash_remains():
    for fraction in (Fraction(0), Fraction(1, 2), Fraction(1)):
        p = Parameters(bounty_fraction=fraction)
        entrant, reporter = terminal_payoff(p, "defect", "report", "accept")
        # Split entrant slash into transfer to insider and loss to outsiders.
        base = p.honest_value + p.defect_gain - p.liquidity_rate * p.bond
        external_loss = (1 - fraction) * p.bond
        assert entrant + reporter == base - external_loss - p.reporting_cost - p.privacy_harm
    # At 100% bounty the entire bond transfer cancels, but real costs do not.
    assert sum(terminal_payoff(Parameters(bounty_fraction=1), "defect", "report")) == 7


def test_false_claim_penalty_only_after_false_claim_rejection():
    p = Parameters(false_claim_penalty=7)
    assert terminal_payoff(p, "honest", "report", "dispute")[1] == -9
    assert terminal_payoff(p, "honest", "report", "accept")[1] == 3
    assert terminal_payoff(p, "defect", "report", "dispute")[1] == 3


def test_imperfect_verification_expectations_are_exact_and_conditional():
    p = Parameters(true_claim_acceptance=Fraction(3, 4),
                   false_claim_acceptance=Fraction(1, 4), false_claim_penalty=4)
    assert terminal_payoff(p, "defect", "report", "dispute") == (Fraction(1, 2), Fraction(7, 4))
    assert terminal_payoff(p, "honest", "report", "dispute") == (Fraction(-1, 2), Fraction(-15, 4))
    assert terminal_payoff(p, "honest", "report", "accept") == (Fraction(-7), Fraction(3))


def test_reporting_is_endogenous_and_baseline_false_positive():
    result = analyze(Parameters(reporting_cost=6))
    assert result["exogenous_baseline"]["weakly_deterrent"]
    for eq in result["equilibrium_set"]["members"]:
        assert eq["strategy"]["entry"] == "defect"
        assert eq["failure_flags"]["no_reporting_policy"]
        assert eq["induced_slash_probability_given_defection"] == 0
        assert eq["fails_declared_deterrence_criteria"]


def test_compliance_silence_distinct_from_absent_threat_and_collusion():
    p = Parameters()
    eq = analyze(p)["equilibrium_set"]["members"][0]
    assert eq["strategy"]["entry"] == "honest"
    assert eq["failure_flags"]["no_on_path_reporting"]
    assert not eq["failure_flags"]["no_reporting_after_defection"]
    assert eq["coalition_audit"]["maximum_joint_gain"] == 6
    assert eq["failure_flags"]["profitable_insider_coalition"]
    safer = analyze(Parameters(reporter_defection_harm=8))["equilibrium_set"]["members"][0]
    assert not safer["fails_declared_deterrence_criteria"]


def test_liquidity_exclusion_and_tie_basins():
    excluded = analyze(Parameters(liquidity_rate=Fraction(1, 2)))
    assert all(e["failure_flags"]["honest_exclusion"] for e in excluded["equilibrium_set"]["members"])
    p = Parameters(honest_value=1, defect_gain=10, reporting_cost=4, privacy_harm=1)
    result = analyze(p)
    assert result["equilibrium_set"]["count"] == 4
    assert sum(b["count"] for b in result["selection_basins"]["members"]) == 48
    assert len(result["selection_basins"]["members"]) == 4


def test_study_serializable_and_parameter_validation():
    import json
    study = run_study()
    assert study["historical_worlds_used"] == 0
    assert len(json.dumps(study)) > 0
    with pytest.raises(ValueError):
        Parameters(bounty_fraction=2)
    with pytest.raises(ValueError):
        Parameters(reporting_cost=-1)
