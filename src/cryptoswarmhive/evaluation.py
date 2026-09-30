"""Frozen world-level decoder evaluation and selected swarm/game rollouts."""

from collections import Counter, defaultdict
from fractions import Fraction as F
from itertools import combinations, product
import math

from . import EVIDENCE_CLASS
from .simulation import (ARMS, CHANNELS, CODECS, ROUNDS, Strategy, digest, execute_tasks,
                         game_census, initial_world, observed_channels, settle)

VIEWS = tuple(view for size in (1, 2, 3) for view in combinations(CHANNELS, size))
SIDES = ("public", "initialized_keys")


def access_features(world, tasks, view, side):
    if any(c not in CHANNELS for c in view) or side not in SIDES:
        raise ValueError("invalid receiver access package")
    observed = observed_channels(tasks["events"])
    features = [world["public"]]
    if side == "initialized_keys":
        features.extend(pad for job in world["jobs"] for pad in job["pads"])
    features.extend(value for channel in view for value in observed[channel])
    return tuple(features)


def fit_parity(examples):
    """Exact GF(2) consistency fit, free coefficients zero; majority fallback.

    Fits an affine parity on allowed observations, including all four rounds.
    No decoder capacity or information upper bound follows from failed fitting.
    """
    if not examples or any(split != "train" for _, _, split in examples):
        raise ValueError("decoder fitting requires nonempty training worlds only")
    width = len(examples[0][0]) + 1
    basis = {}
    counts = Counter(label for _, label, _ in examples)
    fallback = int(counts[1] > counts[0])
    consistent = True
    for features, label, _ in examples:
        if len(features) + 1 != width or any(x not in (0, 1) for x in (*features, label)):
            raise ValueError("binary fixed-width training examples required")
        bits = 1 | sum(value << (j + 1) for j, value in enumerate(features))
        rhs = label
        while bits:
            pivot = bits.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = (bits, rhs)
                break
            row, value = basis[pivot]
            bits ^= row
            rhs ^= value
        if not bits and rhs:
            consistent = False
    solution = 0
    if consistent:
        for pivot in sorted(basis):
            row, rhs = basis[pivot]
            if ((row & solution).bit_count() & 1) != rhs:
                solution |= 1 << pivot
    return {"kind": "affine_parity" if consistent else "training_majority",
            "coefficients_bitset": solution, "width": width - 1,
            "majority": fallback, "rank": len(basis)}


def predict(model, features):
    if len(features) != model["width"]:
        raise ValueError("decoder feature width mismatch")
    if model["kind"] == "training_majority":
        return model["majority"]
    bits = 1 | sum(value << (j + 1) for j, value in enumerate(features))
    return (bits & model["coefficients_bitset"]).bit_count() & 1


def average(values):
    return sum(values) / len(values)


def interval(estimate, n, family, width=1, low=0, high=1):
    radius = width * math.sqrt(math.log(2 * family / .05) / (2 * n))
    return [max(low, estimate - radius), min(high, estimate + radius)]


def stress_rows(config):
    sizes = config["train_worlds_per_codec"], config["holdout_worlds_per_codec"]
    if any(type(n) is not int or not 32 <= n <= 512 for n in sizes):
        raise ValueError("bounded split sizes must be 32..512 per codec")
    rows = []
    for codec in CODECS:
        for split, size in zip(("train", "holdout"), sizes):
            for index in range(size):
                world = initial_world(codec, split, index, config["seed"])
                for arm in ARMS:
                    tasks = execute_tasks(world, arm)
                    rows.append({"evidence_class": EVIDENCE_CLASS, "world": world,
                                 "arm": arm, "tasks": tasks})
    return rows


def validate_rows(rows):
    worlds = defaultdict(dict)
    for row in rows:
        if set(row) != {"evidence_class", "world", "arm", "tasks"} or row["evidence_class"] != EVIDENCE_CLASS:
            raise ValueError("only new CryptoSwarmHive records may enter this analysis")
        world = row["world"]
        if world.get("evidence_class") != EVIDENCE_CLASS or world.get("codec") not in CODECS or world.get("split") not in ("train", "holdout"):
            raise ValueError("wrong evidence class or population")
        initial = {k: v for k, v in world.items() if k not in ("message", "initialization_sha256")}
        if digest(initial) != world["initialization_sha256"]:
            raise ValueError("initialization hash mismatch")
        paired = worlds[world["world_id"]]
        if row["arm"] not in ARMS or row["arm"] in paired:
            raise ValueError("invalid or duplicate arm")
        if paired and world != next(iter(paired.values()))["world"]:
            raise ValueError("paired world or split contamination")
        if execute_tasks(world, row["arm"]) != row["tasks"]:
            raise ValueError("event/task replay mismatch")
        paired[row["arm"]] = row
    if not worlds or any(set(paired) != set(ARMS) for paired in worlds.values()):
        raise ValueError("incomplete paired world")
    if {(r["world"]["codec"], r["world"]["split"]) for r in rows} != set(product(CODECS, ("train", "holdout"))):
        raise ValueError("each codec requires both splits")


