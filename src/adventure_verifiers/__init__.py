"""Replay-grounded verifier library for ALife adventure traces."""

from .adapters import adapt_chronicle_events, adapt_pixie_episode, build_pixie_adventure
from .core import (
    ENVIRONMENT_SCHEMA,
    EVENT_SCHEMA,
    RESULT_SCHEMA,
    SUITE_SCHEMA,
    TASK_SCHEMA,
    TRACE_SCHEMA,
    VerifierSpec,
    canonical_sha256,
    make_result,
)
from .verifiers import VERIFIER_SPECS, verify_adventure

__all__ = [
    "ENVIRONMENT_SCHEMA",
    "EVENT_SCHEMA",
    "RESULT_SCHEMA",
    "SUITE_SCHEMA",
    "TASK_SCHEMA",
    "TRACE_SCHEMA",
    "VerifierSpec",
    "VERIFIER_SPECS",
    "adapt_chronicle_events",
    "adapt_pixie_episode",
    "build_pixie_adventure",
    "canonical_sha256",
    "make_result",
    "verify_adventure",
]
