"""Parameter derivation for tennis physics engine.

We aim for an opponent-aware, point-level parameterization:
  pA_srv_point = P(A wins a point on A's serve)
  pB_srv_point = P(B wins a point on B's serve)

Data availability in this repo is mixed:
- Calibrated props pipeline has Tennis Abstract-derived *hold rates*
  (serve_hold_rate) via TennisPlayerProfile.
- Match-winner engine optionally has per-surface return points won in
  tennis/player_stats.json.

We combine these sources conservatively and always clamp to safe bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .hold_math import clamp, infer_point_prob_from_hold


@dataclass(frozen=True)
class PhysicsPointParams:
    pA_srv_point: float
    pB_srv_point: float
    # Derived for convenience
    pA_ret_point: float
    pB_ret_point: float

    # Diagnostics
    pA_hold: float
    pB_hold: float


def derive_point_params(
    *,
    a_hold: float,
    b_hold: float,
    a_return_win: Optional[float] = None,
    b_return_win: Optional[float] = None,
    a_strength: Optional[float] = None,
    b_strength: Optional[float] = None,
) -> PhysicsPointParams:
    """Derive point-win probabilities on serve for A and B.

    Args:
        a_hold/b_hold: Serve hold probabilities (0-1).
        a_return_win/b_return_win: Return points won (0-1), if available.
        a_strength/b_strength: Optional win-rate-like strength signal (0-1).

    Returns:
        PhysicsPointParams
    """

    # 1) Base: invert hold -> point probability (monotone).
    a_base = infer_point_prob_from_hold(a_hold).p_point
    b_base = infer_point_prob_from_hold(b_hold).p_point

    # 2) Opponent return adjustment (if return_win available).
    # Baseline tour-level return points won is around 0.35; we treat deviations
    # as small nudges.
    baseline_ret = 0.35
    if b_return_win is not None:
        # Better returner (higher b_return_win) -> reduce A serve point win.
        a_base -= (float(b_return_win) - baseline_ret) * 0.10
    if a_return_win is not None:
        b_base -= (float(a_return_win) - baseline_ret) * 0.10

    # 3) Strength adjustment (very conservative):
    if a_strength is not None and b_strength is not None:
        diff = float(a_strength) - float(b_strength)
        a_base += diff * 0.02
        b_base -= diff * 0.02

    # Safety clamps: keep within plausible bounds
    a_p = clamp(a_base, 0.45, 0.80)
    b_p = clamp(b_base, 0.45, 0.80)

    # Derived return point probabilities
    # If B serves, A wins return points with 1 - P(B wins on serve)
    a_ret = 1.0 - b_p
    b_ret = 1.0 - a_p

    return PhysicsPointParams(
        pA_srv_point=a_p,
        pB_srv_point=b_p,
        pA_ret_point=clamp(a_ret, 0.20, 0.55),
        pB_ret_point=clamp(b_ret, 0.20, 0.55),
        pA_hold=float(a_hold),
        pB_hold=float(b_hold),
    )
