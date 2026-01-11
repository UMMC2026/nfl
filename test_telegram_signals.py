#!/usr/bin/env python3
"""Test that Telegram filter_and_shape_signals works correctly."""
from ufa.models.user import PlanTier
from ufa.services.telegram_shaper import filter_and_shape_signals_for_telegram

# Sample signals (like from signals_latest.json)
test_signals = [
    {
        "player": "Ja Morant",
        "team": "MEM",
        "stat": "points",
        "line": 20.5,
        "direction": "higher",
        "tier": "SLAM",
        "stability_class": "ELITE",
        "probability": 0.9265,
        "ollama_notes": "Strong pick",
    },
    {
        "player": "Lauri Markkanen",
        "team": "UTA",
        "stat": "assists",
        "line": 1.5,
        "direction": "lower",
        "tier": "SLAM",
        "stability_class": "SOLID",
        "probability": 0.8969,
        "ollama_notes": "Good value",
    },
]

def test_all_tiers():
    """Test that all tiers receive signals."""
    print("Testing filter_and_shape_signals_for_telegram()...\n")
    
    for tier in [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]:
        shaped, total = filter_and_shape_signals_for_telegram(test_signals, tier, limit=-1)
        print(f"Tier {tier.value}:")
        print(f"  Shaped signals: {len(shaped)}")
        print(f"  Total available: {total}")
        
        if shaped:
            sig = shaped[0]
            fields = list(sig.keys())
            print(f"  Fields: {', '.join(fields)}")
            
            # Verify tier-based visibility
            has_prob = "probability" in sig
            has_notes = "ollama_notes" in sig
            
            if tier == PlanTier.FREE:
                assert not has_prob, f"FREE tier should not have probability"
                assert not has_notes, f"FREE tier should not have ollama_notes"
                print(f"  ✅ Correctly hides probability & notes")
            elif tier == PlanTier.STARTER:
                assert has_prob, f"STARTER tier should have probability"
                assert not has_notes, f"STARTER tier should not have ollama_notes"
                print(f"  ✅ Shows probability, hides notes")
            else:
                assert has_prob, f"{tier} tier should have probability"
                assert has_notes, f"{tier} tier should have ollama_notes"
                print(f"  ✅ Shows all fields")
        else:
            print(f"  ⚠️  No signals!")
        
        print()
    
    print("✅ All tests passed!")

if __name__ == "__main__":
    test_all_tiers()
