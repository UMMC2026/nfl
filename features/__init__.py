"""
Features Package
================
Statistical features for enhanced analysis across sports.
"""

from features.nba import (
    PlayerVsOpponentStats,
    MatchupGate,
    compute_matchup_adjustment,
    validate_matchup_sample,
)

__all__ = [
    "PlayerVsOpponentStats",
    "MatchupGate",
    "compute_matchup_adjustment",
    "validate_matchup_sample",
]
