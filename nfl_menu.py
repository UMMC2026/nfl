"""
NFL PROPS ANALYZER - COMMAND CENTER
====================================
Divisional Round Edition - HOU@KC, BAL@BUF, GB@DET, TB@SF
Single entry point for NFL prop analysis workflows.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
NFL_SETTINGS_FILE = PROJECT_ROOT / ".nfl_analyzer_settings.json"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
NFL_ROLE_FILE = PROJECT_ROOT / "nfl_role_mapping.json"

# Cache for role mapping (lazy loaded to prevent freezing)
_role_mapping_cache = None

# Default settings
DEFAULT_SETTINGS = {
    "soft_gates": True,
    "balanced_report": True,
    "default_format": "power",
    "default_legs": 3,
    "last_slate": None,
    "last_label": None,
}

# ESPN API URLs
ESPN_NFL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


def _get_todays_matchups_from_espn() -> list:
    """Fetch today's NFL games from ESPN API."""
    import requests
    
    try:
        r = requests.get(ESPN_NFL_SCOREBOARD_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        games = []
        for event in data.get("events", []):
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            
            comp = competitions[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue
            
            # Find home and away teams
            home_team = None
            away_team = None
            for c in competitors:
                abbr = c.get("team", {}).get("abbreviation", "")
                if c.get("homeAway") == "home":
                    home_team = abbr
                elif c.get("homeAway") == "away":
                    away_team = abbr
            
            if home_team and away_team:
                # Get game time
                game_date = event.get("date", "")
                time_str = ""
                if game_date:
                    try:
                        from dateutil import parser
                        dt = parser.parse(game_date)
                        time_str = dt.strftime("%a %I:%M%p ET")
                    except:
                        pass
                
                games.append({
                    "away": away_team,
                    "home": home_team,
                    "time": time_str,
                    "source": "espn",
                })
        
        return games
    except Exception:
        return []


def _get_todays_matchups_fallback() -> list:
    """Final fallback when all data sources fail."""
    # Return empty list instead of hardcoded games
    return []


def get_todays_matchups(today=None) -> list:
    """Return today's games from ESPN API, nflverse schedule, or empty fallback.

    Priority:
    1. ESPN API (live data)
    2. data/nflverse/schedules/games.parquet (if present)
    3. Empty list (no hardcoded games)
    """
    # Try ESPN API first
    espn_games = _get_todays_matchups_from_espn()
    if espn_games:
        return espn_games
    
    # Try nflverse parquet file
    schedule_path = PROJECT_ROOT / "data" / "nflverse" / "schedules" / "games.parquet"
    if not schedule_path.exists():
        return _get_todays_matchups_fallback()

    try:
        import pandas as pd
    except Exception:
        return _get_todays_matchups_fallback()

    if today is None:
        today = datetime.now().date()

    try:
        df = pd.read_parquet(schedule_path)
    except Exception:
        return _get_todays_matchups_fallback()

    # Identify common columns
    away_col = "away_team" if "away_team" in df.columns else ("away" if "away" in df.columns else None)
    home_col = "home_team" if "home_team" in df.columns else ("home" if "home" in df.columns else None)
    if not away_col or not home_col:
        return _get_todays_matchups_fallback()

    date_col = None
    for c in ("gameday", "game_date", "date", "start_time", "kickoff"):
        if c in df.columns:
            date_col = c
            break
    if not date_col:
        return _get_todays_matchups_fallback()

    # Parse to date and filter
    dt = pd.to_datetime(df[date_col], errors="coerce")
    df = df.assign(_date=dt.dt.date)
    df_today = df[df["_date"] == today]

    # If nothing for today, fallback.
    if df_today.empty:
        return _get_todays_matchups_fallback()

    # If multiple seasons exist, keep the latest season (common with aggregated schedules)
    if "season" in df_today.columns:
        try:
            latest_season = int(df_today["season"].max())
            df_today = df_today[df_today["season"] == latest_season]
        except Exception:
            pass

    # Sort by time if present
    time_col = None
    for c in ("start_time", "start_time_utc", "gametime"):
        if c in df_today.columns:
            time_col = c
            break
    if time_col:
        df_today = df_today.sort_values(by=time_col)

    matchups = []
    for _, row in df_today.iterrows():
        away = str(row.get(away_col, "")).strip().upper()
        home = str(row.get(home_col, "")).strip().upper()
        if not away or not home or away == "NAN" or home == "NAN":
            continue

        time_str = ""
        if time_col:
            try:
                t = pd.to_datetime(row.get(time_col), errors="coerce")
                if pd.notna(t):
                    time_str = t.strftime("%a %I:%M%p")
            except Exception:
                time_str = str(row.get(time_col, ""))

        matchups.append({
            "away": away,
            "home": home,
            "time": time_str,
            "source": "nflverse",
        })

    return matchups or _get_todays_matchups_fallback()


def build_opponent_map_from_matchups(matchups: list) -> dict:
    opp_by_team = {}
    for g in matchups or []:
        away = g.get("away")
        home = g.get("home")
        if away and home:
            opp_by_team[away] = home
            opp_by_team[home] = away
    return opp_by_team


def load_settings() -> dict:
    if NFL_SETTINGS_FILE.exists():
        try:
            return {**DEFAULT_SETTINGS, **json.loads(NFL_SETTINGS_FILE.read_text())}
        except:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    NFL_SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def load_role_mapping() -> dict:
    """Load role mapping with caching to prevent repeated file reads."""
    global _role_mapping_cache
    if _role_mapping_cache is None:
        if NFL_ROLE_FILE.exists():
            _role_mapping_cache = json.loads(NFL_ROLE_FILE.read_text())
        else:
            _role_mapping_cache = {}
    return _role_mapping_cache


def invalidate_role_cache():
    """Call this after modifying the role mapping file."""
    global _role_mapping_cache
    _role_mapping_cache = None


def clear_screen():
    """Clear screen using ANSI escape codes (faster, no subprocess)."""
    # ANSI escape: \033[2J clears screen, \033[H moves cursor to home
    print("\033[2J\033[H", end="", flush=True)


def print_header():
    print("\n" + "=" * 70)
    print("      NFL PROPS ANALYZER v1.0 - DIVISIONAL ROUND")
    print("          HOU@KC | BAL@BUF | GB@DET | TB@SF")
    print("=" * 70)


def print_menu(settings: dict):
    soft = "ON " if settings["soft_gates"] else "OFF"
    bal = "ON " if settings["balanced_report"] else "OFF"
    fmt = settings.get("default_format", "power").upper()
    legs = settings.get("default_legs", 3)
    
    print(f"""
  CURRENT: SoftGates={soft} | Balanced={bal} | Format={fmt} | Legs={legs}
  
  +================================================================+
  |  NFL PREGAME WORKFLOW                                          |
  |  --------------------                                          |
  |  [1] INGEST NFL SLATE       - Paste Underdog NFL props         |
  |  [A] ODDS API INGEST        - Auto-fetch props (No manual paste)|
  |  [I] INJURY CHECK           - Live ESPN injuries + status      |
  |  [2] ANALYZE NFL SLATE      - Run probability analysis         |
  |  [3] MATCHUP CONTEXT        - Team rankings & schemes          |
  |  [4] ROSTER CHECK           - Verify players in mapping        |
  |                                                                |
  |  NFL POSTGAME WORKFLOW                                         |
  |  ---------------------                                         |
  |  [5] RESOLVE NFL PICKS      - Enter results, track accuracy    |
  |  [6] NFL CALIBRATION        - Historical accuracy review       |
  |                                                                |
  |  MANAGEMENT                                                    |
  |  ----------                                                    |
  |  [7] VIEW IR LIST           - Players on injured reserve       |
  |  [8] ADD PLAYER             - Add missing player to mapping    |
  |  [9] SETTINGS               - Toggle features & modes          |
  |                                                                |
  |  REPORTS & BROADCAST                                           |
  |  -------------------                                           |
  |  [R] EXPORT REPORT          - Save full human-readable report  |
  |  [V] VIEW RESULTS           - Show latest NFL analysis         |
  |  [C] COMPREHENSIVE REPORT   - Full detailed analysis + AI      |
  |  [T] SEND TO TELEGRAM       - Broadcast picks to Telegram      |
  |                                                                |
  |  [10] TOP 10 + UMMCSPORTS   - Best picks + AI + Context → Ch.  |
  |  [0] EXIT                                                      |
  +================================================================+
""")


def parse_nfl_lines_multiline(lines: list, classifications: dict, ir_list: list, partial_lookup: dict, stat_map: dict) -> list:
    """
    Parse MULTI-LINE Underdog format (like NBA parser).
    Format:
      - "athlete or team avatar" signals next line is player name
      - Standalone number = line value
      - Stat name on following line
      - "Higher" / "Lower" on subsequent lines
    """
    import re
    picks = []
    current_player = None
    current_team = None
    expect_player_name = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Player marker
        if "athlete or team avatar" in line.lower():
            expect_player_name = True
            continue
        
        # Player name (right after marker)
        if expect_player_name:
            # Reset for new player
            current_player = None
            current_team = "UNK"
            
            # Lookup player in classifications
            player_info = classifications.get(line, {})
            if player_info:
                current_player = line
                current_team = player_info.get("team", "UNK")
            else:
                # Try partial match
                name_lower = line.lower()
                matched = False
                for name_key, full_name in partial_lookup.items():
                    if name_lower == full_name.lower() or name_lower in full_name.lower():
                        current_player = full_name
                        player_info = classifications.get(full_name, {})
                        current_team = player_info.get("team", "UNK")
                        matched = True
                        break
                if not matched:
                    # Use the name as-is if not found
                    current_player = line
                    current_team = "UNK"
            expect_player_name = False
            continue
        
        # Extract team from matchup string (e.g., "DEN vs NE - 2:00PM CST" or "NE @ DEN - 2:00PM CST")
        matchup_match = re.match(r'^([A-Z]{2,3})\s*(vs|@)\s*([A-Z]{2,3})\s*-', line)
        if matchup_match and current_player:
            team1 = matchup_match.group(1)
            separator = matchup_match.group(2)
            # Player is on the first team (before "vs" or "@")
            current_team = team1
            continue
        
        # Stat line (standalone number)
        if re.match(r'^[\d\.]+$', line):
            line_val = float(line)
            
            # Next line should be stat name
            if i + 1 < len(lines):
                stat_line = lines[i + 1].strip().lower()
                stat_key = None
                
                # Try multi-word stat match first (longer matches)
                for stat_phrase, skey in sorted(stat_map.items(), key=lambda x: -len(x[0])):
                    if stat_phrase in stat_line:
                        stat_key = skey
                        break
                
                if not stat_key:
                    continue
                
                # Look for Higher/Lower in next few lines
                has_higher = False
                has_lower = False
                for j in range(i + 2, min(i + 10, len(lines))):
                    check_line = lines[j].strip().lower()
                    if 'higher' in check_line:
                        has_higher = True
                    elif 'lower' in check_line:
                        has_lower = True
                    # Stop at next number or player marker
                    if re.match(r'^[\d\.]+$', check_line) or 'athlete or team avatar' in check_line:
                        break
                
                if current_player and stat_key:
                    player_info = classifications.get(current_player, {})
                    team = player_info.get("team", current_team or "UNK")
                    position = player_info.get("position", "UNK")
                    on_ir = current_player in ir_list
                    
                    if has_higher:
                        picks.append({
                            "player": current_player,
                            "team": team,
                            "position": position,
                            "stat": stat_key,
                            "line": line_val,
                            "direction": "higher",
                            "on_ir": on_ir,
                            "raw": f"{current_player} {stat_key} {line_val} higher"
                        })
                    if has_lower:
                        picks.append({
                            "player": current_player,
                            "team": team,
                            "position": position,
                            "stat": stat_key,
                            "line": line_val,
                            "direction": "lower",
                            "on_ir": on_ir,
                            "raw": f"{current_player} {stat_key} {line_val} lower"
                        })
                    # If no direction found, default to higher
                    if not has_higher and not has_lower:
                        picks.append({
                            "player": current_player,
                            "team": team,
                            "position": position,
                            "stat": stat_key,
                            "line": line_val,
                            "direction": "higher",
                            "on_ir": on_ir,
                            "raw": f"{current_player} {stat_key} {line_val} higher"
                        })
    
    return picks


def _is_underdog_web_noise_line(line: str) -> bool:
    """Heuristics for modern Underdog web copy/paste noise.

    Examples seen in the wild:
      - "Trending"
      - "13h 59m"
      - "496.4K"
      - "Privacy"
    """
    import re

    s = (line or "").strip()
    if not s:
        return True

    low = s.lower()
    if low in {"trending", "privacy"}:
        return True

    # View-count style tokens (e.g., 496.4K, 1.2M)
    if re.match(r"^\d+(?:\.\d+)?[kKmM]$", s):
        return True

    # Relative time stamps (e.g., 13h 59m)
    if re.match(r"^\d+\s*h\s*\d+\s*m$", low):
        return True

    return False


def _looks_like_underdog_web_multiline(lines: list) -> bool:
    """Detect the Underdog web multi-line format (TEAM - POS blocks)."""
    import re

    for l in lines:
        s = (l or "").strip()
        if re.match(r"^[A-Z]{2,3}\s*-\s*[A-Z]{1,4}$", s):
            return True
    return False


def _clean_underdog_player_name(raw: str) -> str:
    """Best-effort cleanup for player lines that include badges (e.g., 'Money Mouth')."""
    import re

    s = (raw or "").strip()
    if not s:
        return ""

    # Insert spaces for CamelCase badge concatenation (e.g., DarnoldMoney -> Darnold Money)
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Strip common trailing badge words/phrases (non-exhaustive, safe)
    badge_words = {
        "goblin",
        "demon",
        "discount",
        "boost",
        "trending",
        "money",
        "mouth",
    }

    parts = [p for p in re.split(r"\s+", s) if p]
    # Remove trailing badge-ish tokens
    while parts and parts[-1].lower().strip("-_") in badge_words:
        parts.pop()
    s = " ".join(parts).strip()

    return s


def _normalize_underdog_web_to_single_lines(lines: list) -> list:
    """Convert Underdog web multi-line paste into single-line strings.

    Underdog often pastes as blocks like:
      PlayerName(+badges)
      TEAM - POS
      PlayerName
      vs/@ Opponent ...
      235.50.5
      Pass Yards
      Less
      More

    We normalize each block into:
      "PlayerName More 235.5 Pass Yards"

    The existing single-line parser then handles mapping and stat keys.
    """
    import re

    cleaned = [l.strip() for l in lines if not _is_underdog_web_noise_line(l)]

    out: list[str] = []
    i = 0
    while i < len(cleaned):
        s = cleaned[i]

        # Anchor on TEAM - POS lines to find block boundaries
        if re.match(r"^[A-Z]{2,3}\s*-\s*[A-Z]{1,4}$", s):
            # Player name is usually just above OR just below this line.
            player_candidates: list[str] = []
            if i - 1 >= 0:
                player_candidates.append(cleaned[i - 1])
            if i + 1 < len(cleaned):
                player_candidates.append(cleaned[i + 1])

            player = ""
            for cand in player_candidates:
                cand_s = _clean_underdog_player_name(cand)
                # Avoid accidentally using matchup lines
                if cand_s and not re.search(r"\b(vs\.?|@)\b", cand_s, re.IGNORECASE):
                    player = cand_s
                    break

            # Scan forward for: numeric line -> stat line -> direction (More/Less)
            j = i + 1
            line_val = None
            stat_text = None
            direction = None

            while j < len(cleaned) and (j - i) <= 20:
                token = cleaned[j]
                low = token.lower()

                # Stop if another TEAM - POS begins (new block)
                if j != i and re.match(r"^[A-Z]{2,3}\s*-\s*[A-Z]{1,4}$", token):
                    break

                if line_val is None:
                    # Only accept line values from numeric-only-ish lines.
                    # This avoids accidentally capturing time strings like "Sun 2:00pm".
                    if re.search(r"[A-Za-z]", token):
                        j += 1
                        continue
                    m = re.search(r"\d+(?:\.\d+)?", token)
                    if m:
                        # Use the *first* number on the line. This avoids issues like "235.50.5".
                        try:
                            line_val = float(m.group(0))
                        except Exception:
                            line_val = None
                    j += 1
                    continue

                if stat_text is None:
                    # Find a non-direction, non-matchup text line as the stat label
                    if low in {"more", "less"}:
                        j += 1
                        continue
                    if re.search(r"\b(vs\.?|@)\b", token, re.IGNORECASE):
                        j += 1
                        continue
                    if token and not re.search(r"\d", token):
                        stat_text = token.strip()
                    j += 1
                    continue

                # direction
                if low in {"more", "less"}:
                    direction = "More" if low == "more" else "Less"
                    break

                j += 1

            if player and (line_val is not None) and stat_text and direction:
                out.append(f"{player} {direction} {line_val} {stat_text}")
                # Advance to continue after this block
                i = max(i + 1, j + 1)
                continue

        i += 1

    return out


def parse_nfl_lines(lines_text: str) -> list:
    """Parse pasted NFL lines into structured picks - FLEXIBLE PARSER.
    
    Supports TWO formats:
    1. MULTI-LINE (Underdog copy-paste): "athlete or team avatar" + player name + number + stat
    2. SINGLE-LINE: "Player stat line direction" 
    """
    import re
    
    picks = []
    lines = lines_text.strip().split("\n")
    
    # Extended NFL stat mappings (case-insensitive)
    stat_map = {
        "pass yards": "pass_yds",
        "passing yards": "pass_yds",
        "pass yds": "pass_yds",
        "rush yards": "rush_yds",
        "rushing yards": "rush_yds",
        "rush yds": "rush_yds",
        "rec yards": "rec_yds",
        "receiving yards": "rec_yds",
        "rec yds": "rec_yds",
        "receptions": "receptions",
        "recs": "receptions",
        "catches": "receptions",
        "pass tds": "pass_tds",
        "passing tds": "pass_tds",
        "passing touchdowns": "pass_tds",
        "rush tds": "rush_tds",
        "rushing tds": "rush_tds",
        "rushing touchdowns": "rush_tds",
        "rec tds": "rec_tds",
        "receiving tds": "rec_tds",
        "anytime td": "anytime_td",
        "anytime touchdown": "anytime_td",
        "completions": "completions",
        "comps": "completions",
        "attempts": "pass_attempts",
        "pass attempts": "pass_attempts",
        "interceptions": "interceptions",
        "ints": "interceptions",
        "rush attempts": "rush_attempts",
        "carries": "rush_attempts",
        "rush att": "rush_attempts",
        "targets": "targets",
        "longest reception": "longest_rec",
        "longest rush": "longest_rush",
        "longest pass": "longest_pass",
        "yards": "total_yds",
        "total yards": "total_yds",
        "fantasy points": "fantasy_pts",
        "fantasy": "fantasy_pts",
        "kicking points": "kicking_pts",
        # Kicker milestone props
        "1+ fg or xp made in each quarter": "fg_xp_each_qtr",
        "fg or xp made in each quarter": "fg_xp_each_qtr",
        "1+ fg made": "fg_made",
        "field goals made": "fg_made",
        "fg made": "fg_made",
        "extra points made": "xp_made",
        "xp made": "xp_made",
        "1+ xp made": "xp_made",
        # Defense/Special Teams
        "sacks": "sacks",
        "tackles": "tackles",
        "solo tackles": "solo_tackles",
        "combined tackles": "tackles",
        "tackles + assists": "tackles_assists",
        "pass deflections": "pass_deflections",
        "forced fumbles": "forced_fumbles",
        "fumbles recovered": "fumbles_recovered",
        "defensive ints": "interceptions_def",
        "defensive interceptions": "interceptions_def",
        "interception": "interceptions_def",
        # Punter stats
        "total punts": "punts",
        "punts": "punts",
        "avg yards per punt": "punt_avg",
        "average punt yards": "punt_avg",
        "punt yards": "punt_yds",
        # Combo stats
        "rush + rec yards": "rush_rec_yds",
        "rush + receiving yards": "rush_rec_yds",
        "pass + rush yards": "pass_rush_yds",
        "pass + rushing yards": "pass_rush_yds",
        # TD combos
        "rush + rec tds": "rush_rec_tds",
        "rushing + receiving tds": "rush_rec_tds",
        "anytime td scorer": "anytime_td",
        # First quarter props
        "1q rec yards": "1q_rec_yds",
        "1q rush yards": "1q_rush_yds",
        "1q pass yards": "1q_pass_yds",
        "1q receiving yards": "1q_rec_yds",
        "1q rushing yards": "1q_rush_yds",
        "1q passing yards": "1q_pass_yds",
        # Fantasy
        "fantasy points": "fantasy_pts",
    }
    
    # Single-word stat shortcuts
    single_stat_map = {
        "passing": "pass_yds",
        "rushing": "rush_yds",
        "receiving": "rec_yds",
        "receptions": "receptions",
        "completions": "completions",
        "attempts": "pass_attempts",
        "carries": "rush_attempts",
        "targets": "targets",
        "interceptions": "interceptions",
        "assists": "def_assists",
        "sacks": "sacks",
        "tackles": "tackles",
    }
    
    role_mapping = load_role_mapping()
    classifications = role_mapping.get("player_classifications", {})
    ir_list = role_mapping.get("injured_reserve", [])
    
    # Build partial name lookup (last name -> full name)
    partial_lookup = {}
    for full_name in classifications.keys():
        parts = full_name.split()
        if len(parts) >= 2:
            partial_lookup[parts[-1].lower()] = full_name  # Last name
            partial_lookup[parts[0].lower()] = full_name   # First name
        partial_lookup[full_name.lower()] = full_name
    
    # DETECT FORMAT: Check if this looks like multi-line Underdog paste.
    # Variant A: older Underdog paste includes "athlete or team avatar" markers.
    is_multiline = any("athlete or team avatar" in line.lower() for line in lines)

    if is_multiline:
        print("  [i] Detected multi-line Underdog format, using multi-line parser...")
        return parse_nfl_lines_multiline(lines, classifications, ir_list, partial_lookup, stat_map)

    # Variant B: modern Underdog web paste (TEAM - POS blocks).
    if _looks_like_underdog_web_multiline(lines):
        print("  [i] Detected Underdog web multi-line format, normalizing...")
        normalized = _normalize_underdog_web_to_single_lines(lines)
        if normalized:
            lines = normalized
    
    # SINGLE-LINE PARSER (fallback for manual entry)
    print("  [i] Using single-line parser...")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip obvious non-prop lines
        if line.upper() in ["END", "DONE", "QUIT", "EXIT"]:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        
        # GARBAGE FILTER: Skip lines that look like metadata/junk from Underdog copy/paste
        # Skip lines that are just multipliers (e.g., "1.03x", "0.94X", "Higher 1.06x")
        if re.match(r'^[\d\.]+[xX]?$', line.strip()):
            continue
        if re.match(r'^(higher|lower)\s*[\d\.]+[xX]?$', line.strip(), re.IGNORECASE):
            continue
        # Skip game time headers (e.g., "DEN vs BUF - 3:30PM CST", "7:00PM CST")
        if re.search(r'\d+:\d+\s*(am|pm|AM|PM|CST|EST|PST|ET|CT)', line):
            continue
        # Skip lines with "vs" or "@" that don't have player stats (game headers)
        if re.search(r'\b(vs\.?|@)\b', line, re.IGNORECASE) and not re.search(r'(yards?|yds|rec|rush|pass|td|sack|tackle)', line, re.IGNORECASE):
            continue
        # Skip lines that are just "Picks ()" or similar
        if re.match(r'^picks?\s*\([^)]*\)$', line.strip(), re.IGNORECASE):
            continue
        # Skip "More picks (X)" lines
        if re.match(r'^more\s+picks?\s*\(\d+\)$', line.strip(), re.IGNORECASE):
            continue
        # Skip Underdog UI elements (but not kicker props that mention "quarter")
        # First check if it's a kicker prop we want to keep
        is_kicker_prop = any(kp in line.lower() for kp in ['fg', 'xp', 'field goal', 'extra point', 'kicking'])

        # Skip standalone YES/NO UI tokens (word-level), but do NOT substring-match these
        # because it breaks real names like "Darnold" (contains "no").
        if line.strip().lower() in {"yes", "no"}:
            continue
        
        if not is_kicker_prop and any(junk in line.lower() for junk in [
            'athlete or team avatar', 'projection refreshing', 'expand all', 'collapse all',
            '1st quarter', '2nd quarter', '3rd quarter', '4th quarter', 'expired',
            'buffalo bills', 'denver broncos', 'san francisco', 'seattle seahawks',
            'houston texans', 'new england', 'los angeles rams', 'chicago bears',
            'all nfl', '- 1st', '- 2nd', '- 3rd', '- 4th'
        ]):
            continue
        # Skip score lines like "BUF 0 - DEN 0"
        if re.match(r'^[A-Z]{2,3}\s+\d+\s*-\s*[A-Z]{2,3}\s+\d+', line.strip()):
            continue
        # Skip quarter/half props (2Q, 2H, 1Q, etc. at START of line as the "player")
        if re.match(r'^[12][QH]\s', line.strip()):
            continue
        # Skip "2H 1st Drive" type props (not supported)
        if '2h 1st drive' in line.lower() or '2h targets' in line.lower():
            continue
        # Skip standalone numbers (like scores: "0", "6", etc.)
        if re.match(r'^\d+$', line.strip()):
            continue

        # Skip Underdog web copy noise tokens (view counts / time badges)
        if _is_underdog_web_noise_line(line):
            continue
            
        # STEP 1: Find direction (search from end)
        direction = None
        line_lower = line.lower()
        dir_patterns = [
            (r'\bhigher\b', "higher"),
            (r'\blower\b', "lower"),
            (r'\bmore\b', "higher"),
            (r'\bless\b', "lower"),
            (r'\bover\b', "higher"),
            (r'\bunder\b', "lower"),
            (r'\bo\b', "higher"),  # shorthand
            (r'\bu\b', "lower"),   # shorthand
        ]
        
        for pattern, dir_val in dir_patterns:
            if re.search(pattern, line_lower):
                direction = dir_val
                # Remove direction word from line for easier parsing
                line = re.sub(pattern, '', line_lower, flags=re.IGNORECASE).strip()
                break
        
        # Default to "higher" if no direction found
        if not direction:
            direction = "higher"
        
        # STEP 2: Find the line value (number)
        numbers = re.findall(r'(\d+\.?\d*)', line)
        if not numbers:
            continue
        
        # Take the last number as the line (usually "Player Stat 24.5")
        line_val = float(numbers[-1])
        
        # Remove the line number for player/stat parsing
        line_no_number = re.sub(r'\b' + re.escape(numbers[-1]) + r'\b', '', line).strip()
        
        # STEP 3: Find stat type
        stat = None
        stat_found_at = -1
        remaining_text = line_no_number.lower()
        
        # Try multi-word stats first (longer matches)
        for stat_phrase, stat_key in sorted(stat_map.items(), key=lambda x: -len(x[0])):
            if stat_phrase in remaining_text:
                stat = stat_key
                stat_found_at = remaining_text.find(stat_phrase)
                remaining_text = remaining_text.replace(stat_phrase, '', 1).strip()
                break
        
        # Try single-word stats
        if not stat:
            for word in remaining_text.split():
                if word in single_stat_map:
                    stat = single_stat_map[word]
                    remaining_text = remaining_text.replace(word, '', 1).strip()
                    break
        
        # Default stat based on common patterns
        if not stat:
            stat = "unknown"
        
        # STEP 4: Find player name
        player = None
        
        # Clean up remaining text (should be mostly player name)
        remaining_text = ' '.join(remaining_text.split())  # normalize spaces
        
        # Try exact match first
        for name in classifications.keys():
            if name.lower() in remaining_text.lower():
                player = name
                break
        
        # Try partial match (last name or first name)
        if not player:
            words = remaining_text.split()
            for word in words:
                word_clean = re.sub(r'[^\w]', '', word).lower()
                if word_clean in partial_lookup:
                    player = partial_lookup[word_clean]
                    break
        
        # Fallback: use remaining text as player name
        if not player:
            # Clean up: remove common junk
            player = re.sub(r'\s+', ' ', remaining_text).strip()
            player = player.title()  # Capitalize
        
        if not player or len(player) < 2:
            continue
        
        # Get player info
        player_info = classifications.get(player, {})
        team = player_info.get("team", "UNK")
        position = player_info.get("position", "UNK")
        
        # VALIDATION: Reject picks that have BOTH unknown player AND unknown stat
        # This filters out garbage that slipped through
        if team == "UNK" and stat == "unknown":
            print(f"  ⚠ Skipped (unrecognized): {line.strip()[:50]}")
            continue
        
        # Check IR
        on_ir = player in ir_list
        
        pick = {
            "player": player,
            "team": team,
            "position": position,
            "stat": stat,
            "line": line_val,
            "direction": direction,
            "on_ir": on_ir,
            "raw": line.strip()
        }
        picks.append(pick)
        print(f"  ✓ Parsed: {player} | {stat} | {line_val} | {direction}")
    
    return picks


def ingest_nfl_slate(settings: dict) -> list:
    """Ingest NFL props from user input."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  INGEST NFL SLATE")
    print("=" * 70)
    
    print("\nGames:")
    todays = get_todays_matchups()
    if todays:
        src = todays[0].get("source", "")
        if src == "espn":
            print("\n  (auto-loaded from ESPN API)")
        elif src == "nflverse":
            print("\n  (auto-loaded from nflverse schedules)")
        for g in todays:
            t = f" - {g.get('time')}" if g.get('time') else ""
            print(f"    {g.get('away')} @ {g.get('home')}{t}")
    else:
        print("\n  [!] No games found for today via ESPN API or nflverse.")
        print("  You can still enter props manually.\n")
    
    print("\n" + "-" * 70)
    print("Paste Underdog NFL lines below. Type END when finished:")
    print("-" * 70)
    print(">>> Paste your lines now (type END on its own line when done):")
    sys.stdout.flush()  # Flush before input loop
    
    lines = []
    line_count = 0
    while True:
        try:
            sys.stdout.flush()  # Flush before each input
            line = input()
            if line.strip().upper() == "END":
                break
            if line.strip():  # Only count non-empty lines
                lines.append(line)
                line_count += 1
                # Show progress every 10 lines
                if line_count % 10 == 0:
                    print(f"    ... {line_count} lines received ...")
                    sys.stdout.flush()
        except (EOFError, KeyboardInterrupt):
            print("\n  Input interrupted.")
            break
    
    lines_text = "\n".join(lines)
    picks = parse_nfl_lines(lines_text)
    
    if not picks:
        print("\n[!] No valid picks parsed. Check format.")
        input("\nPress Enter to continue...")
        return []

    # Hydrate opponent from today's matchup list when missing.
    # (Underdog prop lines generally don't include opponent explicitly.)
    opp_by_team = build_opponent_map_from_matchups(get_todays_matchups())

    for p in picks:
        team = p.get("team")
        if team and not p.get("opponent"):
            inferred = opp_by_team.get(team)
            if inferred:
                p["opponent"] = inferred
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = f"nfl_divisional_{timestamp}"
    
    OUTPUTS_DIR.mkdir(exist_ok=True)
    slate_file = OUTPUTS_DIR / f"nfl_slate_{label}.json"
    
    with open(slate_file, "w") as f:
        json.dump({"label": label, "picks": picks, "timestamp": timestamp}, f, indent=2)
    
    settings["last_slate"] = str(slate_file)
    settings["last_label"] = label
    save_settings(settings)
    
    # Display parsed picks
    print(f"\n[✓] Parsed {len(picks)} picks:")
    print("-" * 70)
    
    ir_count = 0
    unk_count = 0
    for p in picks:
        status = ""
        if p.get("on_ir"):
            status = " [IR!]"
            ir_count += 1
        elif p.get("team") == "UNK":
            status = " [UNKNOWN]"
            unk_count += 1
        
        print(f"  {p['player']:25} {p['team']:4} {p['stat']:15} {p['line']:>6.1f} {p['direction']:6}{status}")
    
    print("-" * 70)
    if ir_count:
        print(f"[!] WARNING: {ir_count} players on IR - exclude from entries!")
    if unk_count:
        print(f"[!] WARNING: {unk_count} players not in mapping - add with option [8]")
    
    print(f"\n[✓] Saved to: {slate_file}")
    input("\nPress Enter to continue...")
    
    return picks


def run_injury_check_menu():
    """[I] Run live ESPN injury check for NFL teams."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [I] NFL INJURY CHECK — Live ESPN Data")
    print("=" * 70)
    
    try:
        from nfl_injury_gate import run_injury_check
        
        # Try to detect teams from today's games
        teams = None
        try:
            matchups = get_todays_matchups()
            if matchups:
                teams = []
                for game in matchups:
                    away = game.get('away', '')
                    home = game.get('home', '')
                    if away: teams.append(away)
                    if home: teams.append(home)
                print(f"\n  Today's teams: {', '.join(teams)}")
            else:
                print("\n  No games detected — checking all teams")
        except Exception:
            print("\n  Checking all teams...")
        
        report = run_injury_check(teams=teams, verbose=True)
        
        if not report:
            print("\n  No injuries reported.")
        
    except ImportError:
        print("\n  [!] nfl_injury_gate.py not found.")
    except Exception as e:
        print(f"\n  [!] Error: {e}")
    
    input("\nPress Enter to continue...")


def analyze_nfl_slate(settings: dict):
    """Run NFL probability analysis on ingested slate."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  ANALYZE NFL SLATE")
    print("=" * 70)
    
    # Load last slate
    slate_file = settings.get("last_slate")
    if not slate_file or not Path(slate_file).exists():
        print("\n[!] No slate loaded. Use option [1] to ingest first.")
        input("\nPress Enter to continue...")
        return
    
    with open(slate_file, "r") as f:
        slate = json.load(f)
    
    picks = slate.get("picks", [])
    label = slate.get("label", "unknown")
    
    print(f"\nAnalyzing: {label}")
    print(f"Picks: {len(picks)}")
    print("-" * 70)
    
    # ============================================================
    # STEP 1: INJURY CHECK (Live ESPN) — Before analysis
    # ============================================================
    print("\n[STEP 1] Checking injuries (ESPN live)...")
    try:
        from nfl_injury_gate import fetch_nfl_injury_report, apply_injury_gate, display_injury_report
        
        # Get teams from picks
        pick_teams = list(set(p.get('team', '') for p in picks if p.get('team')))
        if pick_teams:
            injury_report = fetch_nfl_injury_report(pick_teams)
            
            if injury_report:
                display_injury_report(injury_report, teams_playing=pick_teams)
                
                # Apply injury gate to picks
                picks, modified, excluded = apply_injury_gate(picks, injury_report)
                if excluded > 0:
                    print(f"\n  [GATE] {excluded} players EXCLUDED (Out/IR)")
                if modified > 0:
                    print(f"  [GATE] {modified} players flagged (Questionable/Doubtful)")
            else:
                print("  No injuries found for today's teams.")
        else:
            print("  No teams detected in slate.")
    except ImportError:
        print("  [!] Injury gate not available — skipping")
    except Exception as e:
        print(f"  [!] Injury check error: {e} — continuing without")
    
    # ============================================================
    # STEP 2: STATS REFRESH — Update and cache stats
    # ============================================================
    print("\n[STEP 2] Refreshing stats...")
    try:
        from nfl_stats_cache import hydrate_stats_for_picks, preflight_stats_check
        picks = hydrate_stats_for_picks(picks, use_cache=True, verbose=True)
        
        # Preflight validation
        passed, warnings = preflight_stats_check(picks)
        if warnings:
            for w in warnings[:5]:  # Show max 5 warnings
                print(w)
        if not passed:
            print("\n  [!!] Stats validation FAILED — results may be unreliable")
            confirm = input("  Continue anyway? (Y/N): ").strip().upper()
            if confirm != 'Y':
                input("\nPress Enter to continue...")
                return
    except ImportError:
        print("  [!] Stats cache not available — using default hydrator")
    except Exception as e:
        print(f"  [!] Stats refresh error: {e} — using default hydrator")
    
    print("\n" + "-" * 70)
    print("[STEP 3] Running probability analysis...")
    
    # Import analyzer
    try:
        from analyze_nfl_props import calculate_nfl_probability, load_nfl_role_mapping
        role_mapping = load_nfl_role_mapping()
    except ImportError:
        print("[!] analyze_nfl_props.py not found. Using basic analysis.")
        role_mapping = load_role_mapping()
    
    results = []
    for pick in picks:
        # Skip IR players
        if pick.get("on_ir"):
            pick["probability"] = 0.0
            pick["grade"] = "IR"
            pick["action"] = "EXCLUDE"
            results.append(pick)
            continue
        
        # Calculate probability AND hydrate stats
        try:
            from hydrators.nfl_stat_hydrator import hydrate_nfl_stat
            
            # Get hydrated stats
            stat_data = hydrate_nfl_stat(
                player=pick["player"],
                stat=pick["stat"],
                team=pick["team"],
                season=2025,
                games=10,
                position=pick.get("position")
            )
            
            # Store stats in pick
            pick["sample_size"] = stat_data.get("samples", 0)
            pick["recent_avg"] = stat_data.get("mean", 0.0)
            pick["sigma"] = stat_data.get("std_dev", 0.0)
            pick["line_gap"] = (pick["recent_avg"] - pick["line"]) if pick["recent_avg"] else 0.0
            
            # Calculate probability
            player_info = {"position": pick["position"], "team": pick["team"]}
            prob = calculate_nfl_probability(
                player=pick["player"],
                stat=pick["stat"],
                line=pick["line"],
                direction=pick["direction"],
                player_info=player_info,
                role_mapping=role_mapping
            )
        except Exception as e:
            print(f"[ERROR] {pick['player']}/{pick['stat']}: {e}")
            prob = 0.50  # Default if calculation fails
            pick["sample_size"] = 0
            pick["recent_avg"] = 0.0
            pick["sigma"] = 0.0
            pick["line_gap"] = 0.0
        
        pick["probability"] = prob
        
        # Apply injury penalty (Questionable/Doubtful players)
        injury_penalty = pick.get("injury_penalty", 0.0)
        if injury_penalty > 0 and injury_penalty < 1.0:
            prob = prob * (1.0 - injury_penalty)
            pick["probability"] = prob
            pick["injury_adjusted"] = True
        
        # Grade and action
        if prob >= 0.65:
            pick["grade"] = "A"
            pick["action"] = "STRONG"
        elif prob >= 0.58:
            pick["grade"] = "B"
            pick["action"] = "LEAN"
        elif prob >= 0.52:
            pick["grade"] = "C"
            pick["action"] = "CONSIDER"
        else:
            pick["grade"] = "D"
            pick["action"] = "FADE"
        
        results.append(pick)
    
    # DEDUPLICATION PIPELINE
    print(f"\n[PIPELINE] Applying filters...")
    print(f"  Raw results: {len(results)}")
    
    # FILTER 1: Remove duplicates (same player/stat/line/direction)
    seen = set()
    deduped = []
    for r in results:
        key = (r['player'], r['stat'], r['line'], r['direction'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    print(f"  After deduplication: {len(deduped)}")
    
    # FILTER 2: Remove garbage lines (too small to be real props)
    MIN_LINES = {
        'pass_yds': 150.0,
        'rush_yds': 30.0,
        'rec_yds': 15.0,
        'receptions': 2.0,
        'pass_tds': 0.5,
        'rush_tds': 0.5,
        'rec_tds': 0.5,
        'anytime_td': 0.5,
        'completions': 10.0,
        'attempts': 15.0,
        'rush_attempts': 10.0
    }
    
    real_lines = []
    for r in deduped:
        min_line = MIN_LINES.get(r['stat'], 0.5)
        if r['line'] >= min_line:
            real_lines.append(r)
    print(f"  After garbage filter: {len(real_lines)}")
    
    # FILTER 3: Remove both directions (keep best probability for each player/stat)
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in real_lines:
        key = (r['player'], r['stat'])
        grouped[key].append(r)
    
    filtered = []
    for key, edges in grouped.items():
        if len(edges) == 1:
            filtered.append(edges[0])
        else:
            # Keep higher probability
            best = max(edges, key=lambda x: x.get('probability', 0))
            filtered.append(best)
    print(f"  After direction filter: {len(filtered)}")
    
    results = filtered
    
    # Sort by probability
    results.sort(key=lambda x: x.get("probability", 0), reverse=True)
    
    # Display results
    print(f"\n{'PLAYER':25} {'TEAM':4} {'STAT':15} {'LINE':>6} {'DIR':6} {'PROB':>6} {'GRADE':5} {'ACTION'}")
    print("-" * 85)
    
    for r in results:
        prob_str = f"{r['probability']*100:.1f}%" if r['probability'] > 0 else "N/A"
        print(f"{r['player']:25} {r['team']:4} {r['stat']:15} {r['line']:>6.1f} {r['direction']:6} {prob_str:>6} {r['grade']:5} {r['action']}")
    
    # Summary
    strong = [r for r in results if r["action"] == "STRONG"]
    lean = [r for r in results if r["action"] == "LEAN"]
    
    print("-" * 85)
    print(f"\nSUMMARY: {len(strong)} STRONG | {len(lean)} LEAN | {len(results)} Total")
    
    if strong:
        print(f"\nTOP PLAYS:")
        for s in strong[:5]:
            print(f"  ★ {s['player']} {s['stat']} {s['direction']} {s['line']} ({s['probability']*100:.1f}%)")
    
    # Save results
    result_file = OUTPUTS_DIR / f"nfl_analysis_{label}.json"
    with open(result_file, "w") as f:
        json.dump({"label": label, "results": results}, f, indent=2)
    
    print(f"\n[✓] Saved to: {result_file}")
    input("\nPress Enter to continue...")


def show_matchup_context():
    """Display team matchup context for current week."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  NFL MATCHUP CONTEXT - CURRENT WEEK")
    print("=" * 70)
    
    try:
        from nfl_team_context import NFL_TEAM_CONTEXT
        # Load latest slate file for matchups
        settings = load_settings()
        slate_file = settings.get("last_slate")
        if not slate_file or not Path(slate_file).exists():
            print("\n[!] No slate loaded. Use option [1] to ingest first.")
            input("\nPress Enter to continue...")
            return
        with open(slate_file, "r") as f:
            slate = json.load(f)
        # Build set of unique matchups from picks.
        # If opponent is missing, infer from today's matchups (nflverse if available).
        opp_by_team = build_opponent_map_from_matchups(get_todays_matchups())

        matchups = set()
        missing = set()
        for pick in slate.get("picks", []):
            team = pick.get("team")
            opponent = pick.get("opponent") or (opp_by_team.get(team) if team else None)
            if team and opponent:
                matchup = tuple(sorted([team, opponent]))
                matchups.add(matchup)
            elif team:
                missing.add(team)
        if not matchups:
            print("\n[!] No matchups found in slate.")
            if missing:
                sample = ", ".join(sorted([t for t in missing if t])[:12])
                print(f"[!] Teams missing opponent mapping: {sample}")
                print("    Tip: update DIVISIONAL_MATCHUPS at top of nfl_menu.py for the current week.")
            input("\nPress Enter to continue...")
            return
        print("\nMATCHUPS (from current slate):")
        print("-" * 60)
        for matchup in sorted(matchups):
            team1, team2 = matchup
            print(f"\n  {team1} vs {team2}")
            print("  " + "-" * 40)
            away_ctx = NFL_TEAM_CONTEXT.get(team1)
            home_ctx = NFL_TEAM_CONTEXT.get(team2)
            print(f"    Offense:")
            away_rush = away_ctx.rush_off_rank if away_ctx else "N/A"
            away_pass = away_ctx.pass_off_rank if away_ctx else "N/A"
            home_rush = home_ctx.rush_off_rank if home_ctx else "N/A"
            home_pass = home_ctx.pass_off_rank if home_ctx else "N/A"
            print(f"      {team1}: Rush #{away_rush}, Pass #{away_pass}")
            print(f"      {team2}: Rush #{home_rush}, Pass #{home_pass}")
            print(f"    Defense:")
            away_def_rush = away_ctx.rush_def_rank if away_ctx else "N/A"
            away_def_pass = away_ctx.pass_def_rank if away_ctx else "N/A"
            home_def_rush = home_ctx.rush_def_rank if home_ctx else "N/A"
            home_def_pass = home_ctx.pass_def_rank if home_ctx else "N/A"
            print(f"      {team1}: vs Rush #{away_def_rush}, vs Pass #{away_def_pass}")
            print(f"      {team2}: vs Rush #{home_def_rush}, vs Pass #{home_def_pass}")
            if home_ctx and getattr(home_ctx, "dome", False):
                print(f"    Venue: DOME (indoor)")
            else:
                print(f"    Venue: Outdoor")
    except ImportError:
        print("\n[!] nfl_team_context.py not found. Add team context data.")
    input("\nPress Enter to continue...")


