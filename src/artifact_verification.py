"""Portable provenance helpers shared by ALife artifact verifiers."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_parts(value: str | Path) -> tuple[str, ...]:
    text = str(value).replace("\\", "/")
    parts = []
    for part in text.split("/"):
        if not part or part in {".", ".."} or part.endswith(":"):
            continue
        parts.append(part)
    return tuple(parts)


def _endswith_parts(path: Path, suffix: Sequence[str]) -> bool:
    parts = tuple(part.casefold() for part in path.parts)
    wanted = tuple(part.casefold() for part in suffix)
    return len(parts) >= len(wanted) and parts[-len(wanted) :] == wanted


def project_search_roots(verifier_file: Path, artifact_root: Path) -> list[Path]:
    """Return bounded roots that look like a source/bundle project, never a whole drive."""

    candidates = [verifier_file.resolve().parents[1]]
    for ancestor in [artifact_root.resolve(), *artifact_root.resolve().parents[:3]]:
        if (ancestor / "src").is_dir() and (ancestor / "results").is_dir():
            candidates.append(ancestor)
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(candidate.resolve())
    return unique


def resolve_recorded_file(
    recorded_path: str | Path,
    expected_sha256: str,
    *,
    search_roots: Iterable[Path],
    suffix_parts: int,
    allow_recorded_path: bool = True,
) -> dict[str, Any]:
    """Resolve provenance by exact path or one unique multi-component suffix.

    Basename-only lookup is deliberately forbidden. Ambiguity is returned as a
    first-class failure instead of selecting a hash-matching or first candidate.
    """

    if suffix_parts < 2:
        raise ValueError("portable artifact resolution requires at least two suffix components")
    recorded = Path(str(recorded_path))
    expected = str(expected_sha256).lower()
    if allow_recorded_path and recorded.is_file():
        actual = sha256_file(recorded)
        return {
            "status": "resolved" if actual.lower() == expected else "hash_mismatch",
            "method": "recorded_path",
            "recorded_path": str(recorded_path),
            "resolved_path": str(recorded.resolve()),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "candidates": [str(recorded.resolve())],
        }

    recorded_parts = _normalized_parts(recorded_path)
    if len(recorded_parts) < suffix_parts:
        return {
            "status": "insufficient_suffix",
            "method": "unique_suffix",
            "recorded_path": str(recorded_path),
            "required_suffix_parts": suffix_parts,
            "available_parts": list(recorded_parts),
            "candidates": [],
        }
    suffix = recorded_parts[-suffix_parts:]
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in search_roots:
        root = root.resolve()
        if not root.is_dir():
            continue
        # pathlib.Path.rglob follows Windows directory junctions on supported
        # Python versions. Result directories in this repo are deliberately
        # junctioned to another drive, so an unrestricted rglob can escape the
        # bounded project tree and spend minutes searching unrelated artifacts.
        # os.walk plus explicit reparse-point pruning preserves unique-suffix
        # ambiguity checks while keeping portable verification project-local.
        discovered: list[Path] = []
        for directory, child_dirs, files in os.walk(root, followlinks=False):
            kept_dirs: list[str] = []
            for name in child_dirs:
                child = Path(directory) / name
                try:
                    attributes = int(getattr(os.lstat(child), "st_file_attributes", 0))
                except OSError:
                    continue
                if attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                    continue
                kept_dirs.append(name)
            child_dirs[:] = kept_dirs
            if suffix[-1] in files:
                discovered.append(Path(directory) / suffix[-1])
        for candidate in discovered:
            if not candidate.is_file() or not _endswith_parts(candidate, suffix):
                continue
            key = str(candidate.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                candidates.append(candidate.resolve())
    candidates.sort(key=lambda path: str(path).casefold())
    base = {
        "method": "unique_suffix",
        "recorded_path": str(recorded_path),
        "suffix": "/".join(suffix),
        "expected_sha256": expected,
        "candidates": [str(path) for path in candidates],
    }
    if not candidates:
        return {**base, "status": "missing"}
    if len(candidates) > 1:
        return {**base, "status": "ambiguous"}
    actual = sha256_file(candidates[0])
    return {
        **base,
        "status": "resolved" if actual.lower() == expected else "hash_mismatch",
        "resolved_path": str(candidates[0]),
        "actual_sha256": actual,
    }


def _runtime_environment(package_names: Sequence[str]) -> dict[str, Any]:
    try:
        import psutil

        cpu_logical = psutil.cpu_count(logical=True)
        ram_total_mb = psutil.virtual_memory().total / (1024 * 1024)
    except ImportError:
        cpu_logical = os.cpu_count()
        ram_total_mb = None
    result: dict[str, Any] = {
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_logical": cpu_logical,
        "ram_total_mb": ram_total_mb,
    }
    for package in package_names:
        module = importlib.import_module(package)
        result[package] = getattr(module, "__version__", None)
    return result


def audit_runtime_environment(
    receipt: Mapping[str, Any], package_names: Sequence[str]
) -> dict[str, Any]:
    """Separate receipt self-consistency from actual verifier-runtime drift."""

    keys = ["python", "platform", *package_names, "cpu_logical", "ram_total_mb"]
    recorded = {key: receipt.get(key) for key in keys}
    default_hash = hashlib.sha256(
        json.dumps(recorded, sort_keys=True).encode("utf-8")
    ).hexdigest()
    compact_hash = hashlib.sha256(
        json.dumps(recorded, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    expected_hash = str(receipt.get("environment_sha256", ""))
    matching_encoding = (
        "default_json" if expected_hash == default_hash else "compact_json" if expected_hash == compact_hash else None
    )
    current = _runtime_environment(package_names)
    differences = {
        key: {"recorded": recorded.get(key), "current": current.get(key)}
        for key in keys
        if recorded.get(key) != current.get(key)
    }
    return {
        "receipt_environment_hash_valid": matching_encoding is not None,
        "receipt_environment_hash_encoding": matching_encoding,
        "runtime_exact_match": not differences,
        "differences": differences,
        "recorded": recorded,
        "current": current,
        "interpretation": (
            "The receipt hash checks internal receipt consistency only. Runtime differences "
            "describe replay-environment drift and do not invalidate stored artifact hashes."
        ),
    }
