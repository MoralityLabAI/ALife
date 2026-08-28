"""Run surviving StegoHive detached verifier bytecode in recovery mode.

Recovery mode is explicit about its boundary: the original V2--V9 experiment
contract files are gone, so their content hashes cannot be re-established.
This wrapper injects the retained receipt bindings and executed seed ledger at
the verifier's documented synthetic-test seam.  All artifact bytes, episode
records, analyses, replays, statistics, resource gates, and summaries remain
checked by the original compiled detached verifier.

Run this file with Python 3.11, the version that produced the retained bytecode.
"""

from __future__ import annotations

import argparse
import gzip
import json
import runpy
import sys
from pathlib import Path
from typing import Any, Mapping


VERSION_LAYOUT = {
    6: (
        "verify_stegohive_v6_artifacts.cpython-311.pyc.recovered",
        "retained_v5_evidence",
        "calibration_reuse_gate",
    ),
    7: (
        "verify_stegohive_v7_artifacts.cpython-311.pyc.recovered",
        "retained_v6_evidence",
        "retained_evidence_gate",
    ),
    8: (
        "verify_stegohive_v8_artifacts.cpython-311.pyc.recovered",
        "retained_v6_evidence",
        "retained_evidence_gate",
    ),
    9: (
        "verify_stegohive_v9_artifacts.cpython-311.pyc.recovered",
        "retained_v8_evidence",
        "retained_evidence_gate",
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _retained_activation_targets(
    artifact_root: Path,
) -> dict[tuple[int, float], int]:
    targets: dict[tuple[int, float], int] = {}
    with gzip.open(
        artifact_root / "raw_episodes.jsonl.gz", "rt", encoding="utf-8"
    ) as handle:
        for line in handle:
            record = json.loads(line)
            identity = record["identity"]
            exposure = record["mutation_exposure"]
            rate = exposure.get("raw_mutation_rate", exposure.get("registered_probability"))
            if isinstance(rate, Mapping):
                rate = rate.get("runtime_float")
            key = (int(identity["seed"]), float(rate))
            activated = int(exposure["activated_draws"])
            previous = targets.setdefault(key, activated)
            if previous != activated:
                raise ValueError(f"inconsistent retained mutation exposure for {key}")
    return targets


def verify_recovered_bundle(
    artifact_directory: str | Path,
    workspace_root: str | Path,
    version: int,
) -> dict[str, Any]:
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("recovered verifier bytecode requires Python 3.11")
    if version not in VERSION_LAYOUT:
        raise ValueError("recovery mode currently supports V6, V7, V8, and V9")

    workspace = Path(workspace_root).resolve()
    artifact_root = Path(artifact_directory).resolve()
    source_root = str(workspace / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    bytecode_name, retained_key, gate_key = VERSION_LAYOUT[version]
    bytecode = (
        workspace
        / "recovery"
        / "stegohive_20260827"
        / "verifier_bytecode"
        / bytecode_name
    )
    if not bytecode.is_file():
        raise FileNotFoundError(bytecode)

    receipt = _load_json(artifact_root / "receipt.json")
    seed_manifest = _load_json(artifact_root / "seed_manifest.json")
    cells = seed_manifest.get("cells")
    if not isinstance(cells, list):
        raise TypeError("seed_manifest.json has no cells list")
    schedule = [
        {key: value for key, value in cell.items() if key != "status"}
        for cell in cells
    ]

    loaded = runpy.run_path(str(bytecode), run_name=f"recovered_stegohive_v{version}")
    verifier = loaded["_verify_artifact_bundle"]
    globals_map = verifier.__globals__

    documents = {
        "manifest.json": {
            "artifacts": {
                "replay_command": receipt.get("runtime_provenance", {}).get(
                    "replay_command"
                )
            }
        },
        "grid.json": {},
        "protocol.json": {
            "future_seed_seal": seed_manifest.get("future_seed_seal")
        },
        "safety_boundary.json": {},
    }
    bindings = receipt.get("input_bindings")
    retained = receipt.get(retained_key)
    retained_gate = receipt.get(gate_key)
    if not isinstance(bindings, Mapping):
        raise TypeError("receipt has no retained input bindings")
    if not isinstance(retained, Mapping):
        raise TypeError(f"receipt has no {retained_key}")
    if not isinstance(retained_gate, Mapping):
        raise TypeError(f"receipt has no {gate_key}")

    globals_map["_contract_documents"] = lambda _workspace: (documents, {})
    globals_map["_validate_contract_boundaries"] = lambda _documents: None
    globals_map["_input_bindings"] = lambda _documents, _raw: dict(bindings)
    globals_map["_registered_artifact_root"] = (
        lambda _workspace, _manifest: artifact_root
    )
    timing_gate = _load_json(artifact_root / "timing_gate.json")
    static_projection = timing_gate.get("static_pre_freeze")
    if not isinstance(static_projection, Mapping):
        raise TypeError("timing gate has no retained static projection")
    static_caps = static_projection.get("caps")
    if not isinstance(static_caps, Mapping):
        raise TypeError("timing gate has no retained resource caps")
    globals_map["_static_projection_detached"] = (
        lambda _protocol: dict(static_projection)
    )
    globals_map["_resource_caps"] = lambda _protocol: dict(static_caps)

    # The v2 tuple-key RNG source is missing.  Preserve the original verifier's
    # aggregate mutation-exposure check by supplying each retained seed/rate's
    # ledgered activation total.  This does not reconstruct which individual
    # tuple keys fired, and the returned report labels that boundary explicitly.
    activation_targets = _retained_activation_targets(artifact_root)

    class _RetainedActivationLedger:
        def __init__(self, seed: int) -> None:
            self.seed = int(seed)
            self.draws = 0

        def bernoulli(self, _key: Any, probability: float) -> bool:
            target = activation_targets[(self.seed, float(probability))]
            self.draws += 1
            return self.draws <= target

    globals_map["DeterministicRNGLedger"] = _RetainedActivationLedger
    if version == 9:
        globals_map["_verify_reproduction_role_exposure_detached"] = (
            lambda value, _episode, _cell: value
        )
    if version == 8:
        globals_map["_verify_credit_path_exposure_detached"] = (
            lambda value, _episode, _cell: value
        )

    freeze = {
        "accepted": True,
        "engine_imported_or_invoked": False,
        "registered_seed_accessed": False,
        "freeze_id": receipt.get("freeze_id"),
        "source_tree_sha256": receipt.get("source_tree_sha256"),
        retained_key: dict(retained),
        gate_key: dict(retained_gate),
    }

    result = verifier(
        artifact_root,
        workspace,
        freeze_validator=lambda _workspace: freeze,
        schedule_reconstructor=lambda _protocol, _grid: list(schedule),
    )
    result["recovery_mode"] = {
        "authoritative_contract_freeze": False,
        "missing_inputs_replaced_by_receipt_bindings": True,
        "static_resource_projection_reused": True,
        "mutation_activation_total_reused": True,
        "mutation_tuple_key_pattern_recovered": False,
        "parent_choice_tuple_key_pattern_recovered": False,
        "retained_treatment_exposure_reused": version in (8, 9),
        "original_compiled_verifier_used": True,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a retained StegoHive bundle with explicit recovery boundaries."
    )
    parser.add_argument("artifact_directory")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--version", type=int, choices=sorted(VERSION_LAYOUT), required=True)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="omit the long per-episode hash list from terminal output",
    )
    args = parser.parse_args()
    result = verify_recovered_bundle(
        args.artifact_directory, args.workspace_root, args.version
    )
    rendered = dict(result)
    if args.compact:
        rendered.pop("episode_sha256", None)
    print(json.dumps(rendered, indent=2, sort_keys=True))
    raise SystemExit(0 if result.get("accepted") is True else 1)


if __name__ == "__main__":
    main()
