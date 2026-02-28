#!/usr/bin/env python3
"""Test Mbappe in La Liga (he's at Real Madrid now, not PSG)."""
import requests
import time

key = '29f5fe801b18ad08ee502e5d7b4612d2'
headers = {'X-RapidAPI-Key': key, 'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'}
url = 'https://api-football-v1.p.rapidapi.com/v3/players'

# Mbappe is at Real Madrid in La Liga (140), not Ligue 1 anymore
params = {'search': 'Mbappe', 'league': '140', 'season': '2024'}
print("Fetching Mbappe from La Liga (Real Madrid)...")

r = requests.get(url, headers=headers, params=params)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    d = r.json()
    results = d.get('response', [])
    print(f"Results found: {len(results)}")
    
    if results:
        p = results[0]
        print(f"Player: {p['player']['name']}")
        s = p['statistics'][0]
        print(f"Team: {s['team']['name']}")
        gp = s['games']['appearences'] or 1
        sot = s['shots']['on'] or 0
        passes = s['passes']['total'] or 0
        shots = s['shots']['total'] or 0
        print(f"GP: {gp} | SOT: {sot} ({sot/gp:.1f}/g) | Passes: {passes} ({passes/gp:.1f}/g) | Shots: {shots}")
else:
    print(f"Error: {r.text[:500]}")
