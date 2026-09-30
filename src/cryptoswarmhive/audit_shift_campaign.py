"""Run and replay the frozen v2 audit-transfer diagnostic."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

from .audit_shift import ARMS, EVIDENCE_CLASS, LAYOUTS, calibration_rows, fit_audit, run_evaluation

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "experiments" / "cryptoswarmhive_audit_shift_v2"
SOURCES = (
    "src/cryptoswarmhive/__init__.py", "src/cryptoswarmhive/audit_shift.py",
    "src/cryptoswarmhive/audit_shift_campaign.py", "src/cryptoswarmhive/simulation.py",
    "src/cryptoswarmhive/evaluation.py", "src/stegohive_followup/reporting_game.py",
    "src/stegohive_followup/__init__.py", "tests/test_cryptoswarmhive_audit_shift.py",
    "experiments/cryptoswarmhive_audit_shift_v2/manifest.json",
    "experiments/cryptoswarmhive_audit_shift_v2/PROTOCOL.md",
)


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def row_bytes(rows):
    return gzip.compress(b"".join((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode() for row in rows), mtime=0)


def load_config():
    config = json.loads((STUDY / "manifest.json").read_text())
    fixed = {"schema": "cryptoswarmhive.audit_shift.v2", "evidence_class": EVIDENCE_CLASS,
             "candidate_masks": 64, "layouts": list(LAYOUTS), "arms": list(ARMS),
             "calibration_access": "world_id_and_paired_task_scores_only",
             "selection": "most_erased_fields_with_simultaneous_binomial_harm_upper_bound_at_most_tolerance_then_lexical",
             "freeze_before": "decoder_training_and_holdout", "historical_worlds_loaded": 0, "simulation_only": True}
    for key, value in fixed.items():
        if config.get(key) != value:
            raise ValueError(f"unsupported contract: {key}")
    for key in ("seed", "calibration_worlds", "decoder_train_worlds", "holdout_worlds"):
        if type(config.get(key)) is not int:
            raise ValueError(f"integer required: {key}")
    return config


def render_report(config, policy, summary):
    selected = next(c for c in policy["candidates"] if c["mask"] == policy["frozen_mask"])
    lines = ["# CryptoSwarmHive v2 — audit-transfer results", "",
             "A task-only learned audit succeeded under its calibration schema but failed",
             "under a controlled swap of field meanings. This is new synthetic evidence,",
             "separate from v1 and historical StegoHive worlds.", "",
             "[Protocol](../PROTOCOL.md) · [Frozen audit](audit_freeze.json) ·",
             "[Decoding and utility](summary.json) · [Exact reporting games](game_census.json) · [Receipt](receipt.json)", "",
             f"Calibration used {policy['calibration_worlds']} world blocks and 64 candidate masks, with",
             "task outcomes as its only feedback. The frozen mask is `" + policy["frozen_mask"] + "` (1 = erase).",
             f"It erased {selected['erased_fields']} fields, harmed {selected['harmed_worlds']} calibration worlds, and had",
             f"a simultaneous harm-probability upper bound of {selected['harm_probability_upper_95pct_simultaneous']:.4f}",
             f"against the fixed {policy['harm_tolerance']:.2f} tolerance. Calibration eligibility: {selected['eligible']}.", "",
             f"Evaluation used {config['decoder_train_worlds']} separate decoder-training and {config['holdout_worlds']} held-out world",
             f"blocks, paired across layouts and arms ({summary['paired_layout_arm_records']:,} records).",
             "The auditor was frozen before those phases. Each layout has its own training-only",
             "diagnostic decoder, so representation shift cannot hide leakage from the evaluator.", "",
             "| Layout / arm | Joint decode | Same-audit noise decode | Task value | Harmed worlds | Harm upper bound | Exact joint bits |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    def joint(layout, arm):
        return next(d for d in summary["decoding"] if d["layout"] == layout and d["arm"] == arm and len(d["view"]) == 3 and d["side_information"] == "public")
    for layout in LAYOUTS:
        for arm in ("calibrated", "oracle"):
            decoded = joint(layout, arm)
            utility = next(u for u in summary["utility"] if u["layout"] == layout and u["arm"] == arm)
            control = joint(layout, "calibrated_noise" if arm == "calibrated" else "no_channel")
            lines.append(f"| {layout}/{arm} | {decoded['accuracy']:.3f} | {control['accuracy']:.3f} | {utility['mean_net_task_tokens']:.3f} | {utility['harmed_worlds']}/{utility['holdout_worlds']} | {utility['harm_upper_95pct_simultaneous']:.3f} | {decoded['exact_joint_information_bits']} |")
    lines += ["", "The oracle row's control is its duplicate no-channel arm; it is not a learned",
              "policy. Full tables include all seven observation subsets and initialized-key",
              "side information, with 294 simultaneous decoder comparisons. Near-chance",
              "empirical decoding is not proof of zero information. Exact joint-bit claims",
              "apply only to the declared independent-pad parity kernel.", "",
              "## Propagation into entry and reporting", "",
              "Each game's task value is independently enumerated from the task/error model,",
              "not fitted from held-out rewards. Pure SPE sets and initialization basins remain",
              "separate. The following table uses the calibrated audit and credible-threat",
              "scenario; the JSON retains all eight scenarios for every layout/arm.", "",
              "| Layout | Exact expected task value | Pure SPE entry | Honest exclusion | Insider gain |",
              "|---|---|---|---|---|"]
    for layout in LAYOUTS:
        game = summary["games"][layout]["calibrated"]["credible_threat"]
        members = game["equilibrium_set"]["members"]
        entries = ", ".join(sorted({m["strategy"]["entry"] for m in members}))
        exclusions = ", ".join(map(str, sorted({m["failure_flags"]["honest_exclusion"] for m in members})))
        gains = ", ".join(str(x) for x in sorted({m["coalition_audit"]["maximum_joint_gain"] for m in members}))
        lines.append(f"| {layout} | {game['parameters_exact']['honest_value']} | {entries} | {exclusions} | {gains} |")
    lines += ["", "These are counterfactual exact games, not additional settlement or learning",
              "rollouts. The prior bounty-transfer cancellation and reporting-cost assumptions",
              "remain in force. No decoder score is converted into a fraud-proof probability.", "",
              "## Conclusion supported by this fixture", "",
              "Calibration establishes a distribution-specific audit, not a semantic invariant.",
              "When every field meaning swaps, the same mask removes task hints and leaves all",
              "three diagnostic shares. Joint leakage returns while useful work declines enough",
              "to exclude honest workers in the default game. The privileged current-schema",
              "audit still preserves utility and removes the signal, identifying a transfer",
              "failure rather than an unavoidable task/privacy tradeoff in this toy model.", "",
              "The shifts are designed stress cases with a known causal explanation. This is",
              "not evidence of emerged evasion, a real semantic audit, or the frequency of such",
              "failures in production. No existing campaign evidence was pooled, and no live",
              "systems or real funds were used.", ""]
    return "\n".join(lines).encode()


def build_artifacts():
    config = load_config()
    sources = {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCES}
    calibration = calibration_rows(config["calibration_worlds"], config["seed"])
    policy = fit_audit(calibration, config["harm_tolerance"])
    # Persist provenance outside the learner's strictly task-only input schema.
    calibration_data = row_bytes([{"evidence_class": EVIDENCE_CLASS, "task_feedback": row} for row in calibration])
    freeze = {**policy, "calibration_sha256": sha256(calibration_data).hexdigest(),
              "source_sha256": sources, "freeze_stage": "before_decoder_training_and_holdout"}
    freeze_data = json_bytes(freeze)
    rows, summary = run_evaluation(config, policy)
    games = summary["games"]
    report = render_report(config, policy, summary)
    summary = {k: v for k, v in summary.items() if k != "games"}
    artifacts = {"calibration_task_scores.jsonl.gz": calibration_data, "audit_freeze.json": freeze_data,
                 "evaluation_worlds.jsonl.gz": row_bytes(rows), "summary.json": json_bytes(summary),
                 "game_census.json": json_bytes({"evidence_class": EVIDENCE_CLASS, "scope": "counterfactual exact games, not realized rollouts", "games": games}),
                 "RESULTS.md": report}
    if sources != {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCES}:
        raise RuntimeError("source changed during run")
    receipt = {"evidence_class": EVIDENCE_CLASS, "source_sha256": sources, "historical_worlds_loaded": 0,
               "independent_world_blocks": config["calibration_worlds"] + summary["fresh_world_blocks"],
               "paired_evaluation_records": len(rows), "audit_frozen_before_evaluation_sha256": sha256(freeze_data).hexdigest(),
               "outputs": {name: {"sha256": sha256(data).hexdigest(), "bytes": len(data)} for name, data in artifacts.items()}}
    artifacts["receipt.json"] = json_bytes(receipt)
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = STUDY / "evidence"
    if output.resolve().parent != STUDY.resolve():
        raise ValueError("output must stay inside the v2 experiment")
    artifacts = build_artifacts()
    if args.verify:
        mismatches = [name for name, data in artifacts.items() if not (output / name).is_file() or (output / name).read_bytes() != data]
        if mismatches:
            raise ValueError("replay mismatch: " + ", ".join(mismatches))
        print("Verified all v2 artifacts, audit freeze, source hashes and deterministic replay.")
    else:
        output.mkdir(parents=True, exist_ok=True)
        if any((output / name).is_symlink() for name in artifacts):
            raise ValueError("artifact redirect rejected")
        for name, data in artifacts.items():
            (output / name).write_bytes(data)
        print(f"Wrote {len(artifacts)} v2 artifacts to {output}")


if __name__ == "__main__":
    main()