def roster_check():
    """Verify players are in role mapping."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  NFL ROSTER CHECK")
    print("=" * 70)
    
    role_mapping = load_role_mapping()
    classifications = role_mapping.get("player_classifications", {})
    
    # Group by team
    teams = {}
    for player, info in classifications.items():
        team = info.get("team", "UNK")
        if team not in teams:
            teams[team] = []
        teams[team].append({"name": player, "position": info.get("position", "UNK")})
    
    # Show divisional round teams
    div_teams = ["KC", "HOU", "BUF", "BAL", "DET", "GB", "SF", "TB"]
    
    print("\nDivisional Round Teams:")
    for team in div_teams:
        players = teams.get(team, [])
        print(f"\n  {team} ({len(players)} players):")
        
        # Group by position
        by_pos = {}
        for p in players:
            pos = p["position"]
            if pos not in by_pos:
                by_pos[pos] = []
            by_pos[pos].append(p["name"])
        
        for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
            if pos in by_pos:
                print(f"    {pos}: {', '.join(by_pos[pos])}")
    
    input("\nPress Enter to continue...")


def view_ir_list():
    """Display injured reserve list."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  NFL INJURED RESERVE LIST")
    print("=" * 70)
    
    role_mapping = load_role_mapping()
    ir_list = role_mapping.get("injured_reserve", [])
    classifications = role_mapping.get("player_classifications", {})
    
    if not ir_list:
        print("\n  No players on IR list.")
    else:
        print(f"\n  {len(ir_list)} players on IR:\n")
        for player in ir_list:
            info = classifications.get(player, {})
            team = info.get("team", "UNK")
            pos = info.get("position", "UNK")
            print(f"    ✗ {player:25} {team:4} {pos}")
    
    print("\n  [!] These players are auto-excluded from analysis")
    input("\nPress Enter to continue...")


