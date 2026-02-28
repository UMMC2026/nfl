"""
NHL Player Props Module — v2.0
==============================

Player-level prop modeling for NHL.
Currently supports SOG (Shots on Goal).
"""

from .shots_model import (
    PlayerProfile,
    OpponentDefense,
    SOGProjection,
    PlayerShotsModel,
    project_player_sog,
)

from .shots_simulate import (
    SOGSimulationResult,
    SOGSimulator,
    simulate_player_sog,
    simulate_with_toi_variance,
)

__all__ = [
    # Model
    "PlayerProfile",
    "OpponentDefense", 
    "SOGProjection",
    "PlayerShotsModel",
    "project_player_sog",
    # Simulator
    "SOGSimulationResult",
    "SOGSimulator",
    "simulate_player_sog",
    "simulate_with_toi_variance",
]
