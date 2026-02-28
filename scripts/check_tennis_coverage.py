"""Check raw Odds API matches vs analyzed matches."""
import json

# Raw markets
raw = json.loads(open("tennis/outputs/oddsapi_tennis_match_markets_latest.json", "r").read())
props = raw.get("props", [])
totals = [p for p in props if p.get("stat") == "total_games" and p.get("direction") == "higher"]
spreads = [p for p in props if p.get("stat") == "game_spread"]

print("=== RAW FROM ODDS API (totals lines) ===")
print(f"Matches with totals: {len(totals)}")
for i, p in enumerate(totals, 1):
    ct = p.get("raw", {}).get("commence_time", "")
    name = p.get("player", "?")
    line = p.get("line", "?")
    print(f"  {i:2d}. {ct}  {name}: O/U {line}")

# Analysis output
print("\n=== ANALYSIS OUTPUT ===")
analysis = json.loads(open("tennis/outputs/oddsapi_tennis_dfs_props_analysis_latest.json", "r").read())
print(f"Top-level keys: {list(analysis.keys())}")

edges = analysis.get("edges") or analysis.get("results") or analysis.get("picks") or []
if edges:
    print(f"Edges: {len(edges)}")
    for e in edges[:5]:
        print(f"  {e.get('player','?'):35s} | {e.get('stat','?'):15s} | {e.get('tier','?')}")
else:
    # Check nested data
    for k, v in analysis.items():
        if isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
        elif isinstance(v, dict):
            print(f"  {k}: dict keys={list(v.keys())[:6]}")
        else:
            print(f"  {k}: {v}")