def resolve_nfl_picks():
    """Resolve NFL picks with actual results."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  RESOLVE NFL PICKS - Phase 3 Error Attribution")
    print("=" * 70)
    
    try:
        from ufa.analysis.nfl_error_attribution import NFLErrorAttribution
        engine = NFLErrorAttribution()
        
        print(f"\n  Historical picks loaded: {len(engine.resolved_picks)}")
        
        # Find latest analysis
        nfl_files = sorted(OUTPUTS_DIR.glob("nfl_analysis_*.json"), reverse=True)
        if not nfl_files:
            print("\n  No NFL analysis files found to resolve.")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n  Available analysis files:")
        for i, f in enumerate(nfl_files[:5], 1):
            print(f"    [{i}] {f.name}")
        
        sys.stdout.flush()  # Prevent freeze
        choice = input("\n  Select file to resolve (or Enter to skip): ").strip()
        sys.stdout.flush()
        if not choice:
            input("\nPress Enter to continue...")
            return
        
        try:
            selected = nfl_files[int(choice) - 1]
            with open(selected, "r") as f:
                data = json.load(f)
        except:
            print("  [!] Invalid selection")
            input("\nPress Enter to continue...")
            return
        
        results = data.get("results", [])
        print(f"\n  Found {len(results)} picks to resolve.")
        print("  Enter actual stat values (or 's' to skip, 'q' to quit):\n")
        
        for r in results:
            player = r.get("player", "Unknown")
            stat = r.get("stat", "unknown")
            line = r.get("line", 0)
            direction = r.get("direction", "higher")
            prob = r.get("probability", 0.5)
            
            sys.stdout.flush()  # Prevent freeze
            actual = input(f"  {player} {stat} {line} {direction.upper()} (P={prob:.0%}): ").strip()
            sys.stdout.flush()
            
            if actual.lower() == 'q':
                break
            if actual.lower() == 's' or not actual:
                continue
            
            try:
                actual_val = float(actual)
                pick_dict = {
                    "player": player,
                    "team": r.get("team", "UNK"),
                    "position": r.get("position", "UNK"),
                    "opponent": r.get("opponent", "UNK"),
                    "stat": stat,
                    "line": line,
                    "direction": direction,
                    "p_hit": prob,
                    "posterior_mu": r.get("posterior_mu", 0),
                    "posterior_sigma": r.get("posterior_sigma", 0),
                    "confidence": r.get("confidence", "medium"),
                }
                resolved = engine.resolve(pick_dict, actual_val, datetime.now().strftime("%Y-%m-%d"))
                status = "✓ HIT" if resolved.hit else "✗ MISS"
                print(f"    → {status}")
            except ValueError:
                print(f"    → Skipped (invalid number)")
        
        # Save and show summary
        engine.save_history()
        metrics = engine.summary_metrics()
        
        print(f"\n  {'=' * 50}")
        print(f"  Total resolved: {metrics['n_picks']}")
        print(f"  Hit rate: {metrics['hit_rate']:.1%}")
        print(f"  Brier score: {metrics['brier_score']:.4f}")
        
    except ImportError as e:
        print(f"\n  [!] Error: {e}")
    
    input("\nPress Enter to continue...")


def nfl_calibration_report():
    """Show NFL calibration and bias analysis."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  NFL CALIBRATION REPORT - Phase 3 Analysis")
    print("=" * 70)
    
    try:
        from ufa.analysis.nfl_error_attribution import NFLErrorAttribution
        engine = NFLErrorAttribution()
        
        if not engine.resolved_picks:
            print("\n  No resolved picks found.")
            print("  Use [5] RESOLVE NFL PICKS to add outcomes first.")
            input("\nPress Enter to continue...")
            return
        
        print(engine.full_analysis())
        
    except ImportError as e:
        print(f"\n  [!] Error: {e}")
    
    input("\nPress Enter to continue...")


