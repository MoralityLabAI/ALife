"""Composable hard and diagnostic verifiers for replay-grounded adventures."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

from .core import (
    SUITE_SCHEMA,
    VerifierSpec,
    canonical_sha256,
    event_matches,
    finite_number,
    get_path,
    make_result,
    validate_environment_shape,
    validate_task_shape,
    validate_trace_shape,
)


def _event_index(environment: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(event.get("event_id")): event
        for event in environment.get("events", [])
        if isinstance(event, Mapping) and isinstance(event.get("event_id"), str)
    }


def _is_descendant(
    event_id: str, ancestor_id: str, events: Mapping[str, Mapping[str, Any]]
) -> bool:
    pending = list(events.get(event_id, {}).get("cause", []))
    seen: set[str] = set()
    while pending:
        current = str(pending.pop())
        if current == ancestor_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(events.get(current, {}).get("cause", []))
    return False


def _trace_schema(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    failures = validate_trace_shape(trace)
    if trace.get("task_id") != task.get("task_id"):
        failures.append("trace task ID does not match task")
    if trace.get("episode_id") != environment.get("episode_id"):
        failures.append("trace episode ID does not match environment")
    if trace.get("environment_kind") != task.get("environment_kind"):
        failures.append("trace environment kind does not match task")
    if environment.get("environment_kind") != task.get("environment_kind"):
        failures.append("environment kind does not match task")
    return make_result(
        "trace_schema",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        facts=[{"step_count": len(trace.get("steps", [])), "claim_count": len(trace.get("claims", []))}],
    )


def _event_stream_integrity(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    del task
    failures = validate_environment_shape(environment)
    events = environment.get("events", [])
    try:
        actual_digest = canonical_sha256(events)
    except (TypeError, ValueError):
        actual_digest = "invalid"
        failures.append("canonical environment events are not finite JSON")
    if actual_digest != environment.get("events_sha256"):
        failures.append("canonical environment event digest mismatch")
    if trace.get("event_stream_sha256") != environment.get("events_sha256"):
        failures.append("trace event digest does not match environment")
    if trace.get("replay_receipt") != environment.get("replay_receipt"):
        failures.append("trace replay receipt does not match environment")
    if not environment.get("source_events_digest_valid"):
        failures.append("source event digest does not match its recorded provenance")
    event_by_id = _event_index(environment)
    if len(event_by_id) != len(events):
        failures.append("event IDs are missing or duplicated")
    for event_id, event in event_by_id.items():
        if event.get("episode_id") != environment.get("episode_id"):
            failures.append(f"event {event_id} belongs to another episode")
        tick = event.get("tick")
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            failures.append(f"event {event_id} has an invalid tick")
        causes = event.get("cause")
        if not isinstance(causes, list):
            failures.append(f"event {event_id} cause must be a list")
            continue
        for cause in causes:
            if cause not in event_by_id:
                failures.append(f"event {event_id} cites unknown cause {cause}")
            elif isinstance(tick, int) and isinstance(
                event_by_id[cause].get("tick"), int
            ) and int(event_by_id[cause]["tick"]) > tick:
                failures.append(f"event {event_id} cites future cause {cause}")
            elif _is_descendant(str(cause), event_id, event_by_id):
                failures.append(f"event causal graph contains a cycle through {event_id}")
    return make_result(
        "event_stream_integrity",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        facts=[{"event_count": len(events), "events_sha256": actual_digest}],
    )


def _action_receipts(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    failures: list[str] = []
    events = _event_index(environment)
    rules = task.get("rules", {})
    action_costs = rules.get("action_costs", {})
    receipt_types = set(rules.get("action_receipt_event_types", []))
    verified = 0
    for index, step in enumerate(trace.get("steps", [])):
        action = step.get("action", {})
        action_type = action.get("type")
        receipt_id = action.get("receipt_event_id")
        receipt = events.get(str(receipt_id))
        if action_type not in action_costs:
            failures.append(f"step {index} uses undeclared action {action_type}")
        if receipt is None:
            failures.append(f"step {index} action receipt is missing")
            continue
        if receipt.get("event_type") not in receipt_types:
            failures.append(f"step {index} receipt has a disallowed event type")
        if receipt.get("action") != action_type:
            failures.append(f"step {index} action does not match receipt")
        if receipt.get("tick") != step.get("tick"):
            failures.append(f"step {index} tick does not match receipt")
        if receipt.get("position") != step.get("location"):
            failures.append(f"step {index} location does not match receipt")
        if not failures or not any(message.startswith(f"step {index}") for message in failures):
            verified += 1
    return make_result(
        "action_receipts",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        metrics={"verified_actions": verified, "submitted_actions": len(trace.get("steps", []))},
    )


def _causal_grounding(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    del task
    failures: list[str] = []
    events = _event_index(environment)
    referenced = 0
    for index, step in enumerate(trace.get("steps", [])):
        action = step.get("action", {})
        receipt_id = str(action.get("receipt_event_id", ""))
        for event_id in step.get("observation_event_ids", []):
            referenced += 1
            event = events.get(str(event_id))
            if event is None:
                failures.append(f"step {index} observation cites unknown event {event_id}")
            elif int(event["tick"]) > int(step.get("tick", -1)):
                failures.append(f"step {index} observes future event {event_id}")
        for event_id in step.get("outcome_event_ids", []):
            referenced += 1
            event = events.get(str(event_id))
            if event is None:
                failures.append(f"step {index} outcome cites unknown event {event_id}")
            elif int(event["tick"]) < int(step.get("tick", -1)):
                failures.append(f"step {index} outcome predates its action")
            elif not _is_descendant(str(event_id), receipt_id, events):
                failures.append(f"step {index} outcome is not caused by its action receipt")
    for index, claim in enumerate(trace.get("claims", [])):
        claim_tick = int(claim.get("tick", -1))
        for event_id in claim.get("evidence_event_ids", []):
            referenced += 1
            event = events.get(str(event_id))
            if event is None:
                failures.append(f"claim {index} cites unknown event {event_id}")
            elif int(event["tick"]) > claim_tick:
                failures.append(f"claim {index} cites future evidence {event_id}")
    return make_result(
        "causal_grounding",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        metrics={"referenced_event_count": referenced},
    )


def _route_continuity(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    del environment
    failures: list[str] = []
    movement = task.get("rules", {}).get("movement", {})
    shape = movement.get("shape", [])
    previous = movement.get("start_location", [])
    max_step = int(movement.get("max_torus_manhattan_step", 0))
    total_distance = 0
    for index, step in enumerate(trace.get("steps", [])):
        location = step.get("location", [])
        if len(location) != len(shape):
            failures.append(f"step {index} route dimensionality is invalid")
            continue
        if any(value < 0 or value >= side for value, side in zip(location, shape)):
            failures.append(f"step {index} location is outside the declared torus")
            continue
        distance = sum(
            min(abs(value - origin), side - abs(value - origin))
            for value, origin, side in zip(location, previous, shape)
        )
        total_distance += distance
        if distance > max_step:
            failures.append(f"step {index} route jump {distance} exceeds {max_step}")
        previous = location
    return make_result(
        "route_continuity",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        metrics={"total_torus_manhattan_distance": total_distance},
    )


def _resource_ledger(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    del environment
    failures: list[str] = []
    rules = task.get("rules", {})
    expected = {key: float(value) for key, value in rules.get("initial_resources", {}).items()}
    costs = rules.get("action_costs", {})
    for index, step in enumerate(trace.get("steps", [])):
        action = step.get("action", {})
        action_type = action.get("type")
        declared = costs.get(action_type)
        submitted = action.get("cost")
        if not isinstance(declared, Mapping) or not isinstance(submitted, Mapping):
            failures.append(f"step {index} has no comparable resource cost")
            continue
        if dict(submitted) != dict(declared):
            failures.append(f"step {index} submitted cost differs from task cost")
        for resource, amount in declared.items():
            expected[resource] = expected.get(resource, 0.0) - float(amount)
            if expected[resource] < -1e-12:
                failures.append(f"step {index} overspends {resource}")
    submitted_final = trace.get("final_resources", {})
    if set(submitted_final) != set(expected):
        failures.append("final resource keys do not match the task ledger")
    for resource, amount in expected.items():
        if not finite_number(submitted_final.get(resource)) or abs(
            float(submitted_final.get(resource, math.inf)) - amount
        ) > 1e-9:
            failures.append(f"final resource mismatch for {resource}")
    return make_result(
        "resource_ledger",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        facts=[{"expected_final_resources": expected}],
    )


def _goal_completion(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    failures: list[str] = []
    facts: list[dict[str, Any]] = []
    events = environment.get("events", [])
    for index, goal in enumerate(task.get("goals", [])):
        kind = goal.get("kind")
        goal_id = str(goal.get("goal_id", f"goal-{index}"))
        achieved = False
        observed: Any = None
        if kind == "event_count":
            count = sum(event_matches(event, goal.get("match", {})) for event in events)
            minimum = int(goal.get("minimum", 1))
            achieved = count >= minimum
            observed = count
        elif kind == "visit_location":
            target = goal.get("location")
            count = sum(step.get("location") == target for step in trace.get("steps", []))
            achieved = count >= int(goal.get("minimum", 1))
            observed = count
        elif kind == "claim_count":
            count = sum(
                all(claim.get(key) == value for key, value in goal.get("match", {}).items())
                for claim in trace.get("claims", [])
            )
            achieved = count >= int(goal.get("minimum", 1))
            observed = count
        facts.append({"goal_id": goal_id, "achieved": achieved, "observed": observed})
        if not achieved:
            failures.append(f"goal {goal_id} was not completed")
    return make_result(
        "goal_completion",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        facts=facts,
    )


def _claim_grounding(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    del task
    failures: list[str] = []
    facts: list[dict[str, Any]] = []
    events = _event_index(environment)
    for index, claim in enumerate(trace.get("claims", [])):
        kind = claim.get("kind")
        claim_id = str(claim.get("claim_id", f"claim-{index}"))
        evidence_ids = claim.get("evidence_event_ids", [])
        grounded = False
        if kind == "event_fact" and len(evidence_ids) == 1 and evidence_ids[0] in events:
            exists, actual = get_path(events[evidence_ids[0]], str(claim.get("fact_path", "")))
            grounded = exists and actual == claim.get("value")
        elif kind == "event_count":
            selected = [events[event_id] for event_id in evidence_ids if event_id in events]
            grounded = (
                len(selected) == len(evidence_ids)
                and all(event_matches(event, claim.get("match", {})) for event in selected)
                and len(selected) == claim.get("value")
            )
        elif kind == "visited_location":
            grounded = (
                not evidence_ids
                and sum(
                    step.get("location") == claim.get("location")
                    for step in trace.get("steps", [])
                )
                == claim.get("value")
            )
        facts.append({"claim_id": claim_id, "grounded": grounded})
        if not grounded:
            failures.append(f"claim {claim_id} is not derivable from its evidence")
    return make_result(
        "claim_grounding",
        passed=not failures,
        acceptance_eligible=True,
        failures=failures,
        facts=facts,
    )


def _exploration_coverage(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    del task
    positions = {tuple(step.get("location", [])) for step in trace.get("steps", [])}
    event_types = {str(event.get("event_type")) for event in environment.get("events", [])}
    return make_result(
        "exploration_coverage",
        passed=True,
        acceptance_eligible=False,
        metrics={
            "unique_visited_locations": len(positions),
            "observed_environment_event_types": len(event_types),
        },
    )


def _response_diversity(
    task: Mapping[str, Any], trace: Mapping[str, Any], environment: Mapping[str, Any]
) -> dict[str, Any]:
    del task, trace
    counts = Counter(str(event.get("event_type")) for event in environment.get("events", []))
    return make_result(
        "response_diversity",
        passed=True,
        acceptance_eligible=False,
        metrics={"event_type_counts": dict(sorted(counts.items()))},
    )


VERIFIER_SPECS: dict[str, VerifierSpec] = {
    spec.verifier_id: spec
    for spec in (
        VerifierSpec("trace_schema", True, "Validate typed task/trace identity and structure.", _trace_schema),
        VerifierSpec("event_stream_integrity", True, "Validate event hashes, provenance, IDs, and causal graph.", _event_stream_integrity),
        VerifierSpec("action_receipts", True, "Match every submitted action to an environment receipt.", _action_receipts),
        VerifierSpec("causal_grounding", True, "Reject future, fabricated, or causally unrelated evidence.", _causal_grounding),
        VerifierSpec("route_continuity", True, "Check bounded toroidal movement.", _route_continuity),
        VerifierSpec("resource_ledger", True, "Recompute exact action costs and final resources.", _resource_ledger),
        VerifierSpec("goal_completion", True, "Derive declared task goals from events, visits, or claims.", _goal_completion),
        VerifierSpec("claim_grounding", True, "Derive atomic adventurer claims from cited evidence.", _claim_grounding),
        VerifierSpec("exploration_coverage", False, "Diagnostic location and event-type coverage.", _exploration_coverage),
        VerifierSpec("response_diversity", False, "Diagnostic response-type distribution.", _response_diversity),
    )
}


def verify_adventure(
    task: Mapping[str, Any],
    trace: Mapping[str, Any],
    environment: Mapping[str, Any],
    *,
    extra_verifiers: Mapping[str, VerifierSpec] | None = None,
) -> dict[str, Any]:
    configuration_errors = validate_task_shape(task)
    registry = dict(VERIFIER_SPECS)
    for verifier_id, spec in (extra_verifiers or {}).items():
        if verifier_id in registry:
            configuration_errors.append(
                f"custom verifier cannot override built-in verifier: {verifier_id}"
            )
            continue
        if verifier_id != spec.verifier_id:
            configuration_errors.append(
                f"custom verifier key does not match its spec: {verifier_id}"
            )
            continue
        registry[verifier_id] = spec
    required = list(task.get("required_verifiers", []))
    diagnostics = list(task.get("diagnostic_verifiers", []))
    requested = required + diagnostics
    for verifier_id in requested:
        spec = registry.get(str(verifier_id))
        if spec is None:
            configuration_errors.append(f"unknown verifier: {verifier_id}")
        elif verifier_id in required and not spec.acceptance_eligible:
            configuration_errors.append(
                f"diagnostic verifier cannot be an acceptance gate: {verifier_id}"
            )
        elif verifier_id in diagnostics and spec.acceptance_eligible:
            configuration_errors.append(
                f"hard verifier must remain in required_verifiers: {verifier_id}"
            )
    results = [
        registry[verifier_id].function(task, trace, environment)
        for verifier_id in requested
        if verifier_id in registry
    ]
    result_by_id = {result["verifier_id"]: result for result in results}
    accepted = not configuration_errors and all(
        result_by_id.get(verifier_id, {}).get("passed") is True
        for verifier_id in required
    )
    return {
        "schema": SUITE_SCHEMA,
        "task_id": task.get("task_id"),
        "adventure_id": trace.get("adventure_id"),
        "episode_id": trace.get("episode_id"),
        "accepted": accepted,
        "configuration_errors": configuration_errors,
        "required_verifiers": required,
        "diagnostic_verifiers": diagnostics,
        "results": results,
        "failed_required_verifiers": [
            verifier_id
            for verifier_id in required
            if result_by_id.get(verifier_id, {}).get("passed") is not True
        ],
        "acceptance_rule": "all declared hard verifiers pass; diagnostics are ineligible",
    }
