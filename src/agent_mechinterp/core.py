"""Typed capture, intervention, and editor-firewall primitives.

The fixed NumPy policy in this module is a wiring canary, not a cognitive model.
Its registered identity channels make the expected probe and intervention results
known in advance.  The public record format remains model-agnostic: another policy
only needs to expose named finite layers and ordered output logits.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import numpy as np

from alt_physics_atlas import (
    categories_for,
    initialize_states,
    normalized_entropy,
    state_digest,
)
from geometry_averaging_experiment import degree_matched_offsets
from pixie_sanctuary import active_mask, neighbor_agreement


DECISION_SCHEMA = "alife.agent_mechinterp.decision.v1"
PROPOSAL_SCHEMA = "alife.agent_mechinterp.edit_proposal.v1"
AUTHORIZATION_SCHEMA = "alife.agent_mechinterp.edit_authorization.v1"
EDIT_RECEIPT_SCHEMA = "alife.agent_mechinterp.edit_receipt.v1"
ROW_SCHEMA = "alife.agent_mechinterp.row.v1"
SUMMARY_SCHEMA = "alife.agent_mechinterp.summary.v1"
RECEIPT_SCHEMA = "alife.agent_mechinterp.campaign_receipt.v1"
CHECK_SCHEMA = "alife.agent_mechinterp.hard_checks.v1"

CRITTERS = ("bitlichen", "prism_wyrm", "mitosis_moss")
PLAY_ACTIONS = ("observe", "touch", "sing", "feed", "cool", "shield")
EDITOR_ACTIONS = (
    "bitlichen_density_up",
    "bitlichen_density_down",
    "prism_threshold_up",
    "prism_threshold_down",
    "moss_feed_up",
    "moss_feed_down",
)
PREFERRED_PLAY = {
    "bitlichen": "touch",
    "prism_wyrm": "sing",
    "mitosis_moss": "feed",
}
EDITOR_SPEC = {
    "bitlichen_density_up": ("bitlichen", "initial_alive_probability", 0.05),
    "bitlichen_density_down": ("bitlichen", "initial_alive_probability", -0.05),
    "prism_threshold_up": ("prism_wyrm", "successor_threshold", 1),
    "prism_threshold_down": ("prism_wyrm", "successor_threshold", -1),
    "moss_feed_up": ("mitosis_moss", "feed", 0.005),
    "moss_feed_down": ("mitosis_moss", "feed", -0.005),
}


class InstrumentedPolicy(Protocol):
    """Minimum adapter contract for a replayable policy decision."""

    policy_id: str

    def actions(self, mode: str) -> Sequence[str]: ...

    def forward(
        self, observation: Sequence[float], *, mode: str
    ) -> Mapping[str, Sequence[float]]: ...


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


def _record_hash(value: Mapping[str, Any], field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != field})


def _finite_vector(value: Any) -> bool:
    return isinstance(value, list) and value and all(
        isinstance(item, (int, float))
        and not isinstance(item, bool)
        and math.isfinite(float(item))
        for item in value
    )


def _primary_parameter(critter: str, profile: Mapping[str, Any]) -> float:
    key = {
        "bitlichen": "initial_alive_probability",
        "prism_wyrm": "successor_threshold",
        "mitosis_moss": "feed",
    }[critter]
    return float(profile[key])


def extract_observation(
    *,
    seed: int,
    critter: str,
    profile: Mapping[str, Any],
    side: int,
    matched_degree: int,
    parameter_bounds: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract a deterministic pre-action substrate observation."""

    if critter not in CRITTERS:
        raise ValueError(f"unknown critter: {critter}")
    shape = (int(side), int(side))
    state, _, initialization = initialize_states(
        str(profile["family"]), profile, shape, int(seed)
    )
    categories, category_count = categories_for(str(profile["family"]), state, profile)
    offsets = degree_matched_offsets(2, int(matched_degree))
    identity = [1.0 if item == critter else 0.0 for item in CRITTERS]
    rule = next(iter(parameter_bounds[critter].values()))
    minimum = float(rule["minimum"])
    maximum = float(rule["maximum"])
    parameter = _primary_parameter(critter, profile)
    normalized_parameter = (parameter - minimum) / (maximum - minimum)
    vector = identity + [
        float(np.mean(active_mask(critter, categories))),
        float(normalized_entropy(categories, category_count)),
        float(neighbor_agreement(categories, offsets)),
        float(normalized_parameter),
    ]
    return {
        "critter": critter,
        "seed": int(seed),
        "shape": [int(side), int(side)],
        "state_sha256": state_digest(categories),
        "profile_sha256": canonical_sha256(dict(profile)),
        "initialization": initialization,
        "feature_names": [
            "is_bitlichen",
            "is_prism_wyrm",
            "is_mitosis_moss",
            "active_fraction",
            "normalized_entropy",
            "neighbor_agreement",
            "normalized_primary_parameter",
        ],
        "vector": vector,
    }


