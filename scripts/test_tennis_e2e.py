"""End-to-end test: DFS player props → match market fallback."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tennis.oddsapi_dfs_props import ingest_oddsapi_tennis_dfs_props, ingest_oddsapi_tennis_match_markets

# Step 1: DFS props (expect 0)
props, meta, _ = ingest_oddsapi_tennis_dfs_props(tour="WTA", max_events=2)
print(f"DFS player props: {len(props)}")

# Step 2: Match markets fallback
if not props:
    props, meta, raw_path = ingest_oddsapi_tennis_match_markets(tour="WTA", max_events=2)
    print(f"Match market props: {len(props)}")
    for p in props[:6]:
        player = p.get("player", "?")
        stat = p.get("stat", "?")
        line = p.get("line", 0)
        direction = p.get("direction", "?")
        print(f"  {player:40s} | {stat:15s} | {line:5.1f} | {direction}")

print(f"\nQuota remaining: {meta.get('quota_remaining', '?')}")
print("\nFallback flow: OK" if props else "\nFallback flow: FAILED (0 props)")
