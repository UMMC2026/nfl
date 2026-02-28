"""L10 Form Engine for Tennis
===============================

Lightweight module that injects a real-time "Last 10" (L10) signal into
static or season-long baselines used by the tennis Monte Carlo stack.

Design goals
------------
- Keep Monte Carlo as the source of truth for probabilities
- Treat 2024 / season data as "class" (base ability)
- Treat scraped L10 as "form" (current state)
- Combine them with a weighted moving average and explicit volatility penalty

This module is intentionally generic and stat-agnostic: callers provide
numeric L10 samples for any stat (aces, games won, total games, etc.).

Expected usage
--------------
The typical flow for a given player + stat is:

1. Load baseline season stats (e.g., from TennisStatsAPI or a CSV):
   - old_mu: season average for the stat
   - old_sigma: long-horizon standard deviation

2. Load scraped L10 samples for that stat from a local cache written by a
   scraper (e.g., tennis-data.co.uk, ATP/WTA, Flashscore via Playwright).

3. Call ``update_player_stats_with_l10`` to get updated (mu, sigma).

4. Persist the updated values back into the player's stats object that the
   Monte Carlo engine consumes (e.g., update ``aces_l10`` and ``aces_std``).

The Truth Engine and Monte Carlo remain unchanged: they simply see better
mu/σ inputs that already include form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class L10UpdateMeta:
    """Metadata describing how an L10 update was applied.

    This is useful for diagnostics, calibration, and render-layer explanations.
    """

    used_l10: bool
    n_l10: int
    current_mu: float
    current_sigma: float
    base_weight: float
    l10_weight: float
    vol_penalty: float


def compute_volatility_penalty(
    sigma_l10: float,
    low: float = 3.0,
    high: float = 8.0,
    max_penalty: float = 1.5,
) -> float:
    """Map recent volatility to a multiplicative penalty on sigma.

    ``low`` / ``high`` and ``max_penalty`` should be tuned per stat family
    (e.g., aces vs games vs tiebreakers). For now we expose a simple
    piecewise-linear mapping that can be calibrated from postmortems.
    """

    if sigma_l10 <= low:
        return 1.0
    if sigma_l10 >= high:
        return max_penalty

    # Linear interpolation between 1.0 and max_penalty
    frac = (sigma_l10 - low) / (high - low)
    return 1.0 + frac * (max_penalty - 1.0)


def update_player_stats_with_l10(
    old_mu: float,
    old_sigma: float,
    scraped_scores: List[float],
    min_games_for_full_weight: int = 6,
) -> Tuple[float, float, L10UpdateMeta]:
    """Blend baseline (season/2024) with scraped L10 samples.

    Parameters
    ----------
    old_mu:
        Baseline mean for the stat (e.g., 2024 season average).
    old_sigma:
        Baseline standard deviation for the stat.
    scraped_scores:
        Raw numeric values from the last N matches (N <= 10 is typical).
    min_games_for_full_weight:
        Number of L10 samples required before we trust the full 80% weight.

    Returns
    -------
    (updated_mu, updated_sigma, meta)
    """

    if not scraped_scores:
        # No recent data -> fall back to baseline only.
        meta = L10UpdateMeta(
            used_l10=False,
            n_l10=0,
            current_mu=float(old_mu),
            current_sigma=float(old_sigma),
            base_weight=1.0,
            l10_weight=0.0,
            vol_penalty=1.0,
        )
        return float(old_mu), float(old_sigma), meta

    scores = np.asarray(scraped_scores, dtype=float)
    n_l10 = int(scores.size)

    current_mu = float(scores.mean())
    current_sigma = float(scores.std(ddof=1)) if n_l10 > 1 else float(old_sigma)

    # If we have fewer than ``min_games_for_full_weight`` matches, taper
    # the L10 weight linearly up to the target 0.80.
    target_l10_weight = 0.80
    l10_weight = min(target_l10_weight, target_l10_weight * n_l10 / float(min_games_for_full_weight))
    base_weight = 1.0 - l10_weight

    updated_mu = (old_mu * base_weight) + (current_mu * l10_weight)

    # Blend volatility then apply penalty based on how erratic L10 has been.
    sigma_blend = (old_sigma + current_sigma) / 2.0
    vol_penalty = compute_volatility_penalty(current_sigma)
    updated_sigma = sigma_blend * vol_penalty

    meta = L10UpdateMeta(
        used_l10=True,
        n_l10=n_l10,
        current_mu=current_mu,
        current_sigma=current_sigma,
        base_weight=base_weight,
        l10_weight=l10_weight,
        vol_penalty=vol_penalty,
    )

    return float(updated_mu), float(updated_sigma), meta


def apply_l10_patch_from_dict(
    old_mu: float,
    old_sigma: float,
    patch: Dict,
    key: str,
    min_games_for_full_weight: int = 6,
) -> Tuple[float, float, L10UpdateMeta]:
    """Helper to apply an L10 patch from a generic dict.

    ``patch`` is expected to come from a JSON file written by a scraper
    and should contain a list of samples under ``patch["metrics"][key]``.

    Example schema (per player):
    {
        "surface": "HARD",
        "metrics": {
            "aces": [7, 9, 8, 10, 6, 11, 9, 7, 8, 10],
            "games_won": [12, 14, 15, 11, 13, 16, 15, 14, 13, 12]
        }
    }
    """

    try:
        metrics = patch.get("metrics") or {}
        series = metrics.get(key) or []
    except AttributeError:
        series = []

    return update_player_stats_with_l10(
        old_mu=old_mu,
        old_sigma=old_sigma,
        scraped_scores=series,
        min_games_for_full_weight=min_games_for_full_weight,
    )
