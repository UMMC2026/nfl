"""
Signal qualification pipeline - applies stability and tier filters.
"""

from engine.stability import stability_score, stability_class
from engine.tiers import assign_tier


def qualify_signal(signal: dict) -> dict | None:
    """
    Qualify a raw signal through the filter pipeline.
    
    Returns None if signal fails to qualify (FRAGILE stability).
    Returns enriched signal dict if qualified.
    """
    edge = signal.get("edge", 0)
    std = signal.get("std", 1)
    p_hit = signal.get("p_hit", signal.get("prob", 0))
    
    # Calculate stability metrics
    score = stability_score(edge, std)
    stability = stability_class(score)
    tier = assign_tier(p_hit)
    
    # Enrich signal with computed fields
    signal["stability_score"] = score
    signal["stability_class"] = stability
    signal["tier"] = tier
    
    # FRAGILE signals are filtered out - they have too much variance
    if stability == "FRAGILE":
        return None
    
    # AVOID tier signals are filtered out - no edge
    if tier == "AVOID":
        return None
    
    return signal


def filter_signals(raw_signals: list, 
                   min_tier: str = "LEAN",
                   require_stability: bool = True) -> list:
    """
    Filter a list of raw signals through the qualification pipeline.
    
    Args:
        raw_signals: List of signal dicts from Monte Carlo
        min_tier: Minimum tier to include ("SLAM", "STRONG", "LEAN")
        require_stability: If True, filter out FRAGILE signals
    
    Returns:
        List of qualified signals
    """
    tier_order = {"SLAM": 3, "STRONG": 2, "LEAN": 1, "AVOID": 0}
    min_tier_value = tier_order.get(min_tier, 1)
    
    qualified = []
    for s in raw_signals:
        q = qualify_signal(s)
        if q is None:
            continue
        
        # Check tier threshold
        signal_tier_value = tier_order.get(q["tier"], 0)
        if signal_tier_value < min_tier_value:
            continue
        
        qualified.append(q)
    
    return qualified


def build_signal_from_mc_result(mc_result: dict) -> dict:
    """
    Convert Monte Carlo simulation result to signal format.
    """
    return {
        "player": mc_result.get("player", ""),
        "team": mc_result.get("team", ""),
        "stat": mc_result.get("stat", ""),
        "line": mc_result.get("line", 0),
        "direction": mc_result.get("direction", "higher"),
        "play": "OVER" if mc_result.get("direction") == "higher" else "UNDER",
        "mean": mc_result.get("mean", 0),
        "std": mc_result.get("std", 1),
        "p_hit": mc_result.get("prob", 0),
        "edge": mc_result.get("edge", 0),
    }
