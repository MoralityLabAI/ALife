"""Deterministic, replay-verifiable ALife chronicle data products."""

from .events import EVENT_SCHEMA, ChronicleRecorder, validate_event
from .legends import LEGENDS_SCHEMA, compile_legends

__all__ = [
    "EVENT_SCHEMA",
    "LEGENDS_SCHEMA",
    "ChronicleRecorder",
    "compile_legends",
    "validate_event",
]
