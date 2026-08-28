"""Fast regression checks for the recovered StegoHive environment."""

from __future__ import annotations

import gzip
import json
import sys
import unittest
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
from stegohive_v2.verifiers import verify_episode as verify_v2_episode  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
