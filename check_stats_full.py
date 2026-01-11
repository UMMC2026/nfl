#!/usr/bin/env python3
"""Check ESPN team statistics endpoint - detailed view."""

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

# Team statistics
print("=" * 60)
print("PIT Team Statistics - Full Structure")
data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/23/statistics?season=2024")

results = data.get("results", {})
team_stats = results.get("stats", {})

print(f"Team: {team_stats.get('name', '?')}")
print(f"Categories available: {len(team_stats.get('categories', []))}")

for cat in team_stats.get("categories", []):
    cat_name = cat.get("displayName", "?")
    print(f"\n{cat_name}:")
    
    for stat in cat.get("stats", [])[:5]:
        stat_name = stat.get("displayName", stat.get("name", "?"))
        value = stat.get("displayValue", stat.get("value", "?"))
        desc = stat.get("description", "")
        print(f"  {stat_name}: {value}")
        
        # Check for leaders in each stat
        leaders = stat.get("leaders", [])
        if leaders:
            print(f"    Leaders:")
            for ldr in leaders[:2]:
                athlete = ldr.get("athlete", {})
                aname = athlete.get("displayName", "?")
                aval = ldr.get("displayValue", "?")
                print(f"      {aname}: {aval}")
