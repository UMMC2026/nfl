"""Analyze January 29, 2026 betting results"""

results = [
    {'player': 'Jaylen Brown', 'stat': '3PM', 'line': 1.0, 'direction': 'OVER', 'actual': 1, 'result': 'WON'},
    {'player': 'Jaden McDaniels', 'stat': 'PTS+AST', 'line': 16.5, 'direction': 'OVER', 'actual': 17, 'result': 'WON'},
    {'player': 'Matas Buzelis', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON'},
    {'player': 'Marcus Smart', 'stat': 'PTS', 'line': 9.5, 'direction': 'OVER', 'actual': 12, 'result': 'WON'},
    {'player': 'Amen Thompson', 'stat': 'PTS+AST', 'line': 23.5, 'direction': 'UNDER', 'actual': 22, 'result': 'WON'},
    {'player': 'Rudy Gobert', 'stat': 'REB', 'line': 11.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST'},
    {'player': 'Alperen Sengun', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'UNDER', 'actual': 39, 'result': 'LOST'},
    {'player': 'Domantas Sabonis', 'stat': 'PRA', 'line': 31.5, 'direction': 'UNDER', 'actual': 30, 'result': 'WON'},
    {'player': 'Kyle Kuzma', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 8, 'result': 'LOST'},
    {'player': 'Ryan Rollins', 'stat': 'PRA', 'line': 32.5, 'direction': 'UNDER', 'actual': 36, 'result': 'LOST'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST'},
    {'player': 'Aaron Wiggins', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 5, 'result': 'WON'},
    {'player': 'Jaden Ivey', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON'},
    {'player': 'Kelly Oubre Jr.', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 4, 'result': 'WON'},
    {'player': 'Bobby Portis', 'stat': 'REB', 'line': 8.5, 'direction': 'UNDER', 'actual': 12, 'result': 'LOST'},
    {'player': 'Tobias Harris', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST'},
    {'player': 'Duncan Robinson', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST'},
    {'player': 'Isaiah Collier', 'stat': 'PTS', 'line': 13.5, 'direction': 'UNDER', 'actual': 12, 'result': 'WON'},
    {'player': 'Isaiah Stewart', 'stat': 'PTS', 'line': 7.5, 'direction': 'UNDER', 'actual': 7, 'result': 'WON'},
    {'player': 'Jonas Valanciunas', 'stat': 'PTS', 'line': 12.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST'},
    {'player': 'Kyle Filipowski', 'stat': 'PTS+AST', 'line': 15.5, 'direction': 'UNDER', 'actual': 10, 'result': 'WON'},
    {'player': 'Kris Dunn', 'stat': 'PTS+AST', 'line': 9.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST'},
    {'player': 'Lauri Markkanen', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'OVER', 'actual': 23, 'result': 'LOST'},
    {'player': 'Jonas Valanciunas', 'stat': 'AST+REB', 'line': 10.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST'},
]

# Analysis
wins = sum(1 for r in results if r['result'] == 'WON')
losses = sum(1 for r in results if r['result'] == 'LOST')
total = len(results)

overs = [r for r in results if r['direction'] == 'OVER']
unders = [r for r in results if r['direction'] == 'UNDER']

over_wins = sum(1 for r in overs if r['result'] == 'WON')
under_wins = sum(1 for r in unders if r['result'] == 'WON')

# By stat type
by_stat = {}
for r in results:
    stat = r['stat']
    if stat not in by_stat:
        by_stat[stat] = {'wins': 0, 'losses': 0}
    if r['result'] == 'WON':
        by_stat[stat]['wins'] += 1
    else:
        by_stat[stat]['losses'] += 1

# Margin analysis (how close were the misses?)
close_losses = []
blowout_losses = []
for r in results:
    if r['result'] == 'LOST':
        margin = abs(r['actual'] - r['line'])
        if margin <= 2:
            close_losses.append(r)
        else:
            blowout_losses.append(r)

print('='*70)
print('  JANUARY 29, 2026 RESULTS ANALYSIS')
print('='*70)
print()
print(f'OVERALL: {wins}-{losses} ({wins/total*100:.1f}% hit rate)')
print()
print('BY DIRECTION:')
print(f'  OVERS:  {over_wins}-{len(overs)-over_wins} ({over_wins/len(overs)*100:.1f}%)')
print(f'  UNDERS: {under_wins}-{len(unders)-under_wins} ({under_wins/len(unders)*100:.1f}%)')
print()
print('BY STAT TYPE:')
for stat, data in sorted(by_stat.items(), key=lambda x: x[1]['wins']/(x[1]['wins']+x[1]['losses']) if (x[1]['wins']+x[1]['losses'])>0 else 0, reverse=True):
    total_stat = data['wins'] + data['losses']
    pct = data['wins']/total_stat*100 if total_stat > 0 else 0
    print(f"  {stat:12s}: {data['wins']}-{data['losses']} ({pct:.0f}%)")
print()
print('LOSS ANALYSIS:')
print(f'  Close losses (within 2): {len(close_losses)}')
for r in close_losses:
    margin = r['actual'] - r['line']
    print(f"    - {r['player']} {r['stat']} {r['direction']} {r['line']} -> actual {r['actual']} (margin: {margin:+.1f})")
print()
print(f'  Blowout losses (>2 off): {len(blowout_losses)}')
for r in blowout_losses:
    margin = r['actual'] - r['line']
    print(f"    - {r['player']} {r['stat']} {r['direction']} {r['line']} -> actual {r['actual']} (margin: {margin:+.1f})")

print()
print('='*70)
print('  KEY INSIGHTS')
print('='*70)
print()

# Identify patterns
print('PROBLEM PATTERNS IDENTIFIED:')
print()

# 3PM OVERS
three_pm = [r for r in results if r['stat'] == '3PM']
three_pm_wins = sum(1 for r in three_pm if r['result'] == 'WON')
print(f'1. 3PM OVERS: {three_pm_wins}/{len(three_pm)} ({three_pm_wins/len(three_pm)*100:.0f}%)')
print('   - Harris 0/2, Robinson 0/8 = COMPLETE BUSTS')
print('   - Brown barely hit (1/3), Ivey hit (2/6), Buzelis hit (2/6)')
print('   -> 3PM is HIGH VARIANCE, avoid unless clear edge')
print()

# REB UNDERS
reb_unders = [r for r in results if r['stat'] == 'REB' and r['direction'] == 'UNDER']
reb_under_wins = sum(1 for r in reb_unders if r['result'] == 'WON')
print(f'2. REB UNDERS: {reb_under_wins}/{len(reb_unders)} ({reb_under_wins/len(reb_unders)*100:.0f}%)')
print('   - Gobert 17 REB (line 11.5) = BLOWOUT')
print('   - Kuzma 8 REB (line 5.5), Portis 12 REB (line 8.5) = MISSED')
print('   -> Big men in close games grab extra boards')
print()

# Combo stats
combo = [r for r in results if '+' in r['stat']]
combo_wins = sum(1 for r in combo if r['result'] == 'WON')
print(f'3. COMBO STATS (PTS+AST, PRA, etc): {combo_wins}/{len(combo)} ({combo_wins/len(combo)*100:.0f}%)')
print('   - Sengun PTS+AST 39 vs line 25.5 = MASSIVE BUST')
print('   - Rollins PRA 36 vs line 32.5 = BUST')
print('   - Dunn PTS+AST 16 vs line 9.5 = BUST')
print('   -> Combo stats are VOLATILE, avoid UNDERs on stars')
print()

print('RECOMMENDATIONS:')
print('  [X] AVOID: 3PM OVERS on inconsistent shooters')
print('  [X] AVOID: REB UNDERS on centers in competitive games')
print('  [X] AVOID: Combo stat UNDERS on high-usage players')
print('  [OK] SAFE: PTS UNDERS on role players (Stewart, Collier hit)')
print('  [OK] SAFE: REB OVERS on energy guys (Wiggins hit)')
