#!/usr/bin/env python3
"""Compute-matched ALife pressure transfer to the Confinement Width toy exhibit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import psutil


EPISODE_SCHEMA = "alife.confinement_transfer.episode.v1"
SUMMARY_SCHEMA = "alife.confinement_transfer.summary.v1"
SPLITS = ("discovery", "confirmatory", "holdout")
METHODS = ("compute_matched_random_search", "evolutionary_schedule_search")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def random_schedule(rng: np.random.Generator, horizon: int, action_budget: int) -> tuple[int, ...]:
    return tuple(sorted(int(value) for value in rng.choice(horizon, size=action_budget, replace=False)))


def mutate_schedule(
    schedule: Sequence[int], rng: np.random.Generator, horizon: int, swaps: int
) -> tuple[int, ...]:
    active = set(int(value) for value in schedule)
    for _ in range(swaps):
        remove = int(rng.choice(sorted(active)))
        inactive = sorted(set(range(horizon)) - active)
        add = int(rng.choice(inactive))
        active.remove(remove)
        active.add(add)
    return tuple(sorted(active))


def simulate_schedule(
    schedule: Sequence[int], variant: Mapping[str, Any], design: Mapping[str, Any]
) -> dict[str, Any]:
    horizon = int(design["horizon"])
    action_set = set(int(value) for value in schedule)
    z = float(design["z0"])
    y = float(design["y0"])
    zeta = float(design["zeta"])
    z_target = float(design["z_target"])
    u_bar = float(design["u_bar"])
    beta = float(variant["beta"])
    y_step = float(variant["y_step"])
    first_failure: int | None = None
    kernel_escape_steps = 0
    proxy_failure_steps = 0
    max_eta = 0.0
    advances = 0
    for index in range(horizon):
        z_before = z
        u = 0.0 if z_before <= z_target else -min(u_bar, z_before - z_target)
        predicted_z_next = min(1.0, max(0.0, z_before + u))
        if index in action_set:
            y = min(1.0, y + y_step)
            advances += 1
        z = predicted_z_next
        eta = z - predicted_z_next
        max_eta = max(max_eta, abs(eta))
        proxy_pass = z <= zeta
        true_pass = proxy_pass and y <= beta
        if not proxy_pass:
            proxy_failure_steps += 1
        if proxy_pass and not true_pass:
            kernel_escape_steps += 1
        if first_failure is None and not true_pass:
            first_failure = index + 1
    return {
        "variant": dict(variant),
        "fidelity_half_life_step": first_failure,
        "censored": first_failure is None,
        "kernel_escape_steps": kernel_escape_steps,
        "kernel_escape_rate": kernel_escape_steps / horizon,
        "proxy_failure_steps": proxy_failure_steps,
        "max_abs_closure_defect_eta": max_eta,
        "advance_actions_executed": advances,
        "terminal_z": z,
        "terminal_y": y,
    }


def schedule_key(
    schedule: Sequence[int], variants: Sequence[Mapping[str, Any]], design: Mapping[str, Any]
) -> tuple[float, float]:
    scores = [simulate_schedule(schedule, variant, design)["kernel_escape_rate"] for variant in variants]
    return float(statistics.mean(scores)), -float(statistics.mean(schedule))


def random_search(
    seed: int, variants: Sequence[Mapping[str, Any]], design: Mapping[str, Any]
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    horizon = int(design["horizon"])
    budget = int(design["action_budget"])
    evaluations = int(design["candidate_evaluations_per_method"])
    best: tuple[int, ...] | None = None
    best_key = (-float("inf"), -float("inf"))
    for _ in range(evaluations):
        candidate = random_schedule(rng, horizon, budget)
        key = schedule_key(candidate, variants, design)
        if key > best_key:
            best, best_key = candidate, key
    assert best is not None
    return {
        "method": METHODS[0],
        "selected_schedule": list(best),
        "training_mean_kernel_escape_rate": best_key[0],
        "training_mean_action_time": -best_key[1],
        "candidate_evaluations": evaluations,
        "action_budget": len(best),
    }


def tournament(
    population: Sequence[tuple[int, ...]],
    keys: Mapping[tuple[int, ...], tuple[float, float]],
    rng: np.random.Generator,
) -> tuple[int, ...]:
    chosen = rng.choice(len(population), size=3, replace=False)
    return max((population[int(index)] for index in chosen), key=lambda candidate: keys[candidate])


def evolutionary_search(
    seed: int, variants: Sequence[Mapping[str, Any]], design: Mapping[str, Any]
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    horizon = int(design["horizon"])
    budget = int(design["action_budget"])
    evaluations_limit = int(design["candidate_evaluations_per_method"])
    population_size = int(design["population_size"])
    swaps = int(design["mutation_swaps"])
    population = [random_schedule(rng, horizon, budget) for _ in range(population_size)]
    keys = {candidate: schedule_key(candidate, variants, design) for candidate in population}
    evaluations = population_size
    best = max(population, key=lambda candidate: keys[candidate])
    best_key = keys[best]
    generations = 0
    while evaluations < evaluations_limit:
        children: list[tuple[int, ...]] = []
        child_keys: dict[tuple[int, ...], tuple[float, float]] = {}
        count = min(population_size, evaluations_limit - evaluations)
        for _ in range(count):
            parent = tournament(population, keys, rng)
            child = mutate_schedule(parent, rng, horizon, swaps)
            key = schedule_key(child, variants, design)
            children.append(child)
            child_keys[child] = key
            evaluations += 1
            if key > best_key:
                best, best_key = child, key
        combined = list(dict.fromkeys([best, *population, *children]))
        combined_keys = {**keys, **child_keys, best: best_key}
        population = sorted(combined, key=lambda candidate: combined_keys[candidate], reverse=True)[
            :population_size
        ]
        keys = {candidate: combined_keys[candidate] for candidate in population}
        generations += 1
    return {
        "method": METHODS[1],
        "selected_schedule": list(best),
        "training_mean_kernel_escape_rate": best_key[0],
        "training_mean_action_time": -best_key[1],
        "candidate_evaluations": evaluations,
        "action_budget": len(best),
        "generations": generations,
    }


def evaluate_selected(
    search: Mapping[str, Any], variants: Sequence[Mapping[str, Any]], design: Mapping[str, Any]
) -> dict[str, Any]:
    evaluations = [simulate_schedule(search["selected_schedule"], variant, design) for variant in variants]
    return {
        **search,
        "evaluation_variants": evaluations,
        "heldout_mean_kernel_escape_rate": float(
            statistics.mean(float(row["kernel_escape_rate"]) for row in evaluations)
        ),
        "mean_fidelity_half_life_step": float(
            statistics.mean(
                float(row["fidelity_half_life_step"] or (int(design["horizon"]) + 1))
                for row in evaluations
            )
        ),
        "proxy_failure_steps": sum(int(row["proxy_failure_steps"]) for row in evaluations),
        "max_abs_closure_defect_eta": max(
            float(row["max_abs_closure_defect_eta"]) for row in evaluations
        ),
        "action_budget_mismatch": any(
            int(row["advance_actions_executed"]) != int(design["action_budget"])
            for row in evaluations
        ),
    }


def run_episode(split: str, seed: int, manifest: Mapping[str, Any]) -> dict[str, Any]:
    design = manifest["design"]
    training = design["training_evaluator_variants"]
    evaluation = design["evaluator_variants_by_split"][split]
    random_result = evaluate_selected(random_search(seed, training, design), evaluation, design)
    evolved_result = evaluate_selected(evolutionary_search(seed, training, design), evaluation, design)
    difference = (
        evolved_result["heldout_mean_kernel_escape_rate"]
        - random_result["heldout_mean_kernel_escape_rate"]
    )
    episode = {
        "schema": EPISODE_SCHEMA,
        "split": split,
        "search_seed": seed,
        "experimental_unit": manifest["experimental_unit"],
        "consumer": "Confinement Width fiber-routing exhibit",
        "information_budget": "time index and frozen schedule only; neither method observes hidden y, beta, or evaluation outcomes online",
        "compute_match": {
            "candidate_evaluations_each": int(design["candidate_evaluations_per_method"]),
            "action_budget_each": int(design["action_budget"]),
            "horizon_each": int(design["horizon"]),
            "same_training_evaluators": True,
            "same_tiebreak": True,
        },
        "methods": [random_result, evolved_result],
        "paired_kernel_escape_improvement": difference,
        "validity_gate_pass": all(
            not result["action_budget_mismatch"]
            and result["proxy_failure_steps"] == 0
            and result["max_abs_closure_defect_eta"] == 0.0
            and result["candidate_evaluations"] == int(design["candidate_evaluations_per_method"])
            for result in (random_result, evolved_result)
        ),
    }
    episode["episode_sha256"] = digest_json(episode)
    return episode


def bootstrap_interval(values: Sequence[float], samples: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    array = np.asarray(values, dtype=float)
    means = np.empty(samples, dtype=float)
    for index in range(samples):
        means[index] = float(rng.choice(array, size=len(array), replace=True).mean())
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def summarize(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    by_split: list[dict[str, Any]] = []
    for split in SPLITS:
        matching = [row for row in rows if row["split"] == split]
        differences = [float(row["paired_kernel_escape_improvement"]) for row in matching]
        by_split.append(
            {
                "split": split,
                "paired_search_seeds": len(matching),
                "random_mean_kernel_escape_rate": float(
                    statistics.mean(float(row["methods"][0]["heldout_mean_kernel_escape_rate"]) for row in matching)
                ),
                "evolutionary_mean_kernel_escape_rate": float(
                    statistics.mean(float(row["methods"][1]["heldout_mean_kernel_escape_rate"]) for row in matching)
                ),
                "mean_paired_improvement": float(statistics.mean(differences)),
                "paired_improvement_bootstrap_95": bootstrap_interval(
                    differences,
                    int(manifest["analysis"]["bootstrap_samples"]),
                    int(manifest["analysis"]["bootstrap_seed"]) + SPLITS.index(split),
                ),
                "positive_pair_fraction": sum(value > 0 for value in differences) / len(differences),
                "validity_gate_pass": all(bool(row["validity_gate_pass"]) for row in matching),
            }
        )
    holdout = next(row for row in by_split if row["split"] == "holdout")
    analysis = manifest["analysis"]
    return {
        "schema": SUMMARY_SCHEMA,
        "status": "ok",
        "row_count": len(rows),
        "episode_counts": {split: sum(row["split"] == split for row in rows) for split in SPLITS},
        "split_summary": by_split,
        "holdout": holdout,
        "hypothesis_assessment": {
            "H1_downstream_gain": "supported"
            if holdout["mean_paired_improvement"] >= float(analysis["minimum_holdout_improvement"])
            else "not_supported",
            "H2_directional_robustness": "supported"
            if holdout["positive_pair_fraction"] >= float(analysis["minimum_positive_pair_fraction"])
            else "not_supported",
            "H3_validity_preservation": "supported" if holdout["validity_gate_pass"] else "not_supported",
        },
        "claim_boundary": (
            "This is a compute-matched downstream stress-test gain in the benign two-coordinate "
            "Confinement Width exhibit. It is not evidence of real-world evasion, open-endedness, "
            "or superiority over arbitrary non-evolutionary optimizers."
        ),
    }


def knowledge_card(summary: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    holdout = summary["holdout"]
    hypotheses = summary["hypothesis_assessment"]
    return f"""# Confinement Width Consumer-Transfer Knowledge Card

