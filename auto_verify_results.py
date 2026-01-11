#!/usr/bin/env python3
"""
Auto-verify pick results using ESPN/NBA API
Fetches actual game stats and updates calibration_history.csv
"""

import csv
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import NBA API
try:
    from nba_api.stats.endpoints import playergamelog, commonplayerinfo
    from nba_api.stats.static import players as nba_players
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False

def load_pending_picks(date=None, custom_file=None):
    """Load picks that need verification"""
    history_file = Path(custom_file) if custom_file else Path("calibration_history.csv")
    
    if not history_file.exists():
        print(f"❌ {history_file} not found")
        return [], None
    
    with open(history_file, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # Filter pending picks (no outcome yet)
    pending = [r for r in rows if not r.get('outcome')]
    
    if date:
        # Try both game_date and slate_date fields
        pending = [r for r in pending if r.get('game_date') == date or r.get('slate_date') == date]
    
    return pending, (fieldnames, rows)

def validate_stat_value(stat, value):
    """Sanity check: reject impossible stat values"""
    sanity_limits = {
        'points': (0, 100),      # Max 100 points in a game
        'rebounds': (0, 40),     # Max 40 rebounds realistic
        'assists': (0, 30),      # Max 30 assists realistic
        'steals': (0, 15),       # Max 15 steals realistic
        'blocks': (0, 15),       # Max 15 blocks realistic
        'turnovers': (0, 15),    # Max 15 turnovers realistic
        '3pm': (0, 20),          # Max 20 threes realistic
        'pts+reb+ast': (0, 150)  # Combined max
    }
    
    if stat in sanity_limits:
        min_val, max_val = sanity_limits[stat]
        if value < min_val or value > max_val:
            print(f"  ⚠️  REJECTED: {stat}={value} is impossible (range: {min_val}-{max_val})")
            return False
    
    return True

def get_serpapi_game_stats(player_name, stat, game_date, team=None, opponent=None):
    """Fetch actual stat from SerpApi (Google search scraping) with multiple query attempts
    
    Returns: actual_value (float) or None if not found
    """
    try:
        import requests
        import os
        import re
        
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            print(f"  ⚠️  SERPAPI_API_KEY not set in .env")
            return None
        
        print(f"  🔍 Fetching SerpApi data for {player_name}...")
        
        # Format date for search query
        from datetime import datetime
        date_obj = datetime.strptime(game_date, "%Y-%m-%d")
        readable_date = date_obj.strftime("%B %d, %Y")  # e.g., "January 06, 2026"
        short_date = date_obj.strftime("%m/%d/%Y")       # e.g., "01/06/2026"
        
        # Try multiple query patterns (most specific to least specific)
        query_patterns = []
        if team and opponent:
            query_patterns = [
                f"{player_name} {team} vs {opponent} {readable_date} box score",
                f"{player_name} {readable_date} {team} {opponent} game stats",
                f"{player_name} {short_date} {team} box score",
                f"{player_name} {readable_date} NBA game",
            ]
        else:
            query_patterns = [
                f"{player_name} {readable_date} box score",
                f"{player_name} {readable_date} NBA stats"
            ]
        
        # Map stat names to regex patterns
        stat_patterns = {
            'points': r'(\d+)\s*(?:PTS|points?)',
            'rebounds': r'(\d+)\s*(?:REB|rebounds?)',
            'assists': r'(\d+)\s*(?:AST|assists?)',
            '3pm': r'(\d+)\s*(?:3PM|3-pointers?)',
            'steals': r'(\d+)\s*(?:STL|steals?)',
            'blocks': r'(\d+)\s*(?:BLK|blocks?)',
            'turnovers': r'(\d+)\s*(?:TOV?|turnovers?)'
        }
        
        # Try each query pattern
        for query in query_patterns:
            try:
                params = {
                    "engine": "google",
                    "q": query,
                    "api_key": api_key,
                    "num": 5,
                    "gl": "us",
                    "hl": "en"
                }
                
                response = requests.get("https://serpapi.com/search", params=params, timeout=15)
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                
                # Look in organic results for stat lines
                if "organic_results" in data:
                    for result in data["organic_results"][:5]:
                        title = result.get("title", "")
                        snippet = result.get("snippet", "")
                        combined = f"{title} {snippet}"
                        
                        # Try to find the stat value
                        if stat in stat_patterns:
                            pattern = stat_patterns[stat]
                            match = re.search(pattern, combined, re.IGNORECASE)
                            if match:
                                value = float(match.group(1))
                                
                                # VALIDATION: Check if value is realistic
                                if validate_stat_value(stat, value):
                                    print(f"  ✅ Found {stat} = {value} from SerpApi (query: '{query[:50]}...')")
                                    return value
                        
                        # Handle combo stats
                        if stat == 'pts+reb+ast':
                            pts_match = re.search(r'(\d+)\s*(?:PTS|points?)', combined, re.IGNORECASE)
                            reb_match = re.search(r'(\d+)\s*(?:REB|rebounds?)', combined, re.IGNORECASE)
                            ast_match = re.search(r'(\d+)\s*(?:AST|assists?)', combined, re.IGNORECASE)
                            if pts_match and reb_match and ast_match:
                                value = float(pts_match.group(1)) + float(reb_match.group(1)) + float(ast_match.group(1))
                                
                                if validate_stat_value(stat, value):
                                    print(f"  ✅ Found PRA = {value} from SerpApi")
                                    return value
            
            except Exception as e:
                print(f"  ⚠️  Query '{query[:40]}...' failed: {e}")
                continue
        
        print(f"  ⚠️  Could not parse {stat} from SerpApi results")
        return None
        
    except Exception as e:
        print(f"  ❌ SerpApi error: {e}")
        return None

def get_nba_api_stats(player_name, team, stat, game_date):
    """Fetch actual stat from NBA API for specific game
    
    Returns: actual_value (float) or None if not found
    """
    if not NBA_API_AVAILABLE:
        return None
    
    try:
        # Find player ID
        player_list = nba_players.find_players_by_full_name(player_name)
        if not player_list:
            print(f"  ⚠️  Player not found in NBA API: {player_name}")
            return None
        
        player_id = player_list[0]['id']
        
        # Get current season (2024-25)
        season = "2024-25"
        
        # Fetch game log
        print(f"  🔍 Fetching NBA API data for {player_name} (ID: {player_id})...")
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        
        if gamelog.empty:
            print(f"  ⚠️  No games found")
            return None
        
        # Parse date and find matching game
        target_date = datetime.strptime(game_date, "%Y-%m-%d").strftime("%b %d, %Y")
        
        # Filter by date
        matching_games = gamelog[gamelog['GAME_DATE'] == target_date]
        
        if matching_games.empty:
            print(f"  ⚠️  No game on {target_date}")
            return None
        
        game_row = matching_games.iloc[0]
        
        # Map stat names to NBA API columns
        stat_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST',
            '3pm': 'FG3M',
            'steals': 'STL',
            'blocks': 'BLK',
            'turnovers': 'TOV',
            'pts+reb+ast': lambda r: r['PTS'] + r['REB'] + r['AST'],
            'pts+reb': lambda r: r['PTS'] + r['REB'],
            'pts+ast': lambda r: r['PTS'] + r['AST'],
            'reb+ast': lambda r: r['REB'] + r['AST'],
            'stl+blk': lambda r: r['STL'] + r['BLK']
        }
        
        if stat in stat_map:
            col_or_func = stat_map[stat]
            if callable(col_or_func):
                actual = col_or_func(game_row)
            else:
                actual = game_row[col_or_func]
            
            print(f"  ✅ Found {stat} = {actual}")
            return float(actual)
        else:
            print(f"  ⚠️  Stat not supported: {stat}")
            return None
            
    except Exception as e:
        print(f"  ❌ NBA API error: {e}")
        return None

