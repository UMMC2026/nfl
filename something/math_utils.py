"""
FUOOM DARK MATTER - Math Utilities
===================================
Foundation module for all probability, Kelly, and EV calculations.

This module eliminates hardcoded values and implements dynamic calculation
per the System Stability Audit findings.

Version: 1.0.0
Date: February 9, 2026
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# TIER THRESHOLDS (SOP v2.1 - TRUTH ENFORCED)
# =============================================================================
# CRITICAL: These are the ONLY valid thresholds. v2.0 thresholds are DELETED.

class Tier(Enum):
    SLAM = "SLAM"
    STRONG = "STRONG"
    LEAN = "LEAN"
    NO_PLAY = "NO_PLAY"


TIER_THRESHOLDS = {
    Tier.SLAM: 0.75,      # >= 75% (was 90% in v2.0 - DELETED)
    Tier.STRONG: 0.65,    # >= 65% (was 80% in v2.0 - DELETED)
    Tier.LEAN: 0.55,      # >= 55% (was 70% in v2.0 - DELETED)
    Tier.NO_PLAY: 0.00,   # < 55%
}


def probability_to_tier(probability: float) -> Tier:
    """
    Convert probability to tier using SOP v2.1 thresholds.
    
    Args:
        probability: Model probability (0.0 to 1.0)
        
    Returns:
        Tier enum value
        
    Raises:
        ValueError: If probability is outside valid range
    """
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"Probability must be 0-1, got {probability}")
    
    if probability >= TIER_THRESHOLDS[Tier.SLAM]:
        return Tier.SLAM
    elif probability >= TIER_THRESHOLDS[Tier.STRONG]:
        return Tier.STRONG
    elif probability >= TIER_THRESHOLDS[Tier.LEAN]:
        return Tier.LEAN
    else:
        return Tier.NO_PLAY


def validate_tier_probability_alignment(tier: str, probability: float) -> Tuple[bool, str]:
    """
    Check if tier label matches probability value.
    
    This is a HARD GATE - misalignment is an SOP violation.
    
    Args:
        tier: Tier label string
        probability: Model probability
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    expected_tier = probability_to_tier(probability)
    
    try:
        actual_tier = Tier(tier.upper())
    except ValueError:
        return False, f"Invalid tier label: {tier}"
    
    if actual_tier != expected_tier:
        return False, (
            f"Tier-probability mismatch: {tier} assigned but probability "
            f"{probability:.1%} requires {expected_tier.value}"
        )
    
    return True, "PASSED"


# =============================================================================
# ODDS CONVERSION
# =============================================================================

def american_to_implied(odds: int) -> float:
    """
    Convert American odds to implied probability (includes vig).
    
    Args:
        odds: American odds (e.g., +150, -110)
        
    Returns:
        Implied probability (0.0 to 1.0)
        
    Examples:
        >>> american_to_implied(+150)
        0.4
        >>> american_to_implied(-150)
        0.6
    """
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def american_to_decimal(odds: int) -> float:
    """
    Convert American odds to decimal odds.
    
    Args:
        odds: American odds
        
    Returns:
        Decimal odds (e.g., 2.50 for +150)
        
    Examples:
        >>> american_to_decimal(+150)
        2.5
        >>> american_to_decimal(-150)
        1.6667
    """
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1


def decimal_to_american(decimal_odds: float) -> int:
    """
    Convert decimal odds to American odds.
    
    Args:
        decimal_odds: Decimal odds (e.g., 2.50)
        
    Returns:
        American odds (e.g., +150)
    """
    if decimal_odds >= 2.0:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))


def remove_vig(prob_a: float, prob_b: float) -> Tuple[float, float]:
    """
    Remove vigorish to get true implied probabilities.
    
    Args:
        prob_a: Implied probability for side A
        prob_b: Implied probability for side B
        
    Returns:
        Tuple of (true_prob_a, true_prob_b)
        
    Example:
        >>> # YES +127 (44.1%), NO -257 (72.0%)
        >>> remove_vig(0.441, 0.720)
        (0.380, 0.620)
    """
    total = prob_a + prob_b
    return prob_a / total, prob_b / total


