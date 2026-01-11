#!/usr/bin/env python3
"""Check gamelog JSON structure."""

import urllib.request
import ssl
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())

# George Pickens
print("=" * 60)
print("George Pickens gamelog structure")
data = fetch("https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/4426354/gamelog")

print(f"\nTop-level keys: {list(data.keys())}")

# Check seasonTypes
st = data.get("seasonTypes", [])
print(f"\nseasonTypes: {len(st)}")
if st:
    print(f"  First seasonType keys: {list(st[0].keys())}")
    print(f"  Name: {st[0].get('displayName', '?')}")
    
    cats = st[0].get("categories", [])
    print(f"  categories: {len(cats)}")
    if cats:
        print(f"    First category: {cats[0].get('displayName', '?')}")
        print(f"    totals: {cats[0].get('totals', [])[:5]}")

# Check direct categories
cats = data.get("categories", [])
print(f"\nDirect categories: {len(cats)}")

# Check labels
labels = data.get("labels", [])
print(f"\nLabels: {labels}")