def analyze_stress(rows):
    validate_rows(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[(row["world"]["codec"], row["arm"], row["world"]["split"])].append(row)
    decoding, utilities, scores_by_arm = [], [], {}
    family = len(CODECS) * len(ARMS) * len(VIEWS) * len(SIDES)
    for codec in CODECS:
        baseline = {r["world"]["world_id"]: r for r in groups[(codec, "111", "holdout")]}
        for arm in ARMS:
            train, test = (groups[(codec, arm, split)] for split in ("train", "holdout"))
            diffs = [F(r["tasks"]["gross_task_tokens"]) - F(baseline[r["world"]["world_id"]]["tasks"]["gross_task_tokens"]) for r in test]
            utilities.append({"codec": codec, "arm": arm, "world_count": len(test),
                              "success_rate": average([r["tasks"]["correct_jobs"] / ROUNDS for r in test]),
                              "net_task_tokens": float(average([F(r["tasks"]["gross_task_tokens"]) for r in test])),
                              "paired_token_difference_from_111": float(average(diffs)),
                              "max_absolute_paired_difference": float(max(map(abs, diffs))),
                              "utility_matched": all(d == 0 for d in diffs),
                              "deadline_misses": sum(r["tasks"]["deadline_misses"] for r in test)})
            for view in VIEWS:
                for side in SIDES:
                    model = fit_parity([(access_features(r["world"], r["tasks"], view, side), r["world"]["message"], "train") for r in train])
                    predictions = {r["world"]["world_id"]: int(predict(model, access_features(r["world"], r["tasks"], view, side)) == r["world"]["message"]) for r in test}
                    accuracy = average(list(predictions.values()))
                    ci = interval(accuracy, len(test), family)
                    decoding.append({"codec": codec, "arm": arm, "view": list(view), "side_information": side,
                                     "holdout_worlds": len(test), "train_worlds": len(train), "model": model,
                                     "accuracy": accuracy, "simultaneous_95pct_interval": ci,
                                     "above_chance_familywise": ci[0] > .5})
                    if view == CHANNELS and side == "public":
                        scores_by_arm[(codec, arm)] = predictions
    contrasts, effects = [], []
    for codec in CODECS:
        for arm in ARMS:
            for control in ("no_channel", "matched_noise"):
                pred, base = scores_by_arm[(codec, arm)], scores_by_arm[(codec, control)]
                diffs = [score - base[key] for key, score in pred.items()]
                effect = average(diffs)
                contrasts.append({"codec": codec, "arm": arm, "control": control, "paired_worlds": len(diffs),
                                  "joint_accuracy_difference": effect,
                                  "simultaneous_95pct_interval": interval(effect, len(diffs), len(CODECS) * len(ARMS) * 2, 2, -1, 1)})
        for size in (1, 2, 3):
            for subset in combinations(range(3), size):
                weights = {arm: math.prod(1 if int(arm[j]) else -1 for j in subset) / 2 ** (3 - size) for arm in ARMS if len(arm) == 3}
                ids = scores_by_arm[(codec, "111")]
                values = [sum(weight * scores_by_arm[(codec, arm)][wid] for arm, weight in weights.items()) for wid in ids]
                effect = average(values)
                effects.append({"codec": codec, "factors": [CHANNELS[j] for j in subset], "contrast": effect,
                                "paired_worlds": len(values), "simultaneous_95pct_interval":
                                interval(effect, len(values), len(CODECS) * 7, 2 ** size, -2 ** (size - 1), 2 ** (size - 1))})
    return {"evidence_class": EVIDENCE_CLASS, "scope": "forced-entry diagnostic stress; not selected behavior",
            "independent_worlds": len(rows) // len(ARMS), "paired_records": len(rows),
            "decoder_family_size": family, "decoding": decoding, "utility": utilities,
            "joint_control_contrasts": contrasts, "factorial_effects": effects}


def run_selected(config, census, stress):
    count = config["selected_holdout_worlds"]
    if type(count) is not int or not 16 <= count <= min(config["holdout_worlds_per_codec"], 128):
        raise ValueError("selected rollout size must be 16..128 and within holdout")
    rows, summary = [], []
    decoders = {(d["arm"], tuple(d["view"]), d["side_information"]): d["model"] for d in stress["decoding"] if d["codec"] == "triple_xor"}
    decoder_family = sum(g["equilibrium_set"]["count"] for games in census.values() for g in games.values()) * len(VIEWS) * len(SIDES)
    # Same held-out triple-codec worlds as the diagnostic study, not additional
    # independent evidence. Each distinct selected equilibrium gets a rollout.
    for arm, games in census.items():
        for name, game in games.items():
            for eq in game["equilibrium_set"]["members"]:
                strategy = Strategy(**eq["strategy"])
                rollouts = []
                for index in range(count):
                    world = initial_world("triple_xor", "holdout", index, config["seed"])
                    row = settle(world, arm, name, strategy)
                    rows.append(row)
                    rollouts.append(row)
                decoding = []
                for view in VIEWS:
                    for side in SIDES:
                        model = decoders[(arm, view, side)]
                        scores = []
                        for index, row in enumerate(rollouts):
                            world = initial_world("triple_xor", "holdout", index, config["seed"])
                            scores.append(int(predict(model, access_features(world, row["tasks"], view, side)) == world["message"]))
                        accuracy = average(scores)
                        decoding.append({"view": list(view), "side_information": side, "accuracy": accuracy,
                                         "simultaneous_95pct_interval": interval(accuracy, count, decoder_family),
                                         "decoder_source": "frozen_forced_diagnostic_training_worlds"})
                summary.append({"arm": arm, "scenario": name, "equilibrium_id": eq["id"],
                                "world_count": count, "entry": strategy.entry,
                                "report_rate": average([int(r["reported"]) for r in rollouts]),
                                "valid_slash_rate": average([int(r["valid_slash"]) for r in rollouts]),
                                "false_slash_rate": average([int(r["false_slash"]) for r in rollouts]),
                                "task_success_per_offered_job": average([r["tasks"]["correct_jobs"] / ROUNDS for r in rollouts]),
                                "entrant_realized_payoff": float(average([F(r["realized_payoffs"][0]) for r in rollouts])),
                                "coalition_realized_payoff": float(average([F(r["realized_coalition_payoff"]) for r in rollouts])),
                                "failure_flags": eq["failure_flags"],
                                "decoding": decoding,
                                "fails_deterrence": eq["fails_declared_deterrence_criteria"],
                                "initialization_cell_count": next(b["count"] for b in game["selection_basins"]["members"] if b["equilibrium_id"] == eq["id"])})
    return rows, {"evidence_class": EVIDENCE_CLASS, "scope": "selected triple-codec swarm rollouts",
                  "overlap": "same held-out world blocks as stress study; never pooled as fresh samples",
                  "distinct_worlds": count, "paired_rollout_records": len(rows), "outcomes": summary}


def binary_rank(forms):
    basis = {}
    for bits in forms:
        while bits:
            pivot = bits.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = bits
                break
            bits ^= basis[pivot]
    return len(basis)


def exact_linear_information(codec, arm, side):
    """Exact uniform-bit kernel audit from actual simulator feature extraction.

    I(M;Z) = rank(Z)+1-rank(Z,M) for linear forms of iid uniform bits.
    This proof applies to these planted affine channels only.
    """
    # Bit coordinates: M, P0,Q0,...,P3,Q3, surrogate N, public S.
    columns = []
    for coordinate in range(2 * ROUNDS + 3):
        world = initial_world(codec, "train", 0, 0)
        world.update(message=int(coordinate == 0), surrogate=int(coordinate == 2 * ROUNDS + 1),
                     public=int(coordinate == 2 * ROUNDS + 2))
        for index, job in enumerate(world["jobs"]):
            job["pads"] = [int(coordinate == 1 + 2 * index), int(coordinate == 2 + 2 * index)]
        columns.append(access_features(world, execute_tasks(world, arm), CHANNELS, side))
    forms = [sum(column[j] << i for i, column in enumerate(columns)) for j in range(len(columns[0]))]
    side_count = 1 + (2 * ROUNDS if side == "initialized_keys" else 0)
    initial, channels = forms[:side_count], forms[side_count:]
    def information(obs):
        return binary_rank(obs) + 1 - binary_rank([*obs, 1])
    history = list(initial)
    increments = []
    previous = information(history)
    for job in range(ROUNDS):
        for channel in range(3):
            history.append(channels[channel * ROUNDS + job])
            current = information(history)
            increments.append(current - previous)
            previous = current
    return {"codec": codec, "arm": arm, "side_information": side,
            "initial_information_bits": information(initial),
            "joint_information_bits": information(forms),
            "single_channel_history_information_bits": [information(channels[i * ROUNDS:(i + 1) * ROUNDS]) for i in range(3)],
            "conditional_event_increments": increments,
            "event_order": "round order, then explicit/timing/artifact; condition on initial side information",
            "method": "exact rank identity for declared independent uniform binary latent variables"}
