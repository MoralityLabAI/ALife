"""Reconstructed pure verification interface for archived v2 episodes."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


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


def _check(verifier_id: str, facts: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "facts": dict(facts or {}),
        "failures": [],
        "passed": True,
        "verifier_id": verifier_id,
    }


def _failure(check: dict[str, Any], message: str) -> None:
    check["failures"].append(message)
    check["passed"] = False


def verify_episode(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Recreate the accepted-record verifier receipt for a retained v2 episode.

    This compatibility implementation restores the historical output schema and
    independently recounts lifecycle/action exposure.  It does not claim to be
    the byte-identical lost v2 verifier.
    """

    config = episode["config"]
    exposure = episode["exposure"]
    generations = episode["generations"]
    rng = episode["rng"]
    receipts = rng.get("receipts", []) if isinstance(rng, Mapping) else []
    rng_map = rng if isinstance(rng, Mapping) else {}
    expected_resets = int(config["population_size"]) * int(config["cohorts"])
    checks: list[dict[str, Any]] = [
        _check("episode_schema"),
        _check(
            "deterministic_hashes",
            {
                "derived_deterministic_projection_sha256": episode[
                    "deterministic_projection_sha256"
                ],
                "derived_episode_sha256": episode["episode_sha256"],
            },
        ),
        _check("condition_semantics", {"condition_id": episode["condition"]["id"]}),
        _check(
            "stable_slot_lifecycle",
            {
                "expected_life_reset_acknowledgements": expected_resets,
                "life_reset_acknowledgements": int(
                    exposure["occupant_life_reset_acknowledgements"]
                ),
                "stable_slot_count": int(exposure["stable_slot_keys"]),
            },
        ),
        _check(
            "generation_action_accounting",
            {
                "actions": sum(int(row["action_count"]) for row in generations),
                "controller_reset_acknowledgements": sum(
                    int(row["controller_reset_acknowledgements"])
                    for row in generations
                ),
                "delivered_signals": sum(
                    int(row["delivered_signals"]) for row in generations
                ),
                "ecological_matched_noise_draws": sum(
                    int(row["ecological_matched_noise_draws"])
                    for row in generations
                ),
                "interactions": sum(
                    int(row["ecological_interactions"]) for row in generations
                ),
                "need_class_counts": {
                    key: sum(int(row["need_class_counts"][key]) for row in generations)
                    for key in ("C0", "C1", "C2", "C3")
                },
                "receiver_actions": sum(
                    int(row["receiver_actions"]) for row in generations
                ),
                "steps": len(generations),
            },
        ),
        _check("exposure_consistency"),
        _check("information_flow_containment"),
        _check("probe_firewall", {"checkpoint_count": len(episode["checkpoints"])}),
        _check(
            "rng_receipts",
            {"present": bool(receipts), "receipt_count": len(receipts)},
        ),
        _check("hazard_closure"),
    ]
    by_id = {row["verifier_id"]: row for row in checks}
    required_episode_fields = {
        "checkpoints",
        "claim_scope",
        "condition",
        "config",
        "controller",
        "deterministic_projection_sha256",
        "episode_id",
        "episode_sha256",
        "exposure",
        "external_policy_override",
        "generations",
        "hazards",
        "lifecycle_events",
        "possible_agents",
        "rng",
        "schema",
        "seed",
    }
    if not required_episode_fields.issubset(episode):
        missing = sorted(required_episode_fields - set(episode))
        _failure(by_id["episode_schema"], f"missing episode fields: {missing}")
    if episode.get("schema") != "alife.stegohive.integrated_episode.v2":
        _failure(by_id["episode_schema"], "unexpected integrated episode schema")
    slots = list(episode.get("possible_agents", []))
    expected_slots = [f"slot-{index:03d}" for index in range(int(config["population_size"]))]
    if slots != expected_slots:
        _failure(by_id["stable_slot_lifecycle"], "stable slot registry mismatch")
    lifecycle = list(episode.get("lifecycle_events", []))
    reset_count = sum(bool(row.get("life_reset")) for row in lifecycle)
    acknowledged_count = sum(
        bool(row.get("controller_reset_acknowledged")) for row in lifecycle
    )
    if reset_count != expected_resets or acknowledged_count != expected_resets:
        _failure(by_id["stable_slot_lifecycle"], "life-reset accounting mismatch")
    if int(exposure.get("occupant_life_reset_acknowledgements", -1)) != expected_resets:
        _failure(by_id["stable_slot_lifecycle"], "exposure reset count mismatch")

    summed_actions = sum(int(row.get("action_count", 0)) for row in generations)
    summed_interactions = sum(
        int(row.get("ecological_interactions", 0)) for row in generations
    )
    summed_delivered = sum(int(row.get("delivered_signals", 0)) for row in generations)
    summed_receiver_actions = sum(
        int(row.get("receiver_actions", 0)) for row in generations
    )
    if summed_actions != int(exposure.get("protocol_participate_actions", -1)):
        _failure(by_id["generation_action_accounting"], "protocol action total mismatch")
    if summed_interactions != int(exposure.get("ecological_interactions", -1)):
        _failure(by_id["generation_action_accounting"], "interaction total mismatch")
    if summed_delivered != int(exposure.get("delivered_signals", -1)):
        _failure(by_id["generation_action_accounting"], "delivered signal total mismatch")
    if summed_receiver_actions != int(exposure.get("receiver_actions", -1)):
        _failure(by_id["generation_action_accounting"], "receiver action total mismatch")
    if len(generations) != int(exposure.get("parallel_env_steps", -1)):
        _failure(by_id["generation_action_accounting"], "parallel step total mismatch")
    expected_steps = int(config["cohorts"]) * int(config["generations_per_cohort"])
    if len(generations) != expected_steps:
        _failure(by_id["exposure_consistency"], "configured generation count mismatch")
    need_counts = exposure.get("need_class_counts", {})
    for class_id in ("C0", "C1", "C2", "C3"):
        derived = sum(
            int(row.get("need_class_counts", {}).get(class_id, 0))
            for row in generations
        )
        if derived != int(need_counts.get(class_id, -1)):
            _failure(by_id["exposure_consistency"], f"{class_id} exposure mismatch")

    controller = episode.get("controller", {})
    if (
        episode.get("external_policy_override")
        or controller.get("external_policy_override")
        or not controller.get("stateless")
        or controller.get("action", {}).get("kind") != "protocol.participate"
    ):
        _failure(by_id["information_flow_containment"], "controller containment mismatch")
    checkpoints = list(episode.get("checkpoints", []))
    if any(
        row.get("fitness_feedback_enabled") or row.get("reproduction_enabled")
        for row in checkpoints
    ):
        _failure(by_id["probe_firewall"], "probe affected fitness or reproduction")
    probe_exposure = exposure.get("probes", {})
    if int(probe_exposure.get("checkpoints", -1)) != len(checkpoints):
        _failure(by_id["probe_firewall"], "checkpoint exposure mismatch")
    if probe_exposure.get("fitness_feedback_events") or probe_exposure.get(
        "reproduction_events"
    ):
        _failure(by_id["probe_firewall"], "probe firewall exposure is nonzero")
    hazards = episode.get("hazards", {})
    if any(value != 0 for value in hazards.values()):
        _failure(by_id["hazard_closure"], "one or more containment hazards are nonzero")

    # The lost runtime's projection function was not recovered, so retained
    # historical hashes are checked by detached bytecode.  Fresh reconstructed
    # runs identify their RNG explicitly and can be fully rehashed here.
    if rng_map.get("recovery_status") == "reconstructed_not_original_rng_key_sequence":
        reproduction_transitions = sum(
            bool(row.get("reproduction_enabled")) for row in generations
        )
        if reproduction_transitions != int(
            exposure.get("reproductive_transitions", -1)
        ):
            _failure(
                by_id["exposure_consistency"],
                "reproductive transition total mismatch",
            )
        archive_exposure = exposure.get("archive", {})
        derived_deposits = sum(
            int(row.get("archive_receipt", {}).get("deposits", 0))
            for row in generations
        )
        derived_wakes = sum(
            int(row.get("archive_receipt", {}).get("wakes", 0))
            for row in generations
        )
        if derived_deposits != int(archive_exposure.get("deposits", -1)):
            _failure(by_id["exposure_consistency"], "archive deposit total mismatch")
        if derived_wakes != int(archive_exposure.get("wakes", -1)):
            _failure(by_id["exposure_consistency"], "archive wake total mismatch")
        inheritance_exposure = exposure.get("inheritance", {})
        derived_children = sum(
            int(row.get("inheritance_receipt", {}).get("child_events", 0))
            for row in generations
        )
        if derived_children != int(inheritance_exposure.get("child_events", -1)):
            _failure(by_id["exposure_consistency"], "inheritance child total mismatch")
        derived_probe_trials = sum(int(row.get("trials", 0)) for row in checkpoints)
        if derived_probe_trials != int(probe_exposure.get("trials", -1)):
            _failure(by_id["probe_firewall"], "probe trial total mismatch")
        projection = {
            key: value
            for key, value in episode.items()
            if key not in {"deterministic_projection_sha256", "episode_sha256"}
        }
        derived_projection = canonical_sha256(projection)
        derived_episode = canonical_sha256(
            {key: value for key, value in episode.items() if key != "episode_sha256"}
        )
        by_id["deterministic_hashes"]["facts"] = {
            "derived_deterministic_projection_sha256": derived_projection,
            "derived_episode_sha256": derived_episode,
        }
        if derived_projection != episode.get("deterministic_projection_sha256"):
            _failure(by_id["deterministic_hashes"], "projection hash mismatch")
        if derived_episode != episode.get("episode_sha256"):
            _failure(by_id["deterministic_hashes"], "episode hash mismatch")
        if not isinstance(rng_map.get("draw_count"), int) or int(rng_map.get("draw_count", 0)) <= 0:
            _failure(by_id["rng_receipts"], "reconstructed RNG draw count is invalid")
        if not isinstance(rng_map.get("draws_sha256"), str) or len(rng_map["draws_sha256"]) != 64:
            _failure(by_id["rng_receipts"], "reconstructed RNG digest is invalid")
    failures = [
        f"{row['verifier_id']}: {message}"
        for row in checks
        for message in row["failures"]
    ]
    failed_checks = [row["verifier_id"] for row in checks if not row["passed"]]
    return {
        "accepted": not failures,
        "checks": checks,
        "episode_id": episode["episode_id"],
        "episode_sha256": episode["episode_sha256"],
        "external_io_performed": False,
        "failed_checks": failed_checks,
        "failures": failures,
        "schema": "alife.stegohive.integrated_episode_verification.v2",
        "simulator_imported_or_executed": False,
    }


__all__ = ["canonical_bytes", "canonical_sha256", "verify_episode"]
