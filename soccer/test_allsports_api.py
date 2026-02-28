"""
AllSportsAPI2 Evaluation Script
Tests if API has sufficient data for soccer props system
"""
import requests
import json
from datetime import datetime
import os
from pathlib import Path

# Try to get API key from .env
def get_api_key():
    api_key = os.environ.get('RAPIDAPI_KEY')
    if not api_key:
        env_file = Path(__file__).parent.parent / '.env'
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith('RAPIDAPI_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    break
    return api_key

RAPIDAPI_KEY = get_api_key()

if not RAPIDAPI_KEY:
    print("❌ ERROR: RAPIDAPI_KEY not found in environment or .env file")
    print("   Add to .env: RAPIDAPI_KEY=your_key_here")
    exit(1)

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "allsportsapi2.p.rapidapi.com"
}

def test_player_search():
    """Test 1: Can we find players?"""
    print("\n" + "="*60)
    print("TEST 1: Player Search")
    print("="*60)
    
    test_players = [
        "Cole Palmer",    # Chelsea
        "Mohamed Salah",  # Liverpool
        "Erling Haaland"  # Man City
    ]
    
    for player_name in test_players:
        url = "https://allsportsapi2.p.rapidapi.com/api/soccer/search/player"
        params = {"query": player_name}
        
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            data = response.json()
            
            print(f"\n🔍 Searching: {player_name}")
            print(f"   Status: {response.status_code}")
            print(f"   Results: {len(data.get('players', []))} found")
            
            if data.get('players'):
                player = data['players'][0]
                print(f"   ✅ Found: {player.get('name')} - {player.get('team', 'No team')}")
                print(f"   Player ID: {player.get('id')}")
                return player.get('id')  # Return first player ID for next test
            else:
                print(f"   ❌ Not found")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return None

def test_player_statistics(player_id):
    """Test 2: Can we get match logs with shots data?"""
    print("\n" + "="*60)
    print("TEST 2: Player Statistics (CRITICAL)")
    print("="*60)
    
    if not player_id:
        print("   ⚠️  Skipping - no player ID from previous test")
        return False
    
    url = "https://allsportsapi2.p.rapidapi.com/api/soccer/player/statistics"
    params = {
        "playerId": player_id,
        "season": "2024"
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = response.json()
        
        print(f"\n📊 Player ID: {player_id}")
        print(f"   Status: {response.status_code}")
        
        # Save full response for inspection
        output_file = Path(__file__).parent / "outputs" / "allsports_sample.json"
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"   ✅ Full response saved to: {output_file}")
        
        # Check for critical fields
        print("\n🔍 Checking for REQUIRED fields:")
        
        data_str = json.dumps(data).lower()
        checks = {
            "Match logs": "matches" in data or "games" in data or "statistics" in data,
            "Shots data": "shot" in data_str,
            "Shots on target": "target" in data_str or "on target" in data_str,
            "Team info": "team" in data_str,
            "Season 2024": "2024" in str(data),
        }
        
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
        
        return all(checks.values())
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_league_coverage():
    """Test 3: Which leagues are supported?"""
    print("\n" + "="*60)
    print("TEST 3: League Coverage")
    print("="*60)
    
    url = "https://allsportsapi2.p.rapidapi.com/api/soccer/leagues"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        print(f"\n🏆 Status: {response.status_code}")
        
        # Save response
        output_file = Path(__file__).parent / "outputs" / "allsports_leagues.json"
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"   Saved to: {output_file}")
        
        # Look for Big 5 leagues
        target_leagues = [
            "Premier League", "EPL", "England",
            "La Liga", "Spain",
            "Serie A", "Italy",
            "Bundesliga", "Germany",
            "Ligue 1", "France"
        ]
        
        found_leagues = []
        if 'leagues' in data:
            for league in data.get('leagues', [])[:20]:  # Show first 20
                league_name = league.get('name', '')
                print(f"   - {league_name} (ID: {league.get('id')})")
                if any(target.lower() in league_name.lower() for target in target_leagues):
                    found_leagues.append(league_name)
        
        print(f"\n   Found {len(found_leagues)} Big 5 leagues")
        
        if len(found_leagues) >= 3:
            print(f"   ✅ Good coverage")
            return True
        else:
            print(f"   ⚠️  Limited coverage")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_match_detail():
    """Test 4: Can we get live match data?"""
    print("\n" + "="*60)
    print("TEST 4: Match Detail (Check data structure)")
    print("="*60)
    
    url = "https://allsportsapi2.p.rapidapi.com/api/soccer/matches/live"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        print(f"\n⚽ Live matches: {len(data.get('matches', []))}")
        
        if data.get('matches'):
            match = data['matches'][0]
            print(f"   Sample: {match.get('homeTeam', {}).get('name', 'Home')} vs {match.get('awayTeam', {}).get('name', 'Away')}")
            print(f"   Match ID: {match.get('id')}")
            
            # Test getting match detail
            match_url = "https://allsportsapi2.p.rapidapi.com/api/soccer/match/detail"
            match_params = {"matchId": match.get('id')}
            
            detail_response = requests.get(match_url, headers=HEADERS, params=match_params, timeout=10)
            detail_data = detail_response.json()
            
            output_file = Path(__file__).parent / "outputs" / "allsports_match_sample.json"
            with open(output_file, "w") as f:
                json.dump(detail_data, f, indent=2)
            print(f"   ✅ Match detail saved to: {output_file}")
            return True
        else:
            print("   ⚠️  No live matches right now (not a deal breaker)")
            return True  # Not critical
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("ALLSPORTSAPI2 EVALUATION - SOCCER PROPS SYSTEM")
    print("="*70)
    print(f"Testing at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    player_id = test_player_search()
    
    results = {
        "Player Search": player_id is not None,
        "Player Statistics": test_player_statistics(player_id) if player_id else False,
        "League Coverage": test_league_coverage(),
        "Match Detail": test_match_detail()
    }
    
    # Summary
    print("\n" + "="*70)
    print("FINAL VERDICT")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passing_tests = sum(results.values())
    total_tests = len(results)
    
    print(f"\nScore: {passing_tests}/{total_tests}")
    
    if passing_tests >= 3:
        print("\n✅ RECOMMENDATION: AllSportsAPI2 is viable for integration")
        print("   Next step: Build adapter in soccer/allsportsapi_integration.py")
    elif passing_tests >= 2:
        print("\n⚠️  RECOMMENDATION: Partial support - may need hybrid approach")
        print("   Consider using for specific leagues only")
    else:
        print("\n❌ RECOMMENDATION: Stick with API-Football")
        print("   AllSportsAPI2 doesn't meet minimum requirements")
    
    print("\n📁 Check saved files in soccer/outputs/:")
    print("   - allsports_sample.json (player stats)")
    print("   - allsports_leagues.json (league list)")
    print("   - allsports_match_sample.json (match detail)")
    print("\nReview these files to see exact data structure.")

if __name__ == "__main__":
    main()
