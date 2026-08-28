"""Recovered V6--V9 experiment-cell facades over the fresh V2 ecology."""

from __future__ import annotations

from typing import Any

from .analysis import derive_episode_analysis
from .environment import run_world
from .types import condition_registry, default_config, validate_config
from .verifiers import canonical_sha256, verify_episode


HIGH_RATE = 71 / 1175

VERSION_CELLS: dict[str, dict[str, dict[str, Any]]] = {
    "V6": {
        "A": {"arm": "F10", "population": 16, "generations": 8, "mutation_rate": HIGH_RATE},
        "B": {"arm": "F00", "population": 16, "generations": 8, "mutation_rate": HIGH_RATE},
        "C": {"arm": "F10", "population": 16, "generations": 8, "mutation_rate": HIGH_RATE / 2},
        "D": {"arm": "F10", "population": 8, "generations": 8, "mutation_rate": HIGH_RATE * 2},
        "E": {"arm": "F10", "population": 16, "generations": 12, "mutation_rate": 0.04},
    },
    "V7": {
        "G8_L": {"arm": "F10", "population": 16, "generations": 8, "mutation_rate": 0.04},
        "G8_H": {"arm": "F10", "population": 16, "generations": 8, "mutation_rate": HIGH_RATE},
        "G12_L": {"arm": "F10", "population": 16, "generations": 12, "mutation_rate": 0.04},
        "G12_H": {"arm": "F10", "population": 16, "generations": 12, "mutation_rate": HIGH_RATE},
    },
    "V8": {
        "E_E": {
            "arm": "F00",
            "reproduction_credit_mode": "encounter_local",
            "archive_credit_mode": "encounter_local",
        },
        "B_E": {
            "arm": "F10",
            "reproduction_credit_mode": "balanced_crossplay",
            "archive_credit_mode": "encounter_local",
        },
        "E_B": {
            "arm": "F00",
            "reproduction_credit_mode": "encounter_local",
            "archive_credit_mode": "balanced_crossplay",
        },
        "B_B": {
            "arm": "F10",
            "reproduction_credit_mode": "balanced_crossplay",
            "archive_credit_mode": "balanced_crossplay",
        },
    },
    "V9": {
        "E_E": {
            "arm": "F00",
            "archive_credit_mode": "encounter_local",
            "sender_parent_credit_mode": "encounter_local",
            "receiver_parent_credit_mode": "encounter_local",
        },
        "B_E": {
            "arm": "F10",
            "archive_credit_mode": "encounter_local",
            "sender_parent_credit_mode": "balanced_crossplay",
            "receiver_parent_credit_mode": "encounter_local",
        },
        "E_B": {
            "arm": "F10",
            "archive_credit_mode": "encounter_local",
            "sender_parent_credit_mode": "encounter_local",
            "receiver_parent_credit_mode": "balanced_crossplay",
        },
        "B_B": {
            "arm": "F10",
            "archive_credit_mode": "encounter_local",
            "sender_parent_credit_mode": "balanced_crossplay",
            "receiver_parent_credit_mode": "balanced_crossplay",
        },
    },
}


DEFAULT_CELLS = {"V6": "A", "V7": "G8_H", "V8": "B_B", "V9": "B_B"}


def cell_registry(version: str) -> dict[str, dict[str, Any]]:
    normalized = version.upper()
    if normalized not in VERSION_CELLS:
        raise ValueError(f"unsupported reconstructed experiment version: {version}")
    return {cell: dict(spec) for cell, spec in VERSION_CELLS[normalized].items()}


def run_spec(version: str, cell: str | None = None) -> dict[str, Any]:
    normalized = version.upper()
    cells = cell_registry(normalized)
    cell_id = DEFAULT_CELLS[normalized] if cell is None else cell
    if cell_id not in cells:
        raise ValueError(f"unknown {normalized} cell {cell_id!r}; choose from {sorted(cells)}")
    spec = dict(cells[cell_id])
    config = default_config()
    config.update(
        {
            "generations_per_cohort": int(spec.get("generations", 8)),
            "id": f"{normalized.lower()}-{cell_id.lower()}-reconstructed",
            "mutation_rate": float(spec.get("mutation_rate", HIGH_RATE)),
            "population_size": int(spec.get("population", 16)),
        }
    )
    config["archive"]["capacity"] = int(config["population_size"]) * 2
    config["archive"]["deposit_count"] = max(1, int(config["population_size"]) // 4)
    treatments = {
        key: value
        for key, value in spec.items()
        if key.endswith("_credit_mode")
    }
    return {
        "cell": cell_id,
        "condition": condition_registry()[spec["arm"]],
        "config": validate_config(config),
        "treatments": treatments,
        "version": normalized,
    }


def run_versioned_world(
    version: str, seed: int, cell: str | None = None
) -> dict[str, Any]:
    """Run one fresh reconstructed cell and return an analysis-ready envelope."""

    spec = run_spec(version, cell)
    episode = run_world(
        spec["config"],
        spec["condition"],
        seed,
        treatments=spec["treatments"],
    )
    analysis = derive_episode_analysis(episode)
    verifier = verify_episode(episode)
    identity = {
        "cell_id": spec["cell"],
        "condition_id": spec["cell"],
        "recovery_status": "fresh_reconstruction_not_historical_replay",
        "seed": seed,
        "version": spec["version"],
    }
    envelope = {
        "analysis": analysis,
        "episode": episode,
        "identity": identity,
        "schema": "alife.stegohive.reconstructed_versioned_record.v1",
        "treatments": spec["treatments"],
        "verifier": verifier,
    }
    envelope["record_sha256"] = canonical_sha256(envelope)
    return envelope


__all__ = [
    "DEFAULT_CELLS",
    "HIGH_RATE",
    "VERSION_CELLS",
    "cell_registry",
    "run_spec",
    "run_versioned_world",
]
