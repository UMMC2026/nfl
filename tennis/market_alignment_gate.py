"""
TENNIS MARKET ALIGNMENT GATE
Validates model probabilities against Underdog multiplier-implied probabilities.

Tennis adaptation notes:
- Match winner markets use decimal odds (e.g., 1.65 favorite, 2.35 underdog)
- Total games/sets use HIGHER/LOWER multipliers (same as NBA)
- Player aces use HIGHER/LOWER multipliers
- Threshold set to 12% for Tennis (slightly looser than NBA 10% due to match variance)
"""

from typing import Optional, Dict, Tuple


def calculate_tennis_novig_probability(
    multiplier_favorite: float,
    multiplier_underdog: float
) -> Dict[str, float]:
    """
    Calculate no-vig probabilities from tennis match winner odds.
    
    Args:
        multiplier_favorite: Lower decimal odd (e.g., 1.65)
        multiplier_underdog: Higher decimal odd (e.g., 2.35)
    
    Returns:
        Dict with 'favorite' and 'underdog' win probabilities (0-100 scale)
    """
    try:
        prob_fav = 1.0 / multiplier_favorite
        prob_dog = 1.0 / multiplier_underdog
        total = prob_fav + prob_dog
        
        return {
            "favorite": (prob_fav / total) * 100,
            "underdog": (prob_dog / total) * 100,
        }
    except (ZeroDivisionError, ValueError):
        return {"favorite": 50.0, "underdog": 50.0}


def calculate_tennis_totals_probability(
    multiplier_higher: float,
    multiplier_lower: float
) -> Dict[str, float]:
    """
    Calculate no-vig probabilities for tennis totals (games/sets).
    Uses same formula as NBA OVER/UNDER.
    
    Args:
        multiplier_higher: HIGHER multiplier (over the line)
        multiplier_lower: LOWER multiplier (under the line)
    
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


def check_tennis_market_alignment(
    model_prob: float,
    direction: str,
    multiplier_higher: Optional[float] = None,
    multiplier_lower: Optional[float] = None,
    threshold_pct: float = 12.0,
    market_type: str = "totals"
) -> Tuple[bool, str, Dict]:
    """
    Check if tennis model probability aligns with market within threshold.
    
    Args:
        model_prob: Model probability (0-100 scale)
        direction: "OVER"/"UNDER" for totals, "WIN"/"LOSE" for match winner
        multiplier_higher: HIGHER multiplier or favorite odds
        multiplier_lower: LOWER multiplier or underdog odds
        threshold_pct: Maximum allowed divergence (default 12% for tennis)
        market_type: "totals" (games/sets/aces) or "winner" (match result)
    
    Returns:
        (passes_gate, message, details_dict)
    """
    # No market data - pass with warning
    if multiplier_higher is None or multiplier_lower is None:
        return (True, "⚠️ No market data - cannot validate alignment", {
            "market_prob": None,
            "model_prob": model_prob,
            "divergence": None,
            "threshold": threshold_pct
        })
    
    # Calculate market probabilities based on market type
    if market_type == "totals":
        market_probs = calculate_tennis_totals_probability(multiplier_higher, multiplier_lower)
        direction_key = "over" if direction.upper() == "OVER" else "under"
    else:  # winner
        market_probs = calculate_tennis_novig_probability(multiplier_higher, multiplier_lower)
        direction_key = "favorite" if direction.upper() == "WIN" else "underdog"
    
    market_prob = market_probs.get(direction_key, 50.0)
    
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
        "market_type": market_type,
        "passes": passes
    }
    
    return (passes, msg, details)


# CLI for testing
if __name__ == "__main__":
    print("=== TENNIS MARKET ALIGNMENT GATE TEST ===\n")
    
    # Test 1: Total Games OVER (aligned)
    print("[1] Nadal vs Djokovic - Total Games OVER 22.5")
    print("    Model: 62.0% | Market: 1.70 HIGHER, 2.30 LOWER")
    passes, msg, details = check_tennis_market_alignment(
        model_prob=62.0,
        direction="OVER",
        multiplier_higher=1.70,
        multiplier_lower=2.30,
        threshold_pct=12.0,
        market_type="totals"
    )
    print(f"    Result: {msg}")
    print(f"    Market prob: {details['market_prob']:.1f}%")
    print(f"    Divergence: {details['divergence']:.1f}%")
    print(f"    Passes: {passes}\n")
    
    # Test 2: Player Aces OVER (divergent)
    print("[2] Isner - Player Aces OVER 10.5")
    print("    Model: 72.0% | Market: 1.45 HIGHER, 3.00 LOWER")
    passes, msg, details = check_tennis_market_alignment(
        model_prob=72.0,
        direction="OVER",
        multiplier_higher=1.45,
        multiplier_lower=3.00,
        threshold_pct=12.0,
        market_type="totals"
    )
    print(f"    Result: {msg}")
    print(f"    Market prob: {details['market_prob']:.1f}%")
    print(f"    Divergence: {details['divergence']:.1f}%")
    print(f"    Passes: {passes}\n")
    
    # Test 3: Match Winner (favorite)
    print("[3] Alcaraz (favorite) vs Ruud")
    print("    Model: 68.0% | Odds: 1.50 favorite, 2.70 underdog")
    passes, msg, details = check_tennis_market_alignment(
        model_prob=68.0,
        direction="WIN",
        multiplier_higher=1.50,
        multiplier_lower=2.70,
        threshold_pct=12.0,
        market_type="winner"
    )
    print(f"    Result: {msg}")
    print(f"    Market prob: {details['market_prob']:.1f}%")
    print(f"    Divergence: {details['divergence']:.1f}%")
    print(f"    Passes: {passes}\n")
    
    print("=== TEST COMPLETE ===")
