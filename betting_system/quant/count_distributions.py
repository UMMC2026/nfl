#!/usr/bin/env python3
"""
COUNT_DISTRIBUTIONS.PY — SOP v2.1 QUANT FRAMEWORK
==================================================
Proper probability distributions for count statistics.

KEY INSIGHT: Count stats (3PM, REB, AST, Blocks, etc.) are NOT normally
distributed. They are discrete count data with overdispersion.

Distribution Selection:
- Normal: PTS (high counts, CLT applies), PRA, combos
- Poisson: Low count stats with variance ≈ mean
- Negative Binomial: Count stats with variance > mean (overdispersed)

NBA Overdispersion Analysis (2025-26 calibration):
- 3PM: variance/mean ratio ≈ 1.4 → Negative Binomial
- REB: variance/mean ratio ≈ 1.3 → Negative Binomial  
- AST: variance/mean ratio ≈ 1.25 → Negative Binomial
- BLK: variance/mean ratio ≈ 1.6 → Negative Binomial
- STL: variance/mean ratio ≈ 1.5 → Negative Binomial
- PTS: high counts → Normal approximation OK

Version: 2.1.0
Created: 2026-02-04
"""

import math
from typing import Literal, Tuple
from scipy import stats as scipy_stats
from enum import Enum


class DistributionType(str, Enum):
    """Probability distribution types for different stats"""
    NORMAL = "normal"               # High count, continuous-like (PTS, combos)
    POISSON = "poisson"             # Low count, variance ≈ mean
    NEGATIVE_BINOMIAL = "nbinom"    # Count data with overdispersion
    

# Stat → Distribution mapping
# Based on calibration analysis of 459 picks
STAT_DISTRIBUTION_MAP = {
    # NBA Stats
    "3PM": DistributionType.NEGATIVE_BINOMIAL,
    "REB": DistributionType.NEGATIVE_BINOMIAL,
    "AST": DistributionType.NEGATIVE_BINOMIAL,
    "BLK": DistributionType.NEGATIVE_BINOMIAL,
    "STL": DistributionType.NEGATIVE_BINOMIAL,
    "PTS": DistributionType.NORMAL,
    "PRA": DistributionType.NORMAL,
    "PR": DistributionType.NORMAL,
    "PA": DistributionType.NORMAL,
    "RA": DistributionType.NORMAL,
    "PTS+REB": DistributionType.NORMAL,
    "PTS+AST": DistributionType.NORMAL,
    "REB+AST": DistributionType.NORMAL,
    "STOCKS": DistributionType.NEGATIVE_BINOMIAL,  # BLK+STL
    
    # NHL Stats
    "SOG": DistributionType.NEGATIVE_BINOMIAL,
    "GOALS": DistributionType.POISSON,
    "ASSISTS": DistributionType.POISSON,
    "POINTS": DistributionType.POISSON,
    "SAVES": DistributionType.NEGATIVE_BINOMIAL,
    "BLOCKS": DistributionType.NEGATIVE_BINOMIAL,
    "HITS": DistributionType.NEGATIVE_BINOMIAL,
    
    # Tennis Stats
    "ACES": DistributionType.NEGATIVE_BINOMIAL,
    "DOUBLE_FAULTS": DistributionType.POISSON,
    "GAMES": DistributionType.NORMAL,
    "SETS": DistributionType.POISSON,
    
    # Default
    "DEFAULT": DistributionType.NORMAL,
}

# Overdispersion factors by stat (variance/mean ratio from calibration)
OVERDISPERSION_FACTORS = {
    "3PM": 1.40,
    "REB": 1.30,
    "AST": 1.25,
    "BLK": 1.60,
    "STL": 1.50,
    "SOG": 1.35,
    "SAVES": 1.45,
    "BLOCKS": 1.40,
    "HITS": 1.55,
    "ACES": 1.50,
    "STOCKS": 1.55,
}


def get_distribution_type(stat: str) -> DistributionType:
    """Get the appropriate distribution type for a stat."""
    stat_upper = stat.upper().replace(" ", "_").replace("+", "_")
    return STAT_DISTRIBUTION_MAP.get(stat_upper, DistributionType.NORMAL)


def get_overdispersion(stat: str) -> float:
    """Get overdispersion factor for a stat (variance/mean ratio)."""
    stat_upper = stat.upper().replace(" ", "_").replace("+", "_")
    return OVERDISPERSION_FACTORS.get(stat_upper, 1.0)


# ============================================================================
# PROBABILITY CALCULATIONS
# ============================================================================

def normal_over_prob(mean: float, std: float, line: float) -> float:
    """
    Calculate P(X > line) using Normal distribution.
    
    For high-count stats where CLT applies.
    """
    if std <= 0:
        return 1.0 if mean > line else 0.0
    
    return 1.0 - scipy_stats.norm.cdf(line, mean, std)


def normal_under_prob(mean: float, std: float, line: float) -> float:
    """Calculate P(X < line) using Normal distribution."""
    if std <= 0:
        return 0.0 if mean > line else 1.0
    
    return scipy_stats.norm.cdf(line, mean, std)


def poisson_over_prob(lambda_val: float, line: float) -> float:
    """
    Calculate P(X > line) using Poisson distribution.
    
    For low count stats where variance ≈ mean.
    Lines are typically X.5, so P(X > 1.5) = P(X >= 2) = 1 - P(X <= 1)
    """
    if lambda_val <= 0:
        return 0.0
    
    k = int(math.ceil(line))
    prob_under = scipy_stats.poisson.cdf(k - 1, lambda_val)
    return 1.0 - prob_under


