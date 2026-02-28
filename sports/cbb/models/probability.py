"""
CBB Probability Model

UPGRADED: Now uses Negative Binomial distribution instead of Poisson.
Negative Binomial handles over-dispersion (variance > mean) common in CBB.

Why Negative Binomial?
- Poisson assumes variance = mean (fails for CBB's 60-120 point range)
- Negative Binomial has two parameters (r, p) to fit over-dispersed data
- Better calibration for blowout games and high-variance scenarios

Phase 5B Upgrade: 2026-02-05
"""
from typing import Dict, Tuple, Optional
import math
from dataclasses import dataclass

# Try to import scipy for Negative Binomial
try:
    from scipy.stats import nbinom, poisson as scipy_poisson
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class ProbabilityResult:
    """Result of probability computation"""
    probability: float
    confidence: float
    model_used: str
    capped: bool = False
    cap_reason: Optional[str] = None
    # New fields for Negative Binomial
    dispersion_detected: bool = False
    r_parameter: Optional[float] = None
    p_parameter: Optional[float] = None


def compute_probability(
    stat: str,
    line: float,
    direction: str,
    player_mean: float,
    player_std: float,
    sample_size: int,
    game_context: Optional[Dict] = None
) -> ProbabilityResult:
    """
    Compute probability of hitting a line.
    
    UPGRADED: Uses Negative Binomial when over-dispersion detected.
    Falls back to Poisson when variance ≈ mean.
    
    Args:
        stat: Stat type (points, rebounds, assists, etc.)
        line: The betting line value
        direction: "higher" or "lower"
        player_mean: Player's historical mean for this stat
        player_std: Player's historical standard deviation
        sample_size: Number of games in sample
        game_context: Optional game context for adjustments
        
    Returns:
        ProbabilityResult with probability and metadata
    """
    from sports.cbb.config import CONFIDENCE_CAPS, CBB_EDGE_GATES
    
    # Apply game context adjustments
    adjusted_mean = player_mean
    if game_context:
        adjusted_mean = apply_context_adjustments(player_mean, game_context)
    
    # Detect over-dispersion: variance > mean
    variance = player_std ** 2
    dispersion_ratio = variance / adjusted_mean if adjusted_mean > 0 else 1.0
    
    # Use Negative Binomial if over-dispersed (ratio > 1.2)
    # This is common in CBB due to blowouts
    dispersion_detected = dispersion_ratio > 1.2
    r_param = None
    p_param = None
    
    if dispersion_detected and SCIPY_AVAILABLE:
        # Negative Binomial parameters:
        # mean = r * (1-p) / p
        # variance = r * (1-p) / p^2
        # Solve for r and p given mean and variance
        r_param, p_param = fit_negative_binomial(adjusted_mean, variance)
        raw_prob = negative_binomial_probability(r_param, p_param, line, direction)
        model_used = "negative_binomial"
    else:
        # Fall back to Poisson for well-behaved data
        raw_prob = poisson_probability(adjusted_mean, line, direction)
        model_used = "poisson"
    
    # Apply variance penalty (stricter for CBB)
    capped = False
    cap_reason = None
    
    if player_std > player_mean * CBB_EDGE_GATES.variance_penalty_factor:
        max_conf = CBB_EDGE_GATES.variance_confidence_cap
        if raw_prob > max_conf:
            raw_prob = max_conf
            capped = True
            cap_reason = "HIGH_VARIANCE"
    
    # Apply stat class cap
    stat_class = get_stat_class(stat)
    stat_cap = CONFIDENCE_CAPS.get(stat_class, 0.65)
    if raw_prob > stat_cap:
        raw_prob = stat_cap
        capped = True
        cap_reason = cap_reason or f"STAT_CLASS_CAP ({stat_class})"
    
    # Compute confidence based on sample size
    confidence = compute_confidence(sample_size, player_std)
    
    return ProbabilityResult(
        probability=round(raw_prob, 4),
        confidence=round(confidence, 4),
        model_used=model_used,
        capped=capped,
        cap_reason=cap_reason,
        dispersion_detected=dispersion_detected,
        r_parameter=r_param,
        p_parameter=p_param,
    )


