"""
Golf Odds API Parser
====================
Fetch golf betting markets from The Odds API (https://the-odds-api.com/)

Supported Markets:
- outrights: Tournament winner
- h2h: Player matchups (head-to-head)
- tournament_top_5: Top 5 finish
- tournament_top_10: Top 10 finish
- tournament_top_20: Top 20 finish
- make_cut: Will player make the cut

API Key: Set ODDS_API_KEY in .env
"""

import os
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json


# Golf sport keys available on Odds API
GOLF_SPORT_KEYS = {
    "pga": "golf_pga_championship",
    "masters": "golf_masters_tournament",
    "us_open": "golf_us_open",
    "open_championship": "golf_the_open_championship",
}

# All PGA events (when available)
GOLF_GENERIC_KEY = "golf_pga"  # May not always be available


def fetch_golf_odds(
    api_key: str,
    sport_key: str = "golf_pga",
    regions: str = "us",
    markets: str = "outrights,h2h",
    odds_format: str = "american",
) -> List[Dict]:
    """
    Fetch golf odds from The Odds API.
    
    Args:
        api_key: Your Odds API key
        sport_key: Golf event (golf_pga, golf_masters_tournament, etc.)
        regions: Betting regions (us, uk, eu, au)
        markets: Comma-separated markets (outrights, h2h, spreads)
        odds_format: american | decimal | fractional
        
    Returns:
        List of events with odds data
    """
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # Log API usage
        remaining = resp.headers.get("x-requests-remaining", "?")
        used = resp.headers.get("x-requests-used", "?")
        print(f"[ODDS API] Requests used: {used} | Remaining: {remaining}")
        
        return data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"[ERROR] Invalid API key")
        elif e.response.status_code == 429:
            print(f"[ERROR] Rate limit exceeded")
        else:
            print(f"[ERROR] HTTP {e.response.status_code}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to fetch odds: {e}")
        return []


def parse_outrights(odds_data: List[Dict]) -> List[Dict]:
    """
    Parse tournament winner (outright) markets.
    
    Returns:
        List of dicts: {player, tournament, odds, implied_prob, bookmaker, commence_time}
    """
    outrights = []
    
    for event in odds_data:
        tournament = event.get("sport_title", "Unknown Tournament")
        commence_time = event.get("commence_time", "")
        
        for bookmaker in event.get("bookmakers", []):
            book_name = bookmaker.get("title", "Unknown")
            
            for market in bookmaker.get("markets", []):
                if market.get("key") == "outrights":
                    for outcome in market.get("outcomes", []):
                        player = outcome.get("name", "Unknown")
                        odds = outcome.get("price", 0)
                        
                        # Convert American odds to implied probability
                        if odds > 0:
                            implied_prob = 100 / (odds + 100)
                        else:
                            implied_prob = abs(odds) / (abs(odds) + 100)
                        
                        outrights.append({
                            "player": player,
                            "tournament": tournament,
                            "odds": odds,
                            "implied_prob": implied_prob * 100,  # As percentage
                            "bookmaker": book_name,
                            "commence_time": commence_time,
                            "market": "outright",
                        })
    
    return outrights


def parse_matchups(odds_data: List[Dict]) -> List[Dict]:
    """
    Parse head-to-head player matchups.
    
    Returns:
        List of dicts: {player1, player2, player1_odds, player2_odds, bookmaker, tournament}
    """
    matchups = []
    
    for event in odds_data:
        tournament = event.get("sport_title", "Unknown Tournament")
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        commence_time = event.get("commence_time", "")
        
        for bookmaker in event.get("bookmakers", []):
            book_name = bookmaker.get("title", "Unknown")
            
            for market in bookmaker.get("markets", []):
                if market.get("key") == "h2h":
                    outcomes = market.get("outcomes", [])
                    if len(outcomes) == 2:
                        p1 = outcomes[0].get("name", "")
                        p2 = outcomes[1].get("name", "")
                        p1_odds = outcomes[0].get("price", 0)
                        p2_odds = outcomes[1].get("price", 0)
                        
                        matchups.append({
                            "player1": p1,
                            "player2": p2,
                            "player1_odds": p1_odds,
                            "player2_odds": p2_odds,
                            "bookmaker": book_name,
                            "tournament": tournament,
                            "commence_time": commence_time,
                            "market": "h2h",
                        })
    
    return matchups


def get_best_outright_odds(outrights: List[Dict]) -> Dict[str, Dict]:
    """
    Find best odds for each player across all bookmakers.
    
    Returns:
        Dict mapping player name to best odds info
    """
    best_odds = {}
    
    for outright in outrights:
        player = outright["player"]
        odds = outright["odds"]
        
        if player not in best_odds or odds > best_odds[player]["odds"]:
            best_odds[player] = outright
    
    return best_odds


