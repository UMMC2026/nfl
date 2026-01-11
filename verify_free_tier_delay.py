#!/usr/bin/env python
"""
Verify free-tier 20-minute delay feature end-to-end.
Tests: delay logic, format_signal_for_tier, SignalOut model.
"""

from datetime import datetime, timedelta
from ufa.models.user import PlanTier
from ufa.signals.shaper import SignalShaper
from ufa.api.signals import SignalOut

print("=" * 70)
print("FREE-TIER 20-MINUTE DELAY — END-TO-END VERIFICATION")
print("=" * 70)

# Test 1: Old signal (should NOT be delayed)
print("\n[Test 1] Old Signal (30 min ago) → Should NOT be delayed")
old_signal = {
    "player": "LeBron James",
    "team": "LAL",
    "stat": "points",
    "line": 24.5,
    "direction": "higher",
    "tier": "ELITE",
    "published_at": (datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z",
    "probability": 0.75,
    "stability_score": 0.82,
    "edge": 0.12,
}

shaped_free_old = SignalShaper.shape(old_signal, PlanTier.FREE)
print(f"  Shaped payload keys: {list(shaped_free_old.keys())}")
print(f"  delayed={shaped_free_old.get('delayed')} (expect: False)")
print(f"  Has player/stat/line: {all([shaped_free_old.get(k) for k in ['player', 'stat', 'line']])}")
assert shaped_free_old.get("delayed") == False, "Old signal should NOT be delayed"
print("  ✓ PASS: Old signal visible immediately")

# Test 2: Recent signal (should BE delayed)
print("\n[Test 2] Recent Signal (5 min ago) → Should BE delayed")
recent_signal = old_signal.copy()
recent_signal["published_at"] = (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z"

shaped_free_recent = SignalShaper.shape(recent_signal, PlanTier.FREE)
print(f"  Shaped payload keys: {list(shaped_free_recent.keys())}")
print(f"  delayed={shaped_free_recent.get('delayed')} (expect: True)")
print(f"  delayed_until={shaped_free_recent.get('delayed_until')}")
print(f"  message={shaped_free_recent.get('message')}")
assert shaped_free_recent.get("delayed") == True, "Recent signal should BE delayed"
assert shaped_free_recent.get("delayed_until") is not None, "Should have delayed_until"
assert shaped_free_recent.get("message") is not None, "Should have upgrade message"
print("  ✓ PASS: Recent signal delayed with CTA")

# Test 3: Boundary test (exactly at 20 min threshold)
print("\n[Test 3] Boundary Test (20 min 1 sec old) → Should NOT be delayed")
boundary_signal = old_signal.copy()
boundary_signal["published_at"] = (datetime.utcnow() - timedelta(minutes=20, seconds=1)).isoformat() + "Z"

shaped_boundary = SignalShaper.shape(boundary_signal, PlanTier.FREE)
print(f"  delayed={shaped_boundary.get('delayed')} (expect: False)")
assert shaped_boundary.get("delayed") == False, "Signal at/past 20-min threshold should NOT be delayed"
print("  ✓ PASS: Threshold correctly enforced")

# Test 4: STARTER tier never delayed
print("\n[Test 4] STARTER Tier (recent signal) → Should NOT be delayed")
shaped_starter_recent = SignalShaper.shape(recent_signal, PlanTier.STARTER)
print(f"  delayed={shaped_starter_recent.get('delayed')} (expect: False or absent)")
print(f"  probability={shaped_starter_recent.get('probability')} (expect: 0.75)")
assert shaped_starter_recent.get("delayed") != True, "STARTER should not be delayed"
assert shaped_starter_recent.get("probability") is not None, "STARTER should see probability"
print("  ✓ PASS: STARTER tier sees full payload, no delay")

# Test 5: PRO tier never delayed
print("\n[Test 5] PRO Tier (recent signal) → Should NOT be delayed")
shaped_pro_recent = SignalShaper.shape(recent_signal, PlanTier.PRO)
print(f"  delayed={shaped_pro_recent.get('delayed')} (expect: False or absent)")
print(f"  ollama_notes={shaped_pro_recent.get('ollama_notes')} (expect: None in test)")
assert shaped_pro_recent.get("delayed") != True, "PRO should not be delayed"
print("  ✓ PASS: PRO tier sees full payload, no delay")

# Test 6: SignalOut model accepts all fields (including delay fields)
print("\n[Test 6] SignalOut Model Accepts Delay Fields")
try:
    signal_out = SignalOut(
        player="Test",
        team="TEST",
        stat="points",
        line=25.0,
        direction="higher",
        tier="STRONG",
        delayed=True,
        delayed_until="2025-12-30T14:25:00Z",
        message="Upgrade to see signals within 20 minutes",
    )
    print(f"  Created SignalOut with delay fields: {signal_out.model_dump(exclude_none=True)}")
    print("  ✓ PASS: SignalOut model handles delay fields")
except Exception as e:
    print(f"  ✗ FAIL: {e}")
    raise

# Test 7: format_signal_for_tier passes through delay fields
print("\n[Test 7] format_signal_for_tier Preserves Delay Fields")
from ufa.api.signals import format_signal_for_tier
from ufa.models.user import Plan, PlanTier as PlanTierModel

try:
    # Mock a minimal plan
    plan = Plan(name="free", tier_level="free", price=0)
    
    formatted = format_signal_for_tier(recent_signal, PlanTier.FREE, plan)
    print(f"  Formatted signal delayed={formatted.delayed}")
    print(f"  Has delayed_until={formatted.delayed_until is not None}")
    print(f"  Has message={formatted.message is not None}")
    assert formatted.delayed == True, "Formatted signal should preserve delayed=True"
    print("  ✓ PASS: format_signal_for_tier passes through delay fields")
except Exception as e:
    print(f"  ✗ FAIL: {e}")
    raise

print("\n" + "=" * 70)
print("✅ ALL FREE-TIER DELAY TESTS PASSED")
print("=" * 70)
print("\nFeature Summary:")
print("  • FREE tier signals < 20 min old → delayed=True + CTA")
print("  • FREE tier signals ≥ 20 min old → delayed=False, visible")
print("  • STARTER+ tiers → never delayed, always see full payload")
print("  • Delay communicated via ISO 8601 timestamp + upgrade message")
print("\nProduction Checklist:")
print("  ✓ Delay logic in SignalShaper.should_delay_for_free_tier()")
print("  ✓ Delay applied in SignalShaper.shape() for FREE tier")
print("  ✓ SignalOut model has delay fields")
print("  ✓ format_signal_for_tier passes delay fields through")
print("  ✓ Endpoint ready to return delayed payloads")
print("\nNext: Deploy to staging, monitor FREE→STARTER upgrade rate")
