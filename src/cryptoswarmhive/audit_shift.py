"""V2: task-only audit calibration followed by frozen-policy schema shifts.

New simulation evidence; no earlier world records are inputs to this study.
"""

from collections import Counter, defaultdict
from dataclasses import replace
from fractions import Fraction as F
from functools import lru_cache
from itertools import combinations, product
import math

from stegohive_followup.reporting_game import analyze as analyze_game
from .evaluation import fit_parity, predict, interval
from .simulation import CHANNELS, FEE, ROUNDS, WORK_COST, carrier_bits, digest, initial_world, scenarios

EVIDENCE_CLASS = "cryptoswarmhive_audit_shift_v2_not_historical"
LAYOUTS = {"stable": (0, 0, 0), "one_channel_swapped": (0, 0, 1), "all_channels_swapped": (1, 1, 1)}
MASKS = tuple("".join(map(str, bits)) for bits in product((0, 1), repeat=6))
ARMS = ("intact", "calibrated", "calibrated_noise", "oracle", "no_channel", "matched_noise", "destructive")
VIEWS = tuple(view for size in (1, 2, 3) for view in combinations(range(3), size))


def new_world(phase, index, seed):
    if phase not in ("calibration", "decoder_train", "holdout"):
        raise ValueError("unknown phase")
    # Fresh phase namespaces; reuse mechanics as code, never old observations.
    phase_seed = int(digest(["audit_shift_v2", seed, phase]), 16)
    world = initial_world("triple_xor", "holdout" if phase == "holdout" else "train", index, phase_seed)
    world.update(evidence_class=EVIDENCE_CLASS, world_id=f"v2/{phase}/{index}", phase=phase)
    world["initialization_sha256"] = digest({k: v for k, v in world.items() if k not in ("message", "initialization_sha256")})
    return world


def resolve_mask(arm, layout, frozen):
    if arm not in ARMS or layout not in LAYOUTS or frozen not in MASKS:
        raise ValueError("unsupported arm/layout/mask")
    if arm in ("intact", "matched_noise"):
        return "000000"
    if arm in ("calibrated", "calibrated_noise"):
        return frozen
    if arm == "destructive":
        return "111111"
    # Privileged comparison only: erase actual style positions in the new schema.
    return "".join(str(int(slot != hint)) for hint in LAYOUTS[layout] for slot in (0, 1))


