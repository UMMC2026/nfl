"""
CBB Distribution Detection — Over-Dispersion Aware Model Selection

Replaces blind Poisson with dispersion-aware distribution selection.
If variance >> mean → Negative Binomial (wider tails, lower confidence).
If variance ≈ mean  → Poisson (standard count model).
If variance << mean  → Under-dispersed Poisson (flag but allow).

This module is called by the hybrid_probability_router in cbb_main.py
and provides richer distribution metadata for downstream scoring.

Implementation Date: 2026-02-14
"""

import math
from typing import Tuple, Dict, List, Optional


# ---------------------------------------------------------------------------
# Dispersion thresholds
# ---------------------------------------------------------------------------
OVERDISPERSION_THRESHOLD = 1.20   # var/mean > 1.2 → NegBin
UNDERDISPERSION_THRESHOLD = 0.80  # var/mean < 0.8 → flagged Poisson

# Stat-specific dispersion priors (from CBB empirical analysis)
# Some stats are *expected* to be overdispersed — don't penalize them
STAT_DISPERSION_PRIORS: Dict[str, str] = {
    "points":   "OVERDISPERSED",    # Scoring is game-script dependent
    "pra":      "OVERDISPERSED",    # Combo stat — inherently high variance
    "pts+reb":  "OVERDISPERSED",
    "pts+ast":  "OVERDISPERSED",
    "rebounds":  "MODERATE",         # Boards are somewhat stable
    "assists":   "MODERATE",         # Playmaking is context-dependent
    "3pm":       "OVERDISPERSED",    # Binary-ish at low counts
    "reb+ast":   "MODERATE",
    "steals":    "OVERDISPERSED",    # Low-count, highly variable
    "blocks":    "OVERDISPERSED",    # Low-count, highly variable
    "turnovers": "MODERATE",
}


def detect_dispersion(
    values: List[float],
    stat_type: str = "points",
) -> Tuple[float, float, float, str]:
    """
    Detect if a player's stat distribution is over-dispersed.

    Parameters
    ----------
    values : list of float
        Observed game-level values for the stat.
    stat_type : str
        Stat name (for prior lookup).

    Returns
    -------
    (mean, variance, dispersion_ratio, distribution_type)

    distribution_type is one of:
        NEGATIVE_BINOMIAL         — var >> mean, use NegBin
        POISSON                   — var ≈ mean, standard model
        POISSON_UNDERDISPERSED    — var << mean (flag)
        POISSON_LOW_SAMPLE        — <5 games, default to Poisson
        ZERO_MEAN                 — player averages 0
    """
    if not values or len(values) < 2:
        m = values[0] if values else 0
        return m, m, 1.0, "POISSON_LOW_SAMPLE"

    n = len(values)
    mean = sum(values) / n

    if mean <= 0:
        return 0.0, 0.0, 1.0, "ZERO_MEAN"

    # Sample variance (ddof=1)
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    dispersion_ratio = variance / mean

    if n < 5:
        return mean, variance, dispersion_ratio, "POISSON_LOW_SAMPLE"

    if dispersion_ratio > OVERDISPERSION_THRESHOLD:
        return mean, variance, dispersion_ratio, "NEGATIVE_BINOMIAL"
    elif dispersion_ratio < UNDERDISPERSION_THRESHOLD:
        return mean, variance, dispersion_ratio, "POISSON_UNDERDISPERSED"
    else:
        return mean, variance, dispersion_ratio, "POISSON"


def negbin_params(mean: float, variance: float) -> Tuple[float, float]:
    """
    Convert (mean, variance) to Negative Binomial (r, p) parameters.

    NB parameterisation:
        mean = r(1-p)/p
        var  = r(1-p)/p²
    Solving:
        p = mean / variance
        r = mean² / (variance - mean)
    """
    if variance <= mean:
        raise ValueError("NegBin requires variance > mean")

    p = mean / variance
    r = (mean ** 2) / (variance - mean)

    # Clamp to valid range
    p = max(0.01, min(0.99, p))
    r = max(0.1, r)
    return r, p


def negbin_cdf(k: int, r: float, p: float) -> float:
    """CDF of Negative Binomial P(X <= k) using log-gamma."""
    if k < 0:
        return 0.0
    total = 0.0
    for i in range(k + 1):
        try:
            log_pmf = (
                math.lgamma(i + r)
                - math.lgamma(i + 1)
                - math.lgamma(r)
                + r * math.log(p)
                + i * math.log(1 - p)
            )
            total += math.exp(log_pmf)
        except (OverflowError, ValueError):
            pass
    return min(1.0, total)


def poisson_cdf(k: int, lam: float) -> float:
    """CDF of Poisson P(X <= k)."""
    if k < 0 or lam <= 0:
        return 0.0
    total = 0.0
    for i in range(k + 1):
        try:
            log_pmf = i * math.log(lam) - lam - math.lgamma(i + 1)
            total += math.exp(log_pmf)
        except (OverflowError, ValueError):
            pass
    return min(1.0, total)


def calculate_probability(
    line: float,
    direction: str,
    mean: float,
    variance: float,
    distribution_type: str,
) -> float:
    """
    Calculate P(outcome vs line) using the appropriate distribution.

    Handles half-point lines correctly:
      HIGHER 19.5 → P(X >= 20) = 1 - P(X <= 19)
      LOWER  19.5 → P(X <= 19) = P(X <= 19)
    """
    direction = direction.upper()

    if mean <= 0:
        return 0.50

    # Force variance >= mean for NegBin (safety)
    if distribution_type == "NEGATIVE_BINOMIAL" and variance <= mean:
        distribution_type = "POISSON"

    if distribution_type in ("POISSON", "POISSON_LOW_SAMPLE", "POISSON_UNDERDISPERSED"):
        if direction in ("UNDER", "LOWER"):
            k = int(math.floor(line - 0.5))
            prob = poisson_cdf(k, mean)
        else:
            k = int(math.ceil(line + 0.5))
            prob = 1.0 - poisson_cdf(k - 1, mean)

    elif distribution_type == "NEGATIVE_BINOMIAL":
        r, p = negbin_params(mean, variance)
        if direction in ("UNDER", "LOWER"):
            k = int(math.floor(line - 0.5))
            prob = negbin_cdf(k, r, p)
        else:
            k = int(math.ceil(line + 0.5))
            prob = 1.0 - negbin_cdf(k - 1, r, p)
    else:
        # Fallback to Poisson
        return calculate_probability(line, direction, mean, mean, "POISSON")

    return max(0.01, min(0.99, prob))


def get_distribution_for_player(
    stat_type: str,
    game_values: List[float],
) -> Dict:
    """
    Determine the correct distribution for a player-stat combination.

    Returns dict with:
        mean, variance, distribution_type, dispersion_ratio, confidence, sample_size
    """
    mean, variance, dr, dist_type = detect_dispersion(game_values, stat_type)

    n = len(game_values) if game_values else 0
    if n >= 15:
        confidence = "HIGH"
    elif n >= 8:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "mean": mean,
        "variance": variance,
        "distribution_type": dist_type,
        "dispersion_ratio": dr,
        "confidence": confidence,
        "sample_size": n,
        "stat_prior": STAT_DISPERSION_PRIORS.get(stat_type, "UNKNOWN"),
    }
