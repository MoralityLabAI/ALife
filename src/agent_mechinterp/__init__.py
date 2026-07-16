"""Replay-grounded mechanistic-interpretability harness for ALife agents."""

from .analysis import analyze_decisions
from .core import (
    CanaryPolicy,
    InstrumentedPolicy,
    apply_authorized_edit,
    authorize_edit,
    build_editor_proposal,
    capture_decision,
    extract_observation,
    verify_decision,
    verify_edit_receipt,
    verify_harness_row,
)

__all__ = [
    "CanaryPolicy",
    "InstrumentedPolicy",
    "analyze_decisions",
    "apply_authorized_edit",
    "authorize_edit",
    "build_editor_proposal",
    "capture_decision",
    "extract_observation",
    "verify_decision",
    "verify_edit_receipt",
    "verify_harness_row",
]
