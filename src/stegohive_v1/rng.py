"""Domain-separated deterministic randomness with an auditable draw ledger."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Sequence

from .types import RNG_SCHEMA, canonical_bytes, canonical_sha256, deep_copy_json


_KEY_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


class DuplicateRNGKeyError(RuntimeError):
    """Raised when one logical draw key is consumed more than once."""


class RNGKeyError(ValueError):
    pass


@dataclass(frozen=True)
class RNGKey:
    namespace: str
    branch: str
    cohort: int
    generation: int
    event_kind: str
    entity_ids: tuple[str, ...]
    draw_name: str

    def __post_init__(self) -> None:
        for label, value in (
            ("namespace", self.namespace),
            ("branch", self.branch),
            ("event_kind", self.event_kind),
            ("draw_name", self.draw_name),
        ):
            if not isinstance(value, str) or not _KEY_PART_RE.fullmatch(value):
                raise RNGKeyError(f"{label} is not a safe RNG key component")
        if isinstance(self.cohort, bool) or not isinstance(self.cohort, int):
            raise RNGKeyError("cohort must be an integer")
        if isinstance(self.generation, bool) or not isinstance(self.generation, int):
            raise RNGKeyError("generation must be an integer")
        if not isinstance(self.entity_ids, tuple) or any(
            not isinstance(value, str) or not _KEY_PART_RE.fullmatch(value)
            for value in self.entity_ids
        ):
            raise RNGKeyError("entity_ids must be a tuple of safe role-tagged ids")

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "branch": self.branch,
            "cohort": self.cohort,
            "generation": self.generation,
            "event_kind": self.event_kind,
            "entity_ids": list(self.entity_ids),
            "draw_name": self.draw_name,
        }


def _expanded_digest(base: bytes, lane: int) -> bytes:
    return hashlib.sha256(base + lane.to_bytes(8, "big", signed=False)).digest()


class DeterministicRNGLedger:
    """Counter/hash RNG whose logical keys may each be consumed exactly once."""

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an integer")
        self.seed = seed
        self._used: set[bytes] = set()
        self._receipts: list[dict[str, Any]] = []

    def _reserve(
        self,
        key: RNGKey,
        sampler: str,
        parameters: dict[str, Any],
    ) -> tuple[bytes, str, bytes]:
        key_bytes = canonical_bytes(key.to_dict())
        if key_bytes in self._used:
            raise DuplicateRNGKeyError(
                f"logical RNG key already consumed: {canonical_sha256(key.to_dict())}"
            )
        self._used.add(key_bytes)
        seed_material = canonical_bytes(
            {"schema": RNG_SCHEMA, "seed": self.seed, "key": key.to_dict()}
        )
        digest = hashlib.sha256(seed_material).digest()
        receipt_id = hashlib.sha256(b"receipt:" + seed_material).hexdigest()
        self._receipts.append(
            {
                "receipt_id": receipt_id,
                "key": key.to_dict(),
                "sampler": sampler,
                "parameters": deep_copy_json(parameters),
                "draw_sha256": "",
                "value": None,
            }
        )
        return digest, receipt_id, key_bytes

    def receipt_id_for(self, key: RNGKey) -> str:
        """Return the receipt id for an already consumed logical key."""

        key_bytes = canonical_bytes(key.to_dict())
        if key_bytes not in self._used:
            raise RNGKeyError("logical RNG key has not been consumed")
        seed_material = canonical_bytes(
            {"schema": RNG_SCHEMA, "seed": self.seed, "key": key.to_dict()}
        )
        return hashlib.sha256(b"receipt:" + seed_material).hexdigest()

    def _finish(self, receipt_id: str, value: Any) -> Any:
        for receipt in reversed(self._receipts):
            if receipt["receipt_id"] == receipt_id:
                receipt["value"] = deep_copy_json(value)
                receipt["draw_sha256"] = canonical_sha256(
                    {
                        "key": receipt["key"],
                        "sampler": receipt["sampler"],
                        "parameters": receipt["parameters"],
                        "value": receipt["value"],
                    }
                )
                return value
        raise AssertionError("reserved RNG receipt disappeared")

    def unit(self, key: RNGKey) -> float:
        digest, receipt_id, _ = self._reserve(key, "unit", {})
        value = int.from_bytes(digest[:8], "big") / float(2**64)
        return self._finish(receipt_id, value)

    def integer(self, key: RNGKey, stop: int, *, start: int = 0) -> int:
        if isinstance(start, bool) or isinstance(stop, bool):
            raise TypeError("integer bounds must be integers")
        if not isinstance(start, int) or not isinstance(stop, int) or stop <= start:
            raise ValueError("integer requires stop > start")
        digest, receipt_id, _ = self._reserve(
            key, "integer", {"start": start, "stop": stop}
        )
        value = start + int.from_bytes(digest[:16], "big") % (stop - start)
        return self._finish(receipt_id, value)

    def bernoulli(self, key: RNGKey, probability: float) -> bool:
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(float(probability))
            or not 0.0 <= float(probability) <= 1.0
        ):
            raise ValueError("probability must be finite and in [0, 1]")
        digest, receipt_id, _ = self._reserve(
            key, "bernoulli", {"probability": float(probability)}
        )
        unit = int.from_bytes(digest[:8], "big") / float(2**64)
        return self._finish(receipt_id, unit < float(probability))

    def choice(self, key: RNGKey, values: Sequence[Any]) -> Any:
        if not values:
            raise ValueError("choice requires a non-empty sequence")
        digest, receipt_id, _ = self._reserve(key, "choice", {"count": len(values)})
        index = int.from_bytes(digest[:16], "big") % len(values)
        return self._finish(receipt_id, deep_copy_json(values[index]))

    def permutation(self, key: RNGKey, size: int) -> list[int]:
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 1024:
            raise ValueError("permutation size must be an integer in [1, 1024]")
        digest, receipt_id, _ = self._reserve(key, "permutation", {"size": size})
        ranked = sorted(
            range(size),
            key=lambda index: (_expanded_digest(digest, index), index),
        )
        return self._finish(receipt_id, ranked)

    def weighted_index(self, key: RNGKey, weights: Sequence[float]) -> int:
        if not weights:
            raise ValueError("weighted_index requires weights")
        normalized = [float(value) for value in weights]
        if any(not math.isfinite(value) or value < 0.0 for value in normalized):
            raise ValueError("weights must be finite and non-negative")
        total = sum(normalized)
        if total <= 0.0:
            normalized = [1.0 for _ in normalized]
            total = float(len(normalized))
        digest, receipt_id, _ = self._reserve(
            key, "weighted_index", {"weights": normalized}
        )
        target = int.from_bytes(digest[:8], "big") / float(2**64) * total
        cumulative = 0.0
        index = len(normalized) - 1
        for candidate, weight in enumerate(normalized):
            cumulative += weight
            if target < cumulative:
                index = candidate
                break
        return self._finish(receipt_id, index)

    def receipts(self) -> list[dict[str, Any]]:
        return deep_copy_json(sorted(self._receipts, key=lambda row: row["receipt_id"]))

    def receipts_sha256(self) -> str:
        return canonical_sha256(self.receipts())

    def snapshot(self) -> dict[str, Any]:
        receipts = self.receipts()
        return {
            "schema": RNG_SCHEMA,
            "seed": self.seed,
            "receipts": receipts,
            "receipts_sha256": canonical_sha256(receipts),
        }

    def __len__(self) -> int:
        return len(self._receipts)


__all__ = [
    "DeterministicRNGLedger",
    "DuplicateRNGKeyError",
    "RNGKey",
    "RNGKeyError",
]
