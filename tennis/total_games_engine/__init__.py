"""
Package init for Total Games Engine.
"""

from .total_games_engine import (
    MatchInput,
    MatchOutput,
    process_match,
    process_slate,
    infer_format,
    surface_baseline,
    estimate_expected_sets,
    classify_confidence,
    SURFACE_BASELINES,
    STRONG_EDGE,
    LEAN_EDGE,
    BO5_THRESHOLD,
)

from .governance import (
    governance_gate,
    filter_approved,
    filter_blocked,
    split_by_governance,
)

__all__ = [
    "MatchInput",
    "MatchOutput",
    "process_match",
    "process_slate",
    "infer_format",
    "surface_baseline",
    "estimate_expected_sets",
    "classify_confidence",
    "governance_gate",
    "filter_approved",
    "filter_blocked",
    "split_by_governance",
    "SURFACE_BASELINES",
    "STRONG_EDGE",
    "LEAN_EDGE",
    "BO5_THRESHOLD",
]
