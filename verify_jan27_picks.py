#!/usr/bin/env python3
"""
Verify Jan 27 Stat Rankings picks against actual box scores.
"""

from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as nba_players
import time

# Players to verify from Jan 27 report
picks = [
    {'player': 'Jaden Ivey', 'stat': '3PM', 'line': 0.5, 'side': 'OVER', 'mean': 1.8, 'delta': '+265%'},
    {'player': 'Jalen Pickett', 'stat': '3PM', 'line': 0.5, 'side': 'OVER', 'mean': 1.4, 'delta': '+188%'},
    {'player': 'Zeke Nnaji', 'stat': '3PM', 'line': 1.5, 'side': 'OVER', 'mean': 0.3, 'delta': '-83%'},
    {'player': 'Ronald Holland', 'stat': '3PM', 'line': 1.5, 'side': 'OVER', 'mean': 0.6, 'delta': '-58%'},
    {'player': 'Kris Dunn', 'stat': 'REB+AST', 'line': 14.5, 'side': 'OVER', 'mean': 6.8, 'delta': '-53%'},
    {'player': 'Ausar Thompson', 'stat': 'REB+AST', 'line': 8.5, 'side': 'OVER', 'mean': 10.0, 'delta': '+18%'},
    {'player': 'Jalen Pickett', 'stat': 'REB+AST', 'line': 8.0, 'side': 'OVER', 'mean': 10.9, 'delta': '+37%'},
    {'player': 'Peyton Watson', 'stat': 'REB+AST', 'line': 6.5, 'side': 'OVER', 'mean': 8.8, 'delta': '+35%'},
    {'player': 'Bruce Brown', 'stat': 'PTS+AST', 'line': 8.5, 'side': 'OVER', 'mean': 10.5, 'delta': '+23%'},
    {'player': 'Duncan Robinson', 'stat': 'PTS+AST', 'line': 12.5, 'side': 'OVER', 'mean': 15.2, 'delta': '+22%'},
]

print('=' * 80)
print('  🏀 HIT/MISS VERIFICATION — Jan 27, 2026 Stat Rankings Report')
print('=' * 80)
print()

results = {'hit': 0, 'miss': 0, 'push': 0, 'dnp': 0, 'error': 0}
verified = []

for pick in picks:
    name = pick['player']
    try:
        # Find player
        matches = nba_players.find_players_by_full_name(name)
        if not matches:
            print(f"  ❓ {name}: Player not found in NBA database")
            results['error'] += 1
            continue
        
        player_id = matches[0]['id']
        
        # Get recent game log
        time.sleep(0.7)  # Rate limit to avoid 429
        log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
        df = log.get_data_frames()[0]
        
        if df.empty:
            print(f"  ❓ {name}: No games found this season")
            results['error'] += 1
            continue
        
        # Get most recent game
        latest = df.iloc[0]
        game_date = latest['GAME_DATE']
        matchup = latest['MATCHUP']
        minutes = latest['MIN']
        
        # Check for DNP
        if minutes == 0 or minutes is None:
            print(f"  🚫 {name}: DNP ({game_date}) — {matchup}")
            results['dnp'] += 1
            continue
        
        # Extract actual stat
        if pick['stat'] == '3PM':
            actual = int(latest['FG3M'])
        elif pick['stat'] == 'REB+AST':
            actual = int(latest['REB']) + int(latest['AST'])
        elif pick['stat'] == 'PTS+AST':
            actual = int(latest['PTS']) + int(latest['AST'])
        else:
            actual = 0
        
        # Grade the pick
        line = pick['line']
        if actual > line:
            hit = pick['side'] == 'OVER'
        elif actual < line:
            hit = pick['side'] == 'UNDER'
        else:
            # Push
            result_str = '➖ PUSH'
            results['push'] += 1
            verified.append({**pick, 'actual': actual, 'result': 'PUSH', 'game_date': game_date})
            print(f"  {result_str} | {name}: {pick['stat']} {pick['side']} {line} — Actual: {actual} | {matchup}")
            continue
        
        if hit:
            result_str = '✅ HIT'
            results['hit'] += 1
        else:
            result_str = '❌ MISS'
            results['miss'] += 1
        
        verified.append({**pick, 'actual': actual, 'result': 'HIT' if hit else 'MISS', 'game_date': game_date})
        print(f"  {result_str} | {name}: {pick['stat']} {pick['side']} {line} — Actual: {actual} | {matchup}")
        
    except Exception as e:
        print(f"  ⚠️ {name}: API Error - {e}")
        results['error'] += 1

# Summary
print()
print('=' * 80)
print('  📊 VERIFICATION SUMMARY')
print('=' * 80)
total_graded = results['hit'] + results['miss'] + results['push']
if total_graded > 0:
    hit_rate = results['hit'] / total_graded * 100
    print(f"  ✅ HITs:   {results['hit']}")
    print(f"  ❌ MISSes: {results['miss']}")
    print(f"  ➖ PUSHes: {results['push']}")
    print(f"  🚫 DNPs:   {results['dnp']}")
    print(f"  ⚠️ Errors: {results['error']}")
    print()
    print(f"  📈 Hit Rate: {hit_rate:.1f}% ({results['hit']}/{total_graded})")
else:
    print("  No picks could be verified.")

# Analyze directionally-inconsistent picks
print()
print('=' * 80)
print('  🔍 DIRECTIONAL CONSISTENCY ANALYSIS')
print('=' * 80)
for v in verified:
    delta = v.get('delta', '')
    is_negative_delta = delta.startswith('-')
    is_over = v['side'] == 'OVER'
    
    if is_over and is_negative_delta:
        print(f"  🚨 BUG: {v['player']} {v['stat']} — OVER with mean < line (delta {delta})")
        print(f"       → This should have been UNDER or NO PLAY")
        print(f"       → Result: {v['result']} (Actual: {v['actual']} vs Line: {v['line']})")
