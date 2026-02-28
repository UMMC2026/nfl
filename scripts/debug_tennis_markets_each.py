"""Debug: test each market individually for tennis"""
import os, sys, json, time
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env', override=False)
from src.sources.odds_api import OddsApiClient

client = OddsApiClient.from_env()
sport_key = os.getenv("ODDS_API_TENNIS_WTA_SPORT_KEY", "").strip()

events, _ = client.get_events(sport_key=sport_key)
eid = events[0].get("id")
home = events[0].get("home_team", "")
away = events[0].get("away_team", "")
print(f"Event: {home} vs {away} (ID: {eid})")

# Test each market individually
for market in ["h2h", "totals", "spreads"]:
    try:
        odds_json, q = client.get_event_odds(
            sport_key=sport_key,
            event_id=str(eid),
            regions="us",
            markets=market,
        )
        bms = odds_json.get("bookmakers", [])
        total_outcomes = 0
        for bm in bms:
            for mkt in bm.get("markets", []):
                total_outcomes += len(mkt.get("outcomes", []))
        print(f"  {market:10s}: {len(bms)} bookmakers, {total_outcomes} outcomes (quota: {q.remaining})")
        
        # Show first bookmaker detail
        if bms:
            bm = bms[0]
            for mkt in bm.get("markets", []):
                for oc in mkt.get("outcomes", []):
                    print(f"    [{bm.get('key')}] name={oc.get('name')}, point={oc.get('point')}, price={oc.get('price')}")
    except Exception as e:
        print(f"  {market:10s}: ERROR - {str(e)[:100]}")
    time.sleep(0.2)

# Now test combined
print("\nCombined 'totals,spreads,h2h':")
try:
    odds_json, q = client.get_event_odds(
        sport_key=sport_key,
        event_id=str(eid),
        regions="us",
        markets="totals,spreads,h2h",
    )
    bms = odds_json.get("bookmakers", [])
    for bm in bms[:2]:
        mkts = bm.get("markets", [])
        mkt_keys = [m.get("key") for m in mkts]
        print(f"  {bm.get('key')}: markets={mkt_keys}")
except Exception as e:
    print(f"  ERROR: {str(e)[:200]}")
