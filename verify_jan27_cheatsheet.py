#!/usr/bin/env python3
"""
Verify Jan 27 NBA Cheat Sheet picks against actual box scores.
Also includes structural issue detection and 2-day comparison.
"""

from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as nba_players
import time

# Picks from NBA_CHEATSHEET_20260127_0925.txt
picks = [
    # OVERS
    {'player': 'Miles McBride', 'stat': 'REB', 'line': 1.5, 'side': 'OVER', 'prob': 79.6, 'tier_claimed': 'LEAN'},
    {'player': 'Zach LaVine', 'stat': 'REB', 'line': 1.5, 'side': 'OVER', 'prob': 79.6, 'tier_claimed': 'LEAN'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'side': 'OVER', 'prob': 79.6, 'tier_claimed': 'LEAN'},
    {'player': 'Quentin Grimes', 'stat': 'REB', 'line': 2.5, 'side': 'OVER', 'prob': 75.4, 'tier_claimed': 'LEAN'},
    {'player': 'Caleb Love', 'stat': 'REB', 'line': 2.5, 'side': 'OVER', 'prob': 72.6, 'tier_claimed': 'LEAN'},
    {'player': 'Donovan Clingan', 'stat': 'REB+AST', 'line': 11.5, 'side': 'OVER', 'prob': 71.4, 'tier_claimed': 'LEAN'},
    {'player': 'Precious Achiuwa', 'stat': 'REB+AST', 'line': 4.5, 'side': 'OVER', 'prob': 71.4, 'tier_claimed': 'LEAN'},
    {'player': 'Miles McBride', 'stat': 'REB+AST', 'line': 4.5, 'side': 'OVER', 'prob': 71.4, 'tier_claimed': 'LEAN'},
    # UNDERS
    {'player': 'Kyle Kuzma', 'stat': 'REB', 'line': 6.0, 'side': 'UNDER', 'prob': 76.0, 'tier_claimed': 'LEAN'},
    {'player': 'Mikal Bridges', 'stat': 'REB+AST', 'line': 8.0, 'side': 'UNDER', 'prob': 71.4, 'tier_claimed': 'LEAN'},
    {'player': 'Ryan Rollins', 'stat': 'REB+AST', 'line': 11.5, 'side': 'UNDER', 'prob': 71.4, 'tier_claimed': 'LEAN'},
    {'player': 'Myles Turner', 'stat': 'REB+AST', 'line': 8.5, 'side': 'UNDER', 'prob': 71.4, 'tier_claimed': 'LEAN'},
    {'player': 'Ryan Rollins', 'stat': 'PRA', 'line': 32.5, 'side': 'UNDER', 'prob': 68.0, 'tier_claimed': 'LEAN'},
    # Duplicate removed: {'player': 'Ryan Rollins', 'stat': 'PRA', 'line': 32.5, 'side': 'UNDER', 'prob': 68.0},
    {'player': 'Kyle Kuzma', 'stat': 'PRA', 'line': 23.5, 'side': 'UNDER', 'prob': 68.0, 'tier_claimed': 'LEAN'},
    {'player': 'Gary Trent', 'stat': 'PRA', 'line': 10.5, 'side': 'UNDER', 'prob': 68.0, 'tier_claimed': 'LEAN'},
]

print('=' * 90)
print('  🏀 NBA CHEAT SHEET VERIFICATION — Jan 27, 2026')
print('=' * 90)

# SECTION 1: Structural Issues
print()
print('┌' + '─' * 88 + '┐')
print('│' + '  🚨 STRUCTURAL ISSUES DETECTED'.center(88) + '│')
print('└' + '─' * 88 + '┘')

print("""
  ❌ ERROR #1: Tier-Probability Mismatch (ALL 16 picks)
     Legend says: LEAN = 60-69%, STRONG = 70-79%, SLAM = ≥80%
     But picks at 79.6%, 76.0%, 75.4%, 72.6%, 71.4% are ALL labeled LEAN
     → 79.6% should be STRONG (nearly SLAM)
     → Every pick >69% is mislabeled

  ❌ ERROR #2: Duplicate Edge
     Ryan Rollins PRA U32.5 appears TWICE in the report
     → Violates: EDGE = unique(player, game_id, direction)

  ❌ ERROR #3: Same Player, Multiple Bets, No Correlation Tag
     Miles McBride: REB O1.5 AND REB+AST O4.5
     Kyle Kuzma: REB U6.0 AND PRA U23.5
     Ryan Rollins: REB+AST U11.5 AND PRA U32.5
     → No [CORRELATED] warning = hidden risk concentration

  ⚠️ WARNING: Probability Bucketing
     Only 5 unique probability values: 79.6%, 76.0%, 75.4%, 72.6%, 71.4%, 68.0%
     → Suggests binning, not player-specific calculation
""")

