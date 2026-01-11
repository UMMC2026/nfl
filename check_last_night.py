"""Check games from last night (January 6, 2026)"""
import requests
from datetime import datetime, timedelta

# Check January 6
date = "20260106"
print(f"🏀 Checking NBA games for January 6, 2026\n")

r = requests.get(
    'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
    params={'dates': date}
)

if r.status_code == 200:
    data = r.json()
    games = data.get('events', [])
    
    print(f"Found {len(games)} games:\n")
    
    for game in games:
        status = game['competitions'][0]['status']['type']
        home = game['competitions'][0]['competitors'][0]
        away = game['competitions'][0]['competitors'][1]
        
        print(f"{away['team']['abbreviation']} @ {home['team']['abbreviation']}")
        print(f"  Status: {status['state']} - {status.get('detail', 'N/A')}")
        
        if status['state'] == 'post':
            print(f"  Score: {away['team']['abbreviation']} {away['score']} - {home['team']['abbreviation']} {home['score']}")
        
        print()
else:
    print(f"Error: {r.status_code}")
