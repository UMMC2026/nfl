#!/usr/bin/env python3
"""Check ESPN for player-level stats from a team."""

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

# Check the site leaders endpoint directly
print("=" * 60)
print("NFL SITE LEADERS (Player-level stats)")

data = fetch("https://site.api.espn.com/apis/site/v3/sports/football/nfl/leaders?limit=50")
print(f"Keys: {list(data.keys())}")

leaders = data.get("leaders", [])
print(f"\nLeader categories: {len(leaders)}")

for cat in leaders[:6]:
    cat_name = cat.get("name", "?")
    print(f"\n{cat_name}:")
    
    for player in cat.get("leaders", [])[:3]:
        athlete = player.get("athlete", {})
        name = athlete.get("displayName", "?")
        team = athlete.get("team", {}).get("abbreviation", "?")
        value = player.get("displayValue", player.get("value", "?"))
        print(f"  {name} ({team}): {value}")
