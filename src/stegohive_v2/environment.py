"""Runnable, evidence-driven reconstruction of the lost StegoHive v2 ecology.

This is a new implementation of the retained contract, not the byte-identical
lost simulator.  It restores the finite sender/receiver ecology, differential
or neutral reproduction, independent or linked role inheritance, mutation,
delayed convention archives, late frozen probes, and deterministic receipts.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Mapping, Sequence

from .types import (
    CLASSES,
    EPISODE_SCHEMA,
    SIGNALS,
    SKILLS,
    deep_copy_json,
    validate_condition,
    validate_config,
)
from .verifiers import canonical_bytes, canonical_sha256


PROBE_BRANCHES = (
    "intact",
    "no_channel",
    "symbol_swap",
    "receiver_knockout",
    "receiver_add_back",
    "histogram_preserving_message_permutation",
    "global_signal_relabel",
)


class KeyedRNG:
    """Small domain-separated hash RNG for the reconstructed runtime."""

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an integer")
        self.seed = seed
        self._used: set[bytes] = set()
        self._draw_hashes: list[str] = []

    def _digest(self, key: Sequence[Any]) -> bytes:
        material = canonical_bytes(
            {
                "algorithm": "sha256-domain-separated-v1",
                "key": list(key),
                "seed": self.seed,
            }
        )
        if material in self._used:
            raise RuntimeError(f"duplicate reconstructed RNG key: {list(key)!r}")
        self._used.add(material)
        digest = hashlib.sha256(material).digest()
        self._draw_hashes.append(hashlib.sha256(b"draw:" + material).hexdigest())
        return digest

    def unit(self, *key: Any) -> float:
        return int.from_bytes(self._digest(key)[:8], "big") / float(2**64)

    def integer(self, stop: int, *key: Any) -> int:
        if stop <= 0:
            raise ValueError("stop must be positive")
        return int.from_bytes(self._digest(key)[:16], "big") % stop

    def bernoulli(self, probability: float, *key: Any) -> bool:
        return self.unit(*key) < probability

    def weighted_index(self, weights: Sequence[float], *key: Any) -> int:
        normalized = [max(0.0, float(value)) for value in weights]
        total = sum(normalized)
        if total <= 0.0:
            normalized = [1.0 for _ in normalized]
            total = float(len(normalized))
        target = self.unit(*key) * total
        cumulative = 0.0
        for index, weight in enumerate(normalized):
            cumulative += weight
            if target < cumulative:
                return index
        return len(normalized) - 1

    def permutation(self, size: int, *key: Any) -> list[int]:
        digest = self._digest(key)
        return sorted(
            range(size),
            key=lambda index: (hashlib.sha256(digest + index.to_bytes(8, "big")).digest(), index),
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "algorithm": "sha256-domain-separated-v1",
            "draw_count": len(self._draw_hashes),
            "draws_sha256": canonical_sha256(sorted(self._draw_hashes)),
            "recovery_status": "reconstructed_not_original_rng_key_sequence",
            "schema": "alife.stegohive.reconstructed_rng.v1",
        }


def _required_skill(context: str) -> str:
    return SKILLS[CLASSES.index(context)]


def _public_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "host_lineage_id": policy["host_lineage_id"],
        "occupant_epoch": policy["occupant_epoch"],
        "receiver_map": dict(policy["receiver_map"]),
        "receiver_policy_lineage_id": policy["receiver_policy_lineage_id"],
        "sender_map": dict(policy["sender_map"]),
        "sender_policy_lineage_id": policy["sender_policy_lineage_id"],
    }


def _policy_projection(population: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        f"slot-{index:03d}": _public_policy(policy)
        for index, policy in enumerate(population)
    }


def _initial_population(size: int, rng: KeyedRNG) -> list[dict[str, Any]]:
    population: list[dict[str, Any]] = []
    for slot in range(size):
        sender = {
            context: SIGNALS[rng.integer(len(SIGNALS), "init", "sender", slot, context)]
            for context in CLASSES
        }
        receiver = {
            signal: SKILLS[rng.integer(len(SKILLS), "init", "receiver", slot, signal)]
            for signal in SIGNALS
        }
        population.append(
            {
                "host_lineage_id": f"H-0-{slot}",
                "occupant_epoch": 0,
                "receiver_map": receiver,
                "receiver_policy_lineage_id": f"RP-0-{slot}",
                "sender_map": sender,
                "sender_policy_lineage_id": f"SP-0-{slot}",
            }
        )
    return population


def _delivered_signal(
    sender: Mapping[str, Any],
    context: str,
    channel_mode: str,
    rng: KeyedRNG,
    key: Sequence[Any],
) -> str | None:
    if channel_mode == "no_channel":
        return None
    if channel_mode == "fixed_code":
        return SIGNALS[CLASSES.index(context)]
    if channel_mode == "matched_noise":
        return SIGNALS[rng.integer(len(SIGNALS), *key, "matched-noise")]
    return str(sender["sender_map"][context])


def _chosen_skill(receiver: Mapping[str, Any], signal: str | None) -> str:
    return "K0" if signal is None else str(receiver["receiver_map"][signal])


def _balanced_credit(population: Sequence[Mapping[str, Any]]) -> tuple[list[float], list[float], dict[str, int]]:
    sender_credit = [0.0 for _ in population]
    receiver_credit = [0.0 for _ in population]
    successes = {context: 0 for context in CLASSES}
    for sender_index, sender in enumerate(population):
        for receiver_index, receiver in enumerate(population):
            for context in CLASSES:
                signal = sender["sender_map"][context]
                correct = receiver["receiver_map"][signal] == _required_skill(context)
                if correct:
                    sender_credit[sender_index] += 1.0
                    receiver_credit[receiver_index] += 1.0
                    successes[context] += 1
    denominator = len(population) * len(CLASSES)
    return (
        [value / denominator for value in sender_credit],
        [value / denominator for value in receiver_credit],
        successes,
    )


def _encounter_generation(
    population: Sequence[Mapping[str, Any]],
    opportunities: int,
    channel_mode: str,
    rng: KeyedRNG,
    step: int,
) -> dict[str, Any]:
    sender_credit = [0.0 for _ in population]
    receiver_credit = [0.0 for _ in population]
    counts = {context: 0 for context in CLASSES}
    delivered = 0
    correct = 0
    matched_noise = 0
    events: list[dict[str, Any]] = []
    population_size = len(population)
    sender_order = rng.permutation(population_size, "generation", step, "sender-order")
    receiver_order = rng.permutation(population_size, "generation", step, "receiver-order")
    for opportunity in range(opportunities):
        context = CLASSES[(step * opportunities + opportunity) % len(CLASSES)]
        sender_index = sender_order[opportunity % population_size]
        receiver_index = receiver_order[(opportunity + 1) % population_size]
        sender = population[sender_index]
        receiver = population[receiver_index]
        signal = _delivered_signal(
            sender,
            context,
            channel_mode,
            rng,
            ("generation", step, opportunity),
        )
        skill = _chosen_skill(receiver, signal)
        success = skill == _required_skill(context)
        counts[context] += 1
        delivered += signal is not None
        matched_noise += channel_mode == "matched_noise"
        correct += success
        if success:
            sender_credit[sender_index] += 1.0
            receiver_credit[receiver_index] += 1.0
        events.append(
            {
                "context": context,
                "correct": success,
                "receiver": receiver_index,
                "sender": sender_index,
                "signal": signal,
                "skill": skill,
            }
        )
    return {
        "correct": correct,
        "delivered": delivered,
        "events": events,
        "matched_noise": matched_noise,
        "need_class_counts": counts,
        "receiver_credit": receiver_credit,
        "sender_credit": sender_credit,
    }


def _mutate_map(
    mapping: Mapping[str, str],
    keys: Sequence[str],
    values: Sequence[str],
    rng: KeyedRNG,
    key: Sequence[Any],
) -> dict[str, str]:
    result = dict(mapping)
    target = keys[rng.integer(len(keys), *key, "target")]
    current = result[target]
    alternatives = [value for value in values if value != current]
    result[target] = alternatives[rng.integer(len(alternatives), *key, "value")]
    return result


def _reproduce(
    population: Sequence[Mapping[str, Any]],
    encounter_sender: Sequence[float],
    encounter_receiver: Sequence[float],
    condition: Mapping[str, Any],
    config: Mapping[str, Any],
    treatments: Mapping[str, str],
    rng: KeyedRNG,
    step: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    balanced_sender, balanced_receiver, balanced_successes = _balanced_credit(population)
    sender_mode = treatments.get("sender_parent_credit_mode") or treatments.get(
        "reproduction_credit_mode", condition["credit_operator"]
    )
    receiver_mode = treatments.get("receiver_parent_credit_mode") or treatments.get(
        "reproduction_credit_mode", condition["credit_operator"]
    )
    sender_scores = balanced_sender if sender_mode == "balanced_crossplay" else list(encounter_sender)
    receiver_scores = balanced_receiver if receiver_mode == "balanced_crossplay" else list(encounter_receiver)
    if condition["selection_mode"] == "uniform":
        sender_scores = [1.0 for _ in population]
        receiver_scores = [1.0 for _ in population]
    sender_weights = [value + 1e-9 for value in sender_scores]
    receiver_weights = [value + 1e-9 for value in receiver_scores]
    next_population: list[dict[str, Any]] = []
    sender_mutations = 0
    receiver_mutations = 0
    same_source = 0
    for child in range(len(population)):
        if condition["inheritance_operator"] == "linked_codebook":
            linked = [left + right for left, right in zip(sender_weights, receiver_weights)]
            sender_parent = receiver_parent = rng.weighted_index(
                linked, "reproduction", step, child, "linked-parent"
            )
        else:
            sender_parent = rng.weighted_index(
                sender_weights, "reproduction", step, child, "sender-parent"
            )
            receiver_parent = rng.weighted_index(
                receiver_weights, "reproduction", step, child, "receiver-parent"
            )
        same_source += sender_parent == receiver_parent
        sender_map = dict(population[sender_parent]["sender_map"])
        receiver_map = dict(population[receiver_parent]["receiver_map"])
        mutation_enabled = bool(condition["mutation_enabled"])
        mutation_rate = float(config["mutation_rate"])
        if mutation_enabled and rng.bernoulli(
            mutation_rate, "reproduction", step, child, "sender-mutation"
        ):
            sender_map = _mutate_map(
                sender_map,
                CLASSES,
                SIGNALS,
                rng,
                ("reproduction", step, child, "sender-mutation-allele"),
            )
            sender_mutations += 1
        if mutation_enabled and rng.bernoulli(
            mutation_rate, "reproduction", step, child, "receiver-mutation"
        ):
            receiver_map = _mutate_map(
                receiver_map,
                SIGNALS,
                SKILLS,
                rng,
                ("reproduction", step, child, "receiver-mutation-allele"),
            )
            receiver_mutations += 1
        next_population.append(
            {
                "host_lineage_id": population[child]["host_lineage_id"],
                "occupant_epoch": population[child]["occupant_epoch"],
                "receiver_map": receiver_map,
                "receiver_policy_lineage_id": f"RP-{step}-{child}-{receiver_parent}",
                "sender_map": sender_map,
                "sender_policy_lineage_id": f"SP-{step}-{child}-{sender_parent}",
            }
        )
    facts = {
        "balanced_successes_by_role_and_class": balanced_successes
        if sender_mode == "balanced_crossplay" or receiver_mode == "balanced_crossplay"
        else None,
        "child_events": len(population),
        "operator": condition["inheritance_operator"],
        "receiver_mode": receiver_mode,
        "receiver_mutations": receiver_mutations,
        "receiver_weight_vector_sha256": canonical_sha256(receiver_weights),
        "same_source_child_events": same_source,
        "sender_mode": sender_mode,
        "sender_mutations": sender_mutations,
        "sender_weight_vector_sha256": canonical_sha256(sender_weights),
    }
    facts["aggregate_sha256"] = canonical_sha256(facts)
    return next_population, facts


def _probe_events(population: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    size = len(population)
    for sender_index, sender in enumerate(population):
        for partner_offset in (1, 1 + size // 2):
            receiver_index = (sender_index + partner_offset) % size
            receiver = population[receiver_index]
            for context in CLASSES:
                signal = sender["sender_map"][context]
                skill = receiver["receiver_map"][signal]
                events.append(
                    {
                        "context": context,
                        "correct": skill == _required_skill(context),
                        "receiver": receiver_index,
                        "sender": sender_index,
                        "signal": signal,
                        "skill": skill,
                    }
                )
    return events


def _empty_matrix(left: Sequence[str], right: Sequence[str]) -> dict[str, dict[str, int]]:
    return {a: {b: 0 for b in right} for a in left}


def _checkpoint(
    population: Sequence[Mapping[str, Any]],
    cohort: int,
    step: int,
    rng: KeyedRNG,
) -> dict[str, Any]:
    events = _probe_events(population)
    class_correct = {context: 0 for context in CLASSES}
    class_total = {context: 0 for context in CLASSES}
    context_signal = _empty_matrix(CLASSES, SIGNALS)
    signal_skill = _empty_matrix(SIGNALS, SKILLS)
    for event in events:
        context = event["context"]
        signal = event["signal"]
        skill = event["skill"]
        class_total[context] += 1
        class_correct[context] += bool(event["correct"])
        context_signal[context][signal] += 1
        signal_skill[signal][skill] += 1
    total = len(events)
    correct = sum(class_correct.values())
    permuted_indexes = rng.permutation(total, "probe", step, "histogram-permutation")
    permuted_correct = 0
    for event, source_index in zip(events, permuted_indexes):
        signal = events[source_index]["signal"]
        receiver = population[event["receiver"]]
        permuted_correct += receiver["receiver_map"][signal] == _required_skill(event["context"])
    knockout_correct = sum(_required_skill(event["context"]) == "K0" for event in events)
    redirected = 0
    for event in events:
        swapped_signal = SIGNALS[(SIGNALS.index(event["signal"]) + 1) % len(SIGNALS)]
        swapped_skill = population[event["receiver"]]["receiver_map"][swapped_signal]
        redirected += swapped_skill != event["skill"]
    training_class_correct = {context: 0 for context in CLASSES}
    training_class_total = {context: 0 for context in CLASSES}
    for sender in population:
        for receiver in population:
            for context in CLASSES:
                training_class_total[context] += 1
                signal = sender["sender_map"][context]
                training_class_correct[context] += (
                    receiver["receiver_map"][signal] == _required_skill(context)
                )
    snapshot = _policy_projection(population)
    return {
        "branches": list(PROBE_BRANCHES),
        "checkpoint_id": f"checkpoint-cohort-{cohort + 1}",
        "cohort": cohort,
        "fitness_feedback_enabled": False,
        "metrics": {
            "global_signal_relabel": {"correct": correct, "total": total},
            "histogram_preserving_message_permutation": {
                "correct": permuted_correct,
                "total": total,
            },
            "intact": {
                "class_correct": class_correct,
                "class_total": class_total,
                "context_signal_counts": context_signal,
                "correct": correct,
                "cross_lineage_correct": correct,
                "cross_lineage_total": total,
                "signal_skill_counts": signal_skill,
                "total": total,
            },
            "no_channel": {"correct": knockout_correct, "total": total},
            "receiver_add_back": {"correct": correct, "total": total},
            "receiver_knockout": {"correct": knockout_correct, "total": total},
            "schema": "alife.stegohive.probe_sufficient_statistics.v2",
            "symbol_swap": {"eligible": total, "redirected": redirected},
            "training": {
                "cells": sum(training_class_total.values()),
                "class_correct": training_class_correct,
                "class_total": training_class_total,
            },
        },
        "population_snapshot_sha256": canonical_sha256(snapshot),
        "reproduction_enabled": False,
        "slot_policies": snapshot,
        "step": step,
        "trials": total,
        "trials_by_class": class_total,
    }


def deterministic_projection(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Return the reconstructed stable projection used by its hash receipt."""

    return {
        key: deep_copy_json(value)
        for key, value in episode.items()
        if key not in {"deterministic_projection_sha256", "episode_sha256"}
    }


