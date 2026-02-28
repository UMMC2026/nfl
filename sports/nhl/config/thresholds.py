"""
NHL-Specific Thresholds
=======================
Imports from canonical config/thresholds.py and applies NHL overrides.

GOVERNANCE: These values are stricter than NBA due to goalie variance.
"""

import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.thresholds import TIERS, get_tier_threshold

# =============================================================================
# NHL TIER OVERRIDES (Stricter than defaults)
# =============================================================================

NHL_TIERS = {
    "SLAM": None,       # DISABLED — variance too high
    "STRONG": 0.64,     # 64% minimum (NBA: 65%)
    "LEAN": 0.58,       # 58% minimum (NBA: 55%)
    "NO_PLAY": 0.0,
}

# =============================================================================
# CONFIDENCE CAPS BY CONDITION
# =============================================================================

NHL_CONFIDENCE_CAPS = {
    "default": 0.69,                # Max confidence for any NHL pick
    "small_sample_goalie": 0.58,    # <5 starts in 30 days
    "b2b_goalie": 0.64,             # Back-to-back start
    "backup_goalie": 0.60,          # Non-starter
    "travel_fatigue": 0.66,         # >2 timezone shift
}

# =============================================================================
# PROBABILITY ADJUSTMENTS
# =============================================================================

NHL_ADJUSTMENTS = {
    "b2b_penalty": -0.04,           # -4% for back-to-back goalie
    "travel_penalty": -0.02,        # -2% for travel fatigue
    "home_ice_boost": 0.035,        # ~3.5% home ice advantage
}

# =============================================================================
# EDGE THRESHOLDS
# =============================================================================

NHL_EDGE_MINIMUM = 0.02  # 2% minimum edge to play

# =============================================================================
# SIMULATION PARAMETERS
# =============================================================================

NHL_SIMULATION_COUNT = 20000  # Poisson simulations per game

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_nhl_tier(probability: float) -> str:
    """
    Assign tier based on NHL-specific thresholds.
    
    Args:
        probability: Model probability (0.0 - 1.0)
        
    Returns:
        Tier string: "STRONG", "LEAN", or "NO_PLAY"
    """
    if probability >= NHL_TIERS["STRONG"]:
        return "STRONG"
    elif probability >= NHL_TIERS["LEAN"]:
        return "LEAN"
    else:
        return "NO_PLAY"


def apply_nhl_cap(probability: float, conditions: list[str]) -> float:
    """
    Apply confidence caps based on conditions.
    
    Args:
        probability: Raw model probability
        conditions: List of condition keys from NHL_CONFIDENCE_CAPS
        
    Returns:
        Capped probability
    """
    cap = NHL_CONFIDENCE_CAPS["default"]
    
    for condition in conditions:
        if condition in NHL_CONFIDENCE_CAPS:
            cap = min(cap, NHL_CONFIDENCE_CAPS[condition])
    
    return min(probability, cap)


def apply_nhl_adjustments(probability: float, is_b2b: bool = False, 
                          is_travel_fatigued: bool = False,
                          is_home: bool = False) -> float:
    """
    Apply probability adjustments for NHL-specific factors.
    
    Args:
        probability: Base probability
        is_b2b: Goalie on back-to-back
        is_travel_fatigued: Team traveled >2 timezones
        is_home: Is home team
        
    Returns:
        Adjusted probability
    """
    adj = probability
    
    if is_b2b:
        adj += NHL_ADJUSTMENTS["b2b_penalty"]
    
    if is_travel_fatigued:
        adj += NHL_ADJUSTMENTS["travel_penalty"]
    
    if is_home:
        adj += NHL_ADJUSTMENTS["home_ice_boost"]
    
    # Clamp to valid range
    return max(0.0, min(1.0, adj))
