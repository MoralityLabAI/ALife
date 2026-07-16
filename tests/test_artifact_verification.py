import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from artifact_verification import (  # noqa: E402
    audit_runtime_environment,
    resolve_recorded_file,
    sha256_file,
)


class ArtifactVerificationTests(unittest.TestCase):
    def test_receipt_self_hash_does_not_hide_runtime_difference(self) -> None:
        recorded = {
            "python": "3.11.4-recorded",
            "platform": "recorded-platform",
            "cpu_logical": 12,
            "ram_total_mb": 24000.0,
        }
        receipt = {
            **recorded,
            "environment_sha256": hashlib.sha256(
                json.dumps(recorded, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        }
        audit = audit_runtime_environment(receipt, [])
        self.assertTrue(audit["receipt_environment_hash_valid"])
        self.assertFalse(audit["runtime_exact_match"])
        self.assertIn("python", audit["differences"])

    def test_unique_suffix_ignores_unrelated_same_basenames(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wanted = root / "results" / "graph_state_v1" / "summary.json"
            wanted.parent.mkdir(parents=True)
            wanted.write_text("wanted", encoding="utf-8")
            for name in ("geometry", "curriculum", "transfer", "graph_v2"):
                other = root / "results" / name / "summary.json"
                other.parent.mkdir(parents=True)
                other.write_text(name, encoding="utf-8")
            result = resolve_recorded_file(
                r"C:\old\results\graph_state_v1\summary.json",
                sha256_file(wanted),
                search_roots=[root],
                suffix_parts=3,
            )
            self.assertEqual(result["status"], "resolved")
            self.assertEqual(Path(result["resolved_path"]), wanted.resolve())

    def test_ambiguous_suffix_fails_without_hash_based_guess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "results" / "graph_state_v1" / "summary.json"
            second = root / "copy" / "results" / "graph_state_v1" / "summary.json"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text("wanted", encoding="utf-8")
            second.write_text("different", encoding="utf-8")
            result = resolve_recorded_file(
                r"C:\old\results\graph_state_v1\summary.json",
                sha256_file(first),
                search_roots=[root],
                suffix_parts=3,
            )
            self.assertEqual(result["status"], "ambiguous")
            self.assertEqual(len(result["candidates"]), 2)

    def test_basename_only_resolution_is_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            resolve_recorded_file(
                "summary.json",
                "0" * 64,
                search_roots=[ROOT],
                suffix_parts=1,
            )

    def test_portable_mode_ignores_existing_recorded_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundled = root / "src" / "experiment.py"
            bundled.parent.mkdir(parents=True)
            bundled.write_text("bundle", encoding="utf-8")
            result = resolve_recorded_file(
                Path(__file__),
                sha256_file(bundled),
                search_roots=[root],
                suffix_parts=2,
                allow_recorded_path=False,
            )
            self.assertEqual(result["status"], "missing")
            result = resolve_recorded_file(
                r"C:\old\src\experiment.py",
                sha256_file(bundled),
                search_roots=[root],
                suffix_parts=2,
                allow_recorded_path=False,
            )
            self.assertEqual(result["status"], "resolved")
            self.assertEqual(result["method"], "unique_suffix")


if __name__ == "__main__":
    unittest.main()
