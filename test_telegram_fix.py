import json
from pathlib import Path
from ufa.models.user import PlanTier
from ufa.signals.shaper import SignalShaper
from ufa.services.telegram_shaper import filter_and_shape_signals_for_telegram

# Load real signals
signals_file = Path("output/signals_latest.json")
with open(signals_file) as f:
    signals = json.load(f)

print(f"Loaded {len(signals)} signals from {signals_file}")
print(f"First signal keys: {list(signals[0].keys())}")
print(f"First signal has 'prob': {signals[0].get('prob')}")
print()

# Test FREE tier
print("Testing FREE tier:")
shaped, total = filter_and_shape_signals_for_telegram(signals, PlanTier.FREE)
print(f"  Signals returned: {len(shaped)} of {total}")
if shaped:
    sig = shaped[0]
    print(f"  Fields: {list(sig.keys())}")
    print(f"  Has probability? {'probability' in sig}")
    print(f"  Has ollama_notes? {'ollama_notes' in sig}")
    print(f"  Sample: player={sig.get('player')}, stat={sig.get('stat')}, line={sig.get('line')}")
print()

# Test STARTER tier
print("Testing STARTER tier:")
shaped, total = filter_and_shape_signals_for_telegram(signals, PlanTier.STARTER)
print(f"  Signals returned: {len(shaped)} of {total}")
if shaped:
    sig = shaped[0]
    print(f"  Fields: {list(sig.keys())}")
    print(f"  Has probability? {'probability' in sig}")
    print(f"  Probability value: {sig.get('probability')}")
    print(f"  Has ollama_notes? {'ollama_notes' in sig}")
print()

# Test with limit
print("Testing with limit=2:")
shaped, total = filter_and_shape_signals_for_telegram(signals, PlanTier.STARTER, limit=2)
print(f"  Signals returned: {len(shaped)} (should be 2)")
print(f"  Total available: {total}")

if all([len(shaped) > 0, 'probability' in shaped[0], shaped[0].get('probability')]):
    print("\n✅ FIX WORKING: Signals have correct fields!")
else:
    print("\n❌ Issue found - debugging needed")
