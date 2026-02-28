"""
Auto-Resolve Picks - Fetches box scores and updates calibration_history.csv

Usage:
    python resolve_picks.py --date 2026-01-16
    python resolve_picks.py --file outputs/CLE_PHI_FULL_RISK_FIRST_20260116_FROM_UD.json
    python resolve_picks.py --date 2026-01-16 --dry-run
"""

import argparse
import json
import csv
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, List, Any
import time
import re

try:
    import requests  # type: ignore
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

# Try imports - graceful fallback
try:
    from nba_api.stats.endpoints import boxscoretraditionalv3, boxscoretraditionalv2, scoreboardv2
    from nba_api.stats.static import players, teams
    HAS_NBA_API = True
except ImportError:
    HAS_NBA_API = False
    print("[WARN] nba_api not installed - will use manual entry mode")

CALIBRATION_FILE = Path("calibration_history.csv")
OUTPUTS_DIR = Path("outputs")

# Stat mapping from our keys to box score columns
STAT_MAP = {
    'points': 'PTS',
    'rebounds': 'REB',
    'assists': 'AST',
    '3pm': 'FG3M',
    'steals': 'STL',
    'blocks': 'BLK',
    'turnovers': 'TO',
    'pts+reb+ast': ['PTS', 'REB', 'AST'],
    # Common aliases
    'pra': ['PTS', 'REB', 'AST'],
    'p+r+a': ['PTS', 'REB', 'AST'],
    'points+rebounds+assists': ['PTS', 'REB', 'AST'],
    'pts_reb_ast': ['PTS', 'REB', 'AST'],
    'pts+reb': ['PTS', 'REB'],
    'pts+ast': ['PTS', 'AST'],
    'reb+ast': ['REB', 'AST'],
    'stl+blk': ['STL', 'BLK'],
    # New stats
    'dunks': 'DUNK',  # May need special handling
    'fga': 'FGA',
    'fgm': 'FGM',
    'ftm': 'FTM',
    'fta': 'FTA',
    'minutes': 'MIN',
    # First quarter stats (require period-specific box scores)
    '1q_pts': '1Q_PTS',
    '1q_reb': '1Q_REB',
    '1q_ast': '1Q_AST',
    '1q_points': '1Q_PTS',
    '1q_rebounds': '1Q_REB',
    '1q_assists': '1Q_AST',
}

