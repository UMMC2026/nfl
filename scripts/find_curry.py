import json
import sys
sys.path.insert(0, '.')
from ai_commentary import generate_distributional_context

d = json.load(open('outputs/FRYDAY8DAT_RISK_FIRST_20260130_FROM_UD.json'))
results = d.get('results', d.get('picks', []))

print(f'Total picks: {len(results)}')

# Find Curry points LOWER pick (the one that showed 8000%)
for r in results:
    player = r.get('player', '')  # Changed from 'entity' to 'player'
    stat = r.get('stat', r.get('market', ''))  # Changed from 'market' to 'stat'
    conf = r.get('effective_confidence', 0)
    
    # Debug: print all Curry picks
    if 'Curry' in player:
        print(f'Found: {player} {stat} conf={conf:.1f}')
        emp = r.get('prob_method_details', {}).get('empirical_hit_rate', 'N/A')
        print(f'  emp_hit_rate: {emp}')
        ctx = generate_distributional_context(r)
        print(f'  Generated context: {ctx}')
        print()
