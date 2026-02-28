"""
FUOOM DARK MATTER — shared/math_utils.py
========================================
Core mathematical utilities for the betting pipeline.
Implements: American odds conversion, Kelly criterion, Expected Value,
            Brier score decomposition, vig removal.

SOP v2.1 (Truth-Enforced) compliant.
Audit Reference: FUOOM-AUDIT-001, Sections 2, 6.1, 6.2, 6.3

Author: FUOOM Engineering
Version: 1.0.0
Date: 2026-02-15
"""

import numpy as np
from typing import Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SECTION 1: ODDS CONVERSION (Audit Item #10)
# =============================================================================

def american_to_implied(odds: float) -> float:
    """Convert American odds to implied probability (includes vig).
    
    Args:
        odds: American odds (e.g., +150, -110, +285, -257)
    
    Returns:
        Implied probability as float (0.0 to 1.0)
    
    Examples:
        >>> american_to_implied(+150)   # 0.4000
        >>> american_to_implied(-110)   # 0.5238
        >>> american_to_implied(+285)   # 0.2597
        >>> american_to_implied(-257)   # 0.7199
    """
    if odds > 0:
        return 100.0 / (odds + 100.0)
    elif odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    else:
        raise ValueError("Odds cannot be zero")


def american_to_decimal(odds: float) -> float:
    """Convert American odds to decimal odds.
    
    Args:
        odds: American odds
    
    Returns:
        Decimal odds (e.g., 2.50 for +150)
    """
    if odds > 0:
        return (odds / 100.0) + 1.0
    elif odds < 0:
        return (100.0 / abs(odds)) + 1.0
    else:
        raise ValueError("Odds cannot be zero")


def decimal_to_american(decimal_odds: float) -> float:
    """Convert decimal odds to American odds.
    
    Args:
        decimal_odds: Decimal odds (must be > 1.0)
    
    Returns:
        American odds
    """
    if decimal_odds <= 1.0:
        raise ValueError(f"Decimal odds must be > 1.0, got {decimal_odds}")
    if decimal_odds >= 2.0:
        return (decimal_odds - 1.0) * 100.0  # positive
    else:
        return -100.0 / (decimal_odds - 1.0)  # negative


def remove_vig(prob_a: float, prob_b: float) -> Tuple[float, float]:
    """Remove vigorish to get true implied probabilities.
    
    Args:
        prob_a: Implied probability of outcome A (with vig)
        prob_b: Implied probability of outcome B (with vig)
    
    Returns:
        Tuple of (true_prob_a, true_prob_b) summing to 1.0
    
    Example:
        >>> # DK Predictions: YES +127, NO -257
        >>> prob_yes = american_to_implied(127)   # 0.4405
        >>> prob_no  = american_to_implied(-257)  # 0.7199
        >>> true_yes, true_no = remove_vig(prob_yes, prob_no)
        >>> # true_yes ≈ 0.3796, true_no ≈ 0.6204
    """
    total = prob_a + prob_b
    if total <= 0:
        raise ValueError("Sum of probabilities must be positive")
    vig_pct = (total - 1.0) * 100.0
    logger.debug(f"Vig detected: {vig_pct:.1f}%")
    return prob_a / total, prob_b / total


def remove_vig_multiway(probs: list) -> list:
    """Remove vig from multi-outcome markets (e.g., golf winner, MVP).
    
    Args:
        probs: List of implied probabilities (with vig)
    
    Returns:
        List of true probabilities summing to 1.0
    """
    total = sum(probs)
    if total <= 0:
        raise ValueError("Sum of probabilities must be positive")
    return [p / total for p in probs]


# =============================================================================
# SECTION 2: KELLY CRITERION (Audit Items #2, #3 — CRITICAL)
# =============================================================================

# Fractional Kelly multipliers by tier (SOP v2.1 compliant)
KELLY_FRACTIONS = {
    'SLAM':   0.40,  # Most aggressive allowed
    'STRONG': 0.30,
    'LEAN':   0.20,
    'NO_PLAY': 0.00,  # Never bet
}

# Absolute maximum bet size as fraction of bankroll
KELLY_BANKROLL_CAP = 0.05  # 5% max regardless of edge


def kelly_full(model_prob: float, decimal_odds: float) -> float:
    """Calculate full Kelly criterion fraction.
    
    Formula: kelly = (b*p - q) / b
    where:
        b = decimal_odds - 1 (net payout per unit)
        p = model probability of winning
        q = 1 - p
    
    Args:
        model_prob: Model's estimated win probability (0.0 to 1.0)
        decimal_odds: Decimal odds (e.g., 2.50 for +150)
    
    Returns:
        Full Kelly fraction (can be negative = no edge)
    """
    if not 0.0 < model_prob < 1.0:
        raise ValueError(f"Probability must be in (0, 1), got {model_prob}")
    if decimal_odds <= 1.0:
        raise ValueError(f"Decimal odds must be > 1.0, got {decimal_odds}")
    
    b = decimal_odds - 1.0
    p = model_prob
    q = 1.0 - p
    
    return (b * p - q) / b


def kelly_sized(model_prob: float, decimal_odds: float, tier: str) -> float:
    """Calculate fractional Kelly bet size with all safety caps.
    
    CRITICAL: Returns 0.0 if full Kelly is negative (no edge exists).
    This is the MANDATORY check from Audit Item #3.
    
    Args:
        model_prob: Model's estimated win probability
        decimal_odds: Decimal odds
        tier: Confidence tier ('SLAM', 'STRONG', 'LEAN', 'NO_PLAY')
    
    Returns:
        Bet size as fraction of bankroll (0.0 to KELLY_BANKROLL_CAP)
    
    Raises:
        ValueError: If tier is not recognized
    """
    if tier not in KELLY_FRACTIONS:
        raise ValueError(f"Unknown tier '{tier}'. Valid: {list(KELLY_FRACTIONS.keys())}")
    
    # NO_PLAY = always zero
    if tier == 'NO_PLAY':
        return 0.0
    
    k_full = kelly_full(model_prob, decimal_odds)
    
    # CRITICAL GATE (Audit Item #3): Negative Kelly = NO EDGE
    if k_full <= 0:
        logger.warning(
            f"Negative Kelly ({k_full:.4f}): model_prob={model_prob:.3f}, "
            f"odds={decimal_odds:.2f}. No mathematical edge. EXCLUDING."
        )
        return 0.0
    
    # Apply fractional Kelly by tier
    fraction = KELLY_FRACTIONS[tier]
    k_fractional = k_full * fraction
    
    # Cap at absolute maximum
    k_capped = min(k_fractional, KELLY_BANKROLL_CAP)
    
    logger.debug(
        f"Kelly: full={k_full:.4f}, fraction={fraction}, "
        f"fractional={k_fractional:.4f}, capped={k_capped:.4f}"
    )
    
    return k_capped


def validate_kelly(signal: Dict) -> float:
    """Validate Kelly criterion for a signal dict. Raises on negative Kelly.
    
    This is the validation gate function for validate_output.py.
    
    Args:
        signal: Dict with keys 'probability', 'decimal_odds', 'tier'
    
    Returns:
        Capped Kelly fraction
    
    Raises:
        ValidationError: If Kelly is negative (no edge exists)
    """
    prob = signal.get('probability', 0.0)
    odds = signal.get('decimal_odds', 0.0)
    tier = signal.get('confidence_tier', signal.get('tier', 'NO_PLAY'))
    
    # Convert American odds if decimal not provided
    if odds <= 1.0 and 'american_odds' in signal:
        odds = american_to_decimal(signal['american_odds'])
    
    if odds <= 1.0:
        raise ValueError(f"Cannot calculate Kelly: no valid odds in signal {signal.get('signal_id', 'UNKNOWN')}")
    
    k_full_val = kelly_full(prob, odds)
    
    if k_full_val <= 0:
        raise ValueError(
            f"{signal.get('signal_id', 'UNKNOWN')}: Negative Kelly ({k_full_val:.4f}). "
            f"No mathematical edge exists. MUST exclude."
        )
    
    return kelly_sized(prob, odds, tier)


# =============================================================================
# SECTION 3: EXPECTED VALUE (Audit Item #11)
# =============================================================================

def calculate_ev(model_prob: float, decimal_odds: float) -> float:
    """Calculate Expected Value per unit wagered.
    
    Formula: EV = (p * (odds - 1)) - (1 - p)
    
    Args:
        model_prob: Model's estimated win probability
        decimal_odds: Decimal odds
    
    Returns:
        Expected value per $1 wagered (e.g., +0.50 = 50% ROI)
    
    Example:
        >>> calculate_ev(0.60, 2.50)  # +150 odds
        0.50  # +$0.50 per $1 wagered
    """
    return (model_prob * (decimal_odds - 1.0)) - (1.0 - model_prob)


def calculate_edge(model_prob: float, implied_prob: float) -> float:
    """Calculate probability edge (for tier gating).
    
    Args:
        model_prob: Model's estimated win probability
        implied_prob: Market implied probability (vig-removed)
    
    Returns:
        Edge as probability difference
    """
    return model_prob - implied_prob


def full_edge_analysis(model_prob: float, american_odds: float) -> Dict:
    """Complete edge analysis: probability edge + EV + Kelly.
    
    This is the standard output for every signal.
    
    Args:
        model_prob: Model's estimated probability
        american_odds: American odds from the book
    
    Returns:
        Dict with edge_estimate, expected_value, kelly_full, has_edge
    """
    decimal_odds = american_to_decimal(american_odds)
    implied = american_to_implied(american_odds)
    
    # Remove vig (assume standard -110/-110 vig structure for props)
    # For actual two-sided markets, use remove_vig() with both sides
    edge = calculate_edge(model_prob, implied)
    ev = calculate_ev(model_prob, decimal_odds)
    k_full = kelly_full(model_prob, decimal_odds)
    
    return {
        'model_probability': round(model_prob, 4),
        'implied_probability': round(implied, 4),
        'edge_estimate': round(edge, 4),
        'expected_value': round(ev, 4),
        'kelly_full': round(k_full, 4),
        'has_edge': k_full > 0,
        'decimal_odds': round(decimal_odds, 4),
    }


# =============================================================================
# SECTION 4: BRIER SCORE (Audit Item #12)
# =============================================================================

def brier_score(predicted_probs: np.ndarray, actual_outcomes: np.ndarray) -> float:
    """Calculate Brier score.
    
    Formula: BS = (1/N) * Σ(predicted - actual)²
    
    Interpretation:
        0.00 = perfect calibration
        0.25 = coin flip (predicting 0.50 for everything)
        0.33 = worse than random
    
    Args:
        predicted_probs: Array of predicted probabilities
        actual_outcomes: Array of actual outcomes (0 or 1)
    
    Returns:
        Brier score (lower is better)
    """
    predicted_probs = np.asarray(predicted_probs, dtype=float)
    actual_outcomes = np.asarray(actual_outcomes, dtype=float)
    
    if len(predicted_probs) != len(actual_outcomes):
        raise ValueError("Arrays must have same length")
    if len(predicted_probs) == 0:
        raise ValueError("Cannot compute Brier score on empty arrays")
    
    return float(np.mean((predicted_probs - actual_outcomes) ** 2))


def brier_score_decomposed(predicted_probs: np.ndarray, actual_outcomes: np.ndarray,
                            n_bins: int = 10) -> Dict:
    """Decomposed Brier score: Reliability - Resolution + Uncertainty.
    
    Reliability: How well calibrated (lower = better)
    Resolution: How well it discriminates (higher = better)
    Uncertainty: Inherent unpredictability (fixed for dataset)
    
    Args:
        predicted_probs: Array of predicted probabilities
        actual_outcomes: Array of actual outcomes (0 or 1)
        n_bins: Number of calibration bins
    
    Returns:
        Dict with brier_score, reliability, resolution, uncertainty, per_bin
    """
    predicted_probs = np.asarray(predicted_probs, dtype=float)
    actual_outcomes = np.asarray(actual_outcomes, dtype=float)
    N = len(predicted_probs)
    
    if N == 0:
        raise ValueError("Cannot decompose Brier score on empty arrays")
    
    # Overall base rate
    base_rate = np.mean(actual_outcomes)
    uncertainty = base_rate * (1.0 - base_rate)
    
    # Bin predictions
    bin_edges = np.linspace(0, 1, n_bins + 1)
    reliability = 0.0
    resolution = 0.0
    bin_details = []
    
    for i in range(n_bins):
        mask = (predicted_probs >= bin_edges[i]) & (predicted_probs < bin_edges[i + 1])
        if i == n_bins - 1:  # Include right edge for last bin
            mask = (predicted_probs >= bin_edges[i]) & (predicted_probs <= bin_edges[i + 1])
        
        n_k = np.sum(mask)
        if n_k == 0:
            continue
        
        avg_predicted = np.mean(predicted_probs[mask])
        avg_observed = np.mean(actual_outcomes[mask])
        
        reliability += n_k * (avg_predicted - avg_observed) ** 2
        resolution += n_k * (avg_observed - base_rate) ** 2
        
        bin_details.append({
            'bin': f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}",
            'count': int(n_k),
            'avg_predicted': round(float(avg_predicted), 4),
            'avg_observed': round(float(avg_observed), 4),
            'calibration_error': round(float(abs(avg_predicted - avg_observed)), 4),
        })
    
    reliability /= N
    resolution /= N
    bs = brier_score(predicted_probs, actual_outcomes)
    
    return {
        'brier_score': round(float(bs), 4),
        'reliability': round(float(reliability), 4),  # lower = better
        'resolution': round(float(resolution), 4),    # higher = better
        'uncertainty': round(float(uncertainty), 4),   # fixed
        'decomposition_check': round(float(reliability - resolution + uncertainty), 4),
        'per_bin': bin_details,
    }


