#!/usr/bin/env python3
"""Test getting player stats from gamelog endpoint."""

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
        print(f"    Error: {e}")
        return None

# Known player IDs
players = [
    ("George Pickens", "4426354"),
    ("Najee Harris", "4241457"),
    ("Pat Freiermuth", "4361411"),
    ("Russell Wilson", "14881"),
]

print("=" * 60)
print("Testing Player Gamelog Endpoints")
print("=" * 60)

for name, pid in players:
    print(f"\n{name} ({pid}):")
    
    # Try gamelog
    data = fetch(f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{pid}/gamelog")
    if data:
        print(f"  Keys: {list(data.keys())}")
        
        # Check for season totals
        seasonTypes = data.get("seasonTypes", [])
        for st in seasonTypes[:1]:
            print(f"  Season Type: {st.get('displayName', '?')}")
            
            categories = st.get("categories", [])
            for cat in categories[:2]:
                cat_name = cat.get("displayName", "?")
                print(f"    {cat_name}:")
                
                # Check for totals
                totals = cat.get("totals", [])
                if totals:
                    labels = data.get("labels", [])
                    names = data.get("names", [])
                    print(f"      Totals: {totals[:6]}")
                    if labels:
                        for i, val in enumerate(totals[:6]):
                            lbl = labels[i] if i < len(labels) else f"idx{i}"
                            print(f"        {lbl}: {val}")
                
                # Check events (games)
                events = cat.get("events", [])
                if events:
                    print(f"      Games: {len(events)}")
