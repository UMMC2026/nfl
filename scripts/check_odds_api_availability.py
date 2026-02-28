"""
CHECK ODDS API AVAILABILITY FOR NFL
Diagnose what markets/props are available before fetching
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

# Colors for terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{'=' * 70}")
    print(f"{text}")
    print(f"{'=' * 70}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")

def print_error(text):
    print(f"{Colors.RED}✗{Colors.RESET} {text}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")


def check_api_key():
    """Check if API key is configured."""
    load_dotenv(override=True)
    api_key = (os.getenv("ODDS_API_KEY") or os.getenv("ODDSAPI_KEY") or "").strip()
    
    if not api_key:
        print_error("Missing ODDS_API_KEY in .env file")
        print("   Set ODDS_API_KEY=your_key_here in .env")
        return None
    
    # Mask key for display
    masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print_success(f"API Key found: {masked}")
    return api_key


def check_quota(api_key):
    """Check remaining API quota."""
    url = "https://api.the-odds-api.com/v4/sports"
    params = {"apiKey": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        # Check quota headers
        remaining = response.headers.get("x-requests-remaining", "unknown")
        used = response.headers.get("x-requests-used", "unknown")
        
        print_success(f"Quota: {remaining} remaining, {used} used")
        
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            print_error("API key is invalid (401 Unauthorized)")
            return False
        else:
            print_warning(f"Unexpected status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Connection failed: {e}")
        return False


def get_available_sports(api_key):
    """Get list of all available sports."""
    url = "https://api.the-odds-api.com/v4/sports"
    params = {"apiKey": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        sports = response.json()
        
        # Filter for NFL
        nfl_sports = [s for s in sports if "football" in s.get("key", "").lower() and "american" in s.get("key", "").lower()]
        
        if nfl_sports:
            print_success(f"Found {len(nfl_sports)} NFL-related sport(s):")
            for sport in nfl_sports:
                active = "ACTIVE" if sport.get("active") else "INACTIVE"
                print(f"   • {sport.get('key')} - {sport.get('title')} [{active}]")
                if sport.get("description"):
                    print(f"     {sport.get('description')}")
            return nfl_sports
        else:
            print_warning("No NFL sports found in API")
            return []
            
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to fetch sports: {e}")
        return []


def get_upcoming_events(api_key, sport_key="americanfootball_nfl"):
    """Get upcoming events for NFL."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events"
    params = {"apiKey": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        events = response.json()
        
        if events:
            print_success(f"Found {len(events)} upcoming event(s):")
            for event in events:
                home = event.get("home_team", "Unknown")
                away = event.get("away_team", "Unknown")
                commence = event.get("commence_time", "")
                
                # Parse time
                try:
                    from dateutil import parser
                    dt = parser.parse(commence)
                    time_str = dt.strftime("%a %b %d, %I:%M%p ET")
                except:
                    time_str = commence
                
                print(f"   • {away} @ {home}")
                print(f"     {time_str}")
                print(f"     ID: {event.get('id', 'N/A')}")
            
            return events
        else:
            print_warning("No upcoming events found")
            return []
            
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to fetch events: {e}")
        return []


def check_odds_availability(api_key, sport_key="americanfootball_nfl", regions="us_dfs", markets=None):
    """Check if odds/props are available for NFL."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    
    if markets is None:
        markets = "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions,player_pass_tds,player_anytime_td"
    
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        # Check cost
        last_cost = response.headers.get("x-requests-last", "unknown")
        remaining = response.headers.get("x-requests-remaining", "unknown")
        
        print_info(f"API call cost: {last_cost} requests (remaining: {remaining})")
        
        response.raise_for_status()
        
        events = response.json()
        
        if events:
            print_success(f"Found {len(events)} event(s) with odds/props")
            
            total_props = 0
            bookmakers_found = set()
            markets_found = set()
            
            for event in events:
                home = event.get("home_team", "Unknown")
                away = event.get("away_team", "Unknown")
                
                bookmakers = event.get("bookmakers", [])
                
                if bookmakers:
                    print(f"\n   📊 {away} @ {home}:")
                    
                    for book in bookmakers:
                        book_key = book.get("key", "unknown")
                        book_title = book.get("title", book_key)
                        bookmakers_found.add(book_key)
                        
                        markets_list = book.get("markets", [])
                        
                        if markets_list:
                            print(f"      • {book_title}:")
                            
                            for market in markets_list:
                                market_key = market.get("key", "unknown")
                                markets_found.add(market_key)
                                
                                outcomes = market.get("outcomes", [])
                                total_props += len(outcomes)
                                
                                print(f"        - {market_key}: {len(outcomes)} props")
                                
                                # Show sample props
                                for outcome in outcomes[:3]:
                                    player = outcome.get("description", "Unknown")
                                    point = outcome.get("point", "N/A")
                                    price = outcome.get("price", "N/A")
                                    print(f"          {player}: {point} ({price})")
                                
                                if len(outcomes) > 3:
                                    print(f"          ... and {len(outcomes) - 3} more")
            
            print(f"\n   📈 Summary:")
            print(f"      Total props: {total_props}")
            print(f"      Bookmakers: {', '.join(sorted(bookmakers_found))}")
            print(f"      Markets: {', '.join(sorted(markets_found))}")
            
            return True
        else:
            print_warning("No odds/props data available")
            print("   Possible reasons:")
            print("   1. Props not released yet (common for playoffs)")
            print("   2. Wrong market names for NFL")
            print("   3. Bookmakers don't have NFL in their offerings")
            print("   4. Event is too far in the future")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to fetch odds: {e}")
        return False


def suggest_alternative_markets(api_key, sport_key="americanfootball_nfl"):
    """Try different market configurations to find what works."""
    print_header("🔍 TESTING ALTERNATIVE MARKETS")
    
    market_sets = [
        ("Standard Player Props", "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions"),
        ("Touchdown Props", "player_pass_tds,player_rush_tds,player_anytime_td"),
        ("All Player Markets", "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions,player_pass_tds,player_rush_tds,player_anytime_td"),
        ("Game Markets Only", "h2h,spreads,totals"),
    ]
    
    bookmaker_sets = [
        ("DFS Platforms", "betr_us_dfs,pick6,prizepicks,underdog"),
        ("PrizePicks Only", "prizepicks"),
        ("Underdog Only", "underdog"),
        ("All US Books", "us"),
    ]
    
    for market_name, markets in market_sets:
        for book_name, bookmakers in bookmaker_sets:
            print(f"\n🧪 Testing: {market_name} on {book_name}")
            
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
            params = {
                "apiKey": api_key,
                "regions": "us_dfs" if "dfs" in bookmakers else "us",
                "markets": markets,
                "bookmakers": bookmakers,
                "oddsFormat": "american"
            }
            
            try:
                response = requests.get(url, params=params, timeout=10)
                events = response.json()
                
                if events and len(events) > 0:
                    # Check if any have props
                    total_props = sum(
                        len(outcome)
                        for event in events
                        for book in event.get("bookmakers", [])
                        for market in book.get("markets", [])
                        for outcome in market.get("outcomes", [])
                    )
                    
                    if total_props > 0:
                        print_success(f"FOUND {total_props} props!")
                        print(f"   ✓ Use these settings:")
                        print(f"     Markets: {markets}")
                        print(f"     Bookmakers: {bookmakers}")
                        return True
                    else:
                        print_warning("Events found but no props")
                else:
                    print_warning("No events with this configuration")
                    
            except:
                print_error("Request failed")
    
    return False


def main():
    print_header("🏈 ODDS API AVAILABILITY CHECK - NFL")
    
    print_info("Checking NFL props availability for Super Bowl LIX...")
    print_info("Date: February 7, 2026 (2 days before Super Bowl)")
    
    # Step 1: Check API key
    print_header("1️⃣ API KEY CHECK")
    api_key = check_api_key()
    if not api_key:
        print("\n❌ Cannot proceed without API key")
        return
    
    # Step 2: Check quota
    print_header("2️⃣ QUOTA CHECK")
    if not check_quota(api_key):
        print("\n❌ API connection failed")
        return
    
    # Step 3: Get available sports
    print_header("3️⃣ AVAILABLE SPORTS")
    nfl_sports = get_available_sports(api_key)
    
    if not nfl_sports:
        print("\n❌ No NFL sports available")
        return
    
    # Use first active NFL sport
    sport_key = None
    for sport in nfl_sports:
        if sport.get("active"):
            sport_key = sport.get("key")
            break
    
    if not sport_key:
        sport_key = "americanfootball_nfl"
        print_warning(f"No active NFL sport found, using default: {sport_key}")
    
    # Step 4: Get upcoming events
    print_header("4️⃣ UPCOMING EVENTS")
    events = get_upcoming_events(api_key, sport_key)
    
    if not events:
        print_warning("No upcoming events - this explains why 0 props were returned!")
        print("   Super Bowl props may not be in the API yet.")
        print("   Try again closer to game time (Saturday/Sunday).")
    
    # Step 5: Check odds/props availability
    print_header("5️⃣ PROPS AVAILABILITY CHECK")
    has_props = check_odds_availability(api_key, sport_key)
    
    if not has_props:
        # Step 6: Try alternatives
        suggest_alternative_markets(api_key, sport_key)
    
    # Final recommendation
    print_header("📋 RECOMMENDATION")
    
    if has_props:
        print_success("Odds API has NFL props available!")
        print("   ✓ Use [A] ODDS API INGEST in NFL menu")
    else:
        print_warning("Odds API does NOT have NFL props yet")
        print("\n   Recommended actions:")
        print("   1. Use [1] INGEST NFL SLATE (manual paste from Underdog/PrizePicks)")
        print("   2. Try [A] again on Saturday evening (Feb 8)")
        print("   3. Props typically release 24-48 hours before kickoff")
        print("\n   Why this happens:")
        print("   • Super Bowl props often delayed until Saturday")
        print("   • DFS platforms (PrizePicks/Underdog) release earlier")
        print("   • Odds API aggregates from sportsbooks (slower)")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
