"""
CBB Tournament Hedge Allocator
-------------------------------
Allocate micro-hedges across correlated tournament risk (pace + whistle + seed gaps).

Philosophy:
- Hedges are QUANTIFIED, not emotional
- Never hedge with overs in March
- Hedge targets: team total under, 2H under, opponent FT under
"""

from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class HedgeRecommendation:
    """Hedge allocation recommendation."""
    primary_edge_units: float
    hedge_units: float
    hedge_pct: float
    hedge_targets: List[str]
    correlation_score: float
    reason: str


# Hedge target priorities (in order of preference)
HEDGE_TARGETS = [
    "team_total_under",
    "second_half_under",
    "opponent_ft_under",
    "game_total_under"
]

# March-specific rules
MARCH_HEDGE_RULES = {
    "block_over_hedges": True,
    "min_correlation_for_hedge": 0.20,
    "max_hedge_pct": 0.30,
    "base_hedge_pct": 0.10,
    "correlation_scale": 0.20
}


def compute_correlation_score(
    seed_gap: int,
    ref_profile: str,
    pace_volatility: float,
    coach_variance_mult: float
) -> float:
    """
    Compute correlation score for hedge sizing.
    
    Higher score = more correlated chaos = larger hedge needed.
    
    Args:
        seed_gap: Absolute seed difference (0-15)
        ref_profile: HIGH_FOUL, NEUTRAL, LOW_FOUL
        pace_volatility: Pace variance multiplier (1.0 = baseline)
        coach_variance_mult: Coach variance multiplier
    
    Returns:
        Correlation score (0.0 to 1.0)
    """
    score = 0.0
    
    # Seed gap contribution (0-0.3)
    seed_contribution = min(seed_gap / 15, 1.0) * 0.30
    score += seed_contribution
    
    # Ref profile contribution (0-0.25)
    ref_contributions = {
        "HIGH_FOUL": 0.25,
        "NEUTRAL": 0.12,
        "LOW_FOUL": 0.05
    }
    score += ref_contributions.get(ref_profile, 0.12)
    
    # Pace volatility contribution (0-0.25)
    pace_contribution = min((pace_volatility - 1.0) / 0.5, 1.0) * 0.25
    score += max(pace_contribution, 0)
    
    # Coach variance contribution (0-0.20)
    coach_contribution = min((coach_variance_mult - 1.0) / 0.4, 1.0) * 0.20
    score += max(coach_contribution, 0)
    
    return min(score, 1.0)


def allocate_hedge(
    primary_edge_units: float,
    correlation_score: float,
    is_march: bool = False
) -> float:
    """
    Compute hedge units based on primary edge and correlation.
    
    Args:
        primary_edge_units: Units on primary edge
        correlation_score: 0..1 (higher = more correlated chaos)
        is_march: Whether in March/tournament mode
    
    Returns:
        Recommended hedge units
    """
    rules = MARCH_HEDGE_RULES
    
    # Skip if correlation too low
    if correlation_score < rules["min_correlation_for_hedge"]:
        return 0.0
    
    # Calculate hedge percentage
    hedge_pct = rules["base_hedge_pct"] + rules["correlation_scale"] * correlation_score
    hedge_pct = min(hedge_pct, rules["max_hedge_pct"])
    
    # Apply March caution (reduce hedge sizing)
    if is_march:
        hedge_pct *= 0.80  # More conservative in March
    
    hedge_units = round(primary_edge_units * hedge_pct, 2)
    
    return hedge_units


def recommend_hedge(
    primary_edge_units: float,
    seed_gap: int = 0,
    ref_profile: str = "NEUTRAL",
    pace_volatility: float = 1.0,
    coach_variance_mult: float = 1.0,
    is_march: bool = False,
    available_markets: Optional[List[str]] = None
) -> HedgeRecommendation:
    """
    Generate full hedge recommendation.
    
    Args:
        primary_edge_units: Units on primary edge
        seed_gap: Absolute seed difference
        ref_profile: Ref profile (HIGH_FOUL, NEUTRAL, LOW_FOUL)
        pace_volatility: Pace variance multiplier
        coach_variance_mult: Coach variance multiplier
        is_march: Whether in March/tournament mode
        available_markets: List of available hedge markets
    
    Returns:
        HedgeRecommendation with units and targets
    """
    # Compute correlation
    correlation_score = compute_correlation_score(
        seed_gap=seed_gap,
        ref_profile=ref_profile,
        pace_volatility=pace_volatility,
        coach_variance_mult=coach_variance_mult
    )
    
    # Compute hedge units
    hedge_units = allocate_hedge(
        primary_edge_units=primary_edge_units,
        correlation_score=correlation_score,
        is_march=is_march
    )
    
    # Determine hedge targets
    hedge_targets = []
    if hedge_units > 0:
        if available_markets:
            # Use available markets in priority order
            for target in HEDGE_TARGETS:
                if target in available_markets:
                    hedge_targets.append(target)
                    break
        else:
            # Default to team total under
            hedge_targets = [HEDGE_TARGETS[0]]
    
    # Build reason
    if hedge_units == 0:
        reason = f"NO_HEDGE (correlation {correlation_score:.2f} below threshold)"
    else:
        reason = f"HEDGE_RECOMMENDED (correlation {correlation_score:.2f})"
    
    return HedgeRecommendation(
        primary_edge_units=primary_edge_units,
        hedge_units=hedge_units,
        hedge_pct=hedge_units / primary_edge_units if primary_edge_units > 0 else 0,
        hedge_targets=hedge_targets,
        correlation_score=correlation_score,
        reason=reason
    )


def is_valid_hedge_target(market: str, is_march: bool) -> bool:
    """
    Check if a market is a valid hedge target.
    
    Args:
        market: Market name
        is_march: Whether in March mode
    
    Returns:
        True if valid hedge target
    """
    # Block overs as hedges in March
    if is_march and "over" in market.lower():
        return False
    
    # Must be an under market
    if "under" not in market.lower():
        return False
    
    return True
