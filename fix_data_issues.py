"""
FUOOM DATA QUALITY FIX SCRIPT
Fixes the 4 critical issues identified:
1. Hit rate display (8000% → 80%)
2. Duncan Robinson team mapping
3. Cam Thomas suspicious data
4. UNK opponents

Usage:
    python fix_data_issues.py YOURFILE.json
"""

import json
from pathlib import Path
import sys

# Known player-team mappings (2025-26 season)
PLAYER_TEAM_MAP = {
    'Duncan Robinson': 'MIA',
    'Cam Thomas': 'BKN',
    'Stephen Curry': 'GSW',
    'Nic Claxton': 'BKN',
    'Kyle Filipowski': 'UTA',
    'Terance Mann': 'LAC',  # Not BKN!
    'Egor Demin': 'BKN',
    'Egor Dëmin': 'BKN',
    'Danny Wolf': 'LAC',
}

def fix_hit_rate_display(value):
    """Fix hit rate from 8000% to 80%"""
    if value > 100:
        return value / 100
    return value

def fix_team_mapping(pick):
    """Fix player team assignment"""
    player = pick.get('player', pick.get('entity', ''))
    current_team = pick.get('team', '')
    
    # Check if player has known team
    correct_team = PLAYER_TEAM_MAP.get(player)
    
    if correct_team and correct_team != current_team:
        print(f"⚠️  FIXING: {player} team {current_team} → {correct_team}")
        pick['team'] = correct_team
        
        # If opponent was None/UNK, try to infer it
        if pick.get('opponent') in ['UNK', None, '']:
            # The old 'team' might actually be the opponent
            if current_team and current_team != 'UNK':
                pick['opponent'] = current_team
                print(f"   → Inferred opponent: {current_team}")
    
    return pick

def validate_projection(pick):
    """Flag suspicious projections"""
    player = pick.get('player', pick.get('entity', ''))
    stat = pick.get('stat', pick.get('market', '')).lower()
    mu = pick.get('mu', 0)
    
    warnings = []
    
    # Known player baselines (approximate season averages)
    expected_ranges = {
        ('Cam Thomas', 'points'): (20, 28),      # ~24 PPG
        ('Stephen Curry', 'points'): (22, 30),   # ~26 PPG
        ('Duncan Robinson', '3pm'): (2, 4),      # ~3 3PM
        ('Nic Claxton', 'points'): (8, 14),      # ~11 PPG
    }
    
    key = (player, stat)
    if key in expected_ranges:
        min_val, max_val = expected_ranges[key]
        if not (min_val <= mu <= max_val):
            warnings.append({
                'player': player,
                'stat': stat,
                'mu': mu,
                'expected_range': f"{min_val}-{max_val}",
                'severity': 'CRITICAL' if mu < min_val * 0.5 else 'WARNING'
            })
    
    return warnings

def fix_special_characters(pick):
    """Fix special characters that might cause issues"""
    player = pick.get('player', pick.get('entity', ''))
    
    # Replace special chars
    fixed_player = player.replace('ë', 'e')  # Egor Dëmin → Egor Demin
    
    if fixed_player != player:
        print(f"⚠️  FIXING special char: {player} → {fixed_player}")
        if 'player' in pick:
            pick['player'] = fixed_player
        if 'entity' in pick:
            pick['entity'] = fixed_player
    
    return pick

def analyze_and_fix(json_file, output_file=None):
    """Main function to analyze and fix data issues"""
    
    print("=" * 80)
    print("🔧 FUOOM DATA QUALITY FIX")
    print("=" * 80)
    print(f"Input: {json_file}")
    print()
    
    # Load data
    with open(json_file, encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        picks = data.get('results', data.get('picks', data.get('entries', [])))
    else:
        picks = data
    
    print(f"📊 Loaded {len(picks)} picks")
    print()
    
    # Track fixes
    fixes_applied = {
        'team_fixes': 0,
        'hit_rate_fixes': 0,
        'char_fixes': 0
    }
    
    all_warnings = []
    
    # Process each pick
    for pick in picks:
        # Fix 1: Team mapping
        original_team = pick.get('team')
        pick = fix_team_mapping(pick)
        if pick.get('team') != original_team:
            fixes_applied['team_fixes'] += 1
        
        # Fix 2: Hit rate display
        for key in ['historical_hit_rate', 'hit_rate']:
            if key in pick:
                original = pick[key]
                if isinstance(original, (int, float)) and original > 100:
                    fixed = fix_hit_rate_display(original)
                    pick[key] = fixed
                    fixes_applied['hit_rate_fixes'] += 1
        
        # Fix 3: Special characters
        original_player = pick.get('player', pick.get('entity'))
        pick = fix_special_characters(pick)
        if pick.get('player', pick.get('entity')) != original_player:
            fixes_applied['char_fixes'] += 1
        
        # Validate projection
        warnings = validate_projection(pick)
        all_warnings.extend(warnings)
    
    # Report findings
    print("=" * 80)
    print("📊 FIXES APPLIED:")
    print("=" * 80)
    print(f"Team mappings fixed:      {fixes_applied['team_fixes']}")
    print(f"Hit rates fixed:          {fixes_applied['hit_rate_fixes']}")
    print(f"Special chars fixed:      {fixes_applied['char_fixes']}")
    print()
    
    if all_warnings:
        print("=" * 80)
        print("🚨 SUSPICIOUS PROJECTIONS DETECTED:")
        print("=" * 80)
        for w in all_warnings:
            severity = w['severity']
            emoji = "🔴" if severity == "CRITICAL" else "🟡"
            print(f"{emoji} {w['player']} - {w['stat']}")
            print(f"   Current μ: {w['mu']}")
            print(f"   Expected:  {w['expected_range']}")
            print(f"   Severity:  {severity}")
            print()
        
        print("⚠️  ACTION REQUIRED:")
        print("   These projections are outside normal ranges.")
        print("   Check your data source and cache files.")
        print()
    
    # Save fixed data
    if output_file is None:
        output_file = json_file.replace('.json', '_FIXED.json')
    
    if isinstance(data, dict):
        if 'results' in data:
            data['results'] = picks
        elif 'picks' in data:
            data['picks'] = picks
        output_data = data
    else:
        output_data = picks
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✅ Fixed data saved to: {output_file}")
    print()
    
    return all_warnings

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        import glob
        files = glob.glob("outputs/*RISK_FIRST*.json")
        if files:
            json_file = sorted(files, key=lambda x: Path(x).stat().st_mtime)[-1]
            print(f"Using most recent: {json_file}")
            print()
        else:
            print("Usage: python fix_data_issues.py YOUR_FILE.json")
            sys.exit(1)
    
    warnings = analyze_and_fix(json_file)
    
    if warnings:
        print("=" * 80)
        print("⚠️  CRITICAL WARNINGS FOUND - REVIEW BEFORE BETTING")
        print("=" * 80)
