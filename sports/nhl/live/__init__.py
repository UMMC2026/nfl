"""
NHL Live Engine Module — v2.0
=============================

Real-time intermission betting system with hard gates.

GLOBAL ASSERTION:
  assert live_bets_per_game <= 1
"""

from .ingest_live import (
    GameState,
    IntermissionWindow,
    LiveGameSnapshot,
    IntermissionGate,
    LiveUpdateTracker,
    get_update_tracker,
    fetch_live_game,
    fetch_today_games,
    fetch_validated_live,
)

from .intermission_model import (
    AdjustmentType,
    LiveAdjustment,
    calculate_observed_pace,
    GameTotalModel,
    GoalieSavesModel,
    PlayerShotsLiveModel,
    run_all_adjustments,
)

from .validate_live import (
    LiveValidationResult,
    LiveBetTracker,
    get_live_bet_tracker,
    validate_min_edge,
    validate_line_movement,
    validate_clock_sync,
    validate_live_bet,
    validate_all_adjustments,
    assert_global_constraints,
    LIVE_MIN_EDGE,
)

__all__ = [
    # Ingestion
    "GameState",
    "IntermissionWindow",
    "LiveGameSnapshot",
    "IntermissionGate",
    "LiveUpdateTracker",
    "get_update_tracker",
    "fetch_live_game",
    "fetch_today_games",
    "fetch_validated_live",
    # Models
    "AdjustmentType",
    "LiveAdjustment",
    "calculate_observed_pace",
    "GameTotalModel",
    "GoalieSavesModel",
    "PlayerShotsLiveModel",
    "run_all_adjustments",
    # Validation
    "LiveValidationResult",
    "LiveBetTracker",
    "get_live_bet_tracker",
    "validate_min_edge",
    "validate_line_movement",
    "validate_clock_sync",
    "validate_live_bet",
    "validate_all_adjustments",
    "assert_global_constraints",
    "LIVE_MIN_EDGE",
]
