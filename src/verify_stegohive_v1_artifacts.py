#!/usr/bin/env python3
"""Verify a complete, locally retained StegoHive v1 campaign directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import zlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stegohive_v1.analysis import derive_probe_evidence, qualify_emergence  # noqa: E402
from stegohive_v1.toolset import gym_toolset_card  # noqa: E402
from stegohive_v1.verifiers import canonical_sha256, verify_episode  # noqa: E402


REPORT_SCHEMA = "alife.stegohive.ecology.artifact_verification.v1"
CAMPAIGN_ROW_SCHEMA = "alife.stegohive.ecology.analysis_row.v1"
SEED_MANIFEST_SCHEMA = "alife.stegohive.ecology.seed_manifest.v1"
SUMMARY_SCHEMA = "alife.stegohive.ecology.summary.v1"
RECEIPT_SCHEMA = "alife.stegohive.ecology.campaign_receipt.v1"
HASHES_SCHEMA = "alife.stegohive.ecology.hashes.v1"
RAW_EPISODES_FILE = "raw_episodes.jsonl.gz"

REQUIRED_CAMPAIGN_FILES = (
    RAW_EPISODES_FILE,
    "analysis_rows.jsonl",
    "seed_manifest.json",
    "summary.json",
    "receipt.json",
    "hashes.json",
    "knowledge_card.md",
)
LEDGER_ARTIFACT_FILES = frozenset(
    {
        RAW_EPISODES_FILE,
        "analysis_rows.jsonl",
        "summary.json",
        "seed_manifest.json",
        "knowledge_card.md",
        "receipt.json",
    }
)
RECEIPT_ARTIFACT_FILES = frozenset(LEDGER_ARTIFACT_FILES - {"receipt.json"})
REQUIRED_INPUT_FILES = frozenset(
    {
        "manifest.json",
        "config.json",
        "condition_registry.json",
        "protocol_freeze.json",
        "safety_boundary.json",
    }
)
REQUIRED_SOURCE_SUFFIXES = frozenset(
    {
        "src/stegohive_v1/types.py",
        "src/stegohive_v1/rng.py",
        "src/stegohive_v1/environment.py",
        "src/stegohive_v1/analysis.py",
        "src/stegohive_v1/storyworld_tools.py",
        "src/stegohive_v1/toolset.py",
        "src/stegohive_v1/verifiers.py",
        "src/stegohive_v1/campaign.py",
        "src/verify_stegohive_v1_artifacts.py",
    }
)

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_JSONL_BYTES = 256 * 1024 * 1024
MAX_COMPRESSED_RAW_BYTES = 256 * 1024 * 1024
MAX_DECOMPRESSED_RAW_BYTES = 1024 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_AUDIT_RECEIPTS_BYTES = 786_432
MAX_EPISODE_JSON_BYTES = 32 * 1024 * 1024
DISCOVERY_PREFLIGHT_FRACTION = 0.80
DISCOVERY_WORLD_EQUIVALENTS = 73
DISCOVERY_ARTIFACT_MULTIPLIER = 72
MAX_KNOWLEDGE_BYTES = 2 * 1024 * 1024
MAX_EPISODES = 144


class ArtifactVerificationError(ValueError):
    """Internal fail-closed boundary error."""


def _reject_constant(value: str) -> None:
    raise ArtifactVerificationError(f"non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactVerificationError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_loads(text: str, label: str) -> Any:
    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, ArtifactVerificationError) as error:
        raise ArtifactVerificationError(f"{label} is not strict finite JSON: {error}") from error


def _read_bytes(path: Path, cap: int, label: str) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ArtifactVerificationError(f"cannot stat {label}: {error}") from error
    if size > cap:
        raise ArtifactVerificationError(f"{label} exceeds its sealed byte cap")
    try:
        content = path.read_bytes()
    except OSError as error:
        raise ArtifactVerificationError(f"cannot read {label}: {error}") from error
    if len(content) != size:
        raise ArtifactVerificationError(f"{label} changed while being read")
    return content


def _read_json(path: Path, label: str) -> dict[str, Any]:
    content = _read_bytes(path, MAX_JSON_BYTES, label)
    try:
        value = _strict_loads(content.decode("utf-8-sig"), label)
    except UnicodeDecodeError as error:
        raise ArtifactVerificationError(f"{label} is not UTF-8") from error
    if not isinstance(value, dict):
        raise ArtifactVerificationError(f"{label} must contain a JSON object")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    content = _read_bytes(path, MAX_JSONL_BYTES, label)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ArtifactVerificationError(f"{label} is not UTF-8") from error
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            raise ArtifactVerificationError(f"{label}:{line_number} is blank")
        value = _strict_loads(line, f"{label}:{line_number}")
        if not isinstance(value, dict):
            raise ArtifactVerificationError(f"{label}:{line_number} must be an object")
        rows.append(value)
        if len(rows) > MAX_EPISODES:
            raise ArtifactVerificationError(f"{label} exceeds the episode-row cap")
    if not rows:
        raise ArtifactVerificationError(f"{label} must be non-empty")
    return rows


def _read_gzip_jsonl(
    path: Path,
    label: str,
    *,
    compressed_cap: int,
    decompressed_cap: int,
    audit_receipts_cap: int,
) -> tuple[list[dict[str, Any]], int, int]:
    """Strictly read one deterministic gzip member under both byte caps."""

    compressed_size = path.stat().st_size
    if compressed_size > min(compressed_cap, MAX_COMPRESSED_RAW_BYTES):
        raise ArtifactVerificationError(f"{label} exceeds its compressed byte cap")
    with path.open("rb") as handle:
        header = handle.read(10)
        if len(header) != 10 or header[:3] != b"\x1f\x8b\x08":
            raise ArtifactVerificationError(f"{label} is not a gzip deflate member")
        if header[3] != 0:
            raise ArtifactVerificationError(
                f"{label} must have no optional gzip fields, including filename"
            )
        if header[4:8] != b"\x00\x00\x00\x00":
            raise ArtifactVerificationError(f"{label} gzip mtime must be zero")
        if header[8] != 4:
            raise ArtifactVerificationError(
                f"{label} gzip XFL must identify fastest/level-1 compression"
            )
        handle.seek(0)
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        pending = b""
        decompressed_bytes = 0
        rows: list[dict[str, Any]] = []
        maximum_audit_receipts_bytes = 0
        line_number = 0
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            try:
                decoded = decompressor.decompress(chunk)
            except zlib.error as error:
                raise ArtifactVerificationError(f"{label} gzip stream is invalid: {error}") from error
            decompressed_bytes += len(decoded)
            if decompressed_bytes > min(
                decompressed_cap, MAX_DECOMPRESSED_RAW_BYTES
            ):
                raise ArtifactVerificationError(
                    f"{label} exceeds its decompressed byte cap"
                )
            pending += decoded
            if len(pending) > MAX_EPISODE_JSON_BYTES and b"\n" not in pending:
                raise ArtifactVerificationError(
                    f"{label} contains an episode row above the verifier hard cap"
                )
            while b"\n" in pending:
                line_bytes, pending = pending.split(b"\n", 1)
                line_number += 1
                if not line_bytes:
                    raise ArtifactVerificationError(f"{label}:{line_number} is blank")
                if len(line_bytes) > MAX_EPISODE_JSON_BYTES:
                    raise ArtifactVerificationError(
                        f"{label}:{line_number} exceeds the episode-row byte cap"
                    )
                try:
                    line = line_bytes.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ArtifactVerificationError(
                        f"{label}:{line_number} is not UTF-8"
                    ) from error
                value = _strict_loads(line, f"{label}:{line_number}")
                if not isinstance(value, dict):
                    raise ArtifactVerificationError(
                        f"{label}:{line_number} must be an object"
                    )
                audit_receipts_bytes = len(
                    json.dumps(
                        value.get("audit_receipts", {}),
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    ).encode("utf-8")
                )
                maximum_audit_receipts_bytes = max(
                    maximum_audit_receipts_bytes, audit_receipts_bytes
                )
                if audit_receipts_bytes > audit_receipts_cap:
                    raise ArtifactVerificationError(
                        f"{label}:{line_number} audit_receipts exceed the registered "
                        "registered canonical audit-receipt ceiling"
                    )
                rows.append(value)
                if len(rows) > MAX_EPISODES:
                    raise ArtifactVerificationError(
                        f"{label} exceeds the hard 144-row cap"
                    )
            if decompressor.unused_data:
                raise ArtifactVerificationError(
                    f"{label} contains trailing data or multiple gzip members"
                )
        try:
            tail = decompressor.flush()
        except zlib.error as error:
            raise ArtifactVerificationError(f"{label} gzip trailer is invalid: {error}") from error
        decompressed_bytes += len(tail)
        pending += tail
        if decompressed_bytes > min(decompressed_cap, MAX_DECOMPRESSED_RAW_BYTES):
            raise ArtifactVerificationError(f"{label} exceeds its decompressed byte cap")
        if not decompressor.eof:
            raise ArtifactVerificationError(f"{label} gzip member is truncated")
        if decompressor.unused_data:
            raise ArtifactVerificationError(
                f"{label} contains trailing data or multiple gzip members"
            )
        if pending:
            raise ArtifactVerificationError(
                f"{label} must end with exactly one JSONL newline"
            )
    if path.stat().st_size != compressed_size:
        raise ArtifactVerificationError(f"{label} changed while being read")
    if not rows:
        raise ArtifactVerificationError(f"{label} must be non-empty")
    return rows, decompressed_bytes, maximum_audit_receipts_bytes


def _directory_size_bytes(path: Path) -> int:
    total = 0
    for candidate in path.rglob("*"):
        if candidate.is_symlink():
            raise ArtifactVerificationError("campaign artifacts may not contain symlinks")
        if candidate.is_file():
            total += candidate.stat().st_size
    return total


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_sha256(path: Path, cap: int = MAX_JSONL_BYTES) -> str:
    size = path.stat().st_size
    if size > cap:
        raise ArtifactVerificationError(f"{path} exceeds its sealed byte cap")
    digest = hashlib.sha256()
    observed = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            observed += len(block)
            if observed > cap:
                raise ArtifactVerificationError(f"{path} changed beyond its byte cap")
            digest.update(block)
    if observed != size or path.stat().st_size != size:
        raise ArtifactVerificationError(f"{path} changed while being hashed")
    return digest.hexdigest()


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_under(
    root: Path,
    value: Any,
    *,
    base: Path,
    label: str,
) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ArtifactVerificationError(f"{label} must be a non-empty path string")
    raw = Path(value)
    if not raw.is_absolute() and any(part == ".." for part in raw.parts):
        raise ArtifactVerificationError(f"{label} contains traversal")
    candidate = raw if raw.is_absolute() else base / raw
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ArtifactVerificationError(f"{label} cannot be resolved: {error}") from error
    if not _within(resolved, root):
        raise ArtifactVerificationError(f"{label} escapes artifact_root")
    if not resolved.is_file():
        raise ArtifactVerificationError(f"{label} is not a regular file")
    return resolved


def _registered_metrics(evidence: Mapping[str, Any]) -> dict[str, Any]:
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
        "ood_probe_accuracy_retention": float(evidence.get("ood_retention", 0.0)),
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


def _exposure_gate(episode: Mapping[str, Any]) -> dict[str, Any]:
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


def _derive_analysis_row(
    episode: Mapping[str, Any],
    recorded: Mapping[str, Any],
    *,
    verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = derive_probe_evidence(episode)
    qualification = qualify_emergence(evidence)
    if verification is None:
        verification = verify_episode(episode)
    return {
        "schema": CAMPAIGN_ROW_SCHEMA,
        "episode_id": episode.get("episode_id"),
        "episode_sha256": episode.get("episode_sha256"),
        "seed": int(episode.get("seed", -1)),
        "split": recorded.get("split"),
        "evidence_scope": (
            "resource_only"
            if recorded.get("split") == "profile"
            else (
                "smoke_only"
                if recorded.get("split") == "smoke"
                else "discovery"
            )
        ),
        "regime_id": recorded.get("regime_id"),
        "condition_id": recorded.get("condition_id"),
        "verification": dict(verification),
        "exposure_gate": _exposure_gate(episode),
        "evidence": evidence,
        "registered_metrics": _registered_metrics(evidence),
        "qualification": qualification,
    }


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


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
        "qualification_frequency": _mean(
            [
                float(row.get("qualification", {}).get("qualified") is True)
                for row in rows
            ]
        ),
        "mean_registered_metrics": {
            key: _mean(
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


def _derive_summary(
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
        "toolset": gym_toolset_card(),
    }


def _knowledge_card(summary: Mapping[str, Any]) -> str:
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


def _check(
    check_id: str,
    failures: Sequence[str],
    **facts: Any,
) -> dict[str, Any]:
    unique = list(dict.fromkeys(str(value) for value in failures))
    return {
        "check_id": check_id,
        "passed": not unique,
        "failures": unique,
        "facts": facts,
    }


def _verify_hash_ledger(
    *,
    workspace_root: Path,
    campaign_root: Path,
    ledger: Mapping[str, Any],
    campaign_hashes: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    failures: list[str] = []
    inputs_documents: dict[str, dict[str, Any]] = {}
    if ledger.get("schema") != HASHES_SCHEMA:
        failures.append(f"hashes.json schema must equal {HASHES_SCHEMA}")

    artifacts = ledger.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != LEDGER_ARTIFACT_FILES:
        failures.append("hashes.json artifacts must cover the exact retained artifact set")
    else:
        resolved_artifacts: set[Path] = set()
        for name in sorted(LEDGER_ARTIFACT_FILES):
            row = artifacts.get(name)
            label = f"hashes.artifacts.{name}"
            if not isinstance(row, Mapping) or set(row) != {"path", "sha256"}:
                failures.append(f"{label} must contain exactly path and sha256")
                continue
            try:
                path = _resolve_under(
                    campaign_root,
                    row.get("path"),
                    base=campaign_root,
                    label=label,
                )
            except ArtifactVerificationError as error:
                failures.append(str(error))
                continue
            expected_path = (campaign_root / name).resolve(strict=True)
            if path != expected_path:
                failures.append(f"{label}.path must resolve to {name}")
            if path in resolved_artifacts:
                failures.append(f"{label}.path aliases another artifact")
            resolved_artifacts.add(path)
            if row.get("sha256") != campaign_hashes.get(name):
                failures.append(f"{label}.sha256 does not match retained bytes")

    inputs = ledger.get("inputs")
    if not isinstance(inputs, Mapping) or set(inputs) != REQUIRED_INPUT_FILES:
        failures.append("hashes.json inputs must cover the exact registered input set")
    else:
        resolved_inputs: set[Path] = set()
        for name in sorted(REQUIRED_INPUT_FILES):
            row = inputs.get(name)
            label = f"hashes.inputs.{name}"
            if not isinstance(row, Mapping) or set(row) != {"path", "sha256"}:
                failures.append(f"{label} must contain exactly path and sha256")
                continue
            try:
                path = _resolve_under(
                    workspace_root,
                    row.get("path"),
                    base=workspace_root,
                    label=label,
                )
            except ArtifactVerificationError as error:
                failures.append(str(error))
                continue
            if path in resolved_inputs:
                failures.append(f"{label}.path aliases another input")
            resolved_inputs.add(path)
            try:
                digest = _file_sha256(path, MAX_JSON_BYTES)
                inputs_documents[name] = _read_json(path, label)
            except ArtifactVerificationError as error:
                failures.append(str(error))
                continue
            if row.get("sha256") != digest:
                failures.append(f"{label}.sha256 does not match retained bytes")

    sources = ledger.get("sources")
    normalized_sources: dict[str, Any] = {}
    if not isinstance(sources, Mapping) or not sources:
        failures.append("hashes.json sources must be a non-empty mapping")
    else:
        resolved_sources: set[Path] = set()
        for recorded_path, expected_digest in sources.items():
            label = f"hashes.sources.{recorded_path}"
            if not isinstance(recorded_path, str):
                failures.append("hashes.sources keys must be relative strings")
                continue
            normalized = recorded_path.replace("\\", "/")
            normalized_sources[normalized] = expected_digest
            try:
                path = _resolve_under(
                    workspace_root,
                    recorded_path,
                    base=workspace_root,
                    label=label,
                )
            except ArtifactVerificationError as error:
                failures.append(str(error))
                continue
            if path in resolved_sources:
                failures.append(f"{label} aliases another source")
            resolved_sources.add(path)
            try:
                digest = _file_sha256(path, MAX_JSON_BYTES)
            except ArtifactVerificationError as error:
                failures.append(str(error))
                continue
            if expected_digest != digest:
                failures.append(f"{label} does not match retained source bytes")
        missing_sources = sorted(REQUIRED_SOURCE_SUFFIXES - set(normalized_sources))
        if missing_sources:
            failures.append("hashes.json is missing required sources: " + ", ".join(missing_sources))
        try:
            source_tree_hash = canonical_sha256(dict(sources))
        except (TypeError, ValueError):
            source_tree_hash = None
            failures.append("hashes.sources is not finite canonical JSON")
        if ledger.get("source_tree_sha256") != source_tree_hash:
            failures.append("hashes.source_tree_sha256 does not match sources")
    return (
        _check(
            "hash_closure",
            failures,
            artifact_entries=(len(artifacts) if isinstance(artifacts, Mapping) else 0),
            input_entries=(len(inputs) if isinstance(inputs, Mapping) else 0),
            source_entries=(len(sources) if isinstance(sources, Mapping) else 0),
        ),
        inputs_documents,
    )


def _verify_matrix(
    *,
    episodes: Sequence[Mapping[str, Any]],
    analysis_rows: Sequence[Mapping[str, Any]],
    seed_manifest: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    failures: list[str] = []
    protocol = inputs.get("protocol_freeze.json", {})
    registry = inputs.get("condition_registry.json", {})
    experiment_manifest = inputs.get("manifest.json", {})
    if seed_manifest.get("schema") != SEED_MANIFEST_SCHEMA:
        failures.append(f"seed_manifest.schema must equal {SEED_MANIFEST_SCHEMA}")
    if protocol.get("status") != "discovery_only/unfrozen":
        failures.append("retained protocol must remain discovery_only/unfrozen")
    if seed_manifest.get("protocol_status") != protocol.get("status"):
        failures.append("seed manifest protocol_status differs from retained protocol")
    mode = seed_manifest.get("mode")
    if mode not in {"profile", "smoke", "calibration", "discovery"}:
        failures.append("seed manifest mode is invalid")
    output_modes = experiment_manifest.get("artifacts", {}).get(
        "output_directories_by_mode", {}
    )
    expected_output_binding = {
        "mode": mode,
        "registered_relative_directory": (
            output_modes.get(mode) if isinstance(output_modes, Mapping) else None
        ),
    }
    if seed_manifest.get("output_binding") != expected_output_binding:
        failures.append("seed manifest output binding differs from retained manifest")

    seed_access = protocol.get("seed_access", {})
    if not isinstance(seed_access, Mapping):
        seed_access = {}
        failures.append("protocol seed_access is missing")
    visible_smoke = list(seed_access.get("smoke_replay", []))
    visible_discovery = list(seed_access.get("discovery_visible", []))
    active_discovery = list(seed_access.get("discovery_active", []))
    reserve_discovery = list(
        seed_access.get("discovery_reserve_amendment_required", [])
    )
    if active_discovery + reserve_discovery != visible_discovery:
        failures.append(
            "active then reserve discovery seeds must exactly partition discovery_visible"
        )
    if set(active_discovery) & set(reserve_discovery):
        failures.append("active and reserve discovery seeds overlap")
    sealed_groups = {
        "confirmatory_hash_only": list(seed_access.get("confirmatory_sealed", [])),
        "holdout_hash_only": list(seed_access.get("holdout_sealed", [])),
        "ood_hash_only": list(seed_access.get("ood_sealed_uninspected", [])),
    }
    registered = seed_manifest.get("registered")
    expected_registered = {
        "smoke": visible_smoke,
        "discovery": visible_discovery,
        "discovery_active": active_discovery,
        "discovery_reserve_amendment_required": reserve_discovery,
        **{key: canonical_sha256(values) for key, values in sealed_groups.items()},
    }
    if registered != expected_registered:
        failures.append("seed manifest registered split receipt differs from protocol")

    regime_rows = protocol.get("discovery_campaign", {}).get("candidate_regimes", [])
    allowed_regimes = {
        row.get("id") for row in regime_rows if isinstance(row, Mapping)
    }
    condition_rows = registry.get("conditions", [])
    allowed_conditions = {
        row.get("id") for row in condition_rows if isinstance(row, Mapping)
    }
    executed = seed_manifest.get("executed")
    if not isinstance(executed, list):
        failures.append("seed_manifest.executed must be a list")
        executed = []
    if len(executed) != len(episodes) or len(analysis_rows) != len(episodes):
        failures.append("episode, analysis, and executed row counts must match")
    if len(episodes) > int(experiment_manifest.get("budget", {}).get("max_episodes", 0)):
        failures.append("episode count exceeds the retained experiment budget")
    hard_discovery_cap = int(
        protocol.get("discovery_campaign", {}).get("maximum_episodes", 0)
    )
    if hard_discovery_cap != 144 or len(episodes) > hard_discovery_cap:
        failures.append("retained campaign violates the hard 144-episode discovery cap")

    sealed_seeds = {
        int(seed)
        for values in sealed_groups.values()
        for seed in values
        if isinstance(seed, int) and not isinstance(seed, bool)
    }
    matrix: set[tuple[int, str, str]] = set()
    observed_seeds: set[int] = set()
    observed_regimes: set[str] = set()
    observed_conditions: set[str] = set()
    expected_split = mode if mode in {"profile", "smoke"} else "discovery"
    for index, (episode, row, execution) in enumerate(
        zip(episodes, analysis_rows, executed)
    ):
        label = f"executed[{index}]"
        if not isinstance(execution, Mapping):
            failures.append(f"{label} must be an object")
            continue
        required = {
            "episode_id",
            "episode_sha256",
            "split",
            "seed",
            "regime_id",
            "condition_id",
            "engine_config_sha256",
        }
        if set(execution) != required:
            failures.append(f"{label} must contain the exact execution receipt fields")
        seed = execution.get("seed")
        regime_id = execution.get("regime_id")
        condition_id = execution.get("condition_id")
        if not isinstance(seed, int) or isinstance(seed, bool):
            failures.append(f"{label}.seed must be an integer")
            continue
        if seed in sealed_seeds:
            failures.append(f"{label} accesses a sealed confirmatory/holdout/OOD seed")
        allowed_seeds = (
            visible_smoke if mode in {"profile", "smoke"} else active_discovery
        )
        if seed not in allowed_seeds:
            failures.append(f"{label}.seed is outside its visible split")
        if execution.get("split") != expected_split:
            failures.append(f"{label}.split differs from campaign mode")
        if regime_id not in allowed_regimes:
            failures.append(f"{label}.regime_id is not registered")
        if condition_id not in allowed_conditions:
            failures.append(f"{label}.condition_id is not registered")
        if expected_split == "discovery" and condition_id != "adaptive_dual_archive":
            failures.append(f"{label} uses a non-discovery condition while unfrozen")
        if episode.get("episode_id") != execution.get("episode_id"):
            failures.append(f"{label}.episode_id differs from raw episode")
        if episode.get("episode_sha256") != execution.get("episode_sha256"):
            failures.append(f"{label}.episode_sha256 differs from raw episode")
        if episode.get("seed") != seed:
            failures.append(f"{label}.seed differs from raw episode")
        for key in ("episode_id", "episode_sha256", "seed"):
            if row.get(key) != execution.get(key):
                failures.append(f"analysis_rows[{index}].{key} differs from execution")
        for key in ("split", "regime_id", "condition_id"):
            if row.get(key) != execution.get(key):
                failures.append(f"analysis_rows[{index}].{key} differs from execution")
        triple = (seed, str(regime_id), str(condition_id))
        if triple in matrix:
            failures.append(f"{label} duplicates a seed/regime/condition cell")
        matrix.add(triple)
        observed_seeds.add(seed)
        observed_regimes.add(str(regime_id))
        observed_conditions.add(str(condition_id))
    expected_matrix = {
        (seed, regime, condition)
        for seed in observed_seeds
        for regime in observed_regimes
        for condition in observed_conditions
    }
    if matrix != expected_matrix:
        failures.append("executed rows do not form a complete observed campaign matrix")
    if mode == "discovery":
        registered_matrix = {
            (int(seed), str(regime), "adaptive_dual_archive")
            for seed in active_discovery
            for regime in allowed_regimes
        }
        if matrix != registered_matrix or len(matrix) != 72:
            failures.append(
                "discovery execution is not the exact registered 72-cell active matrix"
            )
    if observed_seeds & {int(seed) for seed in reserve_discovery}:
        failures.append("executed rows access amendment-required reserve discovery seeds")
    return _check(
        "split_matrix",
        failures,
        mode=mode,
        matrix_cells=len(matrix),
        visible_split=expected_split,
    )


def _verify_receipt(
    *,
    receipt: Mapping[str, Any],
    seed_manifest: Mapping[str, Any],
    episode_count: int,
    campaign_hashes: Mapping[str, str],
) -> dict[str, Any]:
    failures: list[str] = []
    if receipt.get("schema") != RECEIPT_SCHEMA:
        failures.append(f"receipt.schema must equal {RECEIPT_SCHEMA}")
    if receipt.get("exit_status") != "ok":
        failures.append("receipt exit_status must be ok")
    if receipt.get("episode_count") != episode_count:
        failures.append("receipt episode_count differs from raw episodes")
    if receipt.get("world_executions") != episode_count + 1:
        failures.append("receipt world_executions must count episodes plus exact replay")
    if receipt.get("deterministic_replay") is not True:
        failures.append("receipt must record exact deterministic replay")
    if receipt.get("external_io") is not False:
        failures.append("receipt external_io must be false")
    if receipt.get("subprocess_used") is not False:
        failures.append("receipt subprocess_used must be false")
    if receipt.get("mode") != seed_manifest.get("mode"):
        failures.append("receipt mode differs from seed manifest")
    mode = seed_manifest.get("mode")
    expected_split = mode if mode in {"profile", "smoke"} else "discovery"
    if receipt.get("split") != expected_split:
        failures.append("receipt split differs from mode")
    if receipt.get("protocol_status") != seed_manifest.get("protocol_status"):
        failures.append("receipt protocol_status differs from seed manifest")
    if receipt.get("output_binding") != seed_manifest.get("output_binding"):
        failures.append("receipt output binding differs from seed manifest")
    if receipt.get("discovery_preflight_gate") != seed_manifest.get(
        "discovery_preflight_gate"
    ):
        failures.append("receipt discovery preflight differs from seed manifest")
    gate = receipt.get("discovery_preflight_gate")
    if mode == "discovery":
        if not isinstance(gate, Mapping) or gate.get("passed") is not True:
            failures.append("discovery receipt lacks a passing resource preflight")
    elif gate is not None:
        failures.append("non-discovery receipt must not carry a discovery preflight")
    artifact_hashes = receipt.get("artifact_sha256")
    if not isinstance(artifact_hashes, Mapping) or set(artifact_hashes) != RECEIPT_ARTIFACT_FILES:
        failures.append("receipt artifact_sha256 must cover the exact pre-receipt artifacts")
    else:
        for name in sorted(RECEIPT_ARTIFACT_FILES):
            if artifact_hashes.get(name) != campaign_hashes.get(name):
                failures.append(f"receipt artifact_sha256.{name} does not match bytes")
    return _check(
        "campaign_receipt",
        failures,
        deterministic_replay=receipt.get("deterministic_replay"),
    )


def _verify_resources(
    *,
    receipt: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
    campaign_root: Path,
    raw_path: Path,
    raw_decompressed_bytes: int,
    maximum_audit_receipts_bytes: int,
) -> dict[str, Any]:
    """Independently enforce registered and verifier-hard resource boundaries."""

    failures: list[str] = []
    manifest_budget = inputs.get("manifest.json", {}).get("budget", {})
    safety_caps = inputs.get("safety_boundary.json", {}).get("resource_caps", {})
    if not isinstance(manifest_budget, Mapping):
        manifest_budget = {}
    if not isinstance(safety_caps, Mapping):
        safety_caps = {}
    expected_caps = {
        "max_wall_seconds": float(manifest_budget.get("max_wall_seconds", 0)),
        "max_peak_rss_bytes": int(manifest_budget.get("max_ram_mb", 0))
        * 1024
        * 1024,
        "max_compressed_artifact_bytes": int(manifest_budget.get("max_disk_mb", 0))
        * 1024
        * 1024,
        "max_decompressed_raw_bytes": int(
            manifest_budget.get("max_decompressed_raw_mb", 0)
        )
        * 1024
        * 1024,
        "max_canonical_audit_receipts_bytes_per_episode": int(
            manifest_budget.get(
                "max_canonical_audit_receipts_bytes_per_episode", 0
            )
        ),
    }
    safety_expected = {
        "max_wall_seconds": float(safety_caps.get("maximum_wall_seconds", 0)),
        "max_peak_rss_bytes": int(safety_caps.get("maximum_ram_mb", 0))
        * 1024
        * 1024,
        "max_compressed_artifact_bytes": int(
            safety_caps.get("maximum_disk_mb", 0)
        )
        * 1024
        * 1024,
        "max_decompressed_raw_bytes": int(
            safety_caps.get("maximum_decompressed_raw_mb", 0)
        )
        * 1024
        * 1024,
        "max_canonical_audit_receipts_bytes_per_episode": int(
            safety_caps.get(
                "maximum_canonical_audit_receipts_bytes_per_episode", 0
            )
        ),
    }
    if expected_caps != safety_expected:
        failures.append("manifest and safety resource caps differ")
    if expected_caps["max_compressed_artifact_bytes"] > MAX_TOTAL_ARTIFACT_BYTES:
        failures.append("registered compressed artifact cap exceeds verifier hard cap")
    if expected_caps["max_decompressed_raw_bytes"] > MAX_DECOMPRESSED_RAW_BYTES:
        failures.append("registered decompressed raw cap exceeds verifier hard cap")
    if (
        expected_caps["max_canonical_audit_receipts_bytes_per_episode"]
        > MAX_AUDIT_RECEIPTS_BYTES
    ):
        failures.append("registered audit_receipts cap exceeds verifier hard cap")
    if any(value <= 0 for value in expected_caps.values()):
        failures.append("registered resource caps must all be positive")

    resource_receipt = receipt.get("resource_receipt", {})
    if not isinstance(resource_receipt, Mapping):
        resource_receipt = {}
        failures.append("receipt.resource_receipt must be an object")
    if resource_receipt.get("caps") != expected_caps:
        failures.append("resource receipt caps differ from retained registration")
    observed = resource_receipt.get("observed", {})
    if not isinstance(observed, Mapping):
        observed = {}
        failures.append("resource receipt observed values must be an object")
    try:
        actual_total_bytes = _directory_size_bytes(campaign_root)
    except ArtifactVerificationError as error:
        actual_total_bytes = -1
        failures.append(str(error))
    actual_compressed_raw_bytes = raw_path.stat().st_size
    expected_observed = {
        "wall_seconds": observed.get("wall_seconds"),
        "peak_rss_bytes": observed.get("peak_rss_bytes"),
        "compressed_artifact_bytes": actual_total_bytes,
        "raw_decompressed_bytes": raw_decompressed_bytes,
        "maximum_canonical_audit_receipts_bytes": maximum_audit_receipts_bytes,
    }
    if set(observed) != set(expected_observed):
        failures.append("resource receipt observed fields are not exact")
    if observed.get("compressed_artifact_bytes") != actual_total_bytes:
        failures.append("resource receipt compressed artifact bytes differ from directory")
    if observed.get("raw_decompressed_bytes") != raw_decompressed_bytes:
        failures.append("resource receipt decompressed raw bytes differ from independent count")
    if (
        observed.get("maximum_canonical_audit_receipts_bytes")
        != maximum_audit_receipts_bytes
    ):
        failures.append(
            "resource receipt maximum canonical audit_receipts bytes differ from independent count"
        )
    if receipt.get("runtime_seconds") != observed.get("wall_seconds"):
        failures.append("receipt runtime_seconds differs from resource wall receipt")
    if receipt.get("resource_only_profile") is not (receipt.get("mode") == "profile"):
        failures.append("receipt resource_only_profile differs from mode")
    numeric_observed: dict[str, float] = {}
    for key, value in observed.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            failures.append(f"resource receipt observed.{key} must be nonnegative numeric")
        else:
            numeric_observed[str(key)] = float(value)
    for observed_key, cap_key in (
        ("wall_seconds", "max_wall_seconds"),
        ("peak_rss_bytes", "max_peak_rss_bytes"),
        ("compressed_artifact_bytes", "max_compressed_artifact_bytes"),
        ("raw_decompressed_bytes", "max_decompressed_raw_bytes"),
        (
            "maximum_canonical_audit_receipts_bytes",
            "max_canonical_audit_receipts_bytes_per_episode",
        ),
    ):
        if numeric_observed.get(observed_key, float("inf")) > expected_caps[cap_key]:
            failures.append(f"resource receipt exceeds {cap_key}")
    if actual_compressed_raw_bytes > expected_caps["max_compressed_artifact_bytes"]:
        failures.append("compressed raw artifact exceeds registered compressed disk cap")

    checks_passed = resource_receipt.get("checks_passed")
    if checks_passed != {
        "wall": True,
        "peak_rss": True,
        "compressed_disk": True,
        "decompressed_raw": True,
        "per_episode_audit_receipts": True,
    }:
        failures.append("resource receipt must record all four cap checks as passed")
    compression = resource_receipt.get("raw_compression")
    if compression != {
        "file": RAW_EPISODES_FILE,
        "format": "gzip",
        "compression_level": 1,
        "mtime": 0,
        "filename_header": "",
        "jsonl_encoding": "utf-8",
    }:
        failures.append("resource receipt raw compression contract differs")
    if resource_receipt.get("rss_measurement") != (
        "process_lifetime_peak_working_set_or_ru_maxrss"
    ):
        failures.append("resource receipt peak-RSS measurement is not registered")
    if resource_receipt.get("postflight_enforced_after_all_artifact_phases") is not True:
        failures.append("resource receipt does not assert all-phase postflight enforcement")
    phase_checks = resource_receipt.get("phase_checks")
    if not isinstance(phase_checks, list) or not phase_checks:
        failures.append("resource receipt phase_checks must be nonempty")
    else:
        for index, check in enumerate(phase_checks):
            if not isinstance(check, Mapping) or check.get("passed") is not True:
                failures.append(f"resource phase check {index} did not pass")
                continue
            if check.get("failed_caps") != []:
                failures.append(f"resource phase check {index} records failed caps")
            for observed_key, cap_key in (
                ("wall_seconds", "max_wall_seconds"),
                ("peak_rss_bytes", "max_peak_rss_bytes"),
                (
                    "compressed_artifact_bytes",
                    "max_compressed_artifact_bytes",
                ),
                ("raw_decompressed_bytes", "max_decompressed_raw_bytes"),
                (
                    "maximum_canonical_audit_receipts_bytes",
                    "max_canonical_audit_receipts_bytes_per_episode",
                ),
            ):
                value = check.get(observed_key)
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or value < 0
                    or value > expected_caps[cap_key]
                ):
                    failures.append(
                        f"resource phase check {index}.{observed_key} violates its cap"
                    )
    profile = resource_receipt.get("traced_profile")
    mode = receipt.get("mode")
    if not isinstance(profile, Mapping):
        failures.append("resource receipt traced_profile must be an object")
    elif mode == "profile":
        if (
            profile.get("enabled") is not True
            or profile.get("seed") != 17
            or not isinstance(profile.get("python_allocation_peak_bytes"), int)
            or profile.get("eligible_as_evidence") is not False
        ):
            failures.append("profile mode lacks its seed-17 non-evidence traced receipt")
    elif (
        profile.get("enabled") is not False
        or profile.get("python_allocation_peak_bytes") is not None
    ):
        failures.append("production mode must not enable Python allocation tracing")
    return _check(
        "resource_bounds",
        failures,
        actual_total_bytes=actual_total_bytes,
        compressed_raw_bytes=actual_compressed_raw_bytes,
        decompressed_raw_bytes=raw_decompressed_bytes,
        maximum_audit_receipts_bytes=maximum_audit_receipts_bytes,
    )


def _verify_discovery_preflight(
    *,
    receipt: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
    workspace_root: Path,
    campaign_root: Path,
) -> dict[str, Any]:
    mode = receipt.get("mode")
    if mode != "discovery":
        failures = (
            []
            if receipt.get("discovery_preflight_gate") is None
            else ["non-discovery artifact carries a discovery preflight"]
        )
        return _check("discovery_preflight", failures, required=False)

    failures: list[str] = []
    gate = receipt.get("discovery_preflight_gate")
    if not isinstance(gate, Mapping):
        return _check(
            "discovery_preflight",
            ["discovery preflight receipt is missing"],
            required=True,
        )
    manifest = inputs.get("manifest.json", {})
    artifacts = manifest.get("artifacts", {})
    outputs = artifacts.get("output_directories_by_mode", {}) if isinstance(artifacts, Mapping) else {}
    smoke_relative = outputs.get("smoke") if isinstance(outputs, Mapping) else None
    if (
        not isinstance(smoke_relative, str)
        or not smoke_relative
        or Path(smoke_relative).is_absolute()
        or ".." in Path(smoke_relative).parts
    ):
        return _check(
            "discovery_preflight",
            ["retained manifest smoke output binding is invalid"],
            required=True,
        )
    try:
        smoke_root = (workspace_root / smoke_relative).resolve(strict=True)
        if not smoke_root.is_dir() or smoke_root == campaign_root:
            raise ArtifactVerificationError("registered smoke root is invalid")
        smoke_receipt_path = smoke_root / "receipt.json"
        smoke_hashes_path = smoke_root / "hashes.json"
        smoke_receipt = _read_json(smoke_receipt_path, "smoke/receipt.json")
        smoke_report = verify_artifact_bundle(
            smoke_root, workspace_root, replay=False
        )
        if smoke_report.get("accepted") is not True:
            failures.append("registered smoke artifact fails independent verification")
        if (
            smoke_receipt.get("mode") != "smoke"
            or smoke_receipt.get("episode_count") != 1
            or smoke_receipt.get("world_executions") != 2
            or smoke_receipt.get("resource_only_profile") is not False
            or smoke_receipt.get("deterministic_replay") is not True
        ):
            failures.append("registered smoke is not one untraced episode plus replay")
        resources = smoke_receipt.get("resource_receipt", {})
        observed = resources.get("observed", {}) if isinstance(resources, Mapping) else {}
        budget = manifest.get("budget", {})
        if not isinstance(observed, Mapping) or not isinstance(budget, Mapping):
            raise ArtifactVerificationError("smoke resource projection inputs are missing")
        projected = {
            "wall_seconds": round(
                float(smoke_receipt["runtime_seconds"])
                / float(smoke_receipt["world_executions"])
                * DISCOVERY_WORLD_EQUIVALENTS,
                6,
            ),
            "compressed_artifact_bytes": int(
                observed["compressed_artifact_bytes"]
            )
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
        checks = {key: projected[key] < thresholds[key] for key in projected}
        expected = {
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
            "smoke_receipt_sha256": _file_sha256(
                smoke_receipt_path, MAX_JSON_BYTES
            ),
            "smoke_hashes_sha256": _file_sha256(
                smoke_hashes_path, MAX_JSON_BYTES
            ),
        }
        if dict(gate) != expected:
            failures.append("discovery preflight differs from independent projection")
        if not expected["passed"]:
            failures.append("discovery projection is not below 80% of every cap")
    except (ArtifactVerificationError, KeyError, OSError, TypeError, ValueError) as error:
        failures.append(f"discovery preflight verification failed: {error}")
    return _check(
        "discovery_preflight",
        failures,
        required=True,
        world_equivalents=DISCOVERY_WORLD_EQUIVALENTS,
        artifact_multiplier=DISCOVERY_ARTIFACT_MULTIPLIER,
    )


def _optional_replay(
    *,
    requested: bool,
    episodes: Sequence[Mapping[str, Any]],
    seed_manifest: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not requested:
        return _check("optional_replay", [], requested=False, replayed=0)
    failures: list[str] = []
    replayed = 0
    try:
        from stegohive_v1.campaign import _apply_regime, _condition, _config_projection
        from stegohive_v1.environment import run_world

        executions = seed_manifest.get("executed", [])
        protocol = inputs["protocol_freeze.json"]
        regimes = {
            row["id"]: row
            for row in protocol["discovery_campaign"]["candidate_regimes"]
        }
        if not episodes or not isinstance(executions, list) or not executions:
            raise ArtifactVerificationError("no retained episode is available to replay")
        execution = executions[0]
        if not isinstance(execution, Mapping):
            raise ArtifactVerificationError("first execution receipt is malformed")
        regime = regimes.get(execution.get("regime_id"))
        if regime is None:
            raise ArtifactVerificationError("first replay regime is not registered")
        base = _config_projection(inputs["config.json"])
        replay = run_world(
            config=_apply_regime(base, regime),
            condition=_condition(str(execution.get("condition_id"))),
            seed=int(execution.get("seed")),
        )
        replayed = 1
        if replay != episodes[0]:
            failures.append("fresh local replay differs from the first raw episode")
    except Exception as error:
        failures.append(f"optional local replay failed: {type(error).__name__}: {error}")
    return _check("optional_replay", failures, requested=True, replayed=replayed)


def verify_artifact_bundle(
    campaign_root: str | Path,
    workspace_root: str | Path | None = None,
    *,
    replay: bool = False,
) -> dict[str, Any]:
    """Verify a retained campaign and every path in its hash ledger.

    The two roots are intentionally separate: artifacts may live on a data
    volume or junction target while registered inputs and source receipts live
    under ``workspace_root``.  No ledger class may cross its assigned root.
    ``replay=True`` additionally reruns the first retained episode in memory.
    """

    checks: dict[str, dict[str, Any]] = {}
    campaign_text: str | None = None
    workspace_text: str | None = None
    try:
        if workspace_root is None:
            raise ArtifactVerificationError("workspace_root must be supplied explicitly")
        workspace = Path(workspace_root).resolve(strict=True)
        if not workspace.is_dir():
            raise ArtifactVerificationError("workspace_root must be an existing directory")
        workspace_text = str(workspace)
        campaign = Path(campaign_root).resolve(strict=True)
        if not campaign.is_dir():
            raise ArtifactVerificationError("campaign_root must be an existing directory")
        campaign_text = str(campaign)

        required_failures: list[str] = []
        paths: dict[str, Path] = {}
        for name in REQUIRED_CAMPAIGN_FILES:
            try:
                path = (campaign / name).resolve(strict=True)
            except (OSError, RuntimeError) as error:
                required_failures.append(f"missing required artifact {name}: {error}")
                continue
            if not _within(path, campaign) or not path.is_file():
                required_failures.append(f"required artifact {name} is not a local file")
                continue
            paths[name] = path
        retained_files = {
            candidate.relative_to(campaign).as_posix()
            for candidate in campaign.rglob("*")
            if candidate.is_file()
        }
        if retained_files != set(REQUIRED_CAMPAIGN_FILES):
            required_failures.append(
                "campaign directory must contain the exact registered artifact files"
            )
        checks["required_files"] = _check(
            "required_files",
            required_failures,
            required=len(REQUIRED_CAMPAIGN_FILES),
            found=len(paths),
        )
        if required_failures:
            raise ArtifactVerificationError("required campaign files are incomplete")

        campaign_hashes = {
            name: _file_sha256(
                path,
                (
                    MAX_KNOWLEDGE_BYTES
                    if name == "knowledge_card.md"
                    else (
                        MAX_COMPRESSED_RAW_BYTES
                        if name == RAW_EPISODES_FILE
                        else MAX_JSONL_BYTES
                    )
                ),
            )
            for name, path in paths.items()
        }
        analysis_rows = _read_jsonl(
            paths["analysis_rows.jsonl"], "analysis_rows.jsonl"
        )
        seed_manifest = _read_json(paths["seed_manifest.json"], "seed_manifest.json")
        summary = _read_json(paths["summary.json"], "summary.json")
        receipt = _read_json(paths["receipt.json"], "receipt.json")
        hashes = _read_json(paths["hashes.json"], "hashes.json")
        knowledge_bytes = _read_bytes(
            paths["knowledge_card.md"], MAX_KNOWLEDGE_BYTES, "knowledge_card.md"
        )

        hash_check, inputs = _verify_hash_ledger(
            workspace_root=workspace,
            campaign_root=campaign,
            ledger=hashes,
            campaign_hashes=campaign_hashes,
        )
        checks["hash_closure"] = hash_check

        manifest_budget = inputs.get("manifest.json", {}).get("budget", {})
        if not isinstance(manifest_budget, Mapping):
            raise ArtifactVerificationError("retained manifest budget is missing")
        registered_compressed_cap = int(manifest_budget.get("max_disk_mb", 0)) * 1024 * 1024
        registered_decompressed_cap = (
            int(manifest_budget.get("max_decompressed_raw_mb", 0)) * 1024 * 1024
        )
        registered_audit_cap = int(
            manifest_budget.get(
                "max_canonical_audit_receipts_bytes_per_episode", 0
            )
        )
        if (
            registered_compressed_cap <= 0
            or registered_decompressed_cap <= 0
            or registered_audit_cap <= 0
        ):
            raise ArtifactVerificationError("retained raw resource caps must be positive")
        episodes, raw_decompressed_bytes, maximum_audit_receipts_bytes = _read_gzip_jsonl(
            paths[RAW_EPISODES_FILE],
            RAW_EPISODES_FILE,
            compressed_cap=registered_compressed_cap,
            decompressed_cap=registered_decompressed_cap,
            audit_receipts_cap=registered_audit_cap,
        )

        episode_failures: list[str] = []
        episode_reports: list[dict[str, Any]] = []
        verification_by_id: dict[str, Mapping[str, Any]] = {}
        seen_episode_ids: set[str] = set()
        for index, episode in enumerate(episodes):
            verification = verify_episode(episode)
            episode_id = episode.get("episode_id")
            episode_reports.append(
                {
                    "index": index,
                    "episode_id": episode_id,
                    "accepted": verification["accepted"],
                    "failed_required_verifiers": verification[
                        "failed_required_verifiers"
                    ],
                }
            )
            if not verification["accepted"]:
                episode_failures.append(
                    f"episode {episode_id!r} failed: "
                    + ", ".join(verification["failed_required_verifiers"])
                )
            if not isinstance(episode_id, str) or episode_id in seen_episode_ids:
                episode_failures.append(f"raw episode row {index} has a duplicate/invalid id")
            elif isinstance(episode_id, str):
                seen_episode_ids.add(episode_id)
                verification_by_id[episode_id] = verification
        checks["episode_verification"] = _check(
            "episode_verification",
            episode_failures,
            episode_count=len(episodes),
            episodes=episode_reports,
        )

        analysis_failures: list[str] = []
        if len(analysis_rows) != len(episodes):
            analysis_failures.append("analysis row count differs from raw episodes")
        analysis_by_id: dict[str, Mapping[str, Any]] = {}
        for index, row in enumerate(analysis_rows):
            episode_id = row.get("episode_id")
            if not isinstance(episode_id, str) or episode_id in analysis_by_id:
                analysis_failures.append(
                    f"analysis row {index} has a duplicate/invalid episode_id"
                )
            else:
                analysis_by_id[episode_id] = row
        rederived_rows: list[dict[str, Any]] = []
        for episode in episodes:
            episode_id = episode.get("episode_id")
            recorded = analysis_by_id.get(str(episode_id))
            if recorded is None:
                analysis_failures.append(f"episode {episode_id!r} has no analysis row")
                continue
            verification = verification_by_id.get(str(episode_id))
            if verification is None:
                analysis_failures.append(
                    f"episode {episode_id!r} has no unique verification receipt"
                )
                continue
            expected = _derive_analysis_row(
                episode, recorded, verification=verification
            )
            rederived_rows.append(expected)
            if dict(recorded) != expected:
                analysis_failures.append(
                    f"analysis for episode {episode_id!r} differs from independent derivation"
                )
        checks["analysis_rederivation"] = _check(
            "analysis_rederivation",
            analysis_failures,
            rows=len(rederived_rows),
        )

        checks["split_matrix"] = _verify_matrix(
            episodes=episodes,
            analysis_rows=analysis_rows,
            seed_manifest=seed_manifest,
            inputs=inputs,
        )

        protocol = inputs.get("protocol_freeze.json", {})
        expected_summary = _derive_summary(
            rederived_rows,
            mode=str(seed_manifest.get("mode")),
            deterministic_replay=receipt.get("deterministic_replay") is True,
            expected_discovery_seeds=len(
                protocol.get("seed_access", {}).get("discovery_active", [])
            ),
            expected_regimes=len(
                protocol.get("discovery_campaign", {}).get("candidate_regimes", [])
            ),
        )
        summary_failures = (
            [] if summary == expected_summary else ["summary differs from independent derivation"]
        )
        checks["summary_rederivation"] = _check(
            "summary_rederivation", summary_failures
        )
        checks["campaign_receipt"] = _verify_receipt(
            receipt=receipt,
            seed_manifest=seed_manifest,
            episode_count=len(episodes),
            campaign_hashes=campaign_hashes,
        )
        checks["resource_bounds"] = _verify_resources(
            receipt=receipt,
            inputs=inputs,
            campaign_root=campaign,
            raw_path=paths[RAW_EPISODES_FILE],
            raw_decompressed_bytes=raw_decompressed_bytes,
            maximum_audit_receipts_bytes=maximum_audit_receipts_bytes,
        )
        checks["discovery_preflight"] = _verify_discovery_preflight(
            receipt=receipt,
            inputs=inputs,
            workspace_root=workspace,
            campaign_root=campaign,
        )
        try:
            knowledge_text = knowledge_bytes.decode("utf-8-sig").replace("\r\n", "\n")
        except UnicodeDecodeError:
            knowledge_text = ""
        knowledge_failures = (
            []
            if knowledge_text == _knowledge_card(expected_summary)
            else ["knowledge_card.md differs from the rederived summary card"]
        )
        checks["knowledge_card"] = _check("knowledge_card", knowledge_failures)
        checks["optional_replay"] = _optional_replay(
            requested=replay,
            episodes=episodes,
            seed_manifest=seed_manifest,
            inputs=inputs,
        )
    except (ArtifactVerificationError, OSError, TypeError, ValueError) as error:
        checks.setdefault(
            "boundary",
            _check("boundary", [f"artifact verification stopped: {error}"]),
        )

    failed_checks = [name for name, check in checks.items() if not check["passed"]]
    failures = [
        failure
        for check in checks.values()
        for failure in check.get("failures", [])
    ]
    return {
        "schema": REPORT_SCHEMA,
        "accepted": not failed_checks,
        "campaign_root": campaign_text,
        "workspace_root": workspace_text,
        "checks": checks,
        "failed_checks": failed_checks,
        "failures": list(dict.fromkeys(failures)),
        "local_artifact_files_only": True,
        "external_io_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root", type=Path)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    arguments = parser.parse_args()
    report = verify_artifact_bundle(
        arguments.campaign_root,
        arguments.workspace_root,
        replay=arguments.replay,
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    raise SystemExit(0 if report["accepted"] else 1)


if __name__ == "__main__":
    main()


__all__ = ["REPORT_SCHEMA", "verify_artifact_bundle"]
