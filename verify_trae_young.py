"""Check if Trae Young actually played on Jan 6"""
import requests

print("🔍 INVESTIGATING TRAE YOUNG - JANUARY 6, 2026\n")
print("="*80)

# Check Hawks schedule for Jan 6
r = requests.get(
    'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
    params={'dates': '20260106'}
)

if r.status_code == 200:
    games = r.json().get('events', [])
    
    # Look for Hawks game
    hawks_game = None
    for game in games:
        for comp in game['competitions']:
            for team in comp['competitors']:
                if team['team']['abbreviation'] == 'ATL':
                    hawks_game = game
                    break
    
    if hawks_game:
        print("✅ HAWKS GAME FOUND:")
        home = hawks_game['competitions'][0]['competitors'][0]
        away = hawks_game['competitions'][0]['competitors'][1]
        print(f"   {away['team']['abbreviation']} @ {home['team']['abbreviation']}")
        print(f"   Status: {hawks_game['competitions'][0]['status']['type']['state']}")
        print(f"   Score: {away['score']} - {home['score']}")
    else:
        print("❌ NO HAWKS GAME ON JANUARY 6, 2026")
        print("\nHawks did not play on this date.")
        print("This confirms Trae Young DID NOT PLAY.\n")
        print("⚠️  SerpApi returned incorrect data - likely from a different date.")

print("\n" + "="*80)
