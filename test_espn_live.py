#!/usr/bin/env python3
"""Test ESPN NFL API endpoints to identify working ones."""

import urllib.request
import ssl
import json

def fetch(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return json.loads(r.read())

print("=" * 60)
print("ESPN NFL API ENDPOINT TEST")
print("=" * 60)

# 1. Scoreboard (current week games)
print("\n[1] SCOREBOARD - Current Week Games")
try:
    data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard")
    events = data.get("events", [])
    print(f"    Found {len(events)} games")
    for e in events[:3]:
        name = e.get("name", "?")
        print(f"    - {name}")
except Exception as ex:
    print(f"    ERROR: {ex}")

# 2. Teams list
print("\n[2] TEAMS LIST")
try:
    data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams")
    teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    print(f"    Found {len(teams)} teams")
    team_ids = {}
    for t in teams:
        team = t.get("team", {})
        abbr = team.get("abbreviation", "?")
        tid = team.get("id", "?")
        team_ids[abbr] = tid
    print(f"    Examples: PIT={team_ids.get('PIT')}, CLE={team_ids.get('CLE')}, IND={team_ids.get('IND')}")
except Exception as ex:
    print(f"    ERROR: {ex}")

# 3. Team roster (using Pittsburgh)
print("\n[3] TEAM ROSTER - Pittsburgh Steelers")
try:
    data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/23/roster")
    athletes = data.get("athletes", [])
    print(f"    Found {len(athletes)} position groups")
    for group in athletes[:3]:
        pos = group.get("position", "?")
        items = group.get("items", [])
        print(f"    {pos}: {len(items)} players")
        for p in items[:2]:
            name = p.get("fullName", "?")
            jersey = p.get("jersey", "?")
            print(f"        #{jersey} {name}")
except Exception as ex:
    print(f"    ERROR: {ex}")

# 4. Individual player stats (testing with a known player ID)
print("\n[4] PLAYER STATS - Najee Harris (ID: 4241457)")
try:
    data = fetch("https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/4241457")
    athlete = data.get("athlete", {})
    name = athlete.get("fullName", "?")
    team = athlete.get("team", {}).get("abbreviation", "?")
    stats = data.get("statistics", {})
    print(f"    {name} ({team})")
    
    # Look for rushing stats
    for cat in stats.get("splits", {}).get("categories", []):
        cat_name = cat.get("name", "")
        if "rushing" in cat_name.lower():
            for stat in cat.get("stats", [])[:3]:
                label = stat.get("label", "?")
                val = stat.get("value", "?")
                print(f"    {label}: {val}")
except Exception as ex:
    print(f"    ERROR: {ex}")

# 5. Season leaders (alternative endpoint)
print("\n[5] STATISTICS ENDPOINT")
try:
    data = fetch("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2024/types/2/leaders?limit=5")
    categories = data.get("categories", [])
    print(f"    Found {len(categories)} stat categories")
    for cat in categories[:3]:
        name = cat.get("name", "?")
        leaders = cat.get("leaders", [])[:2]
        print(f"    {name}:")
        for ldr in leaders:
            athlete = ldr.get("athlete", {})
            player_name = athlete.get("fullName", "?")
            value = ldr.get("value", "?")
            print(f"        {player_name}: {value}")
except Exception as ex:
    print(f"    ERROR: {ex}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
