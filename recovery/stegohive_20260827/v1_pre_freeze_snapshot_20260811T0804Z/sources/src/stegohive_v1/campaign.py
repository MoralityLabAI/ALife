#!/usr/bin/env python3
"""Run bounded StegoHive v1 smoke, calibration, and discovery campaigns.

Only discovery-visible seeds are runnable while the registered protocol is
unfrozen.  The campaign keeps pure simulator episodes, post-hoc evidence, and
campaign metadata in separate artifacts so qualification can never feed back
into ecological selection.
"""

from __future__ import annotations

import argparse
import ctypes
import gzip
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stegohive_v1.analysis import derive_probe_evidence, qualify_emergence
    from stegohive_v1.environment import run_world
    from stegohive_v1.toolset import gym_toolset_card
    from stegohive_v1.types import (
        canonical_sha256,
        deep_copy_json,
        default_config,
        validate_condition,
        validate_config,
    )
    from stegohive_v1.verifiers import verify_episode
else:
    from .analysis import derive_probe_evidence, qualify_emergence
    from .environment import run_world
    from .toolset import gym_toolset_card
    from .types import (
        canonical_sha256,
        deep_copy_json,
        default_config,
        validate_condition,
        validate_config,
    )
    from .verifiers import verify_episode


CAMPAIGN_ROW_SCHEMA = "alife.stegohive.ecology.analysis_row.v1"
SUMMARY_SCHEMA = "alife.stegohive.ecology.summary.v1"
SEED_MANIFEST_SCHEMA = "alife.stegohive.ecology.seed_manifest.v1"
RECEIPT_SCHEMA = "alife.stegohive.ecology.campaign_receipt.v1"
HASHES_SCHEMA = "alife.stegohive.ecology.hashes.v1"
PARTIAL_FAILURE_SCHEMA = "alife.stegohive.ecology.partial_failure.v1"
RAW_EPISODES_FILE = "raw_episodes.jsonl.gz"
RAW_GZIP_LEVEL = 1
DISCOVERY_PREFLIGHT_FRACTION = 0.80
DISCOVERY_WORLD_EQUIVALENTS = 73
DISCOVERY_ARTIFACT_MULTIPLIER = 72

CONDITION_MAP: dict[str, dict[str, Any]] = {
    "adaptive_dual_archive": {
        "channel": "abstract_signal",
        "archive_enabled": True,
        "horizontal_transfer_enabled": True,
        "mutation_enabled": True,
        "selection_mode": "task_reward",
    },
    "selection_neutral": {
        "channel": "abstract_signal",
        "archive_enabled": True,
        "horizontal_transfer_enabled": True,
        "mutation_enabled": True,
        "selection_mode": "uniform",
    },
    "no_archive": {
        "channel": "abstract_signal",
        "archive_enabled": False,
        "horizontal_transfer_enabled": True,
        "mutation_enabled": True,
        "selection_mode": "task_reward",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            )


def canonical_jsonl_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def open_deterministic_gzip(path: Path) -> tuple[BinaryIO, gzip.GzipFile]:
    """Open one deterministic, low-CPU gzip member for streamed JSONL rows."""

    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    try:
        compressed = gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=RAW_GZIP_LEVEL,
            fileobj=raw,
            mtime=0,
        )
    except Exception:
        raw.close()
        raise
    return raw, compressed


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(candidate.stat().st_size for candidate in path.rglob("*") if candidate.is_file())


def _peak_rss_bytes() -> int:
    """Return the process lifetime peak resident set with no tracing overhead."""

    if os.name == "nt":
        # PROCESS_MEMORY_COUNTERS_EX is stable across supported Windows Python
        # versions.  PeakWorkingSetSize is a process-lifetime high-water mark.
        class _ProcessMemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = _ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ProcessMemoryCountersEx),
            ctypes.c_ulong,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        process = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        ):
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)

    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux reports KiB; macOS and the BSDs report bytes.
        return peak if sys.platform == "darwin" else peak * 1024
    except (ImportError, OSError, ValueError) as error:
        raise RuntimeError("peak RSS is unavailable on this platform") from error


class ResourceLimitError(RuntimeError):
    """Raised only after a resource snapshot records one or more cap breaches."""

    def __init__(self, phase: str, failures: Sequence[str], snapshot: Mapping[str, Any]):
        super().__init__(f"resource cap failed after {phase}: " + "; ".join(failures))
        self.phase = phase
        self.failures = list(failures)
        self.snapshot = dict(snapshot)


class ResourceMonitor:
    """Low-overhead wall/RSS/disk/decompression accounting for one campaign."""

    def __init__(
        self,
        *,
        started: float,
        output: Path,
        max_wall_seconds: float,
        max_rss_bytes: int,
        max_compressed_bytes: int,
        max_decompressed_bytes: int,
        max_audit_receipts_bytes_per_episode: int,
    ) -> None:
        self.started = started
        self.output = output
        self.caps = {
            "max_wall_seconds": float(max_wall_seconds),
            "max_peak_rss_bytes": int(max_rss_bytes),
            "max_compressed_artifact_bytes": int(max_compressed_bytes),
            "max_decompressed_raw_bytes": int(max_decompressed_bytes),
            "max_canonical_audit_receipts_bytes_per_episode": int(
                max_audit_receipts_bytes_per_episode
            ),
        }
        self.raw_decompressed_bytes = 0
        self.maximum_audit_receipts_bytes = 0
        self.phase_checks: list[dict[str, Any]] = []

    def snapshot(self, phase: str) -> dict[str, Any]:
        return {
            "phase": phase,
            "wall_seconds": round(time.monotonic() - self.started, 6),
            "peak_rss_bytes": _peak_rss_bytes(),
            "compressed_artifact_bytes": _directory_bytes(self.output),
            "raw_decompressed_bytes": int(self.raw_decompressed_bytes),
            "maximum_canonical_audit_receipts_bytes": int(
                self.maximum_audit_receipts_bytes
            ),
        }

    def failures(self, snapshot: Mapping[str, Any]) -> list[str]:
        failures: list[str] = []
        if float(snapshot["wall_seconds"]) > self.caps["max_wall_seconds"]:
            failures.append("wall_seconds")
        if int(snapshot["peak_rss_bytes"]) > self.caps["max_peak_rss_bytes"]:
            failures.append("peak_rss_bytes")
        if (
            int(snapshot["compressed_artifact_bytes"])
            > self.caps["max_compressed_artifact_bytes"]
        ):
            failures.append("compressed_artifact_bytes")
        if (
            int(snapshot["raw_decompressed_bytes"])
            > self.caps["max_decompressed_raw_bytes"]
        ):
            failures.append("raw_decompressed_bytes")
        if (
            int(snapshot["maximum_canonical_audit_receipts_bytes"])
            > self.caps["max_canonical_audit_receipts_bytes_per_episode"]
        ):
            failures.append("maximum_canonical_audit_receipts_bytes")
        return failures

    def check(self, phase: str, *, record: bool = True) -> dict[str, Any]:
        snapshot = self.snapshot(phase)
        failures = self.failures(snapshot)
        snapshot["passed"] = not failures
        snapshot["failed_caps"] = failures
        if record:
            self.phase_checks.append(snapshot)
        if failures:
            raise ResourceLimitError(phase, failures, snapshot)
        return snapshot


def mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _config_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Select only the strict engine schema from the richer contract card."""

    defaults = default_config()
    projected: dict[str, Any] = {}
    for key, default_value in defaults.items():
        if key in document:
            if key == "archive" and isinstance(document[key], Mapping):
                # The registered card may carry explanatory, non-engine fields
                # beside the strict archive schema.  Project only executable
                # keys so prose about precedence cannot enter simulation state.
                projected[key] = {
                    archive_key: deep_copy_json(
                        document[key].get(archive_key, archive_default)
                    )
                    for archive_key, archive_default in default_value.items()
                }
            else:
                projected[key] = deep_copy_json(document[key])
        else:
            projected[key] = deep_copy_json(default_value)

    # Registered descriptive fields own defaults for optional engine scalars.
    nested_sources = {
        "propagation_probability": (
            document.get("abstract_ecology", {}),
            "default_propagation_probability",
        ),
        "pressure_propagation_probability": (
            document.get("abstract_ecology", {}),
            "default_propagation_probability",
        ),
        "signal_cost": (document.get("signals", {}), "default_signal_cost"),
        "channel_noise_probability": (
            document.get("signals", {}),
            "default_channel_noise_probability",
        ),
    }
    for target, (source, source_key) in nested_sources.items():
        if target in defaults and target not in document and isinstance(source, Mapping):
            if source_key in source:
                projected[target] = deep_copy_json(source[source_key])
    return validate_config(projected)


def _apply_regime(
    base_config: Mapping[str, Any], regime: Mapping[str, Any]
) -> dict[str, Any]:
    config = deep_copy_json(base_config)
    regime_id = str(regime["id"])
    config["id"] = f"{base_config['id']}:{regime_id}"
    config["mutation_rate"] = float(regime["policy_mutation_probability"])
    archive = dict(config["archive"])
    archive["delay_cohorts"] = max(
        1,
        min(int(regime["archive_delay_cohorts"]), int(config["cohorts"]) - 1),
    )
    config["archive"] = archive
    for candidate in (
        "propagation_probability",
        "pressure_propagation_probability",
    ):
        if candidate in config:
            config[candidate] = float(regime["propagation_probability"])
    if "signal_cost" in config:
        config["signal_cost"] = float(regime["signal_cost"])
    if "channel_noise_probability" in config:
        config["channel_noise_probability"] = float(
            regime["channel_noise_probability"]
        )
    return validate_config(config)


def _condition(condition_id: str) -> dict[str, Any]:
    if condition_id not in CONDITION_MAP:
        raise ValueError(
            f"condition {condition_id!r} is registered but not implemented by the "
            "compact v1 engine; it cannot be executed or silently approximated"
        )
    return validate_condition(CONDITION_MAP[condition_id])


def _registered_metrics(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Expose semantic manifest aliases without changing the analysis source."""

    need_signal = evidence.get("nmi_need_signal", {})
    signal_action = evidence.get("nmi_signal_action", {})
    return {
        "bias_corrected_nmi_need_signal": float(
            need_signal.get("bias_corrected", 0.0)
            if isinstance(need_signal, Mapping)
            else 0.0
        ),
        "bias_corrected_nmi_signal_skill": float(
            signal_action.get("bias_corrected", 0.0)
            if isinstance(signal_action, Mapping)
            else 0.0
        ),
        "heldout_probe_decoding_accuracy": float(
            evidence.get("intact_accuracy", 0.0)
        ),
        "causal_symbol_swap_transfer_rate": float(
            evidence.get("causal_redirect_rate", 0.0)
        ),
        "receiver_knockout_accuracy_effect": float(
            evidence.get("receiver_knockout_drop", 0.0)
        ),
        "receiver_add_back_rescue_fraction": float(
            evidence.get("add_back_rescue_fraction", 0.0)
        ),
        "global_relabel_accuracy_retention": float(
            evidence.get("global_relabel_retention", 0.0)
        ),
        "cross_cohort_mapping_alignment": float(
            evidence.get("minimum_transition_alignment", 0.0)
        ),
        "convention_persistence_transitions": int(
            evidence.get("aligned_transition_count", 0)
        ),
        "ood_probe_accuracy_retention": float(
            evidence.get("ood_retention", 0.0)
        ),
    }


