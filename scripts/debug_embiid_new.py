"""Debug Embiid analysis"""
import sys
sys.path.insert(0, '.')
from risk_first_analyzer import analyze_prop_with_gates, PENALTY_MODE

print('PENALTY MODE:')
for k, v in PENALTY_MODE.items():
    print(f'  {k}: {v}')
print()

# Test Embiid
prop = {
    'player': 'Joel Embiid',
    'stat': 'points',
    'line': 27.5,
    'direction': 'higher',
    'team': 'PHI',
    'opponent': 'MIA',
}

result = analyze_prop_with_gates(prop, verbose=True)
print()
print('=' * 60)
print('FINAL RESULT:')
print(f'  Decision: {result.get("decision")}')
print(f'  Effective Confidence: {result.get("effective_confidence"):.1f}%')
print(f'  mu: {result.get("mu")}')
print(f'  sigma: {result.get("sigma")}')
print(f'  z_score: {result.get("z_score")}')
print()
print('Context notes:')
for note in result.get('context_warnings', []):
    print(f'  {note}')
