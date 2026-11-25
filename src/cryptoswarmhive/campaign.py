"""Bounded offline CryptoSwarmHive study and full artifact replay verification."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

from . import EVIDENCE_CLASS
from .evaluation import SIDES, analyze_stress, exact_linear_information, run_selected, stress_rows
from .simulation import ARMS, CHANNELS, CODECS, ROLES, ROUNDS, game_census

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "experiments" / "cryptoswarmhive_eval_v1"
SOURCES = (
    "src/cryptoswarmhive/__init__.py", "src/cryptoswarmhive/simulation.py",
    "src/cryptoswarmhive/evaluation.py", "src/cryptoswarmhive/campaign.py",
    "src/stegohive_followup/reporting_game.py", "src/stegohive_followup/__init__.py",
    "experiments/cryptoswarmhive_eval_v1/manifest.json",
    "experiments/cryptoswarmhive_eval_v1/PROTOCOL.md",
    "experiments/stegohive_followup_20260911/REPORTING_GAME.md",
    "tests/test_cryptoswarmhive.py", "tests/test_stegohive_reporting_game.py",
)


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def compressed_rows(rows):
    return gzip.compress(b"".join((json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode() for r in rows), mtime=0)


def source_hashes():
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def load_manifest():
    config = json.loads((STUDY / "manifest.json").read_text())
    required = {"schema": "cryptoswarmhive.eval.v1", "evidence_class": EVIDENCE_CLASS,
                "roles": list(ROLES), "codecs": list(CODECS), "arms": list(ARMS),
                "side_information": list(SIDES), "rounds_per_world": ROUNDS,
                "simulation_only": True, "historical_worlds_loaded": 0,
                "decoder": "training_only_affine_GF2_parity_free_coefficients_zero_else_majority_tie_zero",
                "utility_gate": "exact_within_world_net_task_token_equality_to_111",
                "analysis_unit": "world; jobs, audit arms, equilibrium profiles and rollout rows are paired observations",
                "confidence": "separate_95pct_simultaneous_Hoeffding_families"}
    for key, expected in required.items():
        if config.get(key) != expected:
            raise ValueError(f"unsupported manifest contract: {key}")
    for key in ("seed", "train_worlds_per_codec", "holdout_worlds_per_codec", "selected_holdout_worlds"):
        if type(config.get(key)) is not int:
            raise ValueError(f"integer required: {key}")
    return config


def render_report(stress, census, selected, information):
    lines = ["# CryptoSwarmHive simulated evaluation — results", "",
             "Completed offline evaluation of six roles, four sequential jobs, and fake-token",
             "escrow. All results are new simulation evidence. No historical StegoHive worlds",
             "were loaded, and no live network, funds or model services were used.", "",
             "[Protocol](../PROTOCOL.md) · [Integrity receipt](receipt.json) ·",
             "[Leakage analysis](stress_summary.json) · [Exact information](exact_information.json) ·",
             "[Game correspondence and basins](game_census.json) · [Selected outcomes](selected_summary.json)", "",
             f"The stress study contains {stress['independent_worlds']:,} independent world blocks",
             f"and {stress['paired_records']:,} paired audit-arm records. The selected evaluation",
             f"adds {selected['paired_rollout_records']:,} rollout records on the same {selected['distinct_worlds']} held-out",
             "triple-policy world blocks; these are not additional independent samples.", "",
             "## Forced diagnostic participation", "",
             "| Policy | Explicit | Timing | Artifact | Joint | Joint 95% simultaneous interval | Matched-noise joint | Task success |",
             "|---|---:|---:|---:|---:|---|---:|---:|"]
    def decoded(codec, arm, view, side="public"):
        return next(d for d in stress["decoding"] if d["codec"] == codec and d["arm"] == arm and d["view"] == list(view) and d["side_information"] == side)
    for codec in CODECS:
        singles = [decoded(codec, "111", (c,))["accuracy"] for c in CHANNELS]
        joint = decoded(codec, "111", CHANNELS)
        noise = decoded(codec, "matched_noise", CHANNELS)["accuracy"]
        utility = next(u for u in stress["utility"] if u["codec"] == codec and u["arm"] == "111")
        ci = joint["simultaneous_95pct_interval"]
        lines.append(f"| {codec} | " + " | ".join(f"{v:.3f}" for v in singles) + f" | {joint['accuracy']:.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] | {noise:.3f} | {utility['success_rate']:.3f} |")
    matched = [u for u in stress["utility"] if u["arm"] != "destructive"]
    erased = [u for u in stress["utility"] if u["arm"] == "destructive"]
    lines += ["", f"All {len(matched)} utility-preserving policy/arm summaries pass exact within-world",
              "task-token equality. The destructive arms have task-success rates " +
              ", ".join(f"{u['codec']}: {u['success_rate']:.3f}" for u in erased) + ".",
              "They fail the utility gate. All seven views, both side-information regimes,",
              "eight factorial arms, controls and world-paired contrasts appear in the JSON.", "",
              "## What the conditional audit establishes", "",
              "| Policy / access | Exact single-channel history information | Joint bits | Twelve chronological increments |",
              "|---|---|---:|---|"]
    for codec, arm, side in (("triple_xor", "111", "public"), ("history_xor", "111", "public"), ("triple_xor", "001", "initialized_keys")):
        entry = next(x for x in information if (x["codec"], x["arm"], x["side_information"]) == (codec, arm, side))
        lines.append(f"| {codec}/{arm}/{side} | {entry['single_channel_history_information_bits']} | {entry['joint_information_bits']} | {entry['conditional_event_increments']} |")
    lines += ["", "The single-channel column is marginal without keys; the joint/increment columns",
              "condition on the stated access. Initialized keys can reveal a message from one",
              "otherwise null channel. The history policy discloses its bit only at the last",
              "artifact when prior observations are included. Exact results use the linear",
              "rank identity for this planted kernel, not empirical failure to decode.", "",
              "## Endogenous game and actual settlement (intact arm)", "",
              "| Scenario | Pure SPE | Entry outcomes | Defection-contingent slash probability | Max insider deviation gain | Honest continuation | Selected joint decode |",
              "|---|---:|---|---|---:|---|---|"]
    for scenario, result in census["111"].items():
        members = result["equilibrium_set"]["members"]
        entries = ", ".join(sorted({m["strategy"]["entry"] for m in members}))
        probabilities = ", ".join(str(v) for v in sorted({m["induced_slash_probability_given_defection"] for m in members}))
        gains = max(m["coalition_audit"]["maximum_joint_gain"] for m in members)
        honest = ", ".join(str(v) for v in sorted({m["honest_entry_continuation_payoff"] for m in members}))
        decoded_values = [d["accuracy"] for outcome in selected["outcomes"] if outcome["arm"] == "111" and outcome["scenario"] == scenario for d in outcome["decoding"] if d["view"] == list(CHANNELS) and d["side_information"] == "public"]
        lines.append(f"| {scenario} | {len(members)} | {entries} | {probabilities} | {gains:g} | {honest} | " + ", ".join(f"{v:.3f}" for v in sorted(set(decoded_values))) + " |")
    lines += ["", f"Selected decoding uses frozen stress-training decoders on {selected['distinct_worlds']} held-out worlds",
              "per equilibrium. Intervals and all channel views are in selected_summary.json.",
              "Honest policies send the independent surrogate; excluded workers complete no",
              "jobs. Thus low selected leakage is not a certificate that the channel is safe.", "",
              "The fixed-probability comparator marks all eight intact-arm bonds weakly",
              "deterrent. Costly reporting and privacy select silent defection; liquidity",
              "and false-claim extortion exclude honest workers. Individual honest compliance",
              "can still admit a profitable entrant+reporter deviation. Only the scenario",
              "where the reporter internalizes defection harm passes the declared coalition",
              "criteria for the intact arm. That assumption does not protect against harms",
              "borne by outsiders. Initial-cell counts are separate from equilibrium sets",
              "and are not empirical learning probabilities. Mixed SPE are described in the",
              "protocol's recursive correspondence but are not numerically enumerated.", "",
              "Every selected ledger conserves 300 fake tokens and closes escrow. The bounty",
              "cancels in entrant+reporter joint payoff; external slash and real costs remain.",
              "Slashing is based on unauthorized-diversion receipts and a declared joint",
              "evidence kernel. No message-decoding rate is treated as a fraud-proof rate.", "",
              "## Interpretation and limits", "",
              "This applies the StegoHive follow-up to an operating finite swarm/escrow model:",
              "joint observations and earlier events expose planted signals, matched audits",
              "preserve task payoff, and endogenous reporting changes realized behavior.",
              "It does not establish emerged collusion, learned semantic audit performance,",
              "real-world crypto security or arbitrary-adversary deterrence. Audit field",
              "separation, perfect observation of entry action, risk neutrality and binding",
              "coalition commitment are explicit assumptions. Near-chance empirical scores",
              "are not proof of zero information. Repeated worlds across arms and equilibria",
              "must remain paired. See the protocol and completion audit for reproduction and",
              "requirement-level verification.", ""]
    return "\n".join(lines).encode()


def build_artifacts():
    config = load_manifest()
    sources = source_hashes()
    rows = stress_rows(config)
    stress = analyze_stress(rows)
    census = game_census()
    selected_rows, selected = run_selected(config, census, stress)
    information = [exact_linear_information(codec, arm, side) for codec in CODECS for arm in ARMS for side in SIDES]
    artifacts = {
        "stress_worlds.jsonl.gz": compressed_rows(rows), "stress_summary.json": json_bytes(stress),
        "game_census.json": json_bytes({"evidence_class": EVIDENCE_CLASS, "scope": "exact finite games and separate initialization basins", "games": census}),
        "selected_worlds.jsonl.gz": compressed_rows(selected_rows), "selected_summary.json": json_bytes(selected),
        "exact_information.json": json_bytes({"evidence_class": EVIDENCE_CLASS, "scope": "exact planted linear kernel", "records": information}),
        "RESULTS.md": render_report(stress, census, selected, information),
    }
    if source_hashes() != sources:
        raise RuntimeError("source/input changed during campaign")
    receipt = {"schema": "cryptoswarmhive.receipt.v1", "evidence_class": EVIDENCE_CLASS,
               "historical_worlds_loaded": 0, "source_sha256": sources,
               "independent_stress_worlds": stress["independent_worlds"], "paired_stress_records": len(rows),
               "selected_overlapping_worlds": selected["distinct_worlds"], "selected_rollout_records": len(selected_rows),
               "scope": "same-source deterministic replay plus separate invariant tests",
               "outputs": {name: {"bytes": len(data), "sha256": sha256(data).hexdigest()} for name, data in artifacts.items()}}
    artifacts["receipt.json"] = json_bytes(receipt)
    return artifacts


def verify_artifacts(output, expected):
    mismatches = [name for name, data in expected.items() if not (output / name).is_file() or (output / name).read_bytes() != data]
    if mismatches:
        raise ValueError("artifact replay mismatch: " + ", ".join(mismatches))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="recompute and compare all artifacts without writing")
    args = parser.parse_args()
    output = STUDY / "evidence"
    if output.resolve().parent != STUDY.resolve():
        raise ValueError("output must stay inside this new experiment")
    artifacts = build_artifacts()
    if args.verify:
        verify_artifacts(output, artifacts)
        print("Verified all CryptoSwarmHive artifacts by deterministic replay, including source hashes and selected ledgers.")
    else:
        output.mkdir(parents=True, exist_ok=True)
        if any((output / name).is_symlink() for name in artifacts):
            raise ValueError("refusing redirected artifact")
        for name, data in artifacts.items():
            (output / name).write_bytes(data)
        print(f"Wrote {len(artifacts)} simulated-evaluation artifacts to {output}")


if __name__ == "__main__":
    main()