def convert_to_finishing_position_props(outrights: List[Dict]) -> List[Dict]:
    """
    Convert Odds API outrights to golf pipeline format (finishing_position props).
    
    Args:
        outrights: Parsed outright odds from parse_outrights()
        
    Returns:
        List of props compatible with generate_edge_from_prop()
    """
    props = []
    
    for outright in outrights:
        # Calculate better_mult from odds
        # Positive odds: better_mult = (odds / 100) + 1
        # Negative odds: better_mult = (100 / abs(odds)) + 1
        odds = outright["odds"]
        if odds > 0:
            better_mult = (odds / 100) + 1
        else:
            better_mult = (100 / abs(odds)) + 1
        
        # Outright winner = finishing position BETTER than 1.5
        prop = {
            "player": outright["player"],
            "tournament": outright["tournament"],
            "market": "finishing_position",
            "line": 1.5,  # Top 1 (win)
            "better_mult": better_mult,
            "higher_mult": None,
            "lower_mult": None,
            "direction": "better",
            "source": "odds_api",
            "bookmaker": outright["bookmaker"],
            "odds": odds,
            "commence_time": outright["commence_time"],
        }
        props.append(prop)
    
    return props


def generate_readable_report(outrights: List[Dict], matchups: List[Dict]) -> str:
    """
    Generate human-readable report of golf odds.
    
    Args:
        outrights: Parsed outright odds
        matchups: Parsed h2h matchups
        
    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 80)
    report.append("[GOLF] ODDS API REPORT — TOURNAMENT MARKETS")
    report.append("=" * 80)
    
    if outrights:
        # Group by tournament
        tournaments = {}
        for o in outrights:
            tourn = o["tournament"]
            if tourn not in tournaments:
                tournaments[tourn] = []
            tournaments[tourn].append(o)
        
        for tourn, odds_list in tournaments.items():
            report.append(f"\n[TOURNAMENT] {tourn}")
            report.append(f"Commence: {odds_list[0]['commence_time']}")
            report.append("-" * 80)
            
            # Get best odds per player
            best_odds = get_best_outright_odds(odds_list)
            
            # Sort by implied probability (favorites first)
            sorted_players = sorted(
                best_odds.items(),
                key=lambda x: x[1]["implied_prob"],
                reverse=True
            )
            
            report.append("\n[OUTRIGHTS] Tournament Winner")
            report.append(f"{'Player':<30} {'Odds':<10} {'Prob':<8} {'Book':<20}")
            report.append("-" * 80)
            
            for player, info in sorted_players[:20]:  # Top 20 favorites
                odds_str = f"{info['odds']:+d}" if info['odds'] != 0 else "EVEN"
                prob_str = f"{info['implied_prob']:.1f}%"
                report.append(
                    f"{player:<30} {odds_str:<10} {prob_str:<8} {info['bookmaker']:<20}"
                )
    
    if matchups:
        report.append("\n" + "=" * 80)
        report.append("[HEAD-TO-HEAD MATCHUPS]")
        report.append("-" * 80)
        
        for matchup in matchups[:10]:  # Show first 10 matchups
            report.append(f"\n{matchup['player1']} vs {matchup['player2']}")
            report.append(f"  {matchup['player1']}: {matchup['player1_odds']:+d}")
            report.append(f"  {matchup['player2']}: {matchup['player2_odds']:+d}")
            report.append(f"  Book: {matchup['bookmaker']}")
    
    if not outrights and not matchups:
        report.append("\n[!] No odds data available")
        report.append("    Check tournament schedule and API key")
    
    report.append("\n" + "=" * 80)
    report.append(f"[TIMESTAMP] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    
    return "\n".join(report)


def fetch_and_convert_majors(api_key: str) -> Tuple[List[Dict], str]:
    """
    Fetch odds for all 4 majors and convert to props.
    
    Returns:
        Tuple of (props_list, readable_report)
    """
    all_outrights = []
    all_matchups = []
    
    # Try each major
    for major_name, sport_key in GOLF_SPORT_KEYS.items():
        print(f"\n[FETCHING] {major_name.upper()}...")
        odds_data = fetch_golf_odds(
            api_key=api_key,
            sport_key=sport_key,
            markets="outrights,h2h",
        )
        
        if odds_data:
            outrights = parse_outrights(odds_data)
            matchups = parse_matchups(odds_data)
            all_outrights.extend(outrights)
            all_matchups.extend(matchups)
            print(f"  ✓ Found {len(outrights)} outrights, {len(matchups)} matchups")
        else:
            print(f"  ✗ No data available")
    
    # Convert to props
    props = convert_to_finishing_position_props(all_outrights)
    
    # Generate report
    report = generate_readable_report(all_outrights, all_matchups)
    
    return props, report


if __name__ == "__main__":
    """
    Standalone test: Fetch and display golf odds
    
    Usage:
        python golf/ingest/odds_api_parser.py
    """
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("[ERROR] ODDS_API_KEY not set in .env")
        exit(1)
    
    print("Fetching golf odds from The Odds API...")
    props, report = fetch_and_convert_majors(api_key)
    
    print(report)
    
    if props:
        print(f"\n[CONVERTED] {len(props)} props ready for pipeline")
        print("\nSample props:")
        for prop in props[:3]:
            print(f"  {prop['player']} - {prop['tournament']} - {prop['odds']:+d} → {prop['better_mult']:.2f}x")
