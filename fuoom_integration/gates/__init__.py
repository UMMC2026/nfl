"""
FUOOM DARK MATTER - Pre-Model Gates Package
=============================================

This package contains the judgment layer that runs BEFORE probability modeling.

Gates (in order):
  1. MinutesRoleGate - Can this player hit this stat?
  2. DirectionGate - Does a real directional path exist?
  3. VarianceKillSwitch - Is variance existential or cosmetic?

Usage:
    from gates import PreModelPipeline
    
    pipeline = PreModelPipeline()
    result = pipeline.run(
        player_id="lebron_james",
        stat_type="PTS",
        line=25.5,
        direction="OVER",
        expected_minutes=35.0,
        mu=28.3,
        sigma=6.2,
        sample_size=10,
    )
    
    if result.allowed:
        # Proceed to probability modeling
        pass
    else:
        # Skip this prop
        print(f"Blocked by {result.blocked_by}: {result.reason}")

Version: 1.0.0
Date: February 10, 2026
"""

from gates.minutes_role_gate import MinutesRoleGate, MinutesRoleResult
from gates.direction_gate import DirectionGate, DirectionGateResult
from gates.variance_kill_switch import VarianceKillSwitch, VarianceResult
from gates.pre_model_pipeline import PreModelPipeline, PreModelResult, run_batch

__all__ = [
    # Gates
    "MinutesRoleGate",
    "DirectionGate", 
    "VarianceKillSwitch",
    
    # Pipeline
    "PreModelPipeline",
    "run_batch",
    
    # Results
    "MinutesRoleResult",
    "DirectionGateResult",
    "VarianceResult",
    "PreModelResult",
]

__version__ = "1.0.0"
