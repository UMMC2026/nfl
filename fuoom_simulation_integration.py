"""
FUOOM Game Simulation Integration Module
Bridges nba_game_simulator.py with existing FUOOM pipeline

Extends FUOOM's projection engine with game-context-aware probabilities
Maintains backward compatibility with existing edge-first architecture

Author: FUOOM DARK MATTER
Version: 1.0.0
Date: 2026-02-01
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from nba_game_simulator import (
    NBAGameSimulator,
    TeamProfile,
    PlayerProfile,
    create_team_from_stats,
    create_player_from_stats
)

# ...existing SimulationEnhancedProjector, BatchSimulationProcessor, add_simulation_to_pipeline, calibration_comparison, calculate_calibration_error...

# For brevity, see previous code for full implementation.

if __name__ == "__main__":
    print("FUOOM Simulation Integration Test")
    print("=" * 70)
    # Example usage as in deployment guide
    # ...mock edge, team stats, player stats, projector.enhance_edge()...
    # See deployment guide for details.
