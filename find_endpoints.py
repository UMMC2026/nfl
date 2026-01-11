#!/usr/bin/env python3
"""Find working ESPN endpoints for player stats."""

import urllib.request
import ssl
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return None

endpoints = [
    # Scoreboard has game stats
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    # Summary for a specific athlete
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?athletes=3139477",
    # Athletes search
    "https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/3139477/splits",
    # Core API leaders
    "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2024/types/2/leaders?limit=10",
]

for url in endpoints:
    print(f"\n{'=' * 60}")
    print(f"Testing: {url[:80]}...")
    data = fetch(url)
    if data:
        print(f"  SUCCESS - Keys: {list(data.keys())[:5]}")
        
        # Check for useful data
        if "events" in data:
            print(f"  Has {len(data['events'])} events")
        if "categories" in data:
            print(f"  Has {len(data['categories'])} categories")
            for cat in data["categories"][:3]:
                name = cat.get("name", "?")
                leaders = cat.get("leaders", [])
                print(f"    {name}: {len(leaders)} leaders")
    else:
        print("  FAILED")

# Try the core API leaders with a specific category
print("\n" + "=" * 60)
print("Testing core API passing leaders...")
data = fetch("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2024/types/2/leaders?limit=20")
if data:
    cats = data.get("categories", [])
    for cat in cats[:4]:
        name = cat.get("name", "?")
        leaders = cat.get("leaders", [])[:3]
        print(f"\n{name}:")
        for ldr in leaders:
            athlete_ref = ldr.get("athlete", {}).get("$ref", "")
            value = ldr.get("value", "?")
            # Fetch athlete name from ref
            if athlete_ref:
                athlete_data = fetch(athlete_ref)
                if athlete_data:
                    aname = athlete_data.get("displayName", "?")
                    team_ref = ldr.get("team", {}).get("$ref", "")
                    team_abbr = "?"
                    if team_ref:
                        team_data = fetch(team_ref)
                        if team_data:
                            team_abbr = team_data.get("abbreviation", "?")
                    print(f"  {aname} ({team_abbr}): {value}")
