"""
SOCCER ENGINE PATCH v1.0
=========================

CRITICAL FIX: Standardize Soccer to stat-centric probability calculation.

CURRENT STATE (WRONG for governance):
- z_score = (line - mean) / std  ← Line-anchored (inverted)
- Breaks ESS comparability
- Breaks FAS attribution
- Conceptually inconsistent with NBA/CBB/NFL

NEW STATE (CORRECT):
- Keep Poisson/Normal CDF math (it's correct)
- Use stat-centric mental model in documentation
- Adapter already handles conversion to UGO

NOTE: The MATH is actually correct (Poisson CDF doesn't care about order).
The issue is CONCEPTUAL — we need consistent language across sports.

SOLUTION:
1. Keep probability calculations as-is (they're mathematically sound)
2. Add clear documentation that mean/lambda is the anchor
3. Adapter handles UGO conversion with proper edge_std
4. This is a SEMANTIC fix, not a math fix
"""

from typing import Tuple
import scipy.stats as scipy_stats


def calculate_poisson_probability_stat_centric(
    mu: float,  # Player's expected stat (ANCHOR)
    line: float,  # Prop line (MEASUREMENT)
) -> Tuple[float, float]:
    """
    Calculate P(X > line) and P(X < line) using Poisson distribution.
    
    STAT-CENTRIC INTERPRETATION:
    - mu (lambda): Player's true rate (the anchor)
    - line: Prop line from book (what we're measuring against)
    - Return: Probability player EXCEEDS line, probability player UNDER line
    
    Example:
        Player averages 3.2 shots on target per match (mu = 3.2)
        Book sets line at 2.5
        edge_std = (3.2 - 2.5) / sqrt(3.2) = 0.39 (weak edge)
        P(over 2.5) ≈ 61%
    
    This is mathematically identical to old calculation, but conceptually
    aligned with NBA/CBB stat-centric approach.
    """
    if mu <= 0:
        return 0.5, 0.5
    
    # Poisson CDF: P(X <= k) where k = floor(line) for integer stats
    # P(X > line) = 1 - P(X <= floor(line))
    
    if line != int(line):
        # Half-line (e.g., 2.5): P(over) = P(X >= 3)
        k = int(line)
        prob_under = scipy_stats.poisson.cdf(k, mu)
        prob_over = 1 - prob_under
    else:
        # Integer line: P(over) = P(X > line) = 1 - P(X <= line)
        prob_under = scipy_stats.poisson.cdf(line, mu)
        prob_over = 1 - prob_under
    
    return prob_over, prob_under


def calculate_normal_probability_stat_centric(
    mu: float,     # Player's expected stat (ANCHOR)
    sigma: float,  # Standard deviation (UNCERTAINTY)
    line: float,   # Prop line (MEASUREMENT)
) -> Tuple[float, float]:
    """
    Calculate probabilities using normal distribution.
    
    STAT-CENTRIC INTERPRETATION:
    - mu: Player's true average (the anchor)
    - sigma: Player's consistency (lower = more stable)
    - line: Prop line from book (what we're measuring against)
    - edge_std (z-score): (mu - line) / sigma
    
    Example:
        Player averages 45.2 passes per match (mu = 45.2)
        With std dev of 8.3 (sigma = 8.3)
        Book sets line at 42.5
        edge_std = (45.2 - 42.5) / 8.3 = 0.33 (weak-moderate edge)
        P(over 42.5) ≈ 63%
    
    This is the SAME math as before, just with consistent terminology.
    """
    if sigma <= 0:
        sigma = mu * 0.3  # Assume 30% CV if unknown
    
    # Normal CDF: P(X <= x)
    # z = (x - mu) / sigma
    # P(X > line) = 1 - P(X <= line) = 1 - CDF((line - mu) / sigma)
    
    z_score = (line - mu) / sigma
    prob_under = scipy_stats.norm.cdf(z_score)
    prob_over = 1 - prob_under
    
    return prob_over, prob_under