# Cache for team schedule to avoid repeated ESPN API calls
_team_schedule_cache = {}

def verify_team_played(team_abbr, game_date):
    """Verify team actually had a game on this date
    
    Returns: True if team played, False otherwise, None if unknown
    """
    # Check cache first
    cache_key = f"{game_date}_{team_abbr}"
    if cache_key in _team_schedule_cache:
        return _team_schedule_cache[cache_key]
    
    # If cache has full schedule for this date, use it
    date_teams_key = f"teams_{game_date}"
    if date_teams_key in _team_schedule_cache:
        teams_that_played = _team_schedule_cache[date_teams_key]
        result = team_abbr in teams_that_played
        _team_schedule_cache[cache_key] = result
        return result
    
    try:
        import requests
        import time
        
        # Convert date format: 2026-01-06 -> 20260106
        date_str = game_date.replace('-', '')
        
        # Retry logic for network issues
        for attempt in range(3):
            try:
                r = requests.get(
                    'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
                    params={'dates': date_str},
                    timeout=15
                )
                
                if r.status_code == 200:
                    break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"  ⚠️  ESPN API retry {attempt + 1}/3...")
                time.sleep(2)
        
        if r.status_code != 200:
            print(f"  ⚠️  ESPN API error: {r.status_code}")
            return None
        
        games = r.json().get('events', [])
        
        # Build set of all teams that played
        teams_that_played = set()
        for game in games:
            for comp in game['competitions']:
                for competitor in comp['competitors']:
                    teams_that_played.add(competitor['team']['abbreviation'])
        
        # Cache the full list of teams for this date
        _team_schedule_cache[date_teams_key] = teams_that_played
        
        # Check if this specific team played
        result = team_abbr in teams_that_played
        _team_schedule_cache[cache_key] = result
        
        return result
        
    except Exception as e:
        print(f"  ⚠️  Team schedule check error: {e}")
        return None

