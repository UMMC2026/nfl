"""
CBB Risk Manager
-----------------
Unit sizing and exposure control based on session state and regime.

Uses:
1. Unit policy from state.json
2. Season regime from config
3. Tournament mode restrictions
4. Daily exposure limits
"""

import json
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


CONFIG_DIR = Path(__file__).parent.parent / "config"


@dataclass
class UnitSizing:
    """Unit sizing recommendation."""
    base_units: float
    adjusted_units: float
    policy: str
    adjustments: list
    max_exposure_remaining: float


def load_unit_policy() -> dict:
    """Load unit policy configuration."""
    policy_file = CONFIG_DIR / "unit_policy.yaml"
    with open(policy_file, 'r') as f:
        return yaml.safe_load(f)


def load_tournament_mode() -> dict:
    """Load tournament mode configuration."""
    tourney_file = CONFIG_DIR / "tournament_mode.yaml"
    with open(tourney_file, 'r') as f:
        return yaml.safe_load(f)


def load_state() -> dict:
    """Load current run state."""
    from .update_state import load_state as _load_state
    return _load_state()


def compute_unit_size(
    edge_tier: str,
    edge_probability: float,
    is_tournament: bool = False,
    regime: str = "MID_SEASON"
) -> UnitSizing:
    """
    Compute recommended unit size for an edge.
    
    Args:
        edge_tier: STRONG or LEAN
        edge_probability: Probability (0-1)
        is_tournament: Whether this is a tournament game
        regime: Current season regime
    
    Returns:
        UnitSizing with base, adjusted units, and reasoning
    """
    state = load_state()
    policy_config = load_unit_policy()
    tournament_config = load_tournament_mode()
    
    adjustments = []
    
    # 1. Get base units from tier
    if edge_tier == "STRONG":
        base_units = 1.5
    else:  # LEAN
        base_units = 1.0
    
    # 2. Get policy multiplier
    current_policy = state['bankroll']['current_policy']
    policy_data = policy_config['POLICIES'].get(current_policy, policy_config['POLICIES']['NORMAL'])
    policy_mult = policy_data['unit_multiplier']
    
    adjusted_units = base_units * policy_mult
    adjustments.append(f"Policy {current_policy}: x{policy_mult}")
    
    # 3. Apply tournament restrictions
    if is_tournament:
        max_units = tournament_config.get('MARCH_MADNESS', {}).get('unit_cap', 1.0)
        if adjusted_units > max_units:
            adjusted_units = max_units
            adjustments.append(f"Tournament cap: max {max_units}u")
    
    # 4. Apply regime adjustments
    if regime == "EARLY_SEASON":
        adjusted_units *= 0.85
        adjustments.append("Early season: x0.85")
    elif regime == "NCAA_TOURNAMENT":
        adjusted_units *= 0.80
        adjustments.append("March Madness: x0.80")
    
    # 5. Check daily exposure
    daily_exposure = state['bankroll']['daily_exposure']
    max_daily = state['bankroll']['max_daily_exposure']
    remaining = max_daily - daily_exposure
    
    if adjusted_units > remaining:
        adjusted_units = max(0.5, remaining)  # Minimum 0.5u if any exposure left
        adjustments.append(f"Daily limit: capped at {remaining:.1f}u remaining")
    
    # 6. Round to nearest 0.25
    adjusted_units = round(adjusted_units * 4) / 4
    
    return UnitSizing(
        base_units=base_units,
        adjusted_units=adjusted_units,
        policy=current_policy,
        adjustments=adjustments,
        max_exposure_remaining=remaining
    )


def can_add_exposure(units: float) -> tuple[bool, str]:
    """
    Check if we can add more exposure today.
    
    Returns:
        (can_add, reason)
    """
    state = load_state()
    daily_exposure = state['bankroll']['daily_exposure']
    max_daily = state['bankroll']['max_daily_exposure']
    remaining = max_daily - daily_exposure
    
    if units <= remaining:
        return True, f"{remaining:.1f}u remaining today"
    else:
        return False, f"Would exceed daily limit ({daily_exposure:.1f}/{max_daily:.1f}u used)"


def record_exposure(units: float) -> dict:
    """Record that exposure was added."""
    from .update_state import load_state, save_state
    state = load_state()
    state['bankroll']['daily_exposure'] += units
    save_state(state)
    return state


def get_max_edges_for_game(is_tournament: bool = False) -> int:
    """Get maximum edges allowed per game."""
    if is_tournament:
        tournament_config = load_tournament_mode()
        return tournament_config.get('MARCH_MADNESS', {}).get('max_edges_per_game', 1)
    return 2  # Default max 2 edges per game


def get_exposure_summary() -> dict:
    """Get current exposure summary."""
    state = load_state()
    return {
        'policy': state['bankroll']['current_policy'],
        'policy_reason': state['bankroll']['policy_reason'],
        'daily_exposure': state['bankroll']['daily_exposure'],
        'max_daily_exposure': state['bankroll']['max_daily_exposure'],
        'remaining': state['bankroll']['max_daily_exposure'] - state['bankroll']['daily_exposure']
    }