def calculate_edge_std_soccer(
    mu: float,     # Expected stat
    sigma: float,  # Standard deviation (or sqrt(mu) for Poisson)
    line: float,   # Prop line
) -> float:
    """
    Calculate universal edge z-score for soccer props.
    
    For Poisson stats (goals, shots, tackles):
        sigma = sqrt(mu)  # Poisson variance = mean
    
    For Normal stats (passes, touches):
        sigma = empirical std dev or mu * CV
    
    Returns:
        edge_std: (mu - line) / sigma
    """
    if sigma <= 0:
        sigma = mu ** 0.5 if mu > 0 else 1.0
    
    return (mu - line) / sigma


# =============================================================================
# BACKWARD COMPATIBILITY WRAPPERS
# =============================================================================
# Keep old function names but redirect to stat-centric versions

def calculate_poisson_probability(mean: float, line: float) -> Tuple[float, float]:
    """Legacy wrapper — redirects to stat-centric version."""
    return calculate_poisson_probability_stat_centric(mean, line)


def calculate_normal_probability(mean: float, std: float, line: float) -> Tuple[float, float]:
    """Legacy wrapper — redirects to stat-centric version."""
    return calculate_normal_probability_stat_centric(mean, std, line)


# =============================================================================
# DOCUMENTATION
# =============================================================================

SOCCER_STAT_CENTRIC_GUIDE = """
SOCCER PROBABILITY CALCULATION — STAT-CENTRIC APPROACH
=======================================================

BEFORE (Line-Anchored Language):
- "Will player hit 2.5 shots?"
- z_score = (line - mean) / std  ← Inverted
- Line is reference, stat is variable

AFTER (Stat-Anchored Language):
- "Player averages 3.2 shots with σ=1.8"
- "Line 2.5 is 0.39σ below projection"
- edge_std = (mu - line) / sigma = 0.39
- Stat is anchor, line is opportunity

MATHEMATICAL EQUIVALENCE:
Both approaches produce IDENTICAL probabilities.
The difference is CONCEPTUAL alignment with NBA/CBB/NFL.

WHY THIS MATTERS:
1. ESS (Edge Stability Score) requires consistent edge_std across sports
2. FAS (Failure Attribution Schema) needs stat as anchor for variance analysis
3. Portfolio optimization needs apples-to-apples z-scores
4. Mental model consistency reduces cognitive load

EXAMPLE CALCULATION:

Player: Mohamed Salah
Stat: Shots on Target
Historical: 3.2 SOT/game over last 10 matches
Variance: Poisson (σ = sqrt(3.2) = 1.79)
Prop Line: 2.5

Stat-Centric:
  mu = 3.2 (anchor)
  line = 2.5 (measurement)
  edge_std = (3.2 - 2.5) / 1.79 = 0.39
  
  Interpretation: Line is 0.39 standard deviations below player's average.
                  Weak edge, but positive.
  
  P(over 2.5) = 1 - Poisson.cdf(2, 3.2) ≈ 61%

This is identical to old calculation, but language aligns with NBA system.
"""

if __name__ == "__main__":
    print(SOCCER_STAT_CENTRIC_GUIDE)
    
    # Example
    mu = 3.2  # Salah averages 3.2 SOT
    line = 2.5
    sigma = mu ** 0.5  # Poisson variance
    
    prob_over, prob_under = calculate_poisson_probability_stat_centric(mu, line)
    edge_std = calculate_edge_std_soccer(mu, sigma, line)
    
    print(f"\n📊 EXAMPLE:")
    print(f"   Player Avg (mu): {mu:.1f} SOT")
    print(f"   Prop Line: {line:.1f}")
    print(f"   Edge Z-Score: {edge_std:.2f}")
    print(f"   P(over): {prob_over:.1%}")
    print(f"   P(under): {prob_under:.1%}")
    print(f"\n   ✅ Player averages {mu - line:.1f} above line")
    print(f"   ✅ This is {edge_std:.2f} standard deviations")
