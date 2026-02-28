# stat_specialist_engine.py
"""
STAT SPECIALIST ENGINE — SINGLE SOURCE OF TRUTH

This module is **pure logic**. No IO. No Monte Carlo. No rendering.
It can be imported anywhere without side effects.

Production lock-in spec (v1.0)
"""
from enum import Enum
from typing import Dict, Any, Optional, Tuple


class StatSpecialist(str, Enum):
    """Stat specialist taxonomy (basket-creation intelligence)."""
    CATCH_AND_SHOOT_3PM = "CATCH_AND_SHOOT_3PM"
    BIG_MAN_3PM = "BIG_MAN_3PM"
    MIDRANGE_SPECIALIST = "MIDRANGE_SPECIALIST"
    BIG_POST_SCORER = "BIG_POST_SCORER"
    RIM_RUNNER = "RIM_RUNNER"
    PASS_FIRST_CREATOR = "PASS_FIRST_CREATOR"
    OFF_DRIBBLE_SCORER = "OFF_DRIBBLE_SCORER"
    BENCH_MICROWAVE = "BENCH_MICROWAVE"
    GENERIC = "GENERIC"


# Confidence caps by specialist (production lock-in table)
# Values are in 0-1 scale (fractions, not percentages)
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

# Same table in percentage scale (0-100) for systems using that convention
SPECIALIST_CONFIDENCE_CAP_PCT: Dict[StatSpecialist, float] = {
    k: v * 100.0 for k, v in SPECIALIST_CONFIDENCE_CAP.items()
}

# Volatility-dampened specialists (apply 0.95 multiplier after cap)
VOLATILITY_DAMPENED_SPECIALISTS = frozenset({
    StatSpecialist.OFF_DRIBBLE_SCORER,
    StatSpecialist.BENCH_MICROWAVE,
})

# Specialists banned from FLEX entries (volatile/unreliable)
FLEX_BANNED_SPECIALISTS = frozenset({
    StatSpecialist.BENCH_MICROWAVE,
    StatSpecialist.OFF_DRIBBLE_SCORER,
})

# Specialists with max legs constraints
SPECIALIST_MAX_LEGS: Dict[StatSpecialist, int] = {
    StatSpecialist.BIG_MAN_3PM: 2,
}


