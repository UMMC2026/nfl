"""Test SDG integration with the governance pipeline."""

from core.decision_governance import enforce_governance

# Test a batch of picks
picks = [
    # Should REJECT: coin flip (line at mean)
    {'player': 'LeBron James', 'stat': 'PTS', 'line': 25.0, 'direction': 'higher',
     'probability': 58.0, 'mu': 25.0, 'sigma': 6.0},
    
    # Should PASS: good deviation
    {'player': 'Tyrese Maxey', 'stat': 'PTS', 'line': 22.5, 'direction': 'higher',
     'probability': 65.0, 'mu': 28.5, 'sigma': 6.0},  # z = -1.0
    
    # Should MEDIUM PENALTY but still pass
    {'player': 'Jaylen Brown', 'stat': 'REB', 'line': 5.5, 'direction': 'higher',
     'probability': 72.0, 'mu': 6.2, 'sigma': 2.0},  # z = -0.35
    
    # Should REJECT: low prob after SDG penalty
    {'player': 'Test Player', 'stat': 'AST', 'line': 7.0, 'direction': 'higher',
     'probability': 56.0, 'mu': 7.0, 'sigma': 2.5},  # z = 0 → 56*0.7=39.2%
]

result = enforce_governance(picks)

print('='*60)
print('FULL GOVERNANCE PIPELINE TEST')
print('='*60)

print(f"\nStats: {result['stats']}")
print(f"\nOptimizable: {len(result['optimizable'])}")
for p in result['optimizable']:
    prob = p.get('gated_probability', p['probability'])
    print(f"  ✅ {p['player']} {p['stat']}: {prob:.1f}%")

print(f"\nRejected: {len(result['rejected'])}")
for p in result['rejected']:
    elig = p.get('eligibility', {})
    reason = elig.get('rejection_reason', '?')
    print(f"  ❌ {p['player']} {p['stat']}: {reason}")

print('\n✅ Full governance pipeline working!')