# Team abbreviation normalization
TEAM_MAP = {
    'PHI': 'PHI', 'SIXERS': 'PHI', '76ERS': 'PHI',
    'CLE': 'CLE', 'CAVS': 'CLE', 'CAVALIERS': 'CLE',
    'NOP': 'NOP', 'NO': 'NOP', 'PELICANS': 'NOP',
    'IND': 'IND', 'PACERS': 'IND',
    'LAL': 'LAL', 'LAKERS': 'LAL',
    'BOS': 'BOS', 'CELTICS': 'BOS',
    'MIL': 'MIL', 'BUCKS': 'MIL',
    'DEN': 'DEN', 'NUGGETS': 'DEN',
    'PHX': 'PHX', 'PHO': 'PHX', 'SUNS': 'PHX',
    'GSW': 'GSW', 'GS': 'GSW', 'WARRIORS': 'GSW',
    'MIA': 'MIA', 'HEAT': 'MIA',
    'DAL': 'DAL', 'MAVS': 'DAL', 'MAVERICKS': 'DAL',
    'MEM': 'MEM', 'GRIZZLIES': 'MEM',
    'SAC': 'SAC', 'KINGS': 'SAC',
    'ATL': 'ATL', 'HAWKS': 'ATL',
    'CHI': 'CHI', 'BULLS': 'CHI',
    'NYK': 'NYK', 'NY': 'NYK', 'KNICKS': 'NYK',
    'BKN': 'BKN', 'BRK': 'BKN', 'NETS': 'BKN',
    'TOR': 'TOR', 'RAPTORS': 'TOR',
    'OKC': 'OKC', 'THUNDER': 'OKC',
    'POR': 'POR', 'BLAZERS': 'POR', 'TRAILBLAZERS': 'POR',
    'UTA': 'UTA', 'JAZZ': 'UTA',
    'MIN': 'MIN', 'WOLVES': 'MIN', 'TIMBERWOLVES': 'MIN',
    'HOU': 'HOU', 'ROCKETS': 'HOU',
    'SAS': 'SAS', 'SA': 'SAS', 'SPURS': 'SAS',
    'LAC': 'LAC', 'CLIPPERS': 'LAC',
    'ORL': 'ORL', 'MAGIC': 'ORL',
    'DET': 'DET', 'PISTONS': 'DET',
    'CHA': 'CHA', 'CHO': 'CHA', 'HORNETS': 'CHA',
    'WAS': 'WAS', 'WIZARDS': 'WAS',
}


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching"""
    # Handle common variations
    name = name.strip().lower()
    # Remove Jr., III, etc.
    for suffix in [' jr.', ' jr', ' iii', ' ii', ' iv']:
        name = name.replace(suffix, '')
    return name


def get_game_ids_for_date(game_date: str) -> List[Dict]:
    """Get all NBA game IDs for a given date using nba_api"""
    if not HAS_NBA_API:
        return []
    
    try:
        # nba_api expects MM/DD/YYYY; many callsites pass YYYY-MM-DD.
        gd = game_date
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", game_date.strip()):
                gd = datetime.strptime(game_date.strip(), "%Y-%m-%d").strftime("%m/%d/%Y")
        except Exception:
            gd = game_date

        scoreboard = scoreboardv2.ScoreboardV2(game_date=gd)
        games = scoreboard.get_normalized_dict() or {}
        game_list = []
        
        for game in games.get('GameHeader', []):
            game_list.append({
                'game_id': game['GAME_ID'],
                'home_team': game['HOME_TEAM_ID'],
                'away_team': game['VISITOR_TEAM_ID'],
                'status': game.get('GAME_STATUS_TEXT', ''),
            })
        
        return game_list
    except Exception as e:
        print(f"[ERROR] Failed to get scoreboard: {e}")
        return []


def _espn_date_str(game_date: str) -> str:
    """Convert YYYY-MM-DD -> YYYYMMDD for ESPN endpoints."""
    return game_date.replace("-", "")


def get_espn_event_ids_for_date(game_date: str) -> List[str]:
    """Return ESPN event IDs for the given date.

    ESPN is used as a fallback when nba_api endpoints are unavailable.
    """
    if not HAS_REQUESTS:
        return []

    yyyymmdd = _espn_date_str(game_date)
    url = (
        "https://site.web.api.espn.com/apis/site/v2/sports/"
        f"basketball/nba/scoreboard?dates={yyyymmdd}"
    )
    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json() or {}
        events = data.get("events") or []

        event_ids: List[str] = []
        for ev in events:
            ev_id = str((ev or {}).get("id") or "").strip()
            if not ev_id:
                continue
            # Keep all events; downstream parsing can skip non-final games.
            event_ids.append(ev_id)
        return event_ids
    except Exception as e:
        print(f"[WARN] ESPN scoreboard unavailable for {game_date}: {e}")
        return []


def _coerce_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        txt = str(value).strip()
        if txt == "":
            return 0
        return int(float(txt))
    except Exception:
        return 0


def _parse_made_attempted(value: Any) -> int:
    """Parse strings like '3-8' and return made (3)."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    txt = str(value).strip()
    if "-" in txt:
        left = txt.split("-", 1)[0].strip()
        return _coerce_int(left)
    return _coerce_int(txt)


