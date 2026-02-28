"""Live-betting helper utilities.

These are intentionally conservative and do not place bets; they only
compute updated edges and suggest NO PLAY / LEAN / PLAY classifications
based on live odds and updated probabilities.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class LiveBetDecision:
    decision: str  # PLAY | LEAN | NO PLAY
    probability: float  # decimal [0,1]
    decimal_odds: float
    ev: float
    notes: str


def evaluate_live_bet(prob: float, decimal_odds: float) -> LiveBetDecision:
    """Evaluate a single live bet opportunity.

    Very simple policy:
      - If EV <= 0: NO PLAY
      - If EV > 0 and prob >= 0.65: PLAY
      - If EV > 0 and 0.55 <= prob < 0.65: LEAN
      - Else: NO PLAY
    """
    p = float(prob)
    if p > 1.0:
        p = p / 100.0
    o = float(decimal_odds)
    b = o - 1.0
    ev = p * b - (1.0 - p)

    if ev <= 0:
        decision = "NO PLAY"
        notes = "Negative or zero EV"
    else:
        if p >= 0.65:
            decision = "PLAY"
            notes = "Positive EV with high win probability"
        elif p >= 0.55:
            decision = "LEAN"
            notes = "Positive EV with moderate win probability"
        else:
            decision = "NO PLAY"
            notes = "Positive EV but low win probability"

    return LiveBetDecision(
        decision=decision,
        probability=p,
        decimal_odds=o,
        ev=ev,
        notes=notes,
    )
