"""
CBB Context Adjustments — Pace, Spread, Defense, Game Script

Adjusts raw lambda based on game context BEFORE probability calculation.
This is the critical missing piece: the model was using static lambda
regardless of whether a team was favored/underdog, fast/slow pace, or
facing elite/weak defense.

Key insight from calibration failures:
  - UNDER picks on underdog stars are structurally -EV
  - Trailing teams inflate their star's counting stats
  - Pace mismatches cause systematic lambda errors

Implementation Date: 2026-02-14
"""

from typing import Dict, Tuple, Optional


# ============================================================================
# PACE ADJUSTMENT
# ============================================================================

# KenPom-style league average pace (possessions per 40 min)
# 2025-26 NCAA average — update annually
CBB_LEAGUE_AVG_PACE = 68.0

# Max pace adjustment magnitude (prevent wild swings)
PACE_CAP_LOW = 0.85
PACE_CAP_HIGH = 1.15


def calculate_pace_factor(
    team_pace: float,
    opponent_pace: float,
    league_avg: float = CBB_LEAGUE_AVG_PACE,
) -> float:
    """
    Calculate pace adjustment factor.

    High-pace games = more possessions = higher counting stats.
    Low-pace games = fewer possessions = lower counting stats.

    Expected game pace is average of both teams' tempos.
    """
    if league_avg <= 0:
        return 1.0

    expected_pace = (team_pace + opponent_pace) / 2.0
    pace_factor = expected_pace / league_avg

    return max(PACE_CAP_LOW, min(PACE_CAP_HIGH, pace_factor))


# ============================================================================
# SPREAD → MINUTES ADJUSTMENT
# ============================================================================

# Spread thresholds
SPREAD_CLOSE = 4.0       # ≤ 4 = close game
SPREAD_COMFORTABLE = 8.0  # 4-8 = comfortable
SPREAD_BLOWOUT = 14.0     # ≥ 14 = blowout risk


def calculate_spread_minutes_factor(
    spread: float,
    direction: str,
    is_favorite: bool,
) -> float:
    """
    Adjust expected production based on projected game script.

    Close games → Stars play full 40 minutes → normal/higher stats.
    Blowouts    → Favorite rests starters in 4th quarter → lower stats.
                → Underdog stars chase → HIGHER stats (UNDER is dangerous).
    """
    direction = direction.upper()
    abs_spread = abs(spread)

    if abs_spread <= SPREAD_CLOSE:
        # Close game — full minutes, both sides
        minutes_factor = 1.05
    elif abs_spread <= SPREAD_COMFORTABLE:
        minutes_factor = 1.0
    elif abs_spread <= SPREAD_BLOWOUT:
        if is_favorite:
            minutes_factor = 0.95   # Stars may sit late
        else:
            minutes_factor = 1.05   # Underdog stars play hard trying to catch up
    else:
        # Extreme blowout territory
        if is_favorite:
            minutes_factor = 0.88   # Heavy rest likely
        else:
            minutes_factor = 0.95   # Still play but garbage time noise

    # Direction interaction: UNDER on trailing star = extra risky
    if direction in ("UNDER", "LOWER"):
        if not is_favorite and abs_spread >= 6:
            # Trailing team's stars INFLATE stats → UNDER is dangerous
            minutes_factor *= 1.05   # Penalise UNDER pick by inflating lambda

    return minutes_factor


# ============================================================================
# OPPONENT DEFENSE ADJUSTMENT
# ============================================================================

# Stat-specific defensive impact coefficients
# Higher = more affected by opponent defense quality
_DEFENSE_IMPACT: Dict[str, float] = {
    "points":   0.15,
    "3pm":      0.12,
    "assists":  0.08,
    "rebounds":  0.05,
    "pra":      0.12,
    "pts+reb":  0.10,
    "pts+ast":  0.10,
    "reb+ast":  0.06,
    "steals":   0.04,
    "blocks":   0.04,
    "turnovers": 0.06,
}


def calculate_opponent_defense_factor(
    stat_type: str,
    opponent_def_rank: int,
    total_teams: int = 360,
) -> float:
    """
    Adjust for opponent defensive strength.

    Elite defense (top 50)     → suppress stats.
    Terrible defense (bottom 50) → inflate stats.

    opponent_def_rank: 1 = best defense, 360 = worst defense.
    """
    if opponent_def_rank <= 0 or total_teams <= 0:
        return 1.0

    percentile = opponent_def_rank / total_teams   # low = good D
    impact = _DEFENSE_IMPACT.get(stat_type.lower(), 0.08)

    if percentile < 0.15:
        # Elite defense
        factor = 1.0 - (0.15 - percentile) * impact * 3
    elif percentile > 0.85:
        # Terrible defense
        factor = 1.0 + (percentile - 0.85) * impact * 3
    else:
        # Mid-pack — gentle linear
        factor = 1.0 + (percentile - 0.50) * impact

    return max(0.85, min(1.15, factor))


# ============================================================================
# GAME SCRIPT GATE  (P0 — most impactful fix)
# ============================================================================

