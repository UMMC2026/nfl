#!/usr/bin/env python3
"""
🎯 MULTI-SITE PROP INGESTION PIPELINE
=====================================
Playwright-based scraper for:
- DraftKings Pick6
- PrizePicks
- Underdog Fantasy

Extracts player props and normalizes for quant pipeline.
"""

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None
from pathlib import Path
from datetime import datetime
import json
import os
import time
import re
from typing import Optional, List, Dict

try:
    from ingestion.props_storage import store_run as _store_props_run
except Exception:
    _store_props_run = None

# Output paths
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "props_combined.json"
OUTPUT_LATEST = OUTPUT_DIR / "props_latest.json"

# Persistent browser profile for Playwright (keeps logins/cookies locally)
CHROME_PROFILE_DIR = Path(__file__).parent.parent / "chrome_profile"
CHROME_PROFILE_DIR.mkdir(exist_ok=True)


def _try_import_odds_api():
    """Best-effort import of the Odds API adapter.

    The adapter lives at `src/sources/odds_api.py`. Since `src/` is not
    necessarily installed as a package, we add it to sys.path at runtime.
    """

    try:
        import sys

        project_root = Path(__file__).resolve().parents[1]
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from sources.odds_api import (  # type: ignore
            OddsApiError,
            oddsapi_fetch_player_props,
            oddsapi_sport_key_for_tag,
        )

        return OddsApiError, oddsapi_fetch_player_props, oddsapi_sport_key_for_tag
    except Exception:
        return None


# ==========================================================
# UTILITY FUNCTIONS
# ==========================================================

def clean_text(text: str) -> str:
    """Clean whitespace from extracted text."""
    return " ".join(text.split())


def parse_prop_text(raw: str, source: str) -> dict:
    """
    Parse raw prop text into structured format.
    Returns: {player, stat, line, direction}
    """
    result = {
        "source": source,
        "raw": raw,
        "player": None,
        "stat": None,
        "line": None,
        "direction": None,
        "parsed": False
    }
    
    # Try to extract direction
    direction_match = re.search(r'\b(More|Less|Higher|Lower|Over|Under)\b', raw, re.IGNORECASE)
    if direction_match:
        dir_text = direction_match.group(1).lower()
        result["direction"] = "higher" if dir_text in ["more", "higher", "over"] else "lower"
    
    # Try to extract line (number like 25.5, 2.5, etc.)
    line_match = re.search(r'(\d+\.?\d*)', raw)
    if line_match:
        result["line"] = float(line_match.group(1))
    
    # Try to extract stat type
    stat_patterns = [
        (r'\b(Points?|PTS)\b', 'points'),
        (r'\b(Rebounds?|REB|REBS)\b', 'rebounds'),
        (r'\b(Assists?|AST|ASTS)\b', 'assists'),
        (r'\b(3PM|3-?Pointers?|Threes?)\b', '3pm'),
        (r'\b(Steals?|STL)\b', 'steals'),
        (r'\b(Blocks?|BLK)\b', 'blocks'),
        (r'\b(PRA|Pts\+Reb\+Ast)\b', 'pra'),
        (r'\b(PA|Pts\+Ast)\b', 'pts+ast'),
        (r'\b(PR|Pts\+Reb)\b', 'pts+reb'),
        (r'\b(RA|Reb\+Ast)\b', 'reb+ast'),
        (r'\b(Fantasy|FPTS)\b', 'fantasy'),
        (r'\b(SOG|Shots? on Goal)\b', 'sog'),
        (r'\b(Saves?)\b', 'saves'),
        (r'\b(Goals?)\b', 'goals'),
        (r'\b(Rushing|Rush Yards?)\b', 'rush_yards'),
        (r'\b(Receiving|Rec Yards?)\b', 'rec_yards'),
        (r'\b(Passing|Pass Yards?)\b', 'pass_yards'),
        (r'\b(Touchdowns?|TDs?)\b', 'touchdowns'),
        (r'\b(Aces?)\b', 'aces'),
        (r'\b(Double Faults?)\b', 'double_faults'),
    ]
    
    for pattern, stat_name in stat_patterns:
        if re.search(pattern, raw, re.IGNORECASE):
            result["stat"] = stat_name
            break
    
    # Try to extract player name (usually at start, before numbers)
    # This is a heuristic - grab text before the first number
    name_match = re.match(r'^([A-Za-z\s\.\'\-]+?)(?=\s*\d|\s*(?:More|Less|Higher|Lower))', raw)
    if name_match:
        result["player"] = name_match.group(1).strip()
    
    # Mark as parsed if we got key fields
    if result["player"] and result["line"] is not None and result["direction"]:
        result["parsed"] = True
    
    return result


# ==========================================================
# SMART VERTICAL PARSER (works with all sites)
# ==========================================================

STAT_TYPES = {
    'Points', 'Rebounds', 'Assists', '3-Pointers Made', 'Pts + Rebs + Asts',
    'Rebounds + Assists', 'Points + Rebounds', 'Points + Assists',
    'Fantasy Points', 'Steals', 'Blocks', 'Blocks + Steals', 'Turnovers',
    'FT Made', 'Offensive Rebounds', '3PM', 'Threes Made', 'Double Doubles',
    # NHL
    'Shots on Goal', 'SOG', 'Saves', 'Goals', 'Goals + Assists',
    # Soccer (Underdog/PrizePicks/Pick6 common labels)
    'Shots', 'Shots Attempted', 'Shots on Target',
    'Passes', 'Passes Attempted',
    'Dribbles', 'Attempted Dribbles',
    'Crosses', 'Tackles', 'Clearances',
    'Assists',
    '1H Saves', '1H Goals', '1H Goals Allowed', 'Goals Allowed',
    # Tennis
    'Aces', 'Double Faults', 'Games Won', 'Total Games',
    # NFL
    'Passing Yards', 'Rushing Yards', 'Receiving Yards', 'Receptions', 'Touchdowns',
}

