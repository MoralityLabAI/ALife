"""Pure legends-mode compilation over chronicle JSONL events."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, TextIO

from .events import read_events, validate_stream


LEGENDS_SCHEMA = "alife.chronicle.legends.v1"


def _entity_profiles(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for event in events:
        for entity in event["entities"]:
            entity_id = entity["id"]
            profile = profiles.setdefault(
                entity_id,
                {
                    "entity_id": entity_id,
                    "kind": entity.get("kind", "unknown"),
                    "species": entity.get("species"),
                },
            )
            if profile["kind"] == "unknown" and entity.get("kind"):
                profile["kind"] = entity["kind"]
            if entity.get("species") is not None:
                profile["species"] = entity["species"]
    return profiles


def _compile_biographies(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles = _entity_profiles(events)
    involvement: dict[str, list[dict[str, Any]]] = defaultdict(list)
    births: dict[str, dict[str, Any]] = {}
    deaths: dict[str, dict[str, Any]] = {}
    lineage: dict[str, list[str]] = defaultdict(list)
    planes: dict[str, set[str]] = defaultdict(set)
    positions: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for event in events:
        seen: set[str] = set()
        for entity in event["entities"]:
            entity_id = entity["id"]
            planes[entity_id].add(event["plane"])
            if entity_id not in seen:
                positions[entity_id].append(
                    {
                        "tick": event["tick"],
                        "plane": event["plane"],
                        "region": event["region"],
                        "position": event["position"],
                    }
                )
                involvement[entity_id].append(
                    {
                        "sequence": event["sequence"],
                        "tick": event["tick"],
                        "event_type": event["event_type"],
                        "plane": event["plane"],
                        "region": event["region"],
                        "role": entity["role"],
                    }
                )
                seen.add(entity_id)
        if event["event_type"] == "birth" and event["entities"]:
            subject = event["entities"][0]["id"]
            births.setdefault(subject, event)
            lineage[subject] = list(event["details"].get("parent_ids", []))
        if event["event_type"] == "death" and event["entities"]:
            deaths[event["entities"][0]["id"]] = event

    biographies: list[dict[str, Any]] = []
    for entity_id in sorted(profiles):
        birth = births.get(entity_id)
        death = deaths.get(entity_id)
        events_for_entity = involvement[entity_id]
        first_tick = birth["tick"] if birth is not None else min(item["tick"] for item in events_for_entity)
        last_tick = death["tick"] if death is not None else max(item["tick"] for item in events_for_entity)
        biographies.append(
            {
                **profiles[entity_id],
                "lifespan": {
                    "birth_tick": birth["tick"] if birth is not None else None,
                    "death_tick": death["tick"] if death is not None else None,
                    "observed_first_tick": first_tick,
                    "observed_last_tick": last_tick,
                    "duration_ticks": last_tick - first_tick,
                    "status": "dead" if death is not None else "alive_or_unobserved",
                },
                "lineage": {"parent_ids": lineage[entity_id]},
                "planes": sorted(planes[entity_id]),
                "position_history": positions[entity_id],
                "notable_events": [
                    item
                    for item in events_for_entity
                    if item["event_type"] not in {"birth", "death"}
                ],
                "cause_of_death": death["cause_chain"] if death is not None else None,
                "birth_event_sequence": birth["sequence"] if birth is not None else None,
                "death_event_sequence": death["sequence"] if death is not None else None,
            }
        )
    return biographies


def _gate_spike_ticks(events: list[dict[str, Any]]) -> tuple[list[int], int]:
    counts = Counter(
        event["tick"] for event in events if event["event_type"] == "gate_transfer"
    )
    if not counts:
        return [], 1
    values = list(counts.values())
    threshold = max(
        1,
        int(math.ceil(statistics.mean(values) + statistics.pstdev(values))),
    )
    return sorted(tick for tick, count in counts.items() if count >= threshold), threshold


def _era_summary(
    events: list[dict[str, Any]], start_tick: int, end_tick: int, *, spike_at_end: bool
) -> dict[str, Any]:
    selected = [event for event in events if start_tick <= event["tick"] <= end_tick]
    counts = Counter(event["event_type"] for event in selected)
    births = Counter(
        str(event["details"].get("kind", "unknown"))
        for event in selected
        if event["event_type"] == "birth"
    )
    deaths = Counter(
        str(event["details"].get("kind", "unknown"))
        for event in selected
        if event["event_type"] == "death"
    )
    entity_ids = sorted(
        {entity["id"] for event in selected for entity in event["entities"]}
    )
    return {
        "start_tick": start_tick,
        "end_tick": end_tick,
        "gate_flux_spike_at_end": spike_at_end,
        "event_count": len(selected),
        "event_counts": dict(sorted(counts.items())),
        "births_by_kind": dict(sorted(births.items())),
        "deaths_by_kind": dict(sorted(deaths.items())),
        "entity_ids": entity_ids,
        "event_sequences": [event["sequence"] for event in selected],
    }


def _compile_chronicles(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[(event["plane"], event["region"])].append(event)

    chronicles: list[dict[str, Any]] = []
    for plane, region in sorted(grouped):
        group = grouped[(plane, region)]
        min_tick = min(event["tick"] for event in group)
        max_tick = max(event["tick"] for event in group)
        spike_ticks, threshold = _gate_spike_ticks(group)
        eras: list[dict[str, Any]] = []
        start = min_tick
        for spike_tick in spike_ticks:
            if spike_tick < start:
                continue
            eras.append(_era_summary(group, start, spike_tick, spike_at_end=True))
            start = spike_tick + 1
        if start <= max_tick or not eras:
            eras.append(_era_summary(group, start, max_tick, spike_at_end=False))
        chronicles.append(
            {
                "plane": plane,
                "region": region,
                "tick_range": [min_tick, max_tick],
                "gate_flux_spike_rule": {
                    "definition": "per-tick gate transfers >= ceil(mean + population_stdev), minimum 1",
                    "threshold": threshold,
                    "spike_ticks": spike_ticks,
                },
                "eras": eras,
            }
        )
    return chronicles


def _compile_cast_index(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles = _entity_profiles(events)
    participation = Counter()
    event_types: dict[str, set[str]] = defaultdict(set)
    neighbors: dict[str, set[str]] = defaultdict(set)
    for event in events:
        ids = sorted({entity["id"] for entity in event["entities"]})
        for entity_id in ids:
            participation[entity_id] += 1
            event_types[entity_id].add(event["event_type"])
            neighbors[entity_id].update(other for other in ids if other != entity_id)
    rows = []
    for entity_id in profiles:
        score = (
            float(participation[entity_id])
            + 0.25 * len(neighbors[entity_id])
            + 0.10 * len(event_types[entity_id])
        )
        rows.append(
            {
                **profiles[entity_id],
                "centrality": round(score, 6),
                "event_participation": participation[entity_id],
                "unique_coentities": len(neighbors[entity_id]),
                "event_type_count": len(event_types[entity_id]),
            }
        )
    rows.sort(key=lambda row: (-row["centrality"], row["entity_id"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def validate_legends(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema") != LEGENDS_SCHEMA:
        errors.append(f"schema must be {LEGENDS_SCHEMA}")
    for key in ("episode_id", "world_id"):
        if not isinstance(value.get(key), str) or not value.get(key):
            errors.append(f"{key} must be a non-empty string")
    for key in ("biographies", "chronicles", "cast_index"):
        if not isinstance(value.get(key), list):
            errors.append(f"{key} must be a list")
    if not isinstance(value.get("event_count"), int) or int(value.get("event_count", -1)) < 0:
        errors.append("event_count must be a non-negative integer")
    entity_ids: set[str] = set()
    for index, biography in enumerate(value.get("biographies", [])):
        if not isinstance(biography, Mapping):
            errors.append(f"biographies[{index}] must be an object")
            continue
        entity_id = biography.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            errors.append(f"biographies[{index}].entity_id must be non-empty")
        elif entity_id in entity_ids:
            errors.append(f"duplicate biography entity_id: {entity_id}")
        entity_ids.add(str(entity_id))
        if not isinstance(biography.get("lifespan"), Mapping):
            errors.append(f"biographies[{index}].lifespan must be an object")
        if not isinstance(biography.get("lineage"), Mapping) or not isinstance(
            biography.get("lineage", {}).get("parent_ids"), list
        ):
            errors.append(f"biographies[{index}].lineage.parent_ids must be a list")
        if not isinstance(biography.get("notable_events"), list):
            errors.append(f"biographies[{index}].notable_events must be a list")
    for index, chronicle in enumerate(value.get("chronicles", [])):
        if not isinstance(chronicle, Mapping):
            errors.append(f"chronicles[{index}] must be an object")
            continue
        for key in ("plane", "region"):
            if not isinstance(chronicle.get(key), str) or not chronicle.get(key):
                errors.append(f"chronicles[{index}].{key} must be non-empty")
        eras = chronicle.get("eras")
        if not isinstance(eras, list) or not eras:
            errors.append(f"chronicles[{index}].eras must be a non-empty list")
        else:
            for era_index, era in enumerate(eras):
                if not isinstance(era, Mapping) or not isinstance(
                    era.get("event_sequences"), list
                ):
                    errors.append(
                        f"chronicles[{index}].eras[{era_index}] must contain event_sequences"
                    )
    ranks = [row.get("rank") for row in value.get("cast_index", []) if isinstance(row, Mapping)]
    if ranks and ranks != list(range(1, len(ranks) + 1)):
        errors.append("cast_index ranks must be contiguous")
    return errors


def compile_legends(
    source: str | Path | TextIO | Iterable[str] | Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compile biographies, plane/region eras, and cast centrality from JSONL only."""

    events = read_events(source)
    errors = validate_stream(events)
    if errors:
        raise ValueError("invalid event stream: " + "; ".join(errors[:10]))
    if not events:
        raise ValueError("cannot compile an empty event stream")
    result = {
        "schema": LEGENDS_SCHEMA,
        "episode_id": events[0]["episode_id"],
        "world_id": events[0]["world_id"],
        "event_schema": events[0]["schema"],
        "event_count": len(events),
        "biographies": _compile_biographies(events),
        "chronicles": _compile_chronicles(events),
        "cast_centrality_method": "event_participation + 0.25*unique_coentities + 0.10*event_type_count",
        "cast_centrality_is_diagnostic": True,
        "cast_index": _compile_cast_index(events),
    }
    legend_errors = validate_legends(result)
    if legend_errors:
        raise RuntimeError("compiled legends invalid: " + "; ".join(legend_errors))
    return result