def verify_pick(pick):
    """Verify a single pick and return updated data"""
    player = pick.get('player') or pick.get('player_name')
    team = pick.get('team')
    stat = pick.get('stat') or pick.get('stat_category')
    line = float(pick['line'])
    direction = pick['direction']
    game_date = pick.get('game_date') or pick.get('slate_date')
    
    print(f"\n📊 {player} ({team}) - {stat} {direction} {line}")
    
    # CRITICAL: Verify team actually played that day
    team_played = verify_team_played(team, game_date)
    
    if team_played is False:
        print(f"  ⚠️  {team} did not play on {game_date} - SKIPPING")
        return None
    elif team_played is None:
        print(f"  ⚠️  Could not verify {team} schedule - proceeding with caution")
    
    # Try NBA API first (most reliable for NBA)
    actual_value = get_nba_api_stats(player, team, stat, game_date)
    
    # Fallback to SerpApi if NBA API fails (pass team and opponent for better queries)
    opponent = pick.get('opponent')
    if actual_value is None:
        actual_value = get_serpapi_game_stats(player, stat, game_date, team=team, opponent=opponent)
    
    if actual_value is None:
        print(f"  ❌ Could not fetch actual value")
        return None
    
    # Determine outcome
    if direction == 'HIGHER':
        outcome = 'HIT' if actual_value > line else 'MISS'
    else:  # LOWER
        outcome = 'HIT' if actual_value < line else 'MISS'
    
    symbol = "✅" if outcome == "HIT" else "❌"
    print(f"  {symbol} {stat} = {actual_value} → {outcome}")
    
    return {
        'actual_value': actual_value,
        'outcome': outcome,
        'result_posted_at': datetime.now(timezone.utc).isoformat()
    }

def save_results(fieldnames, all_rows, custom_file=None):
    """Save updated results to CSV"""
    history_file = Path(custom_file) if custom_file else Path("calibration_history.csv")
    with open(history_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

def main():
    if len(sys.argv) < 2:
        print("""
🤖 AUTO-VERIFY RESULTS

Automatically fetch actual game stats from NBA API / ESPN and update results.

Usage:
  python auto_verify_results.py DATE [--file CALIBRATION_FILE]
  
Examples:
  python auto_verify_results.py 2026-01-02
  python auto_verify_results.py 2026-01-06 --file calibration_jan6.csv
  
Requirements:
  - nba_api (pip install nba-api)
  - Game must be completed
  
Process:
  1. Load pending picks for date
  2. Fetch actual stats from NBA API
  3. Calculate HIT/MISS outcome
  4. Update calibration CSV
  5. Run check_results.py to see performance
        """)
        return
    
    date = sys.argv[1]
    custom_file = None
    
    # Check for --file argument
    if len(sys.argv) >= 4 and sys.argv[2] == '--file':
        custom_file = sys.argv[3]
    
    print(f"\n{'='*80}")
    print(f"[AUTO-VERIFY] RESULTS - {date}")
    if custom_file:
        print(f"[FILE] {custom_file}")
    print(f"{'='*80}\n")
    
    if not NBA_API_AVAILABLE:
        print("[ERROR] nba_api not installed. Install with:")
        print("   pip install nba-api")
        return
    
    # Load pending picks
    pending, (fieldnames, all_rows) = load_pending_picks(date, custom_file)
    
    # Ensure result_posted_at field exists in fieldnames
    if 'result_posted_at' not in fieldnames:
        fieldnames.append('result_posted_at')
    
    if not pending:
        print(f"✅ No pending picks for {date}")
        return
    
    print(f"📋 Found {len(pending)} pending picks for {date}\n")
    
    # Verify each pick
    verified_count = 0
    failed_count = 0
    
    for pick in pending:
        result = verify_pick(pick)
        
        if result:
            # Update the row in all_rows
            pick_id = pick['pick_id']
            for row in all_rows:
                if row['pick_id'] == pick_id:
                    row.update(result)
                    verified_count += 1
                    break
        else:
            failed_count += 1
    
    # Save results
    if verified_count > 0:
        save_results(fieldnames, all_rows, custom_file)
        print(f"\n{'='*80}")
        print(f"✅ Verified {verified_count} picks")
        print(f"❌ Failed {failed_count} picks")
        print(f"{'='*80}\n")
        
        print("📊 Run check_results.py to see performance:")
        print(f"   python check_results.py {date}")
    else:
        print(f"\n⚠️  No picks verified")

if __name__ == "__main__":
    main()