def calculate_vig(prob_a: float, prob_b: float) -> float:
    """
    Calculate the vigorish (overround) in a market.
    
    Args:
        prob_a: Implied probability for side A
        prob_b: Implied probability for side B
        
    Returns:
        Vig as a percentage (e.g., 0.05 for 5% vig)
    """
    return (prob_a + prob_b) - 1.0


# =============================================================================
# EDGE & EXPECTED VALUE
# =============================================================================

def calculate_edge(model_prob: float, implied_prob: float) -> float:
    """
    Calculate edge as probability difference.
    
    Args:
        model_prob: Model's probability estimate
        implied_prob: Market implied probability (after removing vig)
        
    Returns:
        Edge (positive = value, negative = no value)
    """
    return model_prob - implied_prob


def calculate_ev(model_prob: float, decimal_odds: float) -> float:
    """
    Calculate Expected Value per unit wagered.
    
    This is the CORRECT way to size bets - not just probability difference.
    
    Args:
        model_prob: Model's probability of winning
        decimal_odds: Decimal odds for the bet
        
    Returns:
        Expected Value (e.g., +0.50 means +$0.50 per $1 wagered)
        
    Example:
        >>> # Model says 60% chance, odds are +150 (2.50 decimal)
        >>> calculate_ev(0.60, 2.50)
        0.50  # +50% ROI expected
    """
    win_return = model_prob * (decimal_odds - 1)
    loss_cost = (1 - model_prob) * 1.0
    return win_return - loss_cost


# =============================================================================
# KELLY CRITERION
# =============================================================================

# Kelly fraction multipliers by tier (fractional Kelly to reduce variance)
KELLY_FRACTIONS = {
    Tier.SLAM: 0.40,      # Most aggressive allowed
    Tier.STRONG: 0.30,
    Tier.LEAN: 0.20,
    Tier.NO_PLAY: 0.00,   # NEVER bet
}

# Absolute maximum bet size as fraction of bankroll
MAX_KELLY_CAP = 0.05  # 5% of bankroll maximum


@dataclass
class KellyResult:
    """Result of Kelly criterion calculation."""
    kelly_full: float           # Full Kelly fraction
    kelly_fractional: float     # Tier-adjusted Kelly
    kelly_capped: float         # Final capped Kelly
    has_edge: bool              # Whether positive edge exists
    error_message: Optional[str] = None


def calculate_kelly(
    model_prob: float,
    decimal_odds: float,
    tier: Tier = Tier.LEAN
) -> KellyResult:
    """
    Calculate Kelly criterion for optimal bet sizing.
    
    CRITICAL: Negative Kelly means NO EDGE. These picks must be excluded.
    
    Args:
        model_prob: Model's probability of winning (0.0 to 1.0)
        decimal_odds: Decimal odds for the bet
        tier: Confidence tier for fractional Kelly selection
        
    Returns:
        KellyResult with full, fractional, and capped Kelly values
        
    Formula:
        kelly_full = (b * p - q) / b
        where:
            b = decimal_odds - 1 (net payout per unit)
            p = probability of winning
            q = 1 - p (probability of losing)
    
    Example:
        >>> # 60% win probability at +150 odds (2.50 decimal)
        >>> result = calculate_kelly(0.60, 2.50, Tier.STRONG)
        >>> result.kelly_full
        0.333  # 33.3% of bankroll (full Kelly - too aggressive)
        >>> result.kelly_capped
        0.05   # Capped at 5% max
    """
    # Validate inputs
    if not 0.0 < model_prob < 1.0:
        return KellyResult(
            kelly_full=0.0,
            kelly_fractional=0.0,
            kelly_capped=0.0,
            has_edge=False,
            error_message=f"Invalid probability: {model_prob}"
        )
    
    if decimal_odds <= 1.0:
        return KellyResult(
            kelly_full=0.0,
            kelly_fractional=0.0,
            kelly_capped=0.0,
            has_edge=False,
            error_message=f"Invalid decimal odds: {decimal_odds}"
        )
    
    # Calculate Kelly components
    b = decimal_odds - 1  # Net payout per unit wagered
    p = model_prob
    q = 1 - p
    
    # Full Kelly formula
    kelly_full = (b * p - q) / b
    
    # Check for edge
    if kelly_full <= 0:
        return KellyResult(
            kelly_full=kelly_full,
            kelly_fractional=0.0,
            kelly_capped=0.0,
            has_edge=False,
            error_message=f"No mathematical edge: Kelly = {kelly_full:.4f}"
        )
    
    # Apply fractional Kelly based on tier
    fraction = KELLY_FRACTIONS.get(tier, 0.20)
    kelly_fractional = kelly_full * fraction
    
    # Apply absolute cap
    kelly_capped = min(kelly_fractional, MAX_KELLY_CAP)
    
    return KellyResult(
        kelly_full=kelly_full,
        kelly_fractional=kelly_fractional,
        kelly_capped=kelly_capped,
        has_edge=True
    )


