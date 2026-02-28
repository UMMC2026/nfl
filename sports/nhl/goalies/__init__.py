"""NHL Goalies Module — Confirmation + Saves v1.1"""
from sports.nhl.goalies.confirmation_gate import (
    GoalieConfirmationGate,
    GoalieStatus,
    GateCheckResult,
    confirm_both_goalies,
    apply_goalie_adjustments,
    enforce_goalie_gate,
)
from sports.nhl.goalies.saves_model import (
    SavesTier,
    GoalieProfile,
    OpponentProfile,
    SavesProjection,
    project_goalie_saves,
    check_saves_gates,
)
from sports.nhl.goalies.saves_simulate import (
    SavesSimulationResult,
    SavesSimulator,
    simulate_goalie_saves,
    simulate_adjusted_saves,
)

__all__ = [
    # Confirmation gate
    "GoalieConfirmationGate",
    "GoalieStatus",
    "GateCheckResult",
    "confirm_both_goalies",
    "apply_goalie_adjustments",
    "enforce_goalie_gate",
    # Saves model
    "SavesTier",
    "GoalieProfile",
    "OpponentProfile",
    "SavesProjection",
    "project_goalie_saves",
    "check_saves_gates",
    # Saves simulation
    "SavesSimulationResult",
    "SavesSimulator",
    "simulate_goalie_saves",
    "simulate_adjusted_saves",
]
