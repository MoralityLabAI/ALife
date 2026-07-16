"""Core schemas and deterministic helpers for adventure verification."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


TASK_SCHEMA = "alife.adventure.task.v1"
TRACE_SCHEMA = "alife.adventure.trace.v1"
ENVIRONMENT_SCHEMA = "alife.adventure.environment.v1"
EVENT_SCHEMA = "alife.adventure.environment_event.v1"
RESULT_SCHEMA = "alife.adventure.verifier_result.v1"
SUITE_SCHEMA = "alife.adventure.verification_suite.v1"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def get_path(value: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def event_matches(event: Mapping[str, Any], match: Mapping[str, Any]) -> bool:
    for path, expected in match.items():
        exists, actual = get_path(event, str(path))
        if not exists or actual != expected:
            return False
    return True


def make_result(
    verifier_id: str,
    *,
    passed: bool,
    acceptance_eligible: bool,
    failures: Sequence[str] = (),
    facts: Sequence[Mapping[str, Any]] = (),
    metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "verifier_id": verifier_id,
        "version": "1",
        "acceptance_eligible": bool(acceptance_eligible),
        "passed": bool(passed),
        "failures": list(failures),
        "facts": [dict(item) for item in facts],
        "metrics": dict(metrics or {}),
    }


VerifierFunction = Callable[
    [Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], dict[str, Any]
]


@dataclass(frozen=True)
class VerifierSpec:
    verifier_id: str
    acceptance_eligible: bool
    description: str
    function: VerifierFunction


def validate_task_shape(task: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "task_id",
        "environment_kind",
        "required_verifiers",
        "diagnostic_verifiers",
        "goals",
        "rules",
    }
    missing = sorted(required - set(task))
    if missing:
        return ["missing task fields: " + ", ".join(missing)]
    if task.get("schema") != TASK_SCHEMA:
        errors.append(f"task.schema must be {TASK_SCHEMA}")
    for key in ("task_id", "environment_kind"):
        if not isinstance(task.get(key), str) or not task.get(key):
            errors.append(f"task.{key} must be a non-empty string")
    for key in ("required_verifiers", "diagnostic_verifiers", "goals"):
        if not isinstance(task.get(key), list):
            errors.append(f"task.{key} must be a list")
    if isinstance(task.get("required_verifiers"), list) and len(
        task["required_verifiers"]
    ) != len(set(task["required_verifiers"])):
        errors.append("task.required_verifiers contains duplicates")
    if set(task.get("required_verifiers", [])) & set(task.get("diagnostic_verifiers", [])):
        errors.append("hard and diagnostic verifier lists overlap")
    rules = task.get("rules")
    if not isinstance(rules, Mapping):
        errors.append("task.rules must be an object")
        return errors
    action_costs = rules.get("action_costs")
    initial = rules.get("initial_resources")
    movement = rules.get("movement")
    receipt_types = rules.get("action_receipt_event_types")
    gate_travel = rules.get("gate_travel")
    if not isinstance(action_costs, Mapping) or not action_costs:
        errors.append("task.rules.action_costs must be a non-empty object")
    else:
        for action, costs in action_costs.items():
            if not isinstance(action, str) or not isinstance(costs, Mapping):
                errors.append("each action cost must map an action name to an object")
                continue
            if any(not finite_number(value) or value < 0 for value in costs.values()):
                errors.append(f"action {action} has invalid resource costs")
    if not isinstance(initial, Mapping) or any(
        not finite_number(value) or value < 0 for value in initial.values()
    ):
        errors.append("task.rules.initial_resources must contain non-negative finite numbers")
    if not isinstance(receipt_types, list) or not all(
        isinstance(value, str) and value for value in receipt_types
    ):
        errors.append("task.rules.action_receipt_event_types must contain strings")
    if not isinstance(movement, Mapping):
        errors.append("task.rules.movement must be an object")
    else:
        shape = movement.get("shape")
        start = movement.get("start_location")
        if not isinstance(shape, list) or not shape or not all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in shape
        ):
            errors.append("movement.shape must contain positive integers")
        if not isinstance(start, list) or not all(
            isinstance(value, int) and not isinstance(value, bool) for value in start
        ):
            errors.append("movement.start_location must contain integers")
        if isinstance(shape, list) and isinstance(start, list) and len(shape) != len(start):
            errors.append("movement start and shape dimensionalities differ")
        max_step = movement.get("max_torus_manhattan_step")
        if not isinstance(max_step, int) or isinstance(max_step, bool) or max_step < 0:
            errors.append("movement.max_torus_manhattan_step must be non-negative")
        start_plane = movement.get("start_plane")
        if start_plane is not None and (
            not isinstance(start_plane, str) or not start_plane
        ):
            errors.append("movement.start_plane must be a non-empty string when present")
    if gate_travel is not None:
        if not isinstance(gate_travel, Mapping):
            errors.append("task.rules.gate_travel must be an object")
        else:
            for key in ("start_plane", "action_type"):
                if not isinstance(gate_travel.get(key), str) or not gate_travel.get(key):
                    errors.append(f"task.rules.gate_travel.{key} must be a non-empty string")
            for key in ("require_return", "require_positive_cooldown"):
                if not isinstance(gate_travel.get(key), bool):
                    errors.append(f"task.rules.gate_travel.{key} must be a boolean")
            for key in ("minimum_transfers", "minimum_cooldown_rejections"):
                value = gate_travel.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    errors.append(
                        f"task.rules.gate_travel.{key} must be a non-negative integer"
                    )
    for index, goal in enumerate(task.get("goals", [])):
        if not isinstance(goal, Mapping) or goal.get("kind") not in {
            "event_count",
            "visit_location",
            "claim_count",
        }:
            errors.append(f"task.goals[{index}] has an unknown kind")
    return errors


def validate_trace_shape(trace: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "adventure_id",
        "task_id",
        "episode_id",
        "environment_kind",
        "event_stream_sha256",
        "replay_receipt",
        "steps",
        "claims",
        "final_resources",
    }
    missing = sorted(required - set(trace))
    if missing:
        return ["missing trace fields: " + ", ".join(missing)]
    if trace.get("schema") != TRACE_SCHEMA:
        errors.append(f"trace.schema must be {TRACE_SCHEMA}")
    for key in (
        "adventure_id",
        "task_id",
        "episode_id",
        "environment_kind",
        "event_stream_sha256",
        "replay_receipt",
    ):
        if not isinstance(trace.get(key), str) or not trace.get(key):
            errors.append(f"trace.{key} must be a non-empty string")
    steps = trace.get("steps")
    if not isinstance(steps, list):
        errors.append("trace.steps must be a list")
    else:
        previous_tick = -1
        seen_actions: set[str] = set()
        for index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                errors.append(f"trace.steps[{index}] must be an object")
                continue
            if step.get("index") != index:
                errors.append(f"trace.steps[{index}].index must equal list position")
            tick = step.get("tick")
            if not isinstance(tick, int) or isinstance(tick, bool) or tick < previous_tick:
                errors.append(f"trace.steps[{index}].tick must be monotonic")
            elif isinstance(tick, int):
                previous_tick = tick
            location = step.get("location")
            if not isinstance(location, list) or not all(
                isinstance(value, int) and not isinstance(value, bool) for value in location
            ):
                errors.append(f"trace.steps[{index}].location must contain integers")
            if "plane" in step and (
                not isinstance(step.get("plane"), str) or not step.get("plane")
            ):
                errors.append(f"trace.steps[{index}].plane must be a non-empty string")
            action = step.get("action")
            if not isinstance(action, Mapping):
                errors.append(f"trace.steps[{index}].action must be an object")
                continue
            action_id = action.get("action_id")
            if not isinstance(action_id, str) or not action_id:
                errors.append(f"trace.steps[{index}].action.action_id is invalid")
            elif action_id in seen_actions:
                errors.append(f"duplicate action ID: {action_id}")
            else:
                seen_actions.add(action_id)
            for key in ("type", "receipt_event_id"):
                if not isinstance(action.get(key), str) or not action.get(key):
                    errors.append(f"trace.steps[{index}].action.{key} is invalid")
            if not isinstance(action.get("cost"), Mapping):
                errors.append(f"trace.steps[{index}].action.cost must be an object")
            if "parameters" in action and not isinstance(action.get("parameters"), Mapping):
                errors.append(f"trace.steps[{index}].action.parameters must be an object")
            for key in ("observation_event_ids", "outcome_event_ids"):
                if not isinstance(step.get(key), list) or not all(
                    isinstance(value, str) and value for value in step.get(key, [])
                ):
                    errors.append(f"trace.steps[{index}].{key} must contain IDs")
    claims = trace.get("claims")
    if not isinstance(claims, list):
        errors.append("trace.claims must be a list")
    else:
        seen_claims: set[str] = set()
        for index, claim in enumerate(claims):
            if not isinstance(claim, Mapping):
                errors.append(f"trace.claims[{index}] must be an object")
                continue
            claim_id = claim.get("claim_id")
            if not isinstance(claim_id, str) or not claim_id or claim_id in seen_claims:
                errors.append(f"trace.claims[{index}].claim_id is invalid or duplicate")
            else:
                seen_claims.add(claim_id)
            if claim.get("kind") not in {"event_fact", "event_count", "visited_location"}:
                errors.append(f"trace.claims[{index}].kind is unknown")
            if not isinstance(claim.get("tick"), int) or isinstance(claim.get("tick"), bool):
                errors.append(f"trace.claims[{index}].tick must be an integer")
            if not isinstance(claim.get("evidence_event_ids"), list):
                errors.append(f"trace.claims[{index}].evidence_event_ids must be a list")
    if not isinstance(trace.get("final_resources"), Mapping) or any(
        not finite_number(value) for value in trace.get("final_resources", {}).values()
    ):
        errors.append("trace.final_resources must contain finite numbers")
    return errors


def validate_environment_shape(environment: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "environment_kind",
        "episode_id",
        "events",
        "events_sha256",
        "source_events_sha256",
        "source_events_digest_valid",
        "replay_receipt",
    }
    missing = sorted(required - set(environment))
    if missing:
        return ["missing environment fields: " + ", ".join(missing)]
    if environment.get("schema") != ENVIRONMENT_SCHEMA:
        errors.append(f"environment.schema must be {ENVIRONMENT_SCHEMA}")
    if not isinstance(environment.get("events"), list):
        errors.append("environment.events must be a list")
    else:
        for index, event in enumerate(environment["events"]):
            if not isinstance(event, Mapping) or event.get("schema") != EVENT_SCHEMA:
                errors.append(f"environment.events[{index}] has the wrong schema")
                continue
            required_event = {
                "event_id",
                "episode_id",
                "tick",
                "event_type",
                "position",
                "action",
                "details",
                "cause",
                "context",
                "source_schema",
            }
            missing_event = sorted(required_event - set(event))
            if missing_event:
                errors.append(
                    f"environment.events[{index}] missing fields: "
                    + ", ".join(missing_event)
                )
                continue
            for key in ("event_id", "episode_id", "event_type", "source_schema"):
                if not isinstance(event.get(key), str) or not event.get(key):
                    errors.append(f"environment.events[{index}].{key} is invalid")
            if not isinstance(event.get("tick"), int) or isinstance(
                event.get("tick"), bool
            ) or int(event["tick"]) < 0:
                errors.append(f"environment.events[{index}].tick is invalid")
            if not isinstance(event.get("position"), list) or not all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in event.get("position", [])
            ):
                errors.append(f"environment.events[{index}].position is invalid")
            if event.get("action") is not None and not isinstance(
                event.get("action"), str
            ):
                errors.append(f"environment.events[{index}].action is invalid")
            if not isinstance(event.get("details"), Mapping) or not isinstance(
                event.get("context"), Mapping
            ):
                errors.append(f"environment.events[{index}] details/context is invalid")
            if not isinstance(event.get("cause"), list) or not all(
                isinstance(value, str) and value for value in event.get("cause", [])
            ):
                errors.append(f"environment.events[{index}].cause is invalid")
            try:
                canonical_json(event)
            except (TypeError, ValueError):
                errors.append(f"environment.events[{index}] is not finite JSON")
    return errors
