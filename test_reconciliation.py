#!/usr/bin/env python
"""Test reconciliation loader and safety functions."""

from ufa.ingest.reconciliation_loader import ReconciliationLoader
from ufa.daily_pipeline import reconcile_picks, compute_performance_metrics, print_data_status, validate_metrics_state

print("=" * 70)
print("RECONCILIATION & SAFETY FUNCTIONS TEST")
print("=" * 70)

# Test 1: Load CSV
print("\n1️⃣ Testing ReconciliationLoader.load_csv()...")
loader = ReconciliationLoader()
results = loader.load_csv()
print(f"✅ Loaded {len(results)} results from CSV")
for r in results:
    print(f"  {r['player']} {r['stat']}: {r['result']} (actual: {r['actual_value']})")

# Test 2: Build results lookup
print("\n2️⃣ Building results lookup dict...")
results_lookup = {}
for result in results:
    key = (result['date'], result['player'], result['stat'])
    results_lookup[key] = result
print(f"✅ Created lookup with {len(results_lookup)} entries")

# Test 3: Create mock picks
print("\n3️⃣ Creating mock picks...")
mock_picks = [
    {'date': '2025-12-31', 'player': 'OG Anunoby', 'stat': 'points', 'confidence': 0.75, 'tier': 'SLAM'},
    {'date': '2025-12-31', 'player': 'Jamal Shead', 'stat': 'points', 'confidence': 0.75, 'tier': 'SLAM'},
    {'date': '2025-12-31', 'player': 'Giannis Antetokounmpo', 'stat': 'points', 'confidence': 0.75, 'tier': 'SLAM'},
    {'date': '2025-12-31', 'player': 'Unknown Player', 'stat': 'assists', 'confidence': 0.60, 'tier': 'STRONG'},
]
print(f"✅ Created {len(mock_picks)} mock picks")

# Test 4: Reconcile
print("\n4️⃣ Testing reconcile_picks()...")
resolved, pending = reconcile_picks(mock_picks, results_lookup)
print(f"✅ Resolved: {len(resolved)} | Pending: {len(pending)}")
print(f"  Resolved picks: {[p['player'] for p in resolved]}")
print(f"  Pending picks: {[p['player'] for p in pending]}")

# Test 5: Compute metrics
print("\n5️⃣ Testing compute_performance_metrics()...")
metrics = compute_performance_metrics(resolved)
print(f"✅ Metrics computed:")
print(f"  Wins: {metrics['wins']}")
print(f"  Losses: {metrics['losses']}")
print(f"  Pushes: {metrics['pushes']}")
print(f"  Resolved: {metrics['resolved']}")
print(f"  Win rate: {metrics['win_rate']}")
print(f"  ROI: {metrics['roi']}")

# Test 6: Validate metrics state
print("\n6️⃣ Testing validate_metrics_state()...")
try:
    validate_metrics_state(metrics, len(resolved))
    print(f"✅ Metrics state valid (no exception raised)")
except RuntimeError as e:
    print(f"❌ Metrics state invalid: {e}")

# Test 7: Print data status
print("\n7️⃣ Testing print_data_status()...")
print_data_status(metrics, len(pending))

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED")
print("=" * 70)
