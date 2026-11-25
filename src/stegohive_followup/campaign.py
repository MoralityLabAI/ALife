"""Run or independently replay the bounded follow-up into its own directory."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from . import EVIDENCE_CLASS
from .leakage import ARMS, CHANNELS, CODECS, analyze, generate
from .reporting_game import run_study

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "experiments" / "stegohive_followup_20260911"
SOURCE_PATHS = (
    "src/stegohive_followup/__init__.py",
    "src/stegohive_followup/leakage.py",
    "src/stegohive_followup/reporting_game.py",
    "src/stegohive_followup/campaign.py",
    "experiments/stegohive_followup_20260911/manifest.json",
    "experiments/stegohive_followup_20260911/PROTOCOL.md",
    "experiments/stegohive_followup_20260911/REPORTING_GAME.md",
    "tests/test_stegohive_joint_channels.py",
    "tests/test_stegohive_reporting_game.py",
)


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest():
    manifest = json.loads((STUDY / "manifest.json").read_text())
    required = {"schema": "stegohive.finite_followup.v1", "evidence_class": EVIDENCE_CLASS,
                "codecs": list(CODECS), "factor_order": list(CHANNELS), "arms": list(ARMS),
                "side_information": ["public_only", "receiver_key"],
                "decoder": "training_only_lookup_majority_tie_and_unseen_zero",
                "views": "all_seven_nonempty_subsets",
                "analysis_unit": "world_with_paired_counterfactual_arms",
                "utility_gate": "exact_paired_task_payoff_equality_to_111",
                "confidence": "simultaneous_Hoeffding_95_percent_separately_by_declared_family",
                "retained_historical_worlds_loaded": 0}
    for key, value in required.items():
        if manifest.get(key) != value:
            raise ValueError(f"unsupported manifest contract: {key}")
    for key in ("seed", "train_worlds_per_codec", "holdout_worlds_per_codec"):
        if type(manifest.get(key)) is not int:
            raise ValueError(f"integer required: {key}")
    return manifest


def report_markdown(leakage, game):
    lines = ["# StegoHive finite follow-up results — September 11, 2026", "",
             "New planted reconstruction diagnostic and synthetic game census. Zero retained",
             "historical worlds were loaded. These results do not measure evolved collusion.", "",
             "See [protocol](../PROTOCOL.md), [game definition](../REPORTING_GAME.md),",
             "and [integrity receipt](receipt.json).", "",
             f"The leakage study has {leakage['independent_worlds']:,} independent world blocks",
             f"and {leakage['paired_arm_records']:,} paired arm records. Training and holdout are disjoint.", "",
             "## Held-out decoding with public side information", "",
             "| Codec / arm | Explicit | Timing | Artifact | Joint | Task payoff |",
             "|---|---:|---:|---:|---:|---:|"]
    def accuracy(codec, arm, view):
        return next(d["accuracy"] for d in leakage["decoding"] if d["codec"] == codec and d["arm"] == arm and d["view"] == view and d["side_information"] == "public_only")
    for codec in CODECS:
        for arm in ("111", "no_channel", "matched_noise", "destructive"):
            values = [accuracy(codec, arm, v) for v in (*CHANNELS, "+".join(CHANNELS))]
            payoff = next(p["task_payoff"] for p in leakage["task_payoff"] if p["codec"] == codec and p["arm"] == arm)
            lines.append(f"| {codec} / {arm} | " + " | ".join(f"{v:.3f}" for v in values + [payoff]) + " |")
    lines += ["", "The JSON reports all seven channel views, two side-information regimes,",
              "all factorial arms, paired control contrasts and conservative simultaneous",
              "intervals. The three-channel kernel has exact marginal and pairwise information",
              "zero, while joint information is one bit; its history-conditional increments",
              "are (0,0,1). With initialized independent keys, the artifact alone can reveal M.", "",
              "Near-chance empirical accuracy does not prove a null channel. Exact information",
              "claims come only from enumeration of the declared finite kernel. The field-aware",
              "audits preserve task payoff identically in every paired world; destructive",
              "erasure does not pass that utility gate. Utility preservation is a structural",
              "assumption of this fixture, not a discovered semantic audit.", "",
              "## Endogenous entry/report/dispute outcomes", "",
              "The complete pure SPE sets are separate from the 48-cell initialization census.",
              "Mixed SPE are characterized recursively in the game note, not numerically enumerated.", "",
              "| Scenario | Pure SPE count | Entries | Defection slash probabilities | Largest coalition gain |",
              "|---|---:|---|---|---:|"]
    for name, result in game["scenarios"].items():
        members = result["equilibrium_set"]["members"]
        entries = ", ".join(sorted({m["strategy"]["entry"] for m in members}))
        probabilities = ", ".join(map(str, sorted({m["induced_slash_probability_given_defection"] for m in members})))
        gain = max(m["coalition_audit"]["maximum_joint_gain"] for m in members)
        lines.append(f"| {name} | {len(members)} | {entries} | {probabilities} | {gain:g} |")
    lines += ["", "The exogenous comparator labels all eight scenario bonds weakly deterrent.",
              "Endogenous play exposes costly/privacy-suppressed reporting, honest exclusion,",
              "false-claim extortion, and profitable insider deviations. An honest quiet path",
              "alone is not a failed threat: inspect the response to counterfactual defection.",
              "The coalition test assumes enforceable commitment and transferable utility;",
              "within-coalition bounty transfers cancel. The protected scenario assumes that",
              "the reporter internalizes enough defection harm, and does not generalize to",
              "harm borne by outsiders. Basin cell counts are not behavioral probabilities.", "",
              "No decoder accuracy is converted into a valid-slash probability. No live system",
              "was changed. The executable verification replays this new study and checks",
              "input/source/output hashes; it does not verify historical ecology evidence.", ""]
    return "\n".join(lines).encode()


def build_artifacts():
    manifest = load_manifest()
    # Capture source/input identity before evaluating held-out output.
    sources = {path: sha((ROOT / path).read_bytes()) for path in SOURCE_PATHS}
    rows = generate(manifest["train_worlds_per_codec"], manifest["holdout_worlds_per_codec"], manifest["seed"])
    leakage = analyze(rows)
    game = run_study()
    raw = b"".join((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode() for row in rows)
    artifacts = {"worlds.jsonl.gz": gzip.compress(raw, mtime=0),
                 "leakage_summary.json": json_bytes(leakage),
                 "reporting_game_summary.json": json_bytes(game),
                 "RESULTS.md": report_markdown(leakage, game)}
    receipt = {"schema": "stegohive.finite_followup.receipt.v1", "evidence_class": EVIDENCE_CLASS,
               "historical_worlds_loaded": 0, "source_sha256": sources,
               "independent_worlds": leakage["independent_worlds"],
               "paired_arm_records": len(rows), "game_scenarios": len(game["scenarios"]),
               "outputs": {name: {"sha256": sha(data), "bytes": len(data)} for name, data in artifacts.items()},
               "verification_scope": "deterministic_new_study_replay_not_historical_verification"}
    artifacts["receipt.json"] = json_bytes(receipt)
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="replay and compare without writing")
    args = parser.parse_args()
    artifacts = build_artifacts()
    output = STUDY / "evidence"
    # Reject a redirected evidence directory; never write through the results junction.
    if output.resolve().parent != STUDY.resolve():
        raise ValueError("evidence directory must remain within this new study")
    if args.verify:
        mismatches = [name for name, data in artifacts.items() if not (output / name).is_file() or (output / name).read_bytes() != data]
        if mismatches:
            raise SystemExit("Replay verification failed: " + ", ".join(mismatches))
        print("Verified: source/input hashes, all world records, both analyses and receipt replay exactly.")
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, data in artifacts.items():
            if (output / name).is_symlink():
                raise ValueError("artifact path cannot be a symlink")
            (output / name).write_bytes(data)
        print(f"Wrote {len(artifacts)} new finite-study artifacts to {output}")


if __name__ == "__main__":
    main()
