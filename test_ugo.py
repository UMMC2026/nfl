"""Test Universal Governance Object"""
import sys
sys.path.insert(0, '.')
from core.universal_governance_object import adapt_edge, Sport, validate_ugo
import json

# Example NBA edge
nba_edge_example = {
    'player': 'LeBron James',
    'stat': 'PTS',
    'line': 25.5,
    'direction': 'higher',
    'mu': 28.3,
    'sigma': 4.2,
    'sample_n': 10,
    'probability': 0.72,
    'tier': 'STRONG',
    'pick_state': 'OPTIMIZABLE',
    'edge_id': 'NBA::LeBron_James::PTS::25.5',
    'game_id': 'LAL_vs_GSW_20260201',
    'date': '2026-02-01',
    'ess_score': 0.68,
    'stability_tags': ['HIGH_VARIANCE'],
    'opponent': 'GSW',
    'home_away': 'HOME',
}

print("="*60)
print("UNIVERSAL GOVERNANCE OBJECT — TEST")
print("="*60)

# Convert NBA → UGO
ugo = adapt_edge(Sport.NBA, nba_edge_example)
print("\n✅ UGO Created:")
print(json.dumps(ugo.to_dict(), indent=2))

# Validate
is_valid, error = validate_ugo(ugo)
print(f"\n{'✅' if is_valid else '❌'} Validation: {error or 'PASS'}")

# Governance checks
print(f"\n🎯 Governance Status:")
print(f"   Optimizable: {ugo.is_optimizable()}")
print(f"   Vetted Only: {ugo.is_vetted_only()}")
print(f"   Rejected: {ugo.is_rejected()}")
print(f"   Governance Hash: {ugo.get_governance_hash()}")

print(f"\n📊 Statistical Core:")
print(f"   Edge Z-Score (edge_std): {ugo.edge_std:.3f}")
print(f"   Projection (mu): {ugo.mu:.1f}")
print(f"   Uncertainty (sigma): {ugo.sigma:.1f}")
print(f"   Line: {ugo.line:.1f}")
print(f"   Gap: {ugo.mu - ugo.line:.1f} ({(ugo.mu - ugo.line) / ugo.line * 100:.1f}% above line)")

print("\n" + "="*60)
print("TEST COMPLETE ✅")
print("="*60)