def get_box_scores_espn(game_date: str) -> Dict[str, Dict[str, Any]]:
    """Fetch ESPN box scores for a date and return player stats keyed by normalized name."""
    if not HAS_REQUESTS:
        return {}

    event_ids = get_espn_event_ids_for_date(game_date)
    if not event_ids:
        return {}

    all_players: Dict[str, Dict[str, Any]] = {}
    for ev_id in event_ids:
        url = (
            "https://site.web.api.espn.com/apis/site/v2/sports/"
            f"basketball/nba/summary?event={ev_id}"
        )
        try:
            time.sleep(0.25)
            resp = requests.get(url, timeout=12)
            resp.raise_for_status()
            data = resp.json() or {}

            # Only trust FINAL games.
            status = (((data.get("header") or {}).get("competitions") or [{}])[0].get("status") or {})
            state = ((status.get("type") or {}).get("state") or "").lower()
            if state != "post":
                continue

            boxscore = data.get("boxscore") or {}
            players_blocks = boxscore.get("players") or []

            for team_block in players_blocks:
                team = (team_block or {}).get("team") or {}
                team_abbr = (team.get("abbreviation") or "").strip()
                statistics_groups = (team_block or {}).get("statistics") or []

                for group in statistics_groups:
                    labels = (group or {}).get("labels") or []
                    athletes = (group or {}).get("athletes") or []
                    if not labels or not athletes:
                        continue

                    label_to_idx = {str(lbl).upper(): idx for idx, lbl in enumerate(labels)}

                    # ESPN commonly uses '3PT' for 3P made-attempted.
                    for a in athletes:
                        athlete = (a or {}).get("athlete") or {}
                        display = (athlete.get("displayName") or athlete.get("shortName") or "").strip()
                        name = normalize_player_name(display)
                        if not name:
                            continue

                        stats_list = (a or {}).get("stats") or []

                        def get_label(lbl: str) -> Any:
                            idx = label_to_idx.get(lbl)
                            if idx is None:
                                return None
                            if idx < 0 or idx >= len(stats_list):
                                return None
                            return stats_list[idx]

                        pts = _coerce_int(get_label("PTS"))
                        reb = _coerce_int(get_label("REB"))
                        ast = _coerce_int(get_label("AST"))
                        stl = _coerce_int(get_label("STL"))
                        blk = _coerce_int(get_label("BLK"))
                        tov = _coerce_int(get_label("TO"))
                        fg3m = _parse_made_attempted(get_label("3PT"))
                        mins = get_label("MIN")

                        all_players[name] = {
                            "PTS": pts,
                            "REB": reb,
                            "AST": ast,
                            "STL": stl,
                            "BLK": blk,
                            "TO": tov,
                            "FG3M": fg3m,
                            "MIN": mins or "0:00",
                            "TEAM": team_abbr,
                        }
        except Exception:
            # Best-effort fallback; keep processing other events.
            continue

    return all_players


def get_box_score(game_id: str) -> Dict[str, Dict]:
    """Fetch box score for a game, return player stats keyed by normalized name"""
    if not HAS_NBA_API:
        return {}
    
    try:
        # Light rate-limit. When nba_api is under stress, responses may be None.
        time.sleep(0.8)

        # --- Preferred: V3 endpoint ---
        player_stats: Dict[str, Dict[str, Any]] = {}
        try:
            box = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
            data = box.get_dict()
        except Exception:
            data = None

        if isinstance(data, dict):
            box_data = data.get('boxScoreTraditional') or {}
            home_players = (box_data.get('homeTeam') or {}).get('players') or []
            away_players = (box_data.get('awayTeam') or {}).get('players') or []

            for player in list(home_players) + list(away_players):
                name = normalize_player_name((player or {}).get('name', ''))
                if not name:
                    continue
                stats = (player or {}).get('statistics') or {}
                player_stats[name] = {
                    'PTS': stats.get('points', 0) or 0,
                    'REB': stats.get('reboundsTotal', 0) or 0,
                    'AST': stats.get('assists', 0) or 0,
                    'STL': stats.get('steals', 0) or 0,
                    'BLK': stats.get('blocks', 0) or 0,
                    'TO': stats.get('turnovers', 0) or 0,
                    'FG3M': stats.get('threePointersMade', 0) or 0,
                    'MIN': stats.get('minutes', '0:00'),
                    'TEAM': (player or {}).get('teamTricode', ''),
                }

        if player_stats:
            return player_stats

        # --- Fallback: V2 endpoint (often more resilient) ---
        try:
            time.sleep(0.4)
            box2 = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
            nd = box2.get_normalized_dict() or {}
            rows = nd.get('PlayerStats') or []

            for r in rows:
                # Normalized dict uses uppercase keys
                raw_name = (r.get('PLAYER_NAME') or r.get('PLAYER_NAME_LAST_FIRST') or '').strip()
                name = normalize_player_name(raw_name)
                if not name:
                    continue
                player_stats[name] = {
                    'PTS': r.get('PTS', 0) or 0,
                    'REB': r.get('REB', 0) or 0,
                    'AST': r.get('AST', 0) or 0,
                    'STL': r.get('STL', 0) or 0,
                    'BLK': r.get('BLK', 0) or 0,
                    'TO': r.get('TO', 0) or 0,
                    'FG3M': r.get('FG3M', 0) or 0,
                    'MIN': r.get('MIN', '0:00'),
                    'TEAM': r.get('TEAM_ABBREVIATION', ''),
                }

            return player_stats
        except Exception as e2:
            # Common when games haven't started / aren't final yet.
            print(f"[WARN] Box score not available for {game_id} (V3 empty, V2 failed): {e2}")
            return {}
    except Exception as e:
        print(f"[ERROR] Failed to get box score for {game_id}: {e}")
        return {}


