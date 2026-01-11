# engine/score_edges.py
"""
Edge scoring with empirical probability + pace adjustment.

Phase 1B: Replaces Normal CDF with empirical frequency-based probabilities.
- Truth-preserving: No distributional assumptions
- Pace-aware: Integrates game pace context
- Stat-class governed: Conditional caps by stat type
- Small sample protected: Caps confidence when n < 10

Confidence Tiers (post-governance):
- SLAM: 75%+ (CORE stats only)
- STRONG: 65-74%
- LEAN: 55-64%
"""

import sys
from pathlib import Path

# Import probability systems
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.empirical_probability import calculate_empirical_probability
from engine.pace_adjustment import pace_adjust_mean, get_team_pace
from ufa.analysis.prob import STAT_CLASS, apply_confidence_governor


# DELETED: Normal CDF removed in Phase 1B
# Empirical probability replaces all CDF calls


def infer_stat_name(pick: dict) -> str:
    """
    Extract stat name from pick dict for classification.
    
    Handles various key patterns: 'stat', 'stat_type', 'prop_type'
    """
    return (
        pick.get("stat") or
        pick.get("stat_type") or
        pick.get("prop_type") or
        pick.get("market", "").lower() or
        "unknown"
    )


def infer_sample_size(pick: dict) -> int:
    """
    Extract or infer sample size for Bayesian shrinkage.
    
    Priority:
    1. Explicit 'sample_size' field
    2. Length of 'recent_values' list
    3. Default to 10
    """
    if "sample_size" in pick:
        return pick["sample_size"]
    
    recent = pick.get("recent_values", [])
    if recent:
        return len(recent)
    
    return 10  # Conservative default


def score_edges(picks, pace_data: dict = None):
    """
    Score picks using empirical probability + pace adjustment.
    
    Phase 1B Flow:
    1. Extract game_logs (required for empirical probability)
    2. Apply pace adjustment to projection mean
    3. Calculate empirical probability from historical frequencies
    4. Apply stat-class conditional caps (CORE/VOLUME/EVENT)
    5. Assign tier based on governed probability
    6. Full audit trail logging
    
    Args:
        picks: List of pick dicts (must have 'game_logs' field)
        pace_data: Optional dict of team -> pace mappings
    
    Returns:
        List of scored picks with empirical probabilities
    """
    scored = []
    pace_data = pace_data or {}

    for p in picks:
        # Support both game_logs (dicts) and recent_values (numbers)
        game_logs = p.get("game_logs") or p.get("recent_games")
        recent_values = p.get("recent_values")

        # If we have recent_values but no game_logs, convert to game_log format
        if not game_logs and recent_values and len(recent_values) >= 2:
            stat_name = infer_stat_name(p)
            game_logs = [{stat_name: val, "minutes": 30} for val in recent_values]

        # HARD ERROR: NFL hydration not implemented
        if p.get("league", "").upper() == "NFL" or p.get("sport", "").upper() == "NFL":
            if not game_logs or len(game_logs) < 2:
                from hydrators.nfl_stat_hydrator import HydrationError
                raise HydrationError("NFL stat engine not implemented. See hydrators/nfl_stat_hydrator.py and SOP §3.1.")

        if not game_logs or len(game_logs) < 2:
            continue

        line = p["line"]
        stat_name = infer_stat_name(p)
        
        # Extract team/opponent for pace adjustment
        team = p.get("team")
        opponent = p.get("opponent") or p.get("opp")
        
        # Normalize direction
        direction_raw = str(p.get("direction", "")).strip().lower()
        if direction_raw in ("over", "o", "higher", "h"):
            direction = "higher"
        else:
            direction = "lower"
        
        # Calculate pace-adjusted mean (if pace data available)
        pace_adjusted_mean = None
        pace_context = None
        
        if team and opponent and pace_data:
            team_pace = get_team_pace(team, pace_data)
            opp_pace = get_team_pace(opponent, pace_data)
            
            # Extract base mean from game logs
            base_mean = sum(g.get(stat_name, 0) for g in game_logs) / len(game_logs)
            pace_adjusted_mean, pace_context = pace_adjust_mean(base_mean, team_pace, opp_pace)
        
        # Calculate empirical probability with pace blending
        prob_result = calculate_empirical_probability(
            game_logs=game_logs,
            stat=stat_name,
            line=line,
            direction=direction,
            pace_adjusted_mean=pace_adjusted_mean
        )
        
        if prob_result["probability"] is None:
            continue
        
        prob = prob_result["probability"]
        
        # Apply stat-class conditional caps
        stat_class = STAT_CLASS.get(stat_name, "core")
        usage_rate = p.get("usage_rate") or p.get("usage_pct")
        minutes_projected = p.get("minutes_projected") or p.get("mpg") or p.get("minutes")

        governed_prob = apply_confidence_governor(
            prob,
            stat_class=stat_class,
            sample_size=prob_result["sample_size"],
            usage_rate=usage_rate,
            minutes_projected=minutes_projected
        )


        # Stack penalties: roster + composite missing
        roster_penalty = p.get("confidence_penalty", 0.0)
        composite_penalty = p.get("composite_missing_penalty", 0.0)
        total_penalty = roster_penalty + composite_penalty
        # Penalties are additive, but probability is bounded below at 0.5
        governed_prob = governed_prob * (1.0 - total_penalty)
        governed_prob = max(governed_prob, 0.5)
        p["confidence_penalty_applied"] = total_penalty

        p["probability"] = round(governed_prob, 4)
        p["confidence_tier"] = assign_tier(governed_prob)

        # Add stat classification for audit trail
        p["stat_class"] = stat_class

        # Add full probability audit trail
        p["prob_method"] = prob_result
        if pace_context:
            p["pace_context"] = pace_context
        
        # Add usage/minutes context if provided
            p["usage_rate"] = usage_rate
        if minutes_projected is not None:
            p["minutes_projected"] = minutes_projected

        if p["confidence_tier"] is None:
            continue

        scored.append(p)

    return scored


def assign_tier(prob):
    """
    Assign tier based on governed probability.
    
    Note: Probability already capped by stat class, so tier thresholds
    reflect true confidence ranges:
    - SLAM: 75%+ (only achievable for CORE stats)
    - STRONG: 65-74%
    - LEAN: 55-64%
    
    Args:
        prob: Governed probability (already capped by UFA system)
    
    Returns:
        'SLAM', 'STRONG', 'LEAN', or None
    """
    if prob >= 0.75:
        return "SLAM"
    if prob >= 0.65:
        return "STRONG"
    if prob >= 0.55:
        return "LEAN"
    return None