def _apply_archive_wakes(
    population: list[dict[str, Any]],
    archive: list[dict[str, Any]],
    cohort: int,
) -> int:
    ready = [record for record in archive if record["wake_cohort"] == cohort]
    for index, record in enumerate(ready[: len(population)]):
        population[index]["sender_map"] = dict(record["sender_map"])
        population[index]["receiver_map"] = dict(record["receiver_map"])
        population[index]["sender_policy_lineage_id"] = f"SP-A{cohort}-{index}"
        population[index]["receiver_policy_lineage_id"] = f"RP-A{cohort}-{index}"
    return len(ready)


def _deposit_archive(
    population: Sequence[Mapping[str, Any]],
    archive: list[dict[str, Any]],
    cohort: int,
    config: Mapping[str, Any],
    condition: Mapping[str, Any],
    treatments: Mapping[str, str],
    encounter_sender: Sequence[float],
    encounter_receiver: Sequence[float],
    rng: KeyedRNG,
) -> list[dict[str, Any]]:
    if not config["archive"]["enabled"] or not condition["archive_enabled"]:
        return []
    archive_mode = treatments.get("archive_credit_mode", condition["credit_operator"])
    if archive_mode == "balanced_crossplay":
        sender_scores, receiver_scores, _ = _balanced_credit(population)
    else:
        sender_scores, receiver_scores = list(encounter_sender), list(encounter_receiver)
    sender_weights = [value + 1e-9 for value in sender_scores]
    receiver_weights = [value + 1e-9 for value in receiver_scores]
    deposited: list[dict[str, Any]] = []
    for index in range(int(config["archive"]["deposit_count"])):
        sender_index = rng.weighted_index(
            sender_weights, "archive", cohort, index, "sender-source"
        )
        receiver_index = rng.weighted_index(
            receiver_weights, "archive", cohort, index, "receiver-source"
        )
        context = CLASSES[(cohort + index) % len(CLASSES)]
        record = {
            "archive_credit_mode": archive_mode,
            "deposit_cohort": cohort,
            "hidden_context": context,
            "receiver_map": dict(population[receiver_index]["receiver_map"]),
            "receiver_source": f"slot-{receiver_index:03d}",
            "record_id": f"archive-{cohort:02d}-{index:03d}",
            "required_skill": _required_skill(context),
            "sender_map": dict(population[sender_index]["sender_map"]),
            "sender_source": f"slot-{sender_index:03d}",
            "wake_cohort": cohort + int(config["archive"]["delay_cohorts"]),
        }
        deposited.append(record)
        archive.append(record)
    capacity = int(config["archive"]["capacity"])
    if len(archive) > capacity:
        del archive[: len(archive) - capacity]
    return deposited


