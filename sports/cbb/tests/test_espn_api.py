"""Test ESPN CBB API data retrieval."""

import sys
import os

import pytest

sys.path.insert(0, "c:/Users/hiday/UNDERDOG ANANLYSIS")

from sports.cbb.ingest.cbb_data_provider import CBBDataProvider


def test_major_players():
    """Test ESPN API with major conference players."""
    if os.environ.get("CBB_OFFLINE") == "1":
        pytest.skip("CBB_OFFLINE=1 (skipping ESPN network test)")
    if os.environ.get("CBB_RUN_ESPN_TESTS", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("Set CBB_RUN_ESPN_TESTS=1 to enable ESPN network tests")

    print("=" * 60)
    print("ESPN CBB API TEST - Major Conference Players")
    print("=" * 60)
    
    provider = CBBDataProvider()
    
    # Test major conference players (2025-26 season stars)
    test_players = [
        ("Cooper Flagg", "Duke"),
        ("RJ Davis", "North Carolina"),
        ("Mark Sears", "Alabama"),
        ("Hunter Dickinson", "Kansas"),
        ("Johni Broome", "Auburn"),
        ("Dylan Harper", "Rutgers"),
    ]
    
    found = 0
    for name, team in test_players:
        stats = provider.get_player_stats_by_name(name, team)
        if stats:
            print(
                f"  [OK] {name} ({team}): "
                f"PPG={stats.points_per_game:.1f}, RPG={stats.rebounds_per_game:.1f}, APG={stats.assists_per_game:.1f}"
            )
            found += 1
        else:
            print(f"  [--] {name} ({team}): NO DATA")
    
    print(f"\nFound: {found}/{len(test_players)} players")
    assert found > 0


def test_team_roster():
    """Test fetching team roster."""
    if os.environ.get("CBB_OFFLINE") == "1":
        pytest.skip("CBB_OFFLINE=1 (skipping ESPN network test)")
    if os.environ.get("CBB_RUN_ESPN_TESTS", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("Set CBB_RUN_ESPN_TESTS=1 to enable ESPN network tests")

    print("\n" + "=" * 60)
    print("ESPN CBB API TEST - Team Roster")
    print("=" * 60)
    
    provider = CBBDataProvider()
    
    # Try Duke
    roster = provider.get_team_roster("Duke")
    if roster:
        print(f"  Duke roster: {len(roster)} players")
        for p in roster[:5]:
            if isinstance(p, dict):
                name = p.get("name", "Unknown")
            else:
                name = getattr(p, "name", "Unknown")
            print(f"    - {name}")
    else:
        print("  Duke roster: NO DATA")

    assert roster, "Expected non-empty roster for Duke"


if __name__ == "__main__":
    test_major_players()
    test_team_roster()