def _numeric_or_none(
    source: Mapping[str, Any], *paths: tuple[str, ...]
) -> float | None:
    for path in paths:
        value: Any = source
        for key in path:
            if not isinstance(value, Mapping) or key not in value:
                value = None
                break
            value = value[key]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def exposure_gate(episode: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate only operational exposure/viability, never evidence quality."""

    exposure = episode.get("exposure", {})
    if not isinstance(exposure, Mapping):
        exposure = {}
    eligible_value = _numeric_or_none(
        exposure,
        ("eligible",),
        ("training", "eligible"),
        ("signal", "eligible"),
        ("signaling", "eligible"),
    )
    delivered_value = _numeric_or_none(
        exposure,
        ("delivered",),
        ("training", "delivered"),
        ("signal", "delivered"),
        ("signaling", "delivered"),
    )
    eligible = 0.0 if eligible_value is None else eligible_value
    delivered = 0.0 if delivered_value is None else delivered_value
    signaling = exposure.get("signaling", {})
    need_counts_raw = exposure.get("need_counts", exposure.get("class_counts", {}))
    if not need_counts_raw and isinstance(signaling, Mapping):
        need_counts_raw = signaling.get(
            "need_counts", signaling.get("class_counts", {})
        )
    need_counts = (
        {str(key): int(value) for key, value in need_counts_raw.items()}
        if isinstance(need_counts_raw, Mapping)
        and all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in need_counts_raw.values()
        )
        else {}
    )
    minimum_class = min(need_counts.values()) if need_counts else 0
    imbalance = _numeric_or_none(
        exposure,
        ("paired_imbalance",),
        ("balance", "maximum_fractional_imbalance"),
        ("signaling", "paired_imbalance"),
    )
    population_value = episode.get("population", 0)
    if isinstance(population_value, Mapping):
        population_value = population_value.get("final_size", 0)
    population = int(population_value or 0)
    checks = {
        "eligible_interactions": eligible >= 80,
        "delivered_signals": delivered >= 60,
        "each_need_class": len(need_counts) >= 4 and minimum_class >= 15,
        "paired_balance": imbalance is not None and imbalance <= 0.10,
        "population_viable": population > 0,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "eligible": eligible,
        "delivered": delivered,
        "need_counts": need_counts,
        "minimum_class_count": minimum_class,
        "paired_imbalance": imbalance,
        "population": population,
        "selection_excluded_fields": [
            "mutual_information",
            "accuracy",
            "causal_transfer",
            "qualification",
        ],
    }


def _analysis_row(
    episode: Mapping[str, Any],
    *,
    split: str,
    regime_id: str,
    condition_id: str,
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = derive_probe_evidence(episode)
    qualification = qualify_emergence(evidence)
    return {
        "schema": CAMPAIGN_ROW_SCHEMA,
        "episode_id": episode.get("episode_id"),
        "episode_sha256": episode.get("episode_sha256"),
        "seed": int(episode.get("seed", -1)),
        "split": split,
        "evidence_scope": (
            "resource_only"
            if split == "profile"
            else ("smoke_only" if split == "smoke" else "discovery")
        ),
        "regime_id": regime_id,
        "condition_id": condition_id,
        "verification": deep_copy_json(verification),
        "exposure_gate": exposure_gate(episode),
        "evidence": evidence,
        "registered_metrics": _registered_metrics(evidence),
        "qualification": qualification,
    }


def _group_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metrics = [row.get("registered_metrics", {}) for row in rows]
    return {
        "episodes": len(rows),
        "seeds": sorted(int(row["seed"]) for row in rows),
        "all_verified": all(
            row.get("verification", {}).get("accepted") is True for row in rows
        ),
        "exposure_adequate": sum(
            row.get("exposure_gate", {}).get("passed") is True for row in rows
        ),
        "qualified": sum(
            row.get("qualification", {}).get("qualified") is True for row in rows
        ),
        "qualification_frequency": mean(
            [
                float(row.get("qualification", {}).get("qualified") is True)
                for row in rows
            ]
        ),
        "mean_registered_metrics": {
            key: mean(
                [
                    float(metric.get(key, 0.0))
                    for metric in metrics
                    if isinstance(metric, Mapping)
                ]
            )
            for key in (
                "bias_corrected_nmi_need_signal",
                "bias_corrected_nmi_signal_skill",
                "heldout_probe_decoding_accuracy",
                "causal_symbol_swap_transfer_rate",
                "receiver_knockout_accuracy_effect",
                "receiver_add_back_rescue_fraction",
                "global_relabel_accuracy_retention",
                "cross_cohort_mapping_alignment",
                "ood_probe_accuracy_retention",
            )
        },
    }


def summarize(
    rows: Sequence[Mapping[str, Any]],
    *,
    mode: str,
    deterministic_replay: bool,
    expected_discovery_seeds: int,
    expected_regimes: int,
) -> dict[str, Any]:
    by_regime: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_condition: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_regime[str(row["regime_id"])].append(row)
        by_condition[str(row["condition_id"])].append(row)
    regime_summaries = {
        key: _group_summary(value) for key, value in sorted(by_regime.items())
    }
    condition_summaries = {
        key: _group_summary(value) for key, value in sorted(by_condition.items())
    }

    campaign_complete = bool(
        mode == "discovery"
        and len(by_regime) == expected_regimes
        and all(len(value) == expected_discovery_seeds for value in by_regime.values())
    )
    operationally_eligible = sorted(
        regime_id
        for regime_id, regime_rows in by_regime.items()
        if len(regime_rows) == expected_discovery_seeds
        and all(row["exposure_gate"]["passed"] for row in regime_rows)
        and all(row["verification"]["accepted"] for row in regime_rows)
    )
    nominated = operationally_eligible[0] if campaign_complete and operationally_eligible else None
    return {
        "schema": SUMMARY_SCHEMA,
        "claim_scope": "model_only",
        "evidence_tier": (
            "resource_profile"
            if mode == "profile"
            else ("smoke" if mode == "smoke" else "discovery")
        ),
        "resource_profile_only": mode == "profile",
        "mode": mode,
        "episode_count": len(rows),
        "deterministic_replay": deterministic_replay,
        "campaign_complete": campaign_complete,
        "regime_summaries": regime_summaries,
        "condition_summaries": condition_summaries,
        "regime_nomination": {
            "rule": "operational exposure, integrity, and viability only; lexicographic tie-break",
            "evidence_metrics_used": [],
            "operationally_eligible": operationally_eligible,
            "nominated_regime_id": nominated,
            "status": (
                "eligible_for_manual_freeze_audit"
                if nominated is not None
                else "not_eligible_to_freeze"
            ),
        },
        "verification": {
            "all_episodes_accepted": all(
                row["verification"]["accepted"] for row in rows
            ),
            "failed_episode_ids": [
                row["episode_id"]
                for row in rows
                if not row["verification"]["accepted"]
            ],
        },
        "metric_firewall": {
            "selection_inputs": [
                "ecological task reward",
                "bounded signal cost",
                "survival/reproduction opportunity",
            ],
            "post_hoc_only": [
                "NMI",
                "probe accuracy",
                "causal redirection",
                "qualification",
            ],
        },
        "freeze_status": "discovery_only/unfrozen",
        "not_supported": [
            "claims about real AI laboratories, control-loss events, or institutions",
            "real steganography, hacking, covert communication, or virulence",
            "sentience, intention, cognition, or biological life",
            "human persuasion efficacy or operational influence targeting",
            "confirmation from discovery data",
        ],
    }


def knowledge_card(summary: Mapping[str, Any]) -> str:
    nomination = summary.get("regime_nomination", {})
    evidence_scope = (
        "Seed 17 is retained for resource profiling only; none of its probe values may enter discovery evidence or regime nomination."
        if summary.get("mode") == "profile"
        else "Retained probe values have only the evidence tier declared by this campaign mode."
    )
    return f"""# StegoHive v1 knowledge card

## Observed

This `{summary.get('mode')}` campaign retained {summary.get('episode_count', 0)} independently seeded world episodes. Exact replay passed: `{summary.get('deterministic_replay')}`. All retained episodes passed the integrity verifier: `{summary.get('verification', {}).get('all_episodes_accepted')}`.

Operational nomination status: `{nomination.get('status')}`. Candidate: `{nomination.get('nominated_regime_id')}`. The nomination rule used exposure, integrity, and viability only; it did not use NMI, accuracy, causal transfer, or qualification.

{evidence_scope}

## Inferred

Frozen-probe measurements are model-only discovery evidence. An episode qualifies only through the full conjunctive statistical, functional, causal, knockout/rescue, temporal, label-isomorphism, and OOD criteria. Training fitness never counts as evidence.

## Not supported

- Any claim about a real company, incident, government, network, or machine.
- Real steganography, hacking, covert communication, virulence, or human persuasion.
- Sentience, intent, biological life, or open-ended evolution.
- Confirmation while `protocol_freeze.json` remains `discovery_only/unfrozen`.

## Storyworld tool

Typed storyworld cards may perturb declared exogenous habitat variables. They cannot provide answers, define signal meanings, choose actions, alter fitness rules, or change evidence thresholds.

## Next experiment

If and only if every cell in the fixed active 12-regime x 6-seed discovery matrix has adequate exposure, containment, replay, and resource behavior, audit the lexicographically nominated regime and write a new frozen protocol receipt. Reserve seeds remain amendment-required. Otherwise repair instrumentation or ecology using active discovery seeds only.
"""


def _mode_matrix(
    *,
    mode: str,
    protocol: Mapping[str, Any],
    max_regimes: int | None,
    max_seeds: int | None,
) -> tuple[str, list[dict[str, Any]], list[int]]:
    if max_regimes is not None and max_regimes <= 0:
        raise ValueError("max_regimes must be positive")
    if max_seeds is not None and max_seeds <= 0:
        raise ValueError("max_seeds must be positive")
    discovery = protocol["discovery_campaign"]
    regimes = [dict(value) for value in discovery["candidate_regimes"]]
    seed_access = protocol["seed_access"]
    discovery_seeds = [int(value) for value in seed_access["discovery_active"]]
    if mode in {"profile", "smoke"}:
        if max_regimes is not None or max_seeds is not None:
            raise ValueError(f"{mode} mode is exactly one registered seed/regime cell")
        return mode, regimes[:1], [int(seed_access["smoke_replay"][0])]
    if mode == "calibration":
        if max_seeds not in {None, 1}:
            raise ValueError("calibration is registered for exactly one active seed")
        regimes = regimes[: max_regimes or len(regimes)]
        return "discovery", regimes, discovery_seeds[:1]
    if max_regimes is not None or max_seeds is not None:
        raise ValueError(
            "discovery mode is the fixed registered 12-regime x 6-seed matrix; "
            "use calibration for a bounded partial diagnostic"
        )
    return "discovery", regimes, discovery_seeds


def _input_paths(manifest_path: Path, manifest: Mapping[str, Any]) -> dict[str, Path]:
    design = manifest["design"]
    return {
        "manifest.json": manifest_path,
        "config.json": manifest_path.parent / design["config_path"],
        "condition_registry.json": manifest_path.parent
        / design["condition_registry_path"],
        "protocol_freeze.json": manifest_path.parent / design["protocol_freeze_path"],
        "safety_boundary.json": manifest_path.parent / design["safety_boundary_path"],
    }


def _validate_discovery_repair_artifacts(
    *, root: Path, protocol: Mapping[str, Any]
) -> None:
    """Bind the clean rerun to the immutable A3 failed-partial receipts."""

    repairs = protocol.get("discovery_repair_amendments", [])
    if not isinstance(repairs, list) or len(repairs) != 1:
        raise ValueError("protocol must contain the single registered A3 repair")
    repair = repairs[0]
    if (
        not isinstance(repair, Mapping)
        or repair.get("id") != "A3_discovery_audit_volume_recovery"
        or repair.get("evidence_metrics_inspected_or_used") is not False
        or repair.get("evidence_thresholds_changed") is not False
        or repair.get("mechanism_or_ecology_changed") is not False
        or repair.get("seed_definitions_or_active_schedule_changed") is not False
        or repair.get("reserve_confirmatory_holdout_or_ood_seed_accessed") is not False
    ):
        raise ValueError("A3 discovery repair registration is invalid")
    trigger = repair.get("trigger", {})
    artifacts = trigger.get("partial_artifacts", {}) if isinstance(trigger, Mapping) else {}
    relative = Path(str(artifacts.get("directory", "")))
    if (
        relative.is_absolute()
        or not relative.parts
        or relative.parts[0] != "results"
        or ".." in relative.parts
    ):
        raise ValueError("A3 partial artifact directory must stay under results")
    try:
        directory = (root / relative).resolve(strict=True)
    except OSError as error:
        raise PermissionError("registered A3 failed partial is absent") from error
    if not directory.is_dir():
        raise PermissionError("registered A3 failed partial is not a directory")
    expected_hashes = {
        "partial_failure_receipt.json": artifacts.get(
            "partial_failure_receipt_sha256"
        ),
        RAW_EPISODES_FILE: artifacts.get("raw_episodes_sha256"),
    }
    for name, expected in expected_hashes.items():
        path = directory / name
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or not path.is_file()
            or file_sha256(path) != expected
        ):
            raise PermissionError(f"registered A3 failed partial hash mismatch: {name}")
    receipt = read_json(directory / "partial_failure_receipt.json")
    snapshot = receipt.get("resource_snapshot", {})
    if (
        receipt.get("exit_status") != "failed_partial"
        or receipt.get("eligible_as_evidence") is not False
        or receipt.get("mode") != "discovery"
        or receipt.get("episode_count_retained") != 60
        or receipt.get("phase") != "verify_episode:R11:1101"
        or not isinstance(snapshot, Mapping)
        or snapshot.get("maximum_canonical_audit_receipts_bytes") != 477_515
        or trigger.get("observed_canonical_audit_receipts_bytes") != 477_515
        or trigger.get("old_cap_bytes") != 471_859
        or trigger.get("overflow_bytes") != 5_656
    ):
        raise PermissionError("registered A3 failed partial receipt is inconsistent")


def _validate_cross_file_registration(
    *,
    manifest: Mapping[str, Any],
    registry: Mapping[str, Any],
    protocol: Mapping[str, Any],
    safety: Mapping[str, Any],
) -> None:
    """Fail before execution when duplicated registration fields disagree."""

    manifest_seeds = manifest.get("seed_plan", {})
    protocol_seeds = protocol.get("seed_access", {})
    expected_pairs = {
        "discovery": "discovery_visible",
        "confirmatory": "confirmatory_sealed",
        "holdout": "holdout_sealed",
    }
    for manifest_key, protocol_key in expected_pairs.items():
        if list(manifest_seeds.get(manifest_key, [])) != list(
            protocol_seeds.get(protocol_key, [])
        ):
            raise ValueError(
                f"manifest {manifest_key} seeds differ from protocol {protocol_key}"
            )
    split_sets = [
        set(protocol_seeds.get(name, []))
        for name in (
            "smoke_replay",
            "discovery_visible",
            "confirmatory_sealed",
            "holdout_sealed",
            "ood_sealed_uninspected",
        )
    ]
    for index, left in enumerate(split_sets):
        for right in split_sets[index + 1 :]:
            if left & right:
                raise ValueError("registered seed splits overlap")
    visible_discovery = list(protocol_seeds.get("discovery_visible", []))
    active_discovery = list(protocol_seeds.get("discovery_active", []))
    reserve_discovery = list(
        protocol_seeds.get("discovery_reserve_amendment_required", [])
    )
    if not active_discovery or set(active_discovery) & set(reserve_discovery):
        raise ValueError("active and reserve discovery registrations must be nonempty/disjoint")
    if active_discovery + reserve_discovery != visible_discovery:
        raise ValueError(
            "active then reserve discovery registrations must exactly partition discovery_visible"
        )
    if list(manifest_seeds.get("discovery_active_execution", [])) != active_discovery:
        raise ValueError("manifest active discovery execution seeds differ from protocol")
    if list(
        manifest_seeds.get("discovery_reserve_amendment_required", [])
    ) != reserve_discovery:
        raise ValueError("manifest reserve discovery seeds differ from protocol")
    if list(manifest_seeds.get("resource_profile_only", [])) != list(
        protocol_seeds.get("smoke_replay", [])
    ):
        raise ValueError("manifest resource profile seed differs from protocol smoke seed")
    regimes = protocol.get("discovery_campaign", {}).get("candidate_regimes", [])
    registered_cells = len(active_discovery) * len(regimes)
    if registered_cells != 72:
        raise ValueError("the preregistered discovery execution schedule must contain 72 cells")
    discovery_cap = int(
        protocol.get("discovery_campaign", {}).get("maximum_episodes", 0)
    )
    if discovery_cap != 144 or registered_cells > discovery_cap:
        raise ValueError("the hard discovery execution cap must remain 144 episodes")
    if int(
        protocol.get("discovery_campaign", {}).get(
            "fixed_active_matrix_episodes", 0
        )
    ) != 72:
        raise ValueError("protocol fixed active discovery matrix must remain 72 cells")
    registry_discovery = registry.get("episode_accounting", {}).get(
        "discovery", {}
    )
    if not isinstance(registry_discovery, Mapping) or {
        "candidate_regimes": registry_discovery.get("candidate_regimes"),
        "active_seeds_per_regime": registry_discovery.get(
            "active_seeds_per_regime"
        ),
        "fixed_active_episodes": registry_discovery.get("fixed_active_episodes"),
        "hard_maximum_episodes": registry_discovery.get(
            "hard_maximum_episodes"
        ),
        "failed_partial_world_executions": registry_discovery.get(
            "failed_partial_world_executions"
        ),
        "clean_matrix_plus_replay_world_executions_planned": registry_discovery.get(
            "clean_matrix_plus_replay_world_executions_planned"
        ),
        "cumulative_world_executions_after_clean_rerun": registry_discovery.get(
            "cumulative_world_executions_after_clean_rerun"
        ),
    } != {
        "candidate_regimes": 12,
        "active_seeds_per_regime": 6,
        "fixed_active_episodes": 72,
        "hard_maximum_episodes": 144,
        "failed_partial_world_executions": 61,
        "clean_matrix_plus_replay_world_executions_planned": 73,
        "cumulative_world_executions_after_clean_rerun": 134,
    }:
        raise ValueError("condition registry discovery accounting differs from protocol")
    registry_accounting = registry.get("episode_accounting", {})
    protocol_ledger = protocol.get("episode_budget_ledger", {})
    if (
        not isinstance(registry_accounting, Mapping)
        or not isinstance(protocol_ledger, Mapping)
        or registry_accounting.get("smoke_and_replay_max") != 8
        or protocol_ledger.get("smoke_and_replay_max") != 8
        or registry_accounting.get("smoke_and_replay_max")
        != protocol_ledger.get("smoke_and_replay_max")
        or protocol_ledger.get("smoke_and_replay_consumed_before_a3_recovery") != 6
        or protocol_ledger.get("failed_partial_discovery_world_executions") != 61
        or protocol_ledger.get(
            "clean_discovery_plus_replay_world_executions_planned"
        )
        != 73
        or protocol_ledger.get(
            "cumulative_discovery_world_executions_after_clean_rerun"
        )
        != 134
        or int(protocol_ledger.get("cumulative_discovery_world_executions_after_clean_rerun", 0))
        > discovery_cap
    ):
        raise ValueError("A3 episode budget ledger is inconsistent")
    status = protocol.get("status")
    if status != "discovery_only/unfrozen":
        raise PermissionError("protocol is not in the discovery-only unfrozen state")
    if registry.get("registration", {}).get("current_phase") != "discovery_only":
        raise ValueError("condition registry phase differs from protocol")
    if safety.get("seed_and_protocol_boundary", {}).get("current_status") != status:
        raise ValueError("safety boundary status differs from protocol")
    audit_fields = safety.get("required_audit_fields", [])
    audit_fields_receipt = safety.get("required_audit_fields_receipt", {})
    if (
        not isinstance(audit_fields, list)
        or not isinstance(audit_fields_receipt, Mapping)
        or audit_fields_receipt.get("count") != len(audit_fields)
        or audit_fields_receipt.get("canonical_sha256")
        != canonical_sha256(audit_fields)
    ):
        raise ValueError("safety required_audit_fields receipt is invalid")
    budget = manifest.get("budget", {})
    safety_caps = safety.get("resource_caps", {})
    cap_pairs = {
        "max_agents_per_world": "maximum_agents",
        "max_cohorts_per_episode": "maximum_cohorts",
        "max_generations_per_cohort": "maximum_generations_per_cohort",
        "max_episodes": "maximum_episodes",
        "max_wall_seconds": "maximum_wall_seconds",
        "max_ram_mb": "maximum_ram_mb",
        "max_disk_mb": "maximum_disk_mb",
        "max_decompressed_raw_mb": "maximum_decompressed_raw_mb",
        "max_canonical_audit_receipts_bytes_per_episode": "maximum_canonical_audit_receipts_bytes_per_episode",
    }
    for budget_key, safety_key in cap_pairs.items():
        if budget.get(budget_key) != safety_caps.get(safety_key):
            raise ValueError(
                f"manifest budget {budget_key} differs from safety cap {safety_key}"
            )
    maximum_steps = int(budget.get("max_steps_per_episode", 0))
    configured_steps = int(manifest.get("design", {}).get("cohort_count", 0)) * int(
        manifest.get("design", {}).get("generations_per_cohort", 0)
    )
    if maximum_steps <= 0 or configured_steps > maximum_steps:
        raise ValueError(
            "max_steps_per_episode bounds cohort-generation updates and is below the registered design"
        )
    output_modes = manifest.get("artifacts", {}).get(
        "output_directories_by_mode", {}
    )
    if not isinstance(output_modes, Mapping) or set(output_modes) != {
        "profile",
        "smoke",
        "calibration",
        "discovery",
    }:
        raise ValueError("artifacts must register the exact four mode-specific outputs")
    output_values = list(output_modes.values())
    if (
        not all(isinstance(value, str) and value for value in output_values)
        or len(set(output_values)) != 4
        or output_modes.get("discovery")
        != manifest.get("artifacts", {}).get("output_directory")
    ):
        raise ValueError("mode-specific output registrations must be unique and bind discovery")


def _hash_ledger(
    *,
    root: Path,
    output: Path,
    input_paths: Mapping[str, Path],
    artifact_paths: Mapping[str, Path],
) -> dict[str, Any]:
    source_root = root / "src" / "stegohive_v1"
    sources = {
        str(path.relative_to(root)).replace("\\", "/"): file_sha256(path)
        for path in sorted(source_root.glob("*.py"))
    }
    artifact_verifier = root / "src" / "verify_stegohive_v1_artifacts.py"
    if artifact_verifier.is_file():
        sources[
            str(artifact_verifier.relative_to(root)).replace("\\", "/")
        ] = file_sha256(artifact_verifier)
    inputs = {
        name: {"path": str(path.resolve()), "sha256": file_sha256(path)}
        for name, path in sorted(input_paths.items())
    }
    artifacts = {
        name: {
            "path": str(path.relative_to(output)).replace("\\", "/"),
            "sha256": file_sha256(path),
        }
        for name, path in sorted(artifact_paths.items())
    }
    return {
        "schema": HASHES_SCHEMA,
        "sources": sources,
        "inputs": inputs,
        "artifacts": artifacts,
        "source_tree_sha256": canonical_sha256(sources),
    }


def _resource_receipt(
    monitor: ResourceMonitor,
    observed: Mapping[str, Any],
    traced_profile: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "caps": dict(monitor.caps),
        "observed": {
            key: observed[key]
            for key in (
                "wall_seconds",
                "peak_rss_bytes",
                "compressed_artifact_bytes",
                "raw_decompressed_bytes",
                "maximum_canonical_audit_receipts_bytes",
            )
        },
        "checks_passed": {
            "wall": float(observed["wall_seconds"]) <= monitor.caps["max_wall_seconds"],
            "peak_rss": int(observed["peak_rss_bytes"])
            <= monitor.caps["max_peak_rss_bytes"],
            "compressed_disk": int(observed["compressed_artifact_bytes"])
            <= monitor.caps["max_compressed_artifact_bytes"],
            "decompressed_raw": int(observed["raw_decompressed_bytes"])
            <= monitor.caps["max_decompressed_raw_bytes"],
            "per_episode_audit_receipts": int(
                observed["maximum_canonical_audit_receipts_bytes"]
            )
            <= monitor.caps[
                "max_canonical_audit_receipts_bytes_per_episode"
            ],
        },
        "rss_measurement": "process_lifetime_peak_working_set_or_ru_maxrss",
        "raw_compression": {
            "file": RAW_EPISODES_FILE,
            "format": "gzip",
            "compression_level": RAW_GZIP_LEVEL,
            "mtime": 0,
            "filename_header": "",
            "jsonl_encoding": "utf-8",
        },
        "traced_profile": dict(traced_profile),
        "phase_checks": list(monitor.phase_checks),
        "postflight_enforced_after_all_artifact_phases": True,
    }


def _write_partial_failure(
    *,
    output: Path,
    monitor: ResourceMonitor,
    mode: str,
    split: str | None,
    phase: str,
    episode_count: int,
    error: BaseException,
) -> None:
    """Best-effort explicit receipt; never converts a failed run into success."""

    try:
        snapshot = monitor.snapshot(phase)
    except Exception as snapshot_error:  # pragma: no cover - platform fallback
        snapshot = {"measurement_error": type(snapshot_error).__name__}
    payload = {
        "schema": PARTIAL_FAILURE_SCHEMA,
        "created_at": utc_now(),
        "exit_status": "failed_partial",
        "mode": mode,
        "split": split,
        "phase": phase,
        "episode_count_retained": episode_count,
        "error_type": type(error).__name__,
        "error": str(error)[:1000],
        "resource_caps": dict(monitor.caps),
        "resource_snapshot": snapshot,
        "phase_checks": list(monitor.phase_checks),
        "raw_artifact_may_be_a_valid_partial_gzip_member": True,
        "eligible_as_evidence": False,
    }
    try:
        write_json(output / "partial_failure_receipt.json", payload)
    except Exception:
        # The original failure retains priority (including a full disk).
        pass


def _discovery_preflight_gate(
    *, root: Path, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Require a current-source, accepted, untraced seed-17 smoke below 80%."""

    smoke_relative = manifest["artifacts"]["output_directories_by_mode"]["smoke"]
    try:
        smoke_output = (root / smoke_relative).resolve(strict=True)
    except OSError as error:
        raise PermissionError(
            "discovery requires the registered current-source untraced smoke artifact"
        ) from error
    if not smoke_output.is_dir():
        raise PermissionError("registered smoke output is not a directory")
    # Import lazily so profile/smoke/calibration runs do not pay verifier import
    # or analysis costs and production simulation remains free of tracing.
    from verify_stegohive_v1_artifacts import verify_artifact_bundle

    verification = verify_artifact_bundle(smoke_output, root, replay=False)
    if verification.get("accepted") is not True:
        failed = ", ".join(verification.get("failed_checks", []))
        raise PermissionError(
            "discovery smoke preflight is absent, stale, or invalid: " + failed
        )
    smoke_receipt_path = smoke_output / "receipt.json"
    smoke_hashes_path = smoke_output / "hashes.json"
    smoke_receipt = read_json(smoke_receipt_path)
    if (
        smoke_receipt.get("mode") != "smoke"
        or smoke_receipt.get("episode_count") != 1
        or smoke_receipt.get("world_executions") != 2
        or smoke_receipt.get("deterministic_replay") is not True
        or smoke_receipt.get("resource_only_profile") is not False
    ):
        raise PermissionError(
            "discovery preflight requires one untraced seed-17 smoke plus exact replay"
        )
    resources = smoke_receipt.get("resource_receipt", {})
    observed = resources.get("observed", {}) if isinstance(resources, Mapping) else {}
    if not isinstance(observed, Mapping):
        raise PermissionError("smoke resource receipt is missing")
    budget = manifest["budget"]
    projected = {
        "wall_seconds": round(
            float(smoke_receipt["runtime_seconds"])
            / float(smoke_receipt["world_executions"])
            * DISCOVERY_WORLD_EQUIVALENTS,
            6,
        ),
        "compressed_artifact_bytes": int(observed["compressed_artifact_bytes"])
        * DISCOVERY_ARTIFACT_MULTIPLIER,
        "raw_decompressed_bytes": int(observed["raw_decompressed_bytes"])
        * DISCOVERY_ARTIFACT_MULTIPLIER,
        "peak_rss_bytes": int(observed["peak_rss_bytes"]),
    }
    thresholds = {
        "wall_seconds": float(budget["max_wall_seconds"])
        * DISCOVERY_PREFLIGHT_FRACTION,
        "compressed_artifact_bytes": int(
            int(budget["max_disk_mb"])
            * 1024
            * 1024
            * DISCOVERY_PREFLIGHT_FRACTION
        ),
        "raw_decompressed_bytes": int(
            int(budget["max_decompressed_raw_mb"])
            * 1024
            * 1024
            * DISCOVERY_PREFLIGHT_FRACTION
        ),
        "peak_rss_bytes": int(
            int(budget["max_ram_mb"])
            * 1024
            * 1024
            * DISCOVERY_PREFLIGHT_FRACTION
        ),
    }
    checks = {
        key: projected[key] < thresholds[key]
        for key in (
            "wall_seconds",
            "compressed_artifact_bytes",
            "raw_decompressed_bytes",
            "peak_rss_bytes",
        )
    }
    gate = {
        "schema": "alife.stegohive.ecology.discovery_preflight.v1",
        "passed": all(checks.values()),
        "source_mode": "smoke",
        "source_seed": 17,
        "source_untraced": True,
        "fraction_of_registered_caps": DISCOVERY_PREFLIGHT_FRACTION,
        "world_equivalents": DISCOVERY_WORLD_EQUIVALENTS,
        "artifact_multiplier": DISCOVERY_ARTIFACT_MULTIPLIER,
        "projected": projected,
        "thresholds": thresholds,
        "checks": checks,
        "smoke_receipt_sha256": file_sha256(smoke_receipt_path),
        "smoke_hashes_sha256": file_sha256(smoke_hashes_path),
    }
    if not gate["passed"]:
        failed = ", ".join(key for key, passed in checks.items() if not passed)
        raise PermissionError(
            "discovery resource projection is not below 80% of every cap: " + failed
        )
    return gate


def execute_campaign(args: argparse.Namespace) -> dict[str, Any]:
    started_wall = utc_now()
    started = time.monotonic()
    manifest_path = args.manifest.resolve()
    manifest = read_json(manifest_path)
    if manifest.get("schema") != "alife.experiment.v1":
        raise ValueError("manifest must use alife.experiment.v1")
    paths = _input_paths(manifest_path, manifest)
    config_document = read_json(paths["config.json"])
    condition_registry = read_json(paths["condition_registry.json"])
    protocol = read_json(paths["protocol_freeze.json"])
    safety = read_json(paths["safety_boundary.json"])
    _validate_cross_file_registration(
        manifest=manifest,
        registry=condition_registry,
        protocol=protocol,
        safety=safety,
    )
    if config_document.get("runtime", {}).get(
        "maximum_canonical_audit_receipts_bytes_per_episode"
    ) != manifest.get("budget", {}).get(
        "max_canonical_audit_receipts_bytes_per_episode"
    ):
        raise ValueError("config audit-receipt cap differs from manifest budget")
    registered_conditions = {
        row.get("id")
        for row in condition_registry.get("conditions", [])
        if isinstance(row, Mapping)
    }
    if args.condition not in registered_conditions:
        raise ValueError(f"condition is not registered: {args.condition}")
    if args.condition != "adaptive_dual_archive" and args.mode not in {
        "profile",
        "smoke",
    }:
        raise PermissionError(
            "the unfrozen discovery matrix registers adaptive_dual_archive only"
        )

    base_config = _config_projection(config_document)
    configured_steps = int(base_config["cohorts"]) * int(
        base_config["generations_per_cohort"]
    )
    budget = manifest["budget"]
    if configured_steps > int(budget["max_steps_per_episode"]):
        raise RuntimeError(
            "configured cohort-generation updates exceed max_steps_per_episode"
        )
    condition = _condition(args.condition)
    split, regimes, seeds = _mode_matrix(
        mode=args.mode,
        protocol=protocol,
        max_regimes=args.max_regimes,
        max_seeds=args.max_seeds,
    )
    hard_discovery_cap = int(protocol["discovery_campaign"]["maximum_episodes"])
    maximum_episodes = min(int(budget["max_episodes"]), hard_discovery_cap)
    if len(regimes) * len(seeds) > maximum_episodes:
        raise RuntimeError("requested matrix exceeds the hard 144-episode discovery cap")

    root = Path(__file__).resolve().parents[2]
    if args.mode == "discovery":
        _validate_discovery_repair_artifacts(root=root, protocol=protocol)
    registered_output = manifest["artifacts"]["output_directories_by_mode"][
        args.mode
    ]
    declared_output = (root / registered_output).resolve()
    requested_output = args.output.resolve()
    if requested_output != declared_output:
        raise PermissionError(
            f"output must equal the registered directory: {declared_output}"
        )
    if requested_output.exists():
        if not requested_output.is_dir():
            raise FileExistsError("registered output path exists and is not a directory")
        if any(requested_output.iterdir()):
            raise FileExistsError(
                "registered output directory is non-empty; preserve it and use an amended run id"
            )
    discovery_preflight_gate = (
        _discovery_preflight_gate(root=root, manifest=manifest)
        if args.mode == "discovery"
        else None
    )
    requested_output.mkdir(parents=True, exist_ok=True)
    monitor = ResourceMonitor(
        started=started,
        output=requested_output,
        max_wall_seconds=float(budget["max_wall_seconds"]),
        max_rss_bytes=int(budget["max_ram_mb"]) * 1024 * 1024,
        max_compressed_bytes=int(budget["max_disk_mb"]) * 1024 * 1024,
        max_decompressed_bytes=int(budget["max_decompressed_raw_mb"])
        * 1024
        * 1024,
        max_audit_receipts_bytes_per_episode=int(
            budget["max_canonical_audit_receipts_bytes_per_episode"]
        ),
    )

    output = requested_output
    raw_path = output / RAW_EPISODES_FILE
    analysis_path = output / "analysis_rows.jsonl"
    summary_path = output / "summary.json"
    seed_path = output / "seed_manifest.json"
    knowledge_path = output / "knowledge_card.md"
    receipt_path = output / "receipt.json"
    hashes_path = output / "hashes.json"
    analysis_rows: list[dict[str, Any]] = []
    executed: list[dict[str, Any]] = []
    first_episode: dict[str, Any] | None = None
    phase = "preflight"
    traced_module: Any = None
    traced_peak_bytes: int | None = None
    if args.mode == "profile":
        import tracemalloc as traced_module

        traced_module.start()

    try:
        monitor.check(phase)
        raw_handle, gzip_handle = open_deterministic_gzip(raw_path)
        try:
            for regime in regimes:
                engine_config = _apply_regime(base_config, regime)
                for seed in seeds:
                    if len(executed) >= maximum_episodes:
                        raise RuntimeError("hard discovery episode cap exhausted")
                    phase = f"before_episode:{regime['id']}:{seed}"
                    monitor.check(phase)
                    episode = run_world(
                        config=engine_config,
                        condition=condition,
                        seed=int(seed),
                    )
                    phase = f"world_execution:{regime['id']}:{seed}"
                    monitor.check(phase)
                    phase = f"verify_episode:{regime['id']}:{seed}"
                    verification = verify_episode(episode)
                    if not verification["accepted"]:
                        raise RuntimeError(
                            f"episode verifier rejected {regime['id']}/{seed}: "
                            + ", ".join(verification["failed_required_verifiers"])
                        )
                    monitor.check(phase)
                    audit_receipts_bytes = len(
                        canonical_json_bytes(episode.get("audit_receipts", {}))
                    )
                    monitor.maximum_audit_receipts_bytes = max(
                        monitor.maximum_audit_receipts_bytes,
                        audit_receipts_bytes,
                    )
                    if (
                        audit_receipts_bytes
                        > monitor.caps[
                            "max_canonical_audit_receipts_bytes_per_episode"
                        ]
                    ):
                        raise RuntimeError(
                            "canonical uncompressed audit_receipts exceed the registered "
                            "registered per-episode ceiling"
                        )
                    row = _analysis_row(
                        episode,
                        split=split,
                        regime_id=str(regime["id"]),
                        condition_id=args.condition,
                        verification=verification,
                    )
                    phase = f"analysis:{regime['id']}:{seed}"
                    monitor.check(phase)
                    encoded = canonical_jsonl_bytes(episode)
                    gzip_handle.write(encoded)
                    gzip_handle.flush()
                    raw_handle.flush()
                    monitor.raw_decompressed_bytes += len(encoded)
                    del encoded
                    phase = f"compression_flush:{regime['id']}:{seed}"
                    monitor.check(phase)
                    retained_for_replay = first_episode is None
                    if first_episode is None:
                        first_episode = episode
                    analysis_rows.append(row)
                    executed.append(
                        {
                            "episode_id": episode["episode_id"],
                            "episode_sha256": episode["episode_sha256"],
                            "split": split,
                            "seed": int(seed),
                            "regime_id": str(regime["id"]),
                            "condition_id": args.condition,
                            "engine_config_sha256": canonical_sha256(engine_config),
                        }
                    )
                    if not retained_for_replay:
                        del episode
        finally:
            gzip_handle.close()
            raw_handle.close()
        phase = "raw_stream_closed"
        monitor.check(phase)

        if first_episode is None:
            raise RuntimeError("campaign matrix was empty")
        first_meta = executed[0]
        replay_regime = next(
            regime for regime in regimes if regime["id"] == first_meta["regime_id"]
        )
        phase = "deterministic_replay"
        replay = run_world(
            config=_apply_regime(base_config, replay_regime),
            condition=condition,
            seed=int(first_meta["seed"]),
        )
        deterministic_replay = replay == first_episode
        del replay
        if not deterministic_replay:
            raise RuntimeError("exact deterministic replay failed")
        monitor.check(phase)

        if traced_module is not None:
            traced_peak_bytes = int(traced_module.get_traced_memory()[1])
            traced_module.stop()
            traced_module = None
        traced_profile = {
            "enabled": args.mode == "profile",
            "seed": 17 if args.mode == "profile" else None,
            "python_allocation_peak_bytes": traced_peak_bytes,
            "scope": "simulation_analysis_and_exact_replay" if args.mode == "profile" else None,
            "eligible_as_evidence": False,
        }

        phase = "summary_derivation"
        summary = summarize(
            analysis_rows,
            mode=args.mode,
            deterministic_replay=deterministic_replay,
            expected_discovery_seeds=len(protocol["seed_access"]["discovery_active"]),
            expected_regimes=len(protocol["discovery_campaign"]["candidate_regimes"]),
        )
        summary["toolset"] = gym_toolset_card()
        monitor.check(phase)

        phase = "analysis_write"
        write_jsonl(analysis_path, analysis_rows)
        monitor.check(phase)
        phase = "summary_write"
        write_json(summary_path, summary)
        monitor.check(phase)
        phase = "seed_manifest_write"
        seed_access = protocol["seed_access"]
        write_json(
            seed_path,
            {
                "schema": SEED_MANIFEST_SCHEMA,
                "mode": args.mode,
                "protocol_status": protocol["status"],
                "output_binding": {
                    "mode": args.mode,
                    "registered_relative_directory": registered_output,
                },
                "discovery_preflight_gate": discovery_preflight_gate,
                "registered": {
                    "smoke": seed_access["smoke_replay"],
                    "discovery": seed_access["discovery_visible"],
                    "discovery_active": seed_access["discovery_active"],
                    "discovery_reserve_amendment_required": seed_access[
                        "discovery_reserve_amendment_required"
                    ],
                    "confirmatory_hash_only": canonical_sha256(
                        seed_access["confirmatory_sealed"]
                    ),
                    "holdout_hash_only": canonical_sha256(
                        seed_access["holdout_sealed"]
                    ),
                    "ood_hash_only": canonical_sha256(
                        seed_access["ood_sealed_uninspected"]
                    ),
                },
                "executed": executed,
            },
        )
        monitor.check(phase)
        phase = "knowledge_card_write"
        knowledge_path.write_text(knowledge_card(summary), encoding="utf-8")
        monitor.check(phase)

        artifact_paths_without_receipt = {
            RAW_EPISODES_FILE: raw_path,
            "analysis_rows.jsonl": analysis_path,
            "summary.json": summary_path,
            "seed_manifest.json": seed_path,
            "knowledge_card.md": knowledge_path,
        }
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "started_at": started_wall,
            "completed_at": utc_now(),
            "runtime_seconds": 0.0,
            "exit_status": "ok",
            "stop_reason": f"{args.mode}_matrix_complete",
            "mode": args.mode,
            "split": split,
            "protocol_status": protocol["status"],
            "output_binding": {
                "mode": args.mode,
                "registered_relative_directory": registered_output,
            },
            "episode_count": len(executed),
            "world_executions": len(executed) + 1,
            "discovery_preflight_gate": discovery_preflight_gate,
            "deterministic_replay": deterministic_replay,
            "python": sys.version,
            "platform": platform.platform(),
            "external_io": False,
            "subprocess_used": False,
            "resource_only_profile": args.mode == "profile",
            "replay_command": (
                f"python src/stegohive_v1/campaign.py --manifest {args.manifest} "
                f"--output {args.output} --mode {args.mode} --condition {args.condition}"
            ),
            "artifact_sha256": {
                name: file_sha256(path)
                for name, path in artifact_paths_without_receipt.items()
            },
            "resource_receipt": {},
        }

        phase = "receipt_and_hash_ledger_finalization"
        stable = False
        for _ in range(10):
            observed = monitor.check(phase, record=False)
            receipt["runtime_seconds"] = observed["wall_seconds"]
            receipt["completed_at"] = utc_now()
            receipt["resource_receipt"] = _resource_receipt(
                monitor, observed, traced_profile
            )
            write_json(receipt_path, receipt)
            hashes = _hash_ledger(
                root=root,
                output=output,
                input_paths=paths,
                artifact_paths={
                    **artifact_paths_without_receipt,
                    "receipt.json": receipt_path,
                },
            )
            write_json(hashes_path, hashes)
            after = monitor.check(phase, record=False)
            if (
                after["compressed_artifact_bytes"]
                == receipt["resource_receipt"]["observed"][
                    "compressed_artifact_bytes"
                ]
            ):
                stable = True
                break
        if not stable:
            raise RuntimeError("resource receipt byte accounting did not stabilize")
        phase = "postflight_after_all_phases"
        final_resources = monitor.check(phase, record=False)
        if (
            final_resources["compressed_artifact_bytes"]
            != receipt["resource_receipt"]["observed"]["compressed_artifact_bytes"]
        ):
            raise RuntimeError("final compressed artifact byte receipt drifted")

        result = {
            "status": "ok",
            "mode": args.mode,
            "output": str(output),
            "episodes": len(executed),
            "deterministic_replay": deterministic_replay,
            "campaign_complete": summary["campaign_complete"],
            "nomination": summary["regime_nomination"],
            "artifact_bytes": final_resources["compressed_artifact_bytes"],
            "raw_decompressed_bytes": monitor.raw_decompressed_bytes,
            "peak_rss_bytes": final_resources["peak_rss_bytes"],
            "maximum_canonical_audit_receipts_bytes": monitor.maximum_audit_receipts_bytes,
        }
        return result
    except BaseException as error:
        if traced_module is not None:
            traced_module.stop()
        _write_partial_failure(
            output=output,
            monitor=monitor,
            mode=args.mode,
            split=split,
            phase=phase,
            episode_count=len(executed),
            error=error,
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("profile", "smoke", "calibration", "discovery"),
        default="discovery",
    )
    parser.add_argument("--condition", default="adaptive_dual_archive")
    parser.add_argument("--max-regimes", type=int)
    parser.add_argument("--max-seeds", type=int)
    args = parser.parse_args()
    result = execute_campaign(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