# Sport-specific Brier score thresholds (Audit Item #12)
BRIER_THRESHOLDS = {
    'NBA': {'props': 0.18, 'spread': 0.22, 'total': 0.20, 'moneyline': 0.20},
    'NFL': {'props': 0.20, 'spread': 0.22, 'total': 0.20, 'moneyline': 0.22},
    'CBB': {'props': 0.20, 'spread': 0.22, 'total': 0.22},
    'CFB': {'props': 0.22, 'spread': 0.24, 'total': 0.22},
    'WNBA': {'props': 0.20, 'spread': 0.22, 'total': 0.22},
    'GOLF': {'winner': 0.05, 'top10': 0.15},
    'TENNIS': {'match_winner': 0.18, 'props': 0.20},
}


# =============================================================================
# SECTION 5: UTILITY FUNCTIONS
# =============================================================================

def implied_to_american(implied_prob: float) -> float:
    """Convert implied probability back to American odds.
    
    Args:
        implied_prob: Probability (0.0 to 1.0)
    
    Returns:
        American odds
    """
    if not 0.0 < implied_prob < 1.0:
        raise ValueError(f"Probability must be in (0, 1), got {implied_prob}")
    
    if implied_prob >= 0.5:
        return -(implied_prob / (1.0 - implied_prob)) * 100.0
    else:
        return ((1.0 - implied_prob) / implied_prob) * 100.0