def classify_stat_specialist(player: Dict[str, Any], stat: str) -> StatSpecialist:
    """
    Classify a player's stat specialist type using tracking-feature rules.
    
    Args:
        player: dict of enriched features (already computed upstream)
        stat: 'PTS', 'REB', 'AST', '3PM', etc (case-insensitive)
    
    Returns:
        StatSpecialist enum value
    """
    stat = str(stat or "").upper()
    
    # Normalize stat aliases
    if stat in {"3PT", "3PTS", "THREES", "THREE_POINTERS"}:
        stat = "3PM"
    if stat in {"POINTS", "P"}:
        stat = "PTS"
    if stat in {"REBOUNDS"}:
        stat = "REB"
    if stat in {"ASSISTS"}:
        stat = "AST"

    # --- BENCH MICROWAVE (checked first, stat-agnostic) ---
    if (
        player.get("bench_minutes_rate", 0) >= 0.80
        and player.get("usage_volatility", player.get("usage_spike_volatility", 0)) >= 0.75
    ):
        return StatSpecialist.BENCH_MICROWAVE

    # --- 3PM SPECIALISTS ---
    if stat == "3PM":
        # CATCH_AND_SHOOT_3PM
        if (
            player.get("assisted_3pa_rate", 0) >= 0.65
            and player.get("dribbles_per_shot", 99) <= 1.2
            and player.get("pullup_3pa_rate", 1) < 0.30
        ):
            return StatSpecialist.CATCH_AND_SHOOT_3PM

        # BIG_MAN_3PM
        position = str(player.get("position", "")).upper()
        if (
            position in ("C", "PF")
            and player.get("avg_3pa", 0) >= 2.5
            and player.get("pick_and_pop_rate", 0) >= 0.25
        ):
            return StatSpecialist.BIG_MAN_3PM

        # OFF_DRIBBLE_SCORER (3PM variant)
        if player.get("pullup_3pa_rate", player.get("pullup_fga_rate", 0)) >= 0.45:
            return StatSpecialist.OFF_DRIBBLE_SCORER

    # --- POINTS SPECIALISTS ---
    if stat == "PTS":
        # MIDRANGE_SPECIALIST
        if (
            player.get("midrange_fga_rate", 0) >= 0.35
            and player.get("rim_fga_rate", 1) < 0.35
        ):
            return StatSpecialist.MIDRANGE_SPECIALIST

        # BIG_POST_SCORER
        if (
            player.get("post_touch_rate", 0) >= 0.25
            and player.get("paint_fga_rate", 0) >= 0.45
        ):
            return StatSpecialist.BIG_POST_SCORER

        # OFF_DRIBBLE_SCORER (PTS variant)
        if player.get("pullup_fga_rate", 0) >= 0.45:
            return StatSpecialist.OFF_DRIBBLE_SCORER

    # --- REB / LOW-SHOT BIGS (RIM_RUNNER) ---
    if stat in ("REB", "PTS"):
        if (
            player.get("assisted_fg_rate", 0) >= 0.70
            and player.get("avg_shot_distance", 99) <= 5
        ):
            return StatSpecialist.RIM_RUNNER

    # --- ASSISTS (PASS_FIRST_CREATOR) ---
    if stat == "AST":
        time_of_possession = player.get("time_of_possession", 0)
        team_threshold = player.get("team_top_80_pct_touches", player.get("team_80th_pct", 999))
        usage_rate = player.get("usage_rate", 1)
        scorer_threshold = player.get("scorer_usage_threshold", player.get("scorer_threshold", 0.28))
        
        if time_of_possession >= team_threshold and usage_rate < scorer_threshold:
            return StatSpecialist.PASS_FIRST_CREATOR

    return StatSpecialist.GENERIC


def apply_specialist_confidence_cap(
    confidence: float,
    specialist: StatSpecialist,
    *,
    use_percent_scale: bool = False,
) -> Tuple[float, Dict[str, Any]]:
    """
    Apply specialist-based confidence cap and volatility dampening.
    
    Args:
        confidence: Current confidence (0-1 scale by default, or 0-100 if use_percent_scale=True)
        specialist: StatSpecialist classification
        use_percent_scale: If True, treat confidence as 0-100 scale
    
    Returns:
        (capped_confidence, metadata_dict)
    """
    meta: Dict[str, Any] = {
        "specialist": specialist.value,
        "original_confidence": confidence,
        "cap_applied": False,
        "volatility_dampened": False,
    }
    
    # Get cap in appropriate scale
    if use_percent_scale:
        cap = SPECIALIST_CONFIDENCE_CAP_PCT.get(specialist, 65.0)
    else:
        cap = SPECIALIST_CONFIDENCE_CAP.get(specialist, 0.65)
    
    meta["ceiling"] = cap
    
    # Apply cap (never increases confidence)
    if confidence > cap:
        confidence = cap
        meta["cap_applied"] = True
    
    # Volatility dampening for high-variance specialists
    if specialist in VOLATILITY_DAMPENED_SPECIALISTS:
        confidence = confidence * 0.95
        meta["volatility_dampened"] = True
        meta["volatility_multiplier"] = 0.95
    
    meta["final_confidence"] = confidence
    return confidence, meta


def get_matchup_delta_weight(stat: str, specialist: StatSpecialist) -> float:
    """
    Matchup memory interaction weight.
    
    If stat is 3PM and specialist is a 3PM role specialist, upweight the matchup delta.
    Otherwise, dampen matchup delta.
    
    Returns:
        Weight multiplier (1.25 for 3PM specialists, 0.85 otherwise)
    """
    stat_u = str(stat or "").upper()
    if stat_u in {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"} and specialist in {
        StatSpecialist.CATCH_AND_SHOOT_3PM,
        StatSpecialist.BIG_MAN_3PM,
    }:
        return 1.25
    return 0.85