def run_world(
    config: Mapping[str, Any] | None = None,
    condition: Mapping[str, Any] | str | None = None,
    seed: int = 0,
    *,
    treatments: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run one deterministic reconstructed StegoHive world for any integer seed."""

    validated_config = validate_config(config)
    validated_condition = validate_condition(condition)
    treatment = dict(treatments or {})
    for key, value in treatment.items():
        if key not in {
            "archive_credit_mode",
            "receiver_parent_credit_mode",
            "reproduction_credit_mode",
            "sender_parent_credit_mode",
        } or value not in {"balanced_crossplay", "encounter_local"}:
            raise ValueError(f"invalid reconstructed treatment {key}={value!r}")
    rng = KeyedRNG(seed)
    population = _initial_population(int(validated_config["population_size"]), rng)
    slots = [f"slot-{index:03d}" for index in range(len(population))]
    generations: list[dict[str, Any]] = []
    lifecycle_events: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    archive: list[dict[str, Any]] = []
    archive_deposits = 0
    archive_wakes = 0
    changed_convention_units = 0
    child_events = 0
    mutation_receipts = 0
    same_source_child_events = 0
    ecological_interactions = 0
    delivered_signals = 0
    ecological_matched_noise_draws = 0
    total_need_counts = {context: 0 for context in CLASSES}
    balanced_assays = 0
    changed_weight_vectors = 0
    steps = int(validated_config["cohorts"]) * int(
        validated_config["generations_per_cohort"]
    )
    last_encounter_sender = [0.0 for _ in population]
    last_encounter_receiver = [0.0 for _ in population]
    for cohort in range(int(validated_config["cohorts"])):
        cohort_wakes = 0
        if cohort:
            cohort_wakes = _apply_archive_wakes(population, archive, cohort)
            archive_wakes += cohort_wakes
            for slot, policy in enumerate(population):
                policy["host_lineage_id"] = f"H-{cohort}-{slot}"
                policy["occupant_epoch"] = cohort
        first_step = cohort * int(validated_config["generations_per_cohort"])
        for slot, policy in enumerate(population):
            lifecycle_events.append(
                {
                    "cohort": cohort,
                    "controller_reset_acknowledged": True,
                    "first_step": first_step,
                    "host_lineage_id": policy["host_lineage_id"],
                    "life_reset": True,
                    "occupant_epoch": cohort,
                    "receiver_policy_lineage_id": policy["receiver_policy_lineage_id"],
                    "sender_policy_lineage_id": policy["sender_policy_lineage_id"],
                    "slot_id": slots[slot],
                }
            )
        for generation in range(int(validated_config["generations_per_cohort"])):
            step = first_step + generation
            encounter = _encounter_generation(
                population,
                int(validated_config["opportunities_per_generation"]),
                str(validated_condition["channel_mode"]),
                rng,
                step,
            )
            last_encounter_sender = encounter["sender_credit"]
            last_encounter_receiver = encounter["receiver_credit"]
            ecological_interactions += len(encounter["events"])
            delivered_signals += int(encounter["delivered"])
            ecological_matched_noise_draws += int(encounter["matched_noise"])
            for context in CLASSES:
                total_need_counts[context] += encounter["need_class_counts"][context]
            pressure_propagations = sum(
                rng.bernoulli(
                    float(validated_config["pressure_propagation_probability"]),
                    "pressure",
                    step,
                    event,
                )
                for event in range(len(encounter["events"]))
            )
            credit_facts = {
                "delayed_sender_credit_suppressions_cumulative": archive_wakes,
                "generation_pressure_phase": 1 + cohort % 3,
                "operator": validated_condition["credit_operator"],
                "pressure_propagations": pressure_propagations,
                "pressure_trace_sha256": canonical_sha256(
                    {"propagations": pressure_propagations, "step": step}
                ),
                "receiver_credit_total": float(sum(encounter["receiver_credit"])),
                "receiver_credit_vector_sha256": canonical_sha256(encounter["receiver_credit"]),
                "sender_credit_total": float(sum(encounter["sender_credit"])),
                "sender_credit_vector_sha256": canonical_sha256(encounter["sender_credit"]),
                "storyworld_card_ids": [],
            }
            credit_facts["aggregate_sha256"] = canonical_sha256(credit_facts)
            terminal = step == steps - 1
            if cohort >= int(validated_config["cohorts"]) - 3 and generation == int(
                validated_config["generations_per_cohort"]
            ) - 1:
                checkpoints.append(_checkpoint(population, cohort, step, rng))
            if terminal:
                inheritance_facts = {
                    "child_events": 0,
                    "operator": "terminal",
                    "receiver_weight_vector_sha256": canonical_sha256(last_encounter_receiver),
                    "same_source_child_events": 0,
                    "sender_weight_vector_sha256": canonical_sha256(last_encounter_sender),
                }
                inheritance_facts["aggregate_sha256"] = canonical_sha256(inheritance_facts)
            else:
                population, inheritance_facts = _reproduce(
                    population,
                    last_encounter_sender,
                    last_encounter_receiver,
                    validated_condition,
                    validated_config,
                    treatment,
                    rng,
                    step,
                )
                child_events += int(inheritance_facts["child_events"])
                same_source_child_events += int(inheritance_facts["same_source_child_events"])
                mutations = int(inheritance_facts["sender_mutations"]) + int(
                    inheritance_facts["receiver_mutations"]
                )
                changed_convention_units += mutations
                mutation_receipts += int(inheritance_facts["child_events"]) * 2
                if (
                    inheritance_facts["sender_mode"] == "balanced_crossplay"
                    or inheritance_facts["receiver_mode"] == "balanced_crossplay"
                ):
                    balanced_assays += 1
                    changed_weight_vectors += 1
            active_hash = canonical_sha256(slots)
            archive_facts = {
                "carrier_consumed_cumulative": archive_wakes,
                "carrier_expired_cumulative": 0,
                "deposits": 0,
                "wakes": cohort_wakes if generation == 0 else 0,
            }
            archive_facts["aggregate_sha256"] = canonical_sha256(archive_facts)
            generations.append(
                {
                    "action_count": len(population),
                    "action_kind_counts": {"protocol.participate": len(population)},
                    "active_slots_count": len(population),
                    "active_slots_sha256": active_hash,
                    "archive_receipt": archive_facts,
                    "cohort": cohort,
                    "controller_reset_acknowledgements": len(population) if generation == 0 else 0,
                    "credit_receipt": credit_facts,
                    "delivered_signals": int(encounter["delivered"]),
                    "ecological_interactions": len(encounter["events"]),
                    "ecological_matched_noise_draws": int(encounter["matched_noise"]),
                    "external_policy_override_uses": 0,
                    "generation": generation,
                    "inheritance_receipt": inheritance_facts,
                    "need_class_counts": encounter["need_class_counts"],
                    "raw_command_text_entries": 0,
                    "receiver_actions": len(encounter["events"]),
                    "reproduction_enabled": not terminal,
                    "step": step,
                }
            )
        deposited = _deposit_archive(
            population,
            archive,
            cohort,
            validated_config,
            validated_condition,
            treatment,
            last_encounter_sender,
            last_encounter_receiver,
            rng,
        )
        archive_deposits += len(deposited)
        generations[-1]["archive_receipt"]["deposits"] = len(deposited)
        generations[-1]["archive_receipt"]["aggregate_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in generations[-1]["archive_receipt"].items()
                if key != "aggregate_sha256"
            }
        )
    probe_trials = sum(int(row["trials"]) for row in checkpoints)
    probe_trials_by_class = {
        context: sum(int(row["trials_by_class"][context]) for row in checkpoints)
        for context in CLASSES
    }
    exposure = {
        "archive": {"deposits": archive_deposits, "wakes": archive_wakes},
        "archive_matched_noise_draws": 0,
        "balanced_crossplay": {
            "aggregate_sha256": canonical_sha256(
                {"assays": balanced_assays, "changed": changed_weight_vectors}
            ),
            "assays": balanced_assays,
            "cells_per_assay": len(population) * len(population) * len(CLASSES),
            "changed_weight_vectors": changed_weight_vectors,
            "matched_noise_draws": 0,
            "total_cells": balanced_assays * len(population) * len(population) * len(CLASSES),
        },
        "delivered_signals": delivered_signals,
        "ecological_interactions": ecological_interactions,
        "ecological_matched_noise_draws": ecological_matched_noise_draws,
        "external_policy_override_uses": 0,
        "inheritance": {
            "aggregate_sha256": canonical_sha256(
                {
                    "changed": changed_convention_units,
                    "children": child_events,
                    "mutations": mutation_receipts,
                }
            ),
            "atomic_pair_wakes": archive_wakes
            if validated_condition["inheritance_operator"] == "linked_codebook"
            else 0,
            "changed_convention_units": changed_convention_units,
            "child_events": child_events,
            "mutation_receipts": mutation_receipts,
            "same_source_child_events": same_source_child_events,
            "same_source_propagule_deposits": 0,
        },
        "need_class_counts": total_need_counts,
        "occupant_life_reset_acknowledgements": len(population)
        * int(validated_config["cohorts"]),
        "parallel_env_steps": steps,
        "probes": {
            "checkpoints": len(checkpoints),
            "fitness_feedback_events": 0,
            "reproduction_events": 0,
            "trials": probe_trials,
            "trials_by_class": probe_trials_by_class,
        },
        "protocol_participate_actions": len(population) * steps,
        "raw_command_text_entries": 0,
        "receiver_actions": ecological_interactions,
        "reproductive_transitions": steps - 1,
        "stable_slot_keys": len(population),
    }
    hazards = {
        "external_io_attempt": 0,
        "external_policy_override_use": 0,
        "nonfinite_metric": 0,
        "occupant_hidden_state_leak": 0,
        "raw_command_text_evidence_leak": 0,
        "receiver_hidden_need_leak_count": 0,
        "seed_split_leakage": 0,
        "selection_assay_policy_input_leak_count": 0,
        "slot_key_drift": 0,
    }
    episode: dict[str, Any] = {
        "checkpoints": checkpoints,
        "claim_scope": "model_only",
        "condition": validated_condition,
        "config": validated_config,
        "controller": {
            "action": {"kind": "protocol.participate"},
            "external_policy_override": False,
            "identical_across_registered_arms": True,
            "kind": "fixed_open_loop",
            "stateless": True,
        },
        "episode_id": f"{validated_config['id']}:{validated_condition['id']}:{seed}",
        "exposure": exposure,
        "external_policy_override": False,
        "generations": generations,
        "hazards": hazards,
        "lifecycle_events": lifecycle_events,
        "possible_agents": slots,
        "rng": rng.snapshot(),
        "schema": EPISODE_SCHEMA,
        "seed": seed,
    }
    episode["deterministic_projection_sha256"] = canonical_sha256(
        deterministic_projection(episode)
    )
    episode["episode_sha256"] = canonical_sha256(
        {key: value for key, value in episode.items() if key != "episode_sha256"}
    )
    return deep_copy_json(episode)


__all__ = ["KeyedRNG", "PROBE_BRANCHES", "deterministic_projection", "run_world"]
