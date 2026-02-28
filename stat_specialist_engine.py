"""Stat specialist engine (pure logic, no IO).

This module provides:
- a deterministic specialist classifier based on upstream-enriched features
- a specialist-aware confidence cap (never increases confidence)

It is designed to be imported anywhere without side effects.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class StatSpecialist(str, Enum):
    CATCH_AND_SHOOT_3PM = "CATCH_AND_SHOOT_3PM"
    BIG_MAN_3PM = "BIG_MAN_3PM"
    MIDRANGE_SPECIALIST = "MIDRANGE_SPECIALIST"
    BIG_POST_SCORER = "BIG_POST_SCORER"
    RIM_RUNNER = "RIM_RUNNER"
    PASS_FIRST_CREATOR = "PASS_FIRST_CREATOR"
    OFF_DRIBBLE_SCORER = "OFF_DRIBBLE_SCORER"
    BENCH_MICROWAVE = "BENCH_MICROWAVE"
    GENERIC = "GENERIC"


# Caps are expressed on a 0-1 probability scale.
SPECIALIST_CONFIDENCE_CAP: Dict[StatSpecialist, float] = {
    StatSpecialist.CATCH_AND_SHOOT_3PM: 0.70,
    StatSpecialist.BIG_MAN_3PM: 0.62,
    StatSpecialist.MIDRANGE_SPECIALIST: 0.60,
    StatSpecialist.BIG_POST_SCORER: 0.63,
    StatSpecialist.RIM_RUNNER: 0.65,
    StatSpecialist.PASS_FIRST_CREATOR: 0.68,
    StatSpecialist.OFF_DRIBBLE_SCORER: 0.58,
    StatSpecialist.BENCH_MICROWAVE: 0.55,
    StatSpecialist.GENERIC: 0.65,
}


def _norm_stat(stat: Any) -> str:
    s = str(stat or "").strip().upper()
    if s in {"3PT", "3PTS", "THREES", "THREE_POINTERS"}:
        return "3PM"
    if s in {"POINTS", "P"}:
        return "PTS"
    if s in {"ASSISTS"}:
        return "AST"
    if s in {"REBOUNDS"}:
        return "REB"
    return s


def classify_stat_specialist(player: Dict[str, Any], stat: Any) -> StatSpecialist:
    """Classify a stat specialist for a specific stat.

    Args:
        player: dict of enriched features (already computed upstream)
        stat: 'PTS', 'REB', 'AST', '3PM', etc

    Returns:
        StatSpecialist
    """
    s = _norm_stat(stat)
    p = player or {}

    # --- 3PM SPECIALISTS ---
    if s == "3PM":
        if (
            float(p.get("assisted_3pa_rate", 0) or 0) >= 0.65
            and float(p.get("dribbles_per_shot", 99) or 99) <= 1.2
            and float(p.get("pullup_3pa_rate", 1) or 1) < 0.30
        ):
            return StatSpecialist.CATCH_AND_SHOOT_3PM

        pos = str(p.get("position") or "").strip().upper()
        if (
            pos in ("C", "PF")
            and float(p.get("avg_3pa", 0) or 0) >= 2.5
            and float(p.get("pick_and_pop_rate", 0) or 0) >= 0.25
        ):
            return StatSpecialist.BIG_MAN_3PM

        if float(p.get("pullup_3pa_rate", 0) or 0) >= 0.45:
            return StatSpecialist.OFF_DRIBBLE_SCORER

    # --- POINTS SPECIALISTS ---
    if s == "PTS":
        if (
            float(p.get("midrange_fga_rate", 0) or 0) >= 0.35
            and float(p.get("rim_fga_rate", 1) or 1) < 0.35
        ):
            return StatSpecialist.MIDRANGE_SPECIALIST

        if (
            float(p.get("post_touch_rate", 0) or 0) >= 0.25
            and float(p.get("paint_fga_rate", 0) or 0) >= 0.45
        ):
            return StatSpecialist.BIG_POST_SCORER

        if float(p.get("pullup_fga_rate", 0) or 0) >= 0.45:
            return StatSpecialist.OFF_DRIBBLE_SCORER

    # --- REB / LOW-SHOT BIGS ---
    if s in ("REB", "PTS"):
        if (
            float(p.get("assisted_fg_rate", 0) or 0) >= 0.70
            and float(p.get("avg_shot_distance", 99) or 99) <= 5
        ):
            return StatSpecialist.RIM_RUNNER

    # --- ASSISTS ---
    if s == "AST":
        if (
            float(p.get("time_of_possession", 0) or 0) >= float(p.get("team_top_80_pct_touches", 999) or 999)
            and float(p.get("usage_rate", 1) or 1) < float(p.get("scorer_usage_threshold", 0.28) or 0.28)
        ):
            return StatSpecialist.PASS_FIRST_CREATOR

    # --- BENCH MICROWAVE ---
    if (
        float(p.get("bench_minutes_rate", 0) or 0) >= 0.80
        and float(p.get("usage_volatility", 0) or 0) >= 0.75
    ):
        return StatSpecialist.BENCH_MICROWAVE

    return StatSpecialist.GENERIC


def apply_specialist_confidence_cap(confidence: float, specialist: StatSpecialist) -> float:
    """Apply the specialist confidence cap.

    Accepts confidence expressed in either:
    - 0..1 probability space
    - 0..100 percent space

    Returns in the same scale as the input.
    """
    c = float(confidence)
    in_percent = c > 1.5

    if in_percent:
        c = c / 100.0

    cap = float(SPECIALIST_CONFIDENCE_CAP.get(specialist, SPECIALIST_CONFIDENCE_CAP[StatSpecialist.GENERIC]))
    c = min(c, cap)

    if specialist in (StatSpecialist.OFF_DRIBBLE_SCORER, StatSpecialist.BENCH_MICROWAVE):
        c *= 0.95

    if in_percent:
        return max(0.0, min(100.0, c * 100.0))
    return max(0.0, min(1.0, c))
