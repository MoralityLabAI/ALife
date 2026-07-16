"""Bounded CPU campaign runner for deterministic ALife chronicle corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import psutil

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from chronicle.events import (  # type: ignore[no-redef]
        EventBuilder,
        ChronicleRecorder,
        canonical_json,
        canonical_jsonl,
        stable_entity_id,
        validate_stream,
    )
    from chronicle.export_sft import export_sft_records  # type: ignore[no-redef]
    from chronicle.legends import compile_legends  # type: ignore[no-redef]
else:
    from .events import (
        EventBuilder,
        ChronicleRecorder,
        canonical_json,
        canonical_jsonl,
        stable_entity_id,
        validate_stream,
    )
    from .export_sft import export_sft_records
    from .legends import compile_legends

from alife import LifeUniverse
from geometry_averaging_experiment import (
    degree_matched_offsets,
    neighbor_counts,
    rule_counts,
    state_digest,
    trajectory_digest,
)


EPISODE_CONFIG_SCHEMA = "alife.chronicle.episode_config.v1"
REPLAY_SCHEMA = "alife.chronicle.replay.v1"
CAMPAIGN_SCHEMA = "alife.chronicle.campaign.v1"

HARD_LIMITS = {
    "max_cells_per_world": 4096,
    "max_steps_per_episode": 128,
    "max_episodes": 600,
    "max_wall_seconds": 28_800,
    "max_episode_wall_seconds": 300,
    "max_ram_mb": 4096,
    "max_disk_mb": 4096,
    "max_dimension": 11,
    "max_moore_degree": 3**11 - 1,
}

SOURCE_FILES = (
    "src/alife.py",
    "src/geometry_averaging_experiment.py",
    "src/chronicle/events.py",
    "src/chronicle/legends.py",
    "src/chronicle/export_sft.py",
    "src/chronicle/campaign.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def canonical_hash(value: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def current_rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def source_receipt(project_root: Path) -> dict[str, Any]:
    hashes: dict[str, str] = {}
    for relative in SOURCE_FILES:
        path = project_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"missing replay source: {path}")
        hashes[relative] = sha256_file(path)
    return {"files": hashes, "code_sha256": canonical_hash(hashes)}


def copy_source_snapshot(project_root: Path, output: Path) -> None:
    for relative in SOURCE_FILES:
        destination = output / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project_root / relative, destination)


def version_control_receipt(project_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _check_deadline(deadline: float, max_ram_mb: float) -> None:
    if time.monotonic() > deadline:
        raise TimeoutError("episode wall-time cap exceeded")
    rss = current_rss_mb()
    if rss > max_ram_mb:
        raise MemoryError(f"RAM cap exceeded: {rss:.1f} MB > {max_ram_mb:.1f} MB")


def _base_final_state(universe: LifeUniverse) -> str:
    rows = []
    for plane, grid in universe.grids.items():
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell is None:
                    continue
                rows.append(
                    {
                        "plane": plane,
                        "position": [x, y],
                        "entity_id": stable_entity_id(cell.entity_id),
                        "kind": cell.kind,
                        "species": cell.species,
                        "age": cell.age,
                        "energy": cell.energy,
                        "flavor": cell.flavor,
                        "parent_ids": [stable_entity_id(value) for value in cell.parent_ids],
                    }
                )
    return sha256_bytes(canonical_json({"cells": rows}).encode("utf-8"))


def _run_base_episode(
    config: Mapping[str, Any], deadline: float, max_ram_mb: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    world = config["world"]
    universe = LifeUniverse(
        int(world["width"]),
        int(world["height"]),
        seed=int(config["seed"]),
        seed_density=float(world["density"]),
    )
    recorder = ChronicleRecorder(
        universe,
        episode_id=str(config["episode_id"]),
        world_id=str(config["world_id"]),
    )
    complexities: list[float] = []
    aggregate_events: Counter[str] = Counter()
    for _ in range(int(config["steps"])):
        _check_deadline(deadline, max_ram_mb)
        recorder.step()
        complexities.append(universe.last_complexity())
        aggregate_events.update(universe.event_counts())
    final_stats = universe.stats()
    plane_totals = {plane: values.get("total", 0) for plane, values in final_stats.items()}
    diversity = sum(value > 0 for value in plane_totals.values()) / max(1, len(plane_totals))
    avg_complexity = sum(complexities) / max(1, len(complexities))
    metrics = universe.latest_metrics()
    delight = (
        avg_complexity
        + 2.0 * float(metrics.get("gate_flux", 0.0))
        + 0.6 * diversity
        + 0.35 * float(metrics.get("plane_entropy", 0.0))
    )
    diagnostics = {
        "world_family": "native_multiplane",
        "plane_focus": world["plane_focus"],
        "final_stats": final_stats,
        "aggregate_simulator_events": dict(sorted(aggregate_events.items())),
        "avg_complexity": avg_complexity,
        "peak_complexity": max(complexities, default=0.0),
        "delight": delight,
        "gate_flux": aggregate_events.get("gate_placements", 0),
        "diagnostic_only": True,
        "final_state_sha256": _base_final_state(universe),
    }
    return [dict(event) for event in recorder.events], diagnostics


def _moore_counts_side_two(state: np.ndarray) -> np.ndarray:
    """Exact Moore counts on a side-2 torus using the separable weighted kernel."""

    if any(side != 2 for side in state.shape):
        raise ValueError("optimized high-dimensional Moore arm requires side 2")
    counts = state.astype(np.uint64)
    for axis in range(state.ndim):
        counts = counts + 2 * np.roll(counts, shift=1, axis=axis)
    return counts - state.astype(np.uint64)


def _run_lattice_episode(
    config: Mapping[str, Any], deadline: float, max_ram_mb: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    world = config["world"]
    dimension = int(world["dimension"])
    side = int(world["side"])
    neighborhood = str(world["neighborhood"])
    fixed_degree = int(world["fixed_degree"])
    shape = (side,) * dimension
    cells = side**dimension
    if cells > HARD_LIMITS["max_cells_per_world"]:
        raise ValueError("lattice cell cap exceeded")
    if neighborhood == "moore":
        degree = 3**dimension - 1
        if degree > HARD_LIMITS["max_moore_degree"]:
            raise ValueError("Moore degree cap exceeded")
        offsets: Sequence[Sequence[int]] | None = None
    elif neighborhood == "degree_matched":
        offsets = degree_matched_offsets(dimension, fixed_degree)
        degree = len(offsets)
    else:
        raise ValueError(f"unknown lattice neighborhood: {neighborhood}")
    births_allowed, survivals_allowed = rule_counts(str(world["rule_profile"]), degree)
    rng = np.random.default_rng(int(config["seed"]))
    state = rng.random(shape) < float(world["density"])
    ids = np.zeros(shape, dtype=np.int64)
    next_id = 1
    builder = EventBuilder(str(config["episode_id"]), str(config["world_id"]))
    plane = str(world["plane"])
    builder.emit(
        tick=0,
        event_type="world_initialized",
        plane=plane,
        region="lattice",
        position=(0,) * dimension,
        entities=[],
        cause_chain=[{"type": "episode_config", "entity_ids": []}],
        details={
            "dimension": dimension,
            "side": side,
            "neighborhood": neighborhood,
            "degree": degree,
            "initial_living": int(state.sum()),
        },
    )
    for coordinate in np.argwhere(state):
        position = tuple(int(value) for value in coordinate)
        ids[position] = next_id
        builder.emit(
            tick=0,
            event_type="birth",
            plane=plane,
            region="lattice",
            position=position,
            entities=[
                {
                    "id": stable_entity_id(next_id),
                    "role": "subject",
                    "kind": "life",
                    "species": None,
                }
            ],
            cause_chain=[{"type": "initial_seed", "entity_ids": []}],
            details={"kind": "life", "species": None, "flavor": "initial_seed", "parent_ids": []},
        )
        next_id += 1
    initial_sha256 = state_digest(state)
    trajectory: list[dict[str, Any]] = []
    for tick in range(1, int(config["steps"]) + 1):
        _check_deadline(deadline, max_ram_mb)
        counts = (
            _moore_counts_side_two(state)
            if neighborhood == "moore"
            else neighbor_counts(state, offsets or ())
        )
        born = (~state) & np.isin(counts, births_allowed)
        survived = state & np.isin(counts, survivals_allowed)
        next_state = born | survived
        died = state & ~next_state
        for coordinate in np.argwhere(died):
            position = tuple(int(value) for value in coordinate)
            entity_id = stable_entity_id(int(ids[position]))
            builder.emit(
                tick=tick,
                event_type="death",
                plane=plane,
                region="lattice",
                position=position,
                entities=[{"id": entity_id, "role": "subject", "kind": "life", "species": None}],
                cause_chain=[{"type": "totalistic_survival_rule", "entity_ids": []}],
                details={
                    "kind": "life",
                    "species": None,
                    "neighbor_count": int(counts[position]),
                },
            )
        next_ids = np.where(survived, ids, 0)
        for coordinate in np.argwhere(born):
            position = tuple(int(value) for value in coordinate)
            entity_id = stable_entity_id(next_id)
            next_ids[position] = next_id
            builder.emit(
                tick=tick,
                event_type="birth",
                plane=plane,
                region="lattice",
                position=position,
                entities=[{"id": entity_id, "role": "subject", "kind": "life", "species": None}],
                cause_chain=[{"type": "totalistic_birth_rule", "entity_ids": []}],
                details={
                    "kind": "life",
                    "species": None,
                    "flavor": "cellular_birth",
                    "parent_ids": [],
                    "neighbor_count": int(counts[position]),
                },
            )
            next_id += 1
        trajectory.append(
            {
                "tick": tick,
                "living": int(next_state.sum()),
                "births": int(born.sum()),
                "deaths": int(died.sum()),
                "state_sha256": state_digest(next_state),
            }
        )
        state = next_state
        ids = next_ids
    diagnostics = {
        "world_family": "high_dimensional_lattice",
        "plane": plane,
        "dimension": dimension,
        "neighborhood": neighborhood,
        "degree": degree,
        "side": side,
        "initial_state_sha256": initial_sha256,
        "final_state_sha256": state_digest(state),
        "trajectory_sha256": trajectory_digest(trajectory),
        "final_living": int(state.sum()),
        "complexity": None,
        "delight": None,
        "diagnostic_only": True,
    }
    return [dict(event) for event in builder.events], diagnostics


def run_episode_events(
    config: Mapping[str, Any], *, deadline: float | None = None, max_ram_mb: float | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_episode_config(config)
    effective_deadline = deadline if deadline is not None else time.monotonic() + 300
    effective_ram = float(max_ram_mb if max_ram_mb is not None else HARD_LIMITS["max_ram_mb"])
    family = config["world"]["family"]
    if family == "native_multiplane":
        events, diagnostics = _run_base_episode(config, effective_deadline, effective_ram)
    elif family == "high_dimensional_lattice":
        events, diagnostics = _run_lattice_episode(config, effective_deadline, effective_ram)
    else:
        raise ValueError(f"unknown world family: {family}")
    errors = validate_stream(events)
    if errors:
        raise RuntimeError("generated event stream is invalid: " + "; ".join(errors[:10]))
    return events, diagnostics


def episode_cell_count(config: Mapping[str, Any]) -> int:
    world = config.get("world")
    if not isinstance(world, Mapping):
        raise ValueError("episode world must be an object")
    if not isinstance(world.get("plane"), str) or not world.get("plane"):
        raise ValueError("episode world must have a lore-neutral plane tag")
    if not isinstance(world.get("dimension"), int) or not isinstance(
        world.get("degree"), int
    ):
        raise ValueError("episode world dimension and degree must be integers")
    if world.get("family") == "native_multiplane":
        return int(world["width"]) * int(world["height"]) * 4
    if world.get("family") == "high_dimensional_lattice":
        return int(world["side"]) ** int(world["dimension"])
    raise ValueError("unknown world family")


def validate_episode_config(config: Mapping[str, Any]) -> None:
    if config.get("schema") != EPISODE_CONFIG_SCHEMA:
        raise ValueError(f"episode config schema must be {EPISODE_CONFIG_SCHEMA}")
    if not isinstance(config.get("seed"), int):
        raise ValueError("episode seed must be an integer")
    steps = int(config.get("steps", 0))
    if steps < 1 or steps > HARD_LIMITS["max_steps_per_episode"]:
        raise ValueError("episode step cap exceeded")
    world = config.get("world")
    if not isinstance(world, Mapping):
        raise ValueError("episode world must be an object")
    if world.get("family") == "high_dimensional_lattice":
        dimension = int(world["dimension"])
        if dimension < 4 or dimension > HARD_LIMITS["max_dimension"]:
            raise ValueError("lattice dimension must be in [4, 11]")
    elif world.get("family") != "native_multiplane":
        raise ValueError("unknown world family")
    cells = episode_cell_count(config)
    if cells < 1 or cells > HARD_LIMITS["max_cells_per_world"]:
        raise ValueError("episode cell cap exceeded")


def condition_matrix(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    design = manifest["design"]
    native = design["native"]
    lattice = design["lattice"]
    conditions: list[dict[str, Any]] = []
    for plane in native["planes"]:
        conditions.append(
            {
                "family": "native_multiplane",
                "plane": plane,
                "plane_focus": plane,
                "width": int(native["width"]),
                "height": int(native["height"]),
                "density": float(native["density"]),
                "dimension": 2,
                "degree": 8,
            }
        )
    lattice_planes = list(lattice.get("planes", native["planes"]))
    if not lattice_planes:
        raise ValueError("lattice plane tags must not be empty")
    lattice_index = 0
    for dimension in lattice["dimensions"]:
        for neighborhood in lattice["neighborhoods"]:
            degree = 3 ** int(dimension) - 1 if neighborhood == "moore" else int(lattice["fixed_degree"])
            conditions.append(
                {
                    "family": "high_dimensional_lattice",
                    "plane": str(lattice_planes[lattice_index % len(lattice_planes)]),
                    "dimension": int(dimension),
                    "neighborhood": neighborhood,
                    "degree": degree,
                    "fixed_degree": int(lattice["fixed_degree"]),
                    "side": int(lattice["side"]),
                    "density": float(lattice["density"]),
                    "rule_profile": str(lattice["rule_profile"]),
                }
            )
            lattice_index += 1
    return conditions


def episode_config(
    manifest: Mapping[str, Any], index: int, *, steps: int | None = None
) -> dict[str, Any]:
    conditions = condition_matrix(manifest)
    identifier = f"chronicle-{index:06d}"
    config = {
        "schema": EPISODE_CONFIG_SCHEMA,
        "episode_id": identifier,
        "world_id": f"world-{index:06d}",
        "seed": int(manifest["design"]["seed_start"]) + index,
        "steps": int(steps if steps is not None else manifest["design"]["steps"]),
        "world": conditions[index % len(conditions)],
    }
    validate_episode_config(config)
    return config


def _build_episode_artifacts(
    config: dict[str, Any],
    episode_root: Path,
    *,
    code_receipt: Mapping[str, Any],
    manifest_sha256: str,
    episode_deadline: float,
    max_ram_mb: float,
    max_window_events: int,
    max_biographies: int,
) -> dict[str, Any]:
    started = time.monotonic()
    config_sha256 = canonical_hash(config)
    events, diagnostics = run_episode_events(
        config, deadline=episode_deadline, max_ram_mb=max_ram_mb
    )
    event_bytes = canonical_jsonl(events)
    event_sha256 = sha256_bytes(event_bytes)
    legends = compile_legends(events)
    replay = {
        "schema": REPLAY_SCHEMA,
        "episode_id": config["episode_id"],
        "seed": config["seed"],
        "config_sha256": config_sha256,
        "code_sha256": code_receipt["code_sha256"],
        "event_sha256": event_sha256,
        "final_state_sha256": diagnostics["final_state_sha256"],
    }
    replay["receipt_id"] = canonical_hash(replay)
    sft_records = export_sft_records(
        events,
        seed=int(config["seed"]),
        replay_receipt=replay,
        legends=legends,
        max_window_events=max_window_events,
        max_biographies=max_biographies,
    )
    episode_root.mkdir(parents=True, exist_ok=False)
    config_path = episode_root / "config.json"
    events_path = episode_root / "events.jsonl"
    legends_path = episode_root / "legends.json"
    sft_path = episode_root / "sft.jsonl"
    write_json(config_path, config)
    events_path.write_bytes(event_bytes)
    write_json(legends_path, legends)
    sft_path.write_bytes(canonical_jsonl(sft_records))
    artifact_hashes = {
        "config.json": sha256_file(config_path),
        "events.jsonl": event_sha256,
        "legends.json": sha256_file(legends_path),
        "sft.jsonl": sha256_file(sft_path),
    }
    event_type_counts = Counter(event["event_type"] for event in events)
    receipt = {
        **replay,
        "status": "ok",
        "manifest_sha256": manifest_sha256,
        "world": config["world"],
        "event_count": len(events),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "biography_count": len(legends["biographies"]),
        "chronicle_count": len(legends["chronicles"]),
        "sft_record_count": len(sft_records),
        "diagnostics": diagnostics,
        "diagnostics_are_acceptance_gates": False,
        "wall_seconds": time.monotonic() - started,
        "max_rss_mb": current_rss_mb(),
        "artifact_hashes": artifact_hashes,
        "replay_command": (
            f"python src/chronicle/campaign.py --replay-config {config_path} "
            f"--output {episode_root.parent / (episode_root.name + '-replay')}"
        ),
    }
    write_json(episode_root / "receipt.json", receipt)
    return receipt


def _summary(rows: list[dict[str, Any]], status: str, stop_reason: str) -> dict[str, Any]:
    planes: Counter[str] = Counter()
    dimensions: Counter[str] = Counter()
    degrees: Counter[str] = Counter()
    neighborhoods: Counter[str] = Counter()
    families: Counter[str] = Counter()
    event_types: Counter[str] = Counter()
    total_events = 0
    for row in rows:
        world = row["world"]
        families[str(world["family"])] += 1
        planes[str(world["plane"])] += 1
        dimensions[str(world["dimension"])] += 1
        degrees[str(world["degree"])] += 1
        if world["family"] != "native_multiplane":
            neighborhoods[str(world["neighborhood"])] += 1
        total_events += int(row["event_count"])
        event_types.update(row["event_type_counts"])
    return {
        "schema": CAMPAIGN_SCHEMA,
        "status": status,
        "stop_reason": stop_reason,
        "episode_count": len(rows),
        "total_events": total_events,
        "counts_by_plane": dict(sorted(planes.items())),
        "counts_by_dimension": dict(sorted(dimensions.items(), key=lambda item: int(item[0]))),
        "counts_by_degree": dict(sorted(degrees.items(), key=lambda item: int(item[0]))),
        "counts_by_neighborhood": dict(sorted(neighborhoods.items())),
        "counts_by_world_family": dict(sorted(families.items())),
        "event_type_counts": dict(sorted(event_types.items())),
        "schema_versions": {
            "events": "alife.chronicle.event.v1",
            "legends": "alife.chronicle.legends.v1",
            "sft": "alife.chronicle.sft.v1",
            "replay": REPLAY_SCHEMA,
        },
        "interpretation": (
            "Generator data only. Complexity, delight, gate flux, and coverage counts are "
            "diagnostics and were not used as acceptance gates."
        ),
        "ontology_registry_modified": False,
    }


def write_manifest_md(root: Path) -> None:
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    verification_path = root / "verification_receipt.json"
    verification = (
        json.loads(verification_path.read_text(encoding="utf-8"))
        if verification_path.is_file()
        else {"status": "pending", "sampled_episodes": 0}
    )
    lines = [
        "# ALife Chronicle Corpus Manifest",
        "",
        f"- Episodes: {summary['episode_count']}",
        f"- Total events: {summary['total_events']}",
        f"- Campaign status: {summary['status']}",
        f"- Verification status: {verification.get('status', 'pending')}",
        f"- Sampled replay episodes: {verification.get('sampled_episodes', 0)}",
        "- Acceptance: schema validation and exact event-byte replay only",
        "- Doctrine: generator data, not evidence; diagnostic metrics are not gates",
        "- Ontology registry modified: no",
        "",
        "## Schema versions",
        "",
    ]
    for name, version in sorted(summary["schema_versions"].items()):
        lines.append(f"- {name}: `{version}`")
    lines.extend(["", "## Plane-tag counts", ""])
    for name, count in sorted(summary["counts_by_plane"].items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Dimension counts", ""])
    for name, count in sorted(
        summary["counts_by_dimension"].items(), key=lambda item: int(item[0])
    ):
        lines.append(f"- dimension {name}: {count}")
    lines.extend(["", "## Degree counts", ""])
    for name, count in sorted(
        summary["counts_by_degree"].items(), key=lambda item: int(item[0])
    ):
        lines.append(f"- degree {name}: {count}")
    lines.extend(["", "## Neighborhood counts", ""])
    for name, count in sorted(summary["counts_by_neighborhood"].items()):
        lines.append(f"- {name}: {count}")
    if verification_path.is_file():
        lines.extend(
            [
                "",
                "## Verification receipt",
                "",
                f"- Receipt SHA-256: `{sha256_file(verification_path)}`",
                f"- Event streams validated: {verification.get('validated_event_streams', 0)}",
                f"- Legends validated: {verification.get('validated_legends', 0)}",
                f"- SFT files validated: {verification.get('validated_sft_files', 0)}",
                f"- Legends re-derived: {verification.get('rederived_legends', 0)}",
                f"- SFT files re-derived: {verification.get('rederived_sft_files', 0)}",
                f"- Byte replay failures: {len(verification.get('replay_failures', []))}",
            ]
        )
    (root / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_bundle(root: Path, destination: Path) -> Path:
    write_manifest_md(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite bundle: {destination}")
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    return destination


def _replay_one(config_path: Path, output: Path, max_ram_mb: float) -> None:
    if output.exists():
        raise FileExistsError(f"replay output already exists: {output}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    events, diagnostics = run_episode_events(
        config,
        deadline=time.monotonic() + HARD_LIMITS["max_episode_wall_seconds"],
        max_ram_mb=max_ram_mb,
    )
    output.mkdir(parents=True)
    (output / "events.jsonl").write_bytes(canonical_jsonl(events))
    write_json(output / "diagnostics.json", diagnostics)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("experiments/chronicle_v1/manifest.json")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--episodes", type=int)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--wall-seconds", type=float)
    parser.add_argument("--episode-wall-seconds", type=float)
    parser.add_argument("--max-cells-per-world", type=int)
    parser.add_argument("--replay-config", type=Path)
    args = parser.parse_args()

    if args.replay_config is not None:
        if args.output is None:
            parser.error("--replay-config requires --output")
        _replay_one(args.replay_config, args.output, HARD_LIMITS["max_ram_mb"])
        return

    project_root = Path(__file__).resolve().parents[2]
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = manifest["budget"]
    episodes = int(args.episodes if args.episodes is not None else manifest["design"]["episode_count"])
    steps = int(args.steps if args.steps is not None else manifest["design"]["steps"])
    wall_seconds = float(args.wall_seconds if args.wall_seconds is not None else budget["max_wall_seconds"])
    episode_wall_seconds = float(
        args.episode_wall_seconds
        if args.episode_wall_seconds is not None
        else budget["max_episode_wall_seconds"]
    )
    max_episodes = min(int(budget["max_episodes"]), HARD_LIMITS["max_episodes"])
    max_steps = min(int(budget["max_steps_per_episode"]), HARD_LIMITS["max_steps_per_episode"])
    max_cells = min(int(budget["max_cells_per_world"]), HARD_LIMITS["max_cells_per_world"])
    cell_cap = int(
        args.max_cells_per_world
        if args.max_cells_per_world is not None
        else max_cells
    )
    if episodes < 1 or episodes > max_episodes:
        raise SystemExit(f"episodes must be in [1, {max_episodes}]")
    if steps < 1 or steps > max_steps:
        raise SystemExit(f"steps must be in [1, {max_steps}]")
    if cell_cap < 1 or cell_cap > max_cells:
        raise SystemExit(f"max cells per world must be in [1, {max_cells}]")
    if wall_seconds <= 0 or wall_seconds > min(float(budget["max_wall_seconds"]), HARD_LIMITS["max_wall_seconds"]):
        raise SystemExit("wall-time cap exceeds manifest or hard limit")
    if episode_wall_seconds <= 0 or episode_wall_seconds > min(
        float(budget["max_episode_wall_seconds"]), HARD_LIMITS["max_episode_wall_seconds"]
    ):
        raise SystemExit("episode wall-time cap exceeds manifest or hard limit")
    max_ram_mb = min(float(budget["max_ram_mb"]), HARD_LIMITS["max_ram_mb"])
    max_disk_bytes = min(float(budget["max_disk_mb"]), HARD_LIMITS["max_disk_mb"]) * 1024 * 1024
    output = (
        args.output.resolve()
        if args.output is not None
        else (project_root / manifest["artifacts"]["output_directory"]).resolve()
    )
    for condition_index in range(len(condition_matrix(manifest))):
        candidate = episode_config(manifest, condition_index, steps=steps)
        cells = episode_cell_count(candidate)
        if cells > cell_cap:
            raise SystemExit(
                f"condition {condition_index} requires {cells} cells, exceeding CLI cap {cell_cap}"
            )
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    (output / "episodes").mkdir()
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    copy_source_snapshot(project_root, output)
    code = source_receipt(project_root)
    manifest_sha256 = sha256_file(manifest_path)
    started_utc = utc_now()
    started = time.monotonic()
    deadline = started + wall_seconds
    rows: list[dict[str, Any]] = []
    status = "ok"
    stop_reason = "completed_declared_episodes"
    max_rss = current_rss_mb()
    sft_design = manifest["design"]["sft"]
    try:
        with (output / "episodes.jsonl").open("w", encoding="utf-8") as index_handle:
            for index in range(episodes):
                _check_deadline(deadline, max_ram_mb)
                config = episode_config(manifest, index, steps=steps)
                episode_root = output / "episodes" / config["episode_id"]
                receipt = _build_episode_artifacts(
                    config,
                    episode_root,
                    code_receipt=code,
                    manifest_sha256=manifest_sha256,
                    episode_deadline=min(deadline, time.monotonic() + episode_wall_seconds),
                    max_ram_mb=max_ram_mb,
                    max_window_events=int(sft_design["max_window_events"]),
                    max_biographies=int(sft_design["max_biographies_per_episode"]),
                )
                rows.append(receipt)
                index_handle.write(canonical_json(receipt) + "\n")
                index_handle.flush()
                max_rss = max(max_rss, float(receipt["max_rss_mb"]))
                if (index + 1) % 10 == 0 and directory_bytes(output) > max_disk_bytes:
                    raise RuntimeError("artifact disk cap exceeded")
    except (MemoryError, TimeoutError, RuntimeError, ValueError, OSError) as exc:
        status = "stopped"
        stop_reason = f"{type(exc).__name__}: {exc}"

    summary = _summary(rows, status, stop_reason)
    write_json(output / "summary.json", summary)
    write_json(
        output / "seed_manifest.json",
        {
            "episode_count": len(rows),
            "seeds": [row["seed"] for row in rows],
            "experimental_unit": manifest["experimental_unit"],
            "pairing": manifest["seed_plan"]["pairing"],
        },
    )
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "schema": CAMPAIGN_SCHEMA,
        "status": status,
        "stop_reason": stop_reason,
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "episode_count": len(rows),
        "max_rss_mb": max_rss,
        "artifact_bytes": directory_bytes(output),
        "output_path": str(output),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        **code,
        **environment,
        "environment_sha256": canonical_hash(environment),
        "version_control": version_control_receipt(project_root),
        "hard_limits": HARD_LIMITS,
        "effective_caps": {
            "max_cells_per_world": cell_cap,
            "max_steps_per_episode": steps,
            "max_episodes": episodes,
            "max_wall_seconds": wall_seconds,
            "max_episode_wall_seconds": episode_wall_seconds,
            "max_ram_mb": max_ram_mb,
            "max_disk_mb": max_disk_bytes / (1024 * 1024),
        },
        "replay_command": f"python src/chronicle/verify_chronicle.py {output} --sample 24",
    }
    write_json(output / "campaign_receipt.json", receipt)
    write_manifest_md(output)
    if directory_bytes(output) > max_disk_bytes:
        status = "stopped"
        stop_reason = "artifact disk cap exceeded after final receipts"
    print(
        json.dumps(
            {
                "output": str(output),
                "status": status,
                "stop_reason": stop_reason,
                "episodes": len(rows),
                "events": summary["total_events"],
            },
            indent=2,
        )
    )
    raise SystemExit(0 if status == "ok" and len(rows) == episodes else 1)


if __name__ == "__main__":
    main()