def get_stat_value(player_stats: Dict, stat_key: str) -> Optional[float]:
    """Extract stat value from player stats dict"""
    # Normalize keys (analysis outputs are not always consistent)
    key = str(stat_key or "").strip().lower()
    key = key.replace(" ", "")
    mapping = STAT_MAP.get(key)
    
    if mapping is None:
        return None
    
    if isinstance(mapping, list):
        # Combo stat
        total = 0
        for col in mapping:
            val = player_stats.get(col, 0)
            if val is None:
                return None
            total += val
        return total
    else:
        return player_stats.get(mapping)


def check_hit(actual: float, line: float, direction: str) -> int:
    """Determine if prop hit (1) or missed (0)"""
    d = (direction or "").strip().lower()
    if d in {'higher', 'over', 'o'}:
        return 1 if actual > line else 0
    else:
        return 1 if actual < line else 0


def find_analysis_files(game_date: str) -> List[Path]:
    """Find all analysis JSON files for a given date"""
    pattern = f"*RISK_FIRST_{game_date.replace('-', '')}*.json"
    files = list(OUTPUTS_DIR.glob(pattern))
    
    # Also check for FROM_UD pattern
    pattern2 = f"*{game_date.replace('-', '')}*FROM_UD.json"
    files.extend(OUTPUTS_DIR.glob(pattern2))
    
    # Dedupe
    return list(set(files))


def _extract_yyyymmdd_from_name(name: str) -> Optional[str]:
    m = re.search(r"(20\d{6})", name)
    if not m:
        return None
    return m.group(1)


