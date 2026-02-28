"""
Golf Pipeline Critical Fixes - Validation Test
================================================

Tests all 4 priority fixes:
1. Direction logic: Only generate LOWER edges for round_strokes when player < line
2. Deduplication: Remove duplicate (player, market, line, direction) edges
3. Sport context: Block edges flagged by AI as wrong sport
4. Matchup None handling: Handle missing line gracefully

Run: .venv\Scripts\python.exe golf/test_golf_fixes.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from golf.engines.generate_edges import (
    calculate_round_strokes_probability,
    calculate_matchup_probability,
    generate_edge_from_prop,
    generate_all_edges,
    GolfEdge,
)
from golf.validation.sport_context_gate import check_sport_context, apply_sport_context_gate


def test_priority_1_direction_logic():
    """Test: Direction logic only creates value edges."""
    print("\n" + "=" * 60)
    print("TEST 1: GOLF DIRECTION LOGIC FIX")
    print("=" * 60)
    
    # Test case: Scottie Scheffler avg 68.5, line 67.0
    # OLD BUG: Would create HIGHER edge (98% prob) — betting he shoots WORSE
    # NEW FIX: Should create LOWER edge (2% prob) — betting he shoots BETTER
    
    prop = {
        "player": "Scottie Scheffler",
        "tournament": "Genesis Invitational",
        "market": "round_strokes",
        "line": 67.0,
        "round": 2,
        "lower_mult": 0.85,
    }
    
    player_stats = {
        "avg": 68.5,
        "stddev": 2.5,
        "sg_total": 2.1,
        "sources": ["test"]
    }
    
    edges = generate_edge_from_prop(prop, player_stats)
    
    print(f"\nScenario: {prop['player']} avg {player_stats['avg']}, line {prop['line']}")
    print(f"Expected: LOWER edge only (player better than line)")
    print(f"Generated edges: {len(edges)}")
    
    for edge in edges:
        print(f"  - {edge.direction.upper()} @ {edge.probability:.1%} [{edge.tier}]")
    
    # Validation
    has_lower = any(e.direction == "lower" for e in edges)
    has_higher = any(e.direction == "higher" for e in edges)
    
    if has_lower and not has_higher:
        print("✅ PASS: Only LOWER edge created (correct direction)")
        return True
    elif has_higher:
        print("❌ FAIL: HIGHER edge created (inverted logic bug still present)")
        return False
    else:
        print("⚠️ WARN: No edges created (may be filtered out)")
        return False


def test_priority_2_deduplication():
    """Test: Deduplication removes duplicate props."""
    print("\n" + "=" * 60)
    print("TEST 2: DEDUPLICATION GATE")
    print("=" * 60)
    
    # Simulate duplicate props from multiple books
    duplicate_props = [
        {
            "player": "Si Woo Kim",
            "tournament": "Genesis",
            "market": "round_strokes",
            "line": 68.5,
            "lower_mult": 0.87,
        },
        {
            "player": "Si Woo Kim",  # DUPLICATE
            "tournament": "Genesis",
            "market": "round_strokes",
            "line": 68.5,
            "lower_mult": 0.88,  # Different book, slightly different odds
        },
        {
            "player": "Si Woo Kim",  # DUPLICATE
            "tournament": "Genesis",
            "market": "round_strokes",
            "line": 68.5,
            "lower_mult": 0.86,
        },
    ]
    
    player_db = {
        "Si Woo Kim": {
            "avg": 70.1,
            "stddev": 3.3,
            "sg_total": 0.8,
            "sources": ["test"]
        }
    }
    
    edges = generate_all_edges(duplicate_props, player_db)
    
    print(f"\nScenario: 3 duplicate props for Si Woo Kim round_strokes 68.5 LOWER")
    print(f"Expected: 1 edge after dedup")
    print(f"Generated edges: {len(edges)}")
    
    for edge in edges:
        print(f"  - {edge.player} {edge.market} {edge.line} {edge.direction.upper()} @ {edge.probability:.1%}")
    
    # Validation
    si_woo_edges = [e for e in edges if e.player == "Si Woo Kim" and e.market == "round_strokes" and e.line == 68.5]
    
    if len(si_woo_edges) == 1:
        print("✅ PASS: Duplicates removed (1 unique edge)")
        return True
    elif len(si_woo_edges) > 1:
        print(f"❌ FAIL: {len(si_woo_edges)} edges still present after dedup")
        return False
    else:
        print("⚠️ WARN: No edges created (may be filtered)")
        return False


def test_priority_3_sport_context():
    """Test: Sport context gate blocks mismatched edges."""
    print("\n" + "=" * 60)
    print("TEST 3: SPORT CONTEXT VALIDATION")
    print("=" * 60)
    
    test_cases = [
        {
            "edge": {
                "sport": "GOLF",
                "player": "Scottie Scheffler",
                "market": "round_strokes",
                "pick_state": "OPTIMIZABLE",
            },
            "commentary": "This line is mispriced given Scheffler's recent form.",
            "expected": True,
        },
        {
            "edge": {
                "sport": "GOLF",
                "player": "Scottie Scheffler",
                "market": "round_strokes",
                "pick_state": "OPTIMIZABLE",
            },
            "commentary": "This is not an NBA prop — Scottie Scheffler is a golfer, not a basketball player.",
            "expected": False,
        },
        {
            "edge": {
                "sport": "NBA",  # Wrong sport
                "player": "Rory McIlroy",
                "market": "points",
                "pick_state": "OPTIMIZABLE",
            },
            "commentary": None,
            "expected": False,
        },
    ]
    
    results = []
    for i, tc in enumerate(test_cases, 1):
        is_valid, reason = check_sport_context(tc["edge"], tc["commentary"])
        
        print(f"\nTest 3.{i}: {tc['edge']['player']} ({tc['edge']['sport']})")
        print(f"  Commentary: {tc['commentary'][:60] if tc['commentary'] else 'None'}...")
        print(f"  Expected: {tc['expected']}")
        print(f"  Result: {is_valid} (reason: {reason if not is_valid else 'N/A'})")
        
        if is_valid == tc["expected"]:
            print(f"  ✅ PASS")
            results.append(True)
        else:
            print(f"  ❌ FAIL: Expected {tc['expected']}, got {is_valid}")
            results.append(False)
    
    all_passed = all(results)
    print(f"\n{'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}: {sum(results)}/{len(results)}")
    return all_passed


def test_priority_4_matchup_none():
    """Test: Matchup probability handles None line."""
    print("\n" + "=" * 60)
    print("TEST 4: MATCHUP NONE HANDLING")
    print("=" * 60)
    
    prop_with_none_line = {
        "player": "Pierceson Coody",
        "opponent": "Si Woo Kim",
        "market": "matchup",
        "line": None,  # Missing line
    }
    
    player_stats = {"sg_total": 0.5}
    opponent_stats = {"sg_total": 0.8}
    
    print(f"\nScenario: Matchup with line=None")
    print(f"Expected: Default to 0.5, no crash")
    
    try:
        probs = calculate_matchup_probability(prop_with_none_line, player_stats, opponent_stats)
        print(f"Result: {probs}")
        
        if isinstance(probs, dict) and "higher" in probs:
            print("✅ PASS: None handled gracefully, no crash")
            return True
        else:
            print("❌ FAIL: Unexpected return format")
            return False
    except Exception as e:
        print(f"❌ FAIL: Crashed with {type(e).__name__}: {e}")
        return False


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "=" * 80)
    print("🏌️ GOLF PIPELINE CRITICAL FIXES — VALIDATION TEST SUITE")
    print("=" * 80)
    print("\nTesting fixes for 4 critical issues identified in audit:")
    print("  1. Inverted direction logic (betting golfers shoot WORSE)")
    print("  2. Duplicate picks (Si Woo Kim × 4)")
    print("  3. Sport context mismatch (AI flags wrong sport but picks go through)")
    print("  4. Matchup None crash (NoneType comparison error)")
    
    results = {
        "Direction Logic": test_priority_1_direction_logic(),
        "Deduplication": test_priority_2_deduplication(),
        "Sport Context": test_priority_3_sport_context(),
        "Matchup None": test_priority_4_matchup_none(),
    }
    
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:12} | {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED — Golf pipeline fixes validated")
        print("Safe to deploy to production")
    else:
        failed_count = sum(1 for p in results.values() if not p)
        print(f"❌ {failed_count}/{len(results)} TESTS FAILED")
        print("DO NOT DEPLOY until all tests pass")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    passed = run_all_tests()
    sys.exit(0 if passed else 1)