@dataclass(frozen=True)
class CanaryPolicy:
    """Fixed instrumented policy with deliberately registered identity channels."""

    policy_id: str = "numpy-identity-canary-v1"

    def actions(self, mode: str) -> tuple[str, ...]:
        if mode == "play":
            return PLAY_ACTIONS
        if mode == "editor":
            return EDITOR_ACTIONS
        raise ValueError(f"unknown policy mode: {mode}")

    def forward(
        self,
        observation: Sequence[float],
        *,
        mode: str,
        zero_units: Sequence[int] = (),
        patch_identity: Sequence[float] | None = None,
    ) -> dict[str, list[float]]:
        values = np.asarray(observation, dtype=np.float64)
        if values.shape != (7,) or not np.all(np.isfinite(values)):
            raise ValueError("canary observation must contain seven finite values")
        hidden = values.copy()
        if patch_identity is not None:
            patch = np.asarray(patch_identity, dtype=np.float64)
            if patch.shape != (3,) or not np.all(np.isfinite(patch)):
                raise ValueError("identity patch must contain three finite values")
            hidden[:3] = patch
        for unit in zero_units:
            if not 0 <= int(unit) < hidden.size:
                raise ValueError(f"hidden unit out of range: {unit}")
            hidden[int(unit)] = 0.0
        logits = np.zeros(6, dtype=np.float64)
        if mode == "play":
            logits[1] = 4.0 * hidden[0]
            logits[2] = 4.0 * hidden[1]
            logits[3] = 4.0 * hidden[2]
        elif mode == "editor":
            logits[0] = 4.0 * hidden[0]
            logits[2] = 4.0 * hidden[1]
            logits[4] = 4.0 * hidden[2]
        else:
            raise ValueError(f"unknown policy mode: {mode}")
        # Continuous channels are captured but intentionally disconnected from
        # this canary's output. Learned policies need not share this structure.
        return {"hidden_1": hidden.tolist(), "logits": logits.tolist()}


def capture_decision(
    *,
    policy: InstrumentedPolicy,
    mode: str,
    split: str,
    seed: int,
    critter: str,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    outputs = policy.forward(observation["vector"], mode=mode)
    hidden = [float(value) for value in outputs["hidden_1"]]
    logits = [float(value) for value in outputs["logits"]]
    if not _finite_vector(hidden) or not _finite_vector(logits):
        raise ValueError("instrumented policy emitted a non-finite or empty layer")
    actions = list(policy.actions(mode))
    if len(actions) != len(logits):
        raise ValueError("action vocabulary and logit lengths differ")
    selected_index = int(np.argmax(np.asarray(logits)))
    record: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "decision_id": f"decision-{mode}-{split}-{seed}-{critter}",
        "policy_id": policy.policy_id,
        "mode": mode,
        "split": split,
        "seed": int(seed),
        "critter": critter,
        "observation": copy.deepcopy(dict(observation)),
        "actions": actions,
        "activations": {"hidden_1": hidden},
        "logits": logits,
        "selected_index": selected_index,
        "selected_action": actions[selected_index],
        "intervention": {"kind": "none"},
    }
    record["observation_sha256"] = canonical_sha256(record["observation"])
    record["activations_sha256"] = canonical_sha256(record["activations"])
    record["logits_sha256"] = canonical_sha256(record["logits"])
    record["decision_sha256"] = _record_hash(record, "decision_sha256")
    return record


