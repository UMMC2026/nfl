import json
ps = json.loads(open("tennis/data/player_stats.json", "r").read())
# Check structure
keys = list(ps.keys())[:5]
print(f"Total players: {len(ps)}")
print(f"Sample keys: {keys}")

# Search
for name in ["kasatkina", "mertens", "gauff", "swiatek"]:
    matches = [k for k in ps.keys() if name in k.lower()]
    if matches:
        k = matches[0]
        d = ps[k]
        data_keys = list(d.keys())[:12]
        print(f"\n{k}:")
        print(f"  data keys: {data_keys}")
        print(f"  ranking: {d.get('ranking')}")
        print(f"  elo: {d.get('elo', d.get('elo_overall'))}")
        print(f"  win_pct_L10: {d.get('win_pct_L10')}")
        print(f"  hold_pct_L10: {d.get('hold_pct_L10')}")
    else:
        print(f"\n{name}: NOT FOUND")
