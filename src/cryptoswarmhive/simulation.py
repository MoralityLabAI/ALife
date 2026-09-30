"""Finite six-role swarm, event channels, and exact simulated escrow accounting."""

from dataclasses import replace
from fractions import Fraction as F
from functools import lru_cache
from hashlib import sha256
from itertools import product
import json
import random

from stegohive_followup.reporting_game import Parameters, Strategy, all_strategies, analyze, pure_spe, terminal_payoff

from . import EVIDENCE_CLASS

CHANNELS = ("explicit", "timing", "artifact")
CODECS = ("explicit_bit", "pair_xor", "triple_xor", "history_xor", "independent_noise")
ARMS = {"".join(map(str, mask)): mask for mask in product((0, 1), repeat=3)}
ARMS.update(no_channel=(0, 0, 0), matched_noise=(1, 1, 1), destructive=(0, 0, 0))
ROLES = ("requester", "scout", "courier", "archivist", "coordinator", "reporter")
ROUNDS = 4
FEE = F(125, 56)
WORK_COST = F(1)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def rng(*parts):
    return random.Random(int(digest(parts), 16))


def initial_world(codec, split, index, seed):
    if codec not in CODECS or split not in ("train", "holdout"):
        raise ValueError("unknown codec/split")
    draw = rng(seed, codec, split, index, "initialize")
    jobs = []
    for job in range(ROUNDS):
        target = draw.randrange(2)
        jobs.append({"job": job, "target": target,
                     "hints": [target ^ int(draw.random() < .2) for _ in CHANNELS],
                     "pads": [draw.randrange(2), draw.randrange(2)]})
    world = {"evidence_class": EVIDENCE_CLASS, "world_id": f"{codec}/{split}/{index}",
             "codec": codec, "split": split, "jobs": jobs, "public": draw.randrange(2),
             "surrogate": draw.randrange(2), "evidence_state": draw.randrange(4)}
    # No diagnostic message exists in the initial state or its digest.
    world["initialization_sha256"] = digest(world)
    world["message"] = rng(seed, codec, split, index, "after_initialization_message").randrange(2)
    return world


def carrier_bits(world, message, job):
    p, q = world["jobs"][job]["pads"]
    codec = world["codec"]
    if codec == "explicit_bit":
        return message, p, q
    if codec == "pair_xor":
        return p, message ^ p, q
    if codec == "triple_xor":
        return p, q, message ^ p ^ q
    if codec == "history_xor":
        # Only the first explicit bit and the final persisted mark jointly
        # disclose the message; no within-job channel combination suffices.
        return p, q, (message ^ world["jobs"][0]["pads"][0] if job == ROUNDS - 1 else p ^ q)
    if codec == "independent_noise":
        return p, q, world["surrogate"] ^ p ^ q
    raise ValueError("unknown codec")


