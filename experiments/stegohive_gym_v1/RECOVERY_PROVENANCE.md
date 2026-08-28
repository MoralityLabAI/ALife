# StegoHive Gym V1 recovery provenance

The Python package in `src/stegohive_v1`, the detached verifier, and the five
JSON inputs in this directory were restored byte-for-byte on 2026-08-27 from:

`results/stegohive_gym_v1_pre_freeze_snapshot_20260811T0804Z`

That snapshot identifies itself as the accepted discovery implementation before
confirmatory routing and condition-semantics additions.  It is not evidence that
the later confirmatory source survived.

The imported shared package `src/stegohive` did not survive.  Its two required
members were reconstructed from frozen evidence: the ordered `MACHINE_IDS` value
comes from `config.json` at `world.machine_ids`, and `deep_copy_json` duplicates
the canonical implementation present in `src/stegohive_v1/types.py`.
