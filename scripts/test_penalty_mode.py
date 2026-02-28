"""Test: Re-analyze props with penalty mode OFF"""
import json
import sys
from pathlib import Path
from collections import Counter

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load the props from latest file
outputs = Path(__file__).parent.parent / 'outputs'
files = sorted(outputs.glob('*RISK_FIRST*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
latest = files[0]

with open(latest, 'r') as f:
    data = json.load(f)

# Import analyzer with new penalty mode
from risk_first_analyzer import analyze_prop_with_gates as analyze_prop, PENALTY_MODE

print('PENALTY MODE ACTIVE:')
for k, v in PENALTY_MODE.items():
    print(f'  {k}: {v}')
print()

# Re-analyze first 30 props
results = data.get('results', [])[:30]
new_decisions = []
changes = []

print('RE-ANALYZING 30 PROPS WITH PENALTIES OFF:')
print('-' * 70)
print(f'{"PLAYER":<22} {"STAT":<8} {"LINE":>6} {"OLD":<10} {"NEW":<10} {"CONF":>6}')
print('-' * 70)

for r in results:
    # Build prop dict for re-analysis
    prop = {
        'player': r.get('player'),
        'stat': r.get('stat'),
        'line': r.get('line'),
        'direction': r.get('direction'),
        'team': r.get('team', ''),
        'opponent': r.get('opponent', ''),
    }
    
    try:
        result = analyze_prop(prop, verbose=False)
        old_status = r.get('status', 'UNK')
        new_status = result.get('decision', 'UNK')
        new_conf = result.get('effective_confidence', 0)
        
        # Track changes
        if old_status != new_status:
            changes.append({
                'player': prop['player'],
                'stat': prop['stat'],
                'old': old_status,
                'new': new_status,
                'conf': new_conf
            })
        
        marker = '→' if old_status != new_status else ' '
        print(f'{prop["player"][:22]:<22} {prop["stat"]:<8} {prop["line"]:>6} {old_status:<10} {marker}{new_status:<10} {new_conf:>5.0f}%')
        new_decisions.append(new_status)
    except Exception as e:
        print(f'{prop["player"][:22]:<22} ERROR: {e}')

print()
print('=' * 70)
print('SUMMARY:')
old_counts = Counter(r.get('status') for r in results)
new_counts = Counter(new_decisions)
print(f'  BEFORE (with penalties): {dict(old_counts)}')
print(f'  AFTER (no penalties):    {dict(new_counts)}')

print()
print(f'UPGRADES: {len(changes)} props changed decision')
for c in changes[:10]:
    print(f'  ✅ {c["player"]}: {c["old"]} → {c["new"]} ({c["conf"]:.0f}%)')