def verify_decision(record: Mapping[str, Any], policy: InstrumentedPolicy) -> list[str]:
    errors: list[str] = []
    if record.get("schema") != DECISION_SCHEMA:
        errors.append("wrong decision schema")
    if record.get("policy_id") != policy.policy_id:
        errors.append("policy identifier mismatch")
    if canonical_sha256(record.get("observation")) != record.get("observation_sha256"):
        errors.append("observation hash mismatch")
    if canonical_sha256(record.get("activations")) != record.get("activations_sha256"):
        errors.append("activation hash mismatch")
    if canonical_sha256(record.get("logits")) != record.get("logits_sha256"):
        errors.append("logit hash mismatch")
    if _record_hash(record, "decision_sha256") != record.get("decision_sha256"):
        errors.append("decision record hash mismatch")
    observation = record.get("observation", {})
    vector = observation.get("vector") if isinstance(observation, Mapping) else None
    if not _finite_vector(vector):
        errors.append("observation vector is not finite")
        return errors
    try:
        expected = policy.forward(vector, mode=str(record.get("mode")))
        actions = list(policy.actions(str(record.get("mode"))))
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
        return errors
    expected_hidden = [float(value) for value in expected["hidden_1"]]
    expected_logits = [float(value) for value in expected["logits"]]
    if expected_hidden != record.get("activations", {}).get("hidden_1"):
        errors.append("captured activation does not match policy forward pass")
    if expected_logits != record.get("logits"):
        errors.append("captured logits do not match policy forward pass")
    if len(actions) != len(expected_logits):
        errors.append("action vocabulary and logit lengths differ")
        return errors
    selected_index = int(np.argmax(np.asarray(expected_logits)))
    if record.get("actions") != actions:
        errors.append("action vocabulary mismatch")
    if record.get("selected_index") != selected_index:
        errors.append("selected index mismatch")
    if record.get("selected_action") != actions[selected_index]:
        errors.append("selected action mismatch")
    if record.get("critter") != observation.get("critter"):
        errors.append("decision critter does not match observation")
    return errors


def build_editor_proposal(decision: Mapping[str, Any]) -> dict[str, Any]:
    action = str(decision["selected_action"])
    if action not in EDITOR_SPEC:
        raise ValueError(f"unknown editor action: {action}")
    target, path, delta = EDITOR_SPEC[action]
    parent = decision["observation"]
    # The exact old value is filled from the immutable parent profile by the caller.
    return {
        "schema": PROPOSAL_SCHEMA,
        "proposal_id": f"proposal-{decision['decision_id']}",
        "decision_id": decision["decision_id"],
        "target_critter": target,
        "path": path,
        "delta": delta,
        "old_value": None,
        "new_value": None,
        "parent_profile_sha256": parent["profile_sha256"],
    }


