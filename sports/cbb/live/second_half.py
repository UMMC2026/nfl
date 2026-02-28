"""
CBB Second-Half-Only Unders Module
-----------------------------------
Second halves concentrate pace collapse + ref tightening.
This module suppresses pregame overs and allows only 2H unders when conditions qualify.
"""

import yaml
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime


CONFIG_PATH = Path(__file__).parent.parent / "config" / "second_half.yaml"


def load_config() -> dict:
    """Load second-half configuration."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


@dataclass
class SecondHalfState:
    """Current state for second-half evaluation."""
    pace_ratio: float
    fouls_per_min: float
    baseline_fouls: float
    score_margin: int  # Absolute value of lead
    elapsed_minutes: float
    already_lost_on_game: bool = False


@dataclass
class SecondHalfDecision:
    """Decision output for second-half module."""
    allow_pregame: bool
    allow_2h_unders: bool
    triggers_met: int
    trigger_details: Dict[str, bool]
    unit_mult: float
    reason: str


def check_triggers(state: SecondHalfState) -> Dict[str, bool]:
    """
    Check which second-half triggers are met.
    
    Returns dict of trigger_name -> met (bool)
    """
    config = load_config()
    triggers = config["TRIGGERS"]
    
    results = {}
    
    # Pace ratio below threshold
    results["pace_collapse"] = state.pace_ratio < triggers["pace_ratio_below"]
    
    # Fouls below baseline (refs letting them play)
    foul_threshold = state.baseline_fouls * triggers["foul_rate_below_mult"]
    results["foul_rate_low"] = state.fouls_per_min < foul_threshold
    
    # Lead margin (one team controlling)
    results["lead_control"] = state.score_margin >= triggers["lead_margin_min"]
    
    return results


def allow_second_half_only(state: SecondHalfState) -> SecondHalfDecision:
    """
    Determine if second-half-only mode should activate.
    
    Args:
        state: Current live game state
    
    Returns:
        SecondHalfDecision with allow flags and reasoning
    """
    config = load_config()
    
    if not config["ENABLE"]:
        return SecondHalfDecision(
            allow_pregame=True,
            allow_2h_unders=False,
            triggers_met=0,
            trigger_details={},
            unit_mult=1.0,
            reason="SECOND_HALF_MODULE_DISABLED"
        )
    
    # Check triggers
    trigger_results = check_triggers(state)
    triggers_met = sum(trigger_results.values())
    
    # Need minimum triggers to activate
    activated = triggers_met >= config["MIN_TRIGGERS"]
    
    if not activated:
        return SecondHalfDecision(
            allow_pregame=True,
            allow_2h_unders=False,
            triggers_met=triggers_met,
            trigger_details=trigger_results,
            unit_mult=1.0,
            reason=f"INSUFFICIENT_TRIGGERS ({triggers_met}/{config['MIN_TRIGGERS']})"
        )
    
    # Check if past halftime
    sh_config = config["SECOND_HALF_UNDERS"]
    past_halftime = state.elapsed_minutes >= sh_config["min_elapsed_minutes"]
    
    # Block if already lost on this game
    if state.already_lost_on_game and sh_config["block_after_loss"]:
        return SecondHalfDecision(
            allow_pregame=False,
            allow_2h_unders=False,
            triggers_met=triggers_met,
            trigger_details=trigger_results,
            unit_mult=0.0,
            reason="ALREADY_LOST_ON_GAME"
        )
    
    actions = config["ACTIONS"]
    
    return SecondHalfDecision(
        allow_pregame=not actions["block_pregame_overs"],
        allow_2h_unders=past_halftime and actions["allow_2h_unders"],
        triggers_met=triggers_met,
        trigger_details=trigger_results,
        unit_mult=actions["unit_reduction"],
        reason="SECOND_HALF_ONLY_ACTIVE"
    )


def get_2h_under_units(base_units: float) -> float:
    """Get max units allowed for 2H unders."""
    config = load_config()
    max_units = config["SECOND_HALF_UNDERS"]["max_units"]
    return min(base_units, max_units)


# Convenience function for external use
def evaluate_second_half(live: Dict) -> SecondHalfDecision:
    """
    Evaluate second-half mode from live state dict.
    
    Args:
        live: Dict with keys: pace_ratio, fouls_per_min, baseline_fouls,
              score_margin, elapsed_minutes, already_lost_on_game
    
    Returns:
        SecondHalfDecision
    """
    state = SecondHalfState(
        pace_ratio=live.get("pace_ratio", 1.0),
        fouls_per_min=live.get("fouls_per_min", 0.5),
        baseline_fouls=live.get("baseline_fouls", 0.5),
        score_margin=abs(live.get("score_margin", 0)),
        elapsed_minutes=live.get("elapsed_minutes", 0),
        already_lost_on_game=live.get("already_lost_on_game", False)
    )
    
    return allow_second_half_only(state)
