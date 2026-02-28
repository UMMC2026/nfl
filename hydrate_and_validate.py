"""
DATA HYDRATION & VALIDATION
Fetches real NBA API data to validate/override suspicious projections.

Usage:
    python hydrate_and_validate.py outputs/YOUR_RISK_FIRST.json
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# Expected ranges by player (approximate 2024-25 season averages)
VALIDATION_THRESHOLDS = {
    # player_name: {stat: (min_reasonable, max_reasonable)}
    'Cam Thomas': {'points': (18, 30), 'assists': (2, 6), '3pm': (0, 3)},
    'Stephen Curry': {'points': (20, 32), 'assists': (4, 8), '3pm': (3, 6)},
    'Duncan Robinson': {'points': (6, 15), '3pm': (1, 4)},
    'Nic Claxton': {'points': (8, 16), 'rebounds': (6, 12)},
}

def fetch_player_recent_stats(player_name: str, stat: str, n_games: int = 10) -> Optional[List[float]]:
    """Fetch recent game values from NBA API."""
    try:
        from nba_api.stats.static import players
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        return None
    
    STAT_MAP = {
        'points': 'PTS', 'pts': 'PTS',
        'rebounds': 'REB', 'reb': 'REB',
        'assists': 'AST', 'ast': 'AST',
        '3pm': 'FG3M', 'threes': 'FG3M',
        'steals': 'STL', 'stl': 'STL',
        'blocks': 'BLK', 'blk': 'BLK',
        'turnovers': 'TOV', 'tov': 'TOV',
    }
    
    col = STAT_MAP.get(stat.lower())
    if not col:
        return None
    
    # Find player
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        all_players = players.get_players()
        name_lower = player_name.lower()
        matches = [p for p in all_players if name_lower in p["full_name"].lower()]
    
    if not matches:
        return None
    
    pid = matches[0]["id"]
    
    try:
        time.sleep(0.6)  # Rate limit
        gl = playergamelog.PlayerGameLog(player_id=pid, season='2024-25', timeout=30)
        df = gl.get_data_frames()[0]
        
        if df.empty or col not in df.columns:
            return None
        
        return df[col].head(n_games).astype(float).tolist()
    except Exception:
        return None


def validate_and_fix_pick(pick: Dict) -> Tuple[Dict, List[str]]:
    """Validate a pick's projection against real data. Returns (fixed_pick, warnings)."""
    warnings = []
    player = pick.get('player', pick.get('entity', ''))
    stat = pick.get('stat', pick.get('market', '')).lower()
    mu = pick.get('mu', 0)
    series = pick.get('series', [])
    
    # Check if player has validation thresholds
    if player in VALIDATION_THRESHOLDS:
        thresholds = VALIDATION_THRESHOLDS[player]
        if stat in thresholds:
            min_val, max_val = thresholds[stat]
            
            if mu < min_val * 0.6:
                # Projection is suspiciously low - try to fetch real data
                warnings.append(f"🔴 {player} {stat} μ={mu:.1f} is VERY LOW (expected {min_val}-{max_val})")
                
                # Fetch real data
                real_data = fetch_player_recent_stats(player, stat)
                if real_data:
                    real_avg = sum(real_data) / len(real_data)
                    warnings.append(f"   → NBA API shows avg={real_avg:.1f} over {len(real_data)} games")
                    
                    # Update pick with real data
                    pick['mu_original'] = mu
                    pick['mu'] = real_avg
                    pick['mu_raw'] = real_avg
                    pick['series'] = real_data
                    pick['sample_n'] = len(real_data)
                    pick['data_override'] = True
                    pick['override_source'] = 'NBA_API'
                    warnings.append(f"   → FIXED: μ updated to {real_avg:.1f}")
            
            elif mu > max_val * 1.5:
                warnings.append(f"🟡 {player} {stat} μ={mu:.1f} is HIGH (expected {min_val}-{max_val})")
    
    # Check for empty series with sample_n > 0 (data inconsistency)
    sample_n = pick.get('sample_n', 0)
    if sample_n > 0 and not series:
        warnings.append(f"⚠️  {player} has sample_n={sample_n} but empty series - data may be stale")
        
        # Try to fetch real data
        real_data = fetch_player_recent_stats(player, stat)
        if real_data:
            pick['series'] = real_data
            pick['sample_n'] = len(real_data)
            warnings.append(f"   → Fetched {len(real_data)} games from NBA API")
    
    return pick, warnings


def hydrate_json(json_path: str, output_path: Optional[str] = None) -> Tuple[int, int, List[str]]:
    """Validate and hydrate all picks in a JSON file."""
    
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        picks = data.get('results', data.get('picks', []))
    else:
        picks = data
    
    all_warnings = []
    fixed_count = 0
    
    print(f"Validating {len(picks)} picks...")
    
    for i, pick in enumerate(picks):
        pick, warnings = validate_and_fix_pick(pick)
        if warnings:
            all_warnings.extend(warnings)
            if any('FIXED' in w for w in warnings):
                fixed_count += 1
    
    # Save hydrated data
    if output_path is None:
        output_path = json_path.replace('.json', '_HYDRATED.json')
    
    if isinstance(data, dict):
        if 'results' in data:
            data['results'] = picks
        elif 'picks' in data:
            data['picks'] = picks
    else:
        data = picks
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    return len(picks), fixed_count, all_warnings


def main():
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        import glob
        files = glob.glob("outputs/*RISK_FIRST*.json")
        if not files:
            print("Usage: python hydrate_and_validate.py YOUR_FILE.json")
            sys.exit(1)
        json_file = sorted(files, key=lambda x: Path(x).stat().st_mtime)[-1]
        print(f"Using most recent: {json_file}\n")
    
    print("=" * 80)
    print("🔄 DATA HYDRATION & VALIDATION")
    print("=" * 80)
    
    total, fixed, warnings = hydrate_json(json_file)
    
    print(f"\n📊 Results: {total} picks processed, {fixed} fixed with NBA API data")
    
    if warnings:
        print("\n⚠️  Warnings:")
        for w in warnings:
            print(f"   {w}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