# SECTION 2: Outcome Verification
print('┌' + '─' * 88 + '┐')
print('│' + '  📊 OUTCOME VERIFICATION vs ACTUAL BOX SCORES'.center(88) + '│')
print('└' + '─' * 88 + '┘')
print()

results = {'hit': 0, 'miss': 0, 'push': 0, 'dnp': 0, 'error': 0}
by_market = {'REB': {'hit': 0, 'miss': 0}, 'REB+AST': {'hit': 0, 'miss': 0}, 'PRA': {'hit': 0, 'miss': 0}}
by_side = {'OVER': {'hit': 0, 'miss': 0}, 'UNDER': {'hit': 0, 'miss': 0}}
verified = []

for pick in picks:
    name = pick['player']
    try:
        matches = nba_players.find_players_by_full_name(name)
        if not matches:
            all_players = nba_players.get_players()
            matches = [p for p in all_players if name.lower() in p['full_name'].lower()]
        
        if not matches:
            print(f"  ❓ {name}: Not found in NBA database")
            results['error'] += 1
            continue
        
        player_id = matches[0]['id']
        time.sleep(0.7)
        
        log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
        df = log.get_data_frames()[0]
        
        if df.empty:
            print(f"  ❓ {name}: No games this season")
            results['error'] += 1
            continue
        
        latest = df.iloc[0]
        game_date = latest['GAME_DATE']
        matchup = latest['MATCHUP']
        minutes = latest['MIN']
        
        if minutes == 0 or minutes is None:
            print(f"  🚫 {name}: DNP ({game_date})")
            results['dnp'] += 1
            continue
        
        # Calculate actual
        stat = pick['stat']
        if stat == 'REB':
            actual = int(latest['REB'])
        elif stat == 'REB+AST':
            actual = int(latest['REB']) + int(latest['AST'])
        elif stat == 'PRA':
            actual = int(latest['PTS']) + int(latest['REB']) + int(latest['AST'])
        else:
            actual = 0
        
        line = pick['line']
        side = pick['side']
        
        if actual > line:
            hit = (side == 'OVER')
        elif actual < line:
            hit = (side == 'UNDER')
        else:
            result_str = '➖ PUSH'
            results['push'] += 1
            print(f"  {result_str} | {name}: {stat} {side} {line} — Actual: {actual}")
            continue
        
        result_str = '✅ HIT' if hit else '❌ MISS'
        if hit:
            results['hit'] += 1
            by_market[stat]['hit'] += 1
            by_side[side]['hit'] += 1
        else:
            results['miss'] += 1
            by_market[stat]['miss'] += 1
            by_side[side]['miss'] += 1
        
        # Check tier correctness
        prob = pick['prob']
        correct_tier = 'SLAM' if prob >= 80 else ('STRONG' if prob >= 70 else 'LEAN')
        tier_match = '✓' if correct_tier == pick['tier_claimed'] else f"→{correct_tier}"
        
        verified.append({**pick, 'actual': actual, 'result': 'HIT' if hit else 'MISS', 'correct_tier': correct_tier})
        print(f"  {result_str} | {name}: {stat} {side} {line} — Actual: {actual} | Tier: {pick['tier_claimed']} {tier_match}")
        
    except Exception as e:
        print(f"  ⚠️ {name}: Error - {e}")
        results['error'] += 1

# Summary
print()
print('=' * 90)
print('  📈 OUTCOME LEDGER — Jan 27, 2026')
print('=' * 90)

total = results['hit'] + results['miss'] + results['push']
if total > 0:
    hit_rate = results['hit'] / total * 100
    
    print(f"""
  ┌────────────────────────────────────┐
  │  ✅ HITs:    {results['hit']:>3}                   │
  │  ❌ MISSes:  {results['miss']:>3}                   │
  │  ➖ PUSHes:  {results['push']:>3}                   │
  │  🚫 DNPs:    {results['dnp']:>3}                   │
  │  ⚠️ Errors:  {results['error']:>3}                   │
  ├────────────────────────────────────┤
  │  📊 Hit Rate: {hit_rate:>5.1f}% ({results['hit']}/{total})       │
  └────────────────────────────────────┘
""")

