"""Validated contracts for the evidence-driven StegoHive v2 reconstruction.

The constants and defaults in this module were recovered from retained V2/V3
episode records.  Validation is intentionally stricter than the lost runtime's
unknown implementation details so fresh reconstructed runs fail closed.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Mapping

from stegohive.types import MACHINE_IDS


CONFIG_SCHEMA = "alife.stegohive.integrated_config.v2"
CONDITION_SCHEMA = "alife.stegohive.integrated_condition.v2"
EPISODE_SCHEMA = "alife.stegohive.integrated_episode.v2"
STORYWORLD_SCHEMA = "alife.stegohive.storyworld_envelope.v2"

CLASSES = ("C0", "C1", "C2", "C3")
SIGNALS = ("S0", "S1", "S2", "S3")
SKILLS = ("K0", "K1", "K2", "K3")
CHANNEL_MODES = ("adaptive", "fixed_code", "matched_noise", "no_channel")
CREDIT_OPERATORS = ("balanced_crossplay", "encounter_local")
INHERITANCE_OPERATORS = ("independent_role_blocks", "linked_codebook")
SELECTION_MODES = ("differential", "uniform")

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._|:/-]{0,127}$")


class ContractError(ValueError):
    """Raised when a reconstructed world contract is invalid."""


def deep_copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def default_machine_graph() -> dict[str, list[str]]:
    """Return the six-node ring found in every retained integrated episode."""

    return {
        "BASTION-2": ["FERRY-8", "ONE-ROOT"],
        "CHOIR-6": ["ONE-ROOT", "ORCHARD-4"],
        "FERRY-8": ["BASTION-2", "MOTH-13"],
        "MOTH-13": ["FERRY-8", "ORCHARD-4"],
        "ONE-ROOT": ["BASTION-2", "CHOIR-6"],
        "ORCHARD-4": ["CHOIR-6", "MOTH-13"],
    }


def default_initial_service() -> dict[str, float]:
    return {
        "BASTION-2": 1.0,
        "CHOIR-6": 0.6,
        "FERRY-8": 0.6,
        "MOTH-13": 1.0,
        "ONE-ROOT": 1.0,
        "ORCHARD-4": 0.6,
    }


def default_config() -> dict[str, Any]:
    """Return the retained V3 discovery regime used by the reconstructed runner."""

    return {
        "archive": {
            "capacity": 32,
            "delay_cohorts": 1,
            "deposit_count": 4,
            "enabled": True,
        },
        "cohorts": 6,
        "generations_per_cohort": 12,
        "id": "stegohive-v2-reconstructed",
        "initial_service": default_initial_service(),
        "machine_graph": default_machine_graph(),
        "max_board_records": 256,
        "max_seal_turns": 6,
        "mutation_rate": 0.02,
        "opportunities_per_generation": 8,
        "population_size": 16,
        "pressure_propagation_probability": 0.05,
        "schema": CONFIG_SCHEMA,
        "service_decay": 0.0,
        "service_gain": 0.04,
        "signal_cost": 0.0,
        "storyworld": {"cards": [], "enabled": False, "schema": STORYWORLD_SCHEMA},
        "task_reward": 1.0,
    }


def condition_registry() -> dict[str, dict[str, Any]]:
    """Return all eight condition operators observed in retained V3 episodes."""

    shared = {
        "archive_enabled": True,
        "mutation_enabled": True,
        "schema": CONDITION_SCHEMA,
        "selection_mode": "differential",
    }
    rows = {
        "F00": ("adaptive", "encounter_local", "independent_role_blocks"),
        "F01": ("adaptive", "encounter_local", "linked_codebook"),
        "F10": ("adaptive", "balanced_crossplay", "independent_role_blocks"),
        "F11": ("adaptive", "balanced_crossplay", "linked_codebook"),
        "F11_matched_noise": ("matched_noise", "balanced_crossplay", "linked_codebook"),
        "F11_no_channel": ("no_channel", "balanced_crossplay", "linked_codebook"),
        "F11_selection_neutral": ("adaptive", "balanced_crossplay", "linked_codebook"),
        "fixed_code_ceiling": ("fixed_code", "encounter_local", "independent_role_blocks"),
    }
    result: dict[str, dict[str, Any]] = {}
    for condition_id, (channel, credit, inheritance) in rows.items():
        row = dict(shared)
        row.update(
            {
                "channel_mode": channel,
                "credit_operator": credit,
                "id": condition_id,
                "inheritance_operator": inheritance,
            }
        )
        if condition_id == "F11_selection_neutral":
            row["selection_mode"] = "uniform"
        if condition_id == "fixed_code_ceiling":
            row["mutation_enabled"] = False
        result[condition_id] = row
    return deep_copy_json(result)


def default_condition() -> dict[str, Any]:
    return condition_registry()["F10"]


def _integer(value: Any, label: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ContractError(f"{label} must be an integer in [{lower}, {upper}]")
    return value


def _number(value: Any, label: str, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ContractError(f"{label} must be finite and in [{lower}, {upper}]")
    return result


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{label} must be boolean")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ContractError(f"{label} must be a safe identifier")
    return value


def validate_config(value: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = default_config() if value is None else deep_copy_json(value)
    if not isinstance(source, dict):
        raise ContractError("config must be an object")
    expected = set(default_config())
    if set(source) != expected:
        raise ContractError(f"config fields must be exactly {sorted(expected)}")
    if source["schema"] != CONFIG_SCHEMA:
        raise ContractError(f"config.schema must equal {CONFIG_SCHEMA}")
    population = _integer(source["population_size"], "population_size", 4, 64)
    if population % 2:
        raise ContractError("population_size must be even")
    cohorts = _integer(source["cohorts"], "cohorts", 3, 12)
    generations = _integer(
        source["generations_per_cohort"], "generations_per_cohort", 2, 30
    )
    opportunities = _integer(
        source["opportunities_per_generation"],
        "opportunities_per_generation",
        4,
        256,
    )
    if opportunities % len(CLASSES):
        raise ContractError("opportunities_per_generation must be divisible by four")
    graph = source["machine_graph"]
    if not isinstance(graph, dict) or set(graph) != set(MACHINE_IDS):
        raise ContractError("machine_graph must define the six fictional machines")
    normalized_graph: dict[str, list[str]] = {}
    for node in MACHINE_IDS:
        neighbors = graph[node]
        if not isinstance(neighbors, list) or any(
            neighbor not in MACHINE_IDS or neighbor == node for neighbor in neighbors
        ):
            raise ContractError(f"machine_graph.{node} contains an invalid neighbor")
        normalized_graph[node] = sorted(set(neighbors))
    for node, neighbors in normalized_graph.items():
        if any(node not in normalized_graph[neighbor] for neighbor in neighbors):
            raise ContractError("machine_graph links must be symmetric")
    service = source["initial_service"]
    if not isinstance(service, dict) or set(service) != set(MACHINE_IDS):
        raise ContractError("initial_service must define the six fictional machines")
    normalized_service = {
        node: _number(service[node], f"initial_service.{node}", 0.0, 100.0)
        for node in MACHINE_IDS
    }
    archive = source["archive"]
    archive_fields = {"capacity", "delay_cohorts", "deposit_count", "enabled"}
    if not isinstance(archive, dict) or set(archive) != archive_fields:
        raise ContractError(f"archive fields must be exactly {sorted(archive_fields)}")
    archive_enabled = _boolean(archive["enabled"], "archive.enabled")
    capacity = _integer(archive["capacity"], "archive.capacity", 0, 256)
    delay = _integer(archive["delay_cohorts"], "archive.delay_cohorts", 1, cohorts)
    deposit_count = _integer(
        archive["deposit_count"], "archive.deposit_count", 0, population
    )
    if archive_enabled and (capacity == 0 or deposit_count == 0):
        raise ContractError("enabled archive requires positive capacity and deposit_count")
    storyworld = source["storyworld"]
    if (
        not isinstance(storyworld, dict)
        or set(storyworld) != {"cards", "enabled", "schema"}
        or storyworld["schema"] != STORYWORLD_SCHEMA
        or not isinstance(storyworld["cards"], list)
    ):
        raise ContractError("storyworld must use the retained disabled envelope schema")
    storyworld_enabled = _boolean(storyworld["enabled"], "storyworld.enabled")
    return {
        "archive": {
            "capacity": capacity,
            "delay_cohorts": delay,
            "deposit_count": deposit_count,
            "enabled": archive_enabled,
        },
        "cohorts": cohorts,
        "generations_per_cohort": generations,
        "id": _identifier(source["id"], "config.id"),
        "initial_service": normalized_service,
        "machine_graph": normalized_graph,
        "max_board_records": _integer(source["max_board_records"], "max_board_records", 1, 4096),
        "max_seal_turns": _integer(source["max_seal_turns"], "max_seal_turns", 1, 64),
        "mutation_rate": _number(source["mutation_rate"], "mutation_rate", 0.0, 1.0),
        "opportunities_per_generation": opportunities,
        "population_size": population,
        "pressure_propagation_probability": _number(
            source["pressure_propagation_probability"],
            "pressure_propagation_probability",
            0.0,
            1.0,
        ),
        "schema": CONFIG_SCHEMA,
        "service_decay": _number(source["service_decay"], "service_decay", 0.0, 100.0),
        "service_gain": _number(source["service_gain"], "service_gain", 0.0, 100.0),
        "signal_cost": _number(source["signal_cost"], "signal_cost", 0.0, 100.0),
        "storyworld": {
            "cards": deep_copy_json(storyworld["cards"]),
            "enabled": storyworld_enabled,
            "schema": STORYWORLD_SCHEMA,
        },
        "task_reward": _number(source["task_reward"], "task_reward", 0.000001, 100.0),
    }


def validate_condition(value: Mapping[str, Any] | str | None = None) -> dict[str, Any]:
    if value is None:
        source = default_condition()
    elif isinstance(value, str):
        registry = condition_registry()
        if value not in registry:
            raise ContractError(f"unknown registered condition: {value}")
        source = registry[value]
    else:
        source = deep_copy_json(value)
    expected = {
        "archive_enabled",
        "channel_mode",
        "credit_operator",
        "id",
        "inheritance_operator",
        "mutation_enabled",
        "schema",
        "selection_mode",
    }
    if not isinstance(source, dict) or set(source) != expected:
        raise ContractError(f"condition fields must be exactly {sorted(expected)}")
    if source["schema"] != CONDITION_SCHEMA:
        raise ContractError(f"condition.schema must equal {CONDITION_SCHEMA}")
    for field, choices in (
        ("channel_mode", CHANNEL_MODES),
        ("credit_operator", CREDIT_OPERATORS),
        ("inheritance_operator", INHERITANCE_OPERATORS),
        ("selection_mode", SELECTION_MODES),
    ):
        if source[field] not in choices:
            raise ContractError(f"condition.{field} must be one of {choices}")
    return {
        "archive_enabled": _boolean(source["archive_enabled"], "archive_enabled"),
        "channel_mode": source["channel_mode"],
        "credit_operator": source["credit_operator"],
        "id": _identifier(source["id"], "condition.id"),
        "inheritance_operator": source["inheritance_operator"],
        "mutation_enabled": _boolean(source["mutation_enabled"], "mutation_enabled"),
        "schema": CONDITION_SCHEMA,
        "selection_mode": source["selection_mode"],
    }


__all__ = [
    "CHANNEL_MODES",
    "CLASSES",
    "CONDITION_SCHEMA",
    "CONFIG_SCHEMA",
    "ContractError",
    "CREDIT_OPERATORS",
    "EPISODE_SCHEMA",
    "INHERITANCE_OPERATORS",
    "SELECTION_MODES",
    "SIGNALS",
    "SKILLS",
    "condition_registry",
    "deep_copy_json",
    "default_condition",
    "default_config",
    "default_initial_service",
    "default_machine_graph",
    "validate_condition",
    "validate_config",
]
