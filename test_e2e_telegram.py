import json
from pathlib import Path
from ufa.models.user import PlanTier
from ufa.services.telegram_shaper import (
    filter_and_shape_signals_for_telegram,
    format_signal_for_telegram,
)

# Load real signals
with open("output/signals_latest.json") as f:
    signals = json.load(f)

print(f"✅ Loaded {len(signals)} signals")
print()

# Test END-TO-END for FREE tier
print("=" * 50)
print("TEST: FREE Tier (/signals command)")
print("=" * 50)

shaped_signals, total = filter_and_shape_signals_for_telegram(signals, PlanTier.FREE, limit=2)
print(f"Shaped signals: {len(shaped_signals)} of {total}")

if shaped_signals:
    sig1 = shaped_signals[0]
    print(f"\nFirst signal after shaping:")
    print(f"  Keys: {list(sig1.keys())}")
    print(f"  Player: {sig1.get('player')}")
    print(f"  Has probability? {'probability' in sig1}")
    
    # Now format it for Telegram (should NOT re-shape)
    msg = format_signal_for_telegram(sig1, PlanTier.FREE, show_probability=False, show_notes=False)
    print(f"\nFormatted message:\n{msg}")
    
    if msg and "Unknown" not in msg:
        print("\n✅ WORKS: Signal formatted correctly for FREE tier")
    else:
        print("\n❌ ISSUE: Message is empty or invalid")
else:
    print("❌ No shaped signals!")

print("\n" + "=" * 50)
print("TEST: STARTER Tier with probability")
print("=" * 50)

shaped_signals, total = filter_and_shape_signals_for_telegram(signals, PlanTier.STARTER, limit=1)

if shaped_signals:
    sig = shaped_signals[0]
    print(f"Has probability in shaped signal? {'probability' in sig}")
    print(f"Probability value: {sig.get('probability')}")
    
    msg = format_signal_for_telegram(sig, PlanTier.STARTER, show_probability=True, show_notes=False)
    
    if "Hit Probability" in msg:
        print(f"✅ Probability shown in message")
    else:
        print(f"⚠️ Probability NOT in message:\n{msg}")
