"""Test tennis match market ingestion (non-interactive)"""
import sys
sys.path.insert(0, '.')

from tennis.oddsapi_dfs_props import ingest_oddsapi_tennis_match_markets

print("Testing WTA match market ingestion...")
props, meta, raw_path = ingest_oddsapi_tennis_match_markets(tour="WTA", max_events=5)

print(f"\nProps returned: {len(props)}")
print(f"Raw saved to: {raw_path}")
print(f"Events: {meta.get('event_count', '?')}")
print(f"Quota remaining: {meta.get('quota', {}).get('remaining', '?')}")

if props:
    print(f"\n=== SAMPLE PROPS ===")
    for p in props[:10]:
        print(f"  {p['player']:40s} | {p['stat']:15s} | {p['line']:5.1f} | {p['direction']}")
else:
    print("\nNo props returned!")
