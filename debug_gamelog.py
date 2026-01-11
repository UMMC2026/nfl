#!/usr/bin/env python3
"""Debug player gamelog fetch."""

import urllib.request
import ssl
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"    Error: {type(e).__name__}: {e}")
        return None

# Test specific players
players = [
    ("Pat Freiermuth", "4361411"),
    ("Aaron Rodgers", "8439"),
    ("George Pickens", "4426354"),
]

for name, pid in players:
    print(f"\n{name} ({pid}):")
    url = f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{pid}/gamelog"
    print(f"  URL: {url}")
    
    data = fetch(url)
    if data:
        print(f"  SUCCESS - Keys: {list(data.keys())[:5]}")
        
        # Look for season totals
        for st in data.get("seasonTypes", [])[:1]:
            print(f"  Season: {st.get('displayName', '?')}")
            for cat in st.get("categories", [])[:2]:
                cat_name = cat.get("displayName", "?")
                totals = cat.get("totals", [])
                print(f"    {cat_name}: {totals[:5]}")
    else:
        print("  FAILED")