def authorize_edit(
    proposal: Mapping[str, Any],
    *,
    parent_profile: Mapping[str, Any],
    observed_critter: str,
    taxonomy: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    target = str(proposal.get("target_critter"))
    path = str(proposal.get("path"))
    allowlist = taxonomy.get("editor_allowlist", {})
    rule = allowlist.get(target, {}).get(path)
    if proposal.get("schema") != PROPOSAL_SCHEMA:
        errors.append("wrong proposal schema")
    if target != observed_critter:
        errors.append("proposal target does not match observed critter")
    if rule is None:
        errors.append("proposal path is not allowlisted")
    if canonical_sha256(dict(parent_profile)) != proposal.get("parent_profile_sha256"):
        errors.append("immutable parent profile hash mismatch")
    if path not in parent_profile:
        errors.append("parent profile does not contain proposal path")
    if not errors:
        old = parent_profile[path]
        delta = proposal.get("delta")
        new = proposal.get("new_value")
        if proposal.get("old_value") != old:
            errors.append("proposal old value does not match parent")
        if not isinstance(delta, (int, float)) or isinstance(delta, bool):
            errors.append("proposal delta is not numeric")
        elif not isinstance(new, (int, float)) or isinstance(new, bool):
            errors.append("proposal new value is not numeric")
        elif not math.isclose(float(new), float(old) + float(delta), abs_tol=1e-12):
            errors.append("proposal new value does not equal old plus delta")
        elif abs(float(delta)) > float(rule["max_absolute_delta"]) + 1e-12:
            errors.append("proposal exceeds maximum absolute delta")
        elif not float(rule["minimum"]) <= float(new) <= float(rule["maximum"]):
            errors.append("proposal is outside allowlisted bounds")
        elif rule.get("integer") and (
            not float(new).is_integer() or not float(delta).is_integer()
        ):
            errors.append("proposal requires integer value and delta")
    authorization: dict[str, Any] = {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_id": f"authorization-{proposal.get('proposal_id', 'unknown')}",
        "proposal_sha256": canonical_sha256(dict(proposal)),
        "authorized": not errors,
        "failures": errors,
        "gate_ids": ["editor_firewall"],
        "explicitly_excluded_gate_classes": [
            "mechanistic_evidence",
            "diagnostics",
        ],
    }
    authorization["authorization_sha256"] = _record_hash(
        authorization, "authorization_sha256"
    )
    return authorization


def apply_authorized_edit(
    proposal: Mapping[str, Any],
    authorization: Mapping[str, Any],
    parent_profile: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not authorization.get("authorized"):
        raise ValueError("cannot apply an unauthorized edit")
    if authorization.get("proposal_sha256") != canonical_sha256(dict(proposal)):
        raise ValueError("authorization does not match proposal")
    edited = copy.deepcopy(dict(parent_profile))
    path = str(proposal["path"])
    edited[path] = proposal["new_value"]
    receipt: dict[str, Any] = {
        "schema": EDIT_RECEIPT_SCHEMA,
        "proposal_sha256": canonical_sha256(dict(proposal)),
        "authorization_sha256": authorization["authorization_sha256"],
        "parent_profile_sha256": canonical_sha256(dict(parent_profile)),
        "edited_profile_sha256": canonical_sha256(edited),
        "changed_paths": [path],
        "old_value": parent_profile[path],
        "new_value": edited[path],
    }
    receipt["receipt_sha256"] = _record_hash(receipt, "receipt_sha256")
    return edited, receipt


def verify_authorization(
    authorization: Mapping[str, Any], taxonomy: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    if authorization.get("schema") != AUTHORIZATION_SCHEMA:
        errors.append("wrong authorization schema")
    if _record_hash(authorization, "authorization_sha256") != authorization.get(
        "authorization_sha256"
    ):
        errors.append("authorization hash mismatch")
    hard_ids = {str(item["id"]) for item in taxonomy.get("hard_checks", [])}
    diagnostics = set(map(str, taxonomy.get("diagnostics", [])))
    mechanistic = {
        str(item["id"]) for item in taxonomy.get("mechanistic_evidence", [])
    }
    gates = set(map(str, authorization.get("gate_ids", [])))
    invalid = gates - hard_ids
    if invalid:
        errors.append("authorization contains non-hard gates: " + ", ".join(sorted(invalid)))
    if gates & (diagnostics | mechanistic):
        errors.append("mechanistic evidence or diagnostics used for authorization")
    return errors


def verify_edit_receipt(
    proposal: Mapping[str, Any],
    authorization: Mapping[str, Any],
    parent_profile: Mapping[str, Any],
    edited_profile: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    path = str(proposal.get("path"))
    keys = set(parent_profile) | set(edited_profile)
    changed = sorted(key for key in keys if parent_profile.get(key) != edited_profile.get(key))
    if receipt.get("schema") != EDIT_RECEIPT_SCHEMA:
        errors.append("wrong edit receipt schema")
    if changed != [path] or receipt.get("changed_paths") != [path]:
        errors.append("edit did not change exactly the proposed path")
    if parent_profile.get(path) != proposal.get("old_value"):
        errors.append("receipt parent value mismatch")
    if edited_profile.get(path) != proposal.get("new_value"):
        errors.append("receipt edited value mismatch")
    expected = {
        "proposal_sha256": canonical_sha256(dict(proposal)),
        "authorization_sha256": authorization.get("authorization_sha256"),
        "parent_profile_sha256": canonical_sha256(dict(parent_profile)),
        "edited_profile_sha256": canonical_sha256(dict(edited_profile)),
        "old_value": parent_profile.get(path),
        "new_value": edited_profile.get(path),
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            errors.append(f"edit receipt {key} mismatch")
    if _record_hash(receipt, "receipt_sha256") != receipt.get("receipt_sha256"):
        errors.append("edit receipt hash mismatch")
    return errors


def completed_editor_proposal(
    decision: Mapping[str, Any], parent_profile: Mapping[str, Any]
) -> dict[str, Any]:
    proposal = build_editor_proposal(decision)
    path = str(proposal["path"])
    proposal["old_value"] = parent_profile[path]
    proposal["new_value"] = parent_profile[path] + proposal["delta"]
    return proposal


def verify_harness_row(
    row: Mapping[str, Any],
    *,
    policy: CanaryPolicy,
    taxonomy: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-derive every acceptance-eligible check from a retained row."""

    checks: dict[str, list[str]] = {
        "decision_integrity": verify_decision(row.get("decision", {}), policy),
        "action_link": [],
        "editor_firewall": [],
        "edit_receipt": [],
        "episode_replay": [],
        "authorization_firewall": [],
    }
    mode = row.get("mode")
    execution = row.get("execution", {})
    if row.get("schema") != ROW_SCHEMA:
        checks["decision_integrity"].append("wrong row schema")
    if mode == "play":
        selected = row.get("decision", {}).get("selected_action")
        receipts = execution.get("action_receipts", [])
        if not receipts or any(item != selected for item in receipts):
            checks["action_link"].append("selected play action does not match receipts")
        suite = execution.get("adventure_verification", {})
        if suite.get("accepted") is not True:
            checks["action_link"].append("adventure verification did not accept trace")
    elif mode == "editor":
        proposal = execution.get("proposal", {})
        parent = execution.get("parent_profile", {})
        edited = execution.get("edited_profile", {})
        authorization = execution.get("authorization", {})
        expected_auth = authorize_edit(
            proposal,
            parent_profile=parent,
            observed_critter=str(row.get("critter")),
            taxonomy=taxonomy,
        )
        if expected_auth.get("authorized") is not True:
            checks["editor_firewall"].extend(expected_auth.get("failures", []))
        if authorization.get("proposal_sha256") != expected_auth.get("proposal_sha256"):
            checks["editor_firewall"].append("stored authorization proposal mismatch")
        if authorization.get("authorized") is not True:
            checks["editor_firewall"].append("stored authorization is not affirmative")
        checks["edit_receipt"].extend(
            verify_edit_receipt(
                proposal,
                authorization,
                parent,
                edited,
                execution.get("edit_receipt", {}),
            )
        )
        checks["authorization_firewall"].extend(
            verify_authorization(authorization, taxonomy)
        )
    else:
        checks["decision_integrity"].append("unknown row mode")
    projection = execution.get("executed_projection")
    replay = execution.get("replay_projection")
    if canonical_sha256(projection) != execution.get("executed_projection_sha256"):
        checks["episode_replay"].append("executed projection hash mismatch")
    if canonical_sha256(replay) != execution.get("replay_projection_sha256"):
        checks["episode_replay"].append("replay projection hash mismatch")
    if canonical_sha256(projection) != canonical_sha256(replay):
        checks["episode_replay"].append("episode replay differs")
    if mode == "play" and not checks["authorization_firewall"]:
        # There is no editor authorization in play mode; the check is vacuous but
        # remains explicit for a fixed six-check matrix.
        checks["authorization_firewall"] = []
    passed = {key: not failures for key, failures in checks.items()}
    return {
        "schema": CHECK_SCHEMA,
        "passed": all(passed.values()),
        "checks": passed,
        "failures": checks,
        "acceptance_rule": "all structural hard checks pass; no diagnostic is eligible",
    }
