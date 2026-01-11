#!/usr/bin/env python3
"""Check ESPN roster API structure for stats."""

import urllib.request
import ssl
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return json.loads(r.read())

# Check team roster
print("=" * 60)
print("Checking PIT roster structure...")
data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/23/roster?season=2024")

athletes = data.get("athletes", [])
print(f"Position groups: {len(athletes)}")

for group in athletes:
    print(f"\n{group.get('position', 'Unknown')} group:")
    for player in group.get("items", [])[:2]:
        print(f"  {player.get('fullName', '?')}")
        print(f"    Keys: {list(player.keys())}")
        
        # Check for stats
        stats = player.get("statistics", {})
        if stats:
            print(f"    Stats: {stats}")
        else:
            print("    [No inline stats]")
        break  # Only check first player

# Check individual player stats API
print("\n" + "=" * 60)
print("Checking individual player stats API...")
print("Testing Najee Harris (4241457)...")

data = fetch("https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/4241457")
print(f"Keys: {list(data.keys())}")

athlete = data.get("athlete", {})
print(f"Athlete: {athlete.get('fullName', '?')} - {athlete.get('team', {}).get('abbreviation', '?')}")

stats = data.get("statistics", {})
print(f"Stats keys: {list(stats.keys()) if stats else 'None'}")

splits = stats.get("splits", {})
if splits:
    print(f"Splits keys: {list(splits.keys())}")
    categories = splits.get("categories", [])
    print(f"Categories: {len(categories)}")
    for cat in categories[:3]:
        print(f"  {cat.get('name', '?')}")
        for stat in cat.get("stats", [])[:2]:
            print(f"    {stat.get('label', '?')}: {stat.get('value', '?')}")

# Check team stats page  
print("\n" + "=" * 60)
print("Checking team statistics API...")

try:
    data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/23/statistics?season=2024")
    print(f"Keys: {list(data.keys())}")
except Exception as e:
    print(f"Error: {e}")

# Check alternate team stats
print("\n" + "=" * 60)  
print("Checking team stats in summary...")

try:
    data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/23?season=2024")
    print(f"Keys: {list(data.keys())}")
    
    team = data.get("team", {})
    print(f"Team keys: {list(team.keys())}")
    
    record = team.get("record", {})
    print(f"Record: {record}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("DONE")
