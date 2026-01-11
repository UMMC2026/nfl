"""
Tests for tier-based signal shaping.
Verify field visibility by subscription tier.
"""
import pytest
from datetime import datetime, timedelta
from ufa.models.user import PlanTier
from ufa.signals.shaper import SignalShaper


@pytest.fixture
def sample_signal():
    """Sample signal with all possible fields."""
    return {
        "player": "LeBron James",
        "team": "LAL",
        "stat": "points",
        "line": 24.5,
        "direction": "higher",
        "tier": "STRONG",
        "published_at": (datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z",
        # Starter+
        "probability": 0.68,
        "stability_score": 0.82,
        "stability_class": "MEDIUM",
        "edge": 0.12,
        # Pro+
        "ollama_notes": "Recent form suggests uptick; matchup favorable.",
        "recent_avg": 25.2,
        "recent_min": 18,
        "recent_max": 32,
        # Whale
        "entry_ev_power_3leg": 1.24,
        "entry_ev_power_4leg": 1.18,
        "entry_ev_flex_4leg": 1.31,
        "correlation_risk": "low",
        "model_name": "monte_carlo_v3",
        "model_version": "3.1.2",
        "hit_rate_recent": 0.71,
        "confidence_interval": (0.62, 0.78),
    }


class TestFreeUserPayload:
    """FREE tier sees only basic pick info."""

    def test_free_sees_only_basics(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.FREE)

        # Should have
        assert shaped["player"] == "LeBron James"
        assert shaped["stat"] == "points"
        assert shaped["line"] == 24.5
        assert shaped["direction"] == "higher"
        assert shaped["tier"] == "STRONG"
        assert shaped["delayed"] == False  # Signal is old enough

        # Should NOT have
        assert shaped.get("probability") is None
        assert shaped.get("stability_score") is None
        assert shaped.get("ollama_notes") is None
        assert shaped.get("entry_ev_power_3leg") is None

    def test_free_sees_delayed_recent_signal(self):
        """Recent signals (< 20 min) are hidden from free tier."""
        recent_signal = {
            "player": "Player",
            "team": "TEAM",
            "stat": "points",
            "line": 20.0,
            "direction": "higher",
            "tier": "SLAM",
            "published_at": datetime.utcnow().isoformat() + "Z",  # Just now
        }
        
        shaped = SignalShaper.shape(recent_signal, PlanTier.FREE)
        
        assert shaped["delayed"] == True
        assert "delayed_until" in shaped
        assert shaped.get("probability") is None
        assert shaped.get("player") == "Player"  # Still shows basic info
        assert "Upgrade to see signals" in shaped.get("message", "")

    def test_free_payload_minimal(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.FREE)
        keys = set(shaped.keys())
        
        expected_keys = {"player", "team", "stat", "line", "direction", "tier", "delayed"}
        assert keys == expected_keys, f"Unexpected keys: {keys - expected_keys}"


class TestStarterUserPayload:
    """STARTER tier sees probability + edge."""

    def test_starter_sees_probability(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.STARTER)

        # Starter includes Free fields
        assert shaped["player"] == "LeBron James"
        
        # Starter includes probability
        assert shaped["probability"] == 0.68
        assert shaped["stability_score"] == 0.82
        assert shaped["stability_class"] == "MEDIUM"
        assert shaped["edge"] == 0.12

        # But NOT advanced
        assert shaped.get("ollama_notes") is None
        assert shaped.get("entry_ev_power_3leg") is None

    def test_starter_payload_keys(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.STARTER)
        keys = set(shaped.keys())
        
        expected = {
            "player", "team", "stat", "line", "direction", "tier", "delayed",
            "probability", "stability_score", "stability_class", "edge",
        }
        assert keys == expected


class TestProUserPayload:
    """PRO tier sees analysis + notes."""

    def test_pro_sees_notes(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.PRO)

        # Pro includes everything Starter has
        assert shaped["probability"] == 0.68
        
        # Pro includes analysis
        assert shaped["ollama_notes"] == "Recent form suggests uptick; matchup favorable."
        assert shaped["recent_avg"] == 25.2
        assert shaped["recent_min"] == 18
        assert shaped["recent_max"] == 32

        # But NOT whale metrics
        assert shaped.get("entry_ev_power_3leg") is None
        assert shaped.get("model_name") is None

    def test_pro_payload_keys(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.PRO)
        keys = set(shaped.keys())
        
        expected = {
            "player", "team", "stat", "line", "direction", "tier", "delayed",
            "probability", "stability_score", "stability_class", "edge",
            "ollama_notes", "recent_avg", "recent_min", "recent_max",
        }
        assert keys == expected


class TestWhaleUserPayload:
    """WHALE tier sees full internals."""

    def test_whale_sees_all(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.WHALE)

        # Whale includes everything
        assert shaped["probability"] == 0.68
        assert shaped["ollama_notes"] == "Recent form suggests uptick; matchup favorable."
        assert shaped["entry_ev_power_3leg"] == 1.24
        assert shaped["model_name"] == "monte_carlo_v3"
        assert shaped["hit_rate_recent"] == 0.71

    def test_whale_payload_keys(self, sample_signal):
        shaped = SignalShaper.shape(sample_signal, PlanTier.WHALE)
        keys = set(shaped.keys())
        
        expected = {
            "player", "team", "stat", "line", "direction", "tier", "delayed",
            "probability", "stability_score", "stability_class", "edge",
            "ollama_notes", "recent_avg", "recent_min", "recent_max",
            "entry_ev_power_3leg", "entry_ev_power_4leg", "entry_ev_flex_4leg",
            "correlation_risk", "model_name", "model_version",
            "hit_rate_recent", "confidence_interval",
        }
        assert keys == expected


class TestShapeList:
    """Test batch shaping."""

    def test_shape_multiple_signals(self, sample_signal):
        signals = [sample_signal, sample_signal]
        
        shaped = SignalShaper.shape_list(signals, PlanTier.STARTER)
        
        assert len(shaped) == 2
        assert all("probability" in s for s in shaped)
        assert all("entry_ev_power_3leg" not in s for s in shaped)


class TestFreeUserTimeDelay:
    """Test the time delay feature for free tier."""

    def test_old_signal_not_delayed(self):
        """Signals older than 20 min are shown to free tier."""
        old_signal = {
            "player": "Player",
            "team": "TEAM",
            "stat": "points",
            "line": 20.0,
            "direction": "higher",
            "tier": "SLAM",
            "published_at": (datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z",
        }
        
        shaped = SignalShaper.shape(old_signal, PlanTier.FREE)
        
        assert shaped["delayed"] == False
        assert "delayed_until" not in shaped
        assert shaped["player"] == "Player"
        assert shaped.get("probability") is None

    def test_recent_signal_delayed(self):
        """Signals less than 20 min old are delayed for free tier."""
        recent_signal = {
            "player": "Player",
            "team": "TEAM",
            "stat": "points",
            "line": 20.0,
            "direction": "higher",
            "tier": "SLAM",
            "published_at": datetime.utcnow().isoformat() + "Z",
        }
        
        shaped = SignalShaper.shape(recent_signal, PlanTier.FREE)
        
        assert shaped["delayed"] == True
        assert "delayed_until" in shaped
        assert "Upgrade" in shaped.get("message", "")
        assert shaped["player"] == "Player"  # Still shows basic info

    def test_delay_threshold(self):
        """Signal exactly at 20 min boundary transitions from delayed to not."""
        threshold_signal = {
            "player": "Player",
            "stat": "points",
            "line": 20.0,
            "direction": "higher",
            "published_at": (datetime.utcnow() - timedelta(minutes=20, seconds=1)).isoformat() + "Z",
        }
        
        shaped = SignalShaper.shape(threshold_signal, PlanTier.FREE)
        assert shaped["delayed"] == False

    def test_paid_tiers_never_delayed(self):
        """Paid tiers (Starter, Pro, Whale) are never delayed."""
        recent_signal = {
            "player": "Player",
            "stat": "points",
            "line": 20.0,
            "direction": "higher",
            "published_at": datetime.utcnow().isoformat() + "Z",
        }
        
        for tier in [PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]:
            shaped = SignalShaper.shape(recent_signal, tier)
            assert shaped.get("delayed") == False or "delayed" not in shaped, f"Tier {tier} should never be delayed"
            assert "delayed_until" not in shaped


class TestMissingFields:
    """Test graceful handling of missing fields."""

    def test_missing_probability(self):
        signal = {
            "player": "Player",
            "stat": "points",
            "line": 20.0,
            "direction": "higher",
        }
        
        shaped = SignalShaper.shape(signal, PlanTier.STARTER)
        
        assert shaped["probability"] is None
        assert shaped["player"] == "Player"

    def test_all_optional_fields_none(self):
        signal = {
            "player": "Player",
            "team": "TEAM",
            "stat": "points",
            "line": 20.0,
            "direction": "higher",
            "tier": "SLAM",
        }
        
        shaped = SignalShaper.shape(signal, PlanTier.WHALE)
        
        # All optional fields should be None
        assert shaped["probability"] is None
        assert shaped["entry_ev_power_3leg"] is None
        # But base fields should be present
        assert shaped["player"] == "Player"


class TestTierHierarchy:
    """Verify that higher tiers include all lower tier fields."""

    def test_free_subset_of_starter(self, sample_signal):
        free = set(SignalShaper.shape(sample_signal, PlanTier.FREE).keys())
        starter = set(SignalShaper.shape(sample_signal, PlanTier.STARTER).keys())
        
        assert free.issubset(starter), f"Free not subset of Starter: {free - starter}"

    def test_starter_subset_of_pro(self, sample_signal):
        starter = set(SignalShaper.shape(sample_signal, PlanTier.STARTER).keys())
        pro = set(SignalShaper.shape(sample_signal, PlanTier.PRO).keys())
        
        assert starter.issubset(pro), f"Starter not subset of Pro: {starter - pro}"

    def test_pro_subset_of_whale(self, sample_signal):
        pro = set(SignalShaper.shape(sample_signal, PlanTier.PRO).keys())
        whale = set(SignalShaper.shape(sample_signal, PlanTier.WHALE).keys())
        
        assert pro.issubset(whale), f"Pro not subset of Whale: {pro - whale}"

    def test_full_hierarchy(self, sample_signal):
        free = SignalShaper.shape(sample_signal, PlanTier.FREE)
        starter = SignalShaper.shape(sample_signal, PlanTier.STARTER)
        pro = SignalShaper.shape(sample_signal, PlanTier.PRO)
        whale = SignalShaper.shape(sample_signal, PlanTier.WHALE)
        
        free_keys = set(free.keys())
        starter_keys = set(starter.keys())
        pro_keys = set(pro.keys())
        whale_keys = set(whale.keys())
        
        # Each tier adds new keys
        assert len(free_keys) < len(starter_keys) < len(pro_keys) < len(whale_keys)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
