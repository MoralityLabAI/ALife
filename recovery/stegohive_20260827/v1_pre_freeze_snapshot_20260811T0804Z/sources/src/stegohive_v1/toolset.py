"""Machine-readable registry for the layered StegoHive gym surfaces."""

from __future__ import annotations

from typing import Any


def gym_toolset_card() -> dict[str, Any]:
    """Describe which layer may generate dynamics and which may support claims."""

    return {
        "schema": "alife.stegohive.toolset.v1",
        "claim_scope": "model_only",
        "tools": [
            {
                "id": "adaptive_signal_ecology",
                "entrypoint": "stegohive_v1.environment.run_world",
                "role": "selectable_and_heritable_dynamics",
                "evidence_authority": "none_during_training",
            },
            {
                "id": "frozen_causal_probes",
                "entrypoint": "stegohive_v1.analysis.derive_probe_evidence",
                "role": "post_training_causal_measurement",
                "evidence_authority": "registered_episode_qualification",
            },
            {
                "id": "typed_storyworld_deck",
                "entrypoint": "stegohive_v1.storyworld_tools.validate_storyworld_deck",
                "role": "optional_exogenous_regime_generator",
                "evidence_authority": "none",
            },
            {
                "id": "fictional_shell_fixture",
                "entrypoint": "stegohive.virtual_shell.VirtualShell",
                "role": "v0_hacking_game_and_trajectory_fixture",
                "evidence_authority": "mechanism_and_exposure_only",
            },
            {
                "id": "artifact_verifier",
                "entrypoint": "stegohive_v1.verifiers.verify_episode",
                "role": "integrity_and_boundary_audit",
                "evidence_authority": "artifact_acceptance_not_scientific_confirmation",
            },
        ],
        "separation_rules": [
            "storyworld cards cannot encode answers or alter evidence thresholds",
            "training fitness cannot read frozen-probe evidence metrics",
            "the fictional shell cannot invoke a host shell or network",
            "artifact integrity does not by itself establish emergence",
        ],
    }
