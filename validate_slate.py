"""
FUOOM MASTER VALIDATION GATE
One script to catch ALL known data quality issues automatically

Usage:
    python validate_slate.py outputs/YOURFILE.json
    
This runs BEFORE report generation and blocks bad data from proceeding.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════
# KNOWN GOOD DATA (2025-26 Season)
# ═══════════════════════════════════════════════════════════════════

PLAYER_TEAMS = {
    'Stephen Curry': 'GSW',
    'Cam Thomas': 'BKN',
    'Duncan Robinson': 'MIA',
    'Nic Claxton': 'BKN',
    'Kyle Filipowski': 'UTA',
    'Terance Mann': 'LAC',
    'Egor Dëmin': 'BKN',
    'Danny Wolf': 'DET',
    "De'Anthony Melton": 'GSW',
    'Al Horford': 'BOS',
    'Cade Cunningham': 'DET',
    'Jalen Duren': 'DET',
    'Buddy Hield': 'GSW',
    'Draymond Green': 'GSW',
    'Brandin Podziemski': 'GSW',
    'Moses Moody': 'GSW',
    'Tobias Harris': 'DET',
    'Ausar Thompson': 'DET',
    'Isaiah Stewart': 'DET',
    'Keyonte George': 'UTA',
    'Brice Sensabaugh': 'UTA',
    'Isaiah Collier': 'UTA',
    'Cody Williams': 'UTA',
    "Day'Ron Sharpe": 'BKN',
    'Jalen Wilson': 'BKN',
    'Kyle Anderson': 'MIN',
    'Quinten Post': 'GSW',
    'Gui Santos': 'GSW',
    'Svi Mykhailiuk': 'CHA',
    'Drake Powell': 'CHA',
    'Javonte Green': 'CHA',
    'Daniss Jenkins': 'DEN',
    # Add more as you encounter them
}

# Reasonable projection ranges for key players
SANITY_RANGES = {
    ('Cam Thomas', 'points'): (18, 30),
    ('Stephen Curry', 'points'): (20, 32),
    ('Duncan Robinson', '3pm'): (1.5, 4.5),
    ('Nic Claxton', 'points'): (8, 16),
    ('Cade Cunningham', 'points'): (18, 28),
    ('Terance Mann', 'points'): (6, 14),
    ('Cade Cunningham', 'assists'): (6, 12),
    ('Buddy Hield', 'points'): (12, 22),
    ('Buddy Hield', '3pm'): (2, 5),
    ('Draymond Green', 'rebounds'): (5, 10),
    ('Jalen Duren', 'rebounds'): (8, 14),
    ('Tobias Harris', 'points'): (10, 18),
    # Add more as needed
}

# ═══════════════════════════════════════════════════════════════════
# VALIDATION RULES
# ═══════════════════════════════════════════════════════════════════

class ValidationError:
    def __init__(self, severity, category, message, pick=None):
        self.severity = severity  # CRITICAL, ERROR, WARNING
        self.category = category  # TEAM_MAPPING, PROJECTION, DISPLAY, DATA_QUALITY
        self.message = message
        self.pick = pick

class SlateValidator:
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.fixes_applied = 0
        
    def validate_all(self, picks):
        """Run all validation checks"""
        
        print("🔍 Running validation checks...")
        print()
        
        for pick in picks:
            self.validate_team_mapping(pick)
            self.validate_projection_sanity(pick)
            self.validate_display_values(pick)
            self.validate_opponent_data(pick)
            self.validate_sample_size(pick)
            self.validate_special_characters(pick)
        
        self.check_for_duplicates(picks)
        
        return self.errors, self.warnings
    
    def validate_team_mapping(self, pick):
        """Check player is assigned to correct team"""
        
        player = pick.get('player', '')
        current_team = pick.get('team', '')
        
        if player in PLAYER_TEAMS:
            correct_team = PLAYER_TEAMS[player]
            
            if current_team != correct_team:
                self.errors.append(ValidationError(
                    'CRITICAL',
                    'TEAM_MAPPING',
                    f"{player}: Wrong team '{current_team}' (should be '{correct_team}')",
                    pick
                ))
                
                # Auto-fix
                pick['team'] = correct_team
                self.fixes_applied += 1
                
                # If opponent is UNK, the old team might be the opponent
                if pick.get('opponent') in ['UNK', '', None]:
                    if current_team and current_team != 'UNK':
                        pick['opponent'] = current_team
                        self.fixes_applied += 1
    
    def validate_projection_sanity(self, pick):
        """Check projection is within reasonable range"""
        
        player = pick.get('player', '')
        stat = pick.get('stat', '')
        mu = pick.get('mu', 0)
        
        key = (player, stat)
        
        if key in SANITY_RANGES:
            min_val, max_val = SANITY_RANGES[key]
            
            if not (min_val <= mu <= max_val):
                severity = 'CRITICAL' if mu < min_val * 0.6 else 'ERROR'
                
                self.errors.append(ValidationError(
                    severity,
                    'PROJECTION',
                    f"{player} {stat}: μ={mu:.1f} outside range {min_val}-{max_val}",
                    pick
                ))
        
        # Generic sanity checks
        if stat == 'points' and mu < 3:
            self.warnings.append(ValidationError(
                'WARNING',
                'PROJECTION',
                f"{player} points: μ={mu:.1f} seems very low",
                pick
            ))
        
        if stat == '3pm' and mu > 8:
            self.warnings.append(ValidationError(
                'WARNING',
                'PROJECTION',
                f"{player} 3pm: μ={mu:.1f} seems very high",
                pick
            ))
    
    def validate_display_values(self, pick):
        """Check display values are formatted correctly"""
        
        # Fix hit rate display bug (8000% → 80%)
        if 'historical_hit_rate' in pick:
            rate = pick['historical_hit_rate']
            if rate > 100:
                pick['historical_hit_rate'] = rate / 100
                self.fixes_applied += 1
        
        # Check confidence is percentage (0-100)
        conf = pick.get('confidence', pick.get('eff%', pick.get('effective_confidence', 0)))
        if conf > 100:
            self.warnings.append(ValidationError(
                'WARNING',
                'DISPLAY',
                f"{pick.get('player')}: Confidence {conf}% > 100%",
                pick
            ))
        
        # Check Kelly percentage is reasonable
        kelly = pick.get('kelly_pct', 0)
        if kelly > 50:
            self.warnings.append(ValidationError(
                'WARNING',
                'DISPLAY',
                f"{pick.get('player')}: Kelly {kelly}% seems too high",
                pick
            ))
    
    def validate_opponent_data(self, pick):
        """Check opponent is known"""
        
        opponent = pick.get('opponent', '')
        
        if opponent in ['UNK', '', None]:
            self.warnings.append(ValidationError(
                'WARNING',
                'DATA_QUALITY',
                f"{pick.get('player')}: Opponent unknown",
                pick
            ))
    
    def validate_sample_size(self, pick):
        """Check sample size is adequate"""
        
        n = pick.get('n', pick.get('sample_n', pick.get('sample_size', 0)))
        
        if n == 0:
            self.errors.append(ValidationError(
                'CRITICAL',
                'DATA_QUALITY',
                f"{pick.get('player')} {pick.get('stat')}: Sample size is ZERO",
                pick
            ))
        elif n < 5:
            self.warnings.append(ValidationError(
                'WARNING',
                'DATA_QUALITY',
                f"{pick.get('player')} {pick.get('stat')}: Small sample (n={n})",
                pick
            ))
    
    def validate_special_characters(self, pick):
        """Check for problematic special characters"""
        
        player = pick.get('player', '')
        
        # Known problematic characters
        if 'ë' in player or 'ï' in player or 'ö' in player:
            self.warnings.append(ValidationError(
                'WARNING',
                'DATA_QUALITY',
                f"{player}: Contains special characters (may cause issues)",
                pick
            ))
    
    def check_for_duplicates(self, picks):
        """Check for duplicate picks (same player/stat/direction)"""
        
        seen = defaultdict(list)
        
        for i, pick in enumerate(picks):
            key = (
                pick.get('player'),
                pick.get('stat'),
                pick.get('direction'),
                pick.get('line')
            )
            seen[key].append(i)
        
        for key, indices in seen.items():
            if len(indices) > 1:
                player, stat, direction, line = key
                self.warnings.append(ValidationError(
                    'WARNING',
                    'DATA_QUALITY',
                    f"{player} {stat} {direction} {line}: Appears {len(indices)} times",
                    None
                ))

# ═══════════════════════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════════════════════

def print_validation_report(errors, warnings, fixes_applied):
    """Print comprehensive validation report"""
    
    print()
    print("=" * 80)
    print("📊 VALIDATION RESULTS")
    print("=" * 80)
    print()
    
    # Summary
    critical = [e for e in errors if e.severity == 'CRITICAL']
    errors_only = [e for e in errors if e.severity == 'ERROR']
    
    print(f"🔴 CRITICAL Issues:  {len(critical)}")
    print(f"🟠 Errors:           {len(errors_only)}")
    print(f"🟡 Warnings:         {len(warnings)}")
    print(f"✅ Auto-fixes:       {fixes_applied}")
    print()
    
    # Critical issues (must fix)
    if critical:
        print("=" * 80)
        print("🔴 CRITICAL ISSUES - MUST FIX BEFORE BETTING")
        print("=" * 80)
        for e in critical:
            print(f"  • {e.message}")
        print()
    
    # Errors (should fix)
    if errors_only:
        print("=" * 80)
        print("🟠 ERRORS - SHOULD FIX")
        print("=" * 80)
        for e in errors_only:
            print(f"  • {e.message}")
        print()
    
    # Warnings (review)
    if warnings:
        print("=" * 80)
        print("🟡 WARNINGS - REVIEW RECOMMENDED")
        print("=" * 80)
        
        # Group by category
        by_category = defaultdict(list)
        for w in warnings:
            by_category[w.category].append(w)
        
        for category, warns in by_category.items():
            print(f"\n  {category}:")
            for w in warns[:5]:  # Show max 5 per category
                print(f"    • {w.message}")
            if len(warns) > 5:
                print(f"    ... and {len(warns) - 5} more")
        print()
    
    # Pass/Fail
    print("=" * 80)
    if critical:
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        print()
        print("⚠️  DO NOT PROCEED TO BETTING")
        print("   Fix critical issues before generating reports")
        return False
    elif errors_only:
        print("⚠️  VALIDATION PASSED WITH ERRORS")
        print("=" * 80)
        print()
        print("⚠️  REVIEW ERRORS BEFORE BETTING")
        print("   Some picks may be mispriced")
        return True
    else:
        print("✅ VALIDATION PASSED")
        print("=" * 80)
        print()
        if warnings:
            print("ℹ️  Minor warnings detected (see above)")
        else:
            print("✅ No issues found - data looks clean!")
        return True

# ═══════════════════════════════════════════════════════════════════
# MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════════

def validate_slate(json_file, auto_fix=True, save_fixed=True):
    """
    Main validation function
    
    Args:
        json_file: Path to RISK_FIRST JSON
        auto_fix: Apply automatic fixes
        save_fixed: Save fixed version
    
    Returns:
        bool: True if validation passed
    """
    
    print("=" * 80)
    print("🔒 FUOOM QUALITY GATE - SLATE VALIDATION")
    print("=" * 80)
    print(f"File: {json_file}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print()
    
    # Load data
    with open(json_file, encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, dict):
        picks = data.get('results', data.get('picks', data.get('entries', [])))
    else:
        picks = data
    
    print(f"📊 Loaded {len(picks)} picks")
    print()
    
    # Run validation
    validator = SlateValidator()
    errors, warnings = validator.validate_all(picks)
    
    # Report results
    passed = print_validation_report(errors, warnings, validator.fixes_applied)
    
    # Save fixed version
    if auto_fix and validator.fixes_applied > 0 and save_fixed:
        output_file = json_file.replace('.json', '_VALIDATED.json')
        
        if isinstance(data, dict):
            if 'results' in data:
                data['results'] = picks
            elif 'picks' in data:
                data['picks'] = picks
            output_data = data
        else:
            output_data = picks
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print()
        print(f"💾 Fixed version saved: {output_file}")
    
    print()
    print("=" * 80)
    
    return passed

# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # Find most recent
        import glob
        files = glob.glob("outputs/*RISK_FIRST*.json")
        if files:
            json_file = sorted(files, key=lambda x: Path(x).stat().st_mtime)[-1]
            print(f"📂 Using most recent: {json_file}")
            print()
        else:
            print("Usage: python validate_slate.py YOUR_FILE.json")
            sys.exit(1)
    
    passed = validate_slate(json_file)
    
    sys.exit(0 if passed else 1)
