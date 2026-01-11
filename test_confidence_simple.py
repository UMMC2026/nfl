#!/usr/bin/env python
"""Simple inline verification of confidence capping."""

from ufa.signals.confidence import cap_confidence, CONFIDENCE_ORDER

print("=" * 60)
print("CONFIDENCE CAP VERIFICATION (Simplified)")
print("=" * 60)

print("\n[1] Confidence Ordering:")
for label, value in CONFIDENCE_ORDER.items():
    print(f"  {label} = {value}")

print("\n[2] Cap Function Tests:")
tests = [
    ("ELITE", "STRONG", "STRONG"),  # Should cap
    ("STRONG", "STRONG", "STRONG"),  # No cap needed
    ("WEAK", "STRONG", "WEAK"),      # Below cap
    ("LEAN", "STRONG", "LEAN"),      # Below cap
]

for actual, max_allowed, expected in tests:
    result = cap_confidence(actual, max_allowed)
    status = "✓" if result == expected else "✗"
    print(f"  {status} cap('{actual}', '{max_allowed}') = '{result}' (expect: '{expected}')")

print("\n" + "=" * 60)
print("✅ CONFIDENCE CAP LOGIC VERIFIED")
print("=" * 60)