def validate_kelly_edge(model_prob: float, decimal_odds: float) -> Tuple[bool, str]:
    """
    Validate that a pick has positive Kelly (mathematical edge).
    
    This is a HARD GATE. Negative Kelly = MUST EXCLUDE.
    
    Args:
        model_prob: Model probability
        decimal_odds: Decimal odds
        
    Returns:
        Tuple of (has_edge, message)
    """
    result = calculate_kelly(model_prob, decimal_odds)
    
    if not result.has_edge:
        return False, result.error_message or "No edge detected"
    
    return True, f"Kelly = {result.kelly_full:.4f} (edge exists)"


# =============================================================================
# SIGMA TABLE (Sport-specific standard deviations)
# =============================================================================

SIGMA_TABLE = {
    'NBA': {
        'points': 5.8,
        'rebounds': 2.9,
        'assists': 2.4,
        'threes': 1.3,
        'steals': 0.9,
        'blocks': 0.8,
        'pts+reb': 7.2,
        'pts+ast': 6.8,
        'reb+ast': 4.0,
        'pts+reb+ast': 8.5,
        'team_total': 11.5,
        'spread': 10.8,
    },
    'NFL': {
        'pass_yards': 65.0,
        'rush_yards': 28.0,
        'receiving_yards': 32.0,
        'receptions': 2.5,
        'pass_tds': 0.9,
        'rush_tds': 0.6,
        'rec_tds': 0.5,
        'completions': 5.5,
        'pass_attempts': 6.0,
        'team_total': 10.2,
        'spread': 13.5,
    },
    'CBB': {
        'points': 6.5,
        'rebounds': 3.2,
        'assists': 2.1,
        'team_total': 10.0,
        'spread': 11.0,
    },
    'TENNIS': {
        'aces': 3.5,
        'double_faults': 1.8,
        'games_won': 4.2,
        'sets': 0.8,
    },
    'GOLF': {
        'strokes': 3.2,
        'birdies': 2.1,
        'bogeys': 2.3,
    },
}


def get_sigma(sport: str, stat: str) -> float:
    """
    Get standard deviation for a sport/stat combination.
    
    Args:
        sport: Sport code (NBA, NFL, etc.)
        stat: Stat type (points, rebounds, etc.)
        
    Returns:
        Standard deviation value
        
    Raises:
        ValueError: If sport/stat combination not found
    """
    sport_upper = sport.upper()
    stat_lower = stat.lower()
    
    if sport_upper not in SIGMA_TABLE:
        raise ValueError(f"Unknown sport: {sport}")
    
    if stat_lower not in SIGMA_TABLE[sport_upper]:
        raise ValueError(f"Unknown stat for {sport}: {stat}")
    
    return SIGMA_TABLE[sport_upper][stat_lower]


