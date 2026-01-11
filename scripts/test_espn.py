"""Test ESPN NFL data fetcher."""
from ufa.ingest.espn_nfl import ESPNFetcher, get_verified_starters_for_teams

def main():
    print("=" * 60)
    print("ESPN NFL DATA FETCHER - LIVE TEST")
    print("=" * 60)
    
    fetcher = ESPNFetcher()
    
    # Test 1: Week 17 schedule
    print("\n📅 WEEK 17 SCHEDULE (2024)")
    print("-" * 40)
    try:
        games = fetcher.get_week_schedule(17, 2024)
        print(f"Found {len(games)} games:")
        for game in games:
            print(f"  {game['away']} @ {game['home']} - {game['status']}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 2: QB Starters for key teams
    print("\n🏈 VERIFIED QB STARTERS")
    print("-" * 40)
    test_teams = ["PIT", "CLE", "JAX", "IND"]
    for team in test_teams:
        try:
            qb = fetcher.get_qb_starter(team)
            if qb:
                status = f"(#{qb.jersey})" if qb.jersey else ""
                print(f"  {team}: {qb.name} {status}")
            else:
                print(f"  {team}: Could not determine")
        except Exception as e:
            print(f"  {team}: ERROR - {e}")
    
    # Test 3: Full skill position starters
    print("\n👥 SKILL POSITION STARTERS")
    print("-" * 40)
    try:
        starters = get_verified_starters_for_teams(test_teams)
        for team, positions in starters.items():
            print(f"\n  {team}:")
            if "error" in positions:
                print(f"    ERROR: {positions['error']}")
            else:
                for pos, info in positions.items():
                    if isinstance(info, dict) and "name" in info:
                        print(f"    {pos}: {info['name']}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 4: Player search
    print("\n🔍 PLAYER SEARCH TEST")
    print("-" * 40)
    test_players = ["Jonathan Taylor", "Jaylen Warren", "Brian Thomas Jr"]
    for name in test_players:
        try:
            results = fetcher.search_player(name)
            if results:
                p = results[0]
                print(f"  {name}: Found as {p.get('name')} ({p.get('team')} {p.get('position')})")
            else:
                print(f"  {name}: Not found")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")
    
    # Test 5: Starter validation
    print("\n✓ STARTER VALIDATION")
    print("-" * 40)
    validations = [
        ("Russell Wilson", "PIT", "QB"),  # Old rumor - check if still valid
        ("Aaron Rodgers", "PIT", "QB"),    # Correct as of late 2024
        ("Mac Jones", "JAX", "QB"),         # Should be starter
        ("Trevor Lawrence", "JAX", "QB"),   # On IR
        ("Jonathan Taylor", "IND", "RB"),
    ]
    for name, team, pos in validations:
        try:
            is_valid, msg = fetcher.validate_starter(name, team, pos)
            status = "✓" if is_valid else "✗"
            print(f"  {status} {name} ({team} {pos}): {msg}")
        except Exception as e:
            print(f"  ? {name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