def list_available_analysis_dates(limit: int = 15) -> List[str]:
    """Return available analysis dates as YYYY-MM-DD, newest first."""
    candidates: List[Path] = []
    candidates.extend(OUTPUTS_DIR.glob("*RISK_FIRST_*FROM_UD.json"))
    candidates.extend(OUTPUTS_DIR.glob("*RISK_FIRST_*.json"))

    yyyymmdd: List[str] = []
    for p in candidates:
        d = _extract_yyyymmdd_from_name(p.name)
        if d:
            yyyymmdd.append(d)

    uniq = sorted(set(yyyymmdd), reverse=True)
    out: List[str] = []
    for d in uniq[: max(1, limit)]:
        try:
            out.append(datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d"))
        except Exception:
            continue
    return out


def pick_fallback_date(requested_date: str) -> Optional[str]:
    """If no files exist for requested_date, try a sensible fallback (yesterday or latest available)."""
    # First try yesterday (common midnight crossover issue)
    try:
        req = datetime.strptime(requested_date, "%Y-%m-%d").date()
        yday = (req - timedelta(days=1)).strftime("%Y-%m-%d")
        if find_analysis_files(yday):
            return yday
    except Exception:
        pass

    avail = list_available_analysis_dates(limit=1)
    return avail[0] if avail else None


def load_picks_from_json(json_path: Path) -> List[Dict]:
    """Load playable picks from analysis JSON"""
    data = json.loads(json_path.read_text(encoding='utf-8'))
    results = data.get('results', [])
    
    picks = []
    for r in results:
        decision = r.get('decision', r.get('status', ''))
        if decision in ['PLAY', 'LEAN']:
            picks.append({
                'player': r['player'],
                'team': r.get('team', ''),
                'stat': r['stat'],
                'line': r['line'],
                'direction': r['direction'],
                'predicted_prob': r.get('effective_confidence', 0) / 100.0,
                'decision': decision,
            })
    
    return picks


def resolve_picks(picks: List[Dict], box_scores: Dict[str, Dict], game_date: str) -> List[Dict]:
    """Match picks against box scores and determine hits/misses"""
    resolved = []
    
    for pick in picks:
        player_norm = normalize_player_name(pick['player'])
        player_stats = box_scores.get(player_norm)
        
        if player_stats is None:
            print(f"  [SKIP] {pick['player']} - not found in box scores")
            continue
        
        actual = get_stat_value(player_stats, pick['stat'])
        
        if actual is None:
            print(f"  [SKIP] {pick['player']} {pick['stat']} - stat not mapped")
            continue
        
        hit = check_hit(actual, pick['line'], pick['direction'])
        
        resolved.append({
            'date': game_date,
            'player': pick['player'],
            'team': pick['team'],
            'stat': pick['stat'],
            'line': pick['line'],
            'direction': pick['direction'],
            'predicted_prob': pick['predicted_prob'],
            'actual_result': actual,
            'hit': hit,
            'decision': pick['decision'],
        })
        
        status = "HIT" if hit else "MISS"
        print(f"  {status}: {pick['player']} {pick['stat']} {pick['direction']} {pick['line']} -> actual: {actual}")
    
    return resolved


def append_to_calibration(resolved: List[Dict], dry_run: bool = False):
    """Append resolved picks to calibration_history.csv"""
    if not resolved:
        print("\n[INFO] No picks to append")
        return
    
    file_exists = CALIBRATION_FILE.exists()
    
    if dry_run:
        print(f"\n[DRY RUN] Would append {len(resolved)} picks to {CALIBRATION_FILE}")
        return

    # Read existing header if file exists to ensure consistency
    # calibration_history.csv in this repo uses:
    # pick_id,game_date,player,team,opponent,stat,line,direction,probability,tier,
    # actual_value,outcome,added_utc,league,source
    default_fieldnames = [
        'pick_id', 'game_date', 'player', 'team', 'opponent', 'stat', 'line',
        'direction', 'probability', 'tier', 'actual_value', 'outcome',
        'added_utc', 'league', 'source'
    ]
    fieldnames = default_fieldnames

    if file_exists:
        with open(CALIBRATION_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            existing_header = next(reader, None)
            if existing_header:
                fieldnames = existing_header

    # Safety: backup existing calibration history before mutating
    if file_exists:
        try:
            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            backup_path = CALIBRATION_FILE.with_name(f"calibration_history.backup_{ts}.csv")
            backup_path.write_text(CALIBRATION_FILE.read_text(encoding='utf-8'), encoding='utf-8')
            print(f"[INFO] Backup created: {backup_path}")
        except Exception as e:
            print(f"[WARN] Failed to create calibration backup: {e}")

    def to_calibration_row(row: Dict[str, Any]) -> Dict[str, Any]:
        # Normalize direction and outcome
        d = (row.get('direction') or '').strip().lower()
        if d in {'over', 'o'}:
            d = 'higher'
        elif d in {'under', 'u'}:
            d = 'lower'
        hit = row.get('hit')
        if hit is None:
            # try compute from row fields if not present
            try:
                hit = check_hit(float(row.get('actual_result')), float(row.get('line')), d)
            except Exception:
                hit = None

        predicted_prob = row.get('predicted_prob')
        prob_pct = None
        if predicted_prob is not None:
            try:
                prob_pct = float(predicted_prob) * 100.0
            except Exception:
                prob_pct = None

        actual_val = row.get('actual_result')
        if actual_val is None:
            actual_val = row.get('actual_value')

        outcome = None
        if hit == 1:
            outcome = 'hit'
        elif hit == 0:
            outcome = 'miss'

        added_utc = datetime.now(timezone.utc).isoformat()

        cal = {
            'pick_id': row.get('pick_id') or '',
            'game_date': row.get('date') or row.get('game_date') or '',
            'player': row.get('player') or '',
            'team': row.get('team') or '',
            'opponent': row.get('opponent') or '',
            'stat': row.get('stat') or '',
            'line': row.get('line') if row.get('line') is not None else '',
            'direction': d,
            'probability': '' if prob_pct is None else round(prob_pct, 2),
            'tier': row.get('tier') or row.get('decision') or '',
            'actual_value': '' if actual_val is None else actual_val,
            'outcome': outcome or '',
            'added_utc': added_utc,
            'league': row.get('league') or 'nba',
            'source': row.get('source') or 'resolve_picks',
        }

        # Return only keys that exist in the file header
        return {k: cal.get(k, '') for k in fieldnames}
    
    with open(CALIBRATION_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        
        if not file_exists:
            writer.writeheader()
        
        for row in resolved:
            writer.writerow(to_calibration_row(row))
    
    print(f"\n[SUCCESS] Appended {len(resolved)} picks to {CALIBRATION_FILE}")


def manual_entry_mode(picks: List[Dict], game_date: str):
    """Interactive mode for manual entry when nba_api unavailable"""
    print("\n" + "="*60)
    print("MANUAL ENTRY MODE")
    print("Enter actual stat values for each pick (or 'skip' to skip)")
    print("="*60)
    
    resolved = []
    
    for pick in picks:
        print(f"\n{pick['player']} - {pick['stat']} {pick['direction']} {pick['line']}")
        print(f"  Predicted: {pick['predicted_prob']*100:.1f}%")
        
        while True:
            val = input("  Actual value (or 'skip'): ").strip()
            
            if val.lower() == 'skip':
                break
            
            try:
                actual = float(val)
                hit = check_hit(actual, pick['line'], pick['direction'])
                status = "HIT" if hit else "MISS"
                print(f"  {status}")
                
                resolved.append({
                    'date': game_date,
                    'player': pick['player'],
                    'team': pick['team'],
                    'stat': pick['stat'],
                    'line': pick['line'],
                    'direction': pick['direction'],
                    'predicted_prob': pick['predicted_prob'],
                    'actual_result': actual,
                    'hit': hit,
                    'decision': pick['decision'],
                })
                break
            except ValueError:
                print("  Invalid input - enter a number or 'skip'")
    
    return resolved


def main():
    parser = argparse.ArgumentParser(description="Resolve picks against box scores")
    parser.add_argument('--date', type=str, help="Game date (YYYY-MM-DD)")
    parser.add_argument('--file', type=str, help="Specific analysis JSON file")
    parser.add_argument('--dry-run', action='store_true', help="Preview without saving")
    parser.add_argument('--manual', action='store_true', help="Force manual entry mode")
    args = parser.parse_args()
    
    # Determine date
    if args.date:
        game_date = args.date
    else:
        game_date = date.today().strftime('%Y-%m-%d')
    
    print("="*60)
    print(f"RESOLVE PICKS - {game_date}")
    print("="*60)
    
    # Find analysis files
    if args.file:
        json_files = [Path(args.file)]
    else:
        json_files = find_analysis_files(game_date)

    if not json_files:
        # Common issue: it's just after midnight; analysis files are under yesterday.
        fallback = pick_fallback_date(game_date)
        if fallback and fallback != game_date:
            print(f"[WARN] No analysis files found for {game_date}. Using nearest available date: {fallback}")
            game_date = fallback
            json_files = find_analysis_files(game_date)

    if not json_files:
        print(f"[ERROR] No analysis files found for {game_date}")
        print(f"  Looking in: {OUTPUTS_DIR}")
        avail = list_available_analysis_dates(limit=10)
        if avail:
            print("\nAvailable analysis dates:")
            for d in avail:
                print(f"  - {d}")
            print("\nTip: re-run with --date YYYY-MM-DD (one of the dates above) or --file <analysis.json>")
        return
    
    print(f"\nFound {len(json_files)} analysis file(s):")
    for f in json_files:
        print(f"  - {f.name}")
    
    # Load all picks
    all_picks = []
    for json_file in json_files:
        picks = load_picks_from_json(json_file)
        print(f"\n{json_file.name}: {len(picks)} playable picks")
        all_picks.extend(picks)
    
    if not all_picks:
        print("\n[INFO] No PLAY/LEAN picks to resolve")
        return
    
    # Dedupe picks (same player/stat/line)
    seen = set()
    unique_picks = []
    for p in all_picks:
        key = (p['player'], p['stat'], p['line'], p['direction'])
        if key not in seen:
            seen.add(key)
            unique_picks.append(p)
    
    print(f"\nTotal unique picks to resolve: {len(unique_picks)}")
    
    # Resolve
    if args.manual or not HAS_NBA_API:
        resolved = manual_entry_mode(unique_picks, game_date)
    else:
        print("\nFetching box scores...")
        
        # Get game IDs for date
        games = get_game_ids_for_date(game_date)
        
        if not games:
            print("[WARN] No games found - switching to manual mode")
            resolved = manual_entry_mode(unique_picks, game_date)
        else:
            print(f"Found {len(games)} games")

            # If games aren't final yet, don't pretend we can resolve.
            final_games = [g for g in games if "FINAL" in str(g.get("status", "")).upper()]
            if not final_games:
                print("\n[INFO] No FINAL games yet for this date. Nothing to resolve.")
                print("       Re-run after games complete (or use --manual if you truly have final stats).")
                resolved = []
            else:
                # Fetch all box scores (nba_api first)
                all_box_scores: Dict[str, Dict[str, Any]] = {}
                for game in final_games:
                    print(f"  Fetching game {game['game_id']}... ({game.get('status','')})")
                    box = get_box_score(game['game_id'])
                    if box:
                        all_box_scores.update(box)

                # If nba_api fails (common during 2025-26 season due to endpoint blocks),
                # fall back to ESPN official JSON endpoints.
                if not all_box_scores:
                    print("\n[WARN] nba_api returned 0 players - falling back to ESPN official box scores...")
                    espn_scores = get_box_scores_espn(game_date)
                    if espn_scores:
                        all_box_scores.update(espn_scores)
                    else:
                        # Helpful hint for the most common root cause.
                        try:
                            ev_ids = get_espn_event_ids_for_date(game_date)
                            if ev_ids:
                                print(f"[INFO] ESPN events found for {game_date}: {len(ev_ids)} (but none FINAL/post yet)")
                        except Exception:
                            pass

                print(f"\nLoaded stats for {len(all_box_scores)} players")
                print("\nResolving picks:")

                resolved = resolve_picks(unique_picks, all_box_scores, game_date)
    
    # Summary
    if resolved:
        hits = sum(1 for r in resolved if r['hit'] == 1)
        total = len(resolved)
        print(f"\n{'='*60}")
        print(f"RESOLUTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total resolved: {total}")
        print(f"Hits: {hits} ({hits/total*100:.1f}%)")
        print(f"Misses: {total - hits} ({(total-hits)/total*100:.1f}%)")
        
        # By decision tier
        for tier in ['PLAY', 'LEAN']:
            tier_picks = [r for r in resolved if r['decision'] == tier]
            if tier_picks:
                tier_hits = sum(1 for r in tier_picks if r['hit'] == 1)
                print(f"\n{tier}: {tier_hits}/{len(tier_picks)} ({tier_hits/len(tier_picks)*100:.1f}%)")
    
    # Save
    append_to_calibration(resolved, args.dry_run)
    
    if not args.dry_run and resolved:
        print(f"\nCalibration history updated! Total records: ", end='')
        if CALIBRATION_FILE.exists():
            with open(CALIBRATION_FILE) as f:
                lines = sum(1 for _ in f) - 1  # Exclude header
            print(f"{lines}")


if __name__ == "__main__":
    main()
