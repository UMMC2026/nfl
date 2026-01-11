#!/usr/bin/env python3
"""
Compare yesterday's hits to today's fresh picks.
"""

import csv
import json

# Load yesterday's results
results = {}
with open('data/reconciliation_results.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['date'] == '2025-12-31':
            key = f"{row['player']}|{row['stat']}|{row['line']}"
            results[key] = {
                'tier': row['tier'],
                'result': row['result'],
                'actual': row['actual_value'],
                'line': row['line']
            }

# Load today's picks
with open('picks_hydrated.json') as f:
    today_picks = json.load(f)

# Compare
print('=' * 70)
print('🏀 YESTERDAY PERFORMANCE vs TODAY PICKS')
print('=' * 70)

print('\n📊 YESTERDAY RESULTS (2025-12-31):')
print('-' * 70)
hit_count = sum(1 for r in results.values() if r['result'] == 'HIT')
miss_count = sum(1 for r in results.values() if r['result'] == 'MISS')
push_count = sum(1 for r in results.values() if r['result'] == 'PUSH')

print(f'  ✅ HITS: {hit_count}')
for key, data in results.items():
    if data['result'] == 'HIT':
        player, stat, line = key.split('|')
        print(f'     • {player} {stat} O{line} (SLAM) → HIT at {data["actual"]}')

print(f'\n  ❌ MISSES: {miss_count}')
for key, data in results.items():
    if data['result'] == 'MISS':
        player, stat, line = key.split('|')
        print(f'     • {player} {stat} O{line} (SLAM) → MISS at {data["actual"]}')

print(f'\n  🟡 PUSHES: {push_count}')
for key, data in results.items():
    if data['result'] == 'PUSH':
        player, stat, line = key.split('|')
        print(f'     • {player} {stat} O{line} (SLAM) → PUSH at {data["actual"]}')

print(f'\n  📈 Hit Rate: {hit_count}/{len(results)} = {100*hit_count/len(results):.0f}%')

print('\n🔄 TODAY PICKS (2026-01-01):')
print('-' * 70)
today_slams = [p for p in today_picks if p.get('tier') == 'SLAM']
print(f'  Total SLAM picks for today: {len(today_slams)}')

# Check if any yesterday hits are repeated today
print('\n🔁 REPEATED FROM YESTERDAY HITS:')
repeat_count = 0
for key, data in results.items():
    if data['result'] == 'HIT':
        player, stat, line = key.split('|')
        for p in today_slams:
            if p.get('player') == player and p.get('stat') == stat and str(p.get('line')) == line:
                print(f'  ✅ {player} {stat} O{line} - REPEATING (HIT yesterday)')
                repeat_count += 1

if repeat_count == 0:
    print('  (No winning picks repeated)')

print('\n' + '=' * 70)
print(f'⚡ SUMMARY: {hit_count} HIT | {miss_count} MISS | {push_count} PUSH yesterday')
print(f'🎯 Today has {len(today_slams)} SLAM picks ({repeat_count} are repeats from winning picks)')
print('=' * 70)
