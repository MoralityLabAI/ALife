#!/usr/bin/env python3
"""Create and verify the consolidated ALife goal artifact bundle on D."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = Path(r"D:\ALife\bundles\ALife_emergent_mechanics_track_20260713_v2")
ZIP_PATH = BUNDLE_ROOT.with_suffix(".zip")
TOP_LEVEL = ["GOAL.md", "REPORT.md", "PROGRESS.md", "README.md"]
DIRECTORIES = [
    "registries",
    "experiments/geometry_averaging_v1",
    "experiments/graph_state_v1",
    "experiments/graph_state_v2_confirmation",
    "experiments/discovery_curriculum_v1",
    "experiments/confinement_transfer_v1",
    "tests",
]
SOURCES = [
    "src/artifact_verification.py",
    "src/geometry_averaging_experiment.py",
    "src/verify_geometry_averaging_artifacts.py",
    "src/graph_state_lab.py",
    "src/verify_graph_state_artifacts.py",
    "src/discovery_curriculum.py",
    "src/verify_discovery_curriculum_artifacts.py",
    "src/confinement_transfer.py",
    "src/verify_confinement_transfer_artifacts.py",
    "src/bundle_goal_artifacts.py",
]
EXTERNAL_FILES = [
    (
        Path(
            r"C:\projects\SmallControlHarness\storyworld-whitebox-control-starter"
            r"\storyworld-whitebox-control-starter\src\evals\confinement_width.py"
        ),
        Path("external/confinement_width/src/evals/confinement_width.py"),
    ),
    (
        Path(
            r"C:\projects\SmallControlHarness\storyworld-whitebox-control-starter"
            r"\storyworld-whitebox-control-starter\results\confinement_width"
            r"\fiber_routing_summary.json"
        ),
        Path(
            "external/confinement_width/results/confinement_width/"
            "fiber_routing_summary.json"
        ),
    ),
]
RESULTS = [
    "geometry_averaging_v1",
    "graph_state_v1",
    "graph_state_v2_confirmation",
    "discovery_curriculum_v1",
    "confinement_transfer_v1",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(relative: str) -> None:
    source = ROOT / relative
    target = BUNDLE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    if BUNDLE_ROOT.exists() or ZIP_PATH.exists():
        raise SystemExit(f"refusing to overwrite existing bundle: {BUNDLE_ROOT} or {ZIP_PATH}")
    BUNDLE_ROOT.mkdir(parents=True)
    for relative in [*TOP_LEVEL, *SOURCES]:
        copy_file(relative)
    for relative in DIRECTORIES:
        shutil.copytree(ROOT / relative, BUNDLE_ROOT / relative)
    for result in RESULTS:
        shutil.copytree(ROOT / "results" / result, BUNDLE_ROOT / "results" / result)
    for source, relative_target in EXTERNAL_FILES:
        if not source.is_file():
            raise SystemExit(f"external provenance source is missing: {source}")
        target = BUNDLE_ROOT / relative_target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    portable_commands = [
        ("src/verify_geometry_averaging_artifacts.py", "results/geometry_averaging_v1"),
        ("src/verify_graph_state_artifacts.py", "results/graph_state_v1"),
        ("src/verify_graph_state_artifacts.py", "results/graph_state_v2_confirmation"),
        ("src/verify_discovery_curriculum_artifacts.py", "results/discovery_curriculum_v1"),
        ("src/verify_confinement_transfer_artifacts.py", "results/confinement_transfer_v1"),
    ]
    portable_verification: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(
        prefix="alife_bundle_portability_", dir=ROOT
    ) as temporary:
        relocated = Path(temporary) / BUNDLE_ROOT.name
        shutil.copytree(BUNDLE_ROOT, relocated)
        for verifier, artifact in portable_commands:
            command = [
                sys.executable,
                str(relocated / verifier),
                str(relocated / artifact),
                "--portable",
            ]
            completed = subprocess.run(
                command,
                cwd=relocated,
                capture_output=True,
                text=True,
                check=False,
            )
            try:
                result = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"portable verifier emitted invalid JSON: {verifier}: {exc}\n"
                    f"stdout={completed.stdout}\nstderr={completed.stderr}"
                )
            storage = result.get("provenance", {}).get("storage_location", {})
            if (
                completed.returncode != 0
                or result.get("valid") is not True
                or storage.get("matches_intended_drive") is not False
                or storage.get("affects_validity") is not False
            ):
                raise SystemExit(
                    f"portable verification failed: {verifier} {artifact}\n"
                    + json.dumps(result, indent=2)
                )
            portable_verification.append(
                {
                    "verifier": verifier,
                    "artifact": artifact,
                    "valid": True,
                    "non_d_storage_warning_only": True,
                    "code_resolution_method": result["provenance"]["code_resolution"]["method"],
                }
            )

    payload = sorted(
        path for path in BUNDLE_ROOT.rglob("*") if path.is_file()
    )
    records = [
        {
            "path": path.relative_to(BUNDLE_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in payload
    ]
    checksum_path = BUNDLE_ROOT / "CHECKSUMS.sha256"
    checksum_path.write_text(
        "".join(f"{row['sha256']}  {row['path']}\n" for row in records),
        encoding="utf-8",
    )
    manifest = {
        "schema": "alife.goal_bundle.v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(ROOT),
        "bundle_root": str(BUNDLE_ROOT),
        "payload_file_count": len(records),
        "payload_bytes": sum(row["bytes"] for row in records),
        "checksums_sha256": sha256(checksum_path),
        "full_campaigns": RESULTS,
        "portable_relocation_test": {
            "status": "passed",
            "verifiers": portable_verification,
            "policy": "Non-D storage and runtime-environment drift are reported separately from artifact validity.",
        },
        "verification_commands": [
            "python src/verify_geometry_averaging_artifacts.py results/geometry_averaging_v1 --portable",
            "python src/verify_graph_state_artifacts.py results/graph_state_v1 --portable",
            "python src/verify_graph_state_artifacts.py results/graph_state_v2_confirmation --portable",
            "python src/verify_discovery_curriculum_artifacts.py results/discovery_curriculum_v1 --portable",
            "python src/verify_confinement_transfer_artifacts.py results/confinement_transfer_v1 --portable",
            "python -m unittest discover -s tests -v",
        ],
    }
    (BUNDLE_ROOT / "BUNDLE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for row in records:
        path = BUNDLE_ROOT / row["path"]
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise SystemExit(f"payload verification failed: {path}")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in BUNDLE_ROOT.rglob("*") if item.is_file()):
            archive.write(path, Path(BUNDLE_ROOT.name) / path.relative_to(BUNDLE_ROOT))
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        failed = archive.testzip()
        if failed:
            raise SystemExit(f"zip integrity failure: {failed}")
    print(
        json.dumps(
            {
                "bundle": str(BUNDLE_ROOT),
                "zip": str(ZIP_PATH),
                "zip_bytes": ZIP_PATH.stat().st_size,
                "zip_sha256": sha256(ZIP_PATH),
                **manifest,
                "zip_integrity": "passed",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
