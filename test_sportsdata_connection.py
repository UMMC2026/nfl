"""
Test Sportsdata.io API connection
"""
import os
from dotenv import load_dotenv
from ufa.analysis.learning_integration import SportsDataAPI

# Load environment variables
load_dotenv()

api_key = os.getenv('SPORTSDATA_API_KEY')

if not api_key or api_key == 'your_sportsdata_api_key_here':
    print("❌ SPORTSDATA_API_KEY not set in .env file")
    exit(1)

print(f"🔑 Using API key: {api_key[:10]}...")

# Test connection
try:
    api = SportsDataAPI(api_key)
    
    # Try to fetch games for a recent date
    print("📡 Testing API connection...")
    games = api.get_games_by_date('20260105')  # January 5, 2026
    
    print(f"✅ Sportsdata.io Connected Successfully!")
    print(f"📊 Found {len(games)} NBA games on 2026-01-05")
    
    if games:
        print(f"\nSample game:")
        game = games[0]
        print(f"  {game.away_team} @ {game.home_team}")
        print(f"  Status: {game.status}")
        if game.home_score:
            print(f"  Score: {game.away_team} {game.away_score}, {game.home_team} {game.home_score}")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()
