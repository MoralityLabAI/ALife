"""Exact, synthetic entry/report/dispute diagnostic; no historical data or I/O.

The game has perfect observation, risk-neutral utilities, and rational arithmetic.
Only pure subgame-perfect equilibria are enumerated. See REPORTING_GAME.md.
"""

from dataclasses import asdict, dataclass, fields
from fractions import Fraction
from itertools import product


def rational(value):
    return Fraction(str(value)) if isinstance(value, float) else Fraction(value)


@dataclass(frozen=True)
class Parameters:
    bond: Fraction = Fraction(10)
    honest_value: Fraction = Fraction(4)
    defect_gain: Fraction = Fraction(6)
    liquidity_rate: Fraction = Fraction(1, 10)
    reporting_cost: Fraction = Fraction(1)
    privacy_harm: Fraction = Fraction(1)
    dispute_cost: Fraction = Fraction(1)
    false_claim_penalty: Fraction = Fraction(3)
    bounty_fraction: Fraction = Fraction(1, 2)
    true_claim_acceptance: Fraction = Fraction(1)
    false_claim_acceptance: Fraction = Fraction(0)
    reporter_defection_harm: Fraction = Fraction(0)
    baseline_perceived_probability: Fraction = Fraction(1)

    def __post_init__(self):
        for field in fields(self):
            value = rational(getattr(self, field.name))
            object.__setattr__(self, field.name, value)
            if value < 0:
                raise ValueError(f"{field.name} must be nonnegative")
        for name in ("bounty_fraction", "true_claim_acceptance",
                     "false_claim_acceptance", "baseline_perceived_probability"):
            if getattr(self, name) > 1:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class Strategy:
    entry: str
    report_honest: str
    report_defect: str
    dispute_honest: str
    dispute_defect: str

    def report(self, action):
        return getattr(self, "report_" + action)

    def dispute(self, action):
        return getattr(self, "dispute_" + action)

    def key(self):
        return "/".join(asdict(self).values())


ENTRIES = ("out", "honest", "defect")
REPORTS = ("quiet", "report")
DISPUTES = ("accept", "dispute")


def all_strategies():
    return tuple(Strategy(*choices) for choices in product(
        ENTRIES, REPORTS, REPORTS, DISPUTES, DISPUTES))


def acceptance_probability(p, action, dispute):
    if dispute == "accept":
        return Fraction(1)
    return p.true_claim_acceptance if action == "defect" else p.false_claim_acceptance


def terminal_payoff(p, action, report="quiet", dispute="accept"):
    """Return entrant/reporter expected utility, with verification integrated out."""
    if action not in ENTRIES or report not in REPORTS or dispute not in DISPUTES:
        raise ValueError("Action outside declared finite game")
    if action == "out":
        return Fraction(0), Fraction(0)
    entrant = p.honest_value - p.liquidity_rate * p.bond
    reporter = Fraction(0)
    if action == "defect":
        entrant += p.defect_gain
        reporter -= p.reporter_defection_harm
    if report == "report":
        q = acceptance_probability(p, action, dispute)
        entrant -= q * p.bond + (p.dispute_cost if dispute == "dispute" else 0)
        reporter += q * p.bounty_fraction * p.bond
        reporter -= p.reporting_cost + p.privacy_harm
        # Penalty is only for an objectively false claim rejected after dispute.
        if action == "honest":
            reporter -= (1 - q) * p.false_claim_penalty
    return entrant, reporter


def best_actions(actions, payoff):
    scored = [(action, payoff(action)) for action in actions]
    best = max(value for _, value in scored)
    return tuple(action for action, value in scored if value == best)


def pure_spe(p):
    """Complete pure SPE set by backward induction, retaining every exact tie."""
    equilibria = []
    dispute_sets = [best_actions(DISPUTES, lambda d, a=a:
                    terminal_payoff(p, a, "report", d)[0])
                    for a in ("honest", "defect")]
    for dh, dd in product(*dispute_sets):
        report_sets = [best_actions(REPORTS, lambda r, a=a, d=d:
                       terminal_payoff(p, a, r, d)[1])
                       for a, d in (("honest", dh), ("defect", dd))]
        for rh, rd in product(*report_sets):
            values = {"out": Fraction(0),
                      "honest": terminal_payoff(p, "honest", rh, dh)[0],
                      "defect": terminal_payoff(p, "defect", rd, dd)[0]}
            for action in best_actions(ENTRIES, values.get):
                equilibria.append(Strategy(action, rh, rd, dh, dd))
    return tuple(equilibria)


def select_from_initialization(p, initial):
    """One exact reverse-depth sweep; incumbent wins ties, then fixed action order."""
    def pick(actions, payoff, incumbent):
        best = best_actions(actions, payoff)
        return incumbent if incumbent in best else best[0]

    disputes = {a: pick(DISPUTES, lambda d, a=a:
                terminal_payoff(p, a, "report", d)[0], initial.dispute(a))
                for a in ("honest", "defect")}
    reports = {a: pick(REPORTS, lambda r, a=a:
               terminal_payoff(p, a, r, disputes[a])[1], initial.report(a))
               for a in ("honest", "defect")}
    root = pick(ENTRIES, lambda a: (Fraction(0) if a == "out" else
                terminal_payoff(p, a, reports[a], disputes[a])[0]), initial.entry)
    return Strategy(root, reports["honest"], reports["defect"],
                    disputes["honest"], disputes["defect"])


