"""
oddsapi_soccer_ingest.py
=======================
Fetches and displays best moneyline odds for soccer matches using Odds API.
"""
import os
import requests
from typing import List, Dict

def fetch_soccer_moneylines(api_key: str, regions: str = "us", markets: str = "h2h") -> List[Dict]:
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def get_best_moneylines(odds_data: List[Dict]) -> List[Dict]:
    best_lines = []
    for match in odds_data:
        match_info = {
            "match": f"{match['home_team']} vs {match['away_team']}",
            "commence_time": match["commence_time"],
            "best_home": None,
            "best_away": None,
            "book_home": None,
            "book_away": None
        }
        best_home, best_away = None, None
        book_home, book_away = None, None
        for bookmaker in match.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market["key"] == "h2h":
                    outcomes = market["outcomes"]
                    if len(outcomes) == 2:
                        home, away = outcomes
                        if best_home is None or home["price"] > best_home:
                            best_home = home["price"]
                            book_home = bookmaker["title"]
                        if best_away is None or away["price"] > best_away:
                            best_away = away["price"]
                            book_away = bookmaker["title"]
        match_info["best_home"] = best_home
        match_info["best_away"] = best_away
        match_info["book_home"] = book_home
        match_info["book_away"] = book_away
        best_lines.append(match_info)
    return best_lines

def print_best_moneylines(best_lines: List[Dict]):
    for match in best_lines:
        print(f"{match['match']} @ {match['commence_time']}")
        print(f"  Home: {match['best_home']} ({match['book_home']})")
        print(f"  Away: {match['best_away']} ({match['book_away']})\n")

if __name__ == "__main__":
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("Set ODDS_API_KEY in your environment.")
        exit(1)
    odds_data = fetch_soccer_moneylines(api_key)
    best_lines = get_best_moneylines(odds_data)
    print_best_moneylines(best_lines)
