"""
NHL Module — Risk-First Hockey Analysis v2.0
=============================================

GLOBAL ASSERTIONS:
- unconfirmed_goalie_bets == 0
- slam_count == 0
- live_bets_per_game <= 1
- abs(calibration_error) <= 0.03
- max_drawdown <= 25%
"""

# Core v1.0
from sports.nhl.goalies.confirmation_gate import GoalieConfirmationGate
from sports.nhl.models.poisson_sim import PoissonSimulator

# v1.1 — Goalie Saves
from sports.nhl.goalies.saves_model import (
    SavesTier,
    GoalieProfile,
    OpponentProfile as SavesOpponentProfile,
    SavesProjection,
    project_goalie_saves,
)
from sports.nhl.goalies.saves_simulate import (
    SavesSimulator,
    SavesSimulationResult,
    simulate_goalie_saves,
)

# v2.0 — Context Modules
from sports.nhl.context.ref_bias import RefereeBiasCalculator, calculate_ref_bias_for_game
from sports.nhl.context.travel_fatigue import TravelFatigueCalculator, calculate_travel_adjustment

# v2.0 — Player Props
from sports.nhl.players.shots_model import PlayerShotsModel, project_player_sog
from sports.nhl.players.shots_simulate import SOGSimulator, simulate_player_sog

# v2.0 — Live Engine
from sports.nhl.live.ingest_live import fetch_live_game, fetch_validated_live
from sports.nhl.live.intermission_model import GameTotalModel, run_all_adjustments
from sports.nhl.live.validate_live import validate_live_bet, assert_global_constraints

__version__ = "2.0.0"
__status__ = "DEVELOPMENT"

__all__ = [
    # Core v1.0
    "GoalieConfirmationGate",
    "PoissonSimulator",
    # v1.1 Saves
    "SavesTier",
    "GoalieProfile",
    "SavesOpponentProfile",
    "SavesProjection",
    "project_goalie_saves",
    "SavesSimulator",
    "SavesSimulationResult",
    "simulate_goalie_saves",
    # v2.0 Context
    "RefereeBiasCalculator",
    "calculate_ref_bias_for_game",
    "TravelFatigueCalculator",
    "calculate_travel_adjustment",
    # v2.0 Player Props
    "PlayerShotsModel",
    "project_player_sog",
    "SOGSimulator",
    "simulate_player_sog",
    # v2.0 Live
    "fetch_live_game",
    "fetch_validated_live",
    "GameTotalModel",
    "run_all_adjustments",
    "validate_live_bet",
    "assert_global_constraints",
]
