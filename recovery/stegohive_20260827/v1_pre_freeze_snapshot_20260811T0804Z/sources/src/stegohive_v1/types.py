"""Typed constants and validation for the sealed StegoHive v1 ecology."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Literal, Mapping, TypedDict

from stegohive.types import MACHINE_IDS

from .storyworld_tools import validate_storyworld_deck


CONFIG_SCHEMA = "alife.stegohive.ecology.config.v1"
EPISODE_SCHEMA = "alife.stegohive.ecology.episode.v1"
RNG_SCHEMA = "alife.stegohive.ecology.rng.v1"

SIGNAL_INDEXES = (0, 1, 2, 3)
SIGNAL_IDS = ("S0", "S1", "S2", "S3")
SIGNAL_LABELS = SIGNAL_IDS
CONTEXT_IDS = ("C0", "C1", "C2", "C3")
SKILL_IDS = ("K0", "K1", "K2", "K3")
CHANNELS = ("abstract_signal",)
TOPOLOGIES = ("ring", "paired")
EVALUATION_BRANCHES = (
    "intact",
    "no_channel",
    "per_message_permutation",
    "receiver_knockout",
    "add_back",
    "global_relabel",
    "ood_topology",
    "symbol_swap",
)

MAX_POPULATION = 64
MAX_COHORTS = 6
MAX_GENERATIONS_PER_COHORT = 30
MAX_OPPORTUNITIES_PER_GENERATION = 256
MAX_EVALUATION_OPPORTUNITIES = 512
MAX_ARCHIVE_CAPACITY = 256

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")


class ConfigError(ValueError):
    """Raised when an ecology configuration violates its sealed schema."""


class OpportunityReceipt(TypedDict, total=False):
    opportunity_id: str
    trial_id: str
    phase: Literal["initialization", "training", "evaluation"]
    branch: str
    cohort: int
    generation: int
    machine_id: str
    hidden_need: str
    sender_id: str
    receiver_id: str
    sender_observation: dict[str, Any]
    receiver_observation: dict[str, Any]
    emitted_signal: int | None
    delivered_signal: int | None
    receiver_action: str
    correct_outcome: bool
    task_reward: float
    channel: str
    rng_receipt_ids: list[str]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def deep_copy_json(value: Any) -> Any:
    return json.loads(canonical_bytes(value).decode("utf-8"))


def safe_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID_RE.fullmatch(value):
        raise ConfigError(f"{label} must be a safe enum identifier")
    return value


def _integer(value: Any, label: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{label} must be an integer")
    if not lower <= value <= upper:
        raise ConfigError(f"{label} must be in [{lower}, {upper}]")
    return value


def _number(value: Any, label: str, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ConfigError(f"{label} must be finite and in [{lower}, {upper}]")
    return result


def default_habitat_graph() -> dict[str, list[str]]:
    nodes = list(MACHINE_IDS)
    return {
        node: sorted({nodes[(index - 1) % len(nodes)], nodes[(index + 1) % len(nodes)]})
        for index, node in enumerate(nodes)
    }


def default_ood_habitat_graph() -> dict[str, list[str]]:
    """Return the registered connected one-edge swap of the default graph."""

    graph = default_habitat_graph()
    left, removed_right, added_right = MACHINE_IDS[0:3]
    graph[left].remove(removed_right)
    graph[removed_right].remove(left)
    graph[left].append(added_right)
    graph[added_right].append(left)
    return {node: sorted(neighbors) for node, neighbors in graph.items()}


def _undirected_edges(graph: Mapping[str, list[str]]) -> set[tuple[str, str]]:
    return {
        tuple(sorted((left, right)))
        for left, neighbors in graph.items()
        for right in neighbors
    }


def _is_connected(graph: Mapping[str, list[str]]) -> bool:
    start = MACHINE_IDS[0]
    visited = {start}
    frontier = [start]
    while frontier:
        node = frontier.pop()
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return visited == set(MACHINE_IDS)


def _validate_ood_transform(
    habitat_graph: Mapping[str, list[str]],
    ood_graph: Mapping[str, list[str]],
) -> None:
    habitat_edges = _undirected_edges(habitat_graph)
    ood_edges = _undirected_edges(ood_graph)
    removed = habitat_edges - ood_edges
    added = ood_edges - habitat_edges
    if len(habitat_edges) != len(ood_edges):
        raise ConfigError("ood_habitat_graph must preserve habitat edge count")
    if len(removed) != 1 or len(added) != 1:
        raise ConfigError("ood_habitat_graph must perform exactly one edge swap")
    if not _is_connected(ood_graph):
        raise ConfigError("ood_habitat_graph must remain connected")


def _validate_habitat_graph(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, Mapping) or set(value) != set(MACHINE_IDS):
        raise ConfigError("habitat_graph must define exactly the six fictional machines")
    graph: dict[str, list[str]] = {}
    for machine_id in MACHINE_IDS:
        neighbors = value[machine_id]
        if not isinstance(neighbors, list) or not neighbors:
            raise ConfigError(f"habitat_graph.{machine_id} must be a non-empty array")
        if any(neighbor not in MACHINE_IDS or neighbor == machine_id for neighbor in neighbors):
            raise ConfigError(f"habitat_graph.{machine_id} contains an invalid neighbor")
        if len(neighbors) != len(set(neighbors)):
            raise ConfigError(f"habitat_graph.{machine_id} contains duplicate neighbors")
        graph[machine_id] = sorted(neighbors)
    for left, neighbors in graph.items():
        for right in neighbors:
            if left not in graph[right]:
                raise ConfigError(f"habitat link {left}<->{right} must be symmetric")
    return graph


def default_config() -> dict[str, Any]:
    """Return a small configuration that exercises every core evolutionary phase."""

    return {
        "schema": CONFIG_SCHEMA,
        "id": "stegohive-v1-smoke",
        "population_size": 32,
        "cohorts": 3,
        "generations_per_cohort": 4,
        "opportunities_per_generation": 24,
        "evaluation_opportunities": 32,
        "task_reward": 1.0,
        "propagation_probability": 0.15,
        "signal_cost": 0.02,
        "channel_noise_probability": 0.0,
        "mutation_rate": 0.08,
        "horizontal_transfer_rate": 0.25,
        "topology": "ring",
        "habitat_graph": default_habitat_graph(),
        "ood_habitat_graph": default_ood_habitat_graph(),
        "archive": {
            "enabled": True,
            "capacity": 32,
            "delay_cohorts": 2,
            "deposit_count": 4,
        },
        "storyworld": None,
    }


def validate_config(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate and detach a compact engine configuration."""

    source = default_config() if value is None else deep_copy_json(value)
    if not isinstance(source, dict):
        raise ConfigError("config must be an object")
    allowed = {
        "schema",
        "id",
        "population_size",
        "cohorts",
        "generations_per_cohort",
        "opportunities_per_generation",
        "evaluation_opportunities",
        "task_reward",
        "propagation_probability",
        "signal_cost",
        "channel_noise_probability",
        "mutation_rate",
        "horizontal_transfer_rate",
        "topology",
        "habitat_graph",
        "ood_habitat_graph",
        "archive",
        "storyworld",
    }
    unknown = sorted(set(source) - allowed)
    if unknown:
        raise ConfigError(f"unknown config fields: {', '.join(unknown)}")
    if source.get("schema") != CONFIG_SCHEMA:
        raise ConfigError(f"schema must equal {CONFIG_SCHEMA}")

    config_id = safe_id(source.get("id", "stegohive-v1"), "id")
    population_size = _integer(
        source.get("population_size"), "population_size", 4, MAX_POPULATION
    )
    if population_size % 2:
        raise ConfigError("population_size must be even")
    cohorts = _integer(source.get("cohorts"), "cohorts", 1, MAX_COHORTS)
    generations = _integer(
        source.get("generations_per_cohort"),
        "generations_per_cohort",
        1,
        MAX_GENERATIONS_PER_COHORT,
    )
    opportunities = _integer(
        source.get("opportunities_per_generation"),
        "opportunities_per_generation",
        4,
        MAX_OPPORTUNITIES_PER_GENERATION,
    )
    evaluation_opportunities = _integer(
        source.get("evaluation_opportunities"),
        "evaluation_opportunities",
        4,
        MAX_EVALUATION_OPPORTUNITIES,
    )
    task_reward = _number(source.get("task_reward"), "task_reward", 0.0, 100.0)
    if task_reward <= 0.0:
        raise ConfigError("task_reward must be positive")
    propagation_probability = _number(
        source.get("propagation_probability", 0.15),
        "propagation_probability",
        0.0,
        1.0,
    )
    signal_cost = _number(
        source.get("signal_cost", 0.02), "signal_cost", 0.0, task_reward
    )
    channel_noise_probability = _number(
        source.get("channel_noise_probability", 0.0),
        "channel_noise_probability",
        0.0,
        1.0,
    )
    mutation_rate = _number(source.get("mutation_rate"), "mutation_rate", 0.0, 1.0)
    horizontal_rate = _number(
        source.get("horizontal_transfer_rate"),
        "horizontal_transfer_rate",
        0.0,
        1.0,
    )
    topology = source.get("topology")
    if topology not in TOPOLOGIES:
        raise ConfigError(f"topology must be one of {TOPOLOGIES}")
    graph = _validate_habitat_graph(source.get("habitat_graph"))
    if not _is_connected(graph):
        raise ConfigError("habitat_graph must be connected")
    ood_graph = _validate_habitat_graph(source.get("ood_habitat_graph"))
    _validate_ood_transform(graph, ood_graph)

    archive = source.get("archive")
    if not isinstance(archive, dict):
        raise ConfigError("archive must be an object")
    if set(archive) != {"enabled", "capacity", "delay_cohorts", "deposit_count"}:
        raise ConfigError(
            "archive must contain enabled, capacity, delay_cohorts, and deposit_count"
        )
    if not isinstance(archive["enabled"], bool):
        raise ConfigError("archive.enabled must be boolean")
    capacity = _integer(
        archive["capacity"], "archive.capacity", 0, MAX_ARCHIVE_CAPACITY
    )
    delay = _integer(
        archive["delay_cohorts"],
        "archive.delay_cohorts",
        1,
        max(1, MAX_COHORTS - 1),
    )
    deposit_count = _integer(
        archive["deposit_count"], "archive.deposit_count", 0, population_size
    )
    if archive["enabled"] and (capacity == 0 or deposit_count == 0):
        raise ConfigError("enabled archive needs positive capacity and deposit_count")
    if not archive["enabled"] and deposit_count != 0:
        raise ConfigError("disabled archive must have deposit_count 0")

    storyworld = validate_storyworld_deck(
        source.get("storyworld"),
        max_cohorts=cohorts,
        max_generations=generations,
    )
    return {
        "schema": CONFIG_SCHEMA,
        "id": config_id,
        "population_size": population_size,
        "cohorts": cohorts,
        "generations_per_cohort": generations,
        "opportunities_per_generation": opportunities,
        "evaluation_opportunities": evaluation_opportunities,
        "task_reward": task_reward,
        "propagation_probability": propagation_probability,
        "signal_cost": signal_cost,
        "channel_noise_probability": channel_noise_probability,
        "mutation_rate": mutation_rate,
        "horizontal_transfer_rate": horizontal_rate,
        "topology": topology,
        "habitat_graph": graph,
        "ood_habitat_graph": ood_graph,
        "archive": {
            "enabled": archive["enabled"],
            "capacity": capacity,
            "delay_cohorts": delay,
            "deposit_count": deposit_count,
        },
        "storyworld": storyworld,
    }