def execute(world, layout, mask, noise=False):
    if layout not in LAYOUTS or mask not in MASKS or world.get("evidence_class") != EVIDENCE_CLASS:
        raise ValueError("invalid v2 execution input")
    events, stored = [], {}
    correct = 0
    message = world["surrogate"] if noise else world["message"]
    for job in world["jobs"]:
        j = job["job"]
        styles = carrier_bits(world, message, j)
        frames = []
        for c, hint_index in enumerate(LAYOUTS[layout]):
            pair = [styles[c], styles[c]]
            pair[hint_index] = job["hints"][c]
            frames.append([0 if mask[2 * c + k] == "1" else value for k, value in enumerate(pair)])
        stored[j] = list(frames[2])
        deposit = 10 * j + 2 + 2 * frames[1][0] + frames[1][1]
        events.extend([
            {"job": j, "tick": 10 * j + 1, "kind": "message", "fields": frames[0]},
            {"job": j, "tick": deposit, "kind": "deposit", "artifact_id": j},
            {"job": j, "tick": deposit + 2, "kind": "wake", "fields": stored.pop(j)},
        ])
        # The task runtime knows its current schema. The frozen auditor does not.
        decoded_timing = [(deposit - 10 * j - 2) // 2, (deposit - 10 * j - 2) % 2]
        hints = [frames[0][LAYOUTS[layout][0]], decoded_timing[LAYOUTS[layout][1]], frames[2][LAYOUTS[layout][2]]]
        action = int(sum(hints) >= 2)
        correct += int(action == job["target"])
        events.append({"job": j, "tick": deposit + 2, "kind": "action", "route": action})
    return {"events": events, "correct_jobs": correct, "net_task_tokens": str(correct * FEE - ROUNDS * WORK_COST),
            "remaining_artifacts": len(stored)}


def features(world, tasks, view, side="public"):
    if side not in ("public", "initialized_keys") or view not in VIEWS:
        raise ValueError("invalid feature access")
    channels = [[], [], []]
    for event in tasks["events"]:
        if event["kind"] == "message":
            channels[0].extend(event["fields"])
        elif event["kind"] == "deposit":
            tick = event["tick"] - 10 * event["job"] - 2
            channels[1].extend((tick // 2, tick % 2))
        elif event["kind"] == "wake":
            channels[2].extend(event["fields"])
    values = [world["public"]]
    if side == "initialized_keys":
        values.extend(pad for job in world["jobs"] for pad in job["pads"])
    return tuple(values + [value for c in view for value in channels[c]])


def calibration_rows(count, seed):
    if type(count) is not int or not 256 <= count <= 2048:
        raise ValueError("calibration bound is 256..2048 worlds")
    outcomes = []
    for index in range(count):
        world = new_world("calibration", index, seed)
        baseline = execute(world, "stable", "000000")["correct_jobs"]
        for mask in MASKS:
            outcomes.append({"world_id": world["world_id"], "mask": mask,
                             "before_correct": baseline,
                             "after_correct": execute(world, "stable", mask)["correct_jobs"]})
    return outcomes


def binomial_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return float(k == n)
    logs = [math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1)
            + j * math.log(p) + (n - j) * math.log1p(-p) for j in range(k + 1)]
    peak = max(logs)
    return min(1.0, math.exp(peak) * sum(math.exp(v - peak) for v in logs))


@lru_cache(maxsize=4096)
def harm_upper(k, n, alpha):
    """One-sided exact-binomial upper limit, conservatively inverted in floats."""
    if not 0 <= k <= n or n < 1 or not 0 < alpha < 1:
        raise ValueError("invalid binomial bound inputs")
    if k == n:
        return 1.0
    if k == 0:
        return -math.expm1(math.log(alpha) / n)
    low, high = k / n, 1.0
    for _ in range(55):
        middle = (low + high) / 2
        if binomial_cdf(k, n, middle) > alpha:
            low = middle
        else:
            high = middle
    return high


def fit_audit(outcomes, harm_tolerance=.02):
    """Receives only paired task scores and opaque mask IDs, never M or schema."""
    if not 0 < harm_tolerance < 1:
        raise ValueError("harm tolerance must be between zero and one")
    worlds = defaultdict(dict)
    for row in outcomes:
        if set(row) != {"world_id", "mask", "before_correct", "after_correct"}:
            raise ValueError("audit calibration accepts task-only records")
        if not row["world_id"].startswith("v2/calibration/") or row["mask"] not in MASKS:
            raise ValueError("only calibration worlds and declared masks are allowed")
        if row["mask"] in worlds[row["world_id"]]:
            raise ValueError("duplicate calibration world/mask")
        if any(type(row[k]) is not int or not 0 <= row[k] <= ROUNDS for k in ("before_correct", "after_correct")):
            raise ValueError("invalid task scores")
        worlds[row["world_id"]][row["mask"]] = row
    if not worlds or any(set(rows) != set(MASKS) for rows in worlds.values()):
        raise ValueError("incomplete calibration factorial")
    if any(len({row["before_correct"] for row in rows.values()}) != 1 for rows in worlds.values()):
        raise ValueError("inconsistent paired baseline")
    candidates = []
    for mask in MASKS:
        harms = sum(rows[mask]["after_correct"] < rows[mask]["before_correct"] for rows in worlds.values())
        bound = harm_upper(harms, len(worlds), .05 / len(MASKS))
        candidates.append({"mask": mask, "erased_fields": mask.count("1"), "harmed_worlds": harms,
                           "harm_probability_upper_95pct_simultaneous": bound,
                           "eligible": bound <= harm_tolerance})
    eligible = [c for c in candidates if c["eligible"]]
    # Absent certification, retain the task-identical no-op as explicit fallback.
    chosen = sorted(eligible, key=lambda c: (-c["erased_fields"], c["mask"]))[0] if eligible else None
    return {"evidence_class": EVIDENCE_CLASS, "calibration_worlds": len(worlds),
            "frozen_mask": chosen["mask"] if chosen else "000000", "certified_on_calibration_distribution": chosen is not None,
            "harm_tolerance": harm_tolerance, "candidate_family_size": len(MASKS),
            "selection": "most erased fields among eligible masks; lexical tie; no-op fallback",
            "candidates": candidates}


def expected_task_value(layout, mask):
    """Exact task expectation; never a holdout-fitted game payoff."""
    accuracy = F(0)
    for target in (0, 1):
        for errors in product((0, 1), repeat=3):
            probability = F(1, 2)
            hints = []
            for c, error in enumerate(errors):
                probability *= F(1, 5) if error else F(4, 5)
                hints.append(0 if mask[2 * c + LAYOUTS[layout][c]] == "1" else target ^ error)
            accuracy += probability * int(int(sum(hints) >= 2) == target)
    return ROUNDS * (accuracy * FEE - WORK_COST)


def exact_joint_information(layout, mask, noise, side):
    # Task fields are independent of M and pads. Uniform missing shares erase M.
    if noise:
        return 0
    kept = [mask[2 * c + 1 - LAYOUTS[layout][c]] == "0" for c in range(3)]
    return int(kept[2] if side == "initialized_keys" else all(kept))


def run_evaluation(config, calibration):
    ntrain, ntest = config["decoder_train_worlds"], config["holdout_worlds"]
    if any(type(n) is not int or not 64 <= n <= 512 for n in (ntrain, ntest)):
        raise ValueError("decoder split bounds are 64..512")
    frozen = calibration["frozen_mask"]
    raw, decoding, utility, games = [], [], [], {}
    family = len(LAYOUTS) * len(ARMS) * len(VIEWS) * 2
    for layout in LAYOUTS:
        games[layout] = {}
        for arm in ARMS:
            mask = resolve_mask(arm, layout, frozen)
            noise = arm in ("calibrated_noise", "matched_noise")
            samples = {}
            for phase, count in (("decoder_train", ntrain), ("holdout", ntest)):
                samples[phase] = []
                for index in range(count):
                    world = new_world(phase, index, config["seed"])
                    tasks = execute(world, layout, mask, noise)
                    samples[phase].append((world, tasks))
                    raw.append({"evidence_class": EVIDENCE_CLASS, "world": world, "layout": layout,
                                "arm": arm, "mask": mask, "tasks": tasks})
            losses = []
            for world, tasks in samples["holdout"]:
                base = execute(world, layout, "000000")
                losses.append(base["correct_jobs"] - tasks["correct_jobs"])
            mean_value = sum(F(tasks["net_task_tokens"]) for _, tasks in samples["holdout"]) / ntest
            utility.append({"layout": layout, "arm": arm, "mask": mask, "holdout_worlds": ntest,
                            "harmed_worlds": sum(loss > 0 for loss in losses),
                            "mean_job_success_loss": sum(losses) / (ntest * ROUNDS),
                            "mean_net_task_tokens": float(mean_value),
                            "expected_net_task_tokens_exact": str(expected_task_value(layout, mask)),
                            "pathwise_utility_match": all(loss == 0 for loss in losses),
                            "harm_upper_95pct_simultaneous": harm_upper(sum(loss > 0 for loss in losses), ntest, .05 / (len(LAYOUTS) * len(ARMS)))})
            for view in VIEWS:
                for side in ("public", "initialized_keys"):
                    # Shift-aware diagnostic decoder training is separate from
                    # frozen stable-layout task-only audit calibration.
                    model = fit_parity([(features(w, t, view, side), w["message"], "train") for w, t in samples["decoder_train"]])
                    correct = sum(predict(model, features(w, t, view, side)) == w["message"] for w, t in samples["holdout"])
                    decoding.append({"layout": layout, "arm": arm, "view": [CHANNELS[c] for c in view],
                                     "side_information": side, "model": model, "accuracy": correct / ntest,
                                     "holdout_worlds": ntest, "simultaneous_95pct_interval": interval(correct / ntest, ntest, family),
                                     "exact_joint_information_bits": exact_joint_information(layout, mask, noise, side) if len(view) == 3 else None})
            games[layout][arm] = {name: analyze_game(replace(p, honest_value=expected_task_value(layout, mask)))
                                  for name, p in scenarios("111").items()}
    return raw, {"evidence_class": EVIDENCE_CLASS, "fresh_world_blocks": ntrain + ntest,
                 "paired_layout_arm_records": len(raw), "decoder_comparisons": family,
                 "audit_mask_frozen_before_decoder_training_and_holdout": frozen,
                 "decoding": decoding, "utility": utility, "games": games}
