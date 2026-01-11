"""
Pipeline execution mode control
Prevents accidental broadcast of analysis runs
"""
from enum import Enum
from typing import NamedTuple

class PipelineMode(Enum):
    """Execution modes with different gate behavior"""
    ANALYSIS = "analysis"   # Generate, tag, log, inspect - gates log warnings only
    BROADCAST = "broadcast" # Enforce all gates - abort on any failure
    
class ModeConfig(NamedTuple):
    """Mode-specific behavior configuration"""
    mode: PipelineMode
    enforce_gates: bool
    allow_telegram: bool
    allow_learning: bool
    require_balance: bool
    
# Mode behavior matrix (IMMUTABLE)
MODE_CONFIGS = {
    PipelineMode.ANALYSIS: ModeConfig(
        mode=PipelineMode.ANALYSIS,
        enforce_gates=False,      # Log warnings, don't abort
        allow_telegram=False,     # Never broadcast in analysis mode
        allow_learning=False,     # Don't update calibration on analysis runs
        require_balance=False,    # Allow biased distributions for inspection
    ),
    PipelineMode.BROADCAST: ModeConfig(
        mode=PipelineMode.BROADCAST,
        enforce_gates=True,       # Hard abort on any gate failure
        allow_telegram=True,      # Can broadcast if all gates pass
        allow_learning=True,      # Update calibration on verified results
        require_balance=True,     # Require directional balance
    ),
}

def get_mode_config(mode: PipelineMode) -> ModeConfig:
    """Get configuration for specified mode"""
    return MODE_CONFIGS[mode]

def validate_mode_transition(current: PipelineMode, target: PipelineMode) -> tuple[bool, str]:
    """
    Validate mode transition is safe
    Returns (is_valid, reason)
    """
    # ANALYSIS -> BROADCAST requires explicit confirmation
    if current == PipelineMode.ANALYSIS and target == PipelineMode.BROADCAST:
        return False, "ANALYSIS→BROADCAST requires explicit --force-broadcast flag"
    
    # BROADCAST -> ANALYSIS always safe
    return True, "OK"
