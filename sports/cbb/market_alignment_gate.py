"""
CBB MARKET ALIGNMENT GATE
Validates model probabilities against Underdog multiplier-implied probabilities.

CBB-specific notes:
- College basketball has HIGHER variance than NBA
- Market efficiency is LOWER (softer lines, less sharp money)
- Threshold set to 12% for CBB (updated from 15% to match Tennis, more conservative than initial design)
- Only applies when CBB is enabled (status != RESEARCH)
"""

from typing import Optional, Dict, Tuple


def calculate_cbb_novig_probability(
    multiplier_higher: float,
    multiplier_lower: float
) -> Dict[str, float]:
    """
    Calculate no-vig probabilities from CBB prop multipliers.
    Uses same formula as NBA but with CBB-aware interpretation.
    
    Args:
        multiplier_higher: HIGHER multiplier
        multiplier_lower: LOWER multiplier
    
    Returns:
        Dict with 'over' and 'under' probabilities (0-100 scale)
    """
    try:
        prob_higher = 1.0 / multiplier_higher
        prob_lower = 1.0 / multiplier_lower
        total = prob_higher + prob_lower
        
        return {
            "over": (prob_higher / total) * 100,
            "under": (prob_lower / total) * 100,
        }
    except (ZeroDivisionError, ValueError):
        return {"over": 50.0, "under": 50.0}


def check_cbb_market_alignment(
    model_prob: float,
    direction: str,
    multiplier_higher: Optional[float] = None,
    multiplier_lower: Optional[float] = None,
    threshold_pct: float = 12.0  # Updated: 12% for CBB (was 15%, now aligned with Tennis)
) -> Tuple[bool, str, Dict]:
    """
    Check if CBB model probability aligns with market within threshold.
    
    Args:
        model_prob: Model probability (0-100 scale)
        direction: "OVER" or "UNDER"
        multiplier_higher: HIGHER multiplier from Underdog
        multiplier_lower: LOWER multiplier from Underdog
        threshold_pct: Maximum allowed divergence (default 15% for CBB)
    
    Returns:
        (passes_gate, message, details_dict)
        
    Note:
        CBB threshold is looser (15%) vs NBA (10%) because:
        1. Market is less efficient (smaller betting volume)
        2. Player variance is higher (rotation changes, foul trouble)
        3. Data quality is lower (inconsistent stat tracking)
    """
    # No market data - pass with warning
    if multiplier_higher is None or multiplier_lower is None:
        return (True, "⚠️ No market data - cannot validate alignment", {
            "market_prob": None,
            "model_prob": model_prob,
            "divergence": None,
            "threshold": threshold_pct
        })
    
    # Calculate market probabilities
    market_probs = calculate_cbb_novig_probability(multiplier_higher, multiplier_lower)
    
    # Get relevant market probability
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
    
    # Calculate divergence
    divergence = abs(model_prob - market_prob)
    
    # Check threshold
    passes = divergence <= threshold_pct
    
    # Build message
    if passes:
        msg = f"✓ Market aligned: Model {model_prob:.1f}% vs Market {market_prob:.1f}% (Δ={divergence:.1f}%)"
    else:
        msg = f"❌ MARKET CONFLICT: Model {model_prob:.1f}% vs Market {market_prob:.1f}% (Δ={divergence:.1f}% > {threshold_pct}%)"
    
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


# CLI for testing
if __name__ == "__main__":
    print("=== CBB MARKET ALIGNMENT GATE TEST ===\n")
    
    # Test 1: Points OVER (aligned)
    print("[1] Zach Edey PTS OVER 18.5 (Purdue)")
    print("    Model: 65.0% | Market: 1.80 HIGHER, 2.10 LOWER")
    passes, msg, details = check_cbb_market_alignment(
        model_prob=65.0,
        direction="OVER",
        multiplier_higher=1.80,
        multiplier_lower=2.10,
        threshold_pct=12.0  # Updated from 15% to 12%
    )
    print(f"    Result: {msg}")
    print(f"    Market prob: {details['market_prob']:.1f}%")
    print(f"    Divergence: {details['divergence']:.1f}%")
    print(f"    Passes: {passes}\n")
    
    # Test 2: Rebounds OVER (divergent - softer market)
    print("[2] Mid-major player REB OVER 7.5")
    print("    Model: 72.0% | Market: 2.00 HIGHER, 1.90 LOWER")
    passes, msg, details = check_cbb_market_alignment(
        model_prob=72.0,
        direction="OVER",
        multiplier_higher=2.00,
        multiplier_lower=1.90,
        threshold_pct=12.0  # Updated from 15% to 12%
    )
    print(f"    Result: {msg}")
    print(f"    Market prob: {details['market_prob']:.1f}%")
    print(f"    Divergence: {details['divergence']:.1f}%")
    print(f"    Passes: {passes}\n")
    
    # Test 3: No market data
    print("[3] Unknown player (conference game, no market)")
    passes, msg, details = check_cbb_market_alignment(
        model_prob=60.0,
        direction="UNDER",
        multiplier_higher=None,
        multiplier_lower=None,
        threshold_pct=12.0  # Updated from 15% to 12%
    )
    print(f"    Result: {msg}")
    print(f"    Passes: {passes}\n")
    
    print("=== TEST COMPLETE ===")
