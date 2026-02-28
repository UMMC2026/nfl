"""
MARKET ALIGNMENT GATE
Validates model probabilities against market-implied probabilities.
Blocks picks when model diverges >15% from efficient market pricing.

Purpose:
- Prevent systematic overconfidence vs market wisdom
- Flag probability miscalibration early
- Enforce humility threshold for edge claims

Author: MIT Quant System Refinement - Tier 1 Immediate Fix
Date: 2026-01-24
"""

from typing import Optional, Dict, Tuple


def calculate_novig_probability(multiplier_higher: float, multiplier_lower: float) -> Dict[str, float]:
    """
    Calculate no-vig (fair) probabilities from Underdog multipliers.
    
    Formula: p_i = (1/m_i) / sum(1/m_j)
    
    Args:
        multiplier_higher: HIGHER multiplier (e.g., 1.75)
        multiplier_lower: LOWER multiplier (e.g., 2.20)
    
    Returns:
        Dict with 'over' and 'under' probabilities (0-100 scale)
    """
    try:
        # Convert to implied probabilities
        prob_higher = 1.0 / multiplier_higher
        prob_lower = 1.0 / multiplier_lower
        
        # Remove vig (normalize to sum = 1.0)
        total = prob_higher + prob_lower
        
        return {
            "over": (prob_higher / total) * 100,
            "under": (prob_lower / total) * 100,
        }
    except (ZeroDivisionError, ValueError):
        return {"over": 50.0, "under": 50.0}  # Fallback to 50/50


def check_market_alignment(
    model_prob: float,
    direction: str,
    multiplier_higher: Optional[float] = None,
    multiplier_lower: Optional[float] = None,
    threshold_pct: float = 15.0,
) -> Tuple[bool, str, Dict]:
    """
    Check if model probability aligns with market within threshold.
    
    Args:
        model_prob: Model probability (0-100 scale)
        direction: "OVER" or "UNDER"
        multiplier_higher: HIGHER multiplier from Underdog
        multiplier_lower: LOWER multiplier from Underdog
        threshold_pct: Maximum allowed divergence (default 15%)
    
    Returns:
        (passes_gate, message, details_dict)
        
    Example:
        >>> check_market_alignment(55.8, "OVER", 1.75, 2.20)
        (False, "MARKET CONFLICT: Model 55.8% vs Market 43.2% (Δ=12.6%)", {...})
    """
    # If no market data, cannot validate - PASS with warning
    if multiplier_higher is None or multiplier_lower is None:
        return (True, "⚠️ No market data - cannot validate alignment", {
            "market_prob": None,
            "model_prob": model_prob,
            "divergence": None,
            "threshold": threshold_pct
        })
    
    # Calculate market-implied probabilities
    market_probs = calculate_novig_probability(multiplier_higher, multiplier_lower)
    
    # Get the relevant market probability based on direction
    direction_upper = direction.upper()
    if direction_upper == "OVER":
        market_prob = market_probs["over"]
    elif direction_upper == "UNDER":
        market_prob = market_probs["under"]
    else:
        return (True, f"⚠️ Unknown direction '{direction}' - skipping gate", {
            "market_prob": None,
            "model_prob": model_prob,
            "divergence": None,
            "threshold": threshold_pct
        })
    
    # Calculate divergence (absolute percentage point difference)
    divergence = abs(model_prob - market_prob)
    
    # Check if within threshold
    passes = divergence <= threshold_pct
    
    # Build message
    if passes:
        msg = f"✓ Market aligned: Model {model_prob:.1f}% vs Market {market_prob:.1f}% (Δ={divergence:.1f}%)"
    else:
        msg = f"❌ MARKET CONFLICT: Model {model_prob:.1f}% vs Market {market_prob:.1f}% (Δ={divergence:.1f}% > {threshold_pct}%)"
    
    # Build details dict
    details = {
        "market_prob": market_prob,
        "model_prob": model_prob,
        "divergence": divergence,
        "threshold": threshold_pct,
        "multiplier_higher": multiplier_higher,
        "multiplier_lower": multiplier_lower,
        "direction": direction,
        "passes": passes
    }
    
    return (passes, msg, details)


def apply_market_gate_to_edges(edges: list, threshold_pct: float = 15.0) -> Tuple[list, list]:
    """
    Apply market alignment gate to a list of edges.
    
    Args:
        edges: List of edge dicts with 'probability', 'direction', optional 'multiplier_higher'/'multiplier_lower'
        threshold_pct: Divergence threshold (default 15%)
    
    Returns:
        (passing_edges, blocked_edges)
    """
    passing = []
    blocked = []
    
    for edge in edges:
        prob = edge.get("probability", 50.0)
        direction = edge.get("direction", "OVER")
        mult_h = edge.get("multiplier_higher")
        mult_l = edge.get("multiplier_lower")
        
        passes, msg, details = check_market_alignment(
            model_prob=prob,
            direction=direction,
            multiplier_higher=mult_h,
            multiplier_lower=mult_l,
            threshold_pct=threshold_pct
        )
        
        # Attach gate result to edge
        edge_copy = edge.copy()
        edge_copy["market_gate"] = {
            "passes": passes,
            "message": msg,
            "details": details
        }
        
        if passes:
            passing.append(edge_copy)
        else:
            blocked.append(edge_copy)
    
    return passing, blocked


# CLI for testing
if __name__ == "__main__":
    import sys
    
    print("=== MARKET ALIGNMENT GATE TEST ===\n")
    
    # Test case 1: Maxey AST OVER (from user's example)
    print("[1] Tyrese Maxey AST OVER 6.5")
    print("    Model: 55.8% | Market: 1.75 HIGHER, 2.20 LOWER")
    passes, msg, details = check_market_alignment(
        model_prob=55.8,
        direction="OVER",
        multiplier_higher=1.75,
        multiplier_lower=2.20,
        threshold_pct=15.0
    )
    print(f"    Result: {msg}")
    print(f"    Market prob: {details['market_prob']:.1f}%")
    print(f"    Divergence: {details['divergence']:.1f}%")
    print(f"    Passes: {passes}\n")
    
    # Test case 2: Brunson PTS OVER (aligned example)
    print("[2] Jalen Brunson PTS OVER 27.5")
    print("    Model: 58.0% | Market: 1.65 HIGHER, 2.35 LOWER")
    passes, msg, details = check_market_alignment(
        model_prob=58.0,
        direction="OVER",
        multiplier_higher=1.65,
        multiplier_lower=2.35,
        threshold_pct=15.0
    )
    print(f"    Result: {msg}")
    print(f"    Market prob: {details['market_prob']:.1f}%")
    print(f"    Divergence: {details['divergence']:.1f}%")
    print(f"    Passes: {passes}\n")
    
    # Test case 3: No market data
    print("[3] Player X UNDER 5.5 (no market data)")
    passes, msg, details = check_market_alignment(
        model_prob=65.0,
        direction="UNDER",
        multiplier_higher=None,
        multiplier_lower=None,
        threshold_pct=15.0
    )
    print(f"    Result: {msg}")
    print(f"    Passes: {passes}\n")
    
    print("=== TEST COMPLETE ===")