def add_player_to_mapping():
    """Add a missing player to the role mapping."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  ADD PLAYER TO MAPPING")
    print("=" * 70)
    
    print("\nEnter player details:")
    name = input("  Player Name: ").strip()
    if not name:
        return
    
    team = input("  Team (e.g., KC, BUF): ").strip().upper()
    position = input("  Position (QB/RB/WR/TE/K/DEF): ").strip().upper()
    
    if not team or not position:
        print("[!] Team and position required.")
        input("\nPress Enter to continue...")
        return
    
    if position not in ["QB", "RB", "WR", "TE", "K", "DEF"]:
        print(f"[!] Invalid position: {position}")
        input("\nPress Enter to continue...")
        return
    
    # Load and update mapping
    role_mapping = load_role_mapping()
    if "player_classifications" not in role_mapping:
        role_mapping["player_classifications"] = {}
    
    role_mapping["player_classifications"][name] = {
        "team": team,
        "position": position
    }
    
    # Save
    with open(NFL_ROLE_FILE, "w") as f:
        json.dump(role_mapping, f, indent=2)
    
    print(f"\n[✓] Added: {name} ({team}, {position})")
    input("\nPress Enter to continue...")


def comprehensive_report_with_ai():
    """Generate comprehensive report with AI commentary."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [C] COMPREHENSIVE REPORT WITH AI COMMENTARY")
    print("=" * 70)
    
    # Find latest NFL analysis
    nfl_files = sorted(OUTPUTS_DIR.glob("nfl_analysis_*.json"), reverse=True)
    
    if not nfl_files:
        print("\n  No NFL analysis found. Run [2] ANALYZE first.")
        input("\nPress Enter to continue...")
        return
    
    latest = nfl_files[0]
    print(f"\nSource: {latest.name}")
    
    try:
        import subprocess
        
        # Generate comprehensive report
        print("\n🏈 Generating comprehensive NFL report...")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/nfl_comprehensive_report.py",
                "--file", str(latest)
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=Path.cwd(),
            timeout=60
        )
        
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"\n[X] Error: {result.stderr}")
        
        # Generate AI commentary
        print("\n🤖 Generating AI commentary...")
        result2 = subprocess.run(
            [
                sys.executable,
                "engines/nfl/nfl_ai_commentary.py",
                "--file", str(latest)
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=Path.cwd(),
            timeout=30
        )
        
        if result2.returncode == 0:
            print(result2.stdout)
        else:
            print(f"\n[X] AI Commentary Error: {result2.stderr}")
        
        print("\n[OK] Comprehensive report with AI commentary complete!")
    
    except Exception as e:
        print(f"\n[X] Error: {e}")
    
    input("\nPress Enter to continue...")


def send_nfl_to_telegram():
    """Send NFL picks to Telegram with AI commentary."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [T] SEND NFL PICKS TO TELEGRAM")
    print("=" * 70)
    
    # Find latest NFL analysis
    nfl_files = sorted(OUTPUTS_DIR.glob("nfl_analysis_*.json"), reverse=True)
    
    if not nfl_files:
        print("\n  No NFL analysis found. Run [2] ANALYZE first.")
        input("\nPress Enter to continue...")
        return
    
    latest = nfl_files[0]
    print(f"\nSource: {latest.name}")
    
    try:
        import subprocess
        
        print("\n📱 Generating Telegram message with AI commentary...")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/nfl_comprehensive_report.py",
                "--file", str(latest),
                "--telegram"
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=Path.cwd(),
            timeout=60
        )
        
        if result.returncode == 0:
            print(result.stdout)
            print("\n[OK] Telegram broadcast complete!")
        else:
            print(f"\n[X] Error: {result.stderr}")
    
    except Exception as e:
        print(f"\n[X] Error: {e}")
    
    input("\nPress Enter to continue...")


def send_top10_telegram_with_context():
    """Send TOP 10 NFL picks with AI + game context to UMMCSPORTS Telegram channel."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [10] TOP 10 NFL PICKS + AI + GAME CONTEXT → UMMCSPORTS")
    print("=" * 70)
    
    # Find latest NFL analysis
    nfl_files = sorted(OUTPUTS_DIR.glob("nfl_analysis_*.json"), reverse=True)
    
    if not nfl_files:
        print("\n  ❌ No NFL analysis found. Run [2] ANALYZE first.")
        input("\nPress Enter to continue...")
        return
    
    latest = nfl_files[0]
    print(f"\n📁 Source: {latest.name}")
    
    try:
        import subprocess
        
        print("\n🏈 Generating TOP 10 picks with AI + matchup context...")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/nfl_top10_telegram.py"
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',  # Handle emojis and special characters on Windows
            cwd=Path.cwd(),
            timeout=60
        )
        
        if result.returncode == 0:
            print(result.stdout)
            print("\n✅ TOP 10 picks sent to UMMCSPORTS!")
        else:
            print(f"\n❌ Error: {result.stderr}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    input("\nPress Enter to continue...")


def export_nfl_full_report(settings: dict):
    """Export NFL analysis to full human-readable report."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  [R] EXPORT NFL FULL REPORT")
    print("=" * 70)
    
    # Find latest NFL analysis
    nfl_files = sorted(OUTPUTS_DIR.glob("nfl_analysis_*.json"), reverse=True)
    
    if not nfl_files:
        print("\n  No NFL analysis found. Run [2] ANALYZE first.")
        input("\nPress Enter to continue...")
        return
    
    latest = nfl_files[0]
    print(f"\nSource: {latest.name}")
    
    try:
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/generate_full_report.py",
                "--sport", "NFL",
                "--input", str(latest)
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=Path.cwd(),
            timeout=60
        )
        
        if result.returncode == 0:
            print(result.stdout)
            print("\n[OK] NFL full report generated!")
        else:
            print(f"\n[X] Error: {result.stderr}")
    
    except Exception as e:
        print(f"\n[X] Error generating report: {e}")
    
    input("\nPress Enter to continue...")


def view_results(settings: dict):
    """View latest NFL analysis results."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  VIEW NFL RESULTS")
    print("=" * 70)
    
    # Find latest analysis file
    if not OUTPUTS_DIR.exists():
        print("\n  No outputs found.")
        input("\nPress Enter to continue...")
        return
    
    nfl_files = sorted(OUTPUTS_DIR.glob("nfl_analysis_*.json"), reverse=True)
    
    if not nfl_files:
        print("\n  No NFL analysis files found.")
        input("\nPress Enter to continue...")
        return
    
    print(f"\n  Found {len(nfl_files)} NFL analysis files:\n")
    for i, f in enumerate(nfl_files[:10], 1):
        print(f"  [{i}] {f.name}")
    
    choice = input("\n  Select file (or Enter for latest): ").strip()
    
    try:
        idx = int(choice) - 1 if choice else 0
        selected = nfl_files[idx]
    except:
        selected = nfl_files[0]
    
    with open(selected, "r") as f:
        data = json.load(f)
    
    results = data.get("results", [])
    label = data.get("label", "unknown")
    
    print(f"\n  Showing: {label}")
    print("  " + "-" * 60)
    
    for r in results:
        prob_str = f"{r['probability']*100:.1f}%" if r.get('probability', 0) > 0 else "N/A"
        print(f"  {r['player']:25} {r['stat']:12} {r['line']:>5.1f} {r['direction']:6} {prob_str:>6} {r.get('grade', '?')}")
    
    input("\nPress Enter to continue...")


