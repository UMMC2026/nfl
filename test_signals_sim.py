#!/usr/bin/env python3
"""
Telegram bot mock/stub for testing signals without installing telegram-bot library.

This simulates the /signals command so you can test locally without the library.
"""
import json
from pathlib import Path
from datetime import date
from ufa.models.user import PlanTier
from ufa.services.telegram_shaper import (
    filter_and_shape_signals_for_telegram,
    format_signal_for_telegram,
)

def simulate_signals_command(user_tier=PlanTier.FREE):
    """
    Simulate what the bot sends when user types /signals.
    
    This is what you would see in Telegram chat.
    """
    print("\n" + "="*60)
    print(f"SIMULATING /signals COMMAND FOR {user_tier.value.upper()} TIER")
    print("="*60 + "\n")
    
    # Load signals
    signals_file = Path("output/signals_latest.json")
    if not signals_file.exists():
        print("❌ No signals_latest.json found")
        return
    
    with open(signals_file) as f:
        signals = json.load(f)
    
    print(f"Loaded {len(signals)} signals")
    
    # Filter and shape
    shaped_signals, total_available = filter_and_shape_signals_for_telegram(
        signals,
        user_tier,
        limit=5,  # Show first 5
    )
    
    print(f"After filtering for {user_tier.value}: {len(shaped_signals)} signals\n")
    
    if not shaped_signals:
        print("🔔 No signals available for your tier yet.")
        return
    
    # Simulate feature access
    show_prob = user_tier in [PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]
    show_notes = user_tier in [PlanTier.PRO, PlanTier.WHALE]
    
    # Send header
    header = f"🎯 **Today's Signals** ({len(shaped_signals)} of {total_available})\n"
    header += f"📅 {date.today().strftime('%B %d, %Y')}\n"
    header += "─" * 25
    print(header)
    print()
    
    # Send signals
    for i, shaped_signal in enumerate(shaped_signals, 1):
        msg = format_signal_for_telegram(
            shaped_signal,
            user_tier,
            show_probability=show_prob,
            show_notes=show_notes,
        )
        
        if msg:
            print(f"[Signal {i}]")
            print(msg)
            print()
        else:
            print(f"[Signal {i}] (Delayed - available soon)")
            print()
    
    # Footer
    remaining = f"∞" if user_tier == PlanTier.WHALE else f"{5 - len(shaped_signals)}"
    footer = f"📊 Signals remaining today: {remaining}"
    if user_tier == PlanTier.FREE:
        footer += "\n\n💡 Upgrade for more signals and detailed probabilities!"
    
    print(footer)
    print()

if __name__ == "__main__":
    # Test all tiers
    for tier in [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]:
        simulate_signals_command(tier)
        input("Press Enter to see next tier...\n")
