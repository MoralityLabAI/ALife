"""Fast regression checks for the recovered StegoHive environment."""

from __future__ import annotations

import gzip
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
SOURCE = WORKSPACE / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from stegohive_v1 import (  # noqa: E402
    default_condition,
    default_config,
    run_world,
    verify_episode,
)
from stegohive_v2.analysis import derive_episode_analysis  # noqa: E402
from stegohive_v2.archive import load_retained_record  # noqa: E402
from stegohive_v2.environment import run_world as run_v2_world  # noqa: E402
from stegohive_v2.types import (  # noqa: E402
    condition_registry,
    default_config as default_v2_config,
)
from stegohive_v2.verifiers import verify_episode as verify_v2_episode  # noqa: E402
from stegohive_v2.versions import run_spec, run_versioned_world  # noqa: E402


class StegoHiveRecoveryTests(unittest.TestCase):
    def test_v1_world_executes_and_verifies(self) -> None:
        episode = run_world(default_config(), default_condition(), 0)
        report = verify_episode(episode)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["failed_required_verifiers"], [])

    def test_v2_pure_apis_match_retained_record(self) -> None:
        raw = WORKSPACE / "results" / "stegohive_gym_v2_discovery" / "raw_episodes.jsonl.gz"
        if not raw.is_file():
            self.skipTest("external retained StegoHive results are not mounted")
        with gzip.open(raw, "rt", encoding="utf-8") as handle:
            record = json.loads(next(handle))
        self.assertEqual(derive_episode_analysis(record["episode"]), record["analysis"])
        self.assertEqual(verify_v2_episode(record["episode"]), record["verifier"])

    def test_fresh_v2_world_is_deterministic_and_verified(self) -> None:
        config = default_v2_config()
        config.update({"cohorts": 3, "generations_per_cohort": 2, "population_size": 8})
        config["archive"].update({"capacity": 16, "deposit_count": 2})
        first = run_v2_world(config, "F10", 990001)
        second = run_v2_world(config, condition_registry()["F10"], 990001)
        different = run_v2_world(config, "F10", 990002)
        self.assertEqual(first, second)
        self.assertNotEqual(first["episode_sha256"], different["episode_sha256"])
        self.assertEqual(len(first["generations"]), 6)
        self.assertEqual(len(first["checkpoints"]), 3)
        self.assertTrue(verify_v2_episode(first)["accepted"])
        analysis = derive_episode_analysis(first)
        self.assertEqual(analysis["episode_id"], first["episode_id"])
        self.assertEqual(analysis["evidence"]["checkpoint_count"], 3)

    def test_fresh_v2_verifier_fails_closed_on_tampering(self) -> None:
        config = default_v2_config()
        config.update({"cohorts": 3, "generations_per_cohort": 2, "population_size": 8})
        config["archive"].update({"capacity": 16, "deposit_count": 2})
        episode = run_v2_world(config, "F00", 990003)
        tampered = deepcopy(episode)
        tampered["generations"][0]["action_count"] += 1
        report = verify_v2_episode(tampered)
        self.assertFalse(report["accepted"])
        self.assertIn("generation_action_accounting", report["failed_checks"])
        self.assertIn("deterministic_hashes", report["failed_checks"])

    def test_retained_record_lookup_is_exact_and_read_only(self) -> None:
        raw = WORKSPACE / "results" / "stegohive_gym_v2_discovery" / "raw_episodes.jsonl.gz"
        if not raw.is_file():
            self.skipTest("external retained StegoHive results are not mounted")
        record = load_retained_record("V2", 30001, condition_id="F00")
        self.assertEqual(record["identity"]["seed"], 30001)
        self.assertEqual(record["identity"]["condition_id"], "F00")
        self.assertEqual(derive_episode_analysis(record["episode"]), record["analysis"])

    def test_v6_v9_facades_restore_registered_cells(self) -> None:
        self.assertEqual(run_spec("V6", "D")["config"]["population_size"], 8)
        self.assertEqual(run_spec("V7", "G12_H")["config"]["generations_per_cohort"], 12)
        self.assertEqual(
            run_spec("V8", "E_B")["treatments"],
            {
                "reproduction_credit_mode": "encounter_local",
                "archive_credit_mode": "balanced_crossplay",
            },
        )
        self.assertEqual(
            run_spec("V9", "B_E")["treatments"],
            {
                "archive_credit_mode": "encounter_local",
                "sender_parent_credit_mode": "balanced_crossplay",
                "receiver_parent_credit_mode": "encounter_local",
            },
        )
        record = run_versioned_world("V9", 990004, "B_E")
        self.assertEqual(record["identity"]["version"], "V9")
        self.assertTrue(record["verifier"]["accepted"])
        self.assertEqual(record["treatments"]["sender_parent_credit_mode"], "balanced_crossplay")


if __name__ == "__main__":
    unittest.main()