STAT_TYPES_LOWER = {s.lower() for s in STAT_TYPES}


def smart_extract_props(text: str, source: str) -> list:
    """
    Parse props using smart vertical format detection.
    
    Sites display props as:
        Player Name
        28.5
        Points
        Higher
        
    This parser detects that pattern.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    props = []
    current_player = None
    current_matchup = None  # Track game context for team extraction
    i = 0
    
    # Skip patterns
    skip_words = ['pick\'em', 'drafts', 'live', 'results', 'rankings', 'news', 
                  'featured', 'popular', 'apply', 'boost', 'add picks', 'entry',
                  'rewards', 'flex', 'play', 'standard', 'nba only', 'left',
                  'sign in', 'log in', 'more picks', 'flex play', 'power play',
                  'my entries', 'my picks', 'lobby', 'deposit', 'withdraw']
    
    while i < len(lines):
        line = lines[i]
        
        # Skip UI elements
        if any(sw in line.lower() for sw in skip_words):
            i += 1
            continue
        
        # Extract matchup lines for team context: "MIN vs NOP - 7:00PM CST" or "Iowa State @ Houston"
        matchup_match = re.match(r'^([A-Z]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:vs?|@)\s*([A-Z]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', line)
        if matchup_match:
            current_matchup = {
                'team1': matchup_match.group(1).strip(),
                'team2': matchup_match.group(2).strip()
            }
            i += 1
            continue
        
        # Check if it's a line number (28.5, 19.5)
        line_match = re.match(r'^(\d+\.?\d*)$', line)
        if line_match and i + 2 < len(lines):
            prop_line = float(line_match.group(1))
            next_line = lines[i + 1]
            
            # Check if next line is a stat type
            stat_found = None
            for st in STAT_TYPES:
                if next_line.lower() == st.lower():
                    stat_found = st
                    break
            
            if stat_found and current_player:
                # Look for Higher/Lower in next few lines
                for j in range(i + 2, min(i + 5, len(lines))):
                    if lines[j].lower() in ['higher', 'lower', 'more', 'less', 'over', 'under']:
                        direction = 'higher' if lines[j].lower() in ['higher', 'more', 'over'] else 'lower'
                        stat_norm = stat_found.lower().replace(' + ', '+').replace('-', '').replace('  ', ' ')
                        
                        # Create prop with team info if available from matchup context
                        prop_data = {
                            'source': source,
                            'player': current_player,
                            'stat': stat_norm,
                            'line': prop_line,
                            'direction': direction,
                            'parsed': True,
                            'raw': f"{current_player} {stat_found} {prop_line} {direction}"
                        }
                        
                        # Add team/matchup context if available
                        if current_matchup:
                            prop_data['matchup'] = current_matchup
                        
                        props.append(prop_data)
                        break
                i += 3
                continue
        
        # Check if this is a player name
        # Player names: "LeBron James", "Ja Morant", "De'Aaron Fox", "Shai Gilgeous-Alexander"
        if (re.match(r'^[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Za-z\-\']+)+$', line) 
            and line not in STAT_TYPES 
            and len(line) > 5
            and not re.match(r'^[A-Z]{2,3}$', line)  # Not team abbrev
            and line.lower() not in STAT_TYPES_LOWER):
            current_player = line
        
        i += 1
    
    return props


# ==========================================================
# DRAFTKINGS PICK6
# ==========================================================

def scrape_draftkings(page) -> list:
    """Scrape DraftKings Pick6 props using smart extraction."""
    print("\n" + "=" * 50)
    print("📊 DRAFTKINGS PICK6")
    print("=" * 50)
    
    try:
        page.goto("https://pick6.draftkings.com", timeout=60000)
        print("   ✓ Page loaded")
        
        # Wait for content to load
        print("   ⏳ Waiting for props to load (10s)...")
        time.sleep(10)
        
        # Scroll to trigger lazy loading
        for _ in range(5):
            page.mouse.wheel(0, 3000)
            time.sleep(1)
        
        # Get all text and use smart parser
        all_text = page.inner_text("body")
        props = smart_extract_props(all_text, "DraftKings")
        
        print(f"   ✓ Smart extraction found: {len(props)} props")
        
        # Show sample
        if props:
            print("   Sample:")
            for p in props[:5]:
                print(f"      {p['player'][:18]:<18} {p['stat']:<12} {p['line']:>5} {p['direction']}")
        
        return props
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []


# ==========================================================
# PRIZEPICKS
# ==========================================================

def scrape_prizepicks(page) -> list:
    """Scrape PrizePicks props using smart extraction."""
    print("\n" + "=" * 50)
    print("📊 PRIZEPICKS")
    print("=" * 50)
    
    try:
        page.goto("https://app.prizepicks.com/", timeout=60000)
        print("   ✓ Page loaded")
        time.sleep(10)
        
        # Scroll to load more
        for _ in range(5):
            page.mouse.wheel(0, 3000)
            time.sleep(1)
        
        # Get all text and use smart parser
        all_text = page.inner_text("body")
        props = smart_extract_props(all_text, "PrizePicks")
        
        print(f"   ✓ Smart extraction found: {len(props)} props")
        
        # Show sample
        if props:
            print("   Sample:")
            for p in props[:5]:
                print(f"      {p['player'][:18]:<18} {p['stat']:<12} {p['line']:>5} {p['direction']}")
        
        return props
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []


# ==========================================================
# UNDERDOG FANTASY
# ==========================================================

def scrape_underdog(page) -> list:
    """Scrape Underdog Fantasy props using smart extraction."""
    print("\n" + "=" * 50)
    print("📊 UNDERDOG FANTASY")
    print("=" * 50)
    
    try:
        page.goto("https://underdogfantasy.com/pick-em", timeout=60000)
        print("   ✓ Page loaded")
        time.sleep(10)
        
        # Scroll to load more
        for _ in range(5):
            page.mouse.wheel(0, 3000)
            time.sleep(1)
        
        # Get all text and use smart parser
        all_text = page.inner_text("body")
        props = smart_extract_props(all_text, "Underdog")
        
        print(f"   ✓ Smart extraction found: {len(props)} props")
        
        # Show sample
        if props:
            print("   Sample:")
            for p in props[:5]:
                print(f"      {p['player'][:18]:<18} {p['stat']:<12} {p['line']:>5} {p['direction']}")
        
        return props
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []


# ==========================================================
# MASTER PIPELINE
# ==========================================================

def run_pipeline(sites: Optional[List[str]] = None, headless: bool = False):
    """
    Run the full prop ingestion pipeline.
    
    Args:
        sites: List of sites to scrape ['draftkings', 'prizepicks', 'underdog']
               If None, scrapes all sites.
        headless: Run browser in headless mode (no visible window)
    
    Returns:
        List of all extracted props
    """
    if sites is None:
        sites = ['draftkings', 'prizepicks', 'underdog']
    
    print("\n" + "=" * 60)
    print("🎯 PROP INGESTION PIPELINE")
    print(f"   Sites: {', '.join(sites)}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_props = []
    
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not available in this Python environment. "
            "Run this pipeline using the repo virtualenv: .venv\\Scripts\\python.exe"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        
        # Set viewport for consistent rendering
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        if 'draftkings' in sites:
            all_props += scrape_draftkings(page)
        
        if 'prizepicks' in sites:
            all_props += scrape_prizepicks(page)
        
        if 'underdog' in sites:
            all_props += scrape_underdog(page)
        
        browser.close()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "sites": sites,
        "total_props": len(all_props),
        "parsed_props": sum(1 for p in all_props if p.get("parsed")),
        "props": all_props
    }

    # Persist to SQLite history (best-effort) and attach run_id to artifacts.
    if _store_props_run is not None:
        try:
            output_data["run_id"] = _store_props_run(output_data)
        except Exception:
            output_data["run_id"] = None
    
    # Save timestamped file
    timestamped_file = OUTPUT_DIR / f"props_{timestamp}.json"
    with open(timestamped_file, "w") as f:
        json.dump(output_data, f, indent=2)
    
    # Save latest file
    with open(OUTPUT_LATEST, "w") as f:
        json.dump(output_data, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 PIPELINE SUMMARY")
    print("=" * 60)
    print(f"   Total props extracted: {len(all_props)}")
    print(f"   Successfully parsed:   {output_data['parsed_props']}")
    print(f"   Output file:           {timestamped_file.name}")
    print(f"   Latest file:           {OUTPUT_LATEST.name}")
    
    # Show breakdown by source
    by_source = {}
    for prop in all_props:
        src = prop.get("source", "Unknown")
        by_source[src] = by_source.get(src, 0) + 1
    
    print("\n   By Source:")
    for src, count in by_source.items():
        print(f"     • {src}: {count} props")
    
    return all_props


def run_single_site(site: str, headless: bool = False):
    """Run scraper for a single site."""
    return run_pipeline(sites=[site], headless=headless)


def _parse_h2h_markets(odds_data: List[Dict], sport: str) -> Dict[str, Dict]:
    """Parse h2h/spreads/totals markets to extract game context.
    
    Returns: {event_id: {spread, total, home_team, away_team, matchup}}
    """
    game_lines = {}
    
    for event in odds_data:
        event_id = event.get("id")
        if not event_id:
            continue
            
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        matchup = f"{away_team} @ {home_team}" if away_team and home_team else ""
        
        spread = None
        total = None
        
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                
                # Extract spread (home team perspective)
                if market_key == "spreads":
                    for outcome in market.get("outcomes", []):
                        if outcome.get("name") == home_team:
                            point = outcome.get("point")
                            if point is not None:
                                spread = float(point)
                                break
                
                # Extract total
                elif market_key in ["totals", "totals_over_under"]:
                    for outcome in market.get("outcomes", []):
                        # Over/Under both have same point value
                        point = outcome.get("point")
                        if point is not None:
                            total = float(point)
                            break
                
                # Break if we have both
                if spread is not None and total is not None:
                    break
            
            if spread is not None and total is not None:
                break
        
        game_lines[event_id] = {
            "spread": spread,
            "total": total,
            "home_team": home_team,
            "away_team": away_team,
            "matchup": matchup,
        }
    
    return game_lines


def run_odds_api(*, sport: str = "NBA"):
    """Fetch prop lines via The Odds API (no browser) and write outputs/props_latest.json.

    Output schema matches the scraper pipeline so `convert_scraped.py` can be
    used unchanged to generate the menu slate + set it active.
    
    Now also fetches h2h markets (spreads, totals) and attaches to each prop.
    """

    imported = _try_import_odds_api()
    if not imported:
        print("\n  ✗ Odds API adapter import failed")
        print("    Expected module: src/sources/odds_api.py")
        print("    Make sure you're running from repo root using the .venv interpreter")
        return []

    OddsApiError, oddsapi_fetch_player_props, oddsapi_sport_key_for_tag = imported

    sport_key = oddsapi_sport_key_for_tag(sport)
    if not sport_key:
        print(f"\n  ✗ Unsupported sport tag for Odds API ingestion: {sport!r}")
        print("    Supported: NBA, WNBA, NFL, NHL, MLB, TENNIS/TENNIS_ATP/TENNIS_WTA, SOCCER (or SOCCER_EPL/SOCCER_MLS/...) ")
        return []

    regions = os.getenv("ODDS_API_REGIONS") or "us_dfs"

    # "All stats" presets (kept conservative to stats we can normalize end-to-end).
    markets_s = (os.getenv("ODDS_API_MARKETS") or "all").strip()
    all_markets_by_sport = {
        # Odds API market keys per https://the-odds-api.com/sports-odds-data/betting-markets.html
        "NBA": [
            "player_points",
            "player_rebounds",
            "player_assists",
            "player_threes",
            "player_blocks",
            "player_steals",
            "player_blocks_steals",
            "player_turnovers",
            "player_points_rebounds_assists",
            "player_points_rebounds",
            "player_points_assists",
            "player_rebounds_assists",
        ],
        "WNBA": [
            "player_points",
            "player_rebounds",
            "player_assists",
            "player_threes",
            "player_blocks",
            "player_steals",
            "player_blocks_steals",
            "player_turnovers",
            "player_points_rebounds_assists",
            "player_points_rebounds",
            "player_points_assists",
            "player_rebounds_assists",
        ],
        "NHL": [
            "player_shots_on_goal",
            "player_total_saves",
            "player_goals",
            "player_points",
            "player_assists",
            "player_blocked_shots",
            "player_power_play_points",
        ],
        "SOCCER": [
            "player_shots",
            "player_shots_on_target",
            "player_assists",
        ],
        # Tennis DFS player props (availability varies heavily by book/region/event)
        # Configure sport_key via ODDS_API_TENNIS_*_SPORT_KEY in .env.
        "TENNIS": [
            "player_aces",
            "player_double_faults",
            "player_games_won",
            "player_sets_won",
        ],
        # NFL/MLB are supported by sport mapping, but this repo does not yet
        # normalize a complete set of their props for the core pipeline.
        "NFL": [
            "player_pass_yds",
            "player_rush_yds", 
            "player_reception_yds",
            "player_receptions",
            "player_pass_tds",
            "player_rush_tds",
            "player_anytime_td",
            "player_pass_completions",
            "player_pass_attempts",
            "player_rush_attempts"
        ],
        "MLB": ["batter_hits", "batter_home_runs", "pitcher_strikeouts"],
        # CBB / NCAAB (same markets as NBA, supported end-to-end)
        "BASKETBALL_NCAAB": [
            "player_points",
            "player_rebounds",
            "player_assists",
            "player_threes",
            "player_points_rebounds_assists",
            "player_points_rebounds",
            "player_points_assists",
            "player_rebounds_assists",
        ],
        "CBB": [
            "player_points",
            "player_rebounds",
            "player_assists",
            "player_threes",
            "player_points_rebounds_assists",
            "player_points_rebounds",
            "player_points_assists",
            "player_rebounds_assists",
        ],
        "NCAAB": [
            "player_points",
            "player_rebounds",
            "player_assists",
            "player_threes",
            "player_points_rebounds_assists",
            "player_points_rebounds",
            "player_points_assists",
            "player_rebounds_assists",
        ],
        # Golf uses outrights (not player props) — handled by golf/oddsapi_golf_ingest.py
        # Use golf_menu.py option [8] or `golf.oddsapi_golf_ingest.interactive_run()` directly.
        "GOLF": ["outrights"],
    }

    # DFS bookmaker keys per https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
    # Updated default: PrizePicks, Underdog, DraftKings, MyBookie, SleeperPick6
    bookmakers_s = (
        os.getenv("ODDS_API_BOOKMAKERS")
        or "prizepicks,underdog,draftkings,mybookieag,pick6,sleeperspick6"
    ).strip()
    max_events_s = os.getenv("ODDS_API_MAX_EVENTS")
    max_events = int(max_events_s) if (max_events_s and max_events_s.strip()) else None

    ms_norm = markets_s.strip().lower()
    if ms_norm in {"all", "*", "all_stats", "allstats"}:
        # Soccer uses league-specific sport tags, but shares a market preset.
        if sport.upper().startswith("SOCCER"):
            preset_key = "SOCCER"
        elif sport.upper().startswith("TENNIS"):
            preset_key = "TENNIS"
        else:
            preset_key = sport.upper()
        markets = list(all_markets_by_sport.get(preset_key, ["player_points"]))
    else:
        markets = [m.strip() for m in markets_s.split(",") if m.strip()]

    # Normalize common aliases / typos to official bookmaker keys.
    bookmaker_aliases = {
        "sleeperspick6": "pick6",  # user-typed alias; official key is pick6
        "sleeperpick6": "pick6",
        "dkpick6": "pick6",
        "draftkingspick6": "pick6",
        "betr": "betr_us_dfs",
    }

    bookmakers = []
    for b in [t.strip() for t in bookmakers_s.split(",") if t.strip()]:
        b_norm = b.strip().lower()
        bookmakers.append(bookmaker_aliases.get(b_norm, b_norm))

    print("\n" + "=" * 60)
    print("🔌 ODDS API INGEST (NO SCRAPE)")
    print("=" * 60)
    print(f"  sport:      {sport} ({sport_key})")
    print(f"  regions:    {regions}")
    print(f"  markets:    {','.join(markets) if markets else '(none)'}")
    print(f"  bookmakers: {','.join(bookmakers) if bookmakers else '(all)'}")
    print(f"  max_events: {max_events if max_events is not None else '(default)'}")

    # --- Golf uses outrights, not player props — delegate to specialized module ---
    if sport.upper().startswith("GOLF"):
        print("\n  ℹ️  Golf uses outrights (not player props).")
        print("  Delegating to golf/oddsapi_golf_ingest.py …")
        try:
            from golf.oddsapi_golf_ingest import interactive_run
            interactive_run()
        except Exception as e:
            print(f"\n  ✗ Golf Odds API ingest failed: {e}")
        return []

    try:
        props, meta = oddsapi_fetch_player_props(
            sport=sport,
            sport_key=sport_key,
            regions=regions,
            markets=tuple(markets) if markets else ("player_points",),
            bookmakers=tuple(bookmakers) if bookmakers else None,
            max_events=max_events,
        )
    except Exception as e:
        # Avoid importing requests/adapter types at module import time; just display.
        print(f"\n  ✗ Odds API ingestion failed: {e}")

        # IMPORTANT: Persist a failure artifact for audit/debug.
        # Users frequently interpret an early-return as "nothing stored".
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "sites": ["oddsapi"],
            "total_props": 0,
            "parsed_props": 0,
            "players": 0,
            "props": [],
            "oddsapi_meta": {
                "sport": sport,
                "sport_key": sport_key,
                "regions": regions,
                "markets": markets,
                "bookmakers": bookmakers,
            },
            "error": str(e),
        }

        try:
            output_file = OUTPUT_DIR / f"props_oddsapi_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            with open(OUTPUT_LATEST, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            print(f"\n  ✓ Wrote failure artifact: {output_file.name}")
            print(f"  ✓ Updated {OUTPUT_LATEST.name}")
        except Exception:
            pass

        # Also write a raw artifact in the validator's expected location (best-effort).
        try:
            raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw" / "scraped"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_file = raw_dir / f"raw_props_oddsapi_{sport.upper()}_{timestamp}.json"
            raw_payload = {
                "metadata": {
                    "platform": "oddsapi",
                    "sport": sport.upper(),
                    "sport_key": sport_key,
                    "regions": regions,
                    "markets": markets,
                    "bookmakers": bookmakers,
                    "generated_at_utc": datetime.utcnow().isoformat() + "Z",
                    "error": str(e),
                },
                "props": [],
            }
            raw_file.write_text(json.dumps(raw_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

        return []

    # Diagnostics: events discovered vs. bookmaker coverage.
    try:
        raw_event_odds = (meta or {}).get("raw_event_odds") or []
        ev_total = int((meta or {}).get("event_count") or 0)
        ev_with_books = 0
        for ev in raw_event_odds:
            books = (ev or {}).get("bookmakers") or []
            if isinstance(books, list) and len(books) > 0:
                ev_with_books += 1
        print(f"\n  Events: {ev_total} | Events with bookmaker data: {ev_with_books}")
        if ev_total > 0 and ev_with_books == 0:
            print("  ⚠️ No bookmaker markets returned for these events.")
            print("     This usually means lines are not posted yet for the selected region/bookmakers/markets.")
            print("     Try: switch league (EPL tends to have more coverage), run closer to kickoff,")
            print("          or temporarily clear ODDS_API_BOOKMAKERS to query all available books.")
    except Exception:
        pass

    # Normalize into scraper-style records.
    normalized = []
    props_with_context = 0
    for p in props:
        player = p.get("player")
        stat = p.get("stat")
        line = p.get("line")
        direction = p.get("direction")

        if not (player and stat and line is not None and direction):
            continue

        raw = p.get("raw") or {}
        bm = raw.get("bookmaker_title") or raw.get("bookmaker_key") or "OddsAPI"
        mk = raw.get("market_key")
        event_id = raw.get("event_id")
        
        # Attach spread/total context from game lines
        game_context = game_lines_lookup.get(event_id) if event_id else None
        spread = game_context.get("spread") if game_context else None
        total = game_context.get("total") if game_context else None
        matchup = game_context.get("matchup") if game_context else None
        
        if spread is not None or total is not None:
            props_with_context += 1

        normalized.append(
            {
                "source": f"OddsAPI:{bm}",
                "raw": f"{player} {stat} {line} {direction} ({bm}{'/' + mk if mk else ''})",
                "player": player,
                "stat": stat,
                "line": line,
                "direction": direction,
                "scraped_at": datetime.utcnow().isoformat() + "Z",
                "parsed": True,
                "spread": spread,
                "total": total,
                "matchup": matchup,
                "meta": {"platform": "oddsapi", **p},
            }
        )
    
    if props_with_context > 0:
        print(f"\n  ✓ Attached game context to {props_with_context}/{len(normalized)} props")

    # Dedupe: (player, stat, line, direction)
    seen = set()
    unique = []
    for prop in normalized:
        key = (prop.get("player"), prop.get("stat"), prop.get("line"), prop.get("direction"))
        if key not in seen:
            seen.add(key)
            unique.append(prop)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "sites": ["oddsapi"],
        "total_props": len(unique),
        "parsed_props": len(unique),
        "players": len(set(p["player"] for p in unique)) if unique else 0,
        "props": unique,
        "oddsapi_meta": meta,
    }

    if _store_props_run is not None:
        try:
            output_data["run_id"] = _store_props_run(output_data)
        except Exception:
            output_data["run_id"] = None

    output_file = OUTPUT_DIR / f"props_oddsapi_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_LATEST, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n  ✓ Fetched {len(unique)} props via Odds API")
    print(f"  ✓ Saved to {output_file.name}")
    print(f"  ✓ Updated {OUTPUT_LATEST.name}")

    # Also write a raw artifact in the validator's expected location.
    try:
        raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw" / "scraped"
        raw_dir.mkdir(parents=True, exist_ok=True)

        raw_file = raw_dir / f"raw_props_oddsapi_{sport.upper()}_{timestamp}.json"
        raw_payload = {
            "metadata": {
                "platform": "oddsapi",
                "sport": sport.upper(),
                "sport_key": sport_key,
                "regions": regions,
                "markets": markets,
                "bookmakers": bookmakers,
                "generated_at_utc": datetime.utcnow().isoformat() + "Z",
                "oddsapi_meta": meta,
            },
            "props": [
                {
                    "platform": "oddsapi",
                    "source": p.get("source"),
                    "player": p.get("player"),
                    "stat": p.get("stat"),
                    "line": p.get("line"),
                    "direction": p.get("direction"),
                    "scraped_at": p.get("scraped_at"),
                    # Preserve structured context when available (event/team/market info)
                    "event_id": (p.get("meta") or {}).get("raw", {}).get("event_id") if isinstance(p.get("meta"), dict) else None,
                    "commence_time": (p.get("meta") or {}).get("raw", {}).get("commence_time") if isinstance(p.get("meta"), dict) else None,
                    "home_team": (p.get("meta") or {}).get("raw", {}).get("home_team") if isinstance(p.get("meta"), dict) else None,
                    "away_team": (p.get("meta") or {}).get("raw", {}).get("away_team") if isinstance(p.get("meta"), dict) else None,
                    "bookmaker_key": (p.get("meta") or {}).get("raw", {}).get("bookmaker_key") if isinstance(p.get("meta"), dict) else None,
                    "bookmaker_title": (p.get("meta") or {}).get("raw", {}).get("bookmaker_title") if isinstance(p.get("meta"), dict) else None,
                    "market_key": (p.get("meta") or {}).get("raw", {}).get("market_key") if isinstance(p.get("meta"), dict) else None,
                    # Keep the readable raw string as well
                    "raw": p.get("raw"),
                }
                for p in unique
            ],
        }
        raw_file.write_text(json.dumps(raw_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✓ Wrote validator raw artifact: {raw_file.relative_to(Path(__file__).resolve().parents[1])}")
    except Exception:
        # Never hard fail: this is a convenience for the gate.
        pass

    quota = (meta or {}).get("quota") or {}
    last = quota.get("last_event_odds") or {}
    if last:
        print("\n  Quota (last request):")
        print(f"    remaining={last.get('remaining')} used={last.get('used')} last_cost={last.get('last_cost')}")

    return unique


# ==========================================================
# INTERACTIVE MENU
# ==========================================================

def interactive_menu():
    """Interactive menu for prop ingestion."""
    print("\n" + "=" * 60)
    print("🎯 PROP INGESTION PIPELINE")
    print("=" * 60)
    print("\n  [1] Scrape ALL sites (DK + PP + UD)")
    print("  [2] DraftKings Pick6 only")
    print("  [3] PrizePicks only")
    print("  [4] Underdog Fantasy only")
    print("  [5] View latest results")
    print("  [6] 🔐 Interactive Browse (new browser)")
    print("  [7] 🔌 Connect to Existing Chrome (use logged-in session)")
    print("  [8] 🧠 Persistent Profile Browse (recommended)")
    print("  [9] 🌐 Odds API (no scrape)")
    print("  [Q] Quit")
    
    choice = input("\n  Select: ").strip().upper()
    
    if choice == "1":
        run_pipeline(headless=False)
    elif choice == "2":
        run_single_site("draftkings", headless=False)
    elif choice == "3":
        run_single_site("prizepicks", headless=False)
    elif choice == "4":
        run_single_site("underdog", headless=False)
    elif choice == "5":
        if OUTPUT_LATEST.exists():
            with open(OUTPUT_LATEST) as f:
                data = json.load(f)
            print(f"\n  Latest: {data['timestamp']}")
            print(f"  Props: {data['total_props']}")
            print(f"  Parsed: {data['parsed_props']}")
            
            # Show first 10 parsed props
            parsed = [p for p in data['props'] if p.get('parsed')][:10]
            print("\n  Sample parsed props:")
            for p in parsed:
                print(f"    • {p['player']} | {p['stat']} | {p['line']} | {p['direction']}")
        else:
            print("  No data yet. Run a scrape first.")
    elif choice == "6":
        # Interactive browse mode - login and explore
        interactive_browse()
    elif choice == "7":
        # Connect to existing Chrome
        connect_to_existing_chrome()
    elif choice == "8":
        # Persistent profile browse (Playwright-managed profile)
        interactive_browse_persistent()
    elif choice == "9":
        run_odds_api(sport="NBA")
    elif choice == "Q":
        return
    else:
        print("  Invalid choice.")
    
    input("\n  Press Enter to continue...")
    interactive_menu()


def connect_to_existing_chrome():
    """
    Connect to your already-open Chrome browser.
    Extracts props from ALL open Underdog/PrizePicks/DraftKings tabs.
    
    REQUIRES: Chrome started with --remote-debugging-port=9222
    """
    print("\n" + "=" * 60)
    print("🔌 CONNECT TO EXISTING CHROME")
    print("=" * 60)
    print("\n  To use your existing Chrome with logged-in accounts:")
    print("\n  1. Close ALL Chrome windows completely")
    print("  2. Run this command to reopen Chrome with debugging:")
    print('\n     "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
    print("\n  3. Login to Underdog/DK/PP in that Chrome")
    print("  4. Navigate to the props page")
    print("  5. Come back here and press Enter")
    
    input("\n  Press Enter when Chrome is running with debug port...")
    
    try:
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is not available in this Python environment. "
                "Run this pipeline using the repo virtualenv: .venv\\Scripts\\python.exe"
            )

        with sync_playwright() as p:
            # Try multiple ports
            connected = False
            browser = None
            for port in [9222, 19222, 9223]:
                try:
                    browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
                    print(f"\n  ✓ Connected on port {port}!")
                    connected = True
                    break
                except:
                    continue
            
            if not connected or not browser:
                print("  ✗ Could not connect. Make sure Chrome is running with --remote-debugging-port=9222")
                return []
            
            # Get existing pages
            contexts = browser.contexts
            if not contexts:
                print("  ✗ No browser contexts found.")
                return []
            
            pages = contexts[0].pages
            if not pages:
                print("  ✗ No pages found.")
                return []
            
            print(f"\n  ✓ Found {len(pages)} open tabs:")
            
            all_props = []
            
            for i, pg in enumerate(pages):
                url = pg.url.lower()
                title = pg.title()[:40]
                
                # Determine source
                if 'underdog' in url:
                    source = 'Underdog'
                elif 'draftkings' in url or 'pick6' in url:
                    source = 'DraftKings'
                elif 'prizepicks' in url:
                    source = 'PrizePicks'
                else:
                    print(f"    [{i+1}] {title} (skipping - not a prop site)")
                    continue
                
                print(f"    [{i+1}] {title} ({source})")
                
                # Scroll to load content
                try:
                    for _ in range(3):
                        pg.mouse.wheel(0, 2000)
                        pg.wait_for_timeout(300)
                except:
                    pass
                
                # Extract using smart parser
                text = pg.inner_text('body')
                props = smart_extract_props(text, source)
                print(f"        → Found {len(props)} props")
                all_props.extend(props)
            
            # Dedupe
            seen = set()
            unique = []
            for prop in all_props:
                key = (prop.get('player'), prop.get('stat'), prop.get('line'), prop.get('direction'))
                if key not in seen:
                    seen.add(key)
                    unique.append(prop)
            
            all_props = unique
            
            print(f"\n  ✓ TOTAL UNIQUE PROPS: {len(all_props)}")
            
            # Show sample by player
            if all_props:
                print("\n  Sample props:")
                by_player = {}
                for p in all_props:
                    player = p['player']
                    if player not in by_player:
                        by_player[player] = []
                    by_player[player].append(p)
                
                for player, plist in list(by_player.items())[:8]:
                    print(f"\n    {player}:")
                    for pp in plist[:3]:
                        dir_char = "O" if pp['direction'] == 'higher' else "U"
                        print(f"      • {pp['stat']:<15} {pp['line']:>5} {dir_char}")
            
            # Auto-save
            if all_props:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_data = {
                    "timestamp": datetime.now().isoformat(),
                    "sites": ["chrome"],
                    "total_props": len(all_props),
                    "parsed_props": sum(1 for p in all_props if p.get("parsed")),
                    "players": len(set(p['player'] for p in all_props)),
                    "props": all_props
                }

                if _store_props_run is not None:
                    try:
                        output_data["run_id"] = _store_props_run(output_data)
                    except Exception:
                        output_data["run_id"] = None
                
                output_file = OUTPUT_DIR / f"props_chrome_{timestamp}.json"
                with open(output_file, "w") as f:
                    json.dump(output_data, f, indent=2)
                
                with open(OUTPUT_LATEST, "w") as f:
                    json.dump(output_data, f, indent=2)
                
                print(f"\n  ✓ Saved to {output_file.name}")
                print(f"  ✓ Updated {OUTPUT_LATEST.name}")
            
            return all_props
            
    except Exception as e:
        print(f"\n  ✗ Could not connect to Chrome: {e}")
        import traceback
        traceback.print_exc()
        print("\n  Make sure Chrome is running with:")
        print('     "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
        return []


def interactive_browse():
    """
    Open browser for manual login, then extract props.
    Useful when sites require authentication.
    """
    print("\n" + "=" * 60)
    print("🔐 INTERACTIVE BROWSE MODE")
    print("=" * 60)
    print("\n  This will open a NEW browser where you can:")
    print("    1. Navigate to any prop site")
    print("    2. Login if required")
    print("    3. Browse to the props page")
    print("    4. Press Enter in terminal to extract props")
    print("\n  Sites:")
    print("    • https://pick6.draftkings.com")
    print("    • https://app.prizepicks.com")
    print("    • https://underdogfantasy.com/pick-em")
    print("\n  💡 TIP: To use your EXISTING Chrome with saved logins,")
    print("         run with 'chrome' arg instead of 'browse'")
    
    input("\n  Press Enter to open browser...")
    
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not available in this Python environment. "
            "Run this pipeline using the repo virtualenv: .venv\\Scripts\\python.exe"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Set viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Start at Underdog
        page.goto("https://underdogfantasy.com/pick-em", timeout=60000)
        
        print("\n" + "=" * 60)
        print("🌐 BROWSER OPEN")
        print("=" * 60)
        print("\n  → Navigate to prop pages")
        print("  → Login if required")
        print("  → Make sure props are visible on screen")
        print("\n  When ready, come back here and press Enter to extract.")
        
        input("\n  Press Enter when props are visible...")
        
        # Scroll to load content
        print("\n  ⏳ Scrolling to load all props...")
        for _ in range(5):
            page.mouse.wheel(0, 3000)
            time.sleep(1)
        
        # Extract using smart parser
        print("\n  ⏳ Extracting props...")
        all_text = page.inner_text("body")
        
        # Detect source from URL
        url = page.url.lower()
        if 'underdog' in url:
            source = 'Underdog'
        elif 'draftkings' in url or 'pick6' in url:
            source = 'DraftKings'
        elif 'prizepicks' in url:
            source = 'PrizePicks'
        else:
            source = 'Manual'
        
        results = smart_extract_props(all_text, source)
        
        print(f"\n  ✓ Found {len(results)} props from {source}")
        
        # Show sample
        if results:
            print("\n  Sample props:")
            by_player = {}
            for p in results:
                player = p['player']
                if player not in by_player:
                    by_player[player] = []
                by_player[player].append(p)
            
            for player, plist in list(by_player.items())[:8]:
                print(f"\n    {player}:")
                for pp in plist[:3]:
                    dir_char = "O" if pp['direction'] == 'higher' else "U"
                    print(f"      • {pp['stat']:<15} {pp['line']:>5} {dir_char}")
        
        # Auto-save
        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "sites": [source.lower()],
                "total_props": len(results),
                "parsed_props": sum(1 for p in results if p.get("parsed")),
                "players": len(set(p['player'] for p in results)),
                "props": results
            }

            if _store_props_run is not None:
                try:
                    output_data["run_id"] = _store_props_run(output_data)
                except Exception:
                    output_data["run_id"] = None
            
            output_file = OUTPUT_DIR / f"props_manual_{timestamp}.json"
            with open(output_file, "w") as f:
                json.dump(output_data, f, indent=2)
            
            with open(OUTPUT_LATEST, "w") as f:
                json.dump(output_data, f, indent=2)
            
            print(f"\n  ✓ Saved to {output_file.name}")
            print(f"  ✓ Updated {OUTPUT_LATEST.name}")
        
        browser.close()


def interactive_browse_persistent():
    """Open a Playwright persistent context using `chrome_profile/`.

    This is the most reliable way to keep logins without relying on Chrome CDP.
    """
    print("\n" + "=" * 60)
    print("🧠 PERSISTENT PROFILE BROWSE MODE")
    print("=" * 60)
    print("\n  Uses profile dir:")
    print(f"    {CHROME_PROFILE_DIR}")
    print("\n  This keeps cookies/sessions so you don't have to re-login every time.")
    print("\n  Workflow:")
    print("    1) A browser opens (Playwright-managed)")
    print("    2) Login to DK/PP/Underdog")
    print("    3) Navigate to props")
    print("    4) Press Enter here to extract")

    input("\n  Press Enter to open persistent browser...")

    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not available in this Python environment. "
            "Run this pipeline using the repo virtualenv: .venv\\Scripts\\python.exe"
        )

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_DIR),
            headless=False,
            viewport={"width": 1920, "height": 1080},
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://underdogfantasy.com/pick-em", timeout=60000)

        print("\n" + "=" * 60)
        print("🌐 BROWSER OPEN (PERSISTENT)")
        print("=" * 60)
        input("\n  Press Enter when props are visible...")

        # Scroll to load more content
        print("\n  ⏳ Scrolling to load all props...")
        for _ in range(6):
            try:
                page.mouse.wheel(0, 3500)
                time.sleep(1)
            except Exception:
                break

        print("\n  ⏳ Extracting props...")
        all_text = page.inner_text("body")

        url = page.url.lower()
        if 'underdog' in url:
            source = 'Underdog'
        elif 'draftkings' in url or 'pick6' in url:
            source = 'DraftKings'
        elif 'prizepicks' in url:
            source = 'PrizePicks'
        else:
            source = 'Persistent'

        results = smart_extract_props(all_text, source)
        print(f"\n  ✓ Found {len(results)} props from {source}")

        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "sites": ["persistent"],
                "total_props": len(results),
                "parsed_props": sum(1 for p in results if p.get("parsed")),
                "players": len(set(p['player'] for p in results)),
                "props": results,
            }

            if _store_props_run is not None:
                try:
                    output_data["run_id"] = _store_props_run(output_data)
                except Exception:
                    output_data["run_id"] = None

            output_file = OUTPUT_DIR / f"props_persistent_{timestamp}.json"
            with open(output_file, "w") as f:
                json.dump(output_data, f, indent=2)

            with open(OUTPUT_LATEST, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"\n  ✓ Saved to {output_file.name}")
            print(f"  ✓ Updated {OUTPUT_LATEST.name}")

        context.close()


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "all":
            run_pipeline(headless=False)
        elif arg in ["dk", "draftkings"]:
            run_single_site("draftkings")
        elif arg in ["pp", "prizepicks"]:
            run_single_site("prizepicks")
        elif arg in ["ud", "underdog"]:
            run_single_site("underdog")
        elif arg == "headless":
            run_pipeline(headless=True)
        elif arg in ["browse", "login", "manual"]:
            interactive_browse()
        elif arg == "chrome":
            connect_to_existing_chrome()
        elif arg in ["oddsapi", "odds", "api"]:
            run_odds_api(sport="NBA")
        else:
            print(f"Unknown argument: {arg}")
            print("Usage: python prop_ingestion_pipeline.py [all|dk|pp|ud|headless|browse|chrome|oddsapi]")
    else:
        interactive_menu()
