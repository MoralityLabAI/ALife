from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph_state_lab import (  # noqa: E402
    build_graph,
    channel_matrix,
    condition_specs,
    graph_receipt,
    run_episode,
)


class GraphStateLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "experiments" / "graph_state_v1" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def test_graph_families_preserve_degree_and_connectivity(self) -> None:
        for topology in (
            "ring_regular",
            "rewired_regular",
            "random_regular",
            "circulant_skip_regular",
        ):
            graph = build_graph(topology, nodes=48, degree=6, seed=123, rewires=96)
            receipt = graph_receipt(graph, degree=6)
            self.assertTrue(receipt["connected"])
            self.assertEqual(receipt["degree_min"], 6)
            self.assertEqual(receipt["degree_max"], 6)

    def test_channel_matrix_is_deterministic_and_shaped(self) -> None:
        for dimension in (2, 8, 16):
            first = channel_matrix(dimension)
            second = channel_matrix(dimension)
            self.assertEqual(first.shape, (dimension, dimension))
            self.assertTrue(np.array_equal(first, second))

    def test_manifest_episode_plan_fits_budget(self) -> None:
        planned = sum(
            len(self.manifest["seed_plan"][split])
            * len(condition_specs(self.manifest, split, False))
            for split in ("discovery", "confirmatory", "holdout")
        )
        self.assertEqual(planned, 162)
        self.assertLessEqual(planned, self.manifest["budget"]["max_episodes"])

    def test_episode_is_deterministic_and_perturbation_executes(self) -> None:
        kwargs = {
            "split": "discovery",
            "seed": 777,
            "nodes": 48,
            "degree": 6,
            "topology": "rewired_regular",
            "state_dimension": 4,
            "coupling": 0.25,
            "rewires": 96,
            "steps": 8,
            "burn_in": 2,
            "perturbation_magnitude": 0.5,
            "deadline": time.monotonic() + 30,
            "max_ram_mb": 1024,
        }
        first = run_episode(**kwargs)
        second = run_episode(**kwargs)
        self.assertEqual(first["graph"]["edge_sha256"], second["graph"]["edge_sha256"])
        self.assertEqual(
            first["provenance"]["final_state_sha256"],
            second["provenance"]["final_state_sha256"],
        )
        self.assertTrue(first["intervention"]["executed"])
        self.assertEqual(first["exposure"]["perturbation_executions"], 1)


if __name__ == "__main__":
    unittest.main()
