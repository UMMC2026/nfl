"""soccer/models/dr_soccer_bayes.py

Dr_Soccer_Bayes — v1.0

Ports the concept of Dr_NFL_Bayes to soccer by swapping EPA → goal intensity (lambda).

We use a simple Gamma-Poisson conjugate update around xG-derived signals:
- Prior: Gamma(alpha0, beta0) for team goal rate
- Observations: treat xG as a noisy proxy for goals

Outputs:
- lambda_home
- lambda_away
- uncertainty bands (std, 10/90% approx)

No scraping: inputs are provided by manual xG sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import math


@dataclass
class LambdaEstimate:
    lam: float
    std: float
    p10: float
    p90: float
    details: Dict


def _gamma_posterior(alpha0: float, beta0: float, *, exposures: float, signal: float) -> tuple[float, float]:
    """Return posterior (alpha, beta) given prior and a signal.

    We interpret `signal` as total expected goals over `exposures` matches.
    """
    alpha = alpha0 + max(0.0, signal)
    beta = beta0 + max(0.0, exposures)
    return alpha, beta


def _gamma_mean(alpha: float, beta: float) -> float:
    return alpha / beta if beta > 0 else 0.0


def _gamma_std(alpha: float, beta: float) -> float:
    # Var = alpha / beta^2
    if beta <= 0:
        return 0.0
    return math.sqrt(max(0.0, alpha) / (beta * beta))


def estimate_team_lambda(
    *,
    xg_for: float,
    xg_against: float,
    matches_played: int,
    prior_mean: float = 1.35,
    prior_strength: float = 12.0,
    matchup_weight: float = 0.55,
    context_mult: float = 1.0,
) -> LambdaEstimate:
    """Estimate a team's goal lambda for a single match.

    Args:
        xg_for: team xG for (rolling window average)
        xg_against: opponent xGA (rolling window average)
        matches_played: sample size for sufficiency gating
        prior_mean: global baseline goal mean per team per match
        prior_strength: pseudo-match count for the prior
        matchup_weight: blend between team xG_for and opponent xG_against
        context_mult: contextual multiplier (rest, travel, tactics)

    Returns:
        LambdaEstimate
    """
    # Prior as Gamma(alpha0, beta0)
    beta0 = prior_strength
    alpha0 = prior_mean * beta0

    # Signal: blended expected goals
    blended = (matchup_weight * float(xg_for)) + ((1.0 - matchup_weight) * float(xg_against))
    blended = max(0.05, blended) * max(0.5, context_mult)

    # Treat matches_played as exposure. Keep bounded for stability.
    exposures = float(max(1, min(matches_played, 38)))
    signal_total = blended * exposures

    alpha, beta = _gamma_posterior(alpha0, beta0, exposures=exposures, signal=signal_total)
    lam = _gamma_mean(alpha, beta)
    std = _gamma_std(alpha, beta)

    # Cheap percentile approximation for Gamma via mean ± 1.28*std (normal approx)
    # Safe for reporting bands, not for tail-sensitive decisions.
    p10 = max(0.0, lam - 1.28 * std)
    p90 = max(0.0, lam + 1.28 * std)

    return LambdaEstimate(
        lam=lam,
        std=std,
        p10=p10,
        p90=p90,
        details={
            "alpha": alpha,
            "beta": beta,
            "prior_mean": prior_mean,
            "prior_strength": prior_strength,
            "xg_for": xg_for,
            "xg_against": xg_against,
            "matchup_weight": matchup_weight,
            "context_mult": context_mult,
            "exposures": exposures,
        },
    )


def estimate_match_lambdas(
    *,
    home_xg_for: float,
    home_xg_against: float,
    away_xg_for: float,
    away_xg_against: float,
    home_matches: int,
    away_matches: int,
    home_adv_mult: float = 1.12,
    context_home: float = 1.0,
    context_away: float = 1.0,
) -> Dict[str, LambdaEstimate]:
    """Estimate (lambda_home, lambda_away) with basic home advantage."""
    home = estimate_team_lambda(
        xg_for=home_xg_for,
        xg_against=away_xg_against,
        matches_played=home_matches,
        context_mult=context_home * home_adv_mult,
    )
    away = estimate_team_lambda(
        xg_for=away_xg_for,
        xg_against=home_xg_against,
        matches_played=away_matches,
        context_mult=context_away,
    )

    return {"home": home, "away": away}