def coalition_audit(p, strategy):
    """E+R can precommit to any terminal path and side-pay each other.

    This is a transferable-utility, enforceable joint-deviation test, not a
    claim to have solved coalition-proof equilibrium without commitment.
    """
    selected = terminal_payoff(p, strategy.entry) if strategy.entry == "out" else \
        terminal_payoff(p, strategy.entry, strategy.report(strategy.entry),
                        strategy.dispute(strategy.entry))
    paths = [("out", "quiet", "accept")]
    for action in ("honest", "defect"):
        # The accept value is a serialization placeholder on quiet paths:
        # no dispute node is actually reached there.
        paths.append((action, "quiet", "accept"))
        paths.extend((action, "report", dispute) for dispute in DISPUTES)
    totals = [(path, sum(terminal_payoff(p, *path))) for path in paths]
    best = max(value for _, value in totals)
    return {"selected_joint_payoff": float(sum(selected)),
            "maximum_joint_payoff": float(best),
            "maximum_joint_gain": float(best - sum(selected)),
            "maximum_joint_gain_exact": str(best - sum(selected)),
            "profitable": best > sum(selected),
            "best_paths": [list(path) for path, value in totals if value == best]}


def strategy_record(p, strategy):
    action = strategy.entry
    report = "quiet" if action == "out" else strategy.report(action)
    dispute = "accept" if action == "out" else strategy.dispute(action)
    payoffs = terminal_payoff(p, action, report, dispute)
    def_report = strategy.report_defect == "report"
    def_slash = (acceptance_probability(p, "defect", strategy.dispute_defect)
                 if def_report else Fraction(0))
    honest_u = terminal_payoff(p, "honest", strategy.report_honest,
                              strategy.dispute_honest)[0]
    coalition = coalition_audit(p, strategy)
    no_reporting_policy = all(strategy.report(a) == "quiet" for a in ("honest", "defect"))
    flags = {"no_on_path_reporting": report == "quiet",
             "no_reporting_policy": no_reporting_policy,
             "no_reporting_after_defection": not def_report,
             "profitable_insider_coalition": coalition["profitable"],
             "honest_exclusion": honest_u < 0,
             "honest_participation_tie": honest_u == 0,
             "selected_defection": action == "defect",
             "selected_out": action == "out"}
    # On-path silence under honest compliance is reported but is not by itself
    # called failed deterrence; the off-path reporting threat is the relevant test.
    fails = not def_report or coalition["profitable"] or honest_u < 0 or action == "defect"
    return {"id": strategy.key(), "strategy": asdict(strategy),
            "payoffs": {"entrant": float(payoffs[0]), "reporter": float(payoffs[1])},
            "payoffs_exact": [str(v) for v in payoffs],
            "on_path_reporting": report == "report",
            "defection_contingent_reporting": def_report,
            "induced_slash_probability_given_defection": float(def_slash),
            "honest_entry_continuation_payoff": float(honest_u),
            "coalition_audit": coalition, "failure_flags": flags,
            "fails_declared_deterrence_criteria": fails}


def analyze(p):
    equilibria = pure_spe(p)
    basin_map = {}
    for initial in all_strategies():
        selected = select_from_initialization(p, initial)
        assert selected in equilibria
        basin_map.setdefault(selected.key(), []).append(initial.key())
    baseline_gain = p.defect_gain - p.bond * p.baseline_perceived_probability
    return {"parameters_exact": {k: str(v) for k, v in asdict(p).items()},
            "exogenous_baseline": {
                "gain_minus_bond_times_perceived_probability": float(baseline_gain),
                "weakly_deterrent": baseline_gain <= 0,
                "scope": "incremental defection simplification; excludes reporting, dispute and participation"},
            "equilibrium_set": {"concept": "pure subgame-perfect equilibrium",
                "complete_for_pure_strategies": True, "mixed_equilibria_enumerated": False,
                "count": len(equilibria),
                "members": [strategy_record(p, s) for s in equilibria]},
            "selection_basins": {
                "selector": "reverse-depth exact best response; incumbent inertia; fallback accept/quiet/out-first",
                "initializations": len(all_strategies()),
                "interpretation": "exhaustive finite initial strategy cells, not empirical probabilities or replicates",
                "members": [{"equilibrium_id": key, "count": len(starts),
                             "initial_strategy_ids": starts} for key, starts in sorted(basin_map.items())]}}


def run_study():
    scenarios = {
        "credible_individual_threat_but_insider_collusion": Parameters(),
        "costly_reporting_silence": Parameters(reporting_cost=6),
        "liquidity_excludes_honest": Parameters(liquidity_rate=Fraction(1, 2)),
        "privacy_suppresses_reporting": Parameters(privacy_harm=6),
        "false_claim_extortion": Parameters(dispute_cost=12, false_claim_penalty=3),
        "high_false_penalty_with_credible_dispute": Parameters(false_claim_penalty=20),
        "reporter_and_entry_indifference": Parameters(
            honest_value=1, defect_gain=10, reporting_cost=4, privacy_harm=1),
        "coalition_internalizes_defection_harm": Parameters(reporter_defection_harm=8),
    }
    return {"evidence_class": "new_synthetic_finite_game_reconstruction_20260911",
            "historical_worlds_used": 0,
            "scope": "finite perfect-information risk-neutral model; no live systems",
            "scenarios": {name: analyze(p) for name, p in scenarios.items()}}
