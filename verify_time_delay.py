"""
Quick verification of time delay feature.
"""
from datetime import datetime, timedelta
from ufa.models.user import PlanTier
from ufa.signals.shaper import SignalShaper

print("\n" + "="*70)
print("SIGNAL TIME DELAY FEATURE VERIFICATION")
print("="*70)

# Test 1: Old signal (should not be delayed)
old_signal = {
    "player": "LeBron James",
    "stat": "points",
    "line": 24.5,
    "direction": "higher",
    "tier": "SLAM",
    "published_at": (datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z",
}

shaped_old = SignalShaper.shape(old_signal, PlanTier.FREE)
print("\n✓ Test 1: Old signal (30 min old)")
print(f"  delayed: {shaped_old.get('delayed')}")
assert shaped_old.get('delayed') == False, "Old signal should not be delayed"
print("  ✓ PASS")

# Test 2: Recent signal (should be delayed)
recent_signal = {
    "player": "LeBron James",
    "stat": "points",
    "line": 24.5,
    "direction": "higher",
    "tier": "SLAM",
    "published_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z",
}

shaped_recent = SignalShaper.shape(recent_signal, PlanTier.FREE)
print("\n✓ Test 2: Recent signal (5 min old)")
print(f"  delayed: {shaped_recent.get('delayed')}")
print(f"  delayed_until: {shaped_recent.get('delayed_until')}")
assert shaped_recent.get('delayed') == True, "Recent signal should be delayed"
assert shaped_recent.get('message'), "Should have upgrade message"
print("  ✓ PASS")

# Test 3: Paid tier never delayed
shaped_starter = SignalShaper.shape(recent_signal, PlanTier.STARTER)
print("\n✓ Test 3: Starter tier (recent signal, 5 min old)")
print(f"  delayed: {shaped_starter.get('delayed', 'N/A')}")
assert shaped_starter.get('delayed') == False or 'delayed' not in shaped_starter, "Paid tier should not be delayed"
assert shaped_starter.get('probability') is not None, "Starter should see probability"
print("  ✓ PASS")

# Test 4: Verify field hierarchy
print("\n✓ Test 4: Field visibility hierarchy")
free_fields = set(SignalShaper.shape(old_signal, PlanTier.FREE).keys())
starter_fields = set(SignalShaper.shape(old_signal, PlanTier.STARTER).keys())
pro_fields = set(SignalShaper.shape(old_signal, PlanTier.PRO).keys())
whale_fields = set(SignalShaper.shape(old_signal, PlanTier.WHALE).keys())

print(f"  FREE tier fields: {len(free_fields)} ({', '.join(sorted(free_fields)[:3])}...)")
print(f"  STARTER tier fields: {len(starter_fields)}")
print(f"  PRO tier fields: {len(pro_fields)}")
print(f"  WHALE tier fields: {len(whale_fields)}")

assert free_fields.issubset(starter_fields), "Free fields should be subset of Starter"
assert starter_fields.issubset(pro_fields), "Starter fields should be subset of Pro"
assert pro_fields.issubset(whale_fields), "Pro fields should be subset of Whale"
print("  ✓ PASS: Hierarchy correct (free ⊂ starter ⊂ pro ⊂ whale)")

print("\n" + "="*70)
print("✅ ALL VERIFICATION TESTS PASSED")
print("="*70)
print("\nTime delay feature is working correctly:")
print("  • Free tier: Recent signals (< 20 min) show as delayed with upgrade CTA")
print("  • Free tier: Old signals (≥ 20 min) shown without delay")
print("  • Paid tiers: Never delayed, show full probability & metrics")
print()
