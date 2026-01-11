#!/usr/bin/env python3
"""Check ESPN athlete splits endpoint for individual stats."""

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

# Joe Burrow's ID is 3915511
print("=" * 60)
print("Joe Burrow (3915511) - Season Splits")

data = fetch("https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/3915511/splits")
print(f"Keys: {list(data.keys())}")
print(f"Display Name: {data.get('displayName', '?')}")

categories = data.get("categories", [])
print(f"\nCategories: {len(categories)}")

for cat in categories:
    print(f"\n{cat.get('displayName', '?')}:")
    
    # Check stats array
    stats = cat.get("stats", [])
    if stats:
        print(f"  Stats: {stats[:5]}")
    
    # Check splits
    splits = cat.get("splits", [])
    for split in splits[:2]:
        split_name = split.get("displayName", "?")
        print(f"\n  {split_name}:")
        split_stats = split.get("stats", [])
        if split_stats and isinstance(split_stats, list):
            print(f"    Values: {split_stats[:10]}")

# Check labels
labels = data.get("labels", [])
names = data.get("names", [])
print(f"\nLabels: {labels[:10]}")
print(f"Names: {names[:10]}")
