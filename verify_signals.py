#!/usr/bin/env python3
"""
Complete signals pipeline diagnostic.
Run this to verify everything works end-to-end.
"""
import json
from pathlib import Path
from datetime import date
from ufa.models.user import PlanTier
from ufa.signals.shaper import SignalShaper
from ufa.services.telegram_shaper import (
    filter_and_shape_signals_for_telegram,
    format_signal_for_telegram,
)

def test_signals_pipeline():
    """Run complete diagnostic."""
    print("\n" + "="*70)
    print("SIGNALS PIPELINE DIAGNOSTIC")
    print("="*70 + "\n")
    
    # TEST 1: Load signals
    print("[1] LOADING SIGNALS")
    print("-" * 70)
    
    signals_file = Path("output/signals_latest.json")
    if not signals_file.exists():
        print("❌ FAIL: signals_latest.json not found")
        return False
    
    with open(signals_file) as f:
        signals = json.load(f)
    
    print(f"✅ Loaded {len(signals)} signals")
    
    if not signals:
        print("❌ FAIL: No signals in file")
        return False
    
    # Check signal structure
    sig = signals[0]
    required_fields = ["player", "team", "stat", "line", "direction", "prob"]
    missing = [f for f in required_fields if f not in sig]
    
    if missing:
        print(f"❌ FAIL: Missing fields: {missing}")
        return False
    
    print(f"✅ Signal structure valid")
    print(f"   Sample: {sig['player']} - {sig['stat']} {sig['line']} ({sig['prob']:.1%})\n")
    
    # TEST 2: Shaping for each tier
    print("[2] TIER-BASED SHAPING")
    print("-" * 70)
    
    results = {}
    for tier in [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]:
        try:
            shaped = SignalShaper.shape(signals[0], tier)
            results[tier.value] = shaped
            
            # Check what fields are visible
            has_prob = "probability" in shaped and shaped["probability"] is not None
            has_notes = "ollama_notes" in shaped and shaped["ollama_notes"] is not None
            
            print(f"{tier.value.upper():8} - ", end="")
            fields = []
            if "player" in shaped:
                fields.append("player")
            if has_prob:
                fields.append("probability")
            if has_notes:
                fields.append("ollama_notes")
            print(f"Fields: {', '.join(fields)}")
            
            # Validate tier rules
            if tier == PlanTier.FREE:
                if has_prob:
                    print(f"  ❌ FREE should not have probability!")
                    return False
                if has_notes:
                    print(f"  ❌ FREE should not have ollama_notes!")
                    return False
                print(f"  ✅ Correct visibility")
            elif tier == PlanTier.STARTER:
                if not has_prob:
                    print(f"  ❌ STARTER should have probability!")
                    return False
                if has_notes:
                    print(f"  ❌ STARTER should not have ollama_notes!")
                    return False
                print(f"  ✅ Correct visibility")
            elif tier == PlanTier.PRO:
                if not has_prob:
                    print(f"  ❌ PRO should have probability!")
                    return False
                if not has_notes:
                    print(f"  ⚠️  PRO should have ollama_notes (if available)")
                print(f"  ✅ Correct visibility")
            else:  # WHALE
                if not has_prob:
                    print(f"  ❌ WHALE should have probability!")
                    return False
                print(f"  ✅ Correct visibility")
        
        except Exception as e:
            print(f"❌ FAIL for {tier.value}: {e}")
            return False
    
    print()
    
    # TEST 3: Filter and shape for telegram
    print("[3] TELEGRAM FILTERING & SHAPING")
    print("-" * 70)
    
    for tier in [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]:
        try:
            shaped, total = filter_and_shape_signals_for_telegram(signals, tier, limit=3)
            print(f"{tier.value.upper():8} - {len(shaped)} signals returned (total: {total})")
            
            if len(shaped) == 0 and len(signals) > 0:
                print(f"  ❌ WARN: No signals returned despite {len(signals)} available")
            else:
                print(f"  ✅ Signals available")
        
        except Exception as e:
            print(f"❌ FAIL for {tier.value}: {e}")
            return False
    
    print()
    
    # TEST 4: Format for telegram
    print("[4] TELEGRAM FORMATTING")
    print("-" * 70)
    
    for tier in [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]:
        try:
            shaped, _ = filter_and_shape_signals_for_telegram(signals, tier, limit=1)
            
            if not shaped:
                print(f"{tier.value.upper():8} - No signals to format")
                continue
            
            show_prob = tier in [PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]
            show_notes = tier in [PlanTier.PRO, PlanTier.WHALE]
            
            msg = format_signal_for_telegram(shaped[0], tier, show_prob, show_notes)
            
            if not msg:
                print(f"❌ FAIL for {tier.value}: No message returned")
                return False
            
            print(f"{tier.value.upper():8} - Message generated ({len(msg)} chars)")
            
            # Validate message content
            if "Unknown" in msg and msg.count("Unknown") > 1:
                print(f"  ⚠️  Message contains multiple 'Unknown' fields")
            else:
                print(f"  ✅ Message valid")
                
                # Show preview
                preview = msg.split('\n')[0:3]
                for line in preview:
                    print(f"        {line[:60]}...")
        
        except Exception as e:
            print(f"❌ FAIL for {tier.value}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print()
    
    # TEST 5: Full simulation
    print("[5] FULL SIMULATION (/signals command)")
    print("-" * 70)
    
    try:
        tier = PlanTier.FREE
        shaped_signals, total_available = filter_and_shape_signals_for_telegram(
            signals, tier, limit=2
        )
        
        if not shaped_signals:
            print("❌ FAIL: No signals for simulation")
            return False
        
        # Build the message like the bot would
        messages = []
        
        header = f"🎯 **Today's Signals** ({len(shaped_signals)} of {total_available})\n"
        header += f"📅 {date.today().strftime('%B %d, %Y')}\n"
        header += "─" * 25
        messages.append(header)
        
        for sig in shaped_signals:
            msg = format_signal_for_telegram(sig, tier, show_probability=False)
            if msg:
                messages.append(msg)
        
        messages.append("📊 Signals remaining today: 3")
        
        full_output = "\n\n".join(messages)
        
        print(f"Preview of what user would see:")
        print(f"\n{full_output}\n")
        print(f"✅ Full message generated successfully ({len(full_output)} chars)")
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    print("="*70)
    print("✅ ALL TESTS PASSED - SIGNALS PIPELINE IS WORKING")
    print("="*70)
    print("\n🚀 Next steps:")
    print("   1. Install python-telegram-bot: pip install python-telegram-bot")
    print("   2. Run the bot: python start_bot.py")
    print("   3. Type /signals in Telegram chat")
    print()
    
    return True

if __name__ == "__main__":
    import sys
    success = test_signals_pipeline()
    sys.exit(0 if success else 1)
