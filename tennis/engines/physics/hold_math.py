"""tennis.engines.physics.hold_math

Point -> game "physics".

We treat tennis as a point-level process parameterized by a single variable:

  p = P(server wins a point)

From p we compute P(hold) using standard closed-form tennis math.

This module is intentionally dependency-free so it can be used in pipelines
and tests without pulling in heavy numeric stacks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HoldMathResult:
    p_point: float
    p_hold: float


def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def hold_probability(p_point: float) -> float:
    """Return P(hold) for point-win probability p.

    Uses the standard formula:

    Let q = 1 - p.

    P(hold) = p^4 * (1 + 4q + 10q^2) + 20 * p^3 * q^3 * (p^2 / (1 - 2pq))

    Notes:
    - The second term corresponds to reaching deuce then winning from deuce.
    - We guard against numerical instability near (1 - 2pq) ~ 0.
    """

    p = clamp(float(p_point), 0.0, 1.0)
    q = 1.0 - p

    # Quick outs
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0

    # First part: win before deuce
    pre_deuce = (p**4) * (1.0 + 4.0 * q + 10.0 * (q**2))

    # Second part: reach deuce at 3-3 then win from deuce
    denom = 1.0 - 2.0 * p * q
    if abs(denom) < 1e-12:
        # If denom is ~0, the chain is near fair at deuce; treat as 0.5 win from deuce.
        p_win_from_deuce = 0.5
    else:
        p_win_from_deuce = (p**2) / denom

    deuce_reach = 20.0 * (p**3) * (q**3)
    return clamp(pre_deuce + deuce_reach * p_win_from_deuce, 0.0, 1.0)


def infer_point_prob_from_hold(p_hold: float, *, lo: float = 0.45, hi: float = 0.80) -> HoldMathResult:
    """Infer point-win probability p such that hold_probability(p) ~= p_hold.

    This lets us use databases that store *hold rate* while still honoring the
    repo's canonical point-level decomposition.

    We use a robust bisection (monotone mapping p -> P(hold)).

    Args:
        p_hold: Target hold probability in [0,1]
        lo/hi: Search interval for point win probability.

    Returns:
        HoldMathResult(p_point, p_hold_reconstructed)
    """

    target = clamp(float(p_hold), 0.0, 1.0)
    lo_p = clamp(float(lo), 0.0, 1.0)
    hi_p = clamp(float(hi), 0.0, 1.0)
    if lo_p >= hi_p:
        lo_p, hi_p = 0.45, 0.80

    # If target is extreme, short-circuit.
    if target <= 0.0:
        return HoldMathResult(p_point=0.0, p_hold=0.0)
    if target >= 1.0:
        return HoldMathResult(p_point=1.0, p_hold=1.0)

    # Ensure bracket actually brackets.
    f_lo = hold_probability(lo_p)
    f_hi = hold_probability(hi_p)

    # If the target lies outside the bracket (e.g., unusual hold rates), expand a bit.
    if target < f_lo:
        # move lo down toward 0.35
        lo_p2 = 0.35
        f_lo2 = hold_probability(lo_p2)
        if target >= f_lo2:
            lo_p, f_lo = lo_p2, f_lo2
    if target > f_hi:
        # move hi up toward 0.90
        hi_p2 = 0.90
        f_hi2 = hold_probability(hi_p2)
        if target <= f_hi2:
            hi_p, f_hi = hi_p2, f_hi2

    # Bisection
    for _ in range(60):
        mid = 0.5 * (lo_p + hi_p)
        f_mid = hold_probability(mid)
        if f_mid < target:
            lo_p = mid
        else:
            hi_p = mid

    p_point = 0.5 * (lo_p + hi_p)
    return HoldMathResult(p_point=p_point, p_hold=hold_probability(p_point))
