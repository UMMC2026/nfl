"""
Core modules for slate quality, defensive mode, and reporting controls.
SOP v2.2: Truth + Context Enforced
"""

from .slate_controls import (
    compute_slate_controls,
    SlateControlsResult,
    compute_slate_quality,
    compute_api_health,
    evaluate_defensive_mode,
    build_rejection_summary,
    scale_confidence,
    enforce_tier_cap,
    reset_api_health,
    record_api_success,
    record_api_failure,
)

__all__ = [
    "compute_slate_controls",
    "SlateControlsResult",
    "compute_slate_quality",
    "compute_api_health",
    "evaluate_defensive_mode",
    "build_rejection_summary",
    "scale_confidence",
    "enforce_tier_cap",
    "reset_api_health",
    "record_api_success",
    "record_api_failure",
]
