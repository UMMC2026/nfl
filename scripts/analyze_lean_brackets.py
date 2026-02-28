"""Analyze LEAN picks by probability bracket to find root cause"""
import csv

lean_picks = []
with open('calibration_history.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('league','').upper() == 'NBA' and row.get('tier','').upper() == 'LEAN':
            prob = float(row.get('probability', 0))
            hit = row.get('outcome','').strip().upper() == 'HIT'
            stat = row.get('stat','').lower().strip()
            direction = row.get('direction','').lower().strip()
            lean_picks.append({'prob': prob, 'hit': hit, 'stat': stat, 'dir': direction})

print(f'Total NBA LEAN: {len(lean_picks)}')
print()

print('=== BY PROBABILITY BRACKET ===')
brackets = [(0,55,'CONTAMINATED (pre-governance)'), (55,60,'Borderline 55-60'), (60,65,'Core 60-65'), (65,100,'Strong 65+')]
for lo, hi, label in brackets:
    picks = [p for p in lean_picks if lo <= p['prob'] < hi]
    if picks:
        hits = sum(1 for p in picks if p['hit'])
        print(f'\n{label}: {hits}/{len(picks)} = {hits/len(picks)*100:.1f}%')
        combos = {}
        for p in picks:
            key = f"{p['stat']} {p['dir']}"
            if key not in combos:
                combos[key] = [0,0]
            combos[key][0] += 1
            if p['hit']:
                combos[key][1] += 1
        for k,v in sorted(combos.items(), key=lambda x: -x[1][0]):
            hr = v[1]/v[0]*100 if v[0] > 0 else 0
            marker = 'OK' if hr >= 55 else 'BAD'
            print(f'   {k}: {v[1]}/{v[0]} ({hr:.0f}%) [{marker}]')

print()
print('=== VALID PICKS (prob >= 55) BY STAT+DIR ===')
valid = [p for p in lean_picks if p['prob'] >= 55.0]
print(f'Count: {len(valid)}, Hits: {sum(1 for p in valid if p["hit"])}/{len(valid)} = {sum(1 for p in valid if p["hit"])/len(valid)*100:.1f}%')
valid_by_combo = {}
for p in valid:
    key = f"{p['stat']} {p['dir']}"
    if key not in valid_by_combo:
        valid_by_combo[key] = [0,0]
    valid_by_combo[key][0] += 1
    if p['hit']:
        valid_by_combo[key][1] += 1
for k,v in sorted(valid_by_combo.items(), key=lambda x: -x[1][0]):
    hr = v[1]/v[0]*100 if v[0] > 0 else 0
    marker = 'OK' if hr >= 55 else 'BAD'
    print(f'   {k}: {v[1]}/{v[0]} ({hr:.0f}%) [{marker}]')

# What if we ONLY kept PRA lower?
print()
print('=== PRA LOWER ONLY (BEST EDGE) ===')
pra_lower = [p for p in valid if p['stat'] in ('pra','pts+reb+ast') and p['dir'] in ('lower','under')]
if pra_lower:
    hits = sum(1 for p in pra_lower if p['hit'])
    print(f'PRA lower: {hits}/{len(pra_lower)} = {hits/len(pra_lower)*100:.1f}%')

# Points lower analysis
print()
print('=== POINTS LOWER (PROBLEM CHILD) ===')
pts_lower = [p for p in valid if p['stat'] in ('pts','points') and p['dir'] in ('lower','under')]
if pts_lower:
    hits = sum(1 for p in pts_lower if p['hit'])
    print(f'Points lower: {hits}/{len(pts_lower)} = {hits/len(pts_lower)*100:.1f}%')
    print('These picks should NOT be surviving at LEAN')

# What the forward LEAN tier SHOULD look like
print()
print('=== FORWARD-LOOKING LEAN COMPOSITION ===')
print('After penalty fixes, LEAN will be dominated by:')
print('1. PRA LOWER (72.7%) - ANCHOR')
print('2. Occasional assists-lower, 3pm combos')
print('3. Everything else gets penalized out')
print()
print('Expected forward hit rate: ~65-70% (PRA-lower weighted)')
