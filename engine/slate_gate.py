"""
Slate Gate — Hard Truth Gate for Team Availability

Enforces: If a team is not playing today, it is ILLEGAL to output.
"""

from datetime import date
from typing import List, Dict, Any


def enforce_today_slate(
    picks: List[Dict[str, Any]],
    today_teams: set,
    min_match_rate: float = 0.95
) -> List[Dict[str, Any]]:
    """
    Validate that picks align with today's slate.

    Args:
        picks: List of pick dicts with 'team' field
        today_teams: Set of teams playing today (e.g., {'LAL', 'BOS', 'MIA'})
        min_match_rate: Minimum % of picks that must match today's teams (default 95%)

    Returns:
        List of picks that match today's slate

    Raises:
        RuntimeError: If match rate < min_match_rate (fail closed)
    """
    if not picks:
        raise RuntimeError("SLATE GATE: No picks provided")

    total = len(picks)
    matched = [p for p in picks if p.get("team") in today_teams]
    match_rate = len(matched) / max(total, 1)

    if match_rate < min_match_rate:
        unmatched_teams = set(p.get("team") for p in picks) - today_teams
        raise RuntimeError(
            f"SLATE GATE FAIL: {match_rate:.1%} of picks match today's slate. "
            f"Unmatched teams: {unmatched_teams}. Today's teams: {today_teams}"
        )

    return matched


def get_today_slate_from_espn(league: str = "NBA") -> set:
    """
    Fetch today's teams playing (stub for ESPN integration).
    Replace with actual ESPN API call when ready.

    Args:
        league: 'NBA', 'NFL', or 'CFB'

    Returns:
        Set of team codes (e.g., {'LAL', 'BOS', 'MIA'})
    """
    # TODO: Integrate with ufa.ingest.espn or data_center
    raise NotImplementedError("Call ESPN API or load from data_center/slate.json")