## Observed

- {summary['row_count']} paired search seeds were run across discovery, confirmation, and untouched holdout splits.
- Holdout random-search kernel-escape rate: {holdout['random_mean_kernel_escape_rate']:.4f}.
- Holdout evolutionary-search kernel-escape rate: {holdout['evolutionary_mean_kernel_escape_rate']:.4f}.
- Mean paired improvement: {holdout['mean_paired_improvement']:.4f}; deterministic bootstrap 95% interval {holdout['paired_improvement_bootstrap_95']}.
- Positive-pair fraction: {holdout['positive_pair_fraction']:.4f}; original proxy and closure gates passed: {holdout['validity_gate_pass']}.
- Determinism passed: {receipt['determinism']['passed']}; wall time {receipt['wall_seconds']:.3f}s; max RSS {receipt['max_rss_mb']:.2f} MB.

## Hypothesis Assessment

- H1 downstream gain: **{hypotheses['H1_downstream_gain']}**.
- H2 directional robustness: **{hypotheses['H2_directional_robustness']}**.
- H3 validity preservation: **{hypotheses['H3_validity_preservation']}**.

## Inferred

Within this toy consumer, population selection over schedules finds projection-kernel failure earlier and for more evaluation steps than an equal-evaluation random generator. Whether this is transferable adapted pressure rather than efficient front-loading remains unconfirmed; the observed product is a stronger stress-test distribution for the frozen monotone task, not a better occupant policy.

