"""Fail-closed verification for sealed StegoHive ecology episodes.

The verifier consumes detached, finite JSON data only.  It does not import the
simulator, execute episode content, or perform filesystem/network I/O.  Its
checks are deliberately structural and causal: frozen probe branches must
start from the same checkpoint, opportunity receipts must prove who could see
the hidden need, and every stochastic decision must resolve to a sealed RNG
receipt.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from stegohive.types import MACHINE_IDS


EPISODE_SCHEMA = "alife.stegohive.ecology.episode.v1"
VERIFICATION_SCHEMA = "alife.stegohive.ecology.episode_verification.v1"

TOP_LEVEL_FIELDS = frozenset(
    {
        "schema",
        "episode_id",
        "seed",
        "limits",
        "population",
        "cohorts",
        "generations",
        "cohort_turnovers",
        "host_ancestry",
        "sender_policy_ancestry",
        "receiver_policy_ancestry",
        "selection",
        "archive",
        "horizontal_transfers",
        "audit_receipts",
        "rng",
        "frozen_checkpoint",
        "evaluations",
        "exposure",
        "storyworld_events",
        "deterministic_projection_sha256",
        "episode_sha256",
    }
)

BASE_BRANCHES = frozenset(
    {
        "intact",
        "no_channel",
        "per_message_permutation",
        "receiver_knockout",
        "add_back",
        "global_relabel",
        "ood_topology",
        "symbol_swap",
    }
)

TRIAL_FIELDS = frozenset(
    {
        "trial_id",
        "branch",
        "opportunity_id",
        "cohort",
        "generation",
        "machine_id",
        "channel",
        "sender_id",
        "receiver_id",
        "sender_lineage_id",
        "receiver_lineage_id",
        "hidden_need",
        "delayed_task_binding_id",
        "sender_observation",
        "receiver_observation",
        "emitted_signal",
        "delivered_signal",
        "receiver_action",
        "correct_outcome",
        "task_reward",
        "rng_receipt_ids",
    }
)

SYMBOL_SWAP_FIELDS = frozenset(
    {
        "counterfactual_pair_id",
        "original_delivered_signal",
        "forced_signal",
        "original_receiver_action",
        "counterfactual_receiver_action",
        "decoded_action_for_forced_signal",
        "redirect_toward_forced_signal",
    }
)

POLICY_ANCESTRY_COLUMNS = (
    "policy_lineage_id",
    "parent_policy_lineage_ids",
    "cohort_id",
    "generation",
    "origin_kind",
    "allele_values",
    "alleles_hash",
    "ancestry_receipt_id",
)

AUDIT_SCHEMA = "alife.stegohive.audit_receipts.v1"
REQUIRED_AUDIT_FIELDS_SHA256 = (
    "b953613e5bf6bca68e53afea1f070735fcc3d70b67bf3df5a5102283ea074c54"
)
REQUIRED_AUDIT_FIELDS = (
    "episode_seed",
    "condition_id",
    "candidate_regime_id",
    "cohort_id",
    "generation",
    "machine_id",
    "active_host_population_count",
    "active_host_roster_hash",
    "sender_id",
    "sender_host_lineage_id",
    "sender_policy_lineage_id",
    "receiver_id",
    "receiver_host_lineage_id",
    "receiver_policy_lineage_id",
    "sender_policy_parent_receipt_id",
    "receiver_policy_parent_receipt_id",
    "sender_policy_mutation_receipt_id",
    "receiver_policy_mutation_receipt_id",
    "sender_policy_credit_receipt_id",
    "receiver_policy_credit_receipt_id",
    "sender_policy_ancestry_receipt_id",
    "receiver_policy_ancestry_receipt_id",
    "pressure_class_evaluator_only",
    "required_skill_evaluator_only",
    "signal_id",
    "archive_record_id",
    "archive_delay_cohorts",
    "convention_propagule_id",
    "propagule_sender_source_policy_lineage_id",
    "propagule_receiver_source_policy_lineage_id",
    "propagule_sender_policy_allele_values",
    "propagule_receiver_policy_allele_values",
    "propagule_sender_policy_alleles_hash",
    "propagule_receiver_policy_alleles_hash",
    "propagule_payload_hash",
    "propagule_wake_cohort",
    "propagule_target_host_id",
    "propagule_child_sender_policy_lineage_id",
    "propagule_child_receiver_policy_lineage_id",
    "propagule_result_sender_policy_lineage_id",
    "propagule_result_receiver_policy_lineage_id",
    "propagule_sender_role_state_change",
    "propagule_receiver_role_state_change",
    "propagule_activation_receipt_id",
    "delayed_task_binding_id",
    "delayed_pressure_class_evaluator_only",
    "delayed_required_skill_evaluator_only",
    "live_pressure_class_evaluator_only",
    "live_signal_id",
    "sender_reward_eligible",
    "propagule_visible_to_agents",
    "propagation_source_node_id",
    "propagation_target_node_id",
    "propagation_edge_receipt_id",
    "base_habitat_graph_hash",
    "ood_habitat_graph_hash",
    "ood_removed_edge_receipt",
    "ood_added_edge_receipt",
    "ood_graph_transform_hash",
    "eligibility",
    "emission",
    "delivery",
    "receiver_activation",
    "receiver_policy_input_hash",
    "chosen_skill",
    "counterfactual_pair_id",
    "matched_event_ids_hash",
    "intact_signal_histogram_hash",
    "permuted_signal_histogram_hash",
    "event_index_permutation_hash",
    "probe_feedback_to_fitness",
    "cohort_overlap",
    "hazard_flags",
)

GENERATION_BATCH_COLUMNS = (
    "cohort_id",
    "generation",
    "active_host_population_count",
    "active_host_roster_hash",
    "sender_policy_credit_receipt_id",
    "receiver_policy_credit_receipt_id",
    "sender_credit_values_q6",
    "receiver_credit_values_q6",
)
POLICY_TRANSITION_BATCH_COLUMNS = (
    "cohort_id",
    "generation",
    "sender_parent_slots",
    "receiver_parent_slots",
    "sender_mutations",
    "receiver_mutations",
)
INTERACTION_BATCH_COLUMNS = ("cohort_id", "generation", "events")
INTERACTION_EVENT_COLUMNS = (
    "opportunity_id",
    "sender_id",
    "sender_host_lineage_id",
    "sender_policy_lineage_id",
    "receiver_id",
    "receiver_host_lineage_id",
    "receiver_policy_lineage_id",
    "pressure_class_evaluator_only",
    "required_skill_evaluator_only",
    "signal_id",
    "archive_record_id",
    "machine_id",
    "eligibility",
    "emission",
    "delivery",
    "receiver_activation",
    "receiver_policy_input_hash",
    "chosen_skill",
    "propagation_source_node_id",
    "propagation_target_node_id",
    "propagation_edge_receipt_id",
    "live_pressure_class_evaluator_only",
    "live_signal_id",
    "sender_reward_eligible",
)
PROPAGATION_ROW_COLUMNS = (
    "receipt_id",
    "cohort_id",
    "generation",
    "opportunity_id",
    "source_node_id",
    "target_node_id",
    "declared_graph_hash",
)
ARCHIVE_ROW_COLUMNS = (
    "archive_record_id",
    "archive_delay_cohorts",
    "convention_propagule_id",
    "propagule_sender_source_policy_lineage_id",
    "propagule_receiver_source_policy_lineage_id",
    "propagule_sender_policy_allele_values",
    "propagule_receiver_policy_allele_values",
    "propagule_sender_policy_alleles_hash",
    "propagule_receiver_policy_alleles_hash",
    "propagule_payload_hash",
    "propagule_wake_cohort",
    "propagule_target_host_id",
    "propagule_child_sender_policy_lineage_id",
    "propagule_child_receiver_policy_lineage_id",
    "propagule_result_sender_policy_lineage_id",
    "propagule_result_receiver_policy_lineage_id",
    "propagule_sender_role_state_change",
    "propagule_receiver_role_state_change",
    "propagule_activation_receipt_id",
    "propagule_visible_to_agents",
    "delayed_task_binding_id",
    "delayed_pressure_class_evaluator_only",
    "delayed_required_skill_evaluator_only",
)
PROBE_PAIR_COLUMNS = (
    "counterfactual_pair_id",
    "intact_event_id",
    "symbol_swap_event_id",
)

AUDIT_ID_TEMPLATES = {
    "sender_policy_parent_receipt_id": "SPP:c:g:s",
    "receiver_policy_parent_receipt_id": "RPP:c:g:s",
    "sender_policy_mutation_receipt_id": "SPM:c:g:s",
    "receiver_policy_mutation_receipt_id": "RPM:c:g:s",
    "sender_policy_credit_receipt_id": "SPC:c:g",
    "receiver_policy_credit_receipt_id": "RPC:c:g",
    "sender_policy_ancestry_receipt_id": "SPA:lineage",
    "receiver_policy_ancestry_receipt_id": "RPA:lineage",
}

AUDIT_FIELD_COVERAGE = {
    "episode_seed": "episode.episode_seed",
    "condition_id": "episode.condition_id",
    "candidate_regime_id": "episode.candidate_regime_id",
    "cohort_id": "generation_batches.cohort_id",
    "generation": "generation_batches.generation",
    "machine_id": "interaction_batches.events.machine_id",
    "active_host_population_count": "generation_batches.active_host_population_count",
    "active_host_roster_hash": "generation_batches.active_host_roster_hash",
    "sender_id": "interaction_batches.events.sender_id",
    "sender_host_lineage_id": "interaction_batches.events.sender_host_lineage_id",
    "sender_policy_lineage_id": "interaction_batches.events.sender_policy_lineage_id",
    "receiver_id": "interaction_batches.events.receiver_id",
    "receiver_host_lineage_id": "interaction_batches.events.receiver_host_lineage_id",
    "receiver_policy_lineage_id": "interaction_batches.events.receiver_policy_lineage_id",
    "sender_policy_parent_receipt_id": "id_templates.sender_policy_parent_receipt_id",
    "receiver_policy_parent_receipt_id": "id_templates.receiver_policy_parent_receipt_id",
    "sender_policy_mutation_receipt_id": "id_templates.sender_policy_mutation_receipt_id",
    "receiver_policy_mutation_receipt_id": "id_templates.receiver_policy_mutation_receipt_id",
    "sender_policy_credit_receipt_id": "generation_batches.sender_policy_credit_receipt_id",
    "receiver_policy_credit_receipt_id": "generation_batches.receiver_policy_credit_receipt_id",
    "sender_policy_ancestry_receipt_id": "sender_policy_ancestry.ancestry_receipt_id",
    "receiver_policy_ancestry_receipt_id": "receiver_policy_ancestry.ancestry_receipt_id",
    "pressure_class_evaluator_only": "interaction_batches.events.pressure_class_evaluator_only",
    "required_skill_evaluator_only": "interaction_batches.events.required_skill_evaluator_only",
    "signal_id": "interaction_batches.events.signal_id",
    "archive_record_id": "archive_rows.archive_record_id",
    "archive_delay_cohorts": "archive_rows.archive_delay_cohorts",
    "convention_propagule_id": "archive_rows.convention_propagule_id",
    "propagule_sender_source_policy_lineage_id": "archive_rows.propagule_sender_source_policy_lineage_id",
    "propagule_receiver_source_policy_lineage_id": "archive_rows.propagule_receiver_source_policy_lineage_id",
    "propagule_sender_policy_allele_values": "archive_rows.propagule_sender_policy_allele_values",
    "propagule_receiver_policy_allele_values": "archive_rows.propagule_receiver_policy_allele_values",
    "propagule_sender_policy_alleles_hash": "archive_rows.propagule_sender_policy_alleles_hash",
    "propagule_receiver_policy_alleles_hash": "archive_rows.propagule_receiver_policy_alleles_hash",
    "propagule_payload_hash": "archive_rows.propagule_payload_hash",
    "propagule_wake_cohort": "archive_rows.propagule_wake_cohort",
    "propagule_target_host_id": "archive_rows.propagule_target_host_id",
    "propagule_child_sender_policy_lineage_id": "archive_rows.propagule_child_sender_policy_lineage_id",
    "propagule_child_receiver_policy_lineage_id": "archive_rows.propagule_child_receiver_policy_lineage_id",
    "propagule_result_sender_policy_lineage_id": "archive_rows.propagule_result_sender_policy_lineage_id",
    "propagule_result_receiver_policy_lineage_id": "archive_rows.propagule_result_receiver_policy_lineage_id",
    "propagule_sender_role_state_change": "archive_rows.propagule_sender_role_state_change",
    "propagule_receiver_role_state_change": "archive_rows.propagule_receiver_role_state_change",
    "propagule_activation_receipt_id": "archive_rows.propagule_activation_receipt_id",
    "delayed_task_binding_id": "archive_rows.delayed_task_binding_id",
    "delayed_pressure_class_evaluator_only": "archive_rows.delayed_pressure_class_evaluator_only",
    "delayed_required_skill_evaluator_only": "archive_rows.delayed_required_skill_evaluator_only",
    "live_pressure_class_evaluator_only": "interaction_batches.events.live_pressure_class_evaluator_only",
    "live_signal_id": "interaction_batches.events.live_signal_id",
    "sender_reward_eligible": "interaction_batches.events.sender_reward_eligible",
    "propagule_visible_to_agents": "archive_rows.propagule_visible_to_agents",
    "propagation_source_node_id": "interaction_batches.events.propagation_source_node_id",
    "propagation_target_node_id": "interaction_batches.events.propagation_target_node_id",
    "propagation_edge_receipt_id": "interaction_batches.events.propagation_edge_receipt_id",
    "base_habitat_graph_hash": "episode.base_habitat_graph_hash",
    "ood_habitat_graph_hash": "episode.ood_habitat_graph_hash",
    "ood_removed_edge_receipt": "episode.ood_removed_edge_receipt",
    "ood_added_edge_receipt": "episode.ood_added_edge_receipt",
    "ood_graph_transform_hash": "episode.ood_graph_transform_hash",
    "eligibility": "interaction_batches.events.eligibility",
    "emission": "interaction_batches.events.emission",
    "delivery": "interaction_batches.events.delivery",
    "receiver_activation": "interaction_batches.events.receiver_activation",
    "receiver_policy_input_hash": "interaction_batches.events.receiver_policy_input_hash",
    "chosen_skill": "interaction_batches.events.chosen_skill",
    "counterfactual_pair_id": "probe_pairs.counterfactual_pair_id",
    "matched_event_ids_hash": "probe.matched_event_ids_hash",
    "intact_signal_histogram_hash": "probe.intact_signal_histogram_hash",
    "permuted_signal_histogram_hash": "probe.permuted_signal_histogram_hash",
    "event_index_permutation_hash": "probe.event_index_permutation_hash",
    "probe_feedback_to_fitness": "episode.probe_feedback_to_fitness",
    "cohort_overlap": "episode.cohort_overlap",
    "hazard_flags": "episode.hazard_flags",
}

REQUIRED_VERIFIERS = (
    "episode_schema",
    "frozen_branches",
    "opportunity_receipts",
    "rng_receipts",
    "resource_bounds",
    "cohort_isolation",
    "ancestry_separation",
    "policy_audit_receipts",
    "selection_firewall",
    "abstract_containment",
    "archive_transfer_bounds",
    "deterministic_hashes",
)

HARD_MAX_POPULATION = 64
HARD_MAX_COHORTS = 64
HARD_MAX_GENERATIONS = 10_000
HARD_MAX_ARCHIVE_RECORDS = 256
HARD_MAX_HORIZONTAL_TRANSFERS = 256
HARD_MAX_RNG_RECEIPTS = 262_144
HARD_MAX_TRIALS_PER_BRANCH = 65_536

_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_WINDOWS_PATH = re.compile(r"(?i)(?:^|\s)[a-z]:[\\/]")
_UNC_PATH = re.compile(r"(?:^|\s)\\\\[^\\\s]+\\")
_URI = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://")
_IPV4 = re.compile(r"(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9])")
_SHELL_META = re.compile(r"[;&|`$<>\r\n]")

_FORBIDDEN_KEY_PARTS = (
    "codec",
    "command",
    "filesystem",
    "free_text",
    "natural_language",
    "network",
    "path",
    "prose",
    "shell",
    "socket",
    "subprocess",
    "url",
)
_RECEIVER_SECRET_KEYS = frozenset(
    {
        "hidden_need",
        "need",
        "delayed_task_binding",
        "delayed_task_binding_id",
        "pressure_class_evaluator_only",
        "required_action",
        "required_skill",
        "required_skill_evaluator_only",
        "source_need",
        "source_pressure_class",
        "task_intent",
    }
)
_EVIDENCE_TOKENS = (
    "accuracy",
    "causal_redirect",
    "entropy",
    "evidence",
    "mutual_information",
    "nmi",
    "qualification",
    "qualified",
    "signal_identity",
)


def canonical_sha256(value: Any) -> str:
    """Return a SHA-256 digest of canonical finite JSON."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


