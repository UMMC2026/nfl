"""Quick script to list golf-related Odds API sport keys."""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from sources.odds_api import OddsApiClient

c = OddsApiClient.from_env()
sports, q = c.list_sports()

golf = [s for s in sports if 'golf' in s.get('key', '').lower() or 'golf' in s.get('group', '').lower() or 'pga' in s.get('title', '').lower()]

if golf:
    print(f"\nFound {len(golf)} golf sport(s):\n")
    for g in golf:
        print(f"  key: {g['key']}")
        print(f"    title: {g.get('title', '?')}")
        print(f"    group: {g.get('group', '?')}")
        print(f"    active: {g.get('active')}")
        print(f"    has_outrights: {g.get('has_outrights')}")
        print()
else:
    print("No golf sports found in active sports list.")

# Always show ALL golf keys (including inactive)
print("\nAll golf keys (including inactive):")
sports_all, _ = c._get("/v4/sports", params={"all": "true"})
for s in (sports_all or []):
    if 'golf' in s.get('key', '').lower():
        print(f"  {s['key']:50s} active={str(s.get('active')):5s}  title={s.get('title', '?')}")
        if s.get('has_outrights'):
            print(f"    ^ has_outrights=True")

# Check event-level data for active golf sport keys
print("\n--- Checking events + available markets ---")
for g in golf[:2]:  # Limit to 2 to save quota
    key = g['key']
    print(f"\nSport: {key}")
    try:
        events, _ = c.get_events(sport_key=key)
        print(f"  Events: {len(events)}")
        for ev in events[:3]:
            print(f"    event_id={ev.get('id')}  {ev.get('home_team','?')} vs {ev.get('away_team','?')}")
            print(f"    commence: {ev.get('commence_time')}")
            # Try to discover markets for this event
            try:
                mkts, _ = c.get_event_markets(sport_key=key, event_id=str(ev['id']), regions="us_dfs")
                for bk in mkts.get('bookmakers', [])[:3]:
                    mk_keys = [m.get('key') for m in bk.get('markets', [])]
                    print(f"      book={bk.get('key')}  markets={mk_keys}")
            except Exception as e2:
                print(f"      markets discovery: {e2}")
    except Exception as e:
        print(f"  Error: {e}")
