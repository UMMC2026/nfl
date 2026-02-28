"""
CBB Feature Engineering Module

CBB-specific features — DO NOT copy NBA features blindly.

Key differences from NBA:
- 350+ teams with massive rotation volatility
- Inconsistent pace & minutes
- Higher variance in everything
"""
from .player_features import build_player_features
from .team_features import build_team_features
from .game_context import build_game_context

__all__ = ["build_player_features", "build_team_features", "build_game_context"]