def odds_api_ingest_nfl() -> list:
    """Fetch NFL props from Odds API (automatic, no manual paste)."""
    import os
    from dotenv import load_dotenv
    
    clear_screen()
    print("\n" + "=" * 70)
    print("  🛰️  NFL ODDS API INGEST (Automatic)")
    print("=" * 70)
    
    # Load .env
    load_dotenv(override=True)
    api_key = (os.getenv("ODDS_API_KEY") or os.getenv("ODDSAPI_KEY") or "").strip()
    
    if not api_key:
        print("\n  ✗ Missing ODDS_API_KEY")
        print("    Set ODDS_API_KEY in .env (repo root) and try again.")
        print("    (Alias supported: ODDSAPI_KEY)")
        print("    Example: ODDS_API_KEY=your_api_key_here")
        input("\nPress Enter to continue...")
        return []
    
    print("\n  [i] Fetching NFL props from Odds API...")
    
    try:
        from ingestion.prop_ingestion_pipeline import run_odds_api
        
        ingested = run_odds_api(sport="NFL")
        
        if not ingested or len(ingested) == 0:
            print("\n  ✗ Odds API ingest returned 0 props")
            print("    Check ODDS_API_* settings and your subscription/credits.")
            print("    Note: NFL props may not be available in offseason.")
            input("\nPress Enter to continue...")
            return []
        
        print(f"\n  ✓ Fetched {len(ingested)} props from Odds API")
        
        # Convert OddsAPI format to NFL menu format
        picks = []
        role_mapping = load_role_mapping()
        classifications = role_mapping.get("player_classifications", {})
        ir_list = role_mapping.get("injured_reserve", [])
        
        for prop in ingested:
            player = prop.get("player", "")
            stat = prop.get("stat", "")
            line = prop.get("line", 0)
            direction = prop.get("direction", "higher").lower()
            
            # Get player info
            player_info = classifications.get(player, {})
            team = player_info.get("team", "UNK")
            position = player_info.get("position", "UNK")
            on_ir = player in ir_list
            
            pick = {
                "player": player,
                "team": team,
                "position": position,
                "stat": stat,
                "line": line,
                "direction": direction,
                "on_ir": on_ir,
                "raw": f"{player} {stat} {line} {direction} (OddsAPI)"
            }
            picks.append(pick)
            print(f"  ✓ {player} | {stat} | {line} | {direction}")
        
        # Hydrate opponent from today's matchups
        opp_by_team = build_opponent_map_from_matchups(get_todays_matchups())
        for p in picks:
            team = p.get("team")
            if team and not p.get("opponent"):
                inferred = opp_by_team.get(team)
                if inferred:
                    p["opponent"] = inferred
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = f"nfl_oddsapi_{timestamp}"
        
        OUTPUTS_DIR.mkdir(exist_ok=True)
        slate_file = OUTPUTS_DIR / f"nfl_slate_{label}.json"
        
        with open(slate_file, "w") as f:
            json.dump({"label": label, "picks": picks, "timestamp": timestamp, "source": "OddsAPI"}, f, indent=2)
        
        # Update settings
        settings = load_settings()
        settings["last_slate"] = str(slate_file)
        settings["last_label"] = label
        save_settings(settings)
        
        print("\n" + "-" * 70)
        print(f"[✓] Saved {len(picks)} props to: {slate_file}")
        print(f"[✓] Source: Odds API")
        print(f"\n[i] Next step: Use [2] ANALYZE NFL SLATE to run probability analysis")
        
        input("\nPress Enter to continue...")
        return picks
        
    except ImportError as e:
        print(f"\n  ✗ Import error: {e}")
        print("    Make sure ingestion/prop_ingestion_pipeline.py exists.")
        input("\nPress Enter to continue...")
        return []
    except Exception as e:
        print(f"\n  ✗ Odds API ingest failed: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to continue...")
        return []


