"""
Tier-based signal payload shaping.

Single source of truth for field visibility by subscription tier.
Deterministic, testable, composable.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from ufa.models.user import PlanTier


class SignalShaper:
    """Shape signal payloads based on subscription tier."""

    # Free tier delay (minutes) — creates urgency without blocking access
    FREE_TIER_DELAY_MINUTES = 20

    @staticmethod
    def should_delay_for_free_tier(signal: Dict[str, Any], published_at: Optional[datetime] = None) -> bool:
        """
        Check if signal should be delayed for free tier.
        
        Args:
            signal: The signal dict
            published_at: When the signal was published (defaults to 'published_at' field in signal)
        
        Returns:
            True if signal is too recent for free tier
        """
        if published_at is None:
            published_str = signal.get("published_at")
            if not published_str:
                return False  # No timestamp, no delay
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return False

        now = datetime.utcnow()
        age = now - published_at.replace(tzinfo=None)
        
        return age < timedelta(minutes=SignalShaper.FREE_TIER_DELAY_MINUTES)

    @staticmethod
    def shape(signal: Dict[str, Any], tier: PlanTier, published_at: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Return a signal payload shaped by subscription tier.

        FREE tier sees:
        - player, team, stat, line, direction, tier (pick confidence)
        - BUT: signals < 20 min old are hidden (delayed_until timestamp provided)

        STARTER tier sees:
        - Everything FREE has, PLUS:
        - probability (hit %), stability_score, edge

        PRO tier sees:
        - Everything STARTER has, PLUS:
        - notes, model recommendations

        WHALE tier sees:
        - Everything PRO has, PLUS:
        - Advanced metrics (EV, correlations, model internals)
        """
        # --- FREE TIER DELAY CHECK ---
        if tier == PlanTier.FREE and SignalShaper.should_delay_for_free_tier(signal, published_at):
            # Return a minimal payload indicating delay
            published_str = signal.get("published_at", "")
            try:
                published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                delayed_until = published + timedelta(minutes=SignalShaper.FREE_TIER_DELAY_MINUTES)
            except (ValueError, AttributeError):
                delayed_until = datetime.utcnow() + timedelta(minutes=SignalShaper.FREE_TIER_DELAY_MINUTES)
            
            return {
                "player": signal.get("player", ""),
                "stat": signal.get("stat", ""),
                "line": signal.get("line", 0.0),
                "direction": signal.get("direction", ""),
                "delayed": True,
                "delayed_until": delayed_until.isoformat() + "Z",
                "message": f"Upgrade to see signals within {SignalShaper.FREE_TIER_DELAY_MINUTES} minutes",
            }

        # --- BASE (ALWAYS VISIBLE for non-delayed) ---
        payload = {
            "player": signal.get("player", ""),
            "team": signal.get("team", ""),
            "stat": signal.get("stat", ""),
            "line": signal.get("line", 0.0),
            "direction": signal.get("direction", ""),
            "tier": signal.get("tier", ""),  # Pick confidence: SLAM, STRONG, WEAK
            "delayed": False,
        }

        if tier == PlanTier.FREE:
            return payload

        # --- STARTER+ (Probability & Edge) ---
        # Confidence capping: STARTER sees actual confidence (no cap), PRO/WHALE same
        payload.update({
            "probability": signal.get("probability") or signal.get("prob") or signal.get("p_hit"),
            "stability_score": signal.get("stability_score"),
            "stability_class": signal.get("stability_class"),
            "edge": signal.get("edge"),
        })

        if tier == PlanTier.STARTER:
            return payload

        # --- PRO+ (Analysis & Notes) ---
        payload.update({
            "ollama_notes": signal.get("ollama_notes"),
            "recent_avg": signal.get("recent_avg"),
            "recent_min": signal.get("recent_min"),
            "recent_max": signal.get("recent_max"),
        })

        if tier == PlanTier.PRO:
            return payload

        # --- WHALE (Full Internals) ---
        payload.update({
            "entry_ev_power_3leg": signal.get("entry_ev_power_3leg"),
            "entry_ev_power_4leg": signal.get("entry_ev_power_4leg"),
            "entry_ev_flex_4leg": signal.get("entry_ev_flex_4leg"),
            "correlation_risk": signal.get("correlation_risk"),
            "model_name": signal.get("model_name"),
            "model_version": signal.get("model_version"),
            "hit_rate_recent": signal.get("hit_rate_recent"),
            "confidence_interval": signal.get("confidence_interval"),
        })

        return payload

    @staticmethod
    def shape_list(signals: list[Dict[str, Any]], tier: PlanTier) -> list[Dict[str, Any]]:
        """Shape a list of signals for a tier."""
        return [SignalShaper.shape(signal, tier) for signal in signals]
