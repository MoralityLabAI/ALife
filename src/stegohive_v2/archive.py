"""Read-only lookup for exact retained StegoHive world records."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterator


CAMPAIGNS = {
    "V2": "stegohive_gym_v2_discovery",
    "V3": "stegohive_gym_v3_discovery",
    "V6": "stegohive_gym_v6_local_peak_confirmation",
    "V7": "stegohive_gym_v7_horizon_rate_factorial",
    "V8": "stegohive_gym_v8_credit_path_factorial",
    "V9": "stegohive_gym_v9_reproduction_role_factorial",
}


def default_results_root() -> Path:
    return Path(__file__).resolve().parents[2] / "results"


def retained_path(version: str, results_root: Path | None = None) -> Path:
    normalized = version.upper()
    if normalized not in CAMPAIGNS:
        raise ValueError(f"retained replay is unavailable for version {version!r}")
    root = default_results_root() if results_root is None else Path(results_root)
    return root / CAMPAIGNS[normalized] / "raw_episodes.jsonl.gz"


def iter_retained_records(
    version: str, results_root: Path | None = None
) -> Iterator[dict[str, Any]]:
    path = retained_path(version, results_root)
    if not path.is_file():
        raise FileNotFoundError(
            f"retained {version.upper()} records are not mounted at {path}"
        )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_retained_record(
    version: str,
    seed: int,
    *,
    condition_id: str | None = None,
    order: int | None = None,
    results_root: Path | None = None,
) -> dict[str, Any]:
    """Load one byte-preserved record by its recorded identity."""

    matches: list[dict[str, Any]] = []
    for record in iter_retained_records(version, results_root):
        identity = record.get("identity", {})
        if int(identity.get("seed", record.get("episode", {}).get("seed", -1))) != seed:
            continue
        recorded_condition = identity.get("condition_id") or record.get("episode", {}).get(
            "condition", {}
        ).get("id")
        if condition_id is not None and recorded_condition != condition_id:
            continue
        if order is not None and int(identity.get("order", -1)) != order:
            continue
        matches.append(record)
        if order is not None:
            break
    if not matches:
        qualifier = f", condition={condition_id}" if condition_id else ""
        raise LookupError(f"no retained {version.upper()} record for seed={seed}{qualifier}")
    return matches[0]


__all__ = [
    "CAMPAIGNS",
    "default_results_root",
    "iter_retained_records",
    "load_retained_record",
    "retained_path",
]