def settings_menu(settings: dict):
    """Toggle settings."""
    while True:
        clear_screen()
        print("\n" + "=" * 70)
        print("  NFL SETTINGS")
        print("=" * 70)
        
        print(f"""
  [1] Soft Gates:     {'ON' if settings['soft_gates'] else 'OFF'}
  [2] Balanced Report: {'ON' if settings['balanced_report'] else 'OFF'}
  [3] Default Format:  {settings.get('default_format', 'power').upper()}
  [4] Default Legs:    {settings.get('default_legs', 3)}
  [0] Back
""")
        
        sys.stdout.flush()  # Prevent freeze
        choice = input("  Toggle: ").strip()
        sys.stdout.flush()
        
        if choice == "0":
            break
        elif choice == "1":
            settings["soft_gates"] = not settings["soft_gates"]
        elif choice == "2":
            settings["balanced_report"] = not settings["balanced_report"]
        elif choice == "3":
            settings["default_format"] = "flex" if settings.get("default_format") == "power" else "power"
        elif choice == "4":
            legs = input("  Enter legs (2-6): ").strip()
            try:
                settings["default_legs"] = max(2, min(6, int(legs)))
            except:
                pass
        
        save_settings(settings)


def main():
    import time
    settings = load_settings()
    
    # Pre-load role mapping once at startup
    load_role_mapping()
    
    while True:
        clear_screen()
        print_header()
        print_menu(settings)
        
        # Flush all buffers before input to prevent freeze
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass
        
        try:
            choice = input("  Select: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n  Exiting...")
            sys.stdout.flush()
            break
        
        # Flush after input and add delay
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass
        time.sleep(0.05)  # Buffer delay to prevent freeze
        
        if choice == "1":
            ingest_nfl_slate(settings)
        elif choice == "A":
            odds_api_ingest_nfl()
        elif choice == "I":
            run_injury_check_menu()
        elif choice == "2":
            analyze_nfl_slate(settings)
        elif choice == "3":
            show_matchup_context()
        elif choice == "4":
            roster_check()
        elif choice == "5":
            resolve_nfl_picks()
        elif choice == "6":
            nfl_calibration_report()
        elif choice == "7":
            view_ir_list()
        elif choice == "8":
            add_player_to_mapping()
            invalidate_role_cache()  # Reload cache after adding player
        elif choice == "9":
            settings_menu(settings)
        elif choice == "R":
            export_nfl_full_report(settings)
        elif choice == "V":
            view_results(settings)
        elif choice == "C":
            comprehensive_report_with_ai()
        elif choice == "T":
            send_nfl_to_telegram()
        elif choice == "10":
            send_top10_telegram_with_context()
        elif choice == "0":
            print("\n  Exiting NFL Menu...")
            break
        else:
            print(f"\n  [!] Invalid choice: {choice}")
            sys.stdout.flush()
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
