#!/usr/bin/env python3
"""Verify 2025 NFL season stats from ESPN."""

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

print("=" * 60)
print("2025 NFL SEASON LEADERS (Current Season)")
print("=" * 60)

data = fetch("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2025/types/2/leaders?limit=5")

for cat in data.get("categories", [])[:6]:
    name = cat.get("name", "?")
    print(f"\n{name}:")
    
    for ldr in cat.get("leaders", [])[:3]:
        athlete_ref = ldr.get("athlete", {}).get("$ref", "")
        team_ref = ldr.get("team", {}).get("$ref", "")
        value = ldr.get("value", "?")
        
        if athlete_ref:
            athlete = fetch(athlete_ref)
            aname = athlete.get("displayName", "?")
            
            team_abbr = "?"
            if team_ref:
                team = fetch(team_ref)
                team_abbr = team.get("abbreviation", "?")
            
            print(f"  {aname} ({team_abbr}): {value}")

print("\n" + "=" * 60)
print("Current Week Schedule:")
print("=" * 60)

schedule = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard")
week = schedule.get("week", {}).get("number", "?")
print(f"Week {week}")

for event in schedule.get("events", [])[:5]:
    name = event.get("name", "?")
    status = event.get("status", {}).get("type", {}).get("description", "?")
    print(f"  {name} - {status}")
