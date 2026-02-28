"""Quick test of CBB data provider."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sports.cbb.ingest.cbb_data_provider import CBBDataProvider, ESPNCBBFetcher

def main():
    print("=" * 60)
    print("CBB DATA PROVIDER TEST")
    print("=" * 60)
    
    provider = CBBDataProvider()
    fetcher = ESPNCBBFetcher()
    
    # Test 1: Today's games
    print("\n[1] Today's Games:")
    print("-" * 40)
    games = provider.get_todays_games()
    print(f"Found {len(games)} games")
    for game in games[:5]:
        spread_str = f"Spread: {game.spread}" if game.spread else "No spread"
        print(f"  {game.away_team} @ {game.home_team} | {spread_str}")
    
    # Test 2: Get a team roster (Illinois is playing today)
    print("\n[2] Team Roster (Illinois):")
    print("-" * 40)
    
    # Illinois team ID
    illinois_id = "356"  # ESPN ID for Illinois
    roster_raw = fetcher.get_team_roster(illinois_id)
    print(f"Found {len(roster_raw)} players on roster")
    
    for player in roster_raw[:5]:
        if isinstance(player, dict):
            name = player.get("displayName", "Unknown")
            pos = player.get("position", {})
            pos_abbr = pos.get("abbreviation", "?") if pos else "?"
            jersey = player.get("jersey", "?")
            print(f"  #{jersey} {name} ({pos_abbr})")
        else:
            # It's a CBBPlayer object
            print(f"  {player.name} - PPG: {player.points_per_game}, RPG: {player.rebounds_per_game}")
    
    # Test 3: Get player via data provider
    print("\n[3] Player Lookup via Provider:")
    print("-" * 40)
    
    # Test with a known player - Illinois Terrence Shannon Jr.
    test_players = [
        ("Terrence Shannon Jr.", "ILL"),
        ("R.J. Davis", "UNC"),
        ("Kasparas Jakucionis", "ILL"),
    ]
    
    for player_name, team in test_players:
        player = provider.get_player_stats_by_name(player_name, team)
        if player:
            print(f"\n  {player.name} ({player.team}):")
            print(f"    PPG: {player.points_per_game}")
            print(f"    RPG: {player.rebounds_per_game}")
            print(f"    APG: {player.assists_per_game}")
            print(f"    MPG: {player.minutes_per_game}")
            print(f"    GP:  {player.games_played}")
            
            # Test get_player_mean
            pts_mean = provider.get_player_mean(player_name, "points", team)
            print(f"    get_player_mean(points): {pts_mean}")
        else:
            print(f"\n  {player_name} ({team}): NOT FOUND")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