def is_flex_banned(specialist: StatSpecialist) -> bool:
    """Check if specialist is banned from FLEX entries."""
    return specialist in FLEX_BANNED_SPECIALISTS


def get_max_legs(specialist: StatSpecialist) -> Optional[int]:
    """Get max legs constraint for specialist (None = no constraint)."""
    return SPECIALIST_MAX_LEGS.get(specialist)


def should_reject_pick(
    specialist: StatSpecialist,
    stat: str,
    line: float,
    confidence: float,
    *,
    use_percent_scale: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Check if pick should be REJECTED based on specialist rules.
    
    Returns:
        (should_reject, rejection_reason)
    """
    stat_u = str(stat or "").upper()
    
    # Normalize stat aliases
    if stat_u in {"3PT", "3PTS", "THREES", "THREE_POINTERS"}:
        stat_u = "3PM"
    if stat_u in {"POINTS", "P"}:
        stat_u = "PTS"
    
    # Rule 1: BENCH_MICROWAVE on PTS or 3PM
    if specialist == StatSpecialist.BENCH_MICROWAVE and stat_u in {"PTS", "3PM"}:
        return True, "BENCH_MICROWAVE_FRAGILE_STAT"
    
    # Rule 2: OFF_DRIBBLE_SCORER confidence floor
    threshold = 58.0 if use_percent_scale else 0.58
    if specialist == StatSpecialist.OFF_DRIBBLE_SCORER and confidence < threshold:
        return True, "OFF_DRIBBLE_LOW_CONFIDENCE"
    
    # Rule 3: BIG_MAN_3PM line >= 3.5
    if specialist == StatSpecialist.BIG_MAN_3PM and line >= 3.5:
        return True, "BIG_MAN_3PM_LINE_TOO_HIGH"
    
    return False, None


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def enrich_pick_with_specialist(
    pick: Dict[str, Any],
    player_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to classify and attach specialist metadata to a pick.
    
    Mutates the pick dict in place and returns it.
    """
    if player_features is None:
        player_features = pick  # Use pick dict itself as feature source
    
    stat = pick.get("stat", pick.get("stat_type", pick.get("market", "")))
    specialist = classify_stat_specialist(player_features, stat)
    
    pick["stat_specialist"] = specialist.value
    pick["stat_specialist_type"] = specialist.value  # Alias for compatibility
    
    return pick


def apply_specialist_governance_to_pick(
    pick: Dict[str, Any],
    player_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Full governance pass: classify, cap confidence, check rejection.
    
    Mutates the pick dict in place and returns it.
    """
    if player_features is None:
        player_features = pick
    
    stat = pick.get("stat", pick.get("stat_type", pick.get("market", "")))
    
    # Classify
    specialist = classify_stat_specialist(player_features, stat)
    pick["stat_specialist"] = specialist.value
    pick["stat_specialist_type"] = specialist.value
    
    # Get confidence (try multiple field names)
    confidence = pick.get("confidence", pick.get("probability", pick.get("effective_confidence", 0.5)))
    
    # Detect scale (>1 means percent scale)
    use_percent = confidence > 1.0
    
    # Apply cap
    capped_confidence, cap_meta = apply_specialist_confidence_cap(
        confidence, specialist, use_percent_scale=use_percent
    )
    
    pick["specialist_governance"] = cap_meta
    
    # Update confidence fields
    if "confidence" in pick:
        pick["confidence"] = capped_confidence
    if "probability" in pick:
        pick["probability"] = capped_confidence
    if "effective_confidence" in pick:
        pick["effective_confidence"] = capped_confidence
    
    # Check rejection
    line = pick.get("line", 0)
    should_reject, reason = should_reject_pick(
        specialist, stat, line, capped_confidence, use_percent_scale=use_percent
    )
    
    if should_reject:
        pick["specialist_rejected"] = True
        pick["specialist_rejection_reason"] = reason
    
    return pick
