"""Reconstructed shared constants used by the surviving StegoHive v1 snapshot.

The original file did not survive recovery.  The machine ordering is copied from
the frozen v1 configuration's ``world.machine_ids`` array.  ``deep_copy_json``
matches the canonical JSON implementation embedded in ``stegohive_v1.types``.
"""

from __future__ import annotations

import json
from typing import Any


MACHINE_IDS = (
    "ONE-ROOT",
    "CHOIR-6",
    "ORCHARD-4",
    "MOTH-13",
    "FERRY-8",
    "BASTION-2",
)


def deep_copy_json(value: Any) -> Any:
    """Return a detached JSON-compatible copy with canonical encoding rules."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return json.loads(encoded.decode("utf-8"))


__all__ = ["MACHINE_IDS", "deep_copy_json"]
