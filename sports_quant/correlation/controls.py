from typing import Dict, Tuple

"""Correlation controls and penalties.
This is a simplified placeholder; in production, compute pairwise correlations from historical joint distributions.
"""

NEGATIVE_PAIRS = {
    ("RB_rush_yards", "QB_pass_yards"),
}


def correlation_penalty(prop_a: Dict, prop_b: Dict) -> float:
    a = prop_a.get("stat")
    b = prop_b.get("stat")
    pair = (a, b)
    rev = (b, a)
    if pair in NEGATIVE_PAIRS or rev in NEGATIVE_PAIRS:
        return 1.25  # penalize negative correlation exposures
    return 1.0
