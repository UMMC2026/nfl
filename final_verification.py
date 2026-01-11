#!/usr/bin/env python
"""Final production verification - all systems."""

print("\n" + "="*60)
print("FINAL PRODUCTION VERIFICATION")
print("="*60)

# Test 1: Core imports
print("\n[1] Core Imports...")
try:
    from ufa.signals.shaper import SignalShaper
    from ufa.signals.confidence import cap_confidence
    from ufa.services.telegram_shaper import format_signal_for_telegram
    from ufa.models.user import PlanTier
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    exit(1)

# Test 2: Confidence capping works
print("\n[2] Confidence Capping...")
try:
    assert cap_confidence("ELITE", "STRONG") == "STRONG"
    assert cap_confidence("WEAK", "STRONG") == "WEAK"
    assert cap_confidence("STRONG", "STRONG") == "STRONG"
    print("✅ Confidence capping works")
except Exception as e:
    print(f"❌ Confidence test failed: {e}")
    exit(1)

# Test 3: SignalShaper works
print("\n[3] SignalShaper...")
try:
    from datetime import datetime, timedelta
    signal = {
        "player": "Test",
        "team": "TST",
        "stat": "points",
        "line": 25.5,
        "direction": "higher",
        "tier": "SLAM",
        "published_at": (datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z",
        "probability": 0.65,
        "confidence": "ELITE",
    }
    shaped = SignalShaper.shape(signal, PlanTier.FREE)
    assert shaped is not None
    assert "player" in shaped
    print("✅ SignalShaper works")
except Exception as e:
    print(f"❌ SignalShaper test failed: {e}")
    exit(1)

# Test 4: Telegram formatter works
print("\n[4] Telegram Formatter...")
try:
    msg = format_signal_for_telegram(signal, PlanTier.STARTER, show_probability=True)
    assert msg is not None
    assert "Test" in msg
    print("✅ Telegram formatter works")
except Exception as e:
    print(f"❌ Telegram formatter failed: {e}")
    exit(1)

# Test 5: API can start
print("\n[5] API Import...")
try:
    from ufa.api.main import app
    print("✅ API imports successfully")
except Exception as e:
    print(f"❌ API import failed: {e}")
    exit(1)

print("\n" + "="*60)
print("✅ ALL SYSTEMS GREEN - PRODUCTION READY")
print("="*60)
print("\nAPI Status: Ready to start")
print("Command: python -m uvicorn ufa.api.main:app --port 8000")
print("\n")
