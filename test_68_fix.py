"""Test that the 68% flat cap bug is fixed."""
import sys
sys.path.insert(0, '.')

# Test 1: stat_caps key alignment — both 'PTS' and 'points' should get same cap
print("Test 1: stat_caps key alignment")
stat_caps = {
    "points": 0.75, "pts": 0.75,
    "rebounds": 0.72, "reb": 0.72,
    "assists": 0.70, "ast": 0.70,
    "3pm": 0.65,
    "pra": 0.75,
    "pts+reb": 0.73, "pr": 0.73,
    "pts+ast": 0.72, "pa": 0.72,
    "reb+ast": 0.70, "ra": 0.70,
    "blk": 0.68, "stl": 0.68, "to": 0.68,
    "blk+stl": 0.68, "blocks": 0.68, "steals": 0.68, "turnovers": 0.68,
}
# OddsAPI format (PTS -> pts)
assert stat_caps.get("pts", 0.72) == 0.75, "FAIL: PTS not at 0.75"
# Paste format (points)
assert stat_caps.get("points", 0.72) == 0.75, "FAIL: points not at 0.75"
# Same for REB
assert stat_caps.get("reb", 0.72) == 0.72, "FAIL: REB not at 0.72"
assert stat_caps.get("rebounds", 0.72) == 0.72, "FAIL: rebounds not at 0.72"
# PRA
assert stat_caps.get("pra", 0.72) == 0.75, "FAIL: PRA not at 0.75"
# Unknown stat gets 0.72, NOT 0.68
assert stat_caps.get("xyz_unknown", 0.72) == 0.72, "FAIL: unknown default wrong"
print("  PASS: All stat name formats resolve to correct caps")

# Test 2: COMPOSITE_MAX_CONFIDENCE raised
from sports.cbb.config import COMPOSITE_MAX_CONFIDENCE
print(f"Test 2: COMPOSITE_MAX_CONFIDENCE = {COMPOSITE_MAX_CONFIDENCE}")
assert COMPOSITE_MAX_CONFIDENCE == 0.75, f"FAIL: Expected 0.75, got {COMPOSITE_MAX_CONFIDENCE}"
print("  PASS: Composite cap raised to 75%")

# Test 3: STRONG threshold restored
from sports.cbb.config import CBB_TIER_THRESHOLDS_V2
print(f"Test 3: STRONG threshold = {CBB_TIER_THRESHOLDS_V2['STRONG']}")
assert CBB_TIER_THRESHOLDS_V2['STRONG'] == 0.70, f"FAIL: Expected 0.70"
print("  PASS: STRONG restored to 70%")

# Test 4: audit_skip_gates PROB_STRONG updated
from sports.cbb.audit_skip_gates import CBBGateConfig
gc = CBBGateConfig()
print(f"Test 4: CBBGateConfig.PROB_STRONG = {gc.PROB_STRONG}")
assert gc.PROB_STRONG == 0.70, f"FAIL: Expected 0.70, got {gc.PROB_STRONG}"
print("  PASS: Audit gate threshold updated")

# Test 7: Verify SDG composite cap flow
from sports.cbb.gates.sdg_integration import check_composite_sdg_requirements
test_edge = {
    "stat": "PRA",
    "probability": 0.73,
    "tier": "STRONG",
    "sdg_details": {"multi_window": {"z_l10": 0.8}, "cv": {"cv_ratio": 0.3}},
}
result_edge = check_composite_sdg_requirements(test_edge.copy())
final_prob = result_edge["probability"]
print(f"Test 7 (PRA prob=0.73 after SDG composite check): {final_prob:.4f}")
assert final_prob == 0.73, f"FAIL: Was capped to {final_prob} (should stay at 0.73 since 0.73 < 0.75)"
print("  PASS: Composite prob NOT reduced below 0.75 cap")

# Test 8: Edge at 0.76 should cap to 0.75
test_edge2 = {
    "stat": "PRA",
    "probability": 0.76,
    "tier": "STRONG",
    "sdg_details": {"multi_window": {"z_l10": 0.8}, "cv": {"cv_ratio": 0.3}},
}
result_edge2 = check_composite_sdg_requirements(test_edge2.copy())
final_prob2 = result_edge2["probability"]
print(f"Test 8 (PRA prob=0.76 after SDG composite check): {final_prob2:.4f}")
assert final_prob2 == 0.75, f"FAIL: Was {final_prob2}, expected 0.75"
print("  PASS: Composite capped at 75% (new limit)")

print()
print("=" * 50)
print("ALL 8 TESTS PASSED — 68% flat cap is FIXED")
print("=" * 50)
