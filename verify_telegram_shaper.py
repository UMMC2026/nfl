#!/usr/bin/env python
"""Quick verify telegram_shaper.py imports and basic functionality."""

from datetime import datetime, timedelta
from ufa.models.user import PlanTier
from ufa.services.telegram_shaper import format_signal_for_telegram, format_visible_signal
from ufa.signals.shaper import SignalShaper

# Test 1: Module imports
print("✅ Imports successful")

# Test 2: FREE tier old signal
now = datetime.utcnow()
old_published = (now - timedelta(minutes=25)).isoformat() + "Z"

signal = {
    "player": "LeBron",
    "team": "LAL",
    "stat": "points",
    "line": 25.5,
    "direction": "higher",
    "tier": "SLAM",
    "confidence": "ELITE",
    "published_at": old_published,
}

msg = format_signal_for_telegram(signal, PlanTier.FREE, show_probability=False)
assert "LeBron" in msg
print("✅ FREE tier old signal visible")

# Test 3: SignalShaper confidence capping
shaped = SignalShaper.shape(signal, PlanTier.FREE)
assert shaped.get("confidence") == "STRONG", f"Expected STRONG, got {shaped.get('confidence')}"
print("✅ ELITE capped to STRONG for FREE tier")

# Test 4: STARTER tier sees probability
signal2 = {
    "player": "Mahomes",
    "team": "KC",
    "stat": "pass_yds",
    "line": 300,
    "direction": "higher",
    "tier": "SLAM",
    "confidence": "STRONG",
    "probability": 0.65,
    "published_at": old_published,
    "stability_score": 0.78,
    "stability_class": "HIGH",
}

msg2 = format_signal_for_telegram(signal2, PlanTier.STARTER, show_probability=True)
assert "Probability" in msg2
print("✅ STARTER tier includes probability")

# Test 5: FREE tier recent signal delayed
recent_published = (now - timedelta(minutes=5)).isoformat() + "Z"
signal3 = signal.copy()
signal3["published_at"] = recent_published

msg3 = format_signal_for_telegram(signal3, PlanTier.FREE)
assert msg3 is not None
assert "Delayed" in msg3 or "⏳" in msg3
print("✅ FREE tier recent signal is delayed")

print("\n" + "="*50)
print("✅ All telegram_shaper verification checks passed!")
print("="*50)
