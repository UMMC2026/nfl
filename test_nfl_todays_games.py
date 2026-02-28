"""Regression check: NFL 'today's games' matchup loading.

Goal: prevent regressions where the NFL menu cannot build matchups for Matchup Context.

This test is intentionally lightweight:
- It must pass even when nflverse schedules data is not present.
- It validates schema and opponent-map building.
"""

from __future__ import annotations


def test_get_todays_matchups_has_minimum_schema():
    from nfl_menu import get_todays_matchups

    matchups = get_todays_matchups(today=None)
    assert isinstance(matchups, list)
    assert len(matchups) > 0

    m = matchups[0]
    assert isinstance(m, dict)
    assert "away" in m and "home" in m


def test_build_opponent_map_from_matchups_roundtrips():
    from nfl_menu import build_opponent_map_from_matchups

    matchups = [
        {"away": "BUF", "home": "KC"},
        {"away": "DAL", "home": "PHI"},
    ]
    opp = build_opponent_map_from_matchups(matchups)

    assert opp["BUF"] == "KC"
    assert opp["KC"] == "BUF"
    assert opp["DAL"] == "PHI"
    assert opp["PHI"] == "DAL"
