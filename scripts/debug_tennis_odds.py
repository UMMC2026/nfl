"""Debug tennis match market fetching"""
import os, sys, json, time
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env', override=False)
from src.sources.odds_api import OddsApiClient, OddsApiError

client = OddsApiClient.from_env()
sport_key = os.getenv("ODDS_API_TENNIS_WTA_SPORT_KEY", "").strip()
print(f"Sport key: {sport_key}")

events, _ = client.get_events(sport_key=sport_key)
print(f"Events: {len(events)}")

for ev in events[:3]:
    eid = ev.get("id")
    home = ev.get("home_team", "")
    away = ev.get("away_team", "")
    print(f"\n{'='*50}")
    print(f"Event: {home} vs {away}")
    print(f"ID: {eid}")
    
    try:
        odds_json, _ = client.get_event_odds(
            sport_key=sport_key,
            event_id=str(eid),
            regions="us",
            markets="totals,spreads,h2h",
        )
        
        bookmakers = odds_json.get("bookmakers", [])
        print(f"Bookmakers: {len(bookmakers)}")
        
        for bm in bookmakers[:2]:
            bm_key = bm.get("key", "")
            markets = bm.get("markets", [])
            print(f"  Bookmaker: {bm_key}, Markets: {len(markets)}")
            
            for mkt in markets:
                mkt_key = mkt.get("key", "")
                outcomes = mkt.get("outcomes", [])
                print(f"    Market: {mkt_key}, Outcomes: {len(outcomes)}")
                for outcome in outcomes:
                    name = str(outcome.get("name", "")).strip()
                    point = outcome.get("point")
                    price = outcome.get("price")
                    desc = outcome.get("description")
                    print(f"      name='{name}', point={point}, price={price}, desc={desc}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    time.sleep(0.2)
    break  # Just first event for debugging
