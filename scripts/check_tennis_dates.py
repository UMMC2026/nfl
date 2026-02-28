import json

data = json.loads(open("tennis/outputs/oddsapi_tennis_match_markets_latest.json", "r").read())
for p in data.get("props", []):
    raw = p.get("raw", {})
    ct = raw.get("commence_time", "")
    match_name = p.get("player", "")
    if p.get("direction") == "higher" and p.get("stat") == "total_games":
        print(f"  {ct}  |  {match_name}: O/U {p.get('line')}")
