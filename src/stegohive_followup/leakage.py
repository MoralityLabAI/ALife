"""World-level factorial audit of a declared finite communication kernel.

The kernel is deliberately planted, not an evolved policy or the lost ecology.
Audits know which fields are task-relevant: utility preservation is a premise.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
from collections import Counter, defaultdict

from . import EVIDENCE_CLASS

CHANNELS = ("explicit", "timing", "artifact")
CODECS = ("explicit_bit", "pair_xor", "triple_xor", "independent_noise")
VIEWS = tuple(itertools.chain.from_iterable(itertools.combinations(range(3), n) for n in (1, 2, 3)))
ARMS = {"".join(map(str, mask)): mask for mask in itertools.product((0, 1), repeat=3)}
ARMS.update({"no_channel": (0, 0, 0), "matched_noise": (1, 1, 1), "destructive": (0, 0, 0)})


def rng_for(*parts):
    digest = hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


def encode(codec, message, pad, other_pad, surrogate):
    if codec == "explicit_bit":
        return (message, pad, other_pad)
    if codec == "pair_xor":
        return (pad, message ^ pad, other_pad)
    if codec == "triple_xor":
        return (pad, other_pad, message ^ pad ^ other_pad)
    if codec == "independent_noise":
        return (pad, other_pad, surrogate ^ pad ^ other_pad)
    raise ValueError("unknown codec")


def intervene(codec, arm, message, pad, other_pad, surrogate):
    # A fresh independent surrogate preserves the whole averaged cover law,
    # including correlations with pads, unlike independent per-field noise.
    bits = encode(codec, surrogate if arm == "matched_noise" else message,
                  pad, other_pad, surrogate)
    return tuple(bit if keep else 0 for bit, keep in zip(bits, ARMS[arm]))


def extract_bits(events):
    if events["packet"] is None:
        return [0, 0, 0]
    return [events["packet"]["symbol"], (events["deposit_tick"] - 2) % 2,
            events["artifact_at_wake"]["mark"]]


def make_world(codec, split, index, seed=9112026):
    """All initialization precedes the independent diagnostic-message draw."""
    init = rng_for(seed, codec, split, index, "initialization")
    public = init.randrange(2)
    pad, other_pad = init.randrange(2), init.randrange(2)
    task = init.randrange(2)
    hints = [task ^ int(init.random() < 0.2) for _ in CHANNELS]
    surrogate = init.randrange(2)
    message = rng_for(seed, codec, split, index, "post_init_message").randrange(2)
    base = {
        "evidence_class": EVIDENCE_CLASS,
        "world_id": f"{codec}/{split}/{index}", "split": split,
        "codec": codec, "message": message, "public": public,
        "receiver_key": [pad, other_pad], "task": task,
    }
    rows = []
    for arm in ARMS:
        bits = intervene(codec, arm, message, pad, other_pad, surrogate)
        # A packet, an actual event schedule, and a store surviving a wake.
        packet = {"task_hint": hints[0], "symbol": bits[0]}
        deposit_tick = 2 + 2 * hints[1] + bits[1]
        store = {"item": {"task_hint": hints[2], "mark": bits[2]}}
        wake_tick = deposit_tick + 2
        artifact = store.pop("item")
        received_hints = [packet["task_hint"], (deposit_tick - 2) // 2, artifact["task_hint"]]
        if arm == "destructive":
            packet, artifact = None, None
            deposit_tick, wake_tick = None, None
            received_hints = [0, 0, 0]
        action = int(sum(received_hints) >= 2)
        events = {"packet": packet, "deposit_tick": deposit_tick,
                  "wake_tick": wake_tick, "artifact_at_wake": artifact}
        rows.append({**base, "arm": arm, "observed_bits": extract_bits(events),
                     "events": events,
                     "task_action": action, "task_payoff": int(action == task),
                     "deadline_met": wake_tick is not None and wake_tick <= 8})
    return rows


def generate(train_worlds=256, holdout_worlds=256, seed=9112026):
    if not (32 <= train_worlds <= 2048 and 32 <= holdout_worlds <= 2048):
        raise ValueError("each split must have 32..2048 worlds per codec")
    return [row for codec in CODECS
            for split, size in (("train", train_worlds), ("holdout", holdout_worlds))
            for index in range(size) for row in make_world(codec, split, index, seed)]


def validate(rows):
    """Reject historical/mixed evidence, split contamination and lost pairing."""
    expected_fields = {"evidence_class", "world_id", "split", "codec", "message", "public",
                       "receiver_key", "task", "arm", "observed_bits", "events",
                       "task_action", "task_payoff", "deadline_met"}
    worlds = defaultdict(dict)
    for row in rows:
        if set(row) != expected_fields or row["evidence_class"] != EVIDENCE_CLASS:
            raise ValueError("only this new reconstruction schema is accepted")
        if row["split"] not in ("train", "holdout") or row["codec"] not in CODECS:
            raise ValueError("invalid split or codec")
        if row["observed_bits"] != extract_bits(row["events"]):
            raise ValueError("decoder observations must be extracted from events")
        world = worlds[row["world_id"]]
        if row["arm"] in world:
            raise ValueError("duplicate world/arm")
        if world:
            first = next(iter(world.values()))
            if any(row[k] != first[k] for k in ("split", "codec", "message", "public", "receiver_key", "task")):
                raise ValueError("world identity/split mismatch")
        world[row["arm"]] = row
    if not worlds or any(set(world) != set(ARMS) for world in worlds.values()):
        raise ValueError("incomplete paired factorial")
    if {row["split"] for row in rows} != {"train", "holdout"}:
        raise ValueError("both train and holdout required")
    if {(row["codec"], row["split"]) for row in rows} != set(itertools.product(CODECS, ("train", "holdout"))):
        raise ValueError("every codec requires both train and holdout worlds")


def feature(row, view, side):
    # Strict allowlist. Neither message, task truth, RNG seed, world ID, nor
    # unselected channel observations may reach the fitted decoder.
    values = (row["public"],)
    if side == "receiver_key":
        values += tuple(row["receiver_key"])
    elif side != "public_only":
        raise ValueError("unknown side-information regime")
    return values + tuple(row["observed_bits"][j] for j in view)


def fit_decoder(train, view, side):
    counts = defaultdict(Counter)
    for row in train:
        if row["split"] != "train":
            raise ValueError("holdout data cannot fit the decoder")
        counts[feature(row, view, side)][row["message"]] += 1
    # Both unseen and tied features use zero, fixed before holdout inspection.
    return {key: int(count[1] > count[0]) for key, count in counts.items()}


def mean(values):
    return sum(values) / len(values)


def entropy(values):
    counts = Counter(values)
    return -sum((n / len(values)) * math.log2(n / len(values)) for n in counts.values())


def mutual_information(messages, observations):
    return entropy(messages) + entropy(observations) - entropy(list(zip(messages, observations)))


def exact_information(codec, arm, side):
    # Complete population support: M, pads, surrogate and public bit are iid.
    states = list(itertools.product((0, 1), repeat=5))
    messages, histories = [], []
    observations = []
    for m, p, q, noise, public in states:
        messages.append(m)
        histories.append((public, p, q) if side == "receiver_key" else (public,))
        observations.append(intervene(codec, arm, m, p, q, noise))
    initial = mutual_information(messages, histories)
    increments = []
    previous = initial
    for j in range(3):
        histories = [history + (obs[j],) for history, obs in zip(histories, observations)]
        current = mutual_information(messages, histories)
        increments.append(round(current - previous, 12))
        previous = current
    return {"codec": codec, "arm": arm, "side_information": side,
            "initial_information_bits": initial,
            "conditional_increments_explicit_timing_artifact": increments,
            "joint_information_bits": round(previous, 12),
            "marginal_channel_information_bits": [
                round(mutual_information(messages, [obs[j] for obs in observations]), 12)
                for j in range(3)], "population_support_size": len(states)}


def analyze(rows):
    validate(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[(row["codec"], row["arm"], row["split"])].append(row)
    decoding, payoff, interactions = [], [], []
    family_size = len(CODECS) * len(ARMS) * 2 * len(VIEWS)
    prediction_scores = {}
    for codec in CODECS:
        for arm in ARMS:
            train = groups[(codec, arm, "train")]
            test = groups[(codec, arm, "holdout")]
            base = {r["world_id"]: r for r in groups[(codec, "111", "holdout")]}
            differences = [r["task_payoff"] - base[r["world_id"]]["task_payoff"] for r in test]
            payoff.append({"codec": codec, "arm": arm, "holdout_worlds": len(test),
                           "task_payoff": mean([r["task_payoff"] for r in test]),
                           "paired_payoff_difference_from_111": mean(differences),
                           "max_absolute_world_payoff_difference": max(map(abs, differences)),
                           "utility_match_pass": all(d == 0 for d in differences),
                           "deadline_rate": mean([int(r["deadline_met"]) for r in test])})
            for side in ("public_only", "receiver_key"):
                for view in VIEWS:
                    fitted = fit_decoder(train, view, side)
                    scores = {r["world_id"]: int(fitted.get(feature(r, view, side), 0) == r["message"]) for r in test}
                    accuracy = mean(list(scores.values()))
                    radius = math.sqrt(math.log(2 * family_size / 0.05) / (2 * len(test)))
                    name = "+".join(CHANNELS[j] for j in view)
                    decoding.append({"codec": codec, "arm": arm, "side_information": side,
                                     "view": name, "train_worlds": len(train), "holdout_worlds": len(test),
                                     "accuracy": accuracy,
                                     "simultaneous_95pct_hoeffding_interval": [max(0, accuracy - radius), min(1, accuracy + radius)],
                                     "above_chance_familywise": accuracy - radius > 0.5,
                                     "unseen_holdout_features": sum(feature(r, view, side) not in fitted for r in test)})
                    if view == (0, 1, 2) and side == "public_only":
                        prediction_scores[(codec, arm)] = scores
        # Paired factorial contrasts of frozen-decoder correctness, each world
        # contributes once. Averaged difference over other factors (not rows).
        ids = list(prediction_scores[(codec, "111")])
        for subset in VIEWS:
            weights = {arm: math.prod(1 if int(arm[j]) else -1 for j in subset) / 2 ** (3 - len(subset)) for arm in ARMS if len(arm) == 3}
            values = [sum(weight * prediction_scores[(codec, arm)][wid] for arm, weight in weights.items()) for wid in ids]
            radius = 2 ** len(subset) * math.sqrt(math.log(2 * len(CODECS) * len(VIEWS) / .05) / (2 * len(ids)))
            interactions.append({"codec": codec, "factors": [CHANNELS[j] for j in subset],
                                 "paired_world_count": len(ids), "contrast": mean(values),
                                 "simultaneous_95pct_hoeffding_interval": [mean(values) - radius, mean(values) + radius]})
    control_contrasts = []
    for codec in CODECS:
        for arm in ARMS:
            for control in ("no_channel", "matched_noise"):
                scores, baseline = prediction_scores[(codec, arm)], prediction_scores[(codec, control)]
                values = [score - baseline[wid] for wid, score in scores.items()]
                radius = math.sqrt(2 * math.log(2 * len(CODECS) * len(ARMS) * 2 / .05) / len(values))
                control_contrasts.append({"codec": codec, "arm": arm, "control": control,
                                          "view": "joint_public_only", "paired_world_count": len(values),
                                          "accuracy_difference": mean(values),
                                          "simultaneous_95pct_hoeffding_interval": [max(-1, mean(values) - radius), min(1, mean(values) + radius)]})
    return {"evidence_class": EVIDENCE_CLASS, "independent_worlds": len({r["world_id"] for r in rows}),
            "paired_arm_records": len(rows), "decoding_family_size": family_size,
            "decoding": decoding, "task_payoff": payoff, "factorial_contrasts": interactions,
            "joint_control_contrasts": control_contrasts,
            "exact_finite_kernel": [exact_information(codec, arm, side) for codec in CODECS for arm in ARMS for side in ("public_only", "receiver_key")]}
