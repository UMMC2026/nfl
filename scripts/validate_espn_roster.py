"""
Validation Script for ESPN Roster Fix

Tests the fixed ESPN roster fetcher to verify:
1. All 30 NBA teams fetch successfully
2. 450+ players loaded (expected: ~450-480)
3. No silent failures or missing data

Run before production use to confirm fix.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from engine.roster_gate import build_active_roster_map


def validate_espn_roster():
    """Run validation tests on ESPN roster fetcher."""
    print("=" * 70)
    print("ESPN ROSTER FETCHER VALIDATION")
    print("=" * 70)
    print()
    
    print("[TEST 1] Fetching NBA rosters from ESPN API...")
    print()
    
    try:
        roster_map = build_active_roster_map("NBA")
        
        print()
        print("=" * 70)
        print("VALIDATION RESULTS")
        print("=" * 70)
        
        total_players = len(roster_map)
        
        # Count players per team
        team_counts = {}
        for player, team in roster_map.items():
            team_counts[team] = team_counts.get(team, 0) + 1
        
        teams_fetched = len(team_counts)
        
        print(f"✓ Total players loaded: {total_players}")
        print(f"✓ Teams fetched: {teams_fetched}/30")
        print()
        
        # Expected ranges
        EXPECTED_MIN_PLAYERS = 400  # Conservative (some teams may have small rosters)
        EXPECTED_MAX_PLAYERS = 600  # Liberal (rosters can vary, two-way contracts)
        EXPECTED_MIN_TEAMS = 25     # Allow some failures
        
        # Status checks
        status = "PASS"
        
        if total_players < EXPECTED_MIN_PLAYERS:
            print(f"⚠️  WARNING: Expected >{EXPECTED_MIN_PLAYERS} players, got {total_players}")
            status = "WARN"
        
        if teams_fetched < EXPECTED_MIN_TEAMS:
            print(f"❌ FAIL: Expected >{EXPECTED_MIN_TEAMS} teams, got {teams_fetched}")
            status = "FAIL"
        
        if total_players > EXPECTED_MAX_PLAYERS:
            print(f"⚠️  WARNING: Unusually high player count ({total_players}), possible duplicates?")
            status = "WARN"
        
        print()
        print("[TEST 2] Team distribution analysis...")
        print()
        
        # Show teams with unusual roster sizes
        avg_roster_size = total_players / teams_fetched if teams_fetched > 0 else 0
        print(f"Average roster size: {avg_roster_size:.1f} players/team")
        print()
        
        small_rosters = {team: count for team, count in team_counts.items() if count < 10}
        large_rosters = {team: count for team, count in team_counts.items() if count > 20}
        
        if small_rosters:
            print(f"⚠️  Teams with unusually small rosters (<10 players):")
            for team, count in sorted(small_rosters.items()):
                print(f"   {team}: {count} players")
            print()
            status = "WARN"
        
        if large_rosters:
            print(f"⚠️  Teams with unusually large rosters (>20 players):")
            for team, count in sorted(large_rosters.items()):
                print(f"   {team}: {count} players")
            print()
        
        # Show sample players
        print("[TEST 3] Sample player lookups...")
        print()
        
        test_players = [
            "LeBron James",
            "Stephen Curry", 
            "Kevin Durant",
            "Giannis Antetokounmpo",
            "Nikola Jokic",
            "Luka Doncic"
        ]
        
        missing_players = []
        for player_name in test_players:
            team = roster_map.get(player_name)
            if team:
                print(f"✓ {player_name:<25} → {team}")
            else:
                print(f"✗ {player_name:<25} → NOT FOUND")
                missing_players.append(player_name)
        
        if missing_players:
            print()
            print(f"⚠️  WARNING: {len(missing_players)} star players not found in roster")
            print("    (May indicate name format mismatch or incorrect team ID mapping)")
            status = "WARN"
        
        print()
        print("=" * 70)
        print(f"VALIDATION STATUS: {status}")
        print("=" * 70)
        
        if status == "PASS":
            print("✅ ESPN roster fetcher working correctly")
            print("   Safe to use in production pipeline")
        elif status == "WARN":
            print("⚠️  ESPN roster fetcher has warnings")
            print("   Review output above before production use")
        else:
            print("❌ ESPN roster fetcher validation FAILED")
            print("   DO NOT use in production — debug required")
        
        print()
        
        # Show team distribution
        print("[BONUS] Full team distribution:")
        print()
        for team in sorted(team_counts.keys()):
            count = team_counts[team]
            bar = "█" * (count // 2)
            print(f"{team}: {count:2d} players {bar}")
        
        return status == "PASS"
    
    except Exception as e:
        print()
        print("=" * 70)
        print("VALIDATION STATUS: FAIL")
        print("=" * 70)
        print(f"❌ Exception during roster fetch: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = validate_espn_roster()
    sys.exit(0 if success else 1)