def fit_negative_binomial(mean: float, variance: float) -> Tuple[float, float]:
    """
    Fit Negative Binomial parameters from mean and variance.
    
    For Negative Binomial:
        mean = r * (1-p) / p
        variance = r * (1-p) / p^2
    
    Solving:
        p = mean / variance
        r = mean * p / (1 - p)
    
    Returns:
        Tuple of (r, p) parameters
    """
    if variance <= mean or mean <= 0:
        # Not over-dispersed, return parameters that approximate Poisson
        return (mean, 0.5)
    
    # Solve for p: p = mean / variance
    p = mean / variance
    p = max(0.01, min(0.99, p))  # Clamp to valid range
    
    # Solve for r: r = mean * p / (1 - p)
    r = mean * p / (1 - p)
    r = max(0.5, min(100, r))  # Clamp to reasonable range
    
    return (r, p)


def negative_binomial_probability(r: float, p: float, line: float, direction: str) -> float:
    """
    Compute probability using Negative Binomial distribution.
    
    Uses scipy.stats.nbinom for accurate CDF computation.
    
    Args:
        r: Dispersion parameter (number of successes)
        p: Success probability per trial
        line: The betting line
        direction: "higher" or "lower"
    
    Returns:
        Probability of hitting the line
    """
    if not SCIPY_AVAILABLE:
        # Fall back to Poisson approximation
        mean = r * (1 - p) / p if p > 0 else r
        return poisson_probability(mean, line, direction)
    
    if direction.lower() in ("higher", "over"):
        # P(X > line) = 1 - P(X <= floor(line))
        target = int(math.floor(line))
        prob = 1 - nbinom.cdf(target, r, p)
    else:
        # P(X < line) = P(X <= ceil(line) - 1)
        target = int(math.ceil(line)) - 1
        prob = nbinom.cdf(target, r, p)
    
    return max(0.0, min(1.0, prob))


def poisson_probability(mean: float, line: float, direction: str) -> float:
    """
    Compute probability using Poisson distribution.
    
    P(X >= k) = 1 - P(X < k) for "higher"
    P(X <= k) = P(X < k+1) for "lower"
    """
    if mean <= 0:
        return 0.5  # No data, return neutral
    
    # For "higher", we want P(X > line) = P(X >= line + 0.5) for continuous
    # For "lower", we want P(X < line) = P(X <= line - 0.5)
    
    if direction == "higher":
        # P(X > line) ≈ 1 - CDF(line)
        target = math.floor(line)
        prob = 1 - poisson_cdf(mean, target)
    else:
        # P(X < line) ≈ CDF(line - 1)
        target = math.ceil(line) - 1
        prob = poisson_cdf(mean, target)
    
    return max(0.0, min(1.0, prob))


def poisson_cdf(mean: float, k: int) -> float:
    """Compute Poisson CDF: P(X <= k)"""
    if k < 0:
        return 0.0
    
    total = 0.0
    for i in range(k + 1):
        total += poisson_pmf(mean, i)
    
    return min(1.0, total)


def poisson_pmf(mean: float, k: int) -> float:
    """Compute Poisson PMF: P(X = k)"""
    if k < 0 or mean <= 0:
        return 0.0
    
    # P(X=k) = (e^-λ * λ^k) / k!
    return math.exp(-mean) * (mean ** k) / math.factorial(k)


def apply_context_adjustments(base_mean: float, context: Dict) -> float:
    """Apply game context adjustments to player mean."""
    adjusted = base_mean
    
    # Pace adjustment
    if "pace_factor" in context:
        adjusted *= context["pace_factor"]
    
    # Defense adjustment
    if "defensive_factor" in context:
        adjusted *= (2 - context["defensive_factor"])  # Inverse for offense
    
    # Conference game adjustment (more predictable)
    if context.get("is_conference_game"):
        # Slightly reduce variance expectation
        pass
    
    # Back-to-back penalty
    if context.get("is_back_to_back"):
        adjusted *= 0.95
    
    return adjusted


def compute_confidence(sample_size: int, std: float) -> float:
    """
    Compute confidence score based on sample quality.
    
    Factors:
    - Sample size (more games = higher confidence)
    - Standard deviation (lower variance = higher confidence)
    """
    # Sample size component (max out at ~20 games)
    size_factor = min(sample_size / 20, 1.0)
    
    # Variance component (assume mean of 15 as baseline)
    variance_factor = max(0.5, 1 - (std / 15))
    
    return (size_factor * 0.6 + variance_factor * 0.4)


def get_stat_class(stat: str) -> str:
    """Map stat to confidence cap class."""
    core_stats = {"points", "rebounds", "assists"}
    volume_stats = {"fga", "fta", "fg3a", "minutes"}
    
    if stat.lower() in core_stats:
        return "core"
    elif stat.lower() in volume_stats:
        return "volume_micro"
    else:
        return "event_binary"