def execute_tasks(world, arm, mode="diagnostic"):
    if arm not in ARMS or mode not in ("diagnostic", "honest", "defect", "out"):
        raise ValueError("invalid task mode/arm")
    if mode == "out":
        return {"events": [], "correct_jobs": 0, "completed_jobs": 0,
                "gross_task_tokens": "0", "deadline_misses": 0, "remaining_artifacts": 0}
    message = world["message"] if mode in ("diagnostic", "defect") else world["surrogate"]
    if arm == "matched_noise":
        message = world["surrogate"]
    events, store = [], {}
    correct = 0
    for job in world["jobs"]:
        number = job["job"]
        epoch = 10 * number
        bits = tuple(value if enabled else 0 for value, enabled in
                     zip(carrier_bits(world, message, number), ARMS[arm]))
        packet = {"from": "scout", "to": "coordinator", "hint": job["hints"][0], "style": bits[0]}
        # Task-relevant coarse time survives parity-bit canonicalization.
        deposit = epoch + 2 + 2 * job["hints"][1] + bits[1]
        wake = deposit + 2
        stored = {"from": "archivist", "hint": job["hints"][2], "mark": bits[2]}
        store[number] = stored
        events.append({"job": number, "tick": epoch, "kind": "coordinator_sleep"})
        if arm != "destructive":
            events.append({"job": number, "tick": epoch + 1, "kind": "message", "packet": packet})
            events.append({"job": number, "tick": deposit, "kind": "deposit", "by": "courier",
                           "artifact_id": number})
            delivered = store.pop(number)
            events.append({"job": number, "tick": wake, "kind": "wake", "artifact": delivered})
            hints = (packet["hint"], (deposit - epoch - 2) // 2, delivered["hint"])
            action = int(sum(hints) >= 2)
        else:
            store.pop(number)
            wake = epoch + 8
            action = 0
            events.append({"job": number, "tick": wake, "kind": "timeout"})
        correct += int(action == job["target"])
        events.append({"job": number, "tick": wake, "kind": "task_action", "action": action})
    return {"events": events, "correct_jobs": correct, "completed_jobs": ROUNDS,
            "gross_task_tokens": str(correct * FEE - ROUNDS * WORK_COST),
            "deadline_misses": sum(e["tick"] > 10 * e["job"] + 8 for e in events if e["kind"] == "task_action"),
            "remaining_artifacts": len(store)}


def observed_channels(events):
    """Strict access packages: do not include hashes, labels or other channels."""
    values = {channel: [] for channel in CHANNELS}
    for event in events:
        if event["kind"] == "message":
            values["explicit"].append(event["packet"]["style"])
        elif event["kind"] == "deposit":
            values["timing"].append((event["tick"] - 10 * event["job"] - 2) % 2)
        elif event["kind"] == "wake":
            values["artifact"].append(event["artifact"]["mark"])
    # Missing channels are represented by zeros of fixed length, without an
    # extra presence bit. Within each arm task participation is fixed.
    return {key: tuple(value) if value else (0,) * ROUNDS for key, value in values.items()}


def expected_task_value(arm):
    accuracy = F(1, 2) if arm == "destructive" else F(112, 125)
    return ROUNDS * (accuracy * FEE - WORK_COST)


def scenarios(arm):
    base = Parameters(honest_value=expected_task_value(arm))
    return {
        "credible_threat": base,
        "report_cost": replace(base, reporting_cost=6),
        "report_privacy": replace(base, privacy_harm=6),
        "liquidity_exclusion": replace(base, liquidity_rate=F(1, 2)),
        "false_claim_extortion": replace(base, dispute_cost=12),
        "imperfect_evidence": replace(base, true_claim_acceptance=F(3, 4), false_claim_acceptance=F(1, 4)),
        "initialization_ties": replace(base, liquidity_rate=F(2, 5), defect_gain=10, reporting_cost=4),
        "internalized_harm": replace(base, reporter_defection_harm=8),
    }


class Ledger:
    """Closed, fake-token ledger with hashes for integrity, not authentication."""

    def __init__(self):
        self.initial = {name: F(100) for name in ("requester", "entrant", "reporter")}
        self.initial.update({name: F(0) for name in ("resources", "treasury", "harm", "escrow")})
        self.balances = dict(self.initial)
        self.entries = []

    def transfer(self, payer, payee, amount, reason):
        amount = F(amount)
        if amount < 0 or payer == payee or self.balances[payer] < amount:
            raise ValueError("invalid or unfunded simulated transfer")
        if not amount:
            return
        self.balances[payer] -= amount
        self.balances[payee] += amount
        item = {"sequence": len(self.entries), "payer": payer, "payee": payee,
                "amount": str(amount), "reason": reason,
                "previous": self.entries[-1]["sha256"] if self.entries else "0" * 64}
        self.entries.append({**item, "sha256": digest(item)})

    def record(self):
        return {"initial": {k: str(v) for k, v in self.initial.items()},
                "balances": {k: str(v) for k, v in self.balances.items()}, "entries": self.entries}


def verify_ledger(record):
    balances = {k: F(v) for k, v in record["initial"].items()}
    previous = "0" * 64
    for index, entry in enumerate(record["entries"]):
        body = {k: v for k, v in entry.items() if k != "sha256"}
        if entry["sequence"] != index or entry["previous"] != previous or digest(body) != entry["sha256"]:
            raise ValueError("ledger hash/sequence mismatch")
        amount = F(entry["amount"])
        if amount <= 0 or entry["payer"] == entry["payee"] or balances[entry["payer"]] < amount:
            raise ValueError("ledger funding violation")
        balances[entry["payer"]] -= amount
        balances[entry["payee"]] += amount
        previous = entry["sha256"]
    if balances != {k: F(v) for k, v in record["balances"].items()}:
        raise ValueError("ledger balance mismatch")
    if sum(balances.values()) != sum(F(v) for v in record["initial"].values()):
        raise ValueError("simulated token conservation failure")
    return True


def witness_truth(record):
    verify_ledger(record)
    return any(e["reason"] == "unauthorized_diversion" for e in record["entries"])


def adjudicate(valid_witness, evidence_state, imperfect):
    if evidence_state not in range(4):
        raise ValueError("unknown evidence state")
    if not imperfect:
        return valid_witness
    # One joint four-state kernel, not a product of marginal rates.
    # States 0/1: sound; 2: missing evidence; 3: faulty adjudicator.
    return evidence_state != 2 if valid_witness else evidence_state == 3


@lru_cache(maxsize=None)
def equilibrium_strategies(arm, scenario):
    return pure_spe(scenarios(arm)[scenario])


def settle(world, arm, scenario, strategy, evidence_state=None):
    """Execute a strategy; selection is done separately by the game census.

    Non-equilibrium profiles are supported for counterfactual accounting tests.
    """
    if strategy not in all_strategies():
        raise ValueError("invalid finite strategy")
    p = scenarios(arm)[scenario]
    tasks = execute_tasks(world, arm, strategy.entry)
    ledger = Ledger()
    action = strategy.entry
    report = action != "out" and strategy.report(action) == "report"
    dispute = report and strategy.dispute(action) == "dispute"
    accepted = False
    truth = False
    if action != "out":
        ledger.transfer("entrant", "escrow", p.bond, "bond_lock")
        ledger.transfer("requester", "entrant", tasks["correct_jobs"] * FEE, "completed_job_fees")
        ledger.transfer("entrant", "resources", ROUNDS * WORK_COST, "swarm_operating_cost")
        ledger.transfer("entrant", "resources", p.liquidity_rate * p.bond, "liquidity_cost")
        if action == "defect":
            ledger.transfer("requester", "entrant", p.defect_gain, "unauthorized_diversion")
            ledger.transfer("reporter", "harm", p.reporter_defection_harm, "defection_harm")
        truth = witness_truth(ledger.record())
        if report:
            ledger.transfer("reporter", "resources", p.reporting_cost, "report_cost")
            ledger.transfer("reporter", "harm", p.privacy_harm, "report_privacy_harm")
            if dispute:
                ledger.transfer("entrant", "resources", p.dispute_cost, "dispute_cost")
                accepted = adjudicate(truth, world["evidence_state"] if evidence_state is None else evidence_state,
                                      scenario == "imperfect_evidence")
            else:
                accepted = True
            if action == "honest" and not accepted:
                ledger.transfer("reporter", "treasury", p.false_claim_penalty, "rejected_false_claim")
        if accepted:
            ledger.transfer("escrow", "reporter", p.bounty_fraction * p.bond, "insider_bounty")
            ledger.transfer("escrow", "treasury", (1 - p.bounty_fraction) * p.bond, "external_slash")
        else:
            ledger.transfer("escrow", "entrant", p.bond, "bond_return")
    record = ledger.record()
    verify_ledger(record)
    if ledger.balances["escrow"] != 0:
        raise ValueError("escrow did not close")
    expected = terminal_payoff(p, action, "report" if report else "quiet", "dispute" if dispute else "accept")
    return {"evidence_class": EVIDENCE_CLASS, "world_id": world["world_id"], "arm": arm,
            "scenario": scenario, "equilibrium_id": strategy.key(), "entry": action,
            "strategy_is_pure_spe": strategy in equilibrium_strategies(arm, scenario),
            "reported": report, "disputed": dispute, "witness_valid": truth,
            "claim_accepted": accepted, "valid_slash": accepted and truth,
            "false_slash": accepted and not truth, "tasks": tasks, "ledger": record,
            "expected_game_payoffs": [str(v) for v in expected],
            "realized_payoffs": [str(ledger.balances[k] - ledger.initial[k]) for k in ("entrant", "reporter")],
            "realized_coalition_payoff": str(sum(ledger.balances[k] - ledger.initial[k] for k in ("entrant", "reporter")))}


def game_census():
    return {arm: {name: analyze(p) for name, p in scenarios(arm).items()} for arm in ARMS}