def game_script_check(
    direction: str,
    stat_type: str,
    spread: float,
    is_favorite: bool,
    player_usage: float = 0.20,
) -> Tuple[bool, str, float]:
    """
    Game-script gate: Block or penalise UNDER picks on underdog stars.

    When a team is trailing:
      • Stars play MORE minutes (no garbage-time rest)
      • Stars take MORE shots (team needs scoring)
      • Stars get MORE assists (running the offense)
      • Stars grab MORE rebounds (crashing boards desperately)
    → UNDER on their combo/point stats is structurally -EV.

    Returns
    -------
    (passed, reason, penalty_factor)
        passed: False → hard-block this pick
        penalty_factor: multiplier on lambda (>1 = inflate → UNDER less likely)
    """
    direction = direction.upper()
    stat_lower = stat_type.lower()

    # OVER picks are NOT affected by this gate
    if direction in ("OVER", "HIGHER"):
        return True, "GAME_SCRIPT: OVER not affected", 1.0

    abs_spread = abs(spread) if spread else 0

    # ---- HARD BLOCKS ----

    # Heavy underdog (≥ 6 pts) + combo stat → BLOCK
    if not is_favorite and abs_spread >= 6:
        combo_stats = {"pra", "pts+reb+ast", "pts+ast", "pts+reb",
                       "points+assists", "points+rebounds",
                       "points+rebounds+assists", "reb+ast",
                       "rebounds+assists"}
        if stat_lower in combo_stats:
            return (
                False,
                f"GAME_SCRIPT_BLOCK: Combo UNDER on +{abs_spread} underdog — "
                f"trailing teams inflate star stats",
                1.0,
            )

        # Points UNDER on high-usage underdog
        if stat_lower in ("points", "pts") and player_usage >= 0.22:
            return (
                False,
                f"GAME_SCRIPT_BLOCK: Points UNDER on high-usage (+{abs_spread} underdog)",
                1.0,
            )

    # ---- SOFT PENALTIES ----

    # Moderate underdog (3-6 pts) + combo stat → inflate lambda by 8-12%
    if not is_favorite and 3 <= abs_spread < 6:
        combo_stats = {"pra", "pts+reb+ast", "pts+ast", "pts+reb",
                       "points+assists", "points+rebounds",
                       "reb+ast", "rebounds+assists"}
        if stat_lower in combo_stats:
            penalty = 1.0 + (abs_spread - 3) * 0.03   # 3→1.0, 6→1.09
            return (
                True,
                f"GAME_SCRIPT_WARN: Combo UNDER on moderate underdog (+{abs_spread}), "
                f"lambda inflated ×{penalty:.2f}",
                penalty,
            )

        if stat_lower in ("points", "pts"):
            penalty = 1.0 + (abs_spread - 3) * 0.02
            return (
                True,
                f"GAME_SCRIPT_WARN: Points UNDER on moderate underdog (+{abs_spread})",
                penalty,
            )

    # Close game (≤ 3 pts) + high-usage star → slight lambda inflate
    if abs_spread <= 3 and player_usage >= 0.25:
        return (
            True,
            "GAME_SCRIPT_WARN: Close game, star will play full minutes",
            1.03,
        )

    return True, "GAME_SCRIPT: OK", 1.0


# ============================================================================
# AGGREGATE ADJUSTMENT
# ============================================================================

def adjust_lambda(
    raw_lambda: float,
    stat_type: str,
    direction: str,
    team_pace: float = CBB_LEAGUE_AVG_PACE,
    opponent_pace: float = CBB_LEAGUE_AVG_PACE,
    spread: float = 0.0,
    is_favorite: bool = True,
    opponent_def_rank: int = 180,
    total_teams: int = 360,
    player_usage: float = 0.20,
) -> Dict:
    """
    Apply all context adjustments to raw lambda.

    Returns dict with raw_lambda, adjusted_lambda, all individual factors,
    and game-script gate result.
    """
    # 1. Pace
    pace_f = calculate_pace_factor(team_pace, opponent_pace)

    # 2. Spread / minutes
    spread_f = calculate_spread_minutes_factor(spread, direction, is_favorite)

    # 3. Opponent defense
    defense_f = calculate_opponent_defense_factor(stat_type, opponent_def_rank, total_teams)

    # 4. Game-script gate
    gs_passed, gs_reason, gs_penalty = game_script_check(
        direction, stat_type, spread, is_favorite, player_usage
    )

    # Combine
    total = pace_f * spread_f * defense_f * gs_penalty
    adjusted = raw_lambda * total

    return {
        "raw_lambda": raw_lambda,
        "adjusted_lambda": adjusted,
        "adjustments": {
            "pace": round(pace_f, 4),
            "spread_minutes": round(spread_f, 4),
            "opponent_defense": round(defense_f, 4),
            "game_script_penalty": round(gs_penalty, 4),
            "total": round(total, 4),
        },
        "game_script": {
            "passed": gs_passed,
            "reason": gs_reason,
        },
    }
