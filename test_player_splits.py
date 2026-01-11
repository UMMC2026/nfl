#!/usr/bin/env python3
"""Test getting player stats from athlete splits endpoint."""

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
    except:
        return None

# Get PIT roster first
print("=" * 60)
print("Fetching PIT Roster and Player Stats")
print("=" * 60)

roster = fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/23/roster")

for group in roster.get("athletes", []):
    pos_group = group.get("position", "?")
    if pos_group not in ["offense"]:
        continue
        
    print(f"\n{pos_group}:")
    
    for player in group.get("items", [])[:5]:
        name = player.get("fullName", "?")
        pid = player.get("id", "")
        pos = player.get("position", {}).get("abbreviation", "?")
        
        if pos not in ["QB", "RB", "WR", "TE"]:
            continue
        
        print(f"\n  {name} ({pos}) - ID: {pid}")
        
        # Try to get their splits/stats
        splits = fetch(f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{pid}/splits")
        if splits:
            print(f"    Splits available: {splits.get('displayName', '?')}")
            
            labels = splits.get("labels", [])
            names = splits.get("names", [])
            
            for cat in splits.get("categories", []):
                cat_name = cat.get("displayName", "?")
                print(f"    {cat_name}:")
                
                # Get season totals (usually first split)
                for split in cat.get("splits", [])[:1]:
                    split_name = split.get("displayName", "?")
                    stats = split.get("stats", [])
                    
                    # Map stats to labels
                    if stats and labels:
                        print(f"      {split_name}:")
                        for i, val in enumerate(stats[:6]):
                            label = labels[i] if i < len(labels) else f"stat{i}"
                            print(f"        {label}: {val}")
