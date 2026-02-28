"""Discover what tennis markets are actually available on the Odds API today.
Tries multiple regions and sport keys to find valid markets."""
import os
import sys
import json

sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env', override=False)

from src.sources.odds_api import OddsApiClient, OddsApiError

client = OddsApiClient.from_env()
if not client:
    print("ERROR: ODDS_API_KEY not set")
    sys.exit(1)

# Sport key from .env
sport_key = os.getenv("ODDS_API_TENNIS_WTA_SPORT_KEY", "").strip()
print(f"Sport key: {sport_key}")

# 1. List events
print("\n=== EVENTS ===")
events, q = client.get_events(sport_key=sport_key)
print(f"Events found: {len(events)}")
for ev in events[:5]:
    print(f"  {ev.get('id', '?')[:20]}... | {ev.get('home_team','?')} vs {ev.get('away_team','?')} | {ev.get('commence_time','?')}")

if not events:
    print("No events found — sport key may be wrong or tournament not active")
    sys.exit(0)

# 2. Try discovering markets for the first event across different regions
first_event_id = events[0].get("id")
print(f"\n=== MARKET DISCOVERY (event: {first_event_id}) ===")

regions_to_try = ["us", "us_dfs", "us2", "eu", "uk", "au"]
for region in regions_to_try:
    try:
        mk_json, q_mk = client.get_event_markets(
            sport_key=sport_key,
            event_id=str(first_event_id),
            regions=region,
        )
        # Extract market keys
        if isinstance(mk_json, dict):
            markets_found = []
            for bm in mk_json.get("bookmakers", []):
                for mkt in bm.get("markets", []):
                    mk = mkt.get("key", "")
                    if mk and mk not in markets_found:
                        markets_found.append(mk)
            if markets_found:
                print(f"  Region '{region}': {len(markets_found)} markets -> {markets_found}")
            else:
                print(f"  Region '{region}': no markets")
        else:
            print(f"  Region '{region}': unexpected response type")
    except OddsApiError as e:
        print(f"  Region '{region}': ERROR - {e}")
    except Exception as e:
        print(f"  Region '{region}': EXCEPTION - {type(e).__name__}: {e}")

# 3. Try fetching odds with specific markets + US region (non-DFS sportsbooks)
print(f"\n=== TRY PLAYER PROPS (us region, no bookmaker filter) ===")
tennis_markets = [
    "player_aces", "player_double_faults", "player_games_won", "player_sets_won",
    "player_total_games", "spreads", "totals", "h2h",
]
for market in tennis_markets:
    try:
        odds_json, q_odds = client.get_event_odds(
            sport_key=sport_key,
            event_id=str(first_event_id),
            regions="us",
            markets=market,
        )
        bms = odds_json.get("bookmakers", [])
        if bms:
            total_outcomes = sum(len(m.get("outcomes",[])) for b in bms for m in b.get("markets",[]))
            bm_names = [b.get("key","?") for b in bms]
            print(f"  Market '{market}': {total_outcomes} outcomes from {bm_names}")
        else:
            print(f"  Market '{market}': 0 bookmakers")
    except OddsApiError as e:
        err_str = str(e)
        if "INVALID_MARKET" in err_str.upper():
            print(f"  Market '{market}': INVALID (not supported)")
        else:
            print(f"  Market '{market}': ERROR - {err_str[:100]}")
    except Exception as e:
        print(f"  Market '{market}': EXCEPTION - {type(e).__name__}: {str(e)[:100]}")

print("\n=== QUOTA STATUS ===")
print(f"Remaining: {q.remaining}, Used: {q.used}")
