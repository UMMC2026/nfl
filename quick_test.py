from ufa.models.user import PlanTier
from ufa.services.telegram_shaper import filter_and_shape_signals_for_telegram

signals = [
    {"player": "Test", "team": "TST", "stat": "pts", "line": 10, "direction": "higher", "tier": "SLAM", "probability": 0.9, "ollama_notes": "Good"}
]

shaped, total = filter_and_shape_signals_for_telegram(signals, PlanTier.FREE)
print(f"FREE: {len(shaped)} signals, fields: {list(shaped[0].keys())}")
assert "probability" not in shaped[0], "Should not have probability for FREE"
assert "ollama_notes" not in shaped[0], "Should not have ollama_notes for FREE"
print("✅ PASS")