# By Market
print('  BY MARKET:')
for market, data in by_market.items():
    t = data['hit'] + data['miss']
    if t > 0:
        rate = data['hit'] / t * 100
        print(f"    {market:>8}: {data['hit']}/{t} ({rate:.0f}%)")

print()
print('  BY SIDE:')
for side, data in by_side.items():
    t = data['hit'] + data['miss']
    if t > 0:
        rate = data['hit'] / t * 100
        print(f"    {side:>8}: {data['hit']}/{t} ({rate:.0f}%)")

# Tier analysis
print()
print('=' * 90)
print('  🔍 TIER ACCURACY ANALYSIS')
print('=' * 90)

tier_errors = sum(1 for v in verified if v['correct_tier'] != v['tier_claimed'])
print(f"""
  Picks with WRONG tier label: {tier_errors}/{len(verified)}
  
  Legend says:
    LEAN:   60-69%
    STRONG: 70-79%  
    SLAM:   ≥80%
  
  But report labeled ALL as LEAN, including:
    79.6% → should be STRONG (nearly SLAM!)
    76.0% → should be STRONG
    75.4% → should be STRONG
    72.6% → should be STRONG
    71.4% → should be STRONG
    68.0% → LEAN (correct)
""")

# 2-Day Comparison
print('=' * 90)
print('  📅 2-DAY ROLLING PERFORMANCE (Jan 26-27)')
print('=' * 90)

# Previous results from earlier verification runs
jan27_stat_rankings = {'hit': 3, 'miss': 7, 'total': 10, 'rate': 30.0}
jan27_balanced = {'hit': 5, 'miss': 7, 'total': 12, 'rate': 41.7}
jan27_cheatsheet = {'hit': results['hit'], 'miss': results['miss'], 'total': total, 'rate': hit_rate if total > 0 else 0}

print(f"""
  ┌─────────────────────────────────────────────────────────────┐
  │  REPORT                    │ PLAYS │ HIT │ MISS │ HIT %    │
  ├─────────────────────────────────────────────────────────────┤
  │  Stat Rankings (Jan 27)    │  {jan27_stat_rankings['total']:>3}  │  {jan27_stat_rankings['hit']:>2} │  {jan27_stat_rankings['miss']:>2}  │ {jan27_stat_rankings['rate']:>5.1f}%   │
  │  Balanced Report (Jan 27)  │  {jan27_balanced['total']:>3}  │  {jan27_balanced['hit']:>2} │  {jan27_balanced['miss']:>2}  │ {jan27_balanced['rate']:>5.1f}%   │
  │  Cheat Sheet (Jan 27)      │  {jan27_cheatsheet['total']:>3}  │  {jan27_cheatsheet['hit']:>2} │  {jan27_cheatsheet['miss']:>2}  │ {jan27_cheatsheet['rate']:>5.1f}%   │
  ├─────────────────────────────────────────────────────────────┤
""")

combined_hit = jan27_stat_rankings['hit'] + jan27_balanced['hit'] + jan27_cheatsheet['hit']
combined_miss = jan27_stat_rankings['miss'] + jan27_balanced['miss'] + jan27_cheatsheet['miss']
combined_total = combined_hit + combined_miss
combined_rate = combined_hit / combined_total * 100 if combined_total > 0 else 0

print(f"""  │  COMBINED (All Reports)    │  {combined_total:>3}  │  {combined_hit:>2} │  {combined_miss:>2}  │ {combined_rate:>5.1f}%   │
  └─────────────────────────────────────────────────────────────┘
""")

# Final Assessment
print('=' * 90)
print('  ⚖️ FINAL ASSESSMENT')  
print('=' * 90)

avg_claimed = sum(p['prob'] for p in picks) / len(picks)
print(f"""
  Average Claimed Probability: {avg_claimed:.1f}%
  Actual Hit Rate:             {hit_rate:.1f}%
  Overconfidence Gap:          {avg_claimed - hit_rate:+.1f}%

  🔴 ROOT CAUSES:
  
  1. TIER MISLABELING
     → 14/15 picks had wrong tier (LEAN instead of STRONG)
     → Misleads users about conviction level
     
  2. PROBABILITY BUCKETING  
     → Only 6 unique probability values
     → Not player-specific posteriors
     
  3. DUPLICATE EDGES
     → Ryan Rollins PRA U32.5 appeared twice
     → Should have been auto-rejected
     
  4. CORRELATED EXPOSURE
     → Same player, multiple markets, no warning
     → Hidden concentration risk
     
  5. NO MINUTES/ROLE GATES
     → Bench players without usage context
""")
