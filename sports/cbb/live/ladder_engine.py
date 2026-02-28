"""
CBB March In-Game Ladder Engine
--------------------------------
Conditional reinforcement when early signals confirm structural unders.
This is NOT martingale — any loss stops the ladder.

Philosophy:
- Observability before automation
- Conditional escalation, not reactive
- Convex-down risk curve
"""

import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


CONFIG_PATH = Path(__file__).parent / "ladder_policy.yaml"


def load_ladder_policy() -> dict:
    """Load ladder policy configuration."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


@dataclass
class LadderState:
    """Current state for ladder evaluation."""
    mode: str  # NORMAL, UNDERS_ONLY, 2H_ONLY, HALTED
    fouls_per_min: float
    baseline_fouls: float
    pace_ratio: float
    top_foulout_probs: list
    elapsed_minutes: float
    has_lost_today: bool = False


@dataclass
class LadderDecision:
    """Ladder step decision output."""
    step_allowed: bool
    step_name: str
    unit_mult: float
    unit_cap: float
    final_units: float
    requirements_met: Dict[str, bool]
    reason: str


# Global halt flag
HALT_LADDER = False


def is_tournament() -> bool:
    """Check if currently in tournament regime."""
    from sports.cbb.edges.edge_gates import detect_season_regime
    regime = detect_season_regime()
    return regime in ["CONFERENCE_TOURNAMENT", "NCAA_TOURNAMENT"]


def ladder_step_allowed(
    step: str,
    state: LadderState
) -> Tuple[bool, Dict[str, bool]]:
    """
    Check if a ladder step is allowed based on current state.
    
    Args:
        step: PREGAME, HALF_TIME, or SECOND_HALF
        state: Current ladder state
    
    Returns:
        (allowed, requirements_met dict)
    """
    global HALT_LADDER
    
    policy = load_ladder_policy()
    march = policy["MARCH"]
    
    # Check global conditions
    if not is_tournament():
        return False, {"tournament": False}
    
    if not march["ENABLE"]:
        return False, {"enabled": False}
    
    if HALT_LADDER or state.has_lost_today:
        return False, {"halt": True}
    
    # Get step requirements
    step_config = march.get(step, {})
    requirements = step_config.get("require", {})
    
    if not requirements:
        # PREGAME has no requirements (just reduced units)
        return True, {}
    
    # Check each requirement
    met = {}
    
    for req_key, req_value in requirements.items():
        if req_key == "lock_unders":
            met[req_key] = state.mode == "UNDERS_ONLY"
        
        elif req_key == "foul_rate_below_mult":
            foul_threshold = state.baseline_fouls * req_value
            met[req_key] = state.fouls_per_min < foul_threshold
        
        elif req_key == "pace_ratio_below":
            met[req_key] = state.pace_ratio < req_value
        
        elif req_key == "foulout_prob_min":
            max_prob = max(state.top_foulout_probs) if state.top_foulout_probs else 0
            met[req_key] = max_prob >= req_value
    
    all_met = all(met.values())
    return all_met, met


def compute_ladder_units(
    base_units: float,
    step: str
) -> Tuple[float, float, float]:
    """
    Compute ladder units for a step.
    
    Args:
        base_units: Base unit size
        step: PREGAME, HALF_TIME, or SECOND_HALF
    
    Returns:
        (unit_mult, unit_cap, final_units)
    """
    policy = load_ladder_policy()
    march = policy["MARCH"]
    caps = policy["UNIT_CAPS"]
    
    step_config = march.get(step, {})
    unit_mult = step_config.get("unit_mult", 1.0)
    unit_cap = caps.get(step, 1.0)
    
    # Apply multiplier then cap
    adjusted = base_units * unit_mult
    final = min(adjusted, unit_cap)
    
    return unit_mult, unit_cap, round(final, 2)


def evaluate_ladder_step(
    step: str,
    state: LadderState,
    base_units: float = 1.0
) -> LadderDecision:
    """
    Evaluate a ladder step and return decision.
    
    Args:
        step: PREGAME, HALF_TIME, or SECOND_HALF
        state: Current ladder state
        base_units: Base unit size
    
    Returns:
        LadderDecision with all details
    """
    allowed, requirements_met = ladder_step_allowed(step, state)
    unit_mult, unit_cap, final_units = compute_ladder_units(base_units, step)
    
    if not allowed:
        # Find failed requirement
        failed = [k for k, v in requirements_met.items() if not v]
        reason = f"BLOCKED: {failed[0] if failed else 'unknown'}"
        final_units = 0.0
    else:
        reason = f"ALLOWED: {step}"
    
    return LadderDecision(
        step_allowed=allowed,
        step_name=step,
        unit_mult=unit_mult,
        unit_cap=unit_cap,
        final_units=final_units if allowed else 0.0,
        requirements_met=requirements_met,
        reason=reason
    )


def record_ladder_loss() -> None:
    """Record a loss and halt the ladder."""
    global HALT_LADDER
    
    policy = load_ladder_policy()
    if policy["MARCH"]["STOP_ON_LOSS"]:
        HALT_LADDER = True


def reset_ladder() -> None:
    """Reset ladder for new day/session."""
    global HALT_LADDER
    HALT_LADDER = False


def get_ladder_summary(state: LadderState, base_units: float = 1.0) -> Dict:
    """
    Get summary of all ladder steps.
    
    Args:
        state: Current ladder state
        base_units: Base unit size
    
    Returns:
        Dict with step summaries
    """
    steps = ["PREGAME", "HALF_TIME", "SECOND_HALF"]
    
    results = {}
    total_potential = 0.0
    
    for step in steps:
        decision = evaluate_ladder_step(step, state, base_units)
        results[step] = {
            "allowed": decision.step_allowed,
            "units": decision.final_units,
            "reason": decision.reason
        }
        if decision.step_allowed:
            total_potential += decision.final_units
    
    policy = load_ladder_policy()
    max_exposure = policy["MAX_LADDER_EXPOSURE"]
    
    results["_summary"] = {
        "total_potential_units": total_potential,
        "max_ladder_exposure": max_exposure,
        "halt_active": HALT_LADDER,
        "is_tournament": is_tournament()
    }
    
    return results


# === INTEGRATION HELPERS ===

def get_next_ladder_action(
    state: LadderState,
    current_step: Optional[str],
    base_units: float = 1.0
) -> Optional[LadderDecision]:
    """
    Determine the next ladder action based on current state.
    
    Args:
        state: Current ladder state
        current_step: Current step (None, PREGAME, HALF_TIME)
        base_units: Base unit size
    
    Returns:
        LadderDecision for next step, or None if no action
    """
    # Determine which step to evaluate
    if current_step is None:
        next_step = "PREGAME"
    elif current_step == "PREGAME":
        # Only move to HALF_TIME if past halftime
        if state.elapsed_minutes >= 20:
            next_step = "HALF_TIME"
        else:
            return None
    elif current_step == "HALF_TIME":
        # Only move to SECOND_HALF mid-2H
        if state.elapsed_minutes >= 30:
            next_step = "SECOND_HALF"
        else:
            return None
    else:
        # Already at SECOND_HALF, no more steps
        return None
    
    return evaluate_ladder_step(next_step, state, base_units)


# Example usage
if __name__ == "__main__":
    # Test state
    test_state = LadderState(
        mode="UNDERS_ONLY",
        fouls_per_min=0.45,
        baseline_fouls=0.50,
        pace_ratio=0.88,
        top_foulout_probs=[0.32, 0.18],
        elapsed_minutes=25.0,
        has_lost_today=False
    )
    
    summary = get_ladder_summary(test_state, base_units=1.0)
    
    print("\n📈 LADDER SUMMARY")
    print("-" * 40)
    for step in ["PREGAME", "HALF_TIME", "SECOND_HALF"]:
        s = summary[step]
        status = "✅" if s["allowed"] else "❌"
        print(f"{status} {step}: {s['units']}u — {s['reason']}")
    
    print(f"\nTotal Potential: {summary['_summary']['total_potential_units']}u")
    print(f"Max Allowed: {summary['_summary']['max_ladder_exposure']}u")
