"""
Tier assignment based on Monte Carlo probability thresholds.
"""


def assign_tier(p_hit: float) -> str:
    """
    Assign confidence tier based on probability of hitting.
    
    - SLAM: 85%+ (near-locks, publish with high confidence)
    - STRONG: 70-85% (solid edge, publish as strong plays)
    - LEAN: 60-70% (marginal edge, publish with caveats)
    - AVOID: <60% (no edge or negative EV, do not publish)
    """
    if p_hit >= 0.85:
        return "SLAM"
    elif p_hit >= 0.70:
        return "STRONG"
    elif p_hit >= 0.60:
        return "LEAN"
    else:
        return "AVOID"


def tier_emoji(tier: str) -> str:
    """Get emoji for tier display."""
    return {
        "SLAM": "🔥",
        "STRONG": "💪",
        "LEAN": "📊",
        "AVOID": "⚠️"
    }.get(tier, "❓")


def tier_description(tier: str) -> str:
    """Get description for tier."""
    return {
        "SLAM": "High confidence play with strong statistical edge",
        "STRONG": "Solid edge with favorable probability",
        "LEAN": "Marginal edge, proceed with caution",
        "AVOID": "No statistical edge, skip this play"
    }.get(tier, "Unknown tier")