def compression_check(
    projection: float,
    line: float,
    sport: str,
    stat: str,
    raw_confidence: float
) -> float:
    """
    Apply confidence compression for extreme deviations (SOP Rule C1).
    
    If |projection - line| > 2.5 × sigma, cap confidence at 65%.
    
    Args:
        projection: Model projection
        line: Market line
        sport: Sport code
        stat: Stat type
        raw_confidence: Uncapped confidence
        
    Returns:
        Compressed confidence (capped at 0.65 if deviation too large)
    """
    try:
        sigma = get_sigma(sport, stat)
    except ValueError:
        # If we don't have sigma data, apply conservative cap
        return min(raw_confidence, 0.65)
    
    deviation = abs(projection - line) / sigma
    
    if deviation > 2.5:
        return min(0.65, raw_confidence)
    
    return raw_confidence


# =============================================================================
# BRIER SCORE CALIBRATION
# =============================================================================

BRIER_THRESHOLDS = {
    'NBA': {
        'props': 0.18,
        'spreads': 0.20,
        'totals': 0.20,
    },
    'NFL': {
        'spreads': 0.22,
        'totals': 0.20,
        'props': 0.20,
    },
    'GOLF': {
        'winner': 0.05,  # Low base rate
    },
}


def calculate_brier_score(predictions: list, outcomes: list) -> float:
    """
    Calculate Brier score for calibration assessment.
    
    Brier = (1/N) * sum((predicted - actual)^2)
    
    Interpretation:
        0.00 = Perfect calibration
        0.25 = Coin flip (predicting 0.50 for everything)
        > 0.25 = Worse than random
    
    Args:
        predictions: List of predicted probabilities
        outcomes: List of actual outcomes (0 or 1)
        
    Returns:
        Brier score
    """
    if len(predictions) != len(outcomes):
        raise ValueError("Predictions and outcomes must have same length")
    
    n = len(predictions)
    if n == 0:
        return 0.0
    
    squared_errors = [(p - o) ** 2 for p, o in zip(predictions, outcomes)]
    return sum(squared_errors) / n


def is_calibration_acceptable(
    brier_score: float,
    sport: str,
    market_type: str
) -> Tuple[bool, str]:
    """
    Check if calibration meets sport/market-specific threshold.
    
    Args:
        brier_score: Calculated Brier score
        sport: Sport code
        market_type: Market type (props, spreads, etc.)
        
    Returns:
        Tuple of (is_acceptable, message)
    """
    sport_upper = sport.upper()
    
    if sport_upper not in BRIER_THRESHOLDS:
        threshold = 0.20  # Default
    elif market_type not in BRIER_THRESHOLDS[sport_upper]:
        threshold = 0.20
    else:
        threshold = BRIER_THRESHOLDS[sport_upper][market_type]
    
    if brier_score > threshold:
        return False, f"Brier {brier_score:.3f} exceeds threshold {threshold}"
    
    return True, f"Calibration acceptable: {brier_score:.3f} < {threshold}"


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

__all__ = [
    # Tiers
    'Tier',
    'TIER_THRESHOLDS',
    'probability_to_tier',
    'validate_tier_probability_alignment',
    
    # Odds
    'american_to_implied',
    'american_to_decimal',
    'decimal_to_american',
    'remove_vig',
    'calculate_vig',
    
    # Edge & EV
    'calculate_edge',
    'calculate_ev',
    
    # Kelly
    'KellyResult',
    'KELLY_FRACTIONS',
    'MAX_KELLY_CAP',
    'calculate_kelly',
    'validate_kelly_edge',
    
    # Sigma & Compression
    'SIGMA_TABLE',
    'get_sigma',
    'compression_check',
    
    # Calibration
    'BRIER_THRESHOLDS',
    'calculate_brier_score',
    'is_calibration_acceptable',
]
