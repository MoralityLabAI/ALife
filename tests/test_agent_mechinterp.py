from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent_mechinterp.analysis import analyze_decisions  # noqa: E402
from agent_mechinterp.campaign import build_rows, tamper_audit  # noqa: E402
from agent_mechinterp.core import (  # noqa: E402
    CanaryPolicy,
    authorize_edit,
    verify_authorization,
    verify_harness_row,
)


EXPERIMENT = ROOT / "experiments" / "agent_mechinterp_harness_v1"
MANIFEST = json.loads((EXPERIMENT / "manifest.json").read_text(encoding="utf-8"))
TAXONOMY = json.loads(
    (EXPERIMENT / "mechinterp_taxonomy.json").read_text(encoding="utf-8")
)
SOURCE = json.loads(
    (ROOT / "experiments" / "pixie_sanctuary_v1" / "manifest.json").read_text(
        encoding="utf-8"
    )
)


def tiny_rows() -> list[dict]:
    manifest = copy.deepcopy(MANIFEST)
    manifest["seed_plan"] = {
        "discovery": [71],
        "confirmatory": [81],
        "holdout": [99],
        "pairing": MANIFEST["seed_plan"]["pairing"],
    }
    return build_rows(
        manifest,
        TAXONOMY,
        SOURCE,
        deadline=time.monotonic() + 30.0,
    )


def test_play_and_editor_rows_are_replay_grounded_and_hard_valid() -> None:
    rows = tiny_rows()
    assert len(rows) == 18
    assert {row["mode"] for row in rows} == {"play", "editor"}
    assert all(row["hard_verification"]["passed"] for row in rows)
    assert all(
        verify_harness_row(row, policy=CanaryPolicy(), taxonomy=TAXONOMY)["passed"]
        for row in rows
    )
    assert all(
        row["execution"]["adventure_verification"]["accepted"]
        for row in rows
        if row["mode"] == "play"
    )


def test_known_canary_features_are_decodable_and_causally_used() -> None:
    rows = tiny_rows()
    analysis = analyze_decisions([row["decision"] for row in rows], CanaryPolicy())
    assert analysis["authorization_eligible"] is False
    for result in analysis["modes"].values():
        assert result["probe_accuracy"]["holdout"] == 1.0
        assert result["mean_chosen_logit_drop"] == 4.0
        assert result["patch_action_change_fraction"] == 1.0


def test_every_declared_tamper_hits_its_registered_hard_check() -> None:
    results = tamper_audit(tiny_rows(), TAXONOMY)
    assert {item["tamper_class"] for item in results} == set(
        MANIFEST["design"]["tamper_classes"]
    )
    assert all(item["passed"] for item in results)


def test_mechanistic_metric_cannot_become_an_editor_gate() -> None:
    row = next(item for item in tiny_rows() if item["mode"] == "editor")
    authorization = copy.deepcopy(row["execution"]["authorization"])
    authorization["gate_ids"].append("identity_probe")
    assert any(
        "non-hard" in failure or "mechanistic" in failure
        for failure in verify_authorization(authorization, TAXONOMY)
    )


def test_editor_firewall_rejects_wrong_target_even_with_perfect_probe() -> None:
    row = next(item for item in tiny_rows() if item["mode"] == "editor")
    proposal = copy.deepcopy(row["execution"]["proposal"])
    proposal["target_critter"] = "prism_wyrm" if row["critter"] != "prism_wyrm" else "bitlichen"
    authorization = authorize_edit(
        proposal,
        parent_profile=row["execution"]["parent_profile"],
        observed_critter=row["critter"],
        taxonomy=TAXONOMY,
    )
    assert authorization["authorized"] is False
    assert any("observed critter" in failure for failure in authorization["failures"])
