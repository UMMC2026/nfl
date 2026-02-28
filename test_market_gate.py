"""Quick test of market alignment gate with user's PHI vs NYK examples"""
from market_alignment_gate import check_market_alignment

print("=== MARKET ALIGNMENT GATE TESTS ===\n")

# Test 1: Tyrese Maxey AST OVER 6.5 (should BLOCK - 12.6% divergence)
print("[1] Tyrese Maxey AST OVER 6.5 (threshold=10%)")
print("    Model: 55.8% | Market: 1.09 HIGHER, 0.83 LOWER")
passes, msg, details = check_market_alignment(
    model_prob=55.8,
    direction="OVER",
    multiplier_higher=1.09,
    multiplier_lower=0.83,
    threshold_pct=10.0  # More conservative than 15%
)
print(f"    Result: {msg}")
print(f"    Market prob: {details['market_prob']:.1f}%")
print(f"    Divergence: {details['divergence']:.1f}%")
print(f"    Passes: {passes}")
print()

# Test 2: Paul George AST OVER 3.5 (should PASS - aligned)
print("[2] Paul George AST OVER 3.5")
print("    Model: 57.9% | Market: 1.60 HIGHER, 2.50 LOWER")
passes, msg, details = check_market_alignment(
    model_prob=57.9,
    direction="OVER",
    multiplier_higher=1.60,
    multiplier_lower=2.50,
    threshold_pct=15.0
)
print(f"    Result: {msg}")
print(f"    Market prob: {details['market_prob']:.1f}%")
print(f"    Divergence: {details['divergence']:.1f}%")
print(f"    Passes: {passes}")
print()

# Test 3: No market data (should PASS with warning)
print("[3] Unknown player (no market data)")
passes, msg, details = check_market_alignment(
    model_prob=65.0,
    direction="UNDER",
    multiplier_higher=None,
    multiplier_lower=None,
    threshold_pct=15.0
)
print(f"    Result: {msg}")
print(f"    Passes: {passes}")
print()

print("=== TESTS COMPLETE ===")
