"""
Telegram signal formatting with tier-based shaping and time delay.

Uses the same SignalShaper logic as the API to ensure consistency
across channels (API, Telegram, email, etc.).
"""

from typing import Optional
from datetime import datetime, timedelta
from ufa.signals.shaper import SignalShaper
from ufa.models.user import PlanTier


def format_signal_for_telegram(
    signal: dict,
    tier: PlanTier,
    show_probability: bool = True,
    show_notes: bool = False,
) -> Optional[str]:
    """
    Format a signal for Telegram using SignalShaper.

    Args:
        signal: Raw signal dict from signals_latest.json (or already-shaped signal)
        tier: User's subscription tier
        show_probability: Whether to include probability/edge/stability (from tier)
        show_notes: Whether to include ollama_notes (from tier)

    Returns:
        Formatted message string, or None if signal should be delayed
        (for FREE tier with recent signals)
    """
    # Check if signal is already shaped (has "delayed" field)
    # If not, apply tier-based shaping
    if "delayed" in signal and signal.get("delayed") is not None:
        # Already shaped
        shaped = signal
    else:
        # Raw signal - apply tier-based shaping
        shaped = SignalShaper.shape(signal, tier)

    # If signal is delayed for FREE tier, return delay message
    if shaped.get("delayed"):
        return format_delay_message(shaped)

    # Format normally (signal is visible)
    return format_visible_signal(shaped, show_probability, show_notes)


def format_delay_message(shaped: dict) -> str:
    """
    Format a delay message for signals not yet visible to FREE tier.

    Shows basic info + upgrade CTA + when signal becomes available.
    """
    delayed_until = shaped.get("delayed_until", "soon")
    player = shaped.get("player", "Unknown")
    stat = shaped.get("stat", "stat")
    line = shaped.get("line", "?")
    direction = shaped.get("direction", "")

    direction_text = "OVER" if direction == "higher" else "UNDER"

    lines = [
        "⏳ **Signal Delayed (Coming Soon)**",
        "",
        f"🏀 {player}",
        f"📊 {stat.replace('_', ' ').title()}",
        f"⏱️ {direction_text} {line}",
        "",
        "⚠️ *This signal is reserved for paid members.*",
        f"🕐 Available at: {delayed_until}",
        "",
        "💎 **Upgrade to STARTER** to see signals immediately!",
        f"👉 /upgrade",
    ]

    return "\n".join(lines)


def format_visible_signal(
    shaped: dict,
    show_probability: bool = True,
    show_notes: bool = False,
) -> str:
    """
    Format a visible (non-delayed) signal for Telegram.

    Args:
        shaped: Signal after tier-based shaping
        show_probability: Include prob/edge/stability (based on tier)
        show_notes: Include AI notes (based on tier)

    Returns:
        Formatted message string
    """
    tier = shaped.get("tier", "UNKNOWN")
    tier_emoji = {
        "SLAM": "🔥",
        "STRONG": "💪",
        "LEAN": "📊",
        "ELITE": "⭐",
        "WEAK": "❓",
    }.get(tier, "❓")

    direction = shaped.get("direction", "")
    direction_emoji = "📈" if direction == "higher" else "📉"
    direction_text = "OVER" if direction == "higher" else "UNDER"

    lines = [
        f"{tier_emoji} **{tier}** {tier_emoji}",
        "",
        f"🏀 {shaped.get('player', 'Unknown')}",
        f"📊 {shaped.get('stat', 'stat').replace('_', ' ').title()}",
        f"{direction_emoji} {direction_text} {shaped.get('line', 0)}",
        f"🎯 Team: {shaped.get('team', 'N/A')}",
    ]

    # Add probability section (STARTER+ only)
    if show_probability and shaped.get("probability") is not None:
        prob = shaped.get("probability", 0)
        edge = shaped.get("edge")
        stability = shaped.get("stability_score", 0)
        stability_class = shaped.get("stability_class", "N/A")

        prob_line = f"📈 Hit Probability: {prob:.1%}" if prob else "📈 Hit Probability: N/A"
        lines.append("")
        lines.append(prob_line)
        
        if edge is not None:
            lines.append(f"📐 Edge: {'+' if edge > 0 else ''}{edge:.1f}")
        
        if stability:
            lines.append(f"🔒 Stability: {stability:.2f} ({stability_class})")

    # Add notes section (PRO+ only)
    if show_notes and shaped.get("ollama_notes"):
        lines.extend(
            [
                "",
                "🤖 AI Analysis:",
                f"_{shaped['ollama_notes']}_",
            ]
        )

    return "\n".join(lines)


def format_signal_compact(shaped: dict) -> str:
    """
    Compact single-line format for Telegram list/summary views.

    Uses shaped signal data (tier-appropriate visibility).
    """
    tier = shaped.get("tier", "")
    tier_emoji = {"SLAM": "🔥", "STRONG": "💪", "LEAN": "📊", "ELITE": "⭐"}.get(
        tier, ""
    )

    direction = shaped.get("direction", "")
    direction_text = "O" if direction == "higher" else "U"

    prob = shaped.get("probability")
    prob_str = f" ({prob:.0%})" if prob else ""

    return (
        f"{tier_emoji} {shaped.get('player', '?')} {direction_text}{shaped.get('line', 0)} "
        f"{shaped.get('stat', '')}{prob_str}".strip()
    )


def filter_and_shape_signals_for_telegram(
    signals: list[dict],
    tier: PlanTier,
    limit: int = -1,
) -> tuple[list[dict], int]:
    """
    Filter and shape signals for Telegram display.

    Applies tier-based shaping (what fields are visible in each signal).
    Note: Signal availability is NOT filtered by subscription tier in Telegram.
    All users see all signals, but FREE users see limited field visibility.

    Args:
        signals: Raw signals from signals_latest.json
        tier: User's subscription tier
        limit: Max signals to return (-1 = unlimited)

    Returns:
        Tuple of (shaped_signals, total_available)
        where shaped_signals are ready for Telegram formatting
    """
    # Apply tier-based shaping to each signal (all signals visible to all users)
    # Only field visibility differs by tier, not signal availability
    shaped = [SignalShaper.shape(s, tier) for s in signals]
    
    # Apply limit
    if limit > 0:
        shaped = shaped[:limit]

    # Count total available (all signals)
    total_available = len(signals)

    return shaped, total_available


# For backward compatibility with existing Telegram code
def format_signal_legacy(
    signal: dict, show_probability: bool = True, show_notes: bool = False
) -> str:
    """
    Legacy format_signal function (no tier awareness).

    For compatibility with existing code that doesn't pass tier.
    Assumes WHALE tier (shows all fields).
    """
    shaped = SignalShaper.shape(signal, PlanTier.WHALE)
    return format_visible_signal(shaped, show_probability, show_notes)
