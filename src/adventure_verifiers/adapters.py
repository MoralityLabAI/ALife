"""Adapters from ALife event formats into canonical adventure envelopes."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .core import (
    ENVIRONMENT_SCHEMA,
    EVENT_SCHEMA,
    TASK_SCHEMA,
    TRACE_SCHEMA,
    canonical_sha256,
)


def _canonical_pixie_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": EVENT_SCHEMA,
        "event_id": str(event["event_id"]),
        "episode_id": str(event["episode_id"]),
        "tick": int(event["tick"]),
        "event_type": str(event["event_type"]),
        "position": [
            int(value)
            for value in event.get("position", event.get("visible_position", []))
        ],
        "action": event.get("action"),
        "details": dict(event.get("details", {})),
        "cause": [str(value) for value in event.get("cause", [])],
        "context": {
            key: event[key]
            for key in (
                "dimension",
                "intervention_depth",
                "critter",
                "pixie",
            )
            if key in event
        },
        "source_schema": str(event.get("schema", "unknown")),
    }


def adapt_pixie_episode(row: Mapping[str, Any]) -> dict[str, Any]:
    source_events = [dict(event) for event in row["events"]]
    events = [_canonical_pixie_event(event) for event in source_events]
    recorded = str(row.get("provenance", {}).get("events_sha256", ""))
    source_actual = canonical_sha256(source_events)
    return {
        "schema": ENVIRONMENT_SCHEMA,
        "environment_kind": str(row["schema"]),
        "episode_id": str(row["episode_id"]),
        "events": events,
        "events_sha256": canonical_sha256(events),
        "source_events_sha256": recorded or source_actual,
        "source_events_digest_valid": not recorded or recorded == source_actual,
        "replay_receipt": recorded or source_actual,
        "metadata": {
            "split": row.get("split"),
            "seed": row.get("seed"),
            "condition": dict(row.get("condition", {})),
        },
    }


def adapt_chronicle_events(
    source_events: Sequence[Mapping[str, Any]], *, replay_receipt: str
) -> dict[str, Any]:
    if not source_events:
        raise ValueError("chronicle adapter requires at least one event")
    episode_id = str(source_events[0]["episode_id"])
    id_by_sequence = {
        int(event["sequence"]): f"{episode_id}:chronicle:{int(event['sequence']):08d}"
        for event in source_events
    }
    events: list[dict[str, Any]] = []
    for source in source_events:
        causes = []
        for link in source.get("cause_chain", []):
            if "event_sequence" in link and int(link["event_sequence"]) in id_by_sequence:
                causes.append(id_by_sequence[int(link["event_sequence"])])
        events.append(
            {
                "schema": EVENT_SCHEMA,
                "event_id": id_by_sequence[int(source["sequence"])],
                "episode_id": episode_id,
                "tick": int(source["tick"]),
                "event_type": str(source["event_type"]),
                "position": [int(value) for value in source["position"]],
                "action": str(source["event_type"]),
                "details": dict(source.get("details", {})),
                "cause": causes,
                "context": {
                    "plane": source.get("plane"),
                    "region": source.get("region"),
                    "entities": [dict(value) for value in source.get("entities", [])],
                },
                "source_schema": str(source.get("schema", "unknown")),
            }
        )
    source_digest = canonical_sha256([dict(event) for event in source_events])
    return {
        "schema": ENVIRONMENT_SCHEMA,
        "environment_kind": "alife.chronicle",
        "episode_id": episode_id,
        "events": events,
        "events_sha256": canonical_sha256(events),
        "source_events_sha256": source_digest,
        "source_events_digest_valid": True,
        "replay_receipt": replay_receipt,
        "metadata": {"world_id": source_events[0].get("world_id")},
    }


def _descends_from(
    event_id: str, ancestor_id: str, event_by_id: Mapping[str, Mapping[str, Any]]
) -> bool:
    pending = list(event_by_id.get(event_id, {}).get("cause", []))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == ancestor_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(event_by_id.get(current, {}).get("cause", []))
    return False


def build_pixie_adventure(
    row: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build a valid reference adventure from a Pixie episode row."""

    environment = adapt_pixie_episode(row)
    events = environment["events"]
    event_by_id = {event["event_id"]: event for event in events}
    action_events = [event for event in events if event["event_type"] == "pixie_action"]
    initial_focus = 2 * len(action_events) + 2
    steps: list[dict[str, Any]] = []
    for index, receipt in enumerate(action_events):
        descendants = [
            event["event_id"]
            for event in events
            if event["tick"] >= receipt["tick"]
            and _descends_from(event["event_id"], receipt["event_id"], event_by_id)
        ]
        steps.append(
            {
                "index": index,
                "tick": receipt["tick"],
                "location": list(receipt["position"]),
                "action": {
                    "action_id": f"adventure-action-{index:04d}",
                    "type": str(receipt["action"]),
                    "parameters": {
                        "intervention_depth": receipt.get("context", {}).get(
                            "intervention_depth"
                        )
                    },
                    "cost": {"focus": 2},
                    "receipt_event_id": receipt["event_id"],
                },
                "observation_event_ids": [receipt["event_id"]],
                "outcome_event_ids": descendants,
            }
        )
    classified = next(event for event in events if event["event_type"] == "response_classified")
    resurfaced = next(
        (event for event in events if event["event_type"] == "response_resurfaced"), None
    )
    claims = [
        {
            "claim_id": "claim-response-class",
            "kind": "event_fact",
            "tick": classified["tick"],
            "fact_path": "details.response_class",
            "value": classified["details"]["response_class"],
            "evidence_event_ids": [classified["event_id"]],
        }
    ]
    if resurfaced is not None:
        claims.append(
            {
                "claim_id": "claim-resurfaced",
                "kind": "event_fact",
                "tick": resurfaced["tick"],
                "fact_path": "event_type",
                "value": "response_resurfaced",
                "evidence_event_ids": [resurfaced["event_id"]],
            }
        )
    location = list(action_events[0]["position"])
    task = {
        "schema": TASK_SCHEMA,
        "task_id": f"rescue-{row['episode_id']}",
        "environment_kind": environment["environment_kind"],
        "required_verifiers": [
            "trace_schema",
            "event_stream_integrity",
            "action_receipts",
            "causal_grounding",
            "route_continuity",
            "resource_ledger",
            "goal_completion",
            "claim_grounding",
        ],
        "diagnostic_verifiers": ["exploration_coverage", "response_diversity"],
        "goals": [
            {
                "goal_id": "classified",
                "kind": "event_count",
                "match": {"event_type": "response_classified"},
                "minimum": 1,
            },
            {
                "goal_id": "resurfaced",
                "kind": "event_count",
                "match": {"event_type": "response_resurfaced"},
                "minimum": 1,
            },
        ],
        "rules": {
            "action_costs": {str(action_events[0]["action"]): {"focus": 2}},
            "initial_resources": {"focus": initial_focus},
            "action_receipt_event_types": ["pixie_action"],
            "movement": {
                "shape": [8, 8],
                "start_location": location,
                "max_torus_manhattan_step": 0,
            },
        },
    }
    trace = {
        "schema": TRACE_SCHEMA,
        "adventure_id": f"adventure-{row['episode_id']}",
        "task_id": task["task_id"],
        "episode_id": environment["episode_id"],
        "environment_kind": environment["environment_kind"],
        "event_stream_sha256": environment["events_sha256"],
        "replay_receipt": environment["replay_receipt"],
        "steps": steps,
        "claims": claims,
        "final_resources": {"focus": initial_focus - 2 * len(action_events)},
    }
    return task, trace, environment