def default_condition() -> dict[str, Any]:
    return {
        "id": "adaptive_dual_archive",
        "channel": "abstract_signal",
        "archive_enabled": True,
        "horizontal_transfer_enabled": True,
        "mutation_enabled": True,
        "selection_mode": "task_reward",
    }


def validate_condition(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = default_condition() if value is None else deep_copy_json(value)
    if not isinstance(source, dict):
        raise ConfigError("condition must be an object")
    allowed = {
        "id",
        "channel",
        "archive_enabled",
        "horizontal_transfer_enabled",
        "mutation_enabled",
        "selection_mode",
    }
    unknown = sorted(set(source) - allowed)
    if unknown:
        raise ConfigError(f"unknown condition fields: {', '.join(unknown)}")
    channel = source.get("channel", "abstract_signal")
    if channel not in CHANNELS:
        raise ConfigError(f"condition.channel must be one of {CHANNELS}")
    for field in (
        "archive_enabled",
        "horizontal_transfer_enabled",
        "mutation_enabled",
    ):
        if not isinstance(source.get(field, True), bool):
            raise ConfigError(f"condition.{field} must be boolean")
    selection_mode = source.get("selection_mode", "task_reward")
    if selection_mode not in {"task_reward", "uniform"}:
        raise ConfigError("condition.selection_mode must be task_reward or uniform")
    inferred_id = (
        "no_archive"
        if source.get("archive_enabled", True) is False
        else (
            "selection_neutral"
            if selection_mode == "uniform"
            else "adaptive_dual_archive"
        )
    )
    condition_id = safe_id(source.get("id", inferred_id), "condition.id")
    return {
        "id": condition_id,
        "channel": channel,
        "archive_enabled": bool(source.get("archive_enabled", True)),
        "horizontal_transfer_enabled": bool(
            source.get("horizontal_transfer_enabled", True)
        ),
        "mutation_enabled": bool(source.get("mutation_enabled", True)),
        "selection_mode": selection_mode,
    }


__all__ = [
    "CHANNELS",
    "CONFIG_SCHEMA",
    "CONTEXT_IDS",
    "ConfigError",
    "EPISODE_SCHEMA",
    "EVALUATION_BRANCHES",
    "MACHINE_IDS",
    "MAX_COHORTS",
    "MAX_GENERATIONS_PER_COHORT",
    "MAX_POPULATION",
    "OpportunityReceipt",
    "RNG_SCHEMA",
    "SIGNAL_IDS",
    "SIGNAL_INDEXES",
    "SIGNAL_LABELS",
    "SKILL_IDS",
    "TOPOLOGIES",
    "canonical_sha256",
    "deep_copy_json",
    "default_condition",
    "default_config",
    "default_habitat_graph",
    "default_ood_habitat_graph",
    "validate_condition",
    "validate_config",
]
