"""Evidence-driven reconstruction of the missing StegoHive v2 pure APIs.

The historical v2 simulator source did not survive.  This package restores the
pure analysis, hashing, RNG, and archived-episode verification interfaces used
by the surviving V2--V9 detached verifiers.
"""

from .analysis import derive_episode_analysis
from .rng import DeterministicRNGLedger
from .verifiers import canonical_bytes, canonical_sha256, verify_episode

__all__ = [
    "DeterministicRNGLedger",
    "canonical_bytes",
    "canonical_sha256",
    "derive_episode_analysis",
    "verify_episode",
]
