"""Evidence-driven reconstruction of the missing StegoHive v2 environment.

The historical v2 simulator source did not survive.  This package restores the
pure APIs exactly where evidence permits, plus a clearly labeled fresh runtime
that implements the retained ecological contract for arbitrary new seeds.
"""

from .analysis import derive_episode_analysis
from .archive import load_retained_record
from .environment import deterministic_projection, run_world
from .rng import DeterministicRNGLedger
from .types import (
    condition_registry,
    default_condition,
    default_config,
    validate_condition,
    validate_config,
)
from .verifiers import canonical_bytes, canonical_sha256, verify_episode
from .versions import cell_registry, run_spec, run_versioned_world

__all__ = [
    "DeterministicRNGLedger",
    "canonical_bytes",
    "canonical_sha256",
    "cell_registry",
    "condition_registry",
    "default_condition",
    "default_config",
    "deterministic_projection",
    "derive_episode_analysis",
    "load_retained_record",
    "run_spec",
    "run_versioned_world",
    "run_world",
    "validate_condition",
    "validate_config",
    "verify_episode",
]
