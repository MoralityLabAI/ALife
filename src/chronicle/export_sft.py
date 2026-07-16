"""Export narration-ready, fact-constrained SFT JSONL records."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, TextIO

from .events import canonical_jsonl, read_events, validate_event, validate_stream
from .legends import LEGENDS_SCHEMA, compile_legends, validate_legends


SFT_SCHEMA = "alife.chronicle.sft.v1"


def _fact(
    fact_id: str,
    predicate: str,
    subject: str,
    value: Any,
    evidence: Iterable[int],
) -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "predicate": predicate,
        "subject": subject,
        "value": value,
        "evidence_event_sequences": sorted(set(int(item) for item in evidence)),
    }


def _biography_facts(
    biography: Mapping[str, Any], event_by_sequence: Mapping[int, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[int]]:
    entity_id = str(biography["entity_id"])
    facts: list[dict[str, Any]] = []
    sequences: list[int] = []
    birth_sequence = biography.get("birth_event_sequence")
    if isinstance(birth_sequence, int) and birth_sequence in event_by_sequence:
        birth_event = event_by_sequence[birth_sequence]
        sequences.append(birth_sequence)
        facts.extend(
            [
                _fact(
                    f"{entity_id}:birth:tick",
                    "born_at_tick",
                    entity_id,
                    birth_event["tick"],
                    [birth_sequence],
                ),
                _fact(
                    f"{entity_id}:birth:kind",
                    "born_as_kind",
                    entity_id,
                    birth_event["details"]["kind"],
                    [birth_sequence],
                ),
                _fact(
                    f"{entity_id}:birth:plane",
                    "born_in_plane",
                    entity_id,
                    birth_event["plane"],
                    [birth_sequence],
                ),
                _fact(
                    f"{entity_id}:birth:position",
                    "born_at_position",
                    entity_id,
                    birth_event["position"],
                    [birth_sequence],
                ),
            ]
        )
    parent_ids = (
        list(event_by_sequence[birth_sequence]["details"].get("parent_ids", []))
        if isinstance(birth_sequence, int) and birth_sequence in event_by_sequence
        else []
    )
    for index, parent_id in enumerate(parent_ids):
        if isinstance(birth_sequence, int):
            facts.append(
                _fact(
                    f"{entity_id}:parent:{index}",
                    "has_parent",
                    entity_id,
                    parent_id,
                    [birth_sequence],
                )
            )
    death_sequence = biography.get("death_event_sequence")
    if isinstance(death_sequence, int) and death_sequence in event_by_sequence:
        death_event = event_by_sequence[death_sequence]
        sequences.append(death_sequence)
        facts.extend(
            [
                _fact(
                    f"{entity_id}:death:tick",
                    "died_at_tick",
                    entity_id,
                    death_event["tick"],
                    [death_sequence],
                ),
                _fact(
                    f"{entity_id}:death:plane",
                    "died_in_plane",
                    entity_id,
                    death_event["plane"],
                    [death_sequence],
                ),
                _fact(
                    f"{entity_id}:death:cause",
                    "death_cause_chain",
                    entity_id,
                    death_event["cause_chain"],
                    [death_sequence],
                ),
            ]
        )
    for index, notable in enumerate(biography["notable_events"]):
        sequence = int(notable["sequence"])
        if sequence not in event_by_sequence:
            continue
        sequences.append(sequence)
        facts.append(
            _fact(
                f"{entity_id}:event:{index}",
                "participated_in_event",
                entity_id,
                event_by_sequence[sequence]["event_type"],
                [sequence],
            )
        )
    return facts, sorted(set(sequences))


def _chronicle_window_facts(
    events: list[dict[str, Any]], plane: str, region: str, window_index: int
) -> list[dict[str, Any]]:
    counts = Counter(event["event_type"] for event in events)
    facts: list[dict[str, Any]] = []
    subject = f"{plane}/{region}"
    for event_type, count in sorted(counts.items()):
        evidence = [event["sequence"] for event in events if event["event_type"] == event_type]
        facts.append(
            _fact(
                f"{subject}:window:{window_index}:{event_type}",
                "window_event_count",
                subject,
                {"event_type": event_type, "count": count},
                evidence,
            )
        )
    return facts


def _fact_contract_errors(record: Mapping[str, Any]) -> list[str]:
    """Re-derive the complete fact list from the visible event window."""

    errors: list[str] = []
    window = record.get("window")
    item = record.get("biography_or_chronicle")
    if not isinstance(window, list) or not window or not isinstance(item, Mapping):
        return errors
    typed_value = item.get("value")
    if not isinstance(typed_value, Mapping):
        return ["biography_or_chronicle.value must be an object"]
    event_by_sequence: dict[int, Mapping[str, Any]] = {}
    previous_sequence = -1
    for index, event in enumerate(window):
        if not isinstance(event, Mapping):
            errors.append(f"window[{index}] must be an event object")
            continue
        for error in validate_event(event):
            errors.append(f"window[{index}]: {error}")
        sequence = event.get("sequence")
        if not isinstance(sequence, int):
            continue
        if sequence <= previous_sequence:
            errors.append("window event sequences must be strictly increasing")
        previous_sequence = sequence
        if sequence in event_by_sequence:
            errors.append(f"duplicate window event sequence: {sequence}")
        event_by_sequence[sequence] = event
        if event.get("episode_id") != record.get("episode_id"):
            errors.append(f"window[{index}] episode_id differs from record")

    if errors:
        return errors

    expected: list[dict[str, Any]] = []
    if item.get("type") == "biography":
        entity_id = typed_value.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            return errors + ["biography entity_id must be a non-empty string"]
        try:
            expected, _ = _biography_facts(typed_value, event_by_sequence)
        except (KeyError, TypeError, ValueError) as exc:
            return errors + [f"biography fact derivation failed: {exc}"]
        birth_sequence = typed_value.get("birth_event_sequence")
        if isinstance(birth_sequence, int) and birth_sequence in event_by_sequence:
            birth = event_by_sequence[birth_sequence]
            subject_ids = [
                entity.get("id")
                for entity in birth.get("entities", [])
                if isinstance(entity, Mapping) and entity.get("role") == "subject"
            ]
            if birth.get("event_type") != "birth" or entity_id not in subject_ids:
                errors.append("biography birth_event_sequence does not identify its birth")
            lifespan = typed_value.get("lifespan")
            lineage = typed_value.get("lineage")
            if not isinstance(lifespan, Mapping) or lifespan.get("birth_tick") != birth.get("tick"):
                errors.append("biography birth tick differs from its birth event")
            if not isinstance(lineage, Mapping) or lineage.get("parent_ids") != birth.get(
                "details", {}
            ).get("parent_ids", []):
                errors.append("biography lineage differs from its birth event")
        death_sequence = typed_value.get("death_event_sequence")
        if isinstance(death_sequence, int) and death_sequence in event_by_sequence:
            death = event_by_sequence[death_sequence]
            subject_ids = [
                entity.get("id")
                for entity in death.get("entities", [])
                if isinstance(entity, Mapping) and entity.get("role") == "subject"
            ]
            if death.get("event_type") != "death" or entity_id not in subject_ids:
                errors.append("biography death_event_sequence does not identify its death")
            lifespan = typed_value.get("lifespan")
            if not isinstance(lifespan, Mapping) or lifespan.get("death_tick") != death.get("tick"):
                errors.append("biography death tick differs from its death event")
            if typed_value.get("cause_of_death") != death.get("cause_chain"):
                errors.append("biography death cause differs from its death event")
        for notable in typed_value.get("notable_events", []):
            if not isinstance(notable, Mapping):
                errors.append("biography notable_events must contain objects")
                continue
            sequence = notable.get("sequence")
            if not isinstance(sequence, int) or sequence not in event_by_sequence:
                continue
            event = event_by_sequence[sequence]
            if notable.get("event_type") != event.get("event_type"):
                errors.append("biography notable event type differs from evidence")
            if entity_id not in {
                entity.get("id")
                for entity in event.get("entities", [])
                if isinstance(entity, Mapping)
            }:
                errors.append("biography notable event does not contain the entity")
    elif item.get("type") == "chronicle":
        plane = typed_value.get("plane")
        region = typed_value.get("region")
        window_index = typed_value.get("window_index")
        if not isinstance(plane, str) or not isinstance(region, str):
            errors.append("chronicle plane and region must be strings")
        if not isinstance(window_index, int) or window_index < 0:
            errors.append("chronicle window_index must be a non-negative integer")
        if errors:
            return errors
        visible_events = [dict(event) for event in window if isinstance(event, Mapping)]
        if any(
            event.get("plane") != plane or event.get("region") != region
            for event in visible_events
        ):
            errors.append("chronicle window contains a different plane or region")
        era = typed_value.get("era")
        era_sequences = era.get("event_sequences", []) if isinstance(era, Mapping) else []
        if not set(event_by_sequence).issubset(set(era_sequences)):
            errors.append("chronicle window contains events outside its compiled era")
        expected = _chronicle_window_facts(
            visible_events, str(plane), str(region), int(window_index)
        )
    else:
        return errors

    if record.get("fact_list") != expected:
        errors.append("fact_list does not exactly match facts re-derived from window events")
    return errors


def validate_sft_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "record_id",
        "episode_id",
        "seed",
        "replay_receipt",
        "window",
        "biography_or_chronicle",
        "fact_list",
        "narration",
    }
    missing = sorted(required - set(record))
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
        return errors
    if record.get("schema") != SFT_SCHEMA:
        errors.append(f"schema must be {SFT_SCHEMA}")
    for key in ("record_id", "episode_id"):
        if not isinstance(record.get(key), str) or not record.get(key):
            errors.append(f"{key} must be a non-empty string")
    if record.get("narration") is not None:
        errors.append("narration must be null")
    if not isinstance(record.get("seed"), int):
        errors.append("seed must be an integer")
    if not isinstance(record.get("replay_receipt"), (str, Mapping)):
        errors.append("replay_receipt must be a receipt object or stable receipt ID")
    window = record.get("window")
    if not isinstance(window, list) or not window:
        errors.append("window must be a non-empty event list")
        sequences: set[int] = set()
    else:
        sequences = {
            int(event["sequence"])
            for event in window
            if isinstance(event, Mapping) and isinstance(event.get("sequence"), int)
        }
    facts = record.get("fact_list")
    if not isinstance(facts, list) or not facts:
        errors.append("fact_list must be a non-empty list")
    else:
        fact_ids: set[str] = set()
        for index, fact in enumerate(facts):
            if not isinstance(fact, Mapping):
                errors.append(f"fact_list[{index}] must be an object")
                continue
            fact_id = fact.get("fact_id")
            if not isinstance(fact_id, str) or not fact_id:
                errors.append(f"fact_list[{index}].fact_id must be non-empty")
            elif fact_id in fact_ids:
                errors.append(f"duplicate fact_id: {fact_id}")
            fact_ids.add(str(fact_id))
            evidence = fact.get("evidence_event_sequences")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"fact_list[{index}] must have event evidence")
            elif not set(int(value) for value in evidence).issubset(sequences):
                errors.append(f"fact_list[{index}] cites events outside its window")
    item = record.get("biography_or_chronicle")
    if not isinstance(item, Mapping) or item.get("type") not in {"biography", "chronicle"}:
        errors.append("biography_or_chronicle must be a typed compiler object")
    if not errors:
        errors.extend(_fact_contract_errors(record))
    return errors


def export_sft_records(
    event_source: str | Path | TextIO | Iterable[str] | Iterable[Mapping[str, Any]],
    *,
    seed: int,
    replay_receipt: Mapping[str, Any] | str,
    legends: Mapping[str, Any] | None = None,
    max_window_events: int = 64,
    max_biographies: int = 8,
) -> list[dict[str, Any]]:
    if max_window_events < 1:
        raise ValueError("max_window_events must be positive")
    if max_biographies < 0:
        raise ValueError("max_biographies must be non-negative")
    events = read_events(event_source)
    stream_errors = validate_stream(events)
    if stream_errors:
        raise ValueError("invalid event stream: " + "; ".join(stream_errors[:10]))
    compiled = dict(legends) if legends is not None else compile_legends(events)
    legend_errors = validate_legends(compiled)
    if legend_errors or compiled.get("schema") != LEGENDS_SCHEMA:
        raise ValueError("invalid legends: " + "; ".join(legend_errors))
    event_by_sequence = {event["sequence"]: event for event in events}
    episode_id = events[0]["episode_id"]
    records: list[dict[str, Any]] = []

    biographies = {item["entity_id"]: item for item in compiled["biographies"]}
    selected_ids = [row["entity_id"] for row in compiled["cast_index"][:max_biographies]]
    for entity_id in selected_ids:
        biography = biographies[entity_id]
        facts, sequences = _biography_facts(biography, event_by_sequence)
        if not facts:
            continue
        # Every fact remains visible: trim notable facts and their evidence together.
        allowed_sequences = set(sequences[:max_window_events])
        visible_facts = [
            fact
            for fact in facts
            if set(fact["evidence_event_sequences"]).issubset(allowed_sequences)
        ]
        window = [event_by_sequence[sequence] for sequence in sorted(allowed_sequences)]
        record = {
            "schema": SFT_SCHEMA,
            "record_id": f"{episode_id}:biography:{entity_id}",
            "episode_id": episode_id,
            "seed": int(seed),
            "replay_receipt": replay_receipt,
            "window": window,
            "biography_or_chronicle": {"type": "biography", "value": biography},
            "fact_list": visible_facts,
            "narration": None,
        }
        errors = validate_sft_record(record)
        if errors:
            raise RuntimeError("invalid SFT biography record: " + "; ".join(errors))
        records.append(record)

    for chronicle_index, chronicle in enumerate(compiled["chronicles"]):
        for era_index, era in enumerate(chronicle["eras"]):
            era_events = [event_by_sequence[value] for value in era["event_sequences"]]
            for offset in range(0, len(era_events), max_window_events):
                window = era_events[offset : offset + max_window_events]
                if not window:
                    continue
                window_index = offset // max_window_events
                facts = _chronicle_window_facts(
                    window, chronicle["plane"], chronicle["region"], window_index
                )
                record = {
                    "schema": SFT_SCHEMA,
                    "record_id": (
                        f"{episode_id}:chronicle:{chronicle_index}:era:{era_index}:window:{window_index}"
                    ),
                    "episode_id": episode_id,
                    "seed": int(seed),
                    "replay_receipt": replay_receipt,
                    "window": window,
                    "biography_or_chronicle": {
                        "type": "chronicle",
                        "value": {
                            "plane": chronicle["plane"],
                            "region": chronicle["region"],
                            "window_index": window_index,
                            "gate_flux_spike_rule": chronicle["gate_flux_spike_rule"],
                            "era": era,
                        },
                    },
                    "fact_list": facts,
                    "narration": None,
                }
                errors = validate_sft_record(record)
                if errors:
                    raise RuntimeError("invalid SFT chronicle record: " + "; ".join(errors))
                records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    parser.add_argument("--legends", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--replay-receipt", type=Path, required=True)
    parser.add_argument("--max-window-events", type=int, default=64)
    parser.add_argument("--max-biographies", type=int, default=8)
    args = parser.parse_args()
    legends = json.loads(args.legends.read_text(encoding="utf-8")) if args.legends else None
    receipt = json.loads(args.replay_receipt.read_text(encoding="utf-8"))
    records = export_sft_records(
        args.events,
        seed=args.seed,
        replay_receipt=receipt,
        legends=legends,
        max_window_events=args.max_window_events,
        max_biographies=args.max_biographies,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_jsonl(records))


if __name__ == "__main__":
    main()
