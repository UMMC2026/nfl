"""
Test telegram_shaper.py integration with SignalShaper.

Verifies:
1. format_signal_for_telegram applies tier-based shaping
2. FREE tier signals see delay message for recent signals
3. Paid tiers see full payloads immediately
4. Confidence capping is applied correctly
5. Compact format respects tier visibility
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from ufa.models.user import PlanTier
from ufa.services.telegram_shaper import (
    format_signal_for_telegram,
    format_delay_message,
    format_visible_signal,
    format_signal_compact,
    filter_and_shape_signals_for_telegram,
)
from ufa.signals.shaper import SignalShaper


def test_free_tier_recent_signal_delayed():
    """FREE tier should see delay message for signals < 20 minutes old."""
    # Signal published 5 minutes ago
    now = datetime.utcnow()
    published_at = (now - timedelta(minutes=5)).isoformat() + "Z"
    
    signal = {
        "player": "LeBron James",
        "team": "LAL",
        "stat": "points",
        "line": 25.5,
        "direction": "higher",
        "tier": "SLAM",
        "published_at": published_at,
        "probability": 0.65,
        "edge": 2.5,
        "confidence": "ELITE",  # Will be capped to STRONG for FREE
    }
    
    msg = format_signal_for_telegram(signal, PlanTier.FREE)
    
    # Should show delay message
    assert msg is not None
    assert "Signal Delayed" in msg or "⏳" in msg
    assert "Available at" in msg or "Upgrade" in msg
    print("✅ FREE tier recent signal is delayed")


def test_free_tier_old_signal_visible():
    """FREE tier should see signal if > 20 minutes old."""
    # Signal published 25 minutes ago
    now = datetime.utcnow()
    published_at = (now - timedelta(minutes=25)).isoformat() + "Z"
    
    signal = {
        "player": "LeBron James",
        "team": "LAL",
        "stat": "points",
        "line": 25.5,
        "direction": "higher",
        "tier": "SLAM",
        "published_at": published_at,
        "probability": 0.65,
        "edge": 2.5,
        "confidence": "ELITE",
    }
    
    msg = format_signal_for_telegram(signal, PlanTier.FREE, show_probability=False)
    
    # Should show visible signal (not delay message)
    assert msg is not None
    assert "LeBron James" in msg
    assert "SLAM" in msg or "🔥" in msg
    assert "points" in msg.lower()
    # Should NOT show probability (FREE tier)
    assert "Probability" not in msg
    print("✅ FREE tier old signal is visible without probability")


def test_starter_tier_immediate():
    """STARTER tier should see signals immediately (no delay)."""
    # Signal published 5 minutes ago
    now = datetime.utcnow()
    published_at = (now - timedelta(minutes=5)).isoformat() + "Z"
    
    signal = {
        "player": "LeBron James",
        "team": "LAL",
        "stat": "points",
        "line": 25.5,
        "direction": "higher",
        "tier": "SLAM",
        "published_at": published_at,
        "probability": 0.65,
        "edge": 2.5,
        "confidence": "ELITE",
        "stability_score": 0.78,
        "stability_class": "HIGH",
    }
    
    msg = format_signal_for_telegram(signal, PlanTier.STARTER, show_probability=True)
    
    # Should show full signal with probability
    assert msg is not None
    assert "LeBron James" in msg
    assert "Probability" in msg
    assert "65.0%" in msg
    assert "Signal Delayed" not in msg
    print("✅ STARTER tier sees recent signal immediately with probability")


def test_pro_tier_includes_notes():
    """PRO tier should include AI notes if show_notes=True."""
    signal = {
        "player": "Lamar Jackson",
        "team": "BAL",
        "stat": "pass_yds",
        "line": 250,
        "direction": "higher",
        "tier": "STRONG",
        "published_at": datetime.utcnow().isoformat() + "Z",
        "probability": 0.60,
        "confidence": "STRONG",
        "ollama_notes": "Good matchup vs worst pass defense",
        "recent_avg": 265,
        "recent_min": 210,
        "recent_max": 310,
    }
    
    msg = format_signal_for_telegram(signal, PlanTier.PRO, show_notes=True)
    
    assert msg is not None
    assert "AI Analysis" in msg or "🤖" in msg
    assert "Good matchup" in msg
    print("✅ PRO tier includes AI notes")


def test_confidence_capping_free_to_strong():
    """ELITE confidence should be capped to STRONG for FREE tier."""
    signal = {
        "player": "Patrick Mahomes",
        "team": "KC",
        "stat": "pass_yds",
        "line": 300,
        "direction": "higher",
        "tier": "SLAM",
        "confidence": "ELITE",  # Should be capped
        "published_at": (datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z",
        "probability": 0.72,
    }
    
    shaped = SignalShaper.shape(signal, PlanTier.FREE)
    
    # Confidence should be capped to STRONG
    assert shaped.get("confidence") == "STRONG"
    print("✅ ELITE confidence capped to STRONG for FREE tier")


def test_whale_tier_all_fields():
    """WHALE tier should see all fields including model_version, hit_rate."""
    signal = {
        "player": "Mahomes",
        "team": "KC",
        "stat": "pass_yds",
        "line": 300,
        "direction": "higher",
        "tier": "SLAM",
        "confidence": "ELITE",
        "probability": 0.72,
        "model_name": "monte_carlo_v3",
        "model_version": "3.2.1",
        "hit_rate": 0.645,
        "correlation_risk": 0.15,
        "entry_ev_2": 1.25,
        "entry_ev_3": 0.95,
        "published_at": datetime.utcnow().isoformat() + "Z",
    }
    
    shaped = SignalShaper.shape(signal, PlanTier.WHALE)
    
    # Should have all fields
    assert "model_version" in shaped
    assert shaped.get("model_version") == "3.2.1"
    assert "hit_rate" in shaped
    assert shaped.get("hit_rate") == 0.645
    print("✅ WHALE tier sees all fields including model_version and hit_rate")


def test_filter_and_shape_signals():
    """Test batch filtering and shaping for Telegram display."""
    now = datetime.utcnow()
    old_published = (now - timedelta(minutes=25)).isoformat() + "Z"
    recent_published = (now - timedelta(minutes=5)).isoformat() + "Z"
    
    signals = [
        {
            "player": "LeBron",
            "team": "LAL",
            "stat": "points",
            "line": 25.5,
            "direction": "higher",
            "tier": "SLAM",
            "confidence": "ELITE",
            "published_at": old_published,
        },
        {
            "player": "Mahomes",
            "team": "KC",
            "stat": "pass_yds",
            "line": 300,
            "direction": "higher",
            "tier": "STRONG",
            "confidence": "STRONG",
            "published_at": recent_published,
        },
        {
            "player": "Josh Allen",
            "team": "BUF",
            "stat": "rushing_yds",
            "line": 50,
            "direction": "higher",
            "tier": "LEAN",
            "confidence": "LEAN",
            "published_at": old_published,
        },
    ]
    
    # FREE tier: only sees SLAM signals (and old ones)
    shaped, total = filter_and_shape_signals_for_telegram(signals, PlanTier.FREE, limit=5)
    
    # FREE can see the old SLAM signal
    assert len(shaped) == 1
    assert shaped[0]["player"] == "LeBron"
    assert total == 3  # Total available is all 3
    print("✅ FREE tier filtered to SLAM signals only")
    
    # STARTER tier: sees SLAM and STRONG
    shaped, total = filter_and_shape_signals_for_telegram(signals, PlanTier.STARTER, limit=5)
    assert len(shaped) == 2  # SLAM (old) + STRONG (recent, delayed)
    assert total == 3
    print("✅ STARTER tier sees SLAM and STRONG (with delays applied)")
    
    # PRO tier: sees all
    shaped, total = filter_and_shape_signals_for_telegram(signals, PlanTier.PRO, limit=5)
    assert len(shaped) == 3
    assert total == 3
    print("✅ PRO tier sees all signals")


def test_compact_format():
    """Test compact Telegram list format."""
    signal = {
        "player": "LeBron James",
        "team": "LAL",
        "stat": "points",
        "line": 25.5,
        "direction": "higher",
        "tier": "SLAM",
        "probability": 0.65,
    }
    
    shaped = SignalShaper.shape(signal, PlanTier.STARTER)
    msg = format_signal_compact(shaped)
    
    assert "LeBron James" in msg
    assert "O" in msg  # OVER
    assert "25.5" in msg
    assert "65%" in msg
    print("✅ Compact format shows all required fields")


def test_format_delay_message():
    """Test delay message formatting."""
    now = datetime.utcnow()
    published_at = (now - timedelta(minutes=5)).isoformat() + "Z"
    delayed_until = (now + timedelta(minutes=15)).isoformat() + "Z"
    
    shaped = {
        "player": "LeBron James",
        "stat": "points",
        "line": 25.5,
        "direction": "higher",
        "delayed": True,
        "delayed_until": delayed_until,
    }
    
    msg = format_delay_message(shaped)
    
    assert "⏳" in msg
    assert "Delayed" in msg
    assert "Upgrade" in msg or "STARTER" in msg
    assert "Available at" in msg
    print("✅ Delay message includes CTA and availability time")


if __name__ == "__main__":
    print("\n🧪 Testing Telegram Shaper Integration\n")
    print("=" * 50)
    
    test_free_tier_recent_signal_delayed()
    test_free_tier_old_signal_visible()
    test_starter_tier_immediate()
    test_pro_tier_includes_notes()
    test_confidence_capping_free_to_strong()
    test_whale_tier_all_fields()
    test_filter_and_shape_signals()
    test_compact_format()
    test_format_delay_message()
    
    print("\n" + "=" * 50)
    print("✅ All Telegram shaper tests passed!\n")
