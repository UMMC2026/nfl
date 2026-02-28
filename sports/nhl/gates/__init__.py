"""
NHL Gates Module
================
Hard gates that must pass before any analysis proceeds.

Gates (in order):
1. Goalie Confirmation (MANDATORY)
2. Sample Sufficiency
3. B2B Goalie Detection
4. Edge Threshold
"""

from sports.nhl.goalies.confirmation_gate import (
    GoalieConfirmationGate,
    enforce_goalie_gate,
    GateResult,
)

__all__ = [
    "GoalieConfirmationGate",
    "enforce_goalie_gate",
    "GateResult",
]
