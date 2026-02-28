#!/usr/bin/env python3
"""
Verify Jan 27 BALANCED report picks against actual box scores.
Also flags structural issues (tier mismatch, directional bugs, etc.)
"""

from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as nba_players
import time

# Picks from TUE2NDH_BALANCED_20260127_FROM_UD.txt
picks = [
    {'player': 'Cam Thomas', 'team': 'BKN', 'stat': 'REB+AST', 'line': 3.5, 'side': 'OVER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Jalen Pickett', 'team': 'DEN', 'stat': 'REB+AST', 'line': 8.0, 'side': 'OVER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Peyton Watson', 'team': 'DEN', 'stat': 'REB+AST', 'line': 6.5, 'side': 'OVER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Jonas Valanciunas', 'team': 'DEN', 'stat': 'REB+AST', 'line': 10.5, 'side': 'UNDER', 'prob': 71.4, 'tier': 'LEAN', 'matchup_note': 'vs Weak D - but picking UNDER?'},
    {'player': 'Duncan Robinson', 'team': 'DET', 'stat': 'PTS+AST', 'line': 12.5, 'side': 'OVER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Isaiah Stewart', 'team': 'DET', 'stat': 'REB+AST', 'line': 5.5, 'side': 'OVER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Kris Dunn', 'team': 'LAC', 'stat': 'REB+AST', 'line': 14.5, 'side': 'UNDER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Jalen Green', 'team': 'PHX', 'stat': 'REB+AST', 'line': 5.5, 'side': 'UNDER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Lauri Markkanen', 'team': 'UTA', 'stat': 'PTS+AST', 'line': 24.5, 'side': 'OVER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Isaiah Collier', 'team': 'UTA', 'stat': 'REB+AST', 'line': 12.5, 'side': 'UNDER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Isaiah Collier', 'team': 'UTA', 'stat': 'PTS+AST', 'line': 22.5, 'side': 'UNDER', 'prob': 71.4, 'tier': 'LEAN'},
    {'player': 'Kyle Filipowski', 'team': 'UTA', 'stat': 'PTS+AST', 'line': 15.5, 'side': 'UNDER', 'prob': 71.4, 'tier': 'LEAN'},
]

print('=' * 80)
print('  🏀 BALANCED REPORT VERIFICATION — Jan 27, 2026')
print('=' * 80)

# SECTION 1: Structural Issues
print()
print('┌' + '─' * 78 + '┐')
print('│' + '  🚨 STRUCTURAL ISSUES DETECTED (Pre-Verification)'.ljust(78) + '│')
print('└' + '─' * 78 + '┘')

print()
print('  ❌ ISSUE 1: All picks show exactly 71.4% probability')
print('     → This is synthetic (5/7 bucket), not player-specific')
print('     → Violates "Confidence Is Earned" rule')
print()
print('  ❌ ISSUE 2: Tier-Probability Mismatch')
print('     → 71.4% should be STRONG (65-74%), not LEAN (55-64%)')
print('     → Every pick in this report has wrong tier label')
print()
print('  ❌ ISSUE 3: Directional Matchup Conflicts')
print('     → Jonas Valanciunas: UNDER vs Weak Defense (#27)')
print('     → Weak D favors OVERS, but pick is UNDER')
print('     → This is logically inconsistent')

# SECTION 2: Actual Verification
print()
print('┌' + '─' * 78 + '┐')
print('│' + '  📊 OUTCOME VERIFICATION vs ACTUAL BOX SCORES'.ljust(78) + '│')
print('└' + '─' * 78 + '┘')
print()

results = {'hit': 0, 'miss': 0, 'push': 0, 'dnp': 0, 'error': 0}
verified = []

for pick in picks:
    name = pick['player']
    try:
        # Find player
        matches = nba_players.find_players_by_full_name(name)
        if not matches:
            # Try partial match
            all_players = nba_players.get_players()
            matches = [p for p in all_players if name.lower() in p['full_name'].lower()]
        
        if not matches:
            print(f"  ❓ {name}: Player not found")
            results['error'] += 1
            continue
        
        player_id = matches[0]['id']
        
        # Rate limit
        time.sleep(0.7)
        log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
        df = log.get_data_frames()[0]
        
        if df.empty:
            print(f"  ❓ {name}: No games found")
            results['error'] += 1
            continue
        
        # Get most recent game
        latest = df.iloc[0]
        game_date = latest['GAME_DATE']
        matchup = latest['MATCHUP']
        minutes = latest['MIN']
        
        if minutes == 0 or minutes is None:
            print(f"  🚫 {name}: DNP ({game_date})")
            results['dnp'] += 1
            continue
        
        # Calculate actual stat
        if pick['stat'] == 'REB+AST':
            actual = int(latest['REB']) + int(latest['AST'])
        elif pick['stat'] == 'PTS+AST':
            actual = int(latest['PTS']) + int(latest['AST'])
        else:
            actual = 0
        
        # Grade
        line = pick['line']
        side = pick['side']
        
        if actual > line:
            hit = (side == 'OVER')
        elif actual < line:
            hit = (side == 'UNDER')
        else:
            result_str = '➖ PUSH'
            results['push'] += 1
            verified.append({**pick, 'actual': actual, 'result': 'PUSH', 'minutes': minutes})
            print(f"  {result_str} | {name}: {pick['stat']} {side} {line} — Actual: {actual} | {matchup}")
            continue
        
        result_str = '✅ HIT' if hit else '❌ MISS'
        if hit:
            results['hit'] += 1
        else:
            results['miss'] += 1
        
        verified.append({**pick, 'actual': actual, 'result': 'HIT' if hit else 'MISS', 'minutes': minutes})
        print(f"  {result_str} | {name}: {pick['stat']} {side} {line} — Actual: {actual} | {matchup}")
        
    except Exception as e:
        print(f"  ⚠️ {name}: Error - {e}")
        results['error'] += 1

# Summary
print()
print('=' * 80)
print('  📈 OUTCOME LEDGER SUMMARY')
print('=' * 80)

total = results['hit'] + results['miss'] + results['push']
if total > 0:
    hit_rate = results['hit'] / total * 100
    print(f"""
  ✅ HITs:   {results['hit']}
  ❌ MISSes: {results['miss']}
  ➖ PUSHes: {results['push']}
  🚫 DNPs:   {results['dnp']}
  ⚠️ Errors: {results['error']}

  📊 Hit Rate: {hit_rate:.1f}% ({results['hit']}/{total})
""")

# Tier accuracy check
print('=' * 80)
print('  🔍 TIER ACCURACY ANALYSIS')
print('=' * 80)
print()
print('  SOP Tier Thresholds:')
print('    LEAN:   55-64%')
print('    STRONG: 65-74%')
print('    SLAM:   ≥80%')
print()
print(f'  Report claimed: All LEAN at 71.4%')
print(f'  Correct tier:   STRONG (71.4% is in 65-74% range)')
print()
print('  ⚠️  TIER MISLABELING: 12/12 picks have wrong tier')

# Final assessment
print()
print('=' * 80)
print('  ⚖️ FINAL ASSESSMENT')
print('=' * 80)
print(f"""
  Actual Hit Rate:     {hit_rate:.1f}%
  Claimed Probability: 71.4%
  Gap:                 {71.4 - hit_rate:+.1f}%

  🔴 Model is OVERCONFIDENT by ~{71.4 - hit_rate:.0f} percentage points
  
  Root causes:
  1. Synthetic probability (not player-specific)
  2. Tier-probability mismatch (LEAN vs STRONG)
  3. Directional matchup conflicts
  4. No minutes/role gates applied
""")
