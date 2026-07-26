from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph_investigator_gym import (  # noqa: E402
    MODEL_NAMES,
    BayesianInvestigator,
    SealedTaskEnvironment,
    build_task_bank,
    credible_set,
    evaluate_policy,
    lattice_step,
    normalized_patch_laplacian,
    run_audit_fixtures,
    smooth_patch_priors,
)
from graph_state_lab import run_episode  # noqa: E402


class GraphInvestigatorGymTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (
                ROOT
                / "experiments"
                / "graph_investigator_gym_v1"
                / "manifest.json"
            ).read_text(encoding="utf-8")
        )
        cls.patch = cls.manifest["design"]["patches"][0]
        cls.small_manifest = json.loads(json.dumps(cls.manifest))
        cls.small_manifest["design"]["split_design"]["discovery"].update(
            {
                "nodes": 48,
                "state_dimension": 4,
                "steps": 8,
                "burn_in": 2,
            }
        )
        cls.task, cls.graph_rows = build_task_bank(
            cls.small_manifest,
            "discovery",
            7771,
            cls.patch,
            time.monotonic() + 120,
            1024,
        )

    def test_manifest_counts_and_metric_firewall(self) -> None:
        patches = len(self.manifest["design"]["patches"])
        tasks = sum(
            len(self.manifest["seed_plan"][split]) * patches
            for split in ("discovery", "confirmatory", "holdout")
        )
        pairs = (
            self.manifest["design"]["pairs_per_descriptor"] * 3
        )
        self.assertEqual(tasks, 112)
        self.assertEqual(tasks, self.manifest["budget"]["max_episodes"])
        self.assertEqual(
            tasks * pairs * 2, self.manifest["budget"]["max_graph_arms"]
        )
        self.assertFalse(
            set(self.manifest["metrics"]["selection"])
            & set(self.manifest["metrics"]["evidence"])
        )

    def test_task_bank_has_disjoint_invariant_pairs_and_exposure(self) -> None:
        self.assertEqual(len(self.task["candidates"]), 12)
        self.assertEqual(len(self.graph_rows), 24)
        graph_ids = []
        edge_hashes = []
        for candidate in self.task["candidates"]:
            graph_ids.extend(
                [candidate["left_graph_id"], candidate["right_graph_id"]]
            )
            edge_hashes.extend(
                [
                    candidate["left_edge_sha256"],
                    candidate["right_edge_sha256"],
                ]
            )
            self.assertEqual(
                candidate["exposure"]["executed_perturbations"], 2
            )
            self.assertGreater(candidate["target_separation_z"], 0.0)
        self.assertEqual(len(graph_ids), len(set(graph_ids)))
        self.assertEqual(len(edge_hashes), len(set(edge_hashes)))
        for row in self.graph_rows:
            self.assertTrue(row["intervention"]["executed"])
            self.assertEqual(row["graph"]["edge_sha256"], next(
                value
                for candidate in self.task["candidates"]
                for value in (
                    candidate["left_edge_sha256"],
                    candidate["right_edge_sha256"],
                )
                if value == row["graph"]["edge_sha256"]
            ))

    def test_sealed_environment_public_candidates_exclude_outcomes(self) -> None:
        environment = SealedTaskEnvironment(self.task)
        candidates = environment.candidates()
        self.assertEqual(len(candidates), 12)
        self.assertTrue(all("y" not in row for row in candidates))
        first = candidates[0]["pair_id"]
        self.assertIsInstance(environment.query(first), float)
        with self.assertRaises(KeyError):
            environment.query("not-a-candidate")

    def test_bayesian_update_and_eig_are_deterministic(self) -> None:
        prior = [1.0 / len(MODEL_NAMES)] * len(MODEL_NAMES)
        left = BayesianInvestigator(prior, noise_std=0.25, tau2=4.0)
        right = BayesianInvestigator(prior, noise_std=0.25, tau2=4.0)
        x = [1.0, 0.1, -0.2]
        self.assertAlmostEqual(
            left.expected_information_gain(x),
            right.expected_information_gain(x),
        )
        left.update(x, -0.5)
        right.update(x, -0.5)
        np.testing.assert_allclose(left.probabilities, right.probabilities)
        self.assertAlmostEqual(float(left.probabilities.sum()), 1.0)
        self.assertTrue(credible_set(left.probabilities))

    def test_sheaf_laplacian_is_symmetric_psd_and_zero_is_local(self) -> None:
        patches = self.manifest["design"]["patches"]
        priors = {
            patch["id"]: np.roll(
                np.asarray([0.4, 0.2, 0.15, 0.15, 0.1]),
                index,
            ).tolist()
            for index, patch in enumerate(patches)
        }
        laplacian, edges = normalized_patch_laplacian(patches, priors)
        np.testing.assert_allclose(laplacian, laplacian.T, atol=1e-12)
        self.assertGreaterEqual(float(np.linalg.eigvalsh(laplacian).min()), -1e-10)
        self.assertEqual(len(edges), 4)
        smoothed, receipt = smooth_patch_priors(patches, priors, 0.0)
        for patch in patches:
            np.testing.assert_allclose(
                smoothed[patch["id"]], priors[patch["id"]], atol=1e-12
            )
        self.assertEqual(receipt["holonomy"], "trivial_by_construction_not_an_empirical_transport_claim")

    def test_lattice_is_monotone_and_bottom_explicit(self) -> None:
        before = {
            "explanation": list(MODEL_NAMES),
            "claim_mode": ["abstain", "set", "single"],
        }
        after, receipt = lattice_step(
            before,
            {
                "explanation": ["spectral_gap", "joint"],
                "claim_mode": ["set", "single"],
            },
            conflict_score=0.2,
        )
        self.assertEqual(after["explanation"], ["joint", "spectral_gap"])
        self.assertTrue(set(after["explanation"]).issubset(before["explanation"]))
        self.assertEqual(
            set(receipt["proposal"]),
            {
                "proposed_state",
                "soundness",
                "mode",
                "conflict_score",
                "soft_store",
                "metadata",
            },
        )
        bottom, bottom_receipt = lattice_step(
            before,
            {"explanation": [], "claim_mode": ["single"]},
            conflict_score=1.0,
        )
        self.assertEqual(bottom["explanation"], [])
        self.assertTrue(bottom_receipt["audit"]["after_bottom"])
        self.assertTrue(bottom_receipt["audit"]["would_block"])

    def test_auditor_does_not_change_query_sequence(self) -> None:
        prior = [1.0 / len(MODEL_NAMES)] * len(MODEL_NAMES)
        audited = evaluate_policy(
            self.task,
            "sheaf_eig",
            prior,
            noise_std=0.25,
            tau2=4.0,
            query_budget=6,
            audit_enabled=True,
        )
        unaudited = evaluate_policy(
            self.task,
            "sheaf_eig",
            prior,
            noise_std=0.25,
            tau2=4.0,
            query_budget=6,
            audit_enabled=False,
        )
        self.assertEqual(
            audited["queried_pair_ids"], unaudited["queried_pair_ids"]
        )
        np.testing.assert_allclose(
            audited["final_belief"]["model_probabilities"],
            unaudited["final_belief"]["model_probabilities"],
        )

    def test_audit_fixtures_all_pass(self) -> None:
        result = run_audit_fixtures()
        self.assertTrue(result["passed"])
        self.assertEqual(result["passed_count"], result["fixture_count"])
        self.assertEqual(result["fixture_count"], 4)

    def test_legacy_graph_lab_golden_hashes_are_unchanged(self) -> None:
        row = run_episode(
            split="discovery",
            seed=777,
            nodes=48,
            degree=6,
            topology="rewired_regular",
            state_dimension=4,
            coupling=0.25,
            rewires=96,
            steps=8,
            burn_in=2,
            perturbation_magnitude=0.5,
            deadline=time.monotonic() + 30,
            max_ram_mb=1024,
        )
        self.assertEqual(
            row["graph"]["edge_sha256"],
            "705d8d12ac710d11ddf61745122a163447231c1dc59ea36003c2a93a3ce9d93f",
        )
        self.assertEqual(
            row["provenance"]["final_state_sha256"],
            "c032a88048045270ae78fd38df10daf567be98538308ec0188f0b7175042410b",
        )
        self.assertEqual(
            row["provenance"]["final_perturbed_state_sha256"],
            "e9cbe65279afab1f217e2e48865394bacea29003f256792bf07b4803aac2deb3",
        )


if __name__ == "__main__":
    unittest.main()
