"""
NBA Features Package
====================
Player-vs-opponent matchup memory and statistical adjustments.
"""

from .player_vs_opponent import (
    PlayerVsOpponentStats,
    MatchupRecord,
    MatchupIndex,
    compute_matchup_adjustment,
    build_matchup_index,
    NBA_LEAGUE_PRIORS,
)

from .matchup_gates import (
    MatchupGate,
    MatchupGateResult,
    GateStatus,
    validate_matchup_sample,
    compute_shrinkage_weight,
    get_gate_for_stat,
)

__all__ = [
    # Core stats
    "PlayerVsOpponentStats",
    "MatchupRecord",
    "MatchupIndex",
    "compute_matchup_adjustment",
    "build_matchup_index",
    "NBA_LEAGUE_PRIORS",
    # Gates
    "MatchupGate",
    "MatchupGateResult",
    "GateStatus",
    "validate_matchup_sample",
    "compute_shrinkage_weight",
    "get_gate_for_stat",
]