def poisson_under_prob(lambda_val: float, line: float) -> float:
    """Calculate P(X < line) using Poisson distribution."""
    if lambda_val <= 0:
        return 1.0
    
    k = int(math.floor(line))
    return scipy_stats.poisson.cdf(k, lambda_val)


def negative_binomial_over_prob(mean: float, variance: float, line: float) -> float:
    """
    Calculate P(X > line) using Negative Binomial for overdispersed counts.
    
    NB is appropriate when variance > mean (overdispersion).
    
    NB parameters:
        n = mean² / (variance - mean)
        p = mean / variance
    """
    if mean <= 0:
        return 0.0
    
    if variance <= mean:
        # Not overdispersed, fall back to Poisson
        return poisson_over_prob(mean, line)
    
    try:
        n = (mean ** 2) / (variance - mean)
        p = mean / variance
        
        k = int(math.ceil(line))
        prob_under = scipy_stats.nbinom.cdf(k - 1, n, p)
        return 1.0 - prob_under
    except (ValueError, ZeroDivisionError):
        # Fall back to Poisson on error
        return poisson_over_prob(mean, line)


def negative_binomial_under_prob(mean: float, variance: float, line: float) -> float:
    """Calculate P(X < line) using Negative Binomial."""
    if mean <= 0:
        return 1.0
    
    if variance <= mean:
        return poisson_under_prob(mean, line)
    
    try:
        n = (mean ** 2) / (variance - mean)
        p = mean / variance
        
        k = int(math.floor(line))
        return scipy_stats.nbinom.cdf(k, n, p)
    except (ValueError, ZeroDivisionError):
        return poisson_under_prob(mean, line)


# ============================================================================
# UNIFIED PROBABILITY CALCULATOR
# ============================================================================

def calculate_prop_probability(
    stat: str,
    mean: float,
    std: float,
    line: float,
    direction: Literal["higher", "lower", "over", "under"]
) -> Tuple[float, DistributionType]:
    """
    Calculate probability using the appropriate distribution for the stat type.
    
    Args:
        stat: Stat name (3PM, REB, PTS, etc.)
        mean: Player's average (mu)
        std: Standard deviation (sigma)
        line: Prop line
        direction: "higher"/"over" or "lower"/"under"
    
    Returns:
        (probability, distribution_type_used)
    """
    dist_type = get_distribution_type(stat)
    is_over = direction.lower() in ("higher", "over")
    
    # Calculate variance
    variance = std ** 2 if std > 0 else mean * get_overdispersion(stat)
    
    if dist_type == DistributionType.NORMAL:
        if is_over:
            prob = normal_over_prob(mean, std, line)
        else:
            prob = normal_under_prob(mean, std, line)
            
    elif dist_type == DistributionType.POISSON:
        if is_over:
            prob = poisson_over_prob(mean, line)
        else:
            prob = poisson_under_prob(mean, line)
            
    elif dist_type == DistributionType.NEGATIVE_BINOMIAL:
        # Use overdispersion factor if variance seems too low
        overdispersion = get_overdispersion(stat)
        actual_variance = max(variance, mean * overdispersion)
        
        if is_over:
            prob = negative_binomial_over_prob(mean, actual_variance, line)
        else:
            prob = negative_binomial_under_prob(mean, actual_variance, line)
    else:
        # Default to normal
        if is_over:
            prob = normal_over_prob(mean, std, line)
        else:
            prob = normal_under_prob(mean, std, line)
    
    return (round(prob, 4), dist_type)


# ============================================================================
# QUICK LOOKUP
# ============================================================================

def get_stat_distribution_info(stat: str) -> dict:
    """Get distribution info for a stat for debugging/display."""
    dist_type = get_distribution_type(stat)
    overdispersion = get_overdispersion(stat)
    
    return {
        "stat": stat,
        "distribution": dist_type.value,
        "overdispersion": overdispersion,
        "notes": _get_stat_notes(stat, dist_type)
    }


def _get_stat_notes(stat: str, dist_type: DistributionType) -> str:
    """Get human-readable notes about the distribution choice."""
    if dist_type == DistributionType.NEGATIVE_BINOMIAL:
        return f"Count stat with overdispersion - heavier tails than Poisson"
    elif dist_type == DistributionType.POISSON:
        return f"Low count stat with variance ≈ mean"
    else:
        return f"High count stat - normal approximation valid"


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test the distribution calculations
    print("=" * 60)
    print("COUNT DISTRIBUTIONS TEST")
    print("=" * 60)
    
    # Test cases: (stat, mean, std, line, direction)
    test_cases = [
        ("3PM", 2.5, 1.5, 2.5, "higher"),   # NB - 3-pointers
        ("3PM", 2.5, 1.5, 2.5, "lower"),
        ("REB", 8.0, 3.0, 7.5, "higher"),   # NB - rebounds
        ("AST", 6.0, 2.0, 5.5, "higher"),   # NB - assists
        ("PTS", 25.0, 6.0, 24.5, "higher"), # Normal - points
        ("GOALS", 0.35, 0.5, 0.5, "higher"),# Poisson - goals
    ]
    
    print(f"\n{'Stat':<8} {'Mean':>6} {'Std':>5} {'Line':>6} {'Dir':<6} {'Dist':<10} {'Prob':>7}")
    print("-" * 60)
    
    for stat, mean, std, line, direction in test_cases:
        prob, dist = calculate_prop_probability(stat, mean, std, line, direction)
        print(f"{stat:<8} {mean:>6.1f} {std:>5.1f} {line:>6.1f} {direction:<6} {dist.value:<10} {prob*100:>6.1f}%")
    
    print("\n✅ Distribution tests complete")
