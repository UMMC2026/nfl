"""soccer/sim/soccer_sim.py

Match simulator for soccer v1.0.

Implements:
- Poisson scoreline distribution (optionally Negative Binomial later)
- Monte Carlo simulation for derived markets
- Early-goal volatility + red-card shocks (simple approximations)

NOTE: v1.0 keeps the simulator deterministic given a seed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import math
import random


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def scoreline_distribution(lam_home: float, lam_away: float, max_goals: int = 8) -> Dict[Tuple[int, int], float]:
    dist: Dict[Tuple[int, int], float] = {}
    total = 0.0
    for h in range(max_goals + 1):
        ph = _poisson_pmf(h, lam_home)
        for a in range(max_goals + 1):
            p = ph * _poisson_pmf(a, lam_away)
            dist[(h, a)] = p
            total += p

    # Normalize softly (truncate tail)
    if total > 0:
        for k in list(dist.keys()):
            dist[k] /= total

    return dist


def derived_market_probs(dist: Dict[Tuple[int, int], float]) -> Dict[str, float]:
    home_win = sum(p for (h, a), p in dist.items() if h > a)
    draw = sum(p for (h, a), p in dist.items() if h == a)
    away_win = sum(p for (h, a), p in dist.items() if h < a)

    def over(line: float) -> float:
        return sum(p for (h, a), p in dist.items() if (h + a) > line)

    def under(line: float) -> float:
        return sum(p for (h, a), p in dist.items() if (h + a) < line)

    btts_yes = sum(p for (h, a), p in dist.items() if h > 0 and a > 0)
    btts_no = 1.0 - btts_yes

    out = {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "btts_yes": btts_yes,
        "btts_no": btts_no,
    }

    for line in (0.5, 1.5, 2.5, 3.5):
        out[f"over_{line}"] = over(line)
        out[f"under_{line}"] = under(line)

    return out


@dataclass
class SimOptions:
    sims: int = 10000
    seed: int = 1337
    early_goal_volatility: float = 0.08  # if early goal happens, lambdas drop
    red_card_rate: float = 0.08         # approx chance of a red in a match
    red_card_lambda_mult: float = 0.85  # apply to advantaged team for simplicity


def simulate_match_probs(
    lam_home: float,
    lam_away: float,
    opts: SimOptions = SimOptions(),
) -> Dict[str, float]:
    """Monte Carlo simulation with simple state shocks.

    Returns market probabilities consistent with derived_market_probs().
    """
    rng = random.Random(opts.seed)

    counts = {
        "home_win": 0,
        "draw": 0,
        "away_win": 0,
        "btts_yes": 0,
        "btts_no": 0,
        "over_0.5": 0,
        "under_0.5": 0,
        "over_1.5": 0,
        "under_1.5": 0,
        "over_2.5": 0,
        "under_2.5": 0,
        "over_3.5": 0,
        "under_3.5": 0,
    }

    # Knuth sampling for Poisson
    def sample_poisson(lam: float) -> int:
        if lam <= 0:
            return 0
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= rng.random()
        return k - 1

    for _ in range(opts.sims):
        lh = lam_home
        la = lam_away

        # Early goal volatility (proxy: 10% chance)
        if rng.random() < 0.10:
            lh *= (1.0 - opts.early_goal_volatility)
            la *= (1.0 - opts.early_goal_volatility)

        # Red card shock (very rough): reduces one side's intensity
        if rng.random() < opts.red_card_rate:
            if rng.random() < 0.50:
                lh *= opts.red_card_lambda_mult
            else:
                la *= opts.red_card_lambda_mult

        h = sample_poisson(max(0.0, lh))
        a = sample_poisson(max(0.0, la))

        if h > a:
            counts["home_win"] += 1
        elif h == a:
            counts["draw"] += 1
        else:
            counts["away_win"] += 1

        if h > 0 and a > 0:
            counts["btts_yes"] += 1
        else:
            counts["btts_no"] += 1

        total = h + a
        for line in (0.5, 1.5, 2.5, 3.5):
            if total > line:
                counts[f"over_{line}"] += 1
            elif total < line:
                counts[f"under_{line}"] += 1

    probs = {k: v / float(opts.sims) for k, v in counts.items()}
    # Ensure totals are consistent (under may miss push region for integer lines, not used here)
    return probs
