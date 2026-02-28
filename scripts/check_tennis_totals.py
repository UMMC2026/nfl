"""Check the actual structure of tennis totals/spreads from Odds API"""
import os, sys, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env', override=False)
from src.sources.odds_api import OddsApiClient

client = OddsApiClient.from_env()
sport_key = os.getenv("ODDS_API_TENNIS_WTA_SPORT_KEY", "").strip()

events, _ = client.get_events(sport_key=sport_key)
if not events:
    print("No events"); sys.exit(0)

# Get totals + spreads for first 3 events
for ev in events[:3]:
    eid = ev.get("id")
    print(f"\n{'='*60}")
    print(f"Match: {ev.get('home_team')} vs {ev.get('away_team')}")
    print(f"Time:  {ev.get('commence_time')}")
    
    for market in ["totals", "spreads", "h2h_s1"]:
        try:
            odds_json, _ = client.get_event_odds(
                sport_key=sport_key,
                event_id=str(eid),
                regions="us",
                markets=market,
            )
            for bm in odds_json.get("bookmakers", []):
                print(f"\n  [{market}] Bookmaker: {bm.get('key')}")
                for mkt in bm.get("markets", []):
                    print(f"    Market key: {mkt.get('key')}")
                    for outcome in mkt.get("outcomes", []):
                        print(f"      name={outcome.get('name')}, point={outcome.get('point')}, "
                              f"price={outcome.get('price')}, desc={outcome.get('description')}")
                break  # Just show first bookmaker
        except Exception as e:
            print(f"  [{market}] Error: {str(e)[:80]}")
    break  # Just first event