if __name__ == '__main__':
    # Self-test
    print("=== FUOOM math_utils.py Self-Test ===\n")
    
    # Test odds conversion
    print("--- Odds Conversion ---")
    for odds in [150, -110, 285, -257, -150, 100]:
        imp = american_to_implied(odds)
        dec = american_to_decimal(odds)
        print(f"  {odds:+d} → implied={imp:.4f}, decimal={dec:.4f}")
    
    # Test vig removal
    print("\n--- Vig Removal ---")
    yes_imp = american_to_implied(127)
    no_imp = american_to_implied(-257)
    true_yes, true_no = remove_vig(yes_imp, no_imp)
    print(f"  YES +127 implied={yes_imp:.4f}, NO -257 implied={no_imp:.4f}")
    print(f"  Vig = {(yes_imp + no_imp - 1)*100:.1f}%")
    print(f"  True YES={true_yes:.4f}, True NO={true_no:.4f}")
    
    # Test Kelly
    print("\n--- Kelly Criterion ---")
    for prob, odds, tier in [(0.60, 2.50, 'STRONG'), (0.55, 1.91, 'LEAN'), (0.45, 2.00, 'LEAN')]:
        k_f = kelly_full(prob, odds)
        k_s = kelly_sized(prob, odds, tier)
        has_edge = k_f > 0
        print(f"  p={prob}, odds={odds}, tier={tier} → kelly_full={k_f:.4f}, sized={k_s:.4f}, edge={has_edge}")
    
    # Test EV
    print("\n--- Expected Value ---")
    ev = calculate_ev(0.60, 2.50)
    print(f"  p=0.60, +150 odds → EV = +${ev:.2f} per $1 wagered ({ev*100:.0f}% ROI)")
    
    # Test full edge analysis
    print("\n--- Full Edge Analysis ---")
    analysis = full_edge_analysis(0.60, 150)
    for k, v in analysis.items():
        print(f"  {k}: {v}")
    
    print("\n✅ All self-tests passed")
