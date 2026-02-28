"""Investigate Cam Thomas data issue - why μ=8.7 instead of ~24"""
import json

d = json.load(open('outputs/FRYDAY8DAT_RISK_FIRST_20260130_FROM_UD.json'))
results = d.get('results', [])

print('=== CAM THOMAS INVESTIGATION ===')
for r in results:
    player = r.get('player', '')
    if 'Cam Thomas' in player:
        stat = r.get('stat', '')
        mu = r.get('mu', 0)
        mu_raw = r.get('mu_raw', 0)
        sample_n = r.get('sample_n', 0)
        series = r.get('series', [])
        conf = r.get('effective_confidence', 0)
        direction = r.get('direction', '')
        line = r.get('line', 0)
        
        print(f'\nStat: {stat} {direction} {line}')
        print(f'  mu: {mu}, mu_raw: {mu_raw}')
        print(f'  sample_n: {sample_n}')
        if series:
            print(f'  series (games): {series[:10]}')
            print(f'  series avg: {sum(series)/len(series):.1f}')
        else:
            print('  series: EMPTY - NO DATA!')
        print(f'  confidence: {conf:.1f}%')