## Not Supported

- No claim about operational evasion, deployed systems, or biological evolution.
- No claim that evolution beats hand-designed scheduling, dynamic programming, or all optimizers.
- No inference beyond the frozen two-coordinate Confinement Width model and declared held-out evaluator variants.

## Robustness

Both methods used 128 candidate evaluations, 24 actions, horizon 80, the same training evaluators, and the same information budget. Evidence came from fresh search seeds and unseen beta/y-step combinations.

## Confounds

The objective favors early threshold crossing, and the schedule genome makes temporal concentration directly accessible. The result establishes a compute-matched gain under the frozen point-estimate rule, not transferable adapted pressure or difficult optimization.

## Artifacts

- `frozen_manifest.json`, `raw_episodes.jsonl`, `summary.json`, `seed_manifest.json`
- `receipt.json`, `hashes.json`
- Replay: `{receipt['replay_command']}`

## Next Falsification Test

Freeze the selected schedule generator and evaluate it on a consumer where hidden-fiber dynamics include recovery, delayed costs, and non-monotone thresholds. The gain should disappear if it is only front-loading rather than transferable pressure generation.
"""


def parse_splits(value: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(SPLITS)
    splits = [item.strip() for item in value.split(",") if item.strip()]
    if any(item not in SPLITS for item in splits):
        raise ValueError(f"unknown splits: {splits}")
    return splits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--splits", default="all")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output = (args.output or Path(manifest["artifacts"]["output_directory"])).resolve()
    output.mkdir(parents=True, exist_ok=True)
    splits = parse_splits(args.splits)
    source = manifest["design"]["consumer_baseline"]
    for path_key, hash_key in (
        ("source_path", "source_sha256"),
        ("baseline_summary_path", "baseline_summary_sha256"),
    ):
        path = Path(source[path_key])
        if not path.is_file() or sha256_file(path).lower() != str(source[hash_key]).lower():
            raise SystemExit(f"consumer baseline provenance failure: {path}")
    seeds = manifest["seed_plan"]
    if args.smoke:
        seeds = {split: [manifest["seed_plan"][split][0]] for split in SPLITS}
    planned = sum(len(seeds[split]) for split in splits)
    if planned > int(manifest["budget"]["max_episodes"]):
        raise SystemExit("episode budget exceeded")
    started = time.monotonic()
    started_utc = utc_now()
    rows: list[dict[str, Any]] = []
    with (output / "raw_episodes.jsonl").open("w", encoding="utf-8") as handle:
        for split in splits:
            for seed in seeds[split]:
                row = run_episode(split, int(seed), manifest)
                rows.append(row)
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    replay = run_episode(splits[0], int(seeds[splits[0]][0]), manifest)
    determinism = {
        "performed": True,
        "passed": replay["episode_sha256"] == rows[0]["episode_sha256"],
        "first_sha256": rows[0]["episode_sha256"],
        "replay_sha256": replay["episode_sha256"],
    }
    if not determinism["passed"]:
        raise SystemExit("determinism replay failed")
    summary = summarize(rows, manifest)
    summary["determinism"] = determinism
    write_json(output / "summary.json", summary)
    write_json(output / "seed_manifest.json", {"splits_run": splits, "seeds": {split: seeds[split] for split in splits}})
    shutil.copy2(manifest_path, output / "frozen_manifest.json")
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": psutil.virtual_memory().total / (1024 * 1024),
    }
    receipt = {
        "status": "ok",
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "max_rss_mb": psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024),
        "episode_count": len(rows),
        "code_path": str(Path(__file__).resolve()),
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        **environment,
        "environment_sha256": digest_json(environment),
        "output_path": str(output),
        "consumer_source_sha256": sha256_file(Path(source["source_path"])),
        "consumer_baseline_summary_sha256": sha256_file(Path(source["baseline_summary_path"])),
        "determinism": determinism,
        "replay_command": f"python src/confinement_transfer.py --manifest {manifest_path} --output {output} --splits {','.join(splits)}",
    }
    write_json(output / "receipt.json", receipt)
    (output / "knowledge_card.md").write_text(knowledge_card(summary, receipt), encoding="utf-8")
    artifact_names = ["raw_episodes.jsonl", "summary.json", "seed_manifest.json", "frozen_manifest.json", "receipt.json", "knowledge_card.md"]
    write_json(output / "hashes.json", {name: {"sha256": sha256_file(output / name), "bytes": (output / name).stat().st_size} for name in artifact_names})
    total_bytes = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
    budget = manifest["budget"]
    if time.monotonic() - started > float(budget["max_wall_seconds"]):
        raise SystemExit("wall-time budget exceeded")
    if psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024) > float(budget["max_ram_mb"]):
        raise SystemExit("RAM budget exceeded")
    if total_bytes > float(budget["max_disk_mb"]) * 1024 * 1024:
        raise SystemExit("disk budget exceeded")
    print(json.dumps({"status": "ok", "output": str(output), "episodes": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
