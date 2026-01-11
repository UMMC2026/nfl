"""
Phase 1A Pace Adjustment - Minimal Viable Fix

Corrects projection mean for game pace context.
Mean-only adjustment, no variance modification.
Simple arithmetic average, hard bounds, full logging.
"""

# Constants (IMMUTABLE)
LEAGUE_AVG_PACE = 100.0  # NBA baseline possessions per 48
PACE_FLOOR = 0.92        # Max 8% downward adjustment
PACE_CEILING = 1.08      # Max 8% upward adjustment


def pace_adjust_mean(base_mean: float, team_pace: float, opp_pace: float) -> tuple[float, dict]:
    """
    Apply pace adjustment to projection mean.
    
    Args:
        base_mean: Unadjusted stat projection
        team_pace: Team's pace (possessions per 48)
        opp_pace: Opponent's pace (possessions per 48)
    
    Returns:
        (pace_adjusted_mean, pace_context_dict)
    
    Phase 1A Design:
    - Simple arithmetic average of team + opponent pace
    - League-relative multiplier
    - Hard bounds to prevent runaway inflation
    - Mean-only (variance unchanged)
    - NO stat sensitivity
    - NO position modifiers
    - NO home/away tweaks
    """
    # Handle missing data
    if not team_pace or not opp_pace:
        return base_mean, {
            "team_pace": team_pace,
            "opp_pace": opp_pace,
            "game_pace": LEAGUE_AVG_PACE,
            "league_avg_pace": LEAGUE_AVG_PACE,
            "pace_multiplier": 1.0,
            "pace_adjusted_mean": base_mean,
            "adjustment_delta": 0.0,
            "pace_data_available": False
        }
    
    # Compute game pace (simple average)
    game_pace = (team_pace + opp_pace) / 2
    
    # League-relative multiplier
    pace_multiplier = game_pace / LEAGUE_AVG_PACE
    
    # Hard bounds
    pace_multiplier = max(PACE_FLOOR, min(PACE_CEILING, pace_multiplier))
    
    # Apply to mean only
    pace_adjusted_mean = base_mean * pace_multiplier
    
    # Full logging (mandatory for trust)
    pace_context = {
        "team_pace": round(team_pace, 2),
        "opp_pace": round(opp_pace, 2),
        "game_pace": round(game_pace, 2),
        "league_avg_pace": LEAGUE_AVG_PACE,
        "pace_multiplier": round(pace_multiplier, 4),
        "base_mean": round(base_mean, 2),
        "pace_adjusted_mean": round(pace_adjusted_mean, 2),
        "adjustment_delta": round(pace_adjusted_mean - base_mean, 2),
        "pace_data_available": True
    }
    
    return pace_adjusted_mean, pace_context


def get_team_pace(team: str, pace_data: dict) -> float:
    """
    Lookup team pace from external data source.
    
    Args:
        team: Team abbreviation
        pace_data: Dict of team -> pace mappings
    
    Returns:
        Team pace or league average if missing
    """
    return pace_data.get(team, LEAGUE_AVG_PACE)
