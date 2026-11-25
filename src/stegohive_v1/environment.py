"""Bounded adaptive Lewis-signaling ecology for StegoHive v1.

This module is deliberately data-only.  Its four signals, four contexts, four
skills, habitat links, archives, and visibility labels are invented simulation
enums.  It exposes no prose message, codec, shell, path, socket, or external I/O
surface.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .rng import DeterministicRNGLedger, RNGKey
from .storyworld_tools import events_at
from .types import (
    CONTEXT_IDS,
    EPISODE_SCHEMA,
    EVALUATION_BRANCHES,
    MACHINE_IDS,
    MAX_COHORTS,
    MAX_GENERATIONS_PER_COHORT,
    MAX_POPULATION,
    MAX_ARCHIVE_CAPACITY,
    SIGNAL_IDS,
    SKILL_IDS,
    canonical_sha256,
    deep_copy_json,
    default_config,
    validate_condition,
    validate_config,
)


MAX_HORIZONTAL_TRANSFERS = 256

AUDIT_SCHEMA = "alife.stegohive.audit_receipts.v1"
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
REQUIRED_AUDIT_FIELDS_SHA256 = (
    "b953613e5bf6bca68e53afea1f070735fcc3d70b67bf3df5a5102283ea074c54"
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
    "active_host_population_count": (
        "generation_batches.active_host_population_count"
    ),
    "active_host_roster_hash": "generation_batches.active_host_roster_hash",
    "sender_id": "interaction_batches.events.sender_id",
    "sender_host_lineage_id": (
        "interaction_batches.events.sender_host_lineage_id"
    ),
    "sender_policy_lineage_id": (
        "interaction_batches.events.sender_policy_lineage_id"
    ),
    "receiver_id": "interaction_batches.events.receiver_id",
    "receiver_host_lineage_id": (
        "interaction_batches.events.receiver_host_lineage_id"
    ),
    "receiver_policy_lineage_id": (
        "interaction_batches.events.receiver_policy_lineage_id"
    ),
    "sender_policy_parent_receipt_id": (
        "id_templates.sender_policy_parent_receipt_id"
    ),
    "receiver_policy_parent_receipt_id": (
        "id_templates.receiver_policy_parent_receipt_id"
    ),
    "sender_policy_mutation_receipt_id": (
        "id_templates.sender_policy_mutation_receipt_id"
    ),
    "receiver_policy_mutation_receipt_id": (
        "id_templates.receiver_policy_mutation_receipt_id"
    ),
    "sender_policy_credit_receipt_id": (
        "generation_batches.sender_policy_credit_receipt_id"
    ),
    "receiver_policy_credit_receipt_id": (
        "generation_batches.receiver_policy_credit_receipt_id"
    ),
    "sender_policy_ancestry_receipt_id": (
        "sender_policy_ancestry.ancestry_receipt_id"
    ),
    "receiver_policy_ancestry_receipt_id": (
        "receiver_policy_ancestry.ancestry_receipt_id"
    ),
    "pressure_class_evaluator_only": (
        "interaction_batches.events.pressure_class_evaluator_only"
    ),
    "required_skill_evaluator_only": (
        "interaction_batches.events.required_skill_evaluator_only"
    ),
    "signal_id": "interaction_batches.events.signal_id",
    "archive_record_id": "archive_rows.archive_record_id",
    "archive_delay_cohorts": "archive_rows.archive_delay_cohorts",
    "convention_propagule_id": "archive_rows.convention_propagule_id",
    "propagule_sender_source_policy_lineage_id": (
        "archive_rows.propagule_sender_source_policy_lineage_id"
    ),
    "propagule_receiver_source_policy_lineage_id": (
        "archive_rows.propagule_receiver_source_policy_lineage_id"
    ),
    "propagule_sender_policy_allele_values": (
        "archive_rows.propagule_sender_policy_allele_values"
    ),
    "propagule_receiver_policy_allele_values": (
        "archive_rows.propagule_receiver_policy_allele_values"
    ),
    "propagule_sender_policy_alleles_hash": (
        "archive_rows.propagule_sender_policy_alleles_hash"
    ),
    "propagule_receiver_policy_alleles_hash": (
        "archive_rows.propagule_receiver_policy_alleles_hash"
    ),
    "propagule_payload_hash": "archive_rows.propagule_payload_hash",
    "propagule_wake_cohort": "archive_rows.propagule_wake_cohort",
    "propagule_target_host_id": "archive_rows.propagule_target_host_id",
    "propagule_child_sender_policy_lineage_id": (
        "archive_rows.propagule_child_sender_policy_lineage_id"
    ),
    "propagule_child_receiver_policy_lineage_id": (
        "archive_rows.propagule_child_receiver_policy_lineage_id"
    ),
    "propagule_result_sender_policy_lineage_id": (
        "archive_rows.propagule_result_sender_policy_lineage_id"
    ),
    "propagule_result_receiver_policy_lineage_id": (
        "archive_rows.propagule_result_receiver_policy_lineage_id"
    ),
    "propagule_sender_role_state_change": (
        "archive_rows.propagule_sender_role_state_change"
    ),
    "propagule_receiver_role_state_change": (
        "archive_rows.propagule_receiver_role_state_change"
    ),
    "propagule_activation_receipt_id": (
        "archive_rows.propagule_activation_receipt_id"
    ),
    "delayed_task_binding_id": "archive_rows.delayed_task_binding_id",
    "delayed_pressure_class_evaluator_only": (
        "archive_rows.delayed_pressure_class_evaluator_only"
    ),
    "delayed_required_skill_evaluator_only": (
        "archive_rows.delayed_required_skill_evaluator_only"
    ),
    "live_pressure_class_evaluator_only": (
        "interaction_batches.events.live_pressure_class_evaluator_only"
    ),
    "live_signal_id": "interaction_batches.events.live_signal_id",
    "sender_reward_eligible": (
        "interaction_batches.events.sender_reward_eligible"
    ),
    "propagule_visible_to_agents": (
        "archive_rows.propagule_visible_to_agents"
    ),
    "propagation_source_node_id": (
        "interaction_batches.events.propagation_source_node_id"
    ),
    "propagation_target_node_id": (
        "interaction_batches.events.propagation_target_node_id"
    ),
    "propagation_edge_receipt_id": (
        "interaction_batches.events.propagation_edge_receipt_id"
    ),
    "base_habitat_graph_hash": "episode.base_habitat_graph_hash",
    "ood_habitat_graph_hash": "episode.ood_habitat_graph_hash",
    "ood_removed_edge_receipt": "episode.ood_removed_edge_receipt",
    "ood_added_edge_receipt": "episode.ood_added_edge_receipt",
    "ood_graph_transform_hash": "episode.ood_graph_transform_hash",
    "eligibility": "interaction_batches.events.eligibility",
    "emission": "interaction_batches.events.emission",
    "delivery": "interaction_batches.events.delivery",
    "receiver_activation": (
        "interaction_batches.events.receiver_activation"
    ),
    "receiver_policy_input_hash": (
        "interaction_batches.events.receiver_policy_input_hash"
    ),
    "chosen_skill": "interaction_batches.events.chosen_skill",
    "counterfactual_pair_id": "probe_pairs.counterfactual_pair_id",
    "matched_event_ids_hash": "probe.matched_event_ids_hash",
    "intact_signal_histogram_hash": "probe.intact_signal_histogram_hash",
    "permuted_signal_histogram_hash": (
        "probe.permuted_signal_histogram_hash"
    ),
    "event_index_permutation_hash": "probe.event_index_permutation_hash",
    "probe_feedback_to_fitness": "episode.probe_feedback_to_fitness",
    "cohort_overlap": "episode.cohort_overlap",
    "hazard_flags": "episode.hazard_flags",
}


def _columnar(
    columns: Sequence[str], rows: Sequence[Sequence[Any]]
) -> dict[str, Any]:
    detached_rows = deep_copy_json(list(rows))
    return {
        "columns": list(columns),
        "rows": detached_rows,
        "rows_sha256": canonical_sha256(detached_rows),
    }


def _advance_digest(current: str, row: Mapping[str, Any]) -> str:
    """Extend a compact deterministic trace without retaining the raw row."""

    return canonical_sha256({"prior_sha256": current, "row": row})


def _graph_edges(graph: Mapping[str, Sequence[str]]) -> list[list[str]]:
    return [
        list(edge)
        for edge in sorted(
            {
                tuple(sorted((left, right)))
                for left, neighbors in graph.items()
                for right in neighbors
            }
        )
    ]


def _key(
    namespace: str,
    branch: str,
    cohort: int,
    generation: int,
    event_kind: str,
    entity_ids: Sequence[str],
    draw_name: str,
) -> RNGKey:
    return RNGKey(
        namespace=namespace,
        branch=branch,
        cohort=cohort,
        generation=generation,
        event_kind=event_kind,
        entity_ids=tuple(entity_ids),
        draw_name=draw_name,
    )


def _draw_integer(
    ledger: DeterministicRNGLedger,
    key: RNGKey,
    stop: int,
    *,
    start: int = 0,
) -> tuple[int, str]:
    value = ledger.integer(key, stop, start=start)
    return value, ledger.receipt_id_for(key)


def _draw_bernoulli(
    ledger: DeterministicRNGLedger, key: RNGKey, probability: float
) -> tuple[bool, str]:
    value = ledger.bernoulli(key, probability)
    return value, ledger.receipt_id_for(key)


def _draw_permutation(
    ledger: DeterministicRNGLedger, key: RNGKey, size: int
) -> tuple[list[int], str]:
    value = ledger.permutation(key, size)
    return value, ledger.receipt_id_for(key)


def _draw_weighted(
    ledger: DeterministicRNGLedger, key: RNGKey, weights: Sequence[float]
) -> tuple[int, str]:
    value = ledger.weighted_index(key, weights)
    return value, ledger.receipt_id_for(key)


def _skill_for_context(context: str) -> str:
    return SKILL_IDS[CONTEXT_IDS.index(context)]


def _signal_label(index: int) -> str:
    return SIGNAL_IDS[int(index)]


def _signal_index(value: str) -> int:
    return SIGNAL_IDS.index(value)


def _accuracy(rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round(sum(bool(row["correct_outcome"]) for row in rows) / len(rows), 6)


def checkpoint_hash(projection: Mapping[str, Any]) -> str:
    """Hash a detached frozen population projection."""

    return canonical_sha256(deep_copy_json(projection))


def deterministic_projection(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stable replay projection bound by the episode receipt."""

    fields = (
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
    return deep_copy_json({field: episode[field] for field in fields})


class _EcologyRunner:
    def __init__(
        self,
        config: Mapping[str, Any],
        condition: Mapping[str, Any],
        seed: int,
    ) -> None:
        self.config = dict(config)
        self.condition = dict(condition)
        self.seed = seed
        self.rng = DeterministicRNGLedger(seed)
        self.extra_ledgers: list[DeterministicRNGLedger] = []

        self.population: list[dict[str, Any]] = []
        self.next_sender_policy_id = 0
        self.next_receiver_policy_id = 0
        self.host_ancestry: list[dict[str, Any]] = []
        self.sender_policy_ancestry: list[dict[str, Any]] = []
        self.receiver_policy_ancestry: list[dict[str, Any]] = []
        self.horizontal_transfers: list[dict[str, Any]] = []
        self.training_exposure: dict[str, Any] = {
            "eligible": 0,
            "emitted": 0,
            "delivered": 0,
            "actions_executed": 0,
            "correct": 0,
            "need_counts": {context: 0 for context in CONTEXT_IDS},
        }
        self.training_trace_sha256 = canonical_sha256([])
        self.sender_role_counts: dict[str, int] = {}
        self.receiver_role_counts: dict[str, int] = {}
        self.reproduction_trace_sha256 = canonical_sha256([])
        self.generation_trace_sha256 = canonical_sha256([])
        self.sender_credit_trace_sha256 = canonical_sha256([])
        self.receiver_credit_trace_sha256 = canonical_sha256([])
        self.reproduction_count = 0
        self.generation_count = 0
        self.policy_transition_rows: list[list[Any]] = []
        self.generation_audit_rows: list[list[Any]] = []
        self.interaction_batch_rows: list[list[Any]] = []
        self.propagation_audit_rows: list[list[Any]] = []
        self.cohort_turnovers: list[dict[str, Any]] = []
        self.storyworld_events: list[dict[str, Any]] = []
        self.cohort_host_ids: dict[int, set[str]] = {
            cohort: set() for cohort in range(self.config["cohorts"])
        }

        self.archive_records: list[dict[str, Any]] = []
        self.archive_peak = 0
        self.archive_deposits = 0
        self.archive_wakes = 0
        self.abstract_signal_deliveries = 0
        self.delayed_task_correct = 0
        self.delayed_sender_reward_suppressions = 0
        self.abstract_signal_delivery_trace_sha256 = canonical_sha256([])
        self.archive_saturation = 0
        self.mutation_count = 0
        self.total_ecological_credit = 0.0
        self.current_sender_credits: dict[str, float] = {}
        self.current_receiver_credits: dict[str, float] = {}
        self.pending_delayed_signals: dict[str, list[dict[str, Any]]] = {}
        self.propagation_edge_counts: dict[str, int] = {}

        self.pressure_state: dict[str, int] = {}
        self._initialize_pressure()
        self._initialize_population()
        self.initial_accuracy = self._initial_compatibility_accuracy()

    @property
    def archive_enabled(self) -> bool:
        return bool(
            self.config["archive"]["enabled"]
            and self.condition["archive_enabled"]
        )

    def _append_policy_lineage(
        self,
        *,
        role: str,
        policy_lineage_id: str,
        parent_policy_lineage_ids: Sequence[str],
        cohort_id: int,
        generation: int,
        origin_kind: str,
        allele_values: Sequence[str],
    ) -> dict[str, Any]:
        row = {
            "policy_lineage_id": policy_lineage_id,
            "parent_policy_lineage_ids": list(parent_policy_lineage_ids),
            "cohort_id": cohort_id,
            "generation": generation,
            "origin_kind": origin_kind,
            "allele_values": list(allele_values),
            "alleles_hash": canonical_sha256(list(allele_values)),
        }
        receipt_prefix = "SPA" if role == "sender" else "RPA"
        row["ancestry_receipt_id"] = (
            f"{receipt_prefix}:{policy_lineage_id}"
        )
        target = (
            self.sender_policy_ancestry
            if role == "sender"
            else self.receiver_policy_ancestry
        )
        target.append(row)
        return row

    def _new_policy_lineage_id(self, role: str) -> str:
        if role == "sender":
            lineage_id = f"SP-{self.next_sender_policy_id}"
            self.next_sender_policy_id += 1
        else:
            lineage_id = f"RP-{self.next_receiver_policy_id}"
            self.next_receiver_policy_id += 1
        return lineage_id

    def _initialize_pressure(self) -> None:
        machine_key = _key(
            "habitat.pressure",
            "training",
            0,
            -1,
            "pressure.init",
            ("habitat:all",),
            "machine-order",
        )
        context_key = _key(
            "habitat.pressure",
            "training",
            0,
            -1,
            "pressure.init",
            ("context:all",),
            "context-order",
        )
        machine_order, _ = _draw_permutation(
            self.rng, machine_key, len(MACHINE_IDS)
        )
        context_order, _ = _draw_permutation(
            self.rng, context_key, len(CONTEXT_IDS)
        )
        for position, machine_index in enumerate(machine_order):
            self.pressure_state[MACHINE_IDS[machine_index]] = context_order[
                position % len(context_order)
            ]
        self.initial_pressure_counts = {
            context: sum(
                index == context_index
                for index in self.pressure_state.values()
            )
            for context_index, context in enumerate(CONTEXT_IDS)
        }

    def _initialize_population(self) -> None:
        for index in range(self.config["population_size"]):
            agent_id = f"A-{index}"
            host_lineage_id = f"H-{index}"
            sender_lineage_id = self._new_policy_lineage_id("sender")
            receiver_lineage_id = self._new_policy_lineage_id("receiver")
            sender_map: list[int] = []
            receiver_map: list[str] = []
            sender_initialization_receipts: list[str] = []
            receiver_initialization_receipts: list[str] = []
            for context_index in range(len(CONTEXT_IDS)):
                sender_key = _key(
                    "initial.sender",
                    "training",
                    0,
                    0,
                    "genome.init",
                    (f"agent:{agent_id}", f"context:C{context_index}"),
                    "categorical-entry",
                )
                value, receipt_id = _draw_integer(
                    self.rng, sender_key, len(SIGNAL_IDS)
                )
                sender_map.append(value)
                sender_initialization_receipts.append(receipt_id)
            for signal_index in range(len(SIGNAL_IDS)):
                receiver_key = _key(
                    "initial.receiver",
                    "training",
                    0,
                    0,
                    "genome.init",
                    (f"agent:{agent_id}", f"signal:S{signal_index}"),
                    "categorical-entry",
                )
                value, receipt_id = _draw_integer(
                    self.rng, receiver_key, len(SKILL_IDS)
                )
                receiver_map.append(SKILL_IDS[value])
                receiver_initialization_receipts.append(receipt_id)
            self.host_ancestry.append(
                {
                    "id": host_lineage_id,
                    "parent_ids": [],
                    "cohort": 0,
                    "generation": 0,
                    "skill_modules": list(SKILL_IDS),
                }
            )
            self._append_policy_lineage(
                role="sender",
                policy_lineage_id=sender_lineage_id,
                parent_policy_lineage_ids=[],
                cohort_id=0,
                generation=0,
                origin_kind="initialization",
                allele_values=[_signal_label(value) for value in sender_map],
            )
            self._append_policy_lineage(
                role="receiver",
                policy_lineage_id=receiver_lineage_id,
                parent_policy_lineage_ids=[],
                cohort_id=0,
                generation=0,
                origin_kind="initialization",
                allele_values=receiver_map,
            )
            self.population.append(
                {
                    "agent_id": agent_id,
                    "host_lineage_id": host_lineage_id,
                    "sender_policy_lineage_id": sender_lineage_id,
                    "receiver_policy_lineage_id": receiver_lineage_id,
                    "machine_id": MACHINE_IDS[index % len(MACHINE_IDS)],
                    "sender_map": list(sender_map),
                    "receiver_map": list(receiver_map),
                }
            )
            self.cohort_host_ids[0].add(agent_id)
        self.policy_transition_rows.append(
            [
                0,
                0,
                list(range(self.config["population_size"])),
                list(range(self.config["population_size"])),
                [None for _ in range(self.config["population_size"])],
                [None for _ in range(self.config["population_size"])],
            ]
        )

    def _initial_compatibility_accuracy(self) -> float:
        correct = 0
        total = 0
        for sender in self.population:
            for receiver in self.population:
                for context_index, _ in enumerate(CONTEXT_IDS):
                    signal = sender["sender_map"][context_index]
                    action = receiver["receiver_map"][signal]
                    correct += action == SKILL_IDS[context_index]
                    total += 1
        return round(correct / total, 6)

    def _storyworld_modifiers(
        self, cohort: int, generation: int
    ) -> dict[str, Any]:
        cards = events_at(
            self.config["storyworld"], cohort=cohort, generation=generation
        )
        pressure_delta = {machine_id: 0.0 for machine_id in MACHINE_IDS}
        pair_shift = 1
        archive_multiplier = 1.0
        masked_links: set[tuple[str, str]] = set()
        for card in cards:
            self.storyworld_events.append(deep_copy_json(card))
            effect = card["effect"]
            if card["kind"] == "pressure_shift":
                pressure_delta[effect["machine_id"]] += float(effect["delta"])
            elif card["kind"] == "link_mask" and not effect["active"]:
                masked_links.add(tuple(sorted((effect["left"], effect["right"]))))
            elif card["kind"] == "archive_weather":
                archive_multiplier *= float(effect["delivery_multiplier"])
        return {
            "pressure_delta": pressure_delta,
            "pair_shift": pair_shift,
            "archive_multiplier": archive_multiplier,
            "masked_links": masked_links,
            "card_ids": [card["id"] for card in cards],
        }

    def _receiver_index(self, sender_index: int, opportunity: int, shift: int) -> int:
        size = len(self.population)
        if self.config["topology"] == "paired":
            receiver = sender_index ^ 1
        else:
            receiver = (sender_index + shift + opportunity % 3) % size
        if receiver == sender_index:
            receiver = (receiver + 1) % size
        return receiver

    def _training_generation(
        self, cohort: int, generation: int, modifiers: Mapping[str, Any]
    ) -> dict[str, float]:
        credits = {agent["agent_id"]: 0.0 for agent in self.population}
        sender_credits = {agent["agent_id"]: 0.0 for agent in self.population}
        receiver_credits = {agent["agent_id"]: 0.0 for agent in self.population}
        audit_events: list[list[Any]] = []
        declared_graph = deep_copy_json(self.config["habitat_graph"])
        for left, right in modifiers["masked_links"]:
            if right in declared_graph[left]:
                declared_graph[left].remove(right)
            if left in declared_graph[right]:
                declared_graph[right].remove(left)
        declared_graph_hash = canonical_sha256(declared_graph)
        global_generation = cohort * self.config["generations_per_cohort"] + generation
        for opportunity in range(self.config["opportunities_per_generation"]):
            opportunity_id = f"T:{global_generation}:{opportunity}"
            machine_key = _key(
                "training.task",
                "training",
                cohort,
                generation,
                "opportunity",
                (f"opportunity:{opportunity_id}",),
                "machine",
            )
            machine_index, machine_receipt = _draw_integer(
                self.rng, machine_key, len(MACHINE_IDS)
            )
            machine_id = MACHINE_IDS[machine_index]
            propagate_probability = max(
                0.0,
                min(
                    1.0,
                    self.config["propagation_probability"]
                    + modifiers["pressure_delta"][machine_id],
                ),
            )
            propagate_key = _key(
                "habitat.propagation",
                "training",
                cohort,
                generation,
                "opportunity",
                (f"opportunity:{opportunity_id}", f"machine:{machine_id}"),
                "carry-pressure",
            )
            propagation_draw, propagation_receipt = _draw_bernoulli(
                self.rng, propagate_key, propagate_probability
            )
            eligible_neighbors = [
                neighbor
                for neighbor in self.config["habitat_graph"][machine_id]
                if tuple(sorted((machine_id, neighbor)))
                not in modifiers["masked_links"]
            ]
            source_machine_id: str | None = None
            source_receipts: list[str] = []
            propagation_edge_receipt_id: str | None = None
            if propagation_draw and eligible_neighbors:
                source_key = _key(
                    "habitat.propagation",
                    "training",
                    cohort,
                    generation,
                    "opportunity",
                    (f"opportunity:{opportunity_id}", f"machine:{machine_id}"),
                    "source-neighbor",
                )
                source_index, source_receipt = _draw_integer(
                    self.rng, source_key, len(eligible_neighbors)
                )
                source_machine_id = eligible_neighbors[source_index]
                source_receipts.append(source_receipt)
                propagation_edge_receipt_id = source_receipt
            propagated = source_machine_id is not None
            if source_machine_id is not None:
                edge_id = ":".join(sorted((source_machine_id, machine_id)))
                self.propagation_edge_counts[edge_id] = (
                    self.propagation_edge_counts.get(edge_id, 0) + 1
                )
            new_context_key = _key(
                "training.task",
                "training",
                cohort,
                generation,
                "opportunity",
                (f"opportunity:{opportunity_id}",),
                "fresh-context",
            )
            fresh_context, context_receipt = _draw_integer(
                self.rng, new_context_key, len(CONTEXT_IDS)
            )
            live_context_index = (
                self.pressure_state[source_machine_id]
                if source_machine_id is not None
                else fresh_context
            )
            self.pressure_state[machine_id] = live_context_index
            live_hidden_need = CONTEXT_IDS[live_context_index]

            sender_key = _key(
                "training.pairing",
                "training",
                cohort,
                generation,
                "opportunity",
                (f"opportunity:{opportunity_id}",),
                "sender",
            )
            sender_index, sender_receipt = _draw_integer(
                self.rng, sender_key, len(self.population)
            )
            receiver_index = self._receiver_index(
                sender_index, opportunity, int(modifiers["pair_shift"])
            )
            sender = self.population[sender_index]
            receiver = self.population[receiver_index]
            emitted_index = int(sender["sender_map"][live_context_index])

            noise_key = _key(
                "channel.noise",
                "training",
                cohort,
                generation,
                "opportunity",
                (f"opportunity:{opportunity_id}",),
                "replace",
            )
            noisy, noise_receipt = _draw_bernoulli(
                self.rng, noise_key, self.config["channel_noise_probability"]
            )
            alternate_key = _key(
                "channel.noise",
                "training",
                cohort,
                generation,
                "opportunity",
                (f"opportunity:{opportunity_id}",),
                "alternate",
            )
            alternate, alternate_receipt = _draw_integer(
                self.rng, alternate_key, len(SIGNAL_IDS) - 1
            )
            delivered_index = (
                (emitted_index + 1 + alternate) % len(SIGNAL_IDS)
                if noisy
                else emitted_index
            )
            delayed_record_id: str | None = None
            delayed_task_binding_id: str | None = None
            delayed_signal_observation: dict[str, Any] | None = None
            effective_context_index = live_context_index
            sender_reward_eligible = True
            pending = self.pending_delayed_signals.get(receiver["agent_id"], [])
            if pending:
                delivery = pending.pop(0)
                delayed_record_id = str(delivery["record_id"])
                delivered_index = _signal_index(str(delivery["signal_id"]))
                archive_record = next(
                    row
                    for row in self.archive_records
                    if row["record_id"] == delayed_record_id
                )
                archive_record["abstract_signal"][
                    "delivery_status"
                ] = "delivered"
                archive_record["abstract_signal"][
                    "delivery_opportunity_id"
                ] = opportunity_id
                delayed_signal_observation = deep_copy_json(
                    archive_record["abstract_signal"]
                )
                delayed_task_binding = archive_record[
                    "delayed_task_binding"
                ]
                delayed_task_binding_id = str(
                    delayed_task_binding["binding_id"]
                )
                effective_context_index = CONTEXT_IDS.index(
                    str(
                        delayed_task_binding[
                            "pressure_class_evaluator_only"
                        ]
                    )
                )
                if delayed_task_binding[
                    "required_skill_evaluator_only"
                ] != SKILL_IDS[effective_context_index]:
                    raise AssertionError(
                        "delayed task pressure and skill must remain paired"
                    )
                sender_reward_eligible = False
                self.abstract_signal_delivery_trace_sha256 = _advance_digest(
                    self.abstract_signal_delivery_trace_sha256,
                    {
                        "abstract_signal": delayed_signal_observation,
                        "delayed_task_binding_id": delayed_task_binding_id,
                    },
                )
                self.abstract_signal_deliveries += 1
                self.delayed_sender_reward_suppressions += 1
            hidden_need = CONTEXT_IDS[effective_context_index]
            action = receiver["receiver_map"][delivered_index]
            correct = action == _skill_for_context(hidden_need)
            reward = self.config["task_reward"] if correct else 0.0
            sender_credits[sender["agent_id"]] += (
                (reward if sender_reward_eligible else 0.0)
                - self.config["signal_cost"]
            )
            receiver_credits[receiver["agent_id"]] += reward
            if delayed_record_id is not None:
                self.delayed_task_correct += int(correct)
            delivered_signal_id = _signal_label(delivered_index)
            receiver_policy_input_hash = canonical_sha256(
                {
                    "opportunity_id": opportunity_id,
                    "receiver_id": receiver["agent_id"],
                    "receiver_policy_lineage_id": receiver[
                        "receiver_policy_lineage_id"
                    ],
                    "machine_id": machine_id,
                    "signal_id": delivered_signal_id,
                    "archive_record_id": delayed_record_id,
                }
            )
            audit_events.append(
                [
                    opportunity_id,
                    sender["agent_id"],
                    sender["host_lineage_id"],
                    sender["sender_policy_lineage_id"],
                    receiver["agent_id"],
                    receiver["host_lineage_id"],
                    receiver["receiver_policy_lineage_id"],
                    hidden_need,
                    _skill_for_context(hidden_need),
                    delivered_signal_id,
                    delayed_record_id,
                    machine_id,
                    True,
                    True,
                    True,
                    True,
                    receiver_policy_input_hash,
                    action,
                    source_machine_id,
                    machine_id if propagated else None,
                    propagation_edge_receipt_id,
                    live_hidden_need,
                    _signal_label(emitted_index),
                    sender_reward_eligible,
                ]
            )
            if propagation_edge_receipt_id is not None:
                self.propagation_audit_rows.append(
                    [
                        propagation_edge_receipt_id,
                        cohort,
                        generation,
                        opportunity_id,
                        source_machine_id,
                        machine_id,
                        declared_graph_hash,
                    ]
                )

            receipt = {
                "opportunity_id": opportunity_id,
                "trial_id": opportunity_id,
                "phase": "training",
                "branch": "training",
                "cohort": cohort,
                "generation": generation,
                "global_generation": global_generation,
                "machine_id": machine_id,
                "hidden_need": hidden_need,
                "live_hidden_need": live_hidden_need,
                "delayed_task_binding_id": delayed_task_binding_id,
                "sender_id": sender["agent_id"],
                "receiver_id": receiver["agent_id"],
                "sender_observation": {
                    "opportunity_id": opportunity_id,
                    "machine_id": machine_id,
                    "need": live_hidden_need,
                },
                "receiver_observation": {
                    "opportunity_id": opportunity_id,
                    "machine_id": machine_id,
                    "channel": self.condition["channel"],
                    "carrier": "abstract_signal",
                    "signal": _signal_label(delivered_index),
                    **(
                        {"abstract_signal": delayed_signal_observation}
                        if delayed_signal_observation is not None
                        else {}
                    ),
                },
                "emitted_signal": _signal_label(emitted_index),
                "delivered_signal": _signal_label(delivered_index),
                "receiver_action": action,
                "correct_outcome": correct,
                "task_reward": reward,
                "sender_task_reward": (
                    reward if sender_reward_eligible else 0.0
                ),
                "receiver_task_reward": reward,
                "sender_reward_eligible": sender_reward_eligible,
                "signal_cost": self.config["signal_cost"],
                "channel": self.condition["channel"],
                "pressure_propagated": propagated,
                "pressure_source_machine_id": source_machine_id,
                "rng_receipt_ids": [
                    machine_receipt,
                    propagation_receipt,
                    *source_receipts,
                    context_receipt,
                    sender_receipt,
                    noise_receipt,
                    alternate_receipt,
                ],
            }
            self.training_exposure["eligible"] += 1
            self.training_exposure["emitted"] += 1
            self.training_exposure["delivered"] += 1
            self.training_exposure["actions_executed"] += 1
            self.training_exposure["correct"] += int(correct)
            self.training_exposure["need_counts"][hidden_need] += 1
            self.sender_role_counts[sender["agent_id"]] = (
                self.sender_role_counts.get(sender["agent_id"], 0) + 1
            )
            self.receiver_role_counts[receiver["agent_id"]] = (
                self.receiver_role_counts.get(receiver["agent_id"], 0) + 1
            )
            self.training_trace_sha256 = _advance_digest(
                self.training_trace_sha256, receipt
            )

        credits = {
            agent_id: sender_credits[agent_id] + receiver_credits[agent_id]
            for agent_id in credits
        }
        self.current_sender_credits = sender_credits
        self.current_receiver_credits = receiver_credits
        self.sender_credit_trace_sha256 = _advance_digest(
            self.sender_credit_trace_sha256,
            {
                "cohort": cohort,
                "generation": generation,
                "credits": dict(sorted(sender_credits.items())),
            },
        )
        self.receiver_credit_trace_sha256 = _advance_digest(
            self.receiver_credit_trace_sha256,
            {
                "cohort": cohort,
                "generation": generation,
                "credits": dict(sorted(receiver_credits.items())),
            },
        )
        self.interaction_batch_rows.append(
            [cohort, generation, audit_events]
        )
        self.total_ecological_credit += sum(credits.values())
        return credits

    def _fitness_weights(
        self, population: Sequence[Mapping[str, Any]], credits: Mapping[str, float]
    ) -> list[float]:
        if self.condition["selection_mode"] == "uniform":
            return [1.0 for _ in population]
        values = [float(credits[agent["agent_id"]]) for agent in population]
        floor = min(values)
        return [value - floor + 1e-9 for value in values]

    def _mutate_maps(
        self,
        sender_map: list[int],
        receiver_map: list[str],
        cohort: int,
        generation: int,
        child_tag: str,
    ) -> tuple[
        list[int],
        list[str],
        list[str],
        list[str],
        list[Any] | None,
        list[Any] | None,
    ]:
        sender_receipt_ids: list[str] = []
        receiver_receipt_ids: list[str] = []
        sender_mutation: list[Any] | None = None
        receiver_mutation: list[Any] | None = None
        rate = self.config["mutation_rate"] if self.condition["mutation_enabled"] else 0.0
        sender_key = _key(
            "evolution.mutation.sender",
            "training",
            cohort,
            generation,
            "mutation",
            (f"child:{child_tag}",),
            "activate",
        )
        sender_mutates, sender_activation = _draw_bernoulli(self.rng, sender_key, rate)
        sender_receipt_ids.append(sender_activation)
        if sender_mutates:
            position_key = _key(
                "evolution.mutation.sender",
                "training",
                cohort,
                generation,
                "mutation",
                (f"child:{child_tag}",),
                "position",
            )
            position, position_receipt = _draw_integer(
                self.rng, position_key, len(sender_map)
            )
            alternate_key = _key(
                "evolution.mutation.sender",
                "training",
                cohort,
                generation,
                "mutation",
                (f"child:{child_tag}",),
                "alternate",
            )
            alternate, alternate_receipt = _draw_integer(
                self.rng, alternate_key, len(SIGNAL_IDS) - 1
            )
            sender_map[position] = (
                sender_map[position] + 1 + alternate
            ) % len(SIGNAL_IDS)
            sender_mutation = [position, _signal_label(sender_map[position])]
            sender_receipt_ids.extend([position_receipt, alternate_receipt])
            self.mutation_count += 1

        receiver_key = _key(
            "evolution.mutation.receiver",
            "training",
            cohort,
            generation,
            "mutation",
            (f"child:{child_tag}",),
            "activate",
        )
        receiver_mutates, receiver_activation = _draw_bernoulli(
            self.rng, receiver_key, rate
        )
        receiver_receipt_ids.append(receiver_activation)
        if receiver_mutates:
            position_key = _key(
                "evolution.mutation.receiver",
                "training",
                cohort,
                generation,
                "mutation",
                (f"child:{child_tag}",),
                "position",
            )
            position, position_receipt = _draw_integer(
                self.rng, position_key, len(receiver_map)
            )
            alternate_key = _key(
                "evolution.mutation.receiver",
                "training",
                cohort,
                generation,
                "mutation",
                (f"child:{child_tag}",),
                "alternate",
            )
            alternate, alternate_receipt = _draw_integer(
                self.rng, alternate_key, len(SKILL_IDS) - 1
            )
            prior_index = SKILL_IDS.index(receiver_map[position])
            receiver_map[position] = SKILL_IDS[
                (prior_index + 1 + alternate) % len(SKILL_IDS)
            ]
            receiver_mutation = [position, receiver_map[position]]
            receiver_receipt_ids.extend([position_receipt, alternate_receipt])
            self.mutation_count += 1
        return (
            sender_map,
            receiver_map,
            sender_receipt_ids,
            receiver_receipt_ids,
            sender_mutation,
            receiver_mutation,
        )

    def _horizontal_transfer(
        self, cohort: int, generation: int, credits: Mapping[str, float]
    ) -> None:
        if not self.condition["horizontal_transfer_enabled"]:
            return
        rate = self.config["horizontal_transfer_rate"]
        if rate <= 0.0:
            return
        remaining = MAX_HORIZONTAL_TRANSFERS - len(self.horizontal_transfers)
        if remaining <= 0:
            return
        attempts = min(remaining, max(1, int(rate * len(self.population))))
        for attempt in range(attempts):
            transfer_id = f"X-C{cohort}-G{generation}-{attempt:03d}"
            block_key = _key(
                "evolution.horizontal",
                "training",
                cohort,
                generation,
                "horizontal-transfer",
                (f"transfer:{transfer_id}",),
                "policy-block",
            )
            block_index, block_receipt = _draw_integer(self.rng, block_key, 2)
            policy_block = "sender" if block_index == 0 else "receiver"
            donor_credits = (
                self.current_sender_credits
                if policy_block == "sender"
                else self.current_receiver_credits
            )
            donor_weights = self._fitness_weights(
                self.population, donor_credits
            )
            donor_key = _key(
                "evolution.horizontal",
                "training",
                cohort,
                generation,
                "horizontal-transfer",
                (f"transfer:{transfer_id}",),
                "donor",
            )
            donor_index, donor_receipt = _draw_weighted(
                self.rng, donor_key, donor_weights
            )
            target_key = _key(
                "evolution.horizontal",
                "training",
                cohort,
                generation,
                "horizontal-transfer",
                (f"transfer:{transfer_id}",),
                "recipient-offset",
            )
            target_offset, target_receipt = _draw_integer(
                self.rng, target_key, len(self.population) - 1
            )
            target_index = (donor_index + 1 + target_offset) % len(self.population)
            donor = self.population[donor_index]
            target = self.population[target_index]
            allele_key = _key(
                "evolution.horizontal",
                "training",
                cohort,
                generation,
                "horizontal-transfer",
                (f"transfer:{transfer_id}",),
                "allele-index",
            )
            allele_index, allele_receipt = _draw_integer(
                self.rng, allele_key, len(SIGNAL_IDS)
            )
            if policy_block == "sender":
                recipient_parent_policy_lineage_id = target[
                    "sender_policy_lineage_id"
                ]
                donor_parent_policy_lineage_id = donor[
                    "sender_policy_lineage_id"
                ]
                prior_allele = _signal_label(target["sender_map"][allele_index])
                new_allele = _signal_label(donor["sender_map"][allele_index])
                if (
                    recipient_parent_policy_lineage_id
                    == donor_parent_policy_lineage_id
                ):
                    continue
                target["sender_map"][allele_index] = donor["sender_map"][allele_index]
                child_policy_lineage_id = self._new_policy_lineage_id(
                    "sender"
                )
                target[
                    "sender_policy_lineage_id"
                ] = child_policy_lineage_id
                allele_values = [
                    _signal_label(value) for value in target["sender_map"]
                ]
            else:
                recipient_parent_policy_lineage_id = target[
                    "receiver_policy_lineage_id"
                ]
                donor_parent_policy_lineage_id = donor[
                    "receiver_policy_lineage_id"
                ]
                prior_allele = str(target["receiver_map"][allele_index])
                new_allele = str(donor["receiver_map"][allele_index])
                if (
                    recipient_parent_policy_lineage_id
                    == donor_parent_policy_lineage_id
                ):
                    continue
                target["receiver_map"][allele_index] = donor["receiver_map"][
                    allele_index
                ]
                child_policy_lineage_id = self._new_policy_lineage_id(
                    "receiver"
                )
                target[
                    "receiver_policy_lineage_id"
                ] = child_policy_lineage_id
                allele_values = list(target["receiver_map"])
            self._append_policy_lineage(
                role=policy_block,
                policy_lineage_id=child_policy_lineage_id,
                parent_policy_lineage_ids=[
                    recipient_parent_policy_lineage_id,
                    donor_parent_policy_lineage_id,
                ],
                cohort_id=cohort,
                generation=generation,
                origin_kind="horizontal_transfer",
                allele_values=allele_values,
            )
            self.horizontal_transfers.append(
                {
                    "transfer_id": transfer_id,
                    "transfer_type": "abstract_convention_allele",
                    "cohort": cohort,
                    "generation": generation,
                    "donor_host_id": donor["agent_id"],
                    "recipient_host_id": target["agent_id"],
                    "recipient_parent_policy_lineage_id": (
                        recipient_parent_policy_lineage_id
                    ),
                    "donor_parent_policy_lineage_id": (
                        donor_parent_policy_lineage_id
                    ),
                    "child_policy_lineage_id": child_policy_lineage_id,
                    "policy_block": policy_block,
                    "allele_index": allele_index,
                    "prior_allele": prior_allele,
                    "new_allele": new_allele,
                    "rng_receipt_ids": [
                        donor_receipt,
                        target_receipt,
                        block_receipt,
                        allele_receipt,
                    ],
                }
            )

    def _reproduce(
        self,
        population: Sequence[Mapping[str, Any]],
        credits: Mapping[str, float],
        source_cohort: int,
        source_generation: int,
        target_cohort: int,
        target_generation: int,
    ) -> list[dict[str, Any]]:
        host_weights = self._fitness_weights(population, credits)
        sender_weights = self._fitness_weights(
            population, self.current_sender_credits
        )
        receiver_weights = self._fitness_weights(
            population, self.current_receiver_credits
        )
        next_population: list[dict[str, Any]] = []
        sender_parent_slots: list[int] = []
        receiver_parent_slots: list[int] = []
        sender_mutations: list[list[Any] | None] = []
        receiver_mutations: list[list[Any] | None] = []
        for slot in range(self.config["population_size"]):
            child_tag = f"C{target_cohort}-G{target_generation}-{slot:03d}"
            cohort_boundary = target_cohort != source_cohort
            sender_key = _key(
                "evolution.selection.sender",
                "training",
                source_cohort,
                source_generation,
                "reproduction",
                (f"child:{child_tag}",),
                "parent",
            )
            receiver_key = _key(
                "evolution.selection.receiver",
                "training",
                source_cohort,
                source_generation,
                "reproduction",
                (f"child:{child_tag}",),
                "parent",
            )
            sender_parent_index, sender_receipt = _draw_weighted(
                self.rng, sender_key, sender_weights
            )
            receiver_parent_index, receiver_receipt = _draw_weighted(
                self.rng, receiver_key, receiver_weights
            )
            sender_parent = population[sender_parent_index]
            receiver_parent = population[receiver_parent_index]
            (
                sender_map,
                receiver_map,
                sender_mutation_receipts,
                receiver_mutation_receipts,
                sender_mutation,
                receiver_mutation,
            ) = self._mutate_maps(
                list(sender_parent["sender_map"]),
                list(receiver_parent["receiver_map"]),
                target_cohort,
                target_generation,
                child_tag,
            )
            host_receipts: list[str] = []
            if cohort_boundary:
                host_key = _key(
                    "evolution.selection.host",
                    "training",
                    source_cohort,
                    source_generation,
                    "reproduction",
                    (f"child:{child_tag}",),
                    "parent",
                )
                host_parent_index, host_receipt = _draw_weighted(
                    self.rng, host_key, host_weights
                )
                host_parent = population[host_parent_index]
                host_number = (
                    target_cohort * self.config["population_size"] + slot
                )
                agent_id = f"A-{host_number}"
                host_lineage_id = f"H-{host_number}"
                host_receipts.append(host_receipt)
                self.host_ancestry.append(
                    {
                        "id": host_lineage_id,
                        "parent_ids": [host_parent["host_lineage_id"]],
                        "cohort": target_cohort,
                        "generation": target_generation,
                        "skill_modules": list(SKILL_IDS),
                    }
                )
            else:
                retained_host = population[slot]
                host_parent = retained_host
                agent_id = str(retained_host["agent_id"])
                host_lineage_id = str(retained_host["host_lineage_id"])
            sender_lineage_id = sender_parent["sender_policy_lineage_id"]
            if sender_mutation is not None:
                sender_lineage_id = self._new_policy_lineage_id("sender")
                self._append_policy_lineage(
                    role="sender",
                    policy_lineage_id=sender_lineage_id,
                    parent_policy_lineage_ids=[
                        sender_parent["sender_policy_lineage_id"]
                    ],
                    cohort_id=target_cohort,
                    generation=target_generation,
                    origin_kind="mutation",
                    allele_values=[
                        _signal_label(value) for value in sender_map
                    ],
                )
            receiver_lineage_id = receiver_parent[
                "receiver_policy_lineage_id"
            ]
            if receiver_mutation is not None:
                receiver_lineage_id = self._new_policy_lineage_id("receiver")
                self._append_policy_lineage(
                    role="receiver",
                    policy_lineage_id=receiver_lineage_id,
                    parent_policy_lineage_ids=[
                        receiver_parent["receiver_policy_lineage_id"]
                    ],
                    cohort_id=target_cohort,
                    generation=target_generation,
                    origin_kind="mutation",
                    allele_values=receiver_map,
                )
            child = {
                "agent_id": agent_id,
                "host_lineage_id": host_lineage_id,
                "sender_policy_lineage_id": sender_lineage_id,
                "receiver_policy_lineage_id": receiver_lineage_id,
                "machine_id": MACHINE_IDS[slot % len(MACHINE_IDS)],
                "sender_map": sender_map,
                "receiver_map": receiver_map,
            }
            next_population.append(child)
            sender_parent_slots.append(sender_parent_index)
            receiver_parent_slots.append(receiver_parent_index)
            sender_mutations.append(sender_mutation)
            receiver_mutations.append(receiver_mutation)
            self.cohort_host_ids[target_cohort].add(agent_id)
            reproduction_receipt = {
                "child_host_id": agent_id,
                "child_host_lineage_id": host_lineage_id,
                "child_sender_policy_lineage_id": sender_lineage_id,
                "child_receiver_policy_lineage_id": receiver_lineage_id,
                "host_parent_id": host_parent["agent_id"],
                "host_transition": "new_cohort" if cohort_boundary else "retained",
                "sender_parent_id": sender_parent["agent_id"],
                "receiver_parent_id": receiver_parent["agent_id"],
                "source_cohort": source_cohort,
                "source_generation": source_generation,
                "target_cohort": target_cohort,
                "target_generation": target_generation,
                "fitness_metric": "ecological_task_reward",
                "host_parent_fitness": float(credits[host_parent["agent_id"]]),
                "sender_parent_fitness": float(
                    self.current_sender_credits[sender_parent["agent_id"]]
                ),
                "receiver_parent_fitness": float(
                    self.current_receiver_credits[receiver_parent["agent_id"]]
                ),
                "rng_receipt_ids": [
                    *host_receipts,
                    sender_receipt,
                    receiver_receipt,
                    *sender_mutation_receipts,
                    *receiver_mutation_receipts,
                ],
            }
            self.reproduction_trace_sha256 = _advance_digest(
                self.reproduction_trace_sha256, reproduction_receipt
            )
            self.reproduction_count += 1
        self.policy_transition_rows.append(
            [
                target_cohort,
                target_generation,
                sender_parent_slots,
                receiver_parent_slots,
                sender_mutations,
                receiver_mutations,
            ]
        )
        return next_population

    def _need_to_signal(self, population: Sequence[Mapping[str, Any]]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for context_index, context in enumerate(CONTEXT_IDS):
            counts = [0 for _ in SIGNAL_IDS]
            for agent in population:
                counts[int(agent["sender_map"][context_index])] += 1
            winner = max(range(len(counts)), key=lambda index: (counts[index], -index))
            mapping[context] = _signal_label(winner)
        return mapping

    def _record_generation_audit(self, cohort: int, generation: int) -> None:
        ordered_population = sorted(
            self.population, key=lambda agent: agent["agent_id"]
        )
        roster = [
            {
                "host_id": agent["agent_id"],
                "host_lineage_id": agent["host_lineage_id"],
                "sender_policy_lineage_id": agent[
                    "sender_policy_lineage_id"
                ],
                "receiver_policy_lineage_id": agent[
                    "receiver_policy_lineage_id"
                ],
                "machine_id": agent["machine_id"],
            }
            for agent in ordered_population
        ]
        self.generation_audit_rows.append(
            [
                cohort,
                generation,
                len(roster),
                canonical_sha256(roster),
                f"SPC:{cohort}:{generation}",
                f"RPC:{cohort}:{generation}",
                [
                    round(self.current_sender_credits[agent["agent_id"]], 6)
                    for agent in ordered_population
                ],
                [
                    round(self.current_receiver_credits[agent["agent_id"]], 6)
                    for agent in ordered_population
                ],
            ]
        )

    def _deposit_archive(
        self,
        cohort: int,
        generation: int,
        credits: Mapping[str, float],
        archive_multiplier: float,
    ) -> None:
        if not self.archive_enabled:
            return
        configured = self.config["archive"]["deposit_count"]
        count = int(configured * archive_multiplier)
        if configured > 0 and archive_multiplier > 0.0:
            count = max(1, count)
        sender_weights = self._fitness_weights(
            self.population, self.current_sender_credits
        )
        receiver_weights = self._fitness_weights(
            self.population, self.current_receiver_credits
        )
        for deposit_index in range(count):
            if len(self.archive_records) >= self.config["archive"]["capacity"]:
                self.archive_saturation += 1
                break
            record_id = f"D-C{cohort}-{len(self.archive_records):04d}"
            sender_key = _key(
                "archive.propagule.sender",
                "training",
                cohort,
                generation,
                "archive-deposit",
                (f"record:{record_id}", f"deposit:{deposit_index}"),
                "source",
            )
            receiver_key = _key(
                "archive.propagule.receiver",
                "training",
                cohort,
                generation,
                "archive-deposit",
                (f"record:{record_id}", f"deposit:{deposit_index}"),
                "source",
            )
            sender_index, sender_receipt = _draw_weighted(
                self.rng, sender_key, sender_weights
            )
            receiver_index, receiver_receipt = _draw_weighted(
                self.rng, receiver_key, receiver_weights
            )
            sender_source = self.population[sender_index]
            receiver_source = self.population[receiver_index]
            delayed_context_index = (
                len(self.archive_records) + self.seed
            ) % len(CONTEXT_IDS)
            delayed_pressure_class = CONTEXT_IDS[delayed_context_index]
            delayed_required_skill = SKILL_IDS[delayed_context_index]
            signal_index = int(
                sender_source["sender_map"][delayed_context_index]
            )
            sender_allele_values = [
                _signal_label(value) for value in sender_source["sender_map"]
            ]
            receiver_allele_values = list(receiver_source["receiver_map"])
            sender_alleles_hash = canonical_sha256(sender_allele_values)
            receiver_alleles_hash = canonical_sha256(receiver_allele_values)
            propagule_payload_projection = {
                "propagule_sender_source_policy_lineage_id": sender_source[
                    "sender_policy_lineage_id"
                ],
                "propagule_receiver_source_policy_lineage_id": receiver_source[
                    "receiver_policy_lineage_id"
                ],
                "propagule_sender_policy_allele_values": sender_allele_values,
                "propagule_receiver_policy_allele_values": receiver_allele_values,
            }
            record = {
                "record_id": record_id,
                "origin_cohort": cohort,
                "wake_cohort": cohort + self.config["archive"]["delay_cohorts"],
                "status": "dormant",
                "overt": {
                    "record_id": record_id,
                    "origin_cohort": cohort,
                    "generation": generation,
                    "delivery_status": "dormant",
                },
                "abstract_signal": {
                    "record_id": record_id,
                    "signal_id": _signal_label(signal_index),
                    "scheduled_wake_cohort": (
                        cohort + self.config["archive"]["delay_cohorts"]
                    ),
                    "delivery_status": "dormant",
                    "visible_as_observation": True,
                    "may_affect_action": True,
                    "may_affect_policy": False,
                    "delivery_host_id": None,
                    "delivery_opportunity_id": None,
                },
                "delayed_task_binding": {
                    "binding_id": f"DT-{record_id}",
                    "pressure_class_evaluator_only": delayed_pressure_class,
                    "required_skill_evaluator_only": delayed_required_skill,
                    "visible_to_agents": False,
                    "may_affect_task_truth": True,
                    "may_affect_reward": True,
                    "may_affect_policy_input": False,
                },
                "convention_propagule": {
                    "propagule_id": f"P-{record_id}",
                    **propagule_payload_projection,
                    "source_rng_receipt_ids": [
                        sender_receipt,
                        receiver_receipt,
                    ],
                    "propagule_sender_policy_alleles_hash": sender_alleles_hash,
                    "propagule_receiver_policy_alleles_hash": receiver_alleles_hash,
                    "propagule_payload_hash": canonical_sha256(
                        propagule_payload_projection
                    ),
                    "may_affect_policy": True,
                    "visible_as_observation": False,
                    "activation_host_id": None,
                    "activation_sender_policy_lineage_id": None,
                    "activation_receiver_policy_lineage_id": None,
                    "replaced_sender_policy_lineage_id": None,
                    "replaced_receiver_policy_lineage_id": None,
                },
                "latent_evaluator_metadata": {
                    "provenance_id": f"L-{record_id}",
                    "visible_to_agents": False,
                    "may_affect_action": False,
                    "may_affect_policy": False,
                },
            }
            self.archive_records.append(record)
            self.archive_deposits += 1
        self.archive_peak = max(self.archive_peak, len(self.archive_records))

    def _wake_archive(self, cohort: int) -> None:
        eligible = [
            record
            for record in self.archive_records
            if record["status"] == "dormant" and record["wake_cohort"] == cohort
        ]
        for target_index, record in enumerate(
            eligible[: len(self.population)]
        ):
            propagule = record["convention_propagule"]
            sender_source_id = propagule[
                "propagule_sender_source_policy_lineage_id"
            ]
            receiver_source_id = propagule[
                "propagule_receiver_source_policy_lineage_id"
            ]
            agent = self.population[target_index]
            replaced_sender_id = agent[
                "sender_policy_lineage_id"
            ]
            replaced_receiver_id = agent[
                "receiver_policy_lineage_id"
            ]
            propagule[
                "replaced_sender_policy_lineage_id"
            ] = replaced_sender_id
            propagule[
                "replaced_receiver_policy_lineage_id"
            ] = replaced_receiver_id
            sender_map = [
                _signal_index(value)
                for value in propagule[
                    "propagule_sender_policy_allele_values"
                ]
            ]
            receiver_map = list(
                propagule["propagule_receiver_policy_allele_values"]
            )
            if replaced_sender_id == sender_source_id:
                if agent["sender_map"] != sender_map:
                    raise AssertionError(
                        "equal sender lineage ids must bind equal alleles"
                    )
                child_sender_lineage_id = replaced_sender_id
            else:
                child_sender_lineage_id = self._new_policy_lineage_id(
                    "sender"
                )
                agent["sender_map"] = sender_map
                agent[
                    "sender_policy_lineage_id"
                ] = child_sender_lineage_id
                self._append_policy_lineage(
                    role="sender",
                    policy_lineage_id=child_sender_lineage_id,
                    parent_policy_lineage_ids=[sender_source_id],
                    cohort_id=cohort,
                    generation=0,
                    origin_kind="propagule",
                    allele_values=propagule[
                        "propagule_sender_policy_allele_values"
                    ],
                )
            if replaced_receiver_id == receiver_source_id:
                if agent["receiver_map"] != receiver_map:
                    raise AssertionError(
                        "equal receiver lineage ids must bind equal alleles"
                    )
                child_receiver_lineage_id = replaced_receiver_id
            else:
                child_receiver_lineage_id = self._new_policy_lineage_id(
                    "receiver"
                )
                agent["receiver_map"] = receiver_map
                agent[
                    "receiver_policy_lineage_id"
                ] = child_receiver_lineage_id
                self._append_policy_lineage(
                    role="receiver",
                    policy_lineage_id=child_receiver_lineage_id,
                    parent_policy_lineage_ids=[receiver_source_id],
                    cohort_id=cohort,
                    generation=0,
                    origin_kind="propagule",
                    allele_values=propagule[
                        "propagule_receiver_policy_allele_values"
                    ],
                )
            record["status"] = "woken"
            propagule["activation_host_id"] = agent["agent_id"]
            propagule[
                "activation_sender_policy_lineage_id"
            ] = child_sender_lineage_id
            propagule[
                "activation_receiver_policy_lineage_id"
            ] = child_receiver_lineage_id
            record["overt"]["delivery_status"] = "woken"
            abstract_signal = record["abstract_signal"]
            abstract_signal["delivery_status"] = "queued"
            abstract_signal["delivery_host_id"] = agent["agent_id"]
            self.pending_delayed_signals.setdefault(agent["agent_id"], []).append(
                {
                    "record_id": record["record_id"],
                    "signal_id": abstract_signal["signal_id"],
                }
            )
            self.archive_wakes += 1

    def train(self) -> None:
        last_credits: dict[str, float] = {
            agent["agent_id"]: 0.0 for agent in self.population
        }
        last_archive_multiplier = 1.0
        for cohort in range(self.config["cohorts"]):
            for generation in range(self.config["generations_per_cohort"]):
                modifiers = self._storyworld_modifiers(cohort, generation)
                last_archive_multiplier = float(modifiers["archive_multiplier"])
                last_credits = self._training_generation(
                    cohort, generation, modifiers
                )
                self._record_generation_audit(cohort, generation)
                self._horizontal_transfer(cohort, generation, last_credits)
                generation_receipt = {
                    "cohort": cohort,
                    "generation": generation,
                    "population_size": len(self.population),
                    "opportunities": self.config["opportunities_per_generation"],
                    "ecological_task_reward": round(sum(last_credits.values()), 6),
                    "storyworld_card_ids": list(modifiers["card_ids"]),
                }
                self.generation_trace_sha256 = _advance_digest(
                    self.generation_trace_sha256, generation_receipt
                )
                self.generation_count += 1
                if generation < self.config["generations_per_cohort"] - 1:
                    self.population = self._reproduce(
                        self.population,
                        last_credits,
                        cohort,
                        generation,
                        cohort,
                        generation + 1,
                    )

            final_generation = self.config["generations_per_cohort"] - 1
            outgoing_mapping = self._need_to_signal(self.population)
            self._deposit_archive(
                cohort,
                final_generation,
                last_credits,
                last_archive_multiplier,
            )
            if cohort < self.config["cohorts"] - 1:
                retired_ids = sorted(agent["agent_id"] for agent in self.population)
                for retired_id in retired_ids:
                    for delivery in self.pending_delayed_signals.pop(
                        retired_id, []
                    ):
                        archive_record = next(
                            row
                            for row in self.archive_records
                            if row["record_id"] == delivery["record_id"]
                        )
                        if (
                            archive_record["abstract_signal"][
                                "delivery_status"
                            ]
                            == "queued"
                        ):
                            archive_record["abstract_signal"][
                                "delivery_status"
                            ] = "expired"
                next_population = self._reproduce(
                    self.population,
                    last_credits,
                    cohort,
                    final_generation,
                    cohort + 1,
                    0,
                )
                activated_ids = sorted(
                    agent["agent_id"] for agent in next_population
                )
                self.cohort_turnovers.append(
                    {
                        "from_cohort": cohort,
                        "to_cohort": cohort + 1,
                        "retired_host_ids": retired_ids,
                        "activated_host_ids": activated_ids,
                        "need_to_signal": outgoing_mapping,
                    }
                )
                self.population = next_population
                self._wake_archive(cohort + 1)

    def _checkpoint_projection(self) -> dict[str, Any]:
        exposure = self._signaling_exposure()
        habitat_edges = _graph_edges(self.config["habitat_graph"])
        ood_edges = _graph_edges(self.config["ood_habitat_graph"])
        removed_edge = next(edge for edge in habitat_edges if edge not in ood_edges)
        added_edge = next(edge for edge in ood_edges if edge not in habitat_edges)
        ood_transform = {
            "habitat_edges": habitat_edges,
            "ood_edges": ood_edges,
            "removed_edge": removed_edge,
            "added_edge": added_edge,
            "connected": True,
        }
        ood_transform["transform_sha256"] = canonical_sha256(ood_transform)
        return {
            "population": sorted(
                [
                    {
                        "agent_id": agent["agent_id"],
                        "host_lineage_id": agent["host_lineage_id"],
                        "sender_policy_lineage_id": agent[
                            "sender_policy_lineage_id"
                        ],
                        "receiver_policy_lineage_id": agent[
                            "receiver_policy_lineage_id"
                        ],
                        "machine_id": agent["machine_id"],
                        "sender_map": [
                            _signal_label(value) for value in agent["sender_map"]
                        ],
                        "receiver_map": list(agent["receiver_map"]),
                    }
                    for agent in self.population
                ],
                key=lambda row: row["agent_id"],
            ),
            "pressure_state": {
                machine_id: CONTEXT_IDS[index]
                for machine_id, index in sorted(self.pressure_state.items())
            },
            "configuration_sha256": canonical_sha256(self.config),
            "condition_sha256": canonical_sha256(self.condition),
            "initialization": {
                "sender_receiver_independent": True,
                "analytic_chance_accuracy": 0.25,
                "initial_cross_pair_accuracy": self.initial_accuracy,
                "initial_pressure_counts": self.initial_pressure_counts,
                "designer_codebook": False,
            },
            "training": {
                "exposure": exposure,
                "trace_sha256": self.training_trace_sha256,
                "rng_sha256": self.rng.receipts_sha256(),
                "reproduction_count": self.reproduction_count,
                "reproduction_trace_sha256": self.reproduction_trace_sha256,
                "generation_count": self.generation_count,
                "generation_trace_sha256": self.generation_trace_sha256,
                "mutation_count": self.mutation_count,
                "abstract_signal_deliveries": self.abstract_signal_deliveries,
                "delayed_task_correct": self.delayed_task_correct,
                "delayed_sender_reward_suppressions": (
                    self.delayed_sender_reward_suppressions
                ),
                "abstract_signal_delivery_trace_sha256": (
                    self.abstract_signal_delivery_trace_sha256
                ),
                "propagation_edge_counts": dict(
                    sorted(self.propagation_edge_counts.items())
                ),
                "total_ecological_credit": round(
                    self.total_ecological_credit, 6
                ),
            },
            "archive_state_sha256": canonical_sha256(self.archive_records),
            "habitat_graph_sha256": canonical_sha256(
                self.config["habitat_graph"]
            ),
            "ood_habitat_graph_sha256": canonical_sha256(
                self.config["ood_habitat_graph"]
            ),
            "ood_graph_transform": ood_transform,
        }

    def _signaling_exposure(self) -> dict[str, Any]:
        result = deep_copy_json(self.training_exposure)
        total = int(result["eligible"])
        host_ids = set(self.sender_role_counts) | set(self.receiver_role_counts)
        maximum_role_difference = max(
            (
                abs(
                    self.sender_role_counts.get(host_id, 0)
                    - self.receiver_role_counts.get(host_id, 0)
                )
                for host_id in host_ids
            ),
            default=total,
        )
        result["paired_imbalance"] = (
            round(maximum_role_difference / total, 6)
            if total > 0
            else 1.0
        )
        return result

    def _evaluation_plan(
        self, checkpoint_population: Sequence[Mapping[str, Any]]
    ) -> tuple[list[dict[str, Any]], DeterministicRNGLedger]:
        ledger = DeterministicRNGLedger(self.seed)
        self.extra_ledgers.append(ledger)
        plan: list[dict[str, Any]] = []
        need_orders: dict[int, tuple[list[int], str]] = {}
        for trial_index in range(self.config["evaluation_opportunities"]):
            block = trial_index // len(CONTEXT_IDS)
            if block not in need_orders:
                need_key = _key(
                    "evaluation.plan",
                    "shared",
                    self.config["cohorts"] - 1,
                    block,
                    "probe-plan",
                    (f"block:{block}",),
                    "need-order",
                )
                need_orders[block] = _draw_permutation(
                    ledger, need_key, len(CONTEXT_IDS)
                )
            need_order, need_receipt = need_orders[block]
            context_index = need_order[trial_index % len(CONTEXT_IDS)]
            trial_id = f"EV-{trial_index:04d}"
            sender_key = _key(
                "evaluation.plan",
                "shared",
                self.config["cohorts"] - 1,
                trial_index,
                "probe-plan",
                (f"trial:{trial_id}",),
                "sender",
            )
            sender_index, sender_receipt = _draw_integer(
                ledger, sender_key, len(checkpoint_population)
            )
            receiver_index = (sender_index + 1 + trial_index % 3) % len(
                checkpoint_population
            )
            if receiver_index == sender_index:
                receiver_index = (receiver_index + 1) % len(checkpoint_population)
            machine_key = _key(
                "evaluation.plan",
                "shared",
                self.config["cohorts"] - 1,
                trial_index,
                "probe-plan",
                (f"trial:{trial_id}",),
                "machine",
            )
            machine_index, machine_receipt = _draw_integer(
                ledger, machine_key, len(MACHINE_IDS)
            )
            noise_key = _key(
                "evaluation.plan",
                "shared",
                self.config["cohorts"] - 1,
                trial_index,
                "probe-plan",
                (f"trial:{trial_id}",),
                "channel-noise",
            )
            noisy, noise_receipt = _draw_bernoulli(
                ledger, noise_key, self.config["channel_noise_probability"]
            )
            alternate_key = _key(
                "evaluation.plan",
                "shared",
                self.config["cohorts"] - 1,
                trial_index,
                "probe-plan",
                (f"trial:{trial_id}",),
                "alternate",
            )
            alternate, alternate_receipt = _draw_integer(
                ledger, alternate_key, len(SIGNAL_IDS) - 1
            )
            plan.append(
                {
                    "trial_id": trial_id,
                    "context_index": context_index,
                    "sender_index": sender_index,
                    "receiver_index": receiver_index,
                    "machine_id": MACHINE_IDS[machine_index],
                    "noise_applied": noisy,
                    "noise_alternate": alternate,
                    "rng_receipt_ids": [
                        need_receipt,
                        sender_receipt,
                        machine_receipt,
                        noise_receipt,
                        alternate_receipt,
                    ],
                }
            )
        return plan, ledger

    @staticmethod
    def _apply_noise(signal_index: int, trial: Mapping[str, Any]) -> int:
        if not trial["noise_applied"]:
            return signal_index
        return (
            signal_index + 1 + int(trial["noise_alternate"])
        ) % len(SIGNAL_IDS)

    def _ood_receiver_index(
        self,
        sender_index: int,
        trial_index: int,
        checkpoint_population: Sequence[Mapping[str, Any]],
    ) -> int:
        """Choose a partner from the registered alternate habitat graph."""

        sender_machine = str(checkpoint_population[sender_index]["machine_id"])
        allowed_machines = set(self.config["ood_habitat_graph"][sender_machine])
        candidates = [
            index
            for index, agent in enumerate(checkpoint_population)
            if index != sender_index and agent["machine_id"] in allowed_machines
        ]
        if not candidates:
            candidates = [
                index
                for index in range(len(checkpoint_population))
                if index != sender_index
            ]
        return candidates[trial_index % len(candidates)]

    def _evaluate_branch(
        self,
        branch: str,
        checkpoint_population: Sequence[Mapping[str, Any]],
        checkpoint_sha256: str,
        plan: Sequence[Mapping[str, Any]],
        intact_by_trial: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        ledger = DeterministicRNGLedger(self.seed)
        self.extra_ledgers.append(ledger)
        rows: list[dict[str, Any]] = []
        global_permutation: list[int] | None = None
        global_receipt: str | None = None
        message_order: list[int] | None = None
        message_receipt: str | None = None
        if branch == "global_relabel":
            relabel_key = _key(
                "evaluation.intervention",
                branch,
                self.config["cohorts"] - 1,
                -1,
                "global-relabel",
                ("alphabet:S",),
                "permutation",
            )
            global_permutation, global_receipt = _draw_permutation(
                ledger, relabel_key, len(SIGNAL_IDS)
            )
        elif branch == "per_message_permutation":
            message_key = _key(
                "evaluation.intervention",
                branch,
                self.config["cohorts"] - 1,
                -1,
                "message-permutation",
                ("schedule:evaluation",),
                "trial-order",
            )
            message_order, message_receipt = _draw_permutation(
                ledger, message_key, len(plan)
            )

        archive_signals = [
            record
            for record in self.archive_records
            if record["status"] == "woken"
        ]

        redirect_count = 0
        action_change_count = 0
        for trial_index, trial in enumerate(plan):
            trial_id = str(trial["trial_id"])
            live_context_index = int(trial["context_index"])
            effective_context_index = live_context_index
            sender = checkpoint_population[int(trial["sender_index"])]
            receiver_index = int(trial["receiver_index"])
            if branch == "ood_topology":
                receiver_index = self._ood_receiver_index(
                    int(trial["sender_index"]),
                    trial_index,
                    checkpoint_population,
                )
            receiver = checkpoint_population[receiver_index]
            sender_map = [_signal_index(value) for value in sender["sender_map"]]
            receiver_map = list(receiver["receiver_map"])
            emitted_index = sender_map[live_context_index]
            base_delivered = self._apply_noise(emitted_index, trial)
            delivered_index: int | None = base_delivered
            archive_record_id: str | None = None
            delayed_task_binding_id: str | None = None
            effective_receiver_map = receiver_map
            branch_receipts: list[str] = []

            if branch == "no_channel":
                delivered_index = None
            elif branch == "delayed_archive" and archive_signals:
                archive_record = archive_signals[
                    trial_index % len(archive_signals)
                ]
                archive_record_id = str(archive_record["record_id"])
                delivered_index = _signal_index(
                    str(archive_record["abstract_signal"]["signal_id"])
                )
                delayed_task_binding = archive_record[
                    "delayed_task_binding"
                ]
                delayed_task_binding_id = str(
                    delayed_task_binding["binding_id"]
                )
                effective_context_index = CONTEXT_IDS.index(
                    str(
                        delayed_task_binding[
                            "pressure_class_evaluator_only"
                        ]
                    )
                )
                if delayed_task_binding[
                    "required_skill_evaluator_only"
                ] != SKILL_IDS[effective_context_index]:
                    raise AssertionError(
                        "delayed task pressure and skill must remain paired"
                    )
            elif branch == "per_message_permutation":
                assert message_order is not None and message_receipt is not None
                source_trial_id = str(plan[message_order[trial_index]]["trial_id"])
                delivered_index = _signal_index(
                    str(intact_by_trial[source_trial_id]["delivered_signal"])
                )
                branch_receipts.append(message_receipt)
            elif branch == "global_relabel":
                assert global_permutation is not None and global_receipt is not None
                emitted_index = global_permutation[emitted_index]
                delivered_index = global_permutation[base_delivered]
                relabeled = ["" for _ in SIGNAL_IDS]
                for original_signal, relabeled_signal in enumerate(global_permutation):
                    relabeled[relabeled_signal] = receiver_map[original_signal]
                effective_receiver_map = relabeled
                branch_receipts.append(global_receipt)
            elif branch == "symbol_swap":
                swap_key = _key(
                    "evaluation.intervention",
                    branch,
                    self.config["cohorts"] - 1,
                    trial_index,
                    "do-signal",
                    (f"trial:{trial_id}",),
                    "alternate",
                )
                offset, swap_receipt = _draw_integer(
                    ledger, swap_key, len(SIGNAL_IDS) - 1
                )
                delivered_index = (
                    base_delivered + 1 + offset
                ) % len(SIGNAL_IDS)
                branch_receipts.append(swap_receipt)

            if branch == "receiver_knockout":
                action = SKILL_IDS[0]
            elif delivered_index is None:
                action = receiver_map[0]
            else:
                action = effective_receiver_map[delivered_index]

            hidden_need = CONTEXT_IDS[effective_context_index]
            live_hidden_need = CONTEXT_IDS[live_context_index]
            correct = action == _skill_for_context(hidden_need)
            opportunity_id = trial_id
            receiver_observation: dict[str, Any] = {
                "opportunity_id": opportunity_id,
                "machine_id": trial["machine_id"],
                "channel": self.condition["channel"],
                "carrier": "abstract_signal",
            }
            if delivered_index is not None:
                receiver_observation["signal"] = _signal_label(delivered_index)
            if archive_record_id is not None:
                receiver_observation["archive_record_id"] = archive_record_id
            row: dict[str, Any] = {
                "trial_id": trial_id,
                "branch": branch,
                "opportunity_id": opportunity_id,
                "cohort": self.config["cohorts"] - 1,
                "generation": self.config["generations_per_cohort"] - 1,
                "machine_id": trial["machine_id"],
                "channel": self.condition["channel"],
                "hidden_need": hidden_need,
                "delayed_task_binding_id": delayed_task_binding_id,
                "sender_id": sender["agent_id"],
                "receiver_id": receiver["agent_id"],
                "sender_lineage_id": sender["sender_policy_lineage_id"],
                "receiver_lineage_id": receiver[
                    "receiver_policy_lineage_id"
                ],
                "sender_observation": {
                    "opportunity_id": opportunity_id,
                    "machine_id": trial["machine_id"],
                    "need": live_hidden_need,
                },
                "receiver_observation": receiver_observation,
                "emitted_signal": _signal_label(emitted_index),
                "delivered_signal": (
                    None
                    if delivered_index is None
                    else _signal_label(delivered_index)
                ),
                "receiver_action": action,
                "correct_outcome": correct,
                "task_reward": 0.0,
                "rng_receipt_ids": [
                    *trial["rng_receipt_ids"],
                    *branch_receipts,
                ],
            }
            if branch == "symbol_swap":
                intact = intact_by_trial[trial_id]
                original_action = intact["receiver_action"]
                forced_action = effective_receiver_map[int(delivered_index)]
                redirected = forced_action == action and action != original_action
                changed = action != original_action
                row.update(
                    {
                        "counterfactual_pair_id": f"CF-{trial_id}",
                        "original_delivered_signal": intact["delivered_signal"],
                        "forced_signal": _signal_label(int(delivered_index)),
                        "original_receiver_action": original_action,
                        "counterfactual_receiver_action": action,
                        "decoded_action_for_forced_signal": forced_action,
                        "redirect_toward_forced_signal": redirected,
                    }
                )
                redirect_count += redirected
                action_change_count += changed
            rows.append(row)

        metrics: dict[str, Any] = {
            "trials": len(rows),
            "accuracy": _accuracy(rows),
            "delivered_signals": sum(
                row["delivered_signal"] is not None for row in rows
            ),
            "evaluation_reward_applied": 0.0,
        }
        if branch == "symbol_swap":
            metrics.update(
                {
                    "action_change_rate": round(action_change_count / len(rows), 6),
                    "redirect_toward_forced_signal_rate": round(
                        redirect_count / len(rows), 6
                    ),
                }
            )
        elif branch == "per_message_permutation":
            assert message_order is not None
            matched_ids = sorted(intact_by_trial)
            intact_histogram = {
                signal: sum(
                    row["delivered_signal"] == signal
                    for row in intact_by_trial.values()
                )
                for signal in SIGNAL_IDS
            }
            permuted_histogram = {
                signal: sum(row["delivered_signal"] == signal for row in rows)
                for signal in SIGNAL_IDS
            }
            metrics.update(
                {
                    "matched_event_ids_hash": canonical_sha256(matched_ids),
                    "intact_signal_histogram_hash": canonical_sha256(
                        intact_histogram
                    ),
                    "permuted_signal_histogram_hash": canonical_sha256(
                        permuted_histogram
                    ),
                    "event_index_permutation_hash": canonical_sha256(
                        message_order
                    ),
                }
            )
        return {
            "checkpoint_sha256": checkpoint_sha256,
            "projection_sha256": checkpoint_sha256,
            "trials": rows,
            "metrics": metrics,
        }

    def evaluate(
        self, checkpoint_projection: Mapping[str, Any], checkpoint_sha256: str
    ) -> dict[str, Any]:
        checkpoint_population = checkpoint_projection["population"]
        plan, _ = self._evaluation_plan(checkpoint_population)
        task_plan_public = [
            {
                "trial_id": trial["trial_id"],
                "context": CONTEXT_IDS[int(trial["context_index"])],
                "sender_index": trial["sender_index"],
                "receiver_index": trial["receiver_index"],
                "machine_id": trial["machine_id"],
                "noise_applied": trial["noise_applied"],
                "noise_alternate": trial["noise_alternate"],
            }
            for trial in plan
        ]
        _ = canonical_sha256(task_plan_public)
        evaluations: dict[str, Any] = {}
        intact = self._evaluate_branch(
            "intact",
            checkpoint_population,
            checkpoint_sha256,
            plan,
            {},
        )
        evaluations["intact"] = intact
        intact_by_trial = {row["trial_id"]: row for row in intact["trials"]}
        for branch in EVALUATION_BRANCHES:
            if branch == "intact":
                continue
            result = self._evaluate_branch(
                branch,
                checkpoint_population,
                checkpoint_sha256,
                plan,
                intact_by_trial,
            )
            evaluations[branch] = result
        if self.archive_wakes > 0:
            result = self._evaluate_branch(
                "delayed_archive",
                checkpoint_population,
                checkpoint_sha256,
                plan,
                intact_by_trial,
            )
            evaluations["delayed_archive"] = result
        return evaluations

    def _policy_ancestry_table(
        self, rows: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        return _columnar(
            POLICY_ANCESTRY_COLUMNS,
            [
                [row[column] for column in POLICY_ANCESTRY_COLUMNS]
                for row in rows
            ],
        )

    def _audit_receipts(
        self,
        checkpoint_projection: Mapping[str, Any],
        evaluations: Mapping[str, Any],
        sender_policy_ancestry: Mapping[str, Any],
        receiver_policy_ancestry: Mapping[str, Any],
    ) -> dict[str, Any]:
        transform = checkpoint_projection["ood_graph_transform"]
        permutation_metrics = evaluations["per_message_permutation"]["metrics"]
        archive_rows: list[list[Any]] = []
        for record in self.archive_records:
            propagule = record["convention_propagule"]
            delayed_task_binding = record["delayed_task_binding"]
            activated = propagule["activation_host_id"] is not None
            sender_result_id = propagule[
                "activation_sender_policy_lineage_id"
            ]
            receiver_result_id = propagule[
                "activation_receiver_policy_lineage_id"
            ]
            sender_state_change = (
                sender_result_id
                != propagule["replaced_sender_policy_lineage_id"]
                if activated
                else None
            )
            receiver_state_change = (
                receiver_result_id
                != propagule["replaced_receiver_policy_lineage_id"]
                if activated
                else None
            )
            archive_rows.append(
                [
                    record["record_id"],
                    record["wake_cohort"] - record["origin_cohort"],
                    propagule["propagule_id"],
                    propagule[
                        "propagule_sender_source_policy_lineage_id"
                    ],
                    propagule[
                        "propagule_receiver_source_policy_lineage_id"
                    ],
                    propagule[
                        "propagule_sender_policy_allele_values"
                    ],
                    propagule[
                        "propagule_receiver_policy_allele_values"
                    ],
                    propagule["propagule_sender_policy_alleles_hash"],
                    propagule["propagule_receiver_policy_alleles_hash"],
                    propagule["propagule_payload_hash"],
                    record["wake_cohort"],
                    propagule["activation_host_id"],
                    sender_result_id if sender_state_change else None,
                    receiver_result_id if receiver_state_change else None,
                    sender_result_id,
                    receiver_result_id,
                    sender_state_change,
                    receiver_state_change,
                    f"PA:{record['record_id']}" if activated else None,
                    propagule["visible_as_observation"],
                    delayed_task_binding["binding_id"],
                    delayed_task_binding[
                        "pressure_class_evaluator_only"
                    ],
                    delayed_task_binding[
                        "required_skill_evaluator_only"
                    ],
                ]
            )

        intact_by_id = {
            row["opportunity_id"]: row
            for row in evaluations["intact"]["trials"]
        }
        probe_pair_rows: list[list[Any]] = []
        for row in evaluations["symbol_swap"]["trials"]:
            opportunity_id = row["opportunity_id"]
            intact = intact_by_id[opportunity_id]
            probe_pair_rows.append(
                [
                    row["counterfactual_pair_id"],
                    intact["opportunity_id"],
                    opportunity_id,
                ]
            )

        generation_batches = _columnar(
            GENERATION_BATCH_COLUMNS, self.generation_audit_rows
        )
        policy_transition_batches = _columnar(
            POLICY_TRANSITION_BATCH_COLUMNS, self.policy_transition_rows
        )
        interaction_batches = _columnar(
            INTERACTION_BATCH_COLUMNS, self.interaction_batch_rows
        )
        propagation_rows = _columnar(
            PROPAGATION_ROW_COLUMNS, self.propagation_audit_rows
        )
        archive_table = _columnar(ARCHIVE_ROW_COLUMNS, archive_rows)
        probe_pairs = _columnar(PROBE_PAIR_COLUMNS, probe_pair_rows)
        table_row_hashes = {
            "sender_policy_ancestry": sender_policy_ancestry["rows_sha256"],
            "receiver_policy_ancestry": receiver_policy_ancestry[
                "rows_sha256"
            ],
            "generation_batches": generation_batches["rows_sha256"],
            "policy_transition_batches": policy_transition_batches[
                "rows_sha256"
            ],
            "interaction_batches": interaction_batches["rows_sha256"],
            "propagation_rows": propagation_rows["rows_sha256"],
            "archive_rows": archive_table["rows_sha256"],
            "probe_pairs": probe_pairs["rows_sha256"],
        }
        audit: dict[str, Any] = {
            "schema": AUDIT_SCHEMA,
            "required_fields_sha256": REQUIRED_AUDIT_FIELDS_SHA256,
            "field_coverage": deep_copy_json(AUDIT_FIELD_COVERAGE),
            "id_templates": deep_copy_json(AUDIT_ID_TEMPLATES),
            "episode": {
                "episode_seed": self.seed,
                "condition_id": self.condition["id"],
                "candidate_regime_id": self.config["id"],
                "base_habitat_graph_hash": checkpoint_projection[
                    "habitat_graph_sha256"
                ],
                "ood_habitat_graph_hash": checkpoint_projection[
                    "ood_habitat_graph_sha256"
                ],
                "ood_removed_edge_receipt": list(transform["removed_edge"]),
                "ood_added_edge_receipt": list(transform["added_edge"]),
                "ood_graph_transform_hash": transform["transform_sha256"],
                "probe_feedback_to_fitness": False,
                "cohort_overlap": False,
                "hazard_flags": {
                    "external_io": False,
                    "arbitrary_text_payload": False,
                    "executable_payload": False,
                    "receiver_truth_leak": False,
                    "propagule_observation": False,
                },
            },
            "generation_batches": generation_batches,
            "policy_transition_batches": policy_transition_batches,
            "interaction_batches": interaction_batches,
            "propagation_rows": propagation_rows,
            "archive_rows": archive_table,
            "probe_pairs": probe_pairs,
            "probe": {
                "matched_event_ids_hash": permutation_metrics[
                    "matched_event_ids_hash"
                ],
                "intact_signal_histogram_hash": permutation_metrics[
                    "intact_signal_histogram_hash"
                ],
                "permuted_signal_histogram_hash": permutation_metrics[
                    "permuted_signal_histogram_hash"
                ],
                "event_index_permutation_hash": permutation_metrics[
                    "event_index_permutation_hash"
                ],
            },
            "tables_sha256": canonical_sha256(table_row_hashes),
        }
        audit["audit_receipts_sha256"] = canonical_sha256(audit)
        return audit

    def _combined_rng(self, evaluations: Mapping[str, Any]) -> dict[str, Any]:
        receipts = self.rng.receipts()
        for ledger in self.extra_ledgers:
            receipts.extend(ledger.receipts())
        receipts.sort(key=lambda row: row["receipt_id"])
        receipt_ids = [row["receipt_id"] for row in receipts]
        if len(receipt_ids) != len(set(receipt_ids)):
            raise AssertionError("RNG receipt ids must be globally unique")
        referenced: set[str] = set()
        for branch in evaluations.values():
            for row in branch["trials"]:
                referenced.update(row["rng_receipt_ids"])
        for transfer in self.horizontal_transfers:
            referenced.update(transfer["rng_receipt_ids"])
        for record in self.archive_records:
            referenced.update(
                record["convention_propagule"]["source_rng_receipt_ids"]
            )
        receipt_by_id = {row["receipt_id"]: row for row in receipts}
        missing = sorted(referenced - set(receipt_by_id))
        if missing:
            raise AssertionError(f"referenced RNG receipts are missing: {missing}")
        retained = [receipt_by_id[receipt_id] for receipt_id in sorted(referenced)]
        return {
            "receipts": retained,
            "receipts_sha256": canonical_sha256(retained),
        }

    def episode(self) -> dict[str, Any]:
        checkpoint_projection = self._checkpoint_projection()
        checkpoint_sha256 = checkpoint_hash(checkpoint_projection)
        evaluations = self.evaluate(checkpoint_projection, checkpoint_sha256)
        sender_policy_ancestry = self._policy_ancestry_table(
            self.sender_policy_ancestry
        )
        receiver_policy_ancestry = self._policy_ancestry_table(
            self.receiver_policy_ancestry
        )
        audit_receipts = self._audit_receipts(
            checkpoint_projection,
            evaluations,
            sender_policy_ancestry,
            receiver_policy_ancestry,
        )
        symbol_metrics = evaluations["symbol_swap"]["metrics"]
        episode_id = f"E-{canonical_sha256({'seed': self.seed, 'config': self.config, 'condition': self.condition})[:20]}"
        episode: dict[str, Any] = {
            "schema": EPISODE_SCHEMA,
            "episode_id": episode_id,
            "seed": self.seed,
            "limits": {
                "max_population": MAX_POPULATION,
                "max_cohorts": MAX_COHORTS,
                "max_generations": MAX_COHORTS * MAX_GENERATIONS_PER_COHORT,
                "max_archive_records": MAX_ARCHIVE_CAPACITY,
                "max_horizontal_transfers": MAX_HORIZONTAL_TRANSFERS,
            },
            "population": len(self.population),
            "cohorts": self.config["cohorts"],
            "generations": (
                self.config["cohorts"]
                * self.config["generations_per_cohort"]
            ),
            "cohort_turnovers": deep_copy_json(self.cohort_turnovers),
            "host_ancestry": [
                {
                    "id": row["id"],
                    "parent_ids": list(row["parent_ids"]),
                    "cohort": row["cohort"],
                }
                for row in self.host_ancestry
            ],
            "sender_policy_ancestry": sender_policy_ancestry,
            "receiver_policy_ancestry": receiver_policy_ancestry,
            "selection": {
                "fitness_metric": "ecological_task_reward",
                "fitness_inputs": ["ecological_task_reward"],
                "probe_feedback_to_fitness": False,
            },
            "archive": {
                "capacity": max(1, self.config["archive"]["capacity"]),
                "peak_records": self.archive_peak,
                "wakes": self.archive_wakes,
                "records": deep_copy_json(self.archive_records),
            },
            "horizontal_transfers": deep_copy_json(self.horizontal_transfers),
            "audit_receipts": audit_receipts,
            "rng": self._combined_rng(evaluations),
            "frozen_checkpoint": {
                "projection": checkpoint_projection,
                "sha256": checkpoint_sha256,
            },
            "evaluations": evaluations,
            "exposure": {
                "signaling": self._signaling_exposure(),
                "archive": {
                    "eligible": self.archive_deposits,
                    "deposited": self.archive_deposits,
                    "woken": self.archive_wakes,
                    "abstract_signal_delivered": self.abstract_signal_deliveries,
                },
                "delayed_archive": {
                    "eligible": self.archive_wakes,
                    "activated": (
                        len(evaluations.get("delayed_archive", {}).get("trials", []))
                    ),
                    "training_deliveries": self.abstract_signal_deliveries,
                    "training_correct": self.delayed_task_correct,
                    "sender_reward_suppressions": (
                        self.delayed_sender_reward_suppressions
                    ),
                },
                "symbol_swap": {
                    "eligible": self.config["evaluation_opportunities"],
                    "forced": self.config["evaluation_opportunities"],
                    "action_change_rate": symbol_metrics["action_change_rate"],
                    "redirect_toward_forced_signal_rate": symbol_metrics[
                        "redirect_toward_forced_signal_rate"
                    ],
                },
            },
            "storyworld_events": deep_copy_json(self.storyworld_events),
        }
        episode["deterministic_projection_sha256"] = canonical_sha256(
            deterministic_projection(episode)
        )
        episode["episode_sha256"] = canonical_sha256(episode)
        return deep_copy_json(episode)


def run_world(
    config: Mapping[str, Any] | None,
    condition: Mapping[str, Any] | None,
    seed: int,
) -> dict[str, Any]:
    """Run one bounded evolutionary world and its frozen evaluation branches."""

    validated_config = validate_config(config)
    validated_condition = validate_condition(condition)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    runner = _EcologyRunner(validated_config, validated_condition, seed)
    runner.train()
    return runner.episode()


__all__ = [
    "checkpoint_hash",
    "default_config",
    "deterministic_projection",
    "run_world",
    "validate_config",
]
