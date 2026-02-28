#!/usr/bin/env python3
"""Quick API test for soccer stats."""
import requests
import os

# Set API key
os.environ['RAPIDAPI_KEY'] = '29f5fe801b18ad08ee502e5d7b4612d2'
key = os.environ['RAPIDAPI_KEY']

print(f"Testing API key: {key[:8]}...")
print("="*60)

# Leagues
LEAGUES = {
    'Ligue 1': '61',
    'La Liga': '140', 
    'EPL': '39',
    'Bundesliga': '78',
    'Serie A': '135'
}

headers = {
    'X-RapidAPI-Key': key,
    'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
}

def get_player(name, league_id):
    """Fetch player stats."""
    url = 'https://api-football-v1.p.rapidapi.com/v3/players'
    params = {'search': name, 'league': league_id, 'season': '2024'}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        data = r.json()
        if data['response']:
            return data['response'][0]
    return None

# Test key players from slate
players = [
    ('Mbappe', '61'),      # Ligue 1
    ('Bellingham', '140'), # La Liga
    ('Vinicius', '140'),   # La Liga
    ('Dembele', '61'),     # Ligue 1
    ('Simons', '39'),      # EPL (on loan to Spurs?)
]

print("\n🔍 FETCHING REAL PLAYER STATS...")
print("-"*60)

for name, league in players:
    p = get_player(name, league)
    if p:
        s = p['statistics'][0]
        player_name = p['player']['name']
        team = s['team']['name']
        gp = s['games']['appearences'] or 1
        sot = s['shots']['on'] or 0
        passes = s['passes']['total'] or 0
        shots = s['shots']['total'] or 0
        dribbles = s['dribbles']['attempts'] or 0
        
        print(f"\n✅ {player_name} ({team})")
        print(f"   GP: {gp} | SOT: {sot} ({sot/gp:.1f}/g) | Shots: {shots} ({shots/gp:.1f}/g)")
        print(f"   Passes: {passes} ({passes/gp:.1f}/g) | Dribbles: {dribbles} ({dribbles/gp:.1f}/g)")
    else:
        print(f"\n❌ {name} - Not found in league {league}")

print("\n" + "="*60)
print("API Test Complete!")
