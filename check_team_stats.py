#!/usr/bin/env python3
"""Check ESPN team statistics endpoint."""

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
print("PIT Team Statistics")
data = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/23/statistics?season=2024")

results = data.get("results", {})
print(f"Results keys: {list(results.keys())}")

# Check team stats categories
team_stats = results.get("stats", {})
if team_stats:
    print(f"Stats categories: {list(team_stats.keys())}")
else:
    # Try alternate structure
    for key, val in results.items():
        if isinstance(val, dict):
            print(f"{key}: {list(val.keys())[:5]}")
        elif isinstance(val, list) and val:
            print(f"{key}: [{val[0] if len(val) > 0 else '?'}...]")

# Check splits
splits = results.get("splits", [])
if splits:
    print(f"\nSplits: {len(splits)}")
    for split in splits[:3]:
        print(f"  {split.get('displayName', '?')}")
        categories = split.get("categories", [])
        for cat in categories[:2]:
            print(f"    {cat.get('displayName', '?')}")
            stats = cat.get("stats", [])
            for s in stats[:3]:
                print(f"      {s.get('displayName', '?')}: {s.get('value', '?')}")

# Try looking at athletes in results
athletes = results.get("athletes", [])
if athletes:
    print(f"\nAthletes: {len(athletes)}")
    for a in athletes[:5]:
        print(f"  {a.get('athlete', {}).get('displayName', '?')}")
        for cat in a.get("categories", [])[:2]:
            print(f"    {cat.get('displayName', '?')}")

# Alternative - check the leaders within team
print("\n" + "=" * 60)
print("Team leaders...")
leaders = results.get("leaders", [])
if leaders:
    for leader in leaders[:5]:
        print(f"{leader.get('displayName', '?')}:")
        for ldr in leader.get("leaders", [])[:2]:
            athlete = ldr.get("athlete", {})
            value = ldr.get("displayValue", "?")
            print(f"  {athlete.get('displayName', '?')}: {value}")
