"""Simulate penalty impact on NBA LEAN calibration — matches pipeline logic exactly"""
import csv
import sys
sys.path.insert(0, '.')
from config.data_driven_penalties import get_data_driven_multiplier, SAMPLE_SIZE_RULES

# Load calibration data
lean_picks = []
with open('calibration_history.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('league','').upper() == 'NBA' and row.get('tier','').upper() == 'LEAN':
            lean_picks.append(row)

print(f'Total NBA LEAN picks: {len(lean_picks)}')

survived = []
rejected = []
for p in lean_picks:
    prob = float(p.get('probability', 0))
    stat = p.get('stat', '').lower().strip()
    direction = p.get('direction', '').lower().strip()
    hit = p.get('outcome', '').strip().upper() == 'HIT'
    
    # Use EXACT same function as pipeline
    unified_mult = get_data_driven_multiplier(stat, direction, "nba")
    adj_prob = prob * unified_mult
    
    # Cap to floor
    adj_prob = max(adj_prob, 50.0)
    adj_prob = min(adj_prob, 100.0)
    
    if adj_prob >= 55.0:
        survived.append({'stat': stat, 'dir': direction, 'prob': prob, 'adj_prob': adj_prob, 'hit': hit, 'mult': unified_mult})
    else:
        rejected.append({'stat': stat, 'dir': direction, 'prob': prob, 'adj_prob': adj_prob, 'hit': hit, 'mult': unified_mult})

print(f'\n=== POST-PENALTY SIMULATION ===')
print(f'Survived (adj_prob >= 55%): {len(survived)}')
print(f'Rejected (adj_prob < 55%): {len(rejected)}')

if survived:
    surv_hits = sum(1 for s in survived if s['hit'])
    print(f'\nSurvived hit rate: {surv_hits}/{len(survived)} = {surv_hits/len(survived)*100:.1f}%')
if rejected:
    rej_hits = sum(1 for r in rejected if r['hit'])
    print(f'Rejected hit rate: {rej_hits}/{len(rejected)} = {rej_hits/len(rejected)*100:.1f}%')

print(f'\n--- REJECTED PICKS BREAKDOWN ---')
rej_combos = {}
for r in rejected:
    key = f"{r['stat']} {r['dir']}"
    if key not in rej_combos:
        rej_combos[key] = {'total': 0, 'hits': 0}
    rej_combos[key]['total'] += 1
    if r['hit']:
        rej_combos[key]['hits'] += 1
for k, v in sorted(rej_combos.items()):
    print(f'  {k}: {v["total"]} rejected ({v["hits"]} were hits = collateral)')

print(f'\n--- SURVIVED PICKS BREAKDOWN ---')
surv_combos = {}
for s in survived:
    key = f"{s['stat']} {s['dir']}"
    if key not in surv_combos:
        surv_combos[key] = {'total': 0, 'hits': 0}
    surv_combos[key]['total'] += 1
    if s['hit']:
        surv_combos[key]['hits'] += 1
for k, v in sorted(surv_combos.items()):
    hr = v['hits']/v['total']*100 if v['total'] > 0 else 0
    print(f'  {k}: {v["hits"]}/{v["total"]} ({hr:.1f}%)')

print(f'\n=== PROJECTED NEW LEAN TIER ===')
if survived:
    new_lean_rate = surv_hits / len(survived) * 100
    print(f'Hit rate: {surv_hits}/{len(survived)} = {new_lean_rate:.1f}%')
    print(f'Target: 55.0%')
    print(f'Delta: {new_lean_rate - 55.0:+.1f}%')
    status = 'PASS' if new_lean_rate >= 55.0 else 'FAIL'
    print(f'STATUS: {status}')
    
    # Brier score
    brier_sum = 0
    for s in survived:
        p_norm = s['adj_prob'] / 100.0
        outcome = 1.0 if s['hit'] else 0.0
        brier_sum += (p_norm - outcome) ** 2
    brier = brier_sum / len(survived)
    print(f'\nProjected Brier score (survived LEAN): {brier:.4f}')
    print(f'Threshold: 0.2500')
    brier_status = 'PASS' if brier <= 0.25 else 'FAIL'
    print(f'STATUS: {brier_status}')

# Also compute overall NBA Brier with STRONG included
print(f'\n=== OVERALL NBA (STRONG + LEAN survived) ===')
strong_picks = []
with open('calibration_history.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('league','').upper() == 'NBA' and row.get('tier','').upper() == 'STRONG':
            strong_picks.append(row)

all_nba = []
for p in strong_picks:
    prob = float(p.get('probability', 0))
    hit = p.get('outcome', '').strip().upper() == 'HIT'
    all_nba.append({'prob': prob, 'hit': hit})

for s in survived:
    all_nba.append({'prob': s['adj_prob'], 'hit': s['hit']})

total_hits = sum(1 for x in all_nba if x['hit'])
overall_rate = total_hits / len(all_nba) * 100 if all_nba else 0
print(f'Total NBA picks (STRONG + survived LEAN): {len(all_nba)}')
print(f'Overall hit rate: {total_hits}/{len(all_nba)} = {overall_rate:.1f}%')

brier_all = sum((x['prob']/100 - (1.0 if x['hit'] else 0.0))**2 for x in all_nba) / len(all_nba)
print(f'Overall Brier score: {brier_all:.4f}')
brier_all_status = 'PASS' if brier_all <= 0.25 else 'FAIL'
print(f'STATUS: {brier_all_status}')

# BEFORE vs AFTER comparison
print(f'\n=== BEFORE vs AFTER COMPARISON ===')
original_hits = sum(1 for p in lean_picks if p.get('outcome','').strip().upper() == 'HIT')
print(f'BEFORE: {original_hits}/{len(lean_picks)} = {original_hits/len(lean_picks)*100:.1f}% (all 66 LEAN)')
if survived:
    print(f'AFTER:  {surv_hits}/{len(survived)} = {surv_hits/len(survived)*100:.1f}% ({len(survived)} survived LEAN)')
    improvement = (surv_hits/len(survived)*100) - (original_hits/len(lean_picks)*100)
    print(f'Improvement: {improvement:+.1f}%')
