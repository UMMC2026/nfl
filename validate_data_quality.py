"""
PRE-REPORT DATA QUALITY VALIDATOR
Run BEFORE generating AI reports to catch data issues.

Usage:
    python validate_data_quality.py outputs/YOUR_RISK_FIRST.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Known player-team mappings (2025-26 season)
PLAYER_TEAM_MAP = {
    'Duncan Robinson': 'MIA',
    'Cam Thomas': 'BKN',
    'Stephen Curry': 'GSW',
    'Nic Claxton': 'BKN',
    'Kyle Filipowski': 'UTA',
    'Terance Mann': 'LAC',
    'Egor Demin': 'BKN',
    'Danny Wolf': 'LAC',
    'Al Horford': 'BOS',
    'Jalen Duren': 'DET',
}

# Expected projection ranges by player/stat
EXPECTED_RANGES = {
    ('Cam Thomas', 'points'): (20, 28),
    ('Stephen Curry', 'points'): (22, 30),
    ('Nic Claxton', 'points'): (8, 14),
    ('Kyle Filipowski', 'points'): (8, 14),
    ('Duncan Robinson', '3pm'): (2, 4),
}

def validate_pick(pick: Dict) -> List[str]:
    """Validate a single pick and return list of warnings."""
    warnings = []
    
    player = pick.get('player', pick.get('entity', 'Unknown'))
    team = pick.get('team', '')
    opponent = pick.get('opponent', '')
    stat = pick.get('stat', pick.get('market', '')).lower()
    mu = pick.get('mu', 0)
    sample_n = pick.get('sample_n', 0)
    prob_details = pick.get('prob_method_details', {})
    emp_rate = prob_details.get('empirical_hit_rate')
    
    # 1. Check team mapping
    correct_team = PLAYER_TEAM_MAP.get(player)
    if correct_team and team != correct_team:
        warnings.append(f"⚠️  TEAM MISMATCH: {player} shows '{team}' but plays for '{correct_team}'")
    
    # 2. Check for UNK opponent
    if opponent in ['UNK', '', None]:
        warnings.append(f"⚠️  MISSING OPPONENT: {player} has no opponent data")
    
    # 3. Check empirical hit rate range
    if emp_rate is not None:
        if emp_rate > 100:
            warnings.append(f"🔴 HIT RATE BUG: {player} shows {emp_rate}% (should be <100)")
        elif emp_rate < 0:
            warnings.append(f"🔴 HIT RATE BUG: {player} shows negative {emp_rate}%")
    
    # 4. Check projection against expected range
    key = (player, stat)
    if key in EXPECTED_RANGES:
        min_val, max_val = EXPECTED_RANGES[key]
        if mu < min_val * 0.5:
            warnings.append(f"🔴 SUSPICIOUS PROJECTION: {player} {stat} μ={mu:.1f} (expected {min_val}-{max_val})")
        elif not (min_val * 0.7 <= mu <= max_val * 1.3):
            warnings.append(f"🟡 PROJECTION OUTSIDE RANGE: {player} {stat} μ={mu:.1f} (expected {min_val}-{max_val})")
    
    # 5. Check sample size
    if sample_n == 0 and emp_rate is not None:
        warnings.append(f"⚠️  DATA INCONSISTENCY: {player} has emp_rate={emp_rate} but sample_n=0")
    
    # 6. Check for special characters in player name
    if any(ord(c) > 127 for c in player):
        warnings.append(f"⚠️  SPECIAL CHARACTERS: {player} contains non-ASCII characters")
    
    return warnings


def validate_json(json_path: str) -> Tuple[int, int, List[str]]:
    """Validate entire JSON file and return (total_picks, picks_with_issues, all_warnings)."""
    
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        picks = data.get('results', data.get('picks', data.get('entries', [])))
    else:
        picks = data
    
    all_warnings = []
    picks_with_issues = 0
    
    for pick in picks:
        warnings = validate_pick(pick)
        if warnings:
            picks_with_issues += 1
            all_warnings.extend(warnings)
    
    return len(picks), picks_with_issues, all_warnings


def main():
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # Auto-find latest RISK_FIRST JSON
        import glob
        files = glob.glob("outputs/*RISK_FIRST*.json")
        if not files:
            print("Usage: python validate_data_quality.py YOUR_FILE.json")
            sys.exit(1)
        json_file = sorted(files, key=lambda x: Path(x).stat().st_mtime)[-1]
        print(f"Using most recent: {json_file}\n")
    
    print("=" * 80)
    print("🔍 PRE-REPORT DATA QUALITY CHECK")
    print("=" * 80)
    
    total, with_issues, warnings = validate_json(json_file)
    
    if not warnings:
        print(f"\n✅ ALL {total} PICKS PASSED VALIDATION\n")
        print("Safe to generate AI report.")
    else:
        print(f"\n⚠️  FOUND {len(warnings)} ISSUES IN {with_issues}/{total} PICKS\n")
        
        # Group warnings by type
        critical = [w for w in warnings if '🔴' in w]
        moderate = [w for w in warnings if '🟡' in w]
        minor = [w for w in warnings if '⚠️' in w]
        
        if critical:
            print("🔴 CRITICAL ISSUES (may affect betting decisions):")
            for w in critical:
                print(f"   {w}")
            print()
        
        if moderate:
            print("🟡 MODERATE ISSUES (review before betting):")
            for w in moderate:
                print(f"   {w}")
            print()
        
        if minor:
            print("⚠️  MINOR ISSUES (informational):")
            for w in minor[:10]:  # Limit to first 10
                print(f"   {w}")
            if len(minor) > 10:
                print(f"   ... and {len(minor) - 10} more")
            print()
        
        if critical:
            print("❌ CRITICAL ISSUES FOUND - Review data before proceeding")
        else:
            print("⚠️  Some issues found - Consider reviewing before betting")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
