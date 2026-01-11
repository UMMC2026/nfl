"""NFL structural priors engine.

Provides conservative, interpretable prior probabilities for common NFL prop
types when empirical recent_values are unavailable. Intention: produce a
meaningful prior (not flat 0.48) derived from structural context (usage,
opponent pressure, pace, run-stop rank).

This module is intentionally simple and auditable. It's meant as a starting
point — you'll later tune weights from historical data.
"""
from typing import Tuple
import math


def _clip(p: float, lo: float = 0.05, hi: float = 0.95) -> float:
    return max(lo, min(hi, p))


def compute_prior(pick: dict, context: object) -> Tuple[float, float, float]:
    """Compute prior probability and conservative mu/sigma for a pick.

    Returns (prior_prob, prior_mu, prior_sigma).

    - pick: dict with keys: stat, line, direction, team, player
    - context: ContextFlags (from ContextProvider)
    """
    stat = str(pick.get("stat", "")).lower()
    direction = pick.get("direction", "higher")
    line = float(pick.get("line") or 0.0)

    # Base prior: some stat-classes are naturally skewed
    base = 0.50

    # Heuristics by stat type
    if any(k in stat for k in ["td", "touchdown"]):
        base = 0.15 if direction == "higher" else 0.85  # touchdowns are rare
    elif any(k in stat for k in ["yard", "yd", "yards"]):
        # yardage priors center near 0.5 but allow spread from matchup/pace
        base = 0.50
    elif any(k in stat for k in ["recept", "reception", "receptions", "target"]):
        base = 0.40 if direction == "higher" else 0.60
    elif any(k in stat for k in ["attempt", "pass_attempt", "pass_attempts"]):
        base = 0.48 if direction == "higher" else 0.52
    elif any(k in stat for k in ["sack", "sacks"]):
        base = 0.10 if direction == "higher" else 0.90
    else:
        base = 0.50

    # Adjust by context signals when available
    adj = 0.0
    try:
        # Usage: if expected usage increases, lift over/unders accordingly
        if hasattr(context, "usage_context") and getattr(context, "usage_context").value == "+":
            adj += 0.06
        # Pace (higher pace → more yards/attempts)
        if hasattr(context, "opp_pace") and context.opp_pace:
            if context.opp_pace > 101:
                adj += 0.04
            elif context.opp_pace < 97:
                adj -= 0.03
        # Pass-rush pressure penalizes QB passing yardage/attempts priors
        if hasattr(context, "opp_pass_rush_rate") and context.opp_pass_rush_rate is not None:
            pr = context.opp_pass_rush_rate
            # High pressure -> reduce QB passing prospects
            if "pass" in stat or "pass_" in stat:
                if pr >= 0.18:
                    adj -= 0.06
                elif pr <= 0.14:
                    adj += 0.03
        # Run-stop rank: strong run defense lowers RB yardage priors
        if hasattr(context, "opp_run_stop_rank") and context.opp_run_stop_rank is not None:
            rrank = context.opp_run_stop_rank
            if "rush" in stat or "run" in stat or "rush_yards" in stat:
                if rrank <= 8:
                    adj -= 0.05
                elif rrank >= 20:
                    adj += 0.04
    except Exception:
        adj += 0.0

    prior_prob = _clip(base + adj)

    # Convert prior_prob into a conservative mu/sigma around market line for downstream
    # components that expect mu/sigma. We do a simple mapping:
    # - If prior_prob > 0.5 and direction == higher, set mu a bit above line; else below.
    # - Sigma chosen by stat-type heuristics (yardage ~20% mu, counts ~sqrt(mu)).

    mu = float(line)
    if prior_prob > 0.52:
        mu = line * (1.02 + (prior_prob - 0.52))
    elif prior_prob < 0.48:
        mu = line * (0.98 - (0.48 - prior_prob))

    # sigma heuristics
    if any(k in stat for k in ["yard", "yd"]):
        sigma = max(1.0, abs(mu) * 0.20)
    elif any(k in stat for k in ["td", "sack", "fg_made"]):
        sigma = max(0.5, (abs(mu) ** 0.5) * 1.2)
    else:
        sigma = max(0.5, abs(mu) * 0.15)

    return prior_prob, mu, sigma


__all__ = ["compute_prior"]