DETERMINISTIC_PROJECTION_FIELDS = (
    "schema",
    "episode_id",
    "seed",
    "limits",
    "population",
    "cohorts",
    "generations",
    "cohort_turnovers",
    "host_ancestry",
    "sender_policy_ancestry",
    "receiver_policy_ancestry",
    "selection",
    "archive",
    "horizontal_transfers",
    "audit_receipts",
    "frozen_checkpoint",
    "evaluations",
    "exposure",
    "storyworld_events",
)


def deterministic_projection(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Return the episode content bound by ``deterministic_projection_sha256``.

    The projection is the simulator-owned state/evaluation surface.  RNG
    receipts have their own canonical digest and the complete episode hash
    binds both surfaces.
    """

    return {key: episode.get(key) for key in DETERMINISTIC_PROJECTION_FIELDS}


def seal_episode(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached episode with deterministic and whole-row hashes set."""

    detached = json.loads(
        json.dumps(episode, ensure_ascii=False, allow_nan=False)
    )
    if not isinstance(detached, dict):
        raise TypeError("episode must be an object")
    detached["deterministic_projection_sha256"] = canonical_sha256(
        deterministic_projection(detached)
    )
    detached["episode_sha256"] = canonical_sha256(
        {key: value for key, value in detached.items() if key != "episode_sha256"}
    )
    return detached


def _check(
    verifier_id: str,
    failures: Iterable[str],
    *,
    facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    messages = list(dict.fromkeys(str(value) for value in failures))
    return {
        "verifier_id": verifier_id,
        "passed": not messages,
        "failures": messages,
        "facts": dict(facts or {}),
    }


def _is_int(value: Any, *, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _HEX_SHA256.fullmatch(value) is not None


def _is_safe_id(value: Any) -> bool:
    return isinstance(value, str) and _SAFE_ID.fullmatch(value) is not None


def _is_signal_id(value: Any) -> bool:
    return value in {"S0", "S1", "S2", "S3"}


def _walk(value: Any, path: str = "episode") -> Iterable[tuple[str, str | None, Any]]:
    yield path, None, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk_children(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield child_path, None, child
            yield from _walk_children(child, child_path)


def _walk_children(value: Any, path: str) -> Iterable[tuple[str, str | None, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk_children(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield child_path, None, child
            yield from _walk_children(child, child_path)


def _episode_schema(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    missing = sorted(TOP_LEVEL_FIELDS - set(episode))
    extra = sorted(set(episode) - TOP_LEVEL_FIELDS)
    if missing:
        failures.append("missing episode fields: " + ", ".join(missing))
    if extra:
        failures.append("unexpected episode fields: " + ", ".join(extra))
    if episode.get("schema") != EPISODE_SCHEMA:
        failures.append(f"schema must equal {EPISODE_SCHEMA}")
    if not _is_safe_id(episode.get("episode_id")):
        failures.append("episode_id must be a bounded opaque identifier")
    if not _is_int(episode.get("seed")):
        failures.append("seed must be a non-negative integer")
    mapping_fields = (
        "limits",
        "sender_policy_ancestry",
        "receiver_policy_ancestry",
        "selection",
        "archive",
        "audit_receipts",
        "rng",
        "frozen_checkpoint",
        "evaluations",
        "exposure",
    )
    list_fields = (
        "cohort_turnovers",
        "host_ancestry",
        "horizontal_transfers",
        "storyworld_events",
    )
    for key in mapping_fields:
        if not isinstance(episode.get(key), Mapping):
            failures.append(f"{key} must be an object")
    for key in list_fields:
        if not isinstance(episode.get(key), list):
            failures.append(f"{key} must be a list")
    for key in ("population", "cohorts", "generations"):
        if not _is_int(episode.get(key), minimum=1):
            failures.append(f"{key} must be a positive integer")
    for key in ("deterministic_projection_sha256", "episode_sha256"):
        if not _is_sha256(episode.get(key)):
            failures.append(f"{key} must be a lowercase SHA-256 digest")
    try:
        json.dumps(
            episode,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        failures.append("episode must contain detached finite JSON values only")
    return _check("episode_schema", failures)


def _archive_exposure_exists(episode: Mapping[str, Any]) -> bool:
    archive = episode.get("archive")
    exposure = episode.get("exposure")
    wakes = archive.get("wakes", 0) if isinstance(archive, Mapping) else 0
    delayed = exposure.get("delayed_archive") if isinstance(exposure, Mapping) else None
    if _is_int(wakes) and wakes > 0:
        return True
    if isinstance(delayed, Mapping):
        return any(_is_number(value) and float(value) > 0.0 for value in delayed.values())
    return delayed is True or (_is_number(delayed) and float(delayed) > 0.0)


def _branch_trials(branch: Any) -> list[Mapping[str, Any]]:
    if not isinstance(branch, Mapping):
        return []
    trials = branch.get("trials")
    if not isinstance(trials, list):
        return []
    return [trial for trial in trials if isinstance(trial, Mapping)]


def _frozen_branches(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    evaluations = episode.get("evaluations")
    expected = set(BASE_BRANCHES)
    if _archive_exposure_exists(episode):
        expected.add("delayed_archive")
    if not isinstance(evaluations, Mapping):
        return _check(
            "frozen_branches",
            ["evaluations must be an object containing the frozen branch set"],
            facts={"expected_branches": sorted(expected)},
        )
    actual = set(evaluations)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        failures.append("missing frozen branches: " + ", ".join(missing))
    if extra:
        failures.append("unexpected frozen branches: " + ", ".join(extra))

    checkpoint_hashes: set[str] = set()
    intact_ids: set[str] | None = None
    for name in sorted(actual):
        branch = evaluations.get(name)
        label = f"evaluations.{name}"
        if not isinstance(branch, Mapping):
            failures.append(f"{label} must be an object")
            continue
        required = {"checkpoint_sha256", "projection_sha256", "trials", "metrics"}
        missing_fields = sorted(required - set(branch))
        extra_fields = sorted(set(branch) - required)
        if missing_fields:
            failures.append(f"{label} missing fields: {', '.join(missing_fields)}")
        if extra_fields:
            failures.append(f"{label} has unexpected fields: {', '.join(extra_fields)}")
        checkpoint = branch.get("checkpoint_sha256")
        if not _is_sha256(checkpoint):
            failures.append(f"{label}.checkpoint_sha256 must be a SHA-256 digest")
        else:
            checkpoint_hashes.add(checkpoint)
        if not _is_sha256(branch.get("projection_sha256")):
            failures.append(f"{label}.projection_sha256 must be a SHA-256 digest")
        trials = branch.get("trials")
        if not isinstance(trials, list) or not trials:
            failures.append(f"{label}.trials must be a non-empty list")
            continue
        if len(trials) > HARD_MAX_TRIALS_PER_BRANCH:
            failures.append(f"{label}.trials exceeds the hard trial cap")
        if not isinstance(branch.get("metrics"), Mapping):
            failures.append(f"{label}.metrics must be an object")
        ids = {
            trial.get("opportunity_id")
            for trial in trials
            if isinstance(trial, Mapping) and _is_safe_id(trial.get("opportunity_id"))
        }
        if name == "intact":
            intact_ids = ids
        elif intact_ids is not None and ids != intact_ids:
            failures.append(f"{label} must use the intact opportunity_id set")

    # Iteration is alphabetical, so intact may not have been seen before an
    # earlier branch.  Repeat the schedule comparison without order coupling.
    intact_rows = _branch_trials(evaluations.get("intact"))
    intact_ids = {
        row.get("opportunity_id")
        for row in intact_rows
        if _is_safe_id(row.get("opportunity_id"))
    }
    if intact_ids:
        for name, branch in evaluations.items():
            ids = {
                row.get("opportunity_id")
                for row in _branch_trials(branch)
                if _is_safe_id(row.get("opportunity_id"))
            }
            if ids != intact_ids:
                failures.append(
                    f"evaluations.{name} must use the intact opportunity_id set"
                )
    if len(checkpoint_hashes) > 1:
        failures.append("all frozen branches must share one checkpoint_sha256")
    return _check(
        "frozen_branches",
        failures,
        facts={
            "expected_branches": sorted(expected),
            "actual_branches": sorted(actual),
            "shared_checkpoint_count": len(checkpoint_hashes),
        },
    )


def _contains_value(value: Any, target: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_value(child, target) for child in value.values())
    if isinstance(value, list):
        return any(_contains_value(child, target) for child in value)
    return value == target


def _contains_object(value: Any, target: Any) -> bool:
    if value == target:
        return True
    if isinstance(value, Mapping):
        return any(_contains_object(child, target) for child in value.values())
    if isinstance(value, list):
        return any(_contains_object(child, target) for child in value)
    return False


def _receiver_leaks_need(observation: Mapping[str, Any], hidden_need: Any) -> bool:
    for _, key, value in _walk(observation, "receiver_observation"):
        if isinstance(key, str) and key.casefold() in _RECEIVER_SECRET_KEYS:
            return True
        if value == hidden_need and not isinstance(value, (Mapping, list)):
            return True
    return False


def _trial_map(branch: Any) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in _branch_trials(branch):
        opportunity_id = row.get("opportunity_id")
        if isinstance(opportunity_id, str) and opportunity_id not in result:
            result[opportunity_id] = row
    return result


def _columnar_records(
    value: Any, expected_columns: Sequence[str]
) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    columns = value.get("columns")
    rows = value.get("rows")
    if list(expected_columns) != columns or not isinstance(rows, list):
        return []
    records: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, list) and len(row) == len(expected_columns):
            records.append(dict(zip(expected_columns, row)))
    return records


def _policy_ancestry_records(
    episode: Mapping[str, Any], role: str
) -> list[dict[str, Any]]:
    return _columnar_records(
        episode.get(f"{role}_policy_ancestry"), POLICY_ANCESTRY_COLUMNS
    )


def _opportunity_receipts(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    evaluations = episode.get("evaluations")
    if not isinstance(evaluations, Mapping):
        return _check("opportunity_receipts", ["evaluations must be an object"])
    sender_policy_records = {
        row.get("policy_lineage_id"): row
        for row in _policy_ancestry_records(episode, "sender")
        if _is_safe_id(row.get("policy_lineage_id"))
    }
    sender_policy_cohorts = {
        lineage_id: row.get("cohort_id")
        for lineage_id, row in sender_policy_records.items()
    }
    receiver_policy_records = {
        row.get("policy_lineage_id"): row
        for row in _policy_ancestry_records(episode, "receiver")
        if _is_safe_id(row.get("policy_lineage_id"))
    }
    receiver_policy_cohorts = {
        lineage_id: row.get("cohort_id")
        for lineage_id, row in receiver_policy_records.items()
    }
    checkpoint = episode.get("frozen_checkpoint")
    projection = checkpoint.get("projection") if isinstance(checkpoint, Mapping) else None
    checkpoint_population = (
        projection.get("population") if isinstance(projection, Mapping) else None
    )
    checkpoint_hosts: dict[str, Mapping[str, Any]] = {}
    if not isinstance(checkpoint_population, list):
        failures.append("frozen checkpoint population must be a list")
    else:
        for index, host in enumerate(checkpoint_population):
            label = f"frozen_checkpoint.projection.population[{index}]"
            required_host_fields = {
                "agent_id",
                "sender_policy_lineage_id",
                "receiver_policy_lineage_id",
            }
            if not isinstance(host, Mapping):
                failures.append(f"{label} must be an object")
                continue
            if not required_host_fields.issubset(host):
                failures.append(f"{label} lacks split policy lineage ids")
                continue
            agent_id = host.get("agent_id")
            if not _is_safe_id(agent_id):
                failures.append(f"{label}.agent_id is invalid")
            elif agent_id in checkpoint_hosts:
                failures.append(f"{label}.agent_id is duplicated")
            else:
                checkpoint_hosts[agent_id] = host
            if host.get("sender_policy_lineage_id") not in sender_policy_cohorts:
                failures.append(f"{label} has an unrecorded sender policy lineage")
            if host.get("receiver_policy_lineage_id") not in receiver_policy_cohorts:
                failures.append(f"{label} has an unrecorded receiver policy lineage")
        if (
            _is_int(episode.get("population"), minimum=1)
            and len(checkpoint_population) != episode.get("population")
        ):
            failures.append("frozen checkpoint population count differs from episode")
    archive = episode.get("archive")
    archive_records = archive.get("records") if isinstance(archive, Mapping) else None
    archive_by_binding_id: dict[str, Mapping[str, Any]] = {}
    if isinstance(archive_records, list):
        for record in archive_records:
            if not isinstance(record, Mapping):
                continue
            binding = record.get("delayed_task_binding")
            binding_id = binding.get("binding_id") if isinstance(binding, Mapping) else None
            if _is_safe_id(binding_id) and binding_id not in archive_by_binding_id:
                archive_by_binding_id[binding_id] = record
    intact = _trial_map(evaluations.get("intact"))
    total = 0
    pair_ids: set[str] = set()
    for branch_name, branch in evaluations.items():
        seen_trial_ids: set[str] = set()
        seen_opportunities: set[str] = set()
        for index, trial in enumerate(_branch_trials(branch)):
            total += 1
            label = f"evaluations.{branch_name}.trials[{index}]"
            required = set(TRIAL_FIELDS)
            if branch_name == "symbol_swap":
                required.update(SYMBOL_SWAP_FIELDS)
            missing = sorted(required - set(trial))
            if missing:
                failures.append(f"{label} missing fields: {', '.join(missing)}")
                continue
            trial_id = trial.get("trial_id")
            opportunity_id = trial.get("opportunity_id")
            if not _is_safe_id(trial_id):
                failures.append(f"{label}.trial_id is invalid")
            elif trial_id in seen_trial_ids:
                failures.append(f"{label}.trial_id is duplicated in its branch")
            else:
                seen_trial_ids.add(trial_id)
            if not _is_safe_id(opportunity_id):
                failures.append(f"{label}.opportunity_id is invalid")
            elif opportunity_id in seen_opportunities:
                failures.append(f"{label}.opportunity_id is duplicated in its branch")
            else:
                seen_opportunities.add(opportunity_id)
            if trial.get("branch") != branch_name:
                failures.append(f"{label}.branch must equal {branch_name}")
            for key in ("cohort", "generation"):
                if not _is_int(trial.get(key)):
                    failures.append(f"{label}.{key} must be a non-negative integer")
            if trial.get("machine_id") not in MACHINE_IDS:
                failures.append(f"{label}.machine_id must be a sealed fictional habitat")
            if trial.get("channel") != "abstract_signal":
                failures.append(f"{label}.channel must be abstract_signal")
            for key in (
                "sender_id",
                "receiver_id",
                "sender_lineage_id",
                "receiver_lineage_id",
            ):
                if not _is_safe_id(trial.get(key)):
                    failures.append(f"{label}.{key} must be an opaque identifier")
            if trial.get("sender_id") == trial.get("receiver_id"):
                failures.append(f"{label} sender_id and receiver_id must differ")
            sender_host = checkpoint_hosts.get(trial.get("sender_id"))
            receiver_host = checkpoint_hosts.get(trial.get("receiver_id"))
            if not isinstance(sender_host, Mapping):
                failures.append(f"{label}.sender_id is absent from frozen population")
            elif sender_host.get("sender_policy_lineage_id") != trial.get(
                "sender_lineage_id"
            ):
                failures.append(
                    f"{label}.sender_lineage_id differs from the frozen sender host"
                )
            if not isinstance(receiver_host, Mapping):
                failures.append(f"{label}.receiver_id is absent from frozen population")
            elif receiver_host.get("receiver_policy_lineage_id") != trial.get(
                "receiver_lineage_id"
            ):
                failures.append(
                    f"{label}.receiver_lineage_id differs from the frozen receiver host"
                )
            for key, policy_cohorts in (
                ("sender_lineage_id", sender_policy_cohorts),
                ("receiver_lineage_id", receiver_policy_cohorts),
            ):
                lineage_id = trial.get(key)
                if lineage_id not in policy_cohorts:
                    failures.append(
                        f"{label}.{key} must reference its role-specific policy ancestry"
                    )
                elif (
                    _is_int(trial.get("cohort"))
                    and _is_int(policy_cohorts.get(lineage_id))
                    and policy_cohorts[lineage_id] > trial.get("cohort")
                ):
                    failures.append(f"{label}.{key} references a future policy")
            hidden_need = trial.get("hidden_need")
            if hidden_need not in {"C0", "C1", "C2", "C3"}:
                failures.append(f"{label}.hidden_need must be one of C0..C3")
            delayed_binding_id = trial.get("delayed_task_binding_id")
            delayed_record: Mapping[str, Any] | None = None
            if branch_name == "delayed_archive":
                if not _is_safe_id(delayed_binding_id):
                    failures.append(
                        f"{label}.delayed_task_binding_id must identify a retained binding"
                    )
                else:
                    delayed_record = archive_by_binding_id.get(delayed_binding_id)
                    if delayed_record is None:
                        failures.append(
                            f"{label}.delayed_task_binding_id is absent from the archive"
                        )
            elif delayed_binding_id is not None:
                failures.append(
                    f"{label}.delayed_task_binding_id must be null outside delayed_archive"
                )
            sender_observation = trial.get("sender_observation")
            receiver_observation = trial.get("receiver_observation")
            if not isinstance(sender_observation, Mapping):
                failures.append(f"{label}.sender_observation must be an object")
            elif branch_name == "delayed_archive":
                live_need = sender_observation.get("need")
                if live_need not in {"C0", "C1", "C2", "C3"}:
                    failures.append(
                        f"{label}.sender_observation.need must expose a finite live need"
                    )
                if any(
                    isinstance(key, str)
                    and key.casefold()
                    in {
                        "delayed_task_binding",
                        "delayed_task_binding_id",
                        "pressure_class_evaluator_only",
                        "required_skill_evaluator_only",
                    }
                    for _, key, _ in _walk(sender_observation, "sender_observation")
                ):
                    failures.append(
                        f"{label}.sender_observation exposes delayed evaluator truth"
                    )
            elif not _contains_value(sender_observation, hidden_need):
                failures.append(f"{label}.sender_observation must expose hidden_need")
            if not isinstance(receiver_observation, Mapping):
                failures.append(f"{label}.receiver_observation must be an object")
            elif _receiver_leaks_need(receiver_observation, hidden_need):
                failures.append(f"{label}.receiver_observation leaks hidden_need")
            if not _is_signal_id(trial.get("emitted_signal")):
                failures.append(f"{label}.emitted_signal must be one of S0..S3")
            elif branch_name == "delayed_archive" and isinstance(
                sender_observation, Mapping
            ):
                live_need = sender_observation.get("need")
                sender_policy = sender_policy_records.get(
                    trial.get("sender_lineage_id")
                )
                sender_alleles = (
                    sender_policy.get("allele_values")
                    if isinstance(sender_policy, Mapping)
                    else None
                )
                if (
                    live_need in {"C0", "C1", "C2", "C3"}
                    and isinstance(sender_alleles, list)
                    and len(sender_alleles) == 4
                    and trial.get("emitted_signal")
                    != sender_alleles[int(str(live_need)[1:])]
                ):
                    failures.append(
                        f"{label}.emitted_signal differs from the live sender policy"
                    )
            if not _is_safe_id(trial.get("receiver_action")):
                failures.append(f"{label}.receiver_action must be an opaque enum id")
            delivered = trial.get("delivered_signal")
            if delivered is not None and not _is_signal_id(delivered):
                failures.append(
                    f"{label}.delivered_signal must be null or one of S0..S3"
                )
            if isinstance(delayed_record, Mapping):
                binding = delayed_record.get("delayed_task_binding")
                abstract_signal = delayed_record.get("abstract_signal")
                bound_need = (
                    binding.get("pressure_class_evaluator_only")
                    if isinstance(binding, Mapping)
                    else None
                )
                archived_signal = (
                    abstract_signal.get("signal_id")
                    if isinstance(abstract_signal, Mapping)
                    else None
                )
                if hidden_need != bound_need:
                    failures.append(
                        f"{label}.hidden_need differs from its delayed task binding"
                    )
                if delivered != archived_signal:
                    failures.append(
                        f"{label}.delivered_signal differs from its archived signal"
                    )
                receiver_policy = receiver_policy_records.get(
                    trial.get("receiver_lineage_id")
                )
                receiver_alleles = (
                    receiver_policy.get("allele_values")
                    if isinstance(receiver_policy, Mapping)
                    else None
                )
                if (
                    _is_signal_id(archived_signal)
                    and isinstance(receiver_alleles, list)
                    and len(receiver_alleles) == 4
                    and trial.get("receiver_action")
                    != receiver_alleles[int(str(archived_signal)[1:])]
                ):
                    failures.append(
                        f"{label}.receiver_action differs from the archived policy input"
                    )
                if isinstance(receiver_observation, Mapping):
                    expected_observation_fields = {
                        "opportunity_id",
                        "machine_id",
                        "channel",
                        "carrier",
                        "signal",
                        "archive_record_id",
                    }
                    if set(receiver_observation) != expected_observation_fields:
                        failures.append(
                            f"{label}.receiver_observation must contain only the delayed signal receipt"
                        )
                    if (
                        receiver_observation.get("archive_record_id")
                        != delayed_record.get("record_id")
                        or receiver_observation.get("signal") != archived_signal
                        or receiver_observation.get("opportunity_id")
                        != opportunity_id
                        or receiver_observation.get("machine_id")
                        != trial.get("machine_id")
                        or receiver_observation.get("channel") != "abstract_signal"
                        or receiver_observation.get("carrier") != "abstract_signal"
                    ):
                        failures.append(
                            f"{label}.receiver_observation does not bind its archive record and signal"
                        )
            if not isinstance(trial.get("correct_outcome"), bool):
                failures.append(f"{label}.correct_outcome must be boolean")
            expected_action = (
                f"K{hidden_need[1:]}"
                if isinstance(hidden_need, str)
                and hidden_need in {"C0", "C1", "C2", "C3"}
                else None
            )
            if (
                isinstance(trial.get("correct_outcome"), bool)
                and trial.get("correct_outcome")
                != (trial.get("receiver_action") == expected_action)
            ):
                failures.append(
                    f"{label}.correct_outcome disagrees with the sealed need/action relation"
                )
            if not _is_number(trial.get("task_reward")):
                failures.append(f"{label}.task_reward must be a finite scalar")
            receipt_ids = trial.get("rng_receipt_ids")
            if (
                not isinstance(receipt_ids, list)
                or not receipt_ids
                or any(not _is_safe_id(value) for value in receipt_ids)
                or len(set(receipt_ids)) != len(receipt_ids)
            ):
                failures.append(
                    f"{label}.rng_receipt_ids must be a non-empty unique id list"
                )
            if branch_name == "no_channel" and delivered is not None:
                failures.append(f"{label}.delivered_signal must be null in no_channel")

            original = intact.get(opportunity_id) if isinstance(opportunity_id, str) else None
            if branch_name == "symbol_swap":
                pair_id = trial.get("counterfactual_pair_id")
                if not _is_safe_id(pair_id):
                    failures.append(f"{label}.counterfactual_pair_id is invalid")
                elif pair_id in pair_ids:
                    failures.append(f"{label}.counterfactual_pair_id is duplicated")
                else:
                    pair_ids.add(pair_id)
                if original is None:
                    failures.append(f"{label} has no matched intact opportunity")
                else:
                    matched_fields = (
                        "cohort",
                        "generation",
                        "machine_id",
                        "channel",
                        "sender_id",
                        "receiver_id",
                        "sender_lineage_id",
                        "receiver_lineage_id",
                        "hidden_need",
                        "delayed_task_binding_id",
                        "sender_observation",
                        "emitted_signal",
                        "task_reward",
                    )
                    for key in matched_fields:
                        if trial.get(key) != original.get(key):
                            failures.append(f"{label}.{key} differs from intact match")
                    if trial.get("original_delivered_signal") != original.get(
                        "delivered_signal"
                    ):
                        failures.append(
                            f"{label}.original_delivered_signal differs from intact"
                        )
                    if trial.get("original_receiver_action") != original.get(
                        "receiver_action"
                    ):
                        failures.append(
                            f"{label}.original_receiver_action differs from intact"
                        )
                if trial.get("forced_signal") == trial.get("original_delivered_signal"):
                    failures.append(f"{label}.forced_signal must change the signal")
                for key in ("original_delivered_signal", "forced_signal"):
                    if not _is_signal_id(trial.get(key)):
                        failures.append(f"{label}.{key} must be one of S0..S3")
                if trial.get("delivered_signal") != trial.get("forced_signal"):
                    failures.append(
                        f"{label}.delivered_signal must equal forced_signal"
                    )
                for key in (
                    "original_receiver_action",
                    "counterfactual_receiver_action",
                    "decoded_action_for_forced_signal",
                ):
                    if trial.get(key) not in {"K0", "K1", "K2", "K3"}:
                        failures.append(f"{label}.{key} must be one of K0..K3")
                if trial.get("counterfactual_receiver_action") != trial.get(
                    "decoded_action_for_forced_signal"
                ):
                    failures.append(
                        f"{label}.decoded action must equal counterfactual_receiver_action"
                    )
                if not isinstance(trial.get("redirect_toward_forced_signal"), bool):
                    failures.append(
                        f"{label}.redirect_toward_forced_signal must be boolean"
                    )

    # Required resource-matched signal controls preserve the emitted/delivered
    # multiset except for the declared channel intervention.
    intact_rows = list(intact.values())
    intact_emitted = sorted(str(row.get("emitted_signal")) for row in intact_rows)
    permutation_rows = _branch_trials(evaluations.get("per_message_permutation"))
    if intact_emitted and sorted(
        str(row.get("delivered_signal")) for row in permutation_rows
    ) != sorted(str(row.get("delivered_signal")) for row in intact_rows):
        failures.append("per_message_permutation must preserve the delivered histogram")
    no_channel_rows = _branch_trials(evaluations.get("no_channel"))
    if intact_emitted and sorted(
        str(row.get("emitted_signal")) for row in no_channel_rows
    ) != intact_emitted:
        failures.append("no_channel must preserve the emitted histogram")

    return _check(
        "opportunity_receipts",
        failures,
        facts={"trial_count": total, "counterfactual_pairs": len(pair_ids)},
    )


def _rng_receipts(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    rng = episode.get("rng")
    if not isinstance(rng, Mapping):
        return _check("rng_receipts", ["rng must be an object"])
    if set(rng) != {"receipts", "receipts_sha256"}:
        failures.append("rng must contain exactly receipts and receipts_sha256")
    receipts = rng.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        return _check(
            "rng_receipts",
            failures + ["rng.receipts must be a non-empty list"],
        )
    if len(receipts) > HARD_MAX_RNG_RECEIPTS:
        failures.append("rng.receipts exceeds the hard receipt cap")
    expected_fields = {
        "receipt_id",
        "key",
        "sampler",
        "parameters",
        "draw_sha256",
        "value",
    }
    expected_key_fields = {
        "namespace",
        "branch",
        "cohort",
        "generation",
        "event_kind",
        "entity_ids",
        "draw_name",
    }
    receipt_ids: set[str] = set()
    full_keys: set[str] = set()
    for index, receipt in enumerate(receipts):
        label = f"rng.receipts[{index}]"
        if not isinstance(receipt, Mapping):
            failures.append(f"{label} must be an object")
            continue
        missing = sorted(expected_fields - set(receipt))
        extra = sorted(set(receipt) - expected_fields)
        if missing:
            failures.append(f"{label} missing fields: {', '.join(missing)}")
        if extra:
            failures.append(f"{label} has unexpected fields: {', '.join(extra)}")
        receipt_id = receipt.get("receipt_id")
        if not _is_safe_id(receipt_id):
            failures.append(f"{label}.receipt_id is invalid")
        elif receipt_id in receipt_ids:
            failures.append(f"duplicate RNG receipt_id: {receipt_id}")
        else:
            receipt_ids.add(receipt_id)
        key = receipt.get("key")
        if not isinstance(key, Mapping):
            failures.append(f"{label}.key must be an object")
        else:
            missing_key = sorted(expected_key_fields - set(key))
            extra_key = sorted(set(key) - expected_key_fields)
            if missing_key:
                failures.append(f"{label}.key missing fields: {', '.join(missing_key)}")
            if extra_key:
                failures.append(f"{label}.key has unexpected fields: {', '.join(extra_key)}")
            for name in ("namespace", "branch", "event_kind", "draw_name"):
                if not _is_safe_id(key.get(name)):
                    failures.append(f"{label}.key.{name} is invalid")
            for name in ("cohort", "generation"):
                value = key.get(name)
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < -1
                ):
                    failures.append(f"{label}.key.{name} must be an integer >= -1")
            entity_ids = key.get("entity_ids")
            if not isinstance(entity_ids, list) or any(
                not _is_safe_id(value) for value in entity_ids
            ):
                failures.append(
                    f"{label}.key.entity_ids must be an opaque-id list"
                )
            try:
                key_digest = canonical_sha256(key)
            except (TypeError, ValueError):
                key_digest = ""
                failures.append(f"{label}.key is not finite canonical JSON")
            if key_digest in full_keys:
                failures.append(f"{label}.key duplicates a prior full RNG key")
            elif key_digest:
                full_keys.add(key_digest)
        if not _is_safe_id(receipt.get("sampler")):
            failures.append(f"{label}.sampler must be a finite enum id")
        if not isinstance(receipt.get("parameters"), Mapping):
            failures.append(f"{label}.parameters must be an object")
        if not _is_sha256(receipt.get("draw_sha256")):
            failures.append(f"{label}.draw_sha256 must be a SHA-256 digest")
        else:
            try:
                expected_draw_hash = canonical_sha256(
                    {
                        "key": receipt.get("key"),
                        "sampler": receipt.get("sampler"),
                        "parameters": receipt.get("parameters"),
                        "value": receipt.get("value"),
                    }
                )
            except (TypeError, ValueError):
                expected_draw_hash = None
                failures.append(f"{label} draw is not finite canonical JSON")
            if receipt.get("draw_sha256") != expected_draw_hash:
                failures.append(f"{label}.draw_sha256 does not bind the draw receipt")
    try:
        receipt_digest = canonical_sha256(receipts)
    except (TypeError, ValueError):
        receipt_digest = None
        failures.append("rng.receipts is not finite canonical JSON")
    if rng.get("receipts_sha256") != receipt_digest:
        failures.append("rng.receipts_sha256 does not match rng.receipts")

    referenced: set[str] = set()
    evaluations = episode.get("evaluations")
    if isinstance(evaluations, Mapping):
        for branch_name, branch in evaluations.items():
            for index, trial in enumerate(_branch_trials(branch)):
                ids = trial.get("rng_receipt_ids")
                if not isinstance(ids, list):
                    continue
                for receipt_id in ids:
                    if receipt_id not in receipt_ids:
                        failures.append(
                            f"evaluations.{branch_name}.trials[{index}] references "
                            f"unknown RNG receipt {receipt_id!r}"
                        )
                    elif isinstance(receipt_id, str):
                        referenced.add(receipt_id)
    return _check(
        "rng_receipts",
        failures,
        facts={
            "receipt_count": len(receipts),
            "unique_receipt_ids": len(receipt_ids),
            "unique_full_keys": len(full_keys),
            "referenced_receipt_ids": len(referenced),
        },
    )


def _resource_bounds(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    limits = episode.get("limits")
    expected = {
        "max_population": HARD_MAX_POPULATION,
        "max_cohorts": HARD_MAX_COHORTS,
        "max_generations": HARD_MAX_GENERATIONS,
        "max_archive_records": HARD_MAX_ARCHIVE_RECORDS,
        "max_horizontal_transfers": HARD_MAX_HORIZONTAL_TRANSFERS,
    }
    if not isinstance(limits, Mapping):
        return _check("resource_bounds", ["limits must be an object"])
    if set(limits) != set(expected):
        missing = sorted(set(expected) - set(limits))
        extra = sorted(set(limits) - set(expected))
        if missing:
            failures.append("limits missing fields: " + ", ".join(missing))
        if extra:
            failures.append("limits has unexpected fields: " + ", ".join(extra))
    for key, hard_max in expected.items():
        value = limits.get(key)
        if not _is_int(value, minimum=1):
            failures.append(f"limits.{key} must be a positive integer")
        elif value > hard_max:
            failures.append(f"limits.{key} exceeds sealed hard maximum {hard_max}")
    actual_pairs = (
        ("population", "max_population"),
        ("cohorts", "max_cohorts"),
        ("generations", "max_generations"),
    )
    for actual_name, limit_name in actual_pairs:
        actual = episode.get(actual_name)
        limit = limits.get(limit_name)
        if not _is_int(actual, minimum=1):
            failures.append(f"{actual_name} must be a positive integer")
        elif _is_int(limit, minimum=1) and actual > limit:
            failures.append(f"{actual_name} exceeds limits.{limit_name}")
    return _check(
        "resource_bounds",
        failures,
        facts={
            "population": episode.get("population"),
            "cohorts": episode.get("cohorts"),
            "generations": episode.get("generations"),
        },
    )


def _cohort_isolation(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    turnovers = episode.get("cohort_turnovers")
    cohort_count = episode.get("cohorts")
    if not isinstance(turnovers, list):
        return _check("cohort_isolation", ["cohort_turnovers must be a list"])
    if _is_int(cohort_count, minimum=1) and len(turnovers) != cohort_count - 1:
        failures.append("cohort_turnovers must contain exactly cohorts - 1 receipts")
    activated_history: list[set[str]] = []
    previous_activated: set[str] | None = None
    expected_fields = {
        "from_cohort",
        "to_cohort",
        "retired_host_ids",
        "activated_host_ids",
        "need_to_signal",
    }
    population = episode.get("population")
    for index, turnover in enumerate(turnovers):
        label = f"cohort_turnovers[{index}]"
        if not isinstance(turnover, Mapping):
            failures.append(f"{label} must be an object")
            continue
        if set(turnover) != expected_fields:
            failures.append(f"{label} must contain exactly the turnover receipt fields")
        source = turnover.get("from_cohort")
        target = turnover.get("to_cohort")
        if source != index or target != index + 1:
            failures.append(f"{label} must record consecutive cohort {index}->{index + 1}")
        retired_raw = turnover.get("retired_host_ids")
        activated_raw = turnover.get("activated_host_ids")
        if not isinstance(retired_raw, list) or any(
            not _is_safe_id(value) for value in retired_raw
        ):
            failures.append(f"{label}.retired_host_ids must be an opaque-id list")
            retired: set[str] = set()
        else:
            retired = set(retired_raw)
            if len(retired) != len(retired_raw):
                failures.append(f"{label}.retired_host_ids contains duplicates")
        if not isinstance(activated_raw, list) or any(
            not _is_safe_id(value) for value in activated_raw
        ):
            failures.append(f"{label}.activated_host_ids must be an opaque-id list")
            activated: set[str] = set()
        else:
            activated = set(activated_raw)
            if len(activated) != len(activated_raw):
                failures.append(f"{label}.activated_host_ids contains duplicates")
        if retired & activated:
            failures.append(f"{label} reactivates a retired host in the next cohort")
        if _is_int(population, minimum=1):
            if len(retired) != population or len(activated) != population:
                failures.append(f"{label} must retire and activate the full population")
        if previous_activated is not None and retired != previous_activated:
            failures.append(f"{label}.retired_host_ids differs from prior activation")
        if any(activated & prior for prior in activated_history):
            failures.append(f"{label} activates a host used by an earlier cohort")
        activated_history.append(activated)
        previous_activated = activated
        mapping = turnover.get("need_to_signal")
        if not isinstance(mapping, Mapping) or set(mapping) != {
            "C0",
            "C1",
            "C2",
            "C3",
        }:
            failures.append(f"{label}.need_to_signal must map every C0..C3 need")
        elif any(value not in {"S0", "S1", "S2", "S3"} for value in mapping.values()):
            failures.append(
                f"{label}.need_to_signal values must each be in S0..S3"
            )
    return _check(
        "cohort_isolation",
        failures,
        facts={"turnover_count": len(turnovers)},
    )


def _validate_ancestry_rows(
    rows: Any,
    *,
    label: str,
    cohort_count: Any,
) -> tuple[list[str], set[str]]:
    failures: list[str] = []
    identifiers: set[str] = set()
    if not isinstance(rows, list) or not rows:
        return [f"{label} must be a non-empty list"], identifiers
    for index, row in enumerate(rows):
        row_label = f"{label}[{index}]"
        if not isinstance(row, Mapping):
            failures.append(f"{row_label} must be an object")
            continue
        if set(row) != {"id", "parent_ids", "cohort"}:
            failures.append(f"{row_label} must contain exactly id, parent_ids, cohort")
        identifier = row.get("id")
        if not _is_safe_id(identifier):
            failures.append(f"{row_label}.id is invalid")
        elif identifier in identifiers:
            failures.append(f"{row_label}.id is duplicated")
        parents = row.get("parent_ids")
        if not isinstance(parents, list) or any(
            not _is_safe_id(parent) for parent in parents
        ):
            failures.append(f"{row_label}.parent_ids must be an opaque-id list")
        else:
            if len(set(parents)) != len(parents):
                failures.append(f"{row_label}.parent_ids contains duplicates")
            unknown = [parent for parent in parents if parent not in identifiers]
            if unknown:
                failures.append(f"{row_label}.parent_ids must precede their child")
        cohort = row.get("cohort")
        if not _is_int(cohort):
            failures.append(f"{row_label}.cohort must be non-negative")
        elif _is_int(cohort_count, minimum=1) and cohort >= cohort_count:
            failures.append(f"{row_label}.cohort is outside the episode")
        if _is_safe_id(identifier):
            identifiers.add(identifier)
    return failures, identifiers


def _validate_policy_ancestry_table(
    value: Any,
    *,
    role: str,
    cohort_count: Any,
) -> tuple[list[str], set[str]]:
    failures: list[str] = []
    identifiers: set[str] = set()
    label = f"{role}_policy_ancestry"
    if not isinstance(value, Mapping) or set(value) != {
        "columns",
        "rows",
        "rows_sha256",
    }:
        return [f"{label} must be an exact columnar receipt table"], identifiers
    if value.get("columns") != list(POLICY_ANCESTRY_COLUMNS):
        failures.append(f"{label}.columns differ from the registered policy schema")
    rows = value.get("rows")
    if not isinstance(rows, list) or not rows:
        failures.append(f"{label}.rows must be a non-empty list")
        rows = []
    try:
        rows_sha256 = canonical_sha256(rows)
    except (TypeError, ValueError):
        rows_sha256 = None
        failures.append(f"{label}.rows are not finite canonical JSON")
    if value.get("rows_sha256") != rows_sha256:
        failures.append(f"{label}.rows_sha256 does not bind its rows")
    prefix = "SP-" if role == "sender" else "RP-"
    receipt_prefix = "SPA:" if role == "sender" else "RPA:"
    allowed_alleles = (
        {"S0", "S1", "S2", "S3"}
        if role == "sender"
        else {"K0", "K1", "K2", "K3"}
    )
    chronology: dict[str, tuple[int, int]] = {}
    for index, raw_row in enumerate(rows):
        row_label = f"{label}.rows[{index}]"
        if not isinstance(raw_row, list) or len(raw_row) != len(
            POLICY_ANCESTRY_COLUMNS
        ):
            failures.append(f"{row_label} must match the registered column count")
            continue
        row = dict(zip(POLICY_ANCESTRY_COLUMNS, raw_row))
        identifier = row["policy_lineage_id"]
        if not _is_safe_id(identifier) or not identifier.startswith(prefix):
            failures.append(f"{row_label}.policy_lineage_id has the wrong role namespace")
        elif identifier in identifiers:
            failures.append(f"{row_label}.policy_lineage_id is duplicated")
        parents = row["parent_policy_lineage_ids"]
        if not isinstance(parents, list) or any(
            not _is_safe_id(parent) for parent in parents
        ):
            failures.append(f"{row_label}.parent_policy_lineage_ids is invalid")
            parents = []
        else:
            if len(parents) != len(set(parents)):
                failures.append(f"{row_label}.parent_policy_lineage_ids has duplicates")
            if any(parent not in identifiers for parent in parents):
                failures.append(f"{row_label} policy parents must precede their child")
        cohort = row["cohort_id"]
        generation = row["generation"]
        if not _is_int(cohort):
            failures.append(f"{row_label}.cohort_id must be non-negative")
        elif _is_int(cohort_count, minimum=1) and cohort >= cohort_count:
            failures.append(f"{row_label}.cohort_id is outside the episode")
        if not _is_int(generation):
            failures.append(f"{row_label}.generation must be non-negative")
        if _is_int(cohort) and _is_int(generation):
            for parent in parents:
                parent_time = chronology.get(parent)
                if parent_time is not None and parent_time > (cohort, generation):
                    failures.append(f"{row_label} predates a policy parent")
        origin_kind = row["origin_kind"]
        if origin_kind not in {
            "initialization",
            "mutation",
            "horizontal_transfer",
            "propagule",
        }:
            failures.append(f"{row_label}.origin_kind is unregistered")
        if origin_kind == "initialization" and (
            parents or cohort != 0 or generation != 0
        ):
            failures.append(f"{row_label} initialization must be parentless at C0/G0")
        if origin_kind in {"mutation", "propagule"} and len(parents) != 1:
            failures.append(f"{row_label} {origin_kind} must have exactly one parent")
        if origin_kind == "horizontal_transfer" and len(parents) not in {1, 2}:
            failures.append(f"{row_label} horizontal transfer needs one or two parents")
        alleles = row["allele_values"]
        if (
            not isinstance(alleles, list)
            or len(alleles) != 4
            or any(allele not in allowed_alleles for allele in alleles)
        ):
            failures.append(f"{row_label}.allele_values has the wrong role alphabet")
        if row["alleles_hash"] != (
            canonical_sha256(alleles) if isinstance(alleles, list) else None
        ):
            failures.append(f"{row_label}.alleles_hash does not bind allele_values")
        if row["ancestry_receipt_id"] != f"{receipt_prefix}{identifier}":
            failures.append(f"{row_label}.ancestry_receipt_id is invalid")
        if _is_safe_id(identifier):
            identifiers.add(identifier)
            if _is_int(cohort) and _is_int(generation):
                chronology[identifier] = (cohort, generation)
    return failures, identifiers


def _ancestry_separation(episode: Mapping[str, Any]) -> dict[str, Any]:
    host_failures, host_ids = _validate_ancestry_rows(
        episode.get("host_ancestry"),
        label="host_ancestry",
        cohort_count=episode.get("cohorts"),
    )
    sender_failures, sender_ids = _validate_policy_ancestry_table(
        episode.get("sender_policy_ancestry"),
        role="sender",
        cohort_count=episode.get("cohorts"),
    )
    receiver_failures, receiver_ids = _validate_policy_ancestry_table(
        episode.get("receiver_policy_ancestry"),
        role="receiver",
        cohort_count=episode.get("cohorts"),
    )
    failures = host_failures + sender_failures + receiver_failures
    if host_ids & (sender_ids | receiver_ids):
        failures.append("host and policy ancestry ids must be disjoint")
    if sender_ids & receiver_ids:
        failures.append("sender and receiver policy ancestry ids must be disjoint")
    return _check(
        "ancestry_separation",
        failures,
        facts={
            "host_lineages": len(host_ids),
            "sender_policy_lineages": len(sender_ids),
            "receiver_policy_lineages": len(receiver_ids),
        },
    )


def _validate_columnar_table(
    value: Any,
    *,
    label: str,
    expected_columns: Sequence[str],
) -> tuple[list[str], list[list[Any]]]:
    failures: list[str] = []
    if not isinstance(value, Mapping) or set(value) != {
        "columns",
        "rows",
        "rows_sha256",
    }:
        return [f"{label} must be an exact columnar receipt table"], []
    if value.get("columns") != list(expected_columns):
        failures.append(f"{label}.columns differ from the registered schema")
    rows = value.get("rows")
    if not isinstance(rows, list):
        failures.append(f"{label}.rows must be a list")
        rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(expected_columns):
            failures.append(f"{label}.rows[{index}] has the wrong column count")
    try:
        rows_hash = canonical_sha256(rows)
    except (TypeError, ValueError):
        rows_hash = None
        failures.append(f"{label}.rows are not finite canonical JSON")
    if value.get("rows_sha256") != rows_hash:
        failures.append(f"{label}.rows_sha256 does not bind its rows")
    return failures, rows


def _policy_audit_receipts(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    audit = episode.get("audit_receipts")
    exact_audit_fields = {
        "schema",
        "required_fields_sha256",
        "field_coverage",
        "id_templates",
        "episode",
        "generation_batches",
        "policy_transition_batches",
        "interaction_batches",
        "propagation_rows",
        "archive_rows",
        "probe_pairs",
        "probe",
        "tables_sha256",
        "audit_receipts_sha256",
    }
    if not isinstance(audit, Mapping) or set(audit) != exact_audit_fields:
        return _check(
            "policy_audit_receipts",
            ["audit_receipts must contain the exact registered audit fields"],
        )
    if audit.get("schema") != AUDIT_SCHEMA:
        failures.append(f"audit_receipts.schema must equal {AUDIT_SCHEMA}")
    if audit.get("required_fields_sha256") != REQUIRED_AUDIT_FIELDS_SHA256:
        failures.append("audit_receipts.required_fields_sha256 is unregistered")
    if audit.get("field_coverage") != AUDIT_FIELD_COVERAGE:
        failures.append("audit_receipts.field_coverage differs from the 73-field map")
    if audit.get("id_templates") != AUDIT_ID_TEMPLATES:
        failures.append("audit_receipts.id_templates differ from registered role templates")

    table_specs = {
        "generation_batches": GENERATION_BATCH_COLUMNS,
        "policy_transition_batches": POLICY_TRANSITION_BATCH_COLUMNS,
        "interaction_batches": INTERACTION_BATCH_COLUMNS,
        "propagation_rows": PROPAGATION_ROW_COLUMNS,
        "archive_rows": ARCHIVE_ROW_COLUMNS,
        "probe_pairs": PROBE_PAIR_COLUMNS,
    }
    table_rows: dict[str, list[list[Any]]] = {}
    for table_name, columns in table_specs.items():
        table_failures, rows = _validate_columnar_table(
            audit.get(table_name),
            label=f"audit_receipts.{table_name}",
            expected_columns=columns,
        )
        failures.extend(table_failures)
        table_rows[table_name] = rows

    table_row_hashes = {
        "sender_policy_ancestry": (
            episode.get("sender_policy_ancestry", {}).get("rows_sha256")
            if isinstance(episode.get("sender_policy_ancestry"), Mapping)
            else None
        ),
        "receiver_policy_ancestry": (
            episode.get("receiver_policy_ancestry", {}).get("rows_sha256")
            if isinstance(episode.get("receiver_policy_ancestry"), Mapping)
            else None
        ),
        **{
            name: (
                audit.get(name, {}).get("rows_sha256")
                if isinstance(audit.get(name), Mapping)
                else None
            )
            for name in table_specs
        },
    }
    if audit.get("tables_sha256") != canonical_sha256(table_row_hashes):
        failures.append("audit_receipts.tables_sha256 does not bind all eight tables")
    try:
        audit_hash = canonical_sha256(
            {
                key: value
                for key, value in audit.items()
                if key != "audit_receipts_sha256"
            }
        )
    except (TypeError, ValueError):
        audit_hash = None
        failures.append("audit_receipts are not finite canonical JSON")
    if audit.get("audit_receipts_sha256") != audit_hash:
        failures.append("audit_receipts_sha256 does not bind the audit receipt")

    audit_episode = audit.get("episode")
    episode_fields = {
        "episode_seed",
        "condition_id",
        "candidate_regime_id",
        "base_habitat_graph_hash",
        "ood_habitat_graph_hash",
        "ood_removed_edge_receipt",
        "ood_added_edge_receipt",
        "ood_graph_transform_hash",
        "probe_feedback_to_fitness",
        "cohort_overlap",
        "hazard_flags",
    }
    if not isinstance(audit_episode, Mapping) or set(audit_episode) != episode_fields:
        failures.append("audit_receipts.episode has the wrong fields")
        audit_episode = {}
    if audit_episode.get("episode_seed") != episode.get("seed"):
        failures.append("audit episode_seed differs from episode.seed")
    for key in ("condition_id", "candidate_regime_id"):
        if not _is_safe_id(audit_episode.get(key)):
            failures.append(f"audit_receipts.episode.{key} is invalid")
    if audit_episode.get("probe_feedback_to_fitness") is not False:
        failures.append("audit probe_feedback_to_fitness must be false")
    if audit_episode.get("cohort_overlap") is not False:
        failures.append("audit cohort_overlap must be false")
    hazard_flags = audit_episode.get("hazard_flags")
    expected_hazards = {
        "external_io": False,
        "arbitrary_text_payload": False,
        "executable_payload": False,
        "receiver_truth_leak": False,
        "propagule_observation": False,
    }
    if hazard_flags != expected_hazards:
        failures.append("audit hazard_flags must be the exact all-false safety receipt")

    checkpoint = episode.get("frozen_checkpoint")
    projection = checkpoint.get("projection") if isinstance(checkpoint, Mapping) else None
    transform = (
        projection.get("ood_graph_transform")
        if isinstance(projection, Mapping)
        else None
    )
    checkpoint_bindings = {
        "base_habitat_graph_hash": (
            projection.get("habitat_graph_sha256")
            if isinstance(projection, Mapping)
            else None
        ),
        "ood_habitat_graph_hash": (
            projection.get("ood_habitat_graph_sha256")
            if isinstance(projection, Mapping)
            else None
        ),
        "ood_removed_edge_receipt": (
            transform.get("removed_edge") if isinstance(transform, Mapping) else None
        ),
        "ood_added_edge_receipt": (
            transform.get("added_edge") if isinstance(transform, Mapping) else None
        ),
        "ood_graph_transform_hash": (
            transform.get("transform_sha256")
            if isinstance(transform, Mapping)
            else None
        ),
    }
    for key, expected in checkpoint_bindings.items():
        if audit_episode.get(key) != expected:
            failures.append(f"audit_receipts.episode.{key} differs from checkpoint")

    population = episode.get("population")
    for index, row in enumerate(table_rows["generation_batches"]):
        if len(row) != len(GENERATION_BATCH_COLUMNS):
            continue
        record = dict(zip(GENERATION_BATCH_COLUMNS, row))
        cohort = record["cohort_id"]
        generation = record["generation"]
        if not _is_int(cohort) or not _is_int(generation):
            failures.append(f"generation_batches.rows[{index}] has invalid time")
        if record["active_host_population_count"] != population:
            failures.append(f"generation_batches.rows[{index}] population differs")
        if not _is_sha256(record["active_host_roster_hash"]):
            failures.append(f"generation_batches.rows[{index}] roster hash is invalid")
        if record["sender_policy_credit_receipt_id"] != f"SPC:{cohort}:{generation}":
            failures.append(f"generation_batches.rows[{index}] sender credit id is invalid")
        if record["receiver_policy_credit_receipt_id"] != f"RPC:{cohort}:{generation}":
            failures.append(f"generation_batches.rows[{index}] receiver credit id is invalid")
        for key in ("sender_credit_values_q6", "receiver_credit_values_q6"):
            values = record[key]
            if (
                not isinstance(values, list)
                or not _is_int(population, minimum=1)
                or len(values) != population
                or any(not _is_number(value) for value in values)
            ):
                failures.append(f"generation_batches.rows[{index}].{key} is invalid")

    sender_policy_records = {
        row.get("policy_lineage_id"): row
        for row in _policy_ancestry_records(episode, "sender")
        if _is_safe_id(row.get("policy_lineage_id"))
    }
    sender_policy_ids = set(sender_policy_records)
    receiver_policy_records = {
        row.get("policy_lineage_id"): row
        for row in _policy_ancestry_records(episode, "receiver")
        if _is_safe_id(row.get("policy_lineage_id"))
    }
    receiver_policy_ids = set(receiver_policy_records)
    archive_value = episode.get("archive")
    archive_records_value = (
        archive_value.get("records")
        if isinstance(archive_value, Mapping)
        else []
    )
    archive_records = (
        archive_records_value if isinstance(archive_records_value, list) else []
    )
    archive_record_map = {
        record.get("record_id"): record
        for record in archive_records
        if isinstance(record, Mapping)
        and _is_safe_id(record.get("record_id"))
    }
    archive_delivery_events: dict[str, list[dict[str, Any]]] = {}
    propagated_events: dict[str, tuple[Any, ...]] = {}
    for batch_index, row in enumerate(table_rows["interaction_batches"]):
        if len(row) != len(INTERACTION_BATCH_COLUMNS):
            continue
        cohort, generation, events = row
        if not _is_int(cohort) or not _is_int(generation) or not isinstance(events, list):
            failures.append(f"interaction_batches.rows[{batch_index}] is malformed")
            continue
        for event_index, event in enumerate(events):
            label = f"interaction_batches.rows[{batch_index}].events[{event_index}]"
            if not isinstance(event, list) or len(event) != len(INTERACTION_EVENT_COLUMNS):
                failures.append(f"{label} has the wrong event columns")
                continue
            record = dict(zip(INTERACTION_EVENT_COLUMNS, event))
            if record["sender_id"] == record["receiver_id"]:
                failures.append(f"{label} reuses one host across both roles")
            if record["sender_policy_lineage_id"] not in sender_policy_ids:
                failures.append(f"{label} has an unrecorded sender policy")
            if record["receiver_policy_lineage_id"] not in receiver_policy_ids:
                failures.append(f"{label} has an unrecorded receiver policy")
            need = record["pressure_class_evaluator_only"]
            expected_skill = f"K{need[1:]}" if need in {"C0", "C1", "C2", "C3"} else None
            if record["required_skill_evaluator_only"] != expected_skill:
                failures.append(f"{label} has an invalid evaluator-only skill relation")
            if not _is_signal_id(record["signal_id"]):
                failures.append(f"{label}.signal_id is invalid")
            live_need = record["live_pressure_class_evaluator_only"]
            if live_need not in {"C0", "C1", "C2", "C3"}:
                failures.append(
                    f"{label}.live_pressure_class_evaluator_only is invalid"
                )
            if not _is_signal_id(record["live_signal_id"]):
                failures.append(f"{label}.live_signal_id is invalid")
            live_sender_policy = sender_policy_records.get(
                record["sender_policy_lineage_id"]
            )
            live_sender_alleles = (
                live_sender_policy.get("allele_values")
                if isinstance(live_sender_policy, Mapping)
                else None
            )
            if (
                live_need in {"C0", "C1", "C2", "C3"}
                and isinstance(live_sender_alleles, list)
                and len(live_sender_alleles) == 4
                and record["live_signal_id"]
                != live_sender_alleles[int(str(live_need)[1:])]
            ):
                failures.append(
                    f"{label}.live_signal_id differs from the live sender policy"
                )
            if not isinstance(record["sender_reward_eligible"], bool):
                failures.append(f"{label}.sender_reward_eligible must be boolean")
            archive_record_id = record["archive_record_id"]
            if archive_record_id is None:
                if need != live_need:
                    failures.append(
                        f"{label} nonarchive task pressure differs from live pressure"
                    )
                if record["sender_reward_eligible"] is not True:
                    failures.append(
                        f"{label} nonarchive sender must remain reward eligible"
                    )
            else:
                archived_record = archive_record_map.get(archive_record_id)
                if not isinstance(archived_record, Mapping):
                    failures.append(f"{label}.archive_record_id is unretained")
                else:
                    delayed_binding = archived_record.get("delayed_task_binding")
                    abstract_signal = archived_record.get("abstract_signal")
                    if not isinstance(delayed_binding, Mapping) or (
                        delayed_binding.get("pressure_class_evaluator_only") != need
                        or delayed_binding.get("required_skill_evaluator_only")
                        != record["required_skill_evaluator_only"]
                    ):
                        failures.append(
                            f"{label} effective task differs from its delayed binding"
                        )
                    if not isinstance(abstract_signal, Mapping) or (
                        abstract_signal.get("signal_id") != record["signal_id"]
                    ):
                        failures.append(
                            f"{label} effective signal differs from its archive record"
                        )
                    elif (
                        abstract_signal.get("delivery_host_id")
                        != record["receiver_id"]
                        or abstract_signal.get("delivery_opportunity_id")
                        != record["opportunity_id"]
                    ):
                        failures.append(
                            f"{label} archive delivery receipt differs from its event"
                        )
                    archive_delivery_events.setdefault(
                        str(archive_record_id), []
                    ).append(record)
                if record["sender_reward_eligible"] is not False:
                    failures.append(
                        f"{label} delayed sender reward must be suppressed"
                    )
            if record["machine_id"] not in MACHINE_IDS:
                failures.append(f"{label}.machine_id is invalid")
            if record["chosen_skill"] not in {"K0", "K1", "K2", "K3"}:
                failures.append(f"{label}.chosen_skill is invalid")
            receiver_policy = receiver_policy_records.get(
                record["receiver_policy_lineage_id"]
            )
            receiver_alleles = (
                receiver_policy.get("allele_values")
                if isinstance(receiver_policy, Mapping)
                else None
            )
            if (
                _is_signal_id(record["signal_id"])
                and isinstance(receiver_alleles, list)
                and len(receiver_alleles) == 4
                and record["chosen_skill"]
                != receiver_alleles[int(str(record["signal_id"])[1:])]
            ):
                failures.append(
                    f"{label}.chosen_skill differs from the receiver policy input"
                )
            for key in ("eligibility", "emission", "delivery", "receiver_activation"):
                if not isinstance(record[key], bool):
                    failures.append(f"{label}.{key} must be boolean")
            expected_input_hash = canonical_sha256(
                {
                    "opportunity_id": record["opportunity_id"],
                    "receiver_id": record["receiver_id"],
                    "receiver_policy_lineage_id": record[
                        "receiver_policy_lineage_id"
                    ],
                    "machine_id": record["machine_id"],
                    "signal_id": record["signal_id"],
                    "archive_record_id": record["archive_record_id"],
                }
            )
            if record["receiver_policy_input_hash"] != expected_input_hash:
                failures.append(f"{label}.receiver_policy_input_hash is invalid")
            receipt_id = record["propagation_edge_receipt_id"]
            source_node = record["propagation_source_node_id"]
            target_node = record["propagation_target_node_id"]
            if receipt_id is None:
                if source_node is not None or target_node is not None:
                    failures.append(f"{label} has propagation nodes without receipt")
            elif (
                not _is_safe_id(receipt_id)
                or source_node not in MACHINE_IDS
                or target_node not in MACHINE_IDS
                or target_node != record["machine_id"]
                or source_node == target_node
            ):
                failures.append(f"{label} has an invalid propagation edge receipt")
            else:
                propagated_events[receipt_id] = (
                    cohort,
                    generation,
                    record["opportunity_id"],
                    source_node,
                    target_node,
                )

    propagation_receipts: dict[str, tuple[Any, ...]] = {}
    for index, row in enumerate(table_rows["propagation_rows"]):
        if len(row) != len(PROPAGATION_ROW_COLUMNS):
            continue
        record = dict(zip(PROPAGATION_ROW_COLUMNS, row))
        receipt_id = record["receipt_id"]
        if not _is_safe_id(receipt_id) or receipt_id in propagation_receipts:
            failures.append(f"propagation_rows.rows[{index}].receipt_id is invalid")
            continue
        propagation_receipts[receipt_id] = (
            record["cohort_id"],
            record["generation"],
            record["opportunity_id"],
            record["source_node_id"],
            record["target_node_id"],
        )
        if not _is_sha256(record["declared_graph_hash"]):
            failures.append(f"propagation_rows.rows[{index}] graph hash is invalid")
    if propagation_receipts != propagated_events:
        failures.append("propagation_rows do not close the interaction propagation receipts")

    if isinstance(archive_records, list):
        for record in archive_records:
            if not isinstance(record, Mapping):
                continue
            abstract_signal = record.get("abstract_signal")
            if not isinstance(abstract_signal, Mapping):
                continue
            record_id = record.get("record_id")
            observed = archive_delivery_events.get(str(record_id), [])
            if abstract_signal.get("delivery_status") == "delivered":
                if len(observed) != 1:
                    failures.append(
                        f"archive record {record_id!r} must bind exactly one delivery event"
                    )
            elif observed:
                failures.append(
                    f"undelivered archive record {record_id!r} appears in interaction events"
                )

    expected_archive_rows: list[list[Any]] = []
    if isinstance(archive_records, list):
        for record in archive_records:
            if not isinstance(record, Mapping):
                continue
            propagule = record.get("convention_propagule")
            delayed_binding = record.get("delayed_task_binding")
            if not isinstance(propagule, Mapping) or not isinstance(
                delayed_binding, Mapping
            ):
                continue
            activated = propagule.get("activation_host_id") is not None
            sender_result_id = propagule.get(
                "activation_sender_policy_lineage_id"
            )
            receiver_result_id = propagule.get(
                "activation_receiver_policy_lineage_id"
            )
            sender_state_change = (
                sender_result_id
                != propagule.get("replaced_sender_policy_lineage_id")
                if activated
                else None
            )
            receiver_state_change = (
                receiver_result_id
                != propagule.get("replaced_receiver_policy_lineage_id")
                if activated
                else None
            )
            expected_archive_rows.append(
                [
                    record.get("record_id"),
                    (
                        record.get("wake_cohort") - record.get("origin_cohort")
                        if _is_int(record.get("wake_cohort"))
                        and _is_int(record.get("origin_cohort"))
                        else None
                    ),
                    propagule.get("propagule_id"),
                    propagule.get("propagule_sender_source_policy_lineage_id"),
                    propagule.get("propagule_receiver_source_policy_lineage_id"),
                    propagule.get("propagule_sender_policy_allele_values"),
                    propagule.get("propagule_receiver_policy_allele_values"),
                    propagule.get("propagule_sender_policy_alleles_hash"),
                    propagule.get("propagule_receiver_policy_alleles_hash"),
                    propagule.get("propagule_payload_hash"),
                    record.get("wake_cohort"),
                    propagule.get("activation_host_id"),
                    sender_result_id if sender_state_change else None,
                    receiver_result_id if receiver_state_change else None,
                    sender_result_id,
                    receiver_result_id,
                    sender_state_change,
                    receiver_state_change,
                    f"PA:{record.get('record_id')}" if activated else None,
                    propagule.get("visible_as_observation"),
                    delayed_binding.get("binding_id"),
                    delayed_binding.get("pressure_class_evaluator_only"),
                    delayed_binding.get("required_skill_evaluator_only"),
                ]
            )
    if table_rows["archive_rows"] != expected_archive_rows:
        failures.append("audit archive_rows differ from retained archive records")

    evaluations = episode.get("evaluations")
    expected_probe_pairs: list[list[Any]] = []
    permutation_metrics: Mapping[str, Any] = {}
    if isinstance(evaluations, Mapping):
        intact = _trial_map(evaluations.get("intact"))
        for row in _branch_trials(evaluations.get("symbol_swap")):
            opportunity_id = row.get("opportunity_id")
            intact_row = intact.get(opportunity_id)
            expected_probe_pairs.append(
                [
                    row.get("counterfactual_pair_id"),
                    intact_row.get("opportunity_id")
                    if isinstance(intact_row, Mapping)
                    else None,
                    opportunity_id,
                ]
            )
        permutation = evaluations.get("per_message_permutation")
        metrics = permutation.get("metrics") if isinstance(permutation, Mapping) else None
        if isinstance(metrics, Mapping):
            permutation_metrics = metrics
    if table_rows["probe_pairs"] != expected_probe_pairs:
        failures.append("audit probe_pairs differ from frozen symbol-swap pairs")
    probe = audit.get("probe")
    probe_fields = {
        "matched_event_ids_hash",
        "intact_signal_histogram_hash",
        "permuted_signal_histogram_hash",
        "event_index_permutation_hash",
    }
    if not isinstance(probe, Mapping) or set(probe) != probe_fields:
        failures.append("audit_receipts.probe has the wrong fields")
    else:
        for key in probe_fields:
            if not _is_sha256(probe.get(key)) or probe.get(key) != permutation_metrics.get(key):
                failures.append(f"audit_receipts.probe.{key} differs from permutation metrics")

    return _check(
        "policy_audit_receipts",
        failures,
        facts={
            "required_field_count": len(REQUIRED_AUDIT_FIELDS),
            "generation_batch_count": len(table_rows["generation_batches"]),
            "interaction_batch_count": len(table_rows["interaction_batches"]),
            "archive_row_count": len(table_rows["archive_rows"]),
        },
    )
def _selection_firewall(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    selection = episode.get("selection")
    if not isinstance(selection, Mapping):
        return _check("selection_firewall", ["selection must be an object"])
    required = {"fitness_metric", "fitness_inputs", "probe_feedback_to_fitness"}
    if set(selection) != required:
        missing = sorted(required - set(selection))
        extra = sorted(set(selection) - required)
        if missing:
            failures.append("selection missing fields: " + ", ".join(missing))
        if extra:
            failures.append("selection has unexpected fields: " + ", ".join(extra))
    if selection.get("fitness_metric") != "ecological_task_reward":
        failures.append("selection fitness_metric must be ecological_task_reward")
    if selection.get("fitness_inputs") != ["ecological_task_reward"]:
        failures.append("ecological_task_reward must be the only selection input")
    if selection.get("probe_feedback_to_fitness") is not False:
        failures.append("probe feedback to selection fitness must be disabled")
    for path, key, value in _walk(selection, "selection"):
        candidates = [key, value] if isinstance(value, str) else [key]
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            lowered = candidate.casefold()
            if any(token in lowered for token in _EVIDENCE_TOKENS):
                failures.append(f"{path} places an evidence metric in selection")
                break
    return _check(
        "selection_firewall",
        failures,
        facts={"fitness_metric": selection.get("fitness_metric")},
    )


def _abstract_containment(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    forbidden_strings = 0
    for path, key, value in _walk(episode):
        if isinstance(key, str):
            lowered_key = key.casefold()
            registered_false_hazard = (
                path == "episode.audit_receipts.episode.hazard_flags.free_text"
                and value is False
            )
            if (
                any(part in lowered_key for part in _FORBIDDEN_KEY_PARTS)
                and not registered_false_hazard
            ):
                failures.append(f"{path} uses forbidden capability field {key!r}")
        if not isinstance(value, str):
            continue
        is_digest = _is_sha256(value)
        if (
            _URI.search(value)
            or _WINDOWS_PATH.search(value)
            or _UNC_PATH.search(value)
            or _IPV4.search(value)
            or "../" in value
            or "..\\" in value
            or value.startswith(("/", "\\"))
            or _SHELL_META.search(value)
        ):
            forbidden_strings += 1
            failures.append(f"{path} contains a path, network, or shell-shaped value")
        elif not is_digest and any(character.isspace() for character in value):
            forbidden_strings += 1
            failures.append(f"{path} contains raw prose")
        elif not is_digest and not _is_safe_id(value):
            forbidden_strings += 1
            failures.append(f"{path} is not an opaque enum/id value")

    archive = episode.get("archive")
    records = archive.get("records") if isinstance(archive, Mapping) else None
    if isinstance(records, list):
        sender_policy_rows = {
            row.get("policy_lineage_id"): row
            for row in _policy_ancestry_records(episode, "sender")
            if _is_safe_id(row.get("policy_lineage_id"))
        }
        receiver_policy_rows = {
            row.get("policy_lineage_id"): row
            for row in _policy_ancestry_records(episode, "receiver")
            if _is_safe_id(row.get("policy_lineage_id"))
        }
        activated_hosts_by_cohort = {
            row.get("to_cohort"): set(row.get("activated_host_ids", []))
            for row in episode.get("cohort_turnovers", [])
            if isinstance(row, Mapping)
            and _is_int(row.get("to_cohort"))
            and isinstance(row.get("activated_host_ids"), list)
        }
        rng_rows = {
            row.get("receipt_id"): row
            for row in episode.get("rng", {}).get("receipts", [])
            if isinstance(row, Mapping) and _is_safe_id(row.get("receipt_id"))
        } if isinstance(episode.get("rng"), Mapping) else {}
        rng_ids = set(rng_rows)
        propagule_ids: set[str] = set()
        delayed_binding_ids: set[str] = set()
        delayed_context_counts = {f"C{index}": 0 for index in range(4)}
        required_record_fields = {
            "record_id",
            "origin_cohort",
            "wake_cohort",
            "status",
            "overt",
            "abstract_signal",
            "delayed_task_binding",
            "convention_propagule",
            "latent_evaluator_metadata",
        }
        overt_fields = {
            "record_id",
            "origin_cohort",
            "generation",
            "delivery_status",
        }
        for index, record in enumerate(records):
            label = f"archive.records[{index}]"
            if not isinstance(record, Mapping):
                failures.append(f"{label} must be an object")
                continue
            if set(record) != required_record_fields:
                failures.append(f"{label} must contain only sealed archive fields")
            if not _is_safe_id(record.get("record_id")):
                failures.append(f"{label}.record_id is invalid")
            if record.get("status") not in {"dormant", "woken", "expired"}:
                failures.append(f"{label}.status must be dormant, woken, or expired")
            for key in ("origin_cohort", "wake_cohort"):
                if not _is_int(record.get(key)):
                    failures.append(f"{label}.{key} must be non-negative")
            if (
                _is_int(record.get("origin_cohort"))
                and _is_int(record.get("wake_cohort"))
                and record.get("wake_cohort") <= record.get("origin_cohort")
            ):
                failures.append(f"{label}.wake_cohort must follow origin_cohort")
            overt = record.get("overt")
            abstract_signal = record.get("abstract_signal")
            delayed_binding = record.get("delayed_task_binding")
            propagule = record.get("convention_propagule")
            latent = record.get("latent_evaluator_metadata")
            if not isinstance(overt, Mapping) or set(overt) != overt_fields:
                failures.append(f"{label}.overt must contain only abstract overt metadata")
            elif overt.get("record_id") != record.get("record_id"):
                failures.append(f"{label}.overt.record_id differs from the archive row")
            abstract_signal_fields = {
                "record_id",
                "signal_id",
                "scheduled_wake_cohort",
                "delivery_status",
                "visible_as_observation",
                "may_affect_action",
                "may_affect_policy",
                "delivery_host_id",
                "delivery_opportunity_id",
            }
            if (
                not isinstance(abstract_signal, Mapping)
                or set(abstract_signal) != abstract_signal_fields
            ):
                failures.append(
                    f"{label}.abstract_signal must contain the exact causal signal fields"
                )
            else:
                if abstract_signal.get("record_id") != record.get("record_id"):
                    failures.append(
                        f"{label}.abstract_signal.record_id differs from archive row"
                    )
                if not _is_signal_id(abstract_signal.get("signal_id")):
                    failures.append(
                        f"{label}.abstract_signal.signal_id must be one of S0..S3"
                    )
                if abstract_signal.get("scheduled_wake_cohort") != record.get(
                    "wake_cohort"
                ):
                    failures.append(
                        f"{label}.abstract_signal.scheduled_wake_cohort differs from wake_cohort"
                    )
                delivery_status = abstract_signal.get("delivery_status")
                if delivery_status not in {
                    "dormant",
                    "queued",
                    "delivered",
                    "expired",
                }:
                    failures.append(
                        f"{label}.abstract_signal.delivery_status is invalid"
                    )
                if abstract_signal.get("visible_as_observation") is not True:
                    failures.append(
                        f"{label}.abstract_signal.visible_as_observation must be true"
                    )
                if abstract_signal.get("may_affect_action") is not True:
                    failures.append(
                        f"{label}.abstract_signal.may_affect_action must be true"
                    )
                if abstract_signal.get("may_affect_policy") is not False:
                    failures.append(
                        f"{label}.abstract_signal.may_affect_policy must be false"
                    )
                delivery_host = abstract_signal.get("delivery_host_id")
                delivery_opportunity = abstract_signal.get(
                    "delivery_opportunity_id"
                )
                if delivery_host is not None and not _is_safe_id(delivery_host):
                    failures.append(
                        f"{label}.abstract_signal.delivery_host_id is invalid"
                    )
                if delivery_opportunity is not None and not _is_safe_id(
                    delivery_opportunity
                ):
                    failures.append(
                        f"{label}.abstract_signal.delivery_opportunity_id is invalid"
                    )
                if delivery_status == "dormant":
                    if delivery_host is not None or delivery_opportunity is not None:
                        failures.append(
                            f"{label} dormant abstract signal cannot carry delivery ids"
                        )
                elif delivery_status == "queued":
                    if delivery_host is None or delivery_opportunity is not None:
                        failures.append(
                            f"{label} queued abstract signal needs only delivery_host_id"
                        )
                elif delivery_status == "delivered":
                    if delivery_host is None or delivery_opportunity is None:
                        failures.append(
                            f"{label} delivered abstract signal needs host and opportunity receipts"
                        )
                elif delivery_status == "expired" and delivery_opportunity is not None:
                    failures.append(
                        f"{label} expired abstract signal cannot carry an opportunity id"
                    )

            delayed_binding_fields = {
                "binding_id",
                "pressure_class_evaluator_only",
                "required_skill_evaluator_only",
                "visible_to_agents",
                "may_affect_task_truth",
                "may_affect_reward",
                "may_affect_policy_input",
            }
            if (
                not isinstance(delayed_binding, Mapping)
                or set(delayed_binding) != delayed_binding_fields
            ):
                failures.append(
                    f"{label}.delayed_task_binding must contain the exact evaluator-only task fields"
                )
            else:
                binding_id = delayed_binding.get("binding_id")
                if binding_id != f"DT-{record.get('record_id')}":
                    failures.append(
                        f"{label}.delayed_task_binding.binding_id differs from the archive row"
                    )
                elif binding_id in delayed_binding_ids:
                    failures.append(
                        f"{label}.delayed_task_binding.binding_id is duplicated"
                    )
                else:
                    delayed_binding_ids.add(binding_id)
                delayed_context = delayed_binding.get(
                    "pressure_class_evaluator_only"
                )
                expected_delayed_skill = (
                    f"K{delayed_context[1:]}"
                    if delayed_context in delayed_context_counts
                    else None
                )
                if delayed_context not in delayed_context_counts:
                    failures.append(
                        f"{label}.delayed_task_binding pressure must be one of C0..C3"
                    )
                else:
                    delayed_context_counts[delayed_context] += 1
                if delayed_binding.get(
                    "required_skill_evaluator_only"
                ) != expected_delayed_skill:
                    failures.append(
                        f"{label}.delayed_task_binding task pressure and skill are mismatched"
                    )
                expected_binding_flags = {
                    "visible_to_agents": False,
                    "may_affect_task_truth": True,
                    "may_affect_reward": True,
                    "may_affect_policy_input": False,
                }
                for key, expected in expected_binding_flags.items():
                    if delayed_binding.get(key) is not expected:
                        failures.append(
                            f"{label}.delayed_task_binding.{key} must be {str(expected).lower()}"
                        )

            latent_fields = {
                "provenance_id",
                "visible_to_agents",
                "may_affect_action",
                "may_affect_policy",
            }
            if not isinstance(latent, Mapping) or set(latent) != latent_fields:
                failures.append(
                    f"{label}.latent_evaluator_metadata must contain exact noncausal fields"
                )
            else:
                if not _is_safe_id(latent.get("provenance_id")):
                    failures.append(
                        f"{label}.latent_evaluator_metadata.provenance_id is invalid"
                    )
                for key in (
                    "visible_to_agents",
                    "may_affect_action",
                    "may_affect_policy",
                ):
                    if latent.get(key) is not False:
                        failures.append(
                            f"{label}.latent_evaluator_metadata.{key} must be false"
                        )

            propagule_fields = {
                "propagule_id",
                "propagule_sender_source_policy_lineage_id",
                "propagule_receiver_source_policy_lineage_id",
                "source_rng_receipt_ids",
                "propagule_sender_policy_allele_values",
                "propagule_receiver_policy_allele_values",
                "propagule_sender_policy_alleles_hash",
                "propagule_receiver_policy_alleles_hash",
                "propagule_payload_hash",
                "may_affect_policy",
                "visible_as_observation",
                "activation_host_id",
                "activation_sender_policy_lineage_id",
                "activation_receiver_policy_lineage_id",
                "replaced_sender_policy_lineage_id",
                "replaced_receiver_policy_lineage_id",
            }
            if not isinstance(propagule, Mapping) or set(propagule) != propagule_fields:
                failures.append(
                    f"{label}.convention_propagule must contain the exact heredity fields"
                )
                continue
            propagule_id = propagule.get("propagule_id")
            if not _is_safe_id(propagule_id):
                failures.append(f"{label}.convention_propagule.propagule_id is invalid")
            elif propagule_id in propagule_ids:
                failures.append(
                    f"{label}.convention_propagule.propagule_id is duplicated"
                )
            else:
                propagule_ids.add(propagule_id)
            sender_source_id = propagule.get(
                "propagule_sender_source_policy_lineage_id"
            )
            receiver_source_id = propagule.get(
                "propagule_receiver_source_policy_lineage_id"
            )
            for key, source_id, policy_rows in (
                (
                    "propagule_sender_source_policy_lineage_id",
                    sender_source_id,
                    sender_policy_rows,
                ),
                (
                    "propagule_receiver_source_policy_lineage_id",
                    receiver_source_id,
                    receiver_policy_rows,
                ),
            ):
                source_row = policy_rows.get(source_id)
                if not isinstance(source_row, Mapping):
                    failures.append(
                        f"{label}.convention_propagule.{key} is absent from its role ancestry"
                    )
                elif (
                    _is_int(source_row.get("cohort_id"))
                    and _is_int(record.get("origin_cohort"))
                    and source_row.get("cohort_id") > record.get("origin_cohort")
                ):
                    failures.append(
                        f"{label}.convention_propagule.{key} is future-dated"
                    )
            source_receipts = propagule.get("source_rng_receipt_ids")
            if (
                not isinstance(source_receipts, list)
                or len(source_receipts) != 2
                or len(set(source_receipts)) != 2
                or any(receipt_id not in rng_ids for receipt_id in source_receipts)
            ):
                failures.append(
                    f"{label}.convention_propagule.source_rng_receipt_ids must be two unique RNG receipts"
                )
            else:
                expected_namespaces = (
                    "archive.propagule.sender",
                    "archive.propagule.receiver",
                )
                for receipt_id, expected_namespace in zip(
                    source_receipts, expected_namespaces
                ):
                    receipt = rng_rows.get(receipt_id, {})
                    key = receipt.get("key", {}) if isinstance(receipt, Mapping) else {}
                    if not isinstance(key, Mapping) or (
                        key.get("namespace") != expected_namespace
                        or key.get("branch") != "training"
                        or key.get("cohort") != record.get("origin_cohort")
                        or key.get("generation") != (
                            overt.get("generation")
                            if isinstance(overt, Mapping)
                            else None
                        )
                        or key.get("event_kind") != "archive-deposit"
                        or key.get("draw_name") != "source"
                        or not isinstance(key.get("entity_ids"), list)
                        or f"record:{record.get('record_id')}"
                        not in key.get("entity_ids", [])
                    ):
                        failures.append(
                            f"{label}.convention_propagule source RNG stream does not match its policy block"
                        )
            sender_alleles = propagule.get(
                "propagule_sender_policy_allele_values"
            )
            if (
                not isinstance(sender_alleles, list)
                or len(sender_alleles) != 4
                or any(not _is_signal_id(value) for value in sender_alleles)
            ):
                failures.append(
                    f"{label}.convention_propagule sender allele values must contain four S0..S3 entries"
                )
            receiver_alleles = propagule.get(
                "propagule_receiver_policy_allele_values"
            )
            if (
                not isinstance(receiver_alleles, list)
                or len(receiver_alleles) != 4
                or any(value not in {"K0", "K1", "K2", "K3"} for value in receiver_alleles)
            ):
                failures.append(
                    f"{label}.convention_propagule receiver allele values must contain four K0..K3 entries"
                )
            sender_source_row = sender_policy_rows.get(sender_source_id)
            receiver_source_row = receiver_policy_rows.get(receiver_source_id)
            if (
                isinstance(sender_source_row, Mapping)
                and sender_source_row.get("allele_values") != sender_alleles
            ):
                failures.append(
                    f"{label}.convention_propagule sender alleles differ from the source policy"
                )
            if (
                isinstance(receiver_source_row, Mapping)
                and receiver_source_row.get("allele_values") != receiver_alleles
            ):
                failures.append(
                    f"{label}.convention_propagule receiver alleles differ from the source policy"
                )
            delayed_context = (
                delayed_binding.get("pressure_class_evaluator_only")
                if isinstance(delayed_binding, Mapping)
                else None
            )
            if (
                delayed_context in delayed_context_counts
                and isinstance(sender_alleles, list)
                and len(sender_alleles) == 4
                and isinstance(abstract_signal, Mapping)
                and abstract_signal.get("signal_id")
                != sender_alleles[int(str(delayed_context)[1:])]
            ):
                failures.append(
                    f"{label}.abstract_signal.signal_id differs from the source sender policy at its bound context"
                )
            if propagule.get("propagule_sender_policy_alleles_hash") != (
                canonical_sha256(sender_alleles)
                if isinstance(sender_alleles, list)
                else None
            ):
                failures.append(
                    f"{label}.convention_propagule sender allele hash is invalid"
                )
            if propagule.get("propagule_receiver_policy_alleles_hash") != (
                canonical_sha256(receiver_alleles)
                if isinstance(receiver_alleles, list)
                else None
            ):
                failures.append(
                    f"{label}.convention_propagule receiver allele hash is invalid"
                )
            payload_projection = {
                "propagule_sender_source_policy_lineage_id": sender_source_id,
                "propagule_receiver_source_policy_lineage_id": receiver_source_id,
                "propagule_sender_policy_allele_values": sender_alleles,
                "propagule_receiver_policy_allele_values": receiver_alleles,
            }
            if propagule.get("propagule_payload_hash") != canonical_sha256(
                payload_projection
            ):
                failures.append(
                    f"{label}.convention_propagule payload hash is invalid"
                )
            if propagule.get("may_affect_policy") is not True:
                failures.append(
                    f"{label}.convention_propagule.may_affect_policy must be true"
                )
            if propagule.get("visible_as_observation") is not False:
                failures.append(
                    f"{label}.convention_propagule.visible_as_observation must be false"
                )
            activation_host = propagule.get("activation_host_id")
            if activation_host is not None and not _is_safe_id(activation_host):
                failures.append(
                    f"{label}.convention_propagule.activation_host_id is invalid"
                )
            activation_sender_id = propagule.get(
                "activation_sender_policy_lineage_id"
            )
            activation_receiver_id = propagule.get(
                "activation_receiver_policy_lineage_id"
            )
            replaced_sender_id = propagule.get(
                "replaced_sender_policy_lineage_id"
            )
            replaced_receiver_id = propagule.get(
                "replaced_receiver_policy_lineage_id"
            )
            activation_receipts = (
                activation_host,
                activation_sender_id,
                activation_receiver_id,
                replaced_sender_id,
                replaced_receiver_id,
            )
            for key, identifier in (
                ("activation_sender_policy_lineage_id", activation_sender_id),
                ("activation_receiver_policy_lineage_id", activation_receiver_id),
                ("replaced_sender_policy_lineage_id", replaced_sender_id),
                ("replaced_receiver_policy_lineage_id", replaced_receiver_id),
            ):
                if identifier is not None and not _is_safe_id(identifier):
                    failures.append(f"{label}.convention_propagule.{key} is invalid")
            if record.get("status") == "woken":
                if any(value is None for value in activation_receipts):
                    failures.append(
                        f"{label} woken propagule needs complete split-policy activation receipts"
                    )
                wake_cohort = record.get("wake_cohort")
                if activation_host not in activated_hosts_by_cohort.get(
                    wake_cohort, set()
                ):
                    failures.append(
                        f"{label} activation_host_id is not active in wake_cohort"
                    )
                for (
                    role,
                    activation_id,
                    replaced_id,
                    source_id,
                    policy_rows,
                    expected_alleles,
                ) in (
                    (
                        "sender",
                        activation_sender_id,
                        replaced_sender_id,
                        sender_source_id,
                        sender_policy_rows,
                        sender_alleles,
                    ),
                    (
                        "receiver",
                        activation_receiver_id,
                        replaced_receiver_id,
                        receiver_source_id,
                        receiver_policy_rows,
                        receiver_alleles,
                    ),
                ):
                    activated_row = policy_rows.get(activation_id)
                    replaced_row = policy_rows.get(replaced_id)
                    if not isinstance(activated_row, Mapping):
                        failures.append(
                            f"{label} activated {role} lineage is absent from its ancestry"
                        )
                    elif activation_id == replaced_id:
                        if activation_id != source_id:
                            failures.append(
                                f"{label} no-op {role} wake must retain the identical source lineage"
                            )
                        if activated_row.get("allele_values") != expected_alleles:
                            failures.append(
                                f"{label} no-op {role} lineage alleles differ from propagule"
                            )
                    else:
                        parents = activated_row.get(
                            "parent_policy_lineage_ids", []
                        )
                        if parents != [source_id]:
                            failures.append(
                                f"{label} changed {role} lineage must have only its propagule source parent"
                            )
                        if activated_row.get("origin_kind") != "propagule":
                            failures.append(
                                f"{label} changed {role} lineage lacks propagule origin"
                            )
                        if activated_row.get("allele_values") != expected_alleles:
                            failures.append(
                                f"{label} changed {role} lineage alleles differ from propagule"
                            )
                        if activated_row.get("cohort_id") != wake_cohort:
                            failures.append(
                                f"{label} activated {role} lineage cohort differs from wake_cohort"
                            )
                    if not isinstance(replaced_row, Mapping):
                        failures.append(
                            f"{label} replaced {role} lineage is absent from its ancestry"
                        )
                    elif (
                        _is_int(replaced_row.get("cohort_id"))
                        and _is_int(wake_cohort)
                        and replaced_row.get("cohort_id") > wake_cohort
                    ):
                        failures.append(
                            f"{label} replaced {role} lineage is future-dated"
                        )
            elif any(value is not None for value in activation_receipts):
                failures.append(
                    f"{label} non-woken propagule cannot carry activation or replacement ids"
                )

        if delayed_context_counts and (
            max(delayed_context_counts.values())
            - min(delayed_context_counts.values())
            > 1
        ):
            failures.append(
                "archive delayed task bindings must be balanced across C0..C3"
            )

    # Receiver policy surfaces may contain the typed delivered signal, but
    # never an archive record or latent evaluator object by reference/value.
    evaluations = episode.get("evaluations")
    if isinstance(evaluations, Mapping) and isinstance(records, list):
        protected_values = [
            value
            for record in records
            if isinstance(record, Mapping)
            for value in (
                record.get("latent_evaluator_metadata"),
                record.get("delayed_task_binding"),
                record.get("convention_propagule"),
            )
            if isinstance(value, Mapping)
        ]
        for branch_name, branch in evaluations.items():
            for index, trial in enumerate(_branch_trials(branch)):
                sender_observation = trial.get("sender_observation")
                if any(
                    _contains_object(sender_observation, value)
                    for value in protected_values
                ):
                    failures.append(
                        f"evaluations.{branch_name}.trials[{index}] exposes protected archive state to the sender"
                    )
                if isinstance(sender_observation, Mapping):
                    for sender_path, sender_key, _ in _walk(
                        sender_observation,
                        f"evaluations.{branch_name}.trials[{index}].sender_observation",
                    ):
                        if sender_key in {
                            "delayed_task_binding",
                            "delayed_task_binding_id",
                            "pressure_class_evaluator_only",
                            "required_skill_evaluator_only",
                        }:
                            failures.append(
                                f"{sender_path} exposes delayed evaluator truth"
                            )
                observation = trial.get("receiver_observation")
                if any(_contains_object(observation, value) for value in protected_values):
                    failures.append(
                        f"evaluations.{branch_name}.trials[{index}] exposes protected archive state"
                    )
                if isinstance(observation, Mapping):
                    for observation_path, observation_key, value in _walk(
                        observation,
                        f"evaluations.{branch_name}.trials[{index}].receiver_observation",
                    ):
                        if observation_key in {
                            "convention_propagule",
                            "delayed_task_binding",
                            "delayed_task_binding_id",
                            "pressure_class_evaluator_only",
                            "required_skill_evaluator_only",
                            "latent_evaluator_metadata",
                            "propagule_id",
                            "propagule_sender_source_policy_lineage_id",
                            "propagule_receiver_source_policy_lineage_id",
                            "propagule_sender_policy_allele_values",
                            "propagule_receiver_policy_allele_values",
                            "propagule_sender_policy_alleles_hash",
                            "propagule_receiver_policy_alleles_hash",
                            "propagule_payload_hash",
                            "source_rng_receipt_ids",
                            "activation_sender_policy_lineage_id",
                            "activation_receiver_policy_lineage_id",
                            "replaced_sender_policy_lineage_id",
                            "replaced_receiver_policy_lineage_id",
                            "provenance_id",
                        }:
                            failures.append(
                                f"{observation_path} exposes policy heredity or evaluator metadata"
                            )
                        if observation_key == "abstract_signal":
                            matching = [
                                record
                                for record in records
                                if isinstance(record, Mapping)
                                and record.get("abstract_signal") == value
                            ]
                            if not matching:
                                failures.append(
                                    f"{observation_path} is not a retained abstract signal receipt"
                                )
                            elif isinstance(value, Mapping) and (
                                value.get("delivery_host_id")
                                != trial.get("receiver_id")
                                or value.get("delivery_opportunity_id")
                                != trial.get("opportunity_id")
                            ):
                                failures.append(
                                    f"{observation_path} delivery receipt differs from trial"
                                )
    return _check(
        "abstract_containment",
        failures,
        facts={
            "forbidden_string_count": forbidden_strings,
            "archive_record_count": len(records) if isinstance(records, list) else 0,
        },
    )


def _archive_transfer_bounds(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    limits = episode.get("limits")
    archive_limit = (
        limits.get("max_archive_records") if isinstance(limits, Mapping) else None
    )
    transfer_limit = (
        limits.get("max_horizontal_transfers") if isinstance(limits, Mapping) else None
    )
    archive = episode.get("archive")
    if not isinstance(archive, Mapping):
        failures.append("archive must be an object")
        records: list[Any] = []
    else:
        expected = {"capacity", "peak_records", "wakes", "records"}
        if set(archive) != expected:
            failures.append("archive must contain exactly capacity, peak_records, wakes, records")
        capacity = archive.get("capacity")
        peak = archive.get("peak_records")
        wakes = archive.get("wakes")
        records_value = archive.get("records")
        records = records_value if isinstance(records_value, list) else []
        for key, value in (("capacity", capacity), ("peak_records", peak), ("wakes", wakes)):
            if not _is_int(value):
                failures.append(f"archive.{key} must be a non-negative integer")
        if not _is_int(capacity, minimum=1):
            failures.append("archive.capacity must be positive")
        if _is_int(archive_limit, minimum=1) and _is_int(capacity) and capacity > archive_limit:
            failures.append("archive.capacity exceeds limits.max_archive_records")
        if _is_int(capacity) and _is_int(peak) and peak > capacity:
            failures.append("archive.peak_records exceeds archive.capacity")
        if not isinstance(records_value, list):
            failures.append("archive.records must be a list")
        elif _is_int(capacity) and len(records) > capacity:
            failures.append("archive.records exceeds archive.capacity")
        record_ids = [
            record.get("record_id")
            for record in records
            if isinstance(record, Mapping)
        ]
        if len(record_ids) != len(set(record_ids)):
            failures.append("archive.record_id values must be unique")
        observed_wakes = sum(
            1
            for record in records
            if isinstance(record, Mapping) and record.get("status") == "woken"
        )
        if _is_int(wakes) and wakes < observed_wakes:
            failures.append("archive.wakes is lower than retained woken records")

    transfers = episode.get("horizontal_transfers")
    if not isinstance(transfers, list):
        failures.append("horizontal_transfers must be a list")
        transfers = []
    if _is_int(transfer_limit) and len(transfers) > transfer_limit:
        failures.append(
            "horizontal_transfers exceeds limits.max_horizontal_transfers"
        )
    transfer_ids: set[str] = set()
    sender_policy_rows = {
        row.get("policy_lineage_id"): row
        for row in _policy_ancestry_records(episode, "sender")
        if _is_safe_id(row.get("policy_lineage_id"))
    }
    receiver_policy_rows = {
        row.get("policy_lineage_id"): row
        for row in _policy_ancestry_records(episode, "receiver")
        if _is_safe_id(row.get("policy_lineage_id"))
    }
    rng_ids = {
        row.get("receipt_id")
        for row in episode.get("rng", {}).get("receipts", [])
        if isinstance(row, Mapping) and _is_safe_id(row.get("receipt_id"))
    } if isinstance(episode.get("rng"), Mapping) else set()
    transfer_fields = {
        "transfer_id",
        "transfer_type",
        "cohort",
        "generation",
        "donor_host_id",
        "recipient_host_id",
        "recipient_parent_policy_lineage_id",
        "donor_parent_policy_lineage_id",
        "child_policy_lineage_id",
        "policy_block",
        "allele_index",
        "prior_allele",
        "new_allele",
        "rng_receipt_ids",
    }
    for index, transfer in enumerate(transfers):
        label = f"horizontal_transfers[{index}]"
        if not isinstance(transfer, Mapping):
            failures.append(f"{label} must be an object")
            continue
        if set(transfer) != transfer_fields:
            failures.append(f"{label} must contain only typed convention-transfer fields")
        transfer_id = transfer.get("transfer_id")
        if not _is_safe_id(transfer_id):
            failures.append(f"{label}.transfer_id is invalid")
        elif transfer_id in transfer_ids:
            failures.append(f"{label}.transfer_id is duplicated")
        else:
            transfer_ids.add(transfer_id)
        if transfer.get("transfer_type") != "abstract_convention_allele":
            failures.append(
                f"{label}.transfer_type must be abstract_convention_allele"
            )
        for key in ("cohort", "generation"):
            if not _is_int(transfer.get(key)):
                failures.append(f"{label}.{key} must be non-negative")
        for key in ("donor_host_id", "recipient_host_id"):
            if not _is_safe_id(transfer.get(key)):
                failures.append(f"{label}.{key} is invalid")
        if transfer.get("donor_host_id") == transfer.get("recipient_host_id"):
            failures.append(f"{label} donor and recipient hosts must differ")
        policy_block = transfer.get("policy_block")
        policy_rows = (
            sender_policy_rows
            if policy_block == "sender"
            else receiver_policy_rows
            if policy_block == "receiver"
            else {}
        )
        recipient_parent_id = transfer.get(
            "recipient_parent_policy_lineage_id"
        )
        donor_parent_id = transfer.get("donor_parent_policy_lineage_id")
        child_policy_id = transfer.get("child_policy_lineage_id")
        if (
            recipient_parent_id not in policy_rows
            or donor_parent_id not in policy_rows
            or child_policy_id not in policy_rows
        ):
            failures.append(
                f"{label} must reference the affected role-specific policy ancestry"
            )
        if recipient_parent_id == donor_parent_id:
            failures.append(f"{label} recipient and donor policy parents must differ")
        recipient_parent_row = policy_rows.get(recipient_parent_id)
        donor_parent_row = policy_rows.get(donor_parent_id)
        child_row = policy_rows.get(child_policy_id)
        if isinstance(child_row, Mapping) and child_row.get(
            "parent_policy_lineage_ids"
        ) != [recipient_parent_id, donor_parent_id]:
            failures.append(
                f"{label}.child_policy_lineage_id must record ordered recipient and donor parents"
            )
        if isinstance(child_row, Mapping) and (
            child_row.get("origin_kind") != "horizontal_transfer"
            or child_row.get("cohort_id") != transfer.get("cohort")
            or child_row.get("generation") != transfer.get("generation")
        ):
            failures.append(
                f"{label}.child_policy_lineage_id lacks a matched horizontal-transfer ancestry receipt"
            )
        if policy_block not in {"sender", "receiver"}:
            failures.append(f"{label}.policy_block must be sender or receiver")
        allele_index = transfer.get("allele_index")
        if not _is_int(allele_index) or allele_index > 3:
            failures.append(f"{label}.allele_index must be an integer in [0, 3]")
        allowed_alleles = (
            {"S0", "S1", "S2", "S3"}
            if policy_block == "sender"
            else {"K0", "K1", "K2", "K3"}
            if policy_block == "receiver"
            else set()
        )
        prior_allele = transfer.get("prior_allele")
        new_allele = transfer.get("new_allele")
        if prior_allele not in allowed_alleles or new_allele not in allowed_alleles:
            failures.append(f"{label} prior_allele/new_allele use the wrong role alphabet")
        if _is_int(allele_index) and allele_index <= 3 and isinstance(
            child_row, Mapping
        ):
            donor_alleles = (
                donor_parent_row.get("allele_values")
                if isinstance(donor_parent_row, Mapping)
                else None
            )
            recipient_alleles = (
                recipient_parent_row.get("allele_values")
                if isinstance(recipient_parent_row, Mapping)
                else None
            )
            child_alleles = child_row.get("allele_values")
            if (
                not isinstance(recipient_alleles, list)
                or len(recipient_alleles) != 4
                or recipient_alleles[allele_index] != prior_allele
            ):
                failures.append(f"{label}.prior_allele differs from its recipient parent")
            if (
                not isinstance(donor_alleles, list)
                or len(donor_alleles) != 4
                or donor_alleles[allele_index] != new_allele
            ):
                failures.append(f"{label}.new_allele differs from its donor parent")
            if (
                not isinstance(child_alleles, list)
                or len(child_alleles) != 4
                or child_alleles[allele_index] != new_allele
            ):
                failures.append(f"{label}.new_allele differs from its child policy")
            if (
                isinstance(recipient_alleles, list)
                and len(recipient_alleles) == 4
                and isinstance(child_alleles, list)
                and len(child_alleles) == 4
                and any(
                    recipient_alleles[position] != child_alleles[position]
                    for position in range(4)
                    if position != allele_index
                )
            ):
                failures.append(f"{label} changes more than its declared allele_index")
        receipt_ids = transfer.get("rng_receipt_ids")
        if (
            not isinstance(receipt_ids, list)
            or not receipt_ids
            or any(receipt_id not in rng_ids for receipt_id in receipt_ids)
            or len(set(receipt_ids)) != len(receipt_ids)
        ):
            failures.append(f"{label}.rng_receipt_ids must reference unique RNG receipts")
        for path, key, _ in _walk(transfer, label):
            lowered = key.casefold() if isinstance(key, str) else ""
            if lowered in {
                "host_parent_id",
                "host_parent_ids",
                "host_genome",
                "host_ancestry",
            }:
                failures.append(f"{path} illegally transfers host ancestry")
    return _check(
        "archive_transfer_bounds",
        failures,
        facts={
            "archive_records": len(records),
            "horizontal_transfers": len(transfers),
        },
    )


def _edge_value(value: Any, label: str, failures: list[str]) -> frozenset[str] | None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(endpoint not in MACHINE_IDS for endpoint in value)
        or value[0] == value[1]
    ):
        failures.append(f"{label} must contain two distinct MACHINE_IDS")
        return None
    return frozenset((value[0], value[1]))


def _edge_set(value: Any, label: str, failures: list[str]) -> set[frozenset[str]]:
    if not isinstance(value, list):
        failures.append(f"{label} must be an edge list")
        return set()
    result: set[frozenset[str]] = set()
    for index, edge_value in enumerate(value):
        edge = _edge_value(edge_value, f"{label}[{index}]", failures)
        if edge is None:
            continue
        if edge in result:
            failures.append(f"{label}[{index}] duplicates an undirected edge")
        result.add(edge)
    return result


def _connected_six_node_graph(edges: set[frozenset[str]]) -> bool:
    nodes = set(MACHINE_IDS)
    present = set().union(*edges) if edges else set()
    if present != nodes:
        return False
    start = MACHINE_IDS[0]
    reached = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for edge in edges:
            if current not in edge:
                continue
            for neighbor in edge - {current}:
                if neighbor not in reached:
                    reached.add(neighbor)
                    frontier.append(neighbor)
    return reached == nodes


def _ood_transform_failures(projection: Any) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    transform = (
        projection.get("ood_graph_transform")
        if isinstance(projection, Mapping)
        else None
    )
    expected_fields = {
        "habitat_edges",
        "ood_edges",
        "removed_edge",
        "added_edge",
        "connected",
        "transform_sha256",
    }
    if not isinstance(transform, Mapping) or set(transform) != expected_fields:
        return (
            [
                "frozen_checkpoint.projection.ood_graph_transform must contain the exact transform receipt fields"
            ],
            {},
        )
    habitat_edges = _edge_set(
        transform.get("habitat_edges"),
        "frozen_checkpoint.projection.ood_graph_transform.habitat_edges",
        failures,
    )
    ood_edges = _edge_set(
        transform.get("ood_edges"),
        "frozen_checkpoint.projection.ood_graph_transform.ood_edges",
        failures,
    )
    removed_edge = _edge_value(
        transform.get("removed_edge"),
        "frozen_checkpoint.projection.ood_graph_transform.removed_edge",
        failures,
    )
    added_edge = _edge_value(
        transform.get("added_edge"),
        "frozen_checkpoint.projection.ood_graph_transform.added_edge",
        failures,
    )
    if len(habitat_edges) != len(ood_edges):
        failures.append("OOD transform must preserve the habitat edge count")
    removed = habitat_edges - ood_edges
    added = ood_edges - habitat_edges
    if len(removed) != 1 or removed_edge not in removed:
        failures.append("OOD transform must remove exactly its declared removed_edge")
    if len(added) != 1 or added_edge not in added:
        failures.append("OOD transform must add exactly its declared added_edge")
    habitat_connected = _connected_six_node_graph(habitat_edges)
    ood_connected = _connected_six_node_graph(ood_edges)
    if not habitat_connected:
        failures.append("habitat_edges must form a connected six-node graph")
    if not ood_connected or transform.get("connected") is not True:
        failures.append("ood_edges must independently form a connected six-node graph")
    try:
        transform_hash = canonical_sha256(
            {
                key: value
                for key, value in transform.items()
                if key != "transform_sha256"
            }
        )
    except (TypeError, ValueError):
        transform_hash = None
        failures.append("OOD transform is not finite canonical JSON")
    if transform.get("transform_sha256") != transform_hash:
        failures.append("OOD transform_sha256 does not bind the transform fields")
    return failures, {
        "habitat_edge_count": len(habitat_edges),
        "ood_edge_count": len(ood_edges),
        "habitat_connected": habitat_connected,
        "ood_connected": ood_connected,
    }


def _deterministic_hashes(episode: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    checkpoint = episode.get("frozen_checkpoint")
    checkpoint_hash: Any = None
    projection: Any = None
    if not isinstance(checkpoint, Mapping):
        failures.append("frozen_checkpoint must be an object")
    else:
        if set(checkpoint) != {"projection", "sha256"}:
            failures.append("frozen_checkpoint must contain exactly projection and sha256")
        projection = checkpoint.get("projection")
        if not isinstance(projection, Mapping):
            failures.append("frozen_checkpoint.projection must be an object")
        try:
            checkpoint_hash = canonical_sha256(projection)
        except (TypeError, ValueError):
            failures.append("frozen_checkpoint.projection is not finite canonical JSON")
        if checkpoint.get("sha256") != checkpoint_hash:
            failures.append("frozen_checkpoint.sha256 does not match its projection")

    ood_failures, ood_facts = _ood_transform_failures(projection)
    failures.extend(ood_failures)

    evaluations = episode.get("evaluations")
    if isinstance(evaluations, Mapping):
        for branch_name, branch in evaluations.items():
            if not isinstance(branch, Mapping):
                continue
            if branch.get("checkpoint_sha256") != checkpoint_hash:
                failures.append(
                    f"evaluations.{branch_name}.checkpoint_sha256 differs from frozen checkpoint"
                )
            if branch.get("projection_sha256") != checkpoint_hash:
                failures.append(
                    f"evaluations.{branch_name}.projection_sha256 differs from frozen projection"
                )
    try:
        projection_hash = canonical_sha256(deterministic_projection(episode))
    except (TypeError, ValueError):
        projection_hash = None
        failures.append("deterministic projection is not finite canonical JSON")
    if episode.get("deterministic_projection_sha256") != projection_hash:
        failures.append(
            "deterministic_projection_sha256 does not match deterministic projection"
        )
    try:
        episode_hash = canonical_sha256(
            {key: value for key, value in episode.items() if key != "episode_sha256"}
        )
    except (TypeError, ValueError):
        episode_hash = None
        failures.append("episode is not finite canonical JSON")
    if episode.get("episode_sha256") != episode_hash:
        failures.append("episode_sha256 does not match the sealed episode")
    return _check(
        "deterministic_hashes",
        failures,
        facts={"checkpoint_sha256": checkpoint_hash, **ood_facts},
    )


_VERIFIERS = {
    "episode_schema": _episode_schema,
    "frozen_branches": _frozen_branches,
    "opportunity_receipts": _opportunity_receipts,
    "rng_receipts": _rng_receipts,
    "resource_bounds": _resource_bounds,
    "cohort_isolation": _cohort_isolation,
    "ancestry_separation": _ancestry_separation,
    "policy_audit_receipts": _policy_audit_receipts,
    "selection_firewall": _selection_firewall,
    "abstract_containment": _abstract_containment,
    "archive_transfer_bounds": _archive_transfer_bounds,
    "deterministic_hashes": _deterministic_hashes,
}


def verify_episode(episode: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Verify one ecology episode and return a detached JSON report.

    Malformed caller input never raises from this entrypoint.  Each independent
    verifier fails closed so a broken field cannot suppress the remaining
    audit facts.
    """

    candidate: Mapping[str, Any]
    if isinstance(episode, Mapping):
        candidate = episode
    else:
        candidate = {}
    checks: dict[str, dict[str, Any]] = {}
    for verifier_id in REQUIRED_VERIFIERS:
        function = _VERIFIERS[verifier_id]
        try:
            check = function(candidate)
        except Exception as error:  # fail closed at the public trust boundary
            check = _check(
                verifier_id,
                [f"verifier could not validate malformed input: {type(error).__name__}"],
            )
        checks[verifier_id] = check
    if not isinstance(episode, Mapping):
        checks["episode_schema"] = _check(
            "episode_schema", ["episode must be a JSON object"]
        )
    failed = [
        verifier_id
        for verifier_id in REQUIRED_VERIFIERS
        if not checks[verifier_id]["passed"]
    ]
    return {
        "schema": VERIFICATION_SCHEMA,
        "accepted": not failed,
        "episode_id": candidate.get("episode_id"),
        "episode_schema": candidate.get("schema"),
        "checks": checks,
        "failed_required_verifiers": failed,
        "model_only": True,
        "external_io_performed": False,
    }


__all__ = [
    "BASE_BRANCHES",
    "EPISODE_SCHEMA",
    "REQUIRED_VERIFIERS",
    "TRIAL_FIELDS",
    "canonical_sha256",
    "deterministic_projection",
    "seal_episode",
    "verify_episode",
]
