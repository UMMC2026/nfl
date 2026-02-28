"""
FUOOM DARK MATTER — sports/cbb/direction_gate_wiring.py
=======================================================
CBB DIRECTION GATE WIRING FIX

STATUS: 🚨 CRITICAL — This gate was ORPHANED. Never called in pipeline.
ROOT CAUSE: apply_cbb_gates() in cbb_main.py never imports or calls direction_gate.
EFFECT: 75.9% UNDER bias passed through unchecked (threshold is 65%).

This file provides:
1. The exact patch for cbb_main.py
2. A standalone test to verify the fix
3. CBB-specific experimental mode banner

APPLY THIS FIX TO: sports/cbb/cbb_main.py, function apply_cbb_gates()
(approximately line 1667-1860)

Audit Reference: CBB Governance Failure Report, Finding #2
SOP v2.1 Section 6: Render Gate (Fail-Fast Rule)

Author: FUOOM Engineering
Version: 1.0.0
Date: 2026-02-15
"""

import logging
from typing import List, Dict, Optional
from collections import Counter

logger = logging.getLogger(__name__)


# =============================================================================
# DIRECTION GATE (should already exist in direction_gate.py)
# =============================================================================
# This is the canonical implementation. If your existing direction_gate.py
# differs, replace it with this version.

DIRECTION_BIAS_THRESHOLD = 0.65  # Abort if >65% same direction
MIN_EDGES_FOR_BIAS_CHECK = 5     # Need at least 5 edges to check


def apply_direction_gate(edges: List[Dict], 
                          context: Optional[Dict] = None,
                          threshold: float = DIRECTION_BIAS_THRESHOLD) -> List[Dict]:
    """Direction bias gate — HARD GATE.
    
    If more than `threshold` (default 65%) of edges point in the same
    direction (OVER or UNDER), the pipeline ABORTS by returning [].
    
    This prevents structural model bias from producing systematically
    wrong picks (e.g., 75.9% UNDER in CBB).
    
    Args:
        edges: List of edge dictionaries
        context: Optional context dict (unused, for interface compatibility)
        threshold: Maximum allowed directional bias (default 0.65)
    
    Returns:
        Original edges if gate passes, [] if gate triggers (ABORT)
    """
    if len(edges) < MIN_EDGES_FOR_BIAS_CHECK:
        logger.info(f"Direction Gate: Only {len(edges)} edges — below minimum "
                    f"({MIN_EDGES_FOR_BIAS_CHECK}), skipping check")
        return edges
    
    # Count directions
    directions = [e.get('direction', '').upper() for e in edges if e.get('direction')]
    
    if not directions:
        logger.warning("Direction Gate: No direction data in edges")
        return edges
    
    counter = Counter(directions)
    total = len(directions)
    
    # Check each direction
    for direction, count in counter.items():
        pct = count / total
        if pct > threshold:
            logger.critical(
                f"⛔ DIRECTION GATE TRIGGERED: {count}/{total} ({pct:.1%}) are {direction} "
                f"(threshold: {threshold:.0%}). PIPELINE ABORTED."
            )
            print(f"\n{'='*60}")
            print(f"  ⛔ DIRECTION GATE — PIPELINE ABORTED")
            print(f"{'='*60}")
            print(f"  Bias: {pct:.1%} {direction} ({count} of {total} edges)")
            print(f"  Threshold: {threshold:.0%}")
            print(f"  Direction counts: {dict(counter)}")
            print(f"")
            print(f"  This indicates STRUCTURAL MODEL BIAS, not a real edge.")
            print(f"  Possible causes:")
            print(f"    - Lines are NOT systematically mispriced")
            print(f"    - Model projections are systematically too low/high")
            print(f"    - Game script / context layer missing")
            print(f"")
            print(f"  Action required:")
            print(f"    1. Check model calibration against historical outcomes")
            print(f"    2. Add game script context (win probability → minutes → usage)")
            print(f"    3. Verify line sources are current")
            print(f"{'='*60}\n")
            return []  # ABORT — empty list signals pipeline stop
    
    # Gate passed
    most_common = counter.most_common(1)[0]
    logger.info(
        f"Direction Gate PASSED: {dict(counter)} "
        f"(max bias: {most_common[1]/total:.1%} {most_common[0]})"
    )
    return edges


# =============================================================================
# WIRING PATCH — Apply to cbb_main.py
# =============================================================================
# 
# FIND THIS FUNCTION in sports/cbb/cbb_main.py (around line 1667):
#
#   def apply_cbb_gates(edges: List[Dict], context: Dict) -> List[Dict]:
#       print("\n[3/5] APPLY GATES")
#       print("-" * 40)
#       
#       # Currently only calls:
#       edges = roster_gate(edges)
#       edges = min_mpg_gate(edges)
#       edges = games_played_gate(edges)
#       edges = blowout_gate(edges)
#       edges = game_script_gate(edges)
#       
#       return edges
#
# REPLACE WITH:
#
#   def apply_cbb_gates(edges: List[Dict], context: Dict) -> List[Dict]:
#       print("\n[3/5] APPLY GATES")
#       print("-" * 40)
#       
#       # ═══════════════════════════════════════════════════════════
#       # DIRECTION GATE — MUST RUN FIRST (HARD GATE)
#       # SOP v2.1 Section 6 + CBB Governance Fix 2026-02-15
#       # ═══════════════════════════════════════════════════════════
#       from sports.cbb.direction_gate import apply_direction_gate
#       
#       edges = apply_direction_gate(edges, context=context)
#       if not edges:
#           logging.critical("Direction gate triggered: >65% same direction detected")
#           return []  # ABORT — do not proceed to other gates
#       
#       # Remaining gates (sequential)
#       edges = roster_gate(edges)
#       edges = min_mpg_gate(edges)
#       edges = games_played_gate(edges)
#       edges = blowout_gate(edges)
#       edges = game_script_gate(edges)
#       
#       return edges
#
# ═══════════════════════════════════════════════════════════════


# =============================================================================
# TIER ASSIGNMENT DEBUG
# =============================================================================
# CBB Governance Finding: 74% probability → assigned LEAN (should be STRONG)
# Hypothesis: SDG v2.1 penalties applied BEFORE tier assignment

def debug_tier_assignment(probability: float, stat_type: str, direction: str,
                           sdg_penalty: float = 0.0) -> Dict:
    """Debug tier assignment to find where mislabeling occurs.
    
    If SDG penalties reduce probability BEFORE tier assignment,
    the tier will be wrong. The correct order is:
    1. Calculate raw probability
    2. Assign tier from raw probability
    3. Apply SDG penalties for unit sizing (not tier assignment)
    
    Args:
        probability: Raw model probability
        stat_type: Stat type
        direction: Direction (OVER/UNDER)
        sdg_penalty: Any SDG penalty applied
    
    Returns:
        Debug dict showing what happened
    """
    from shared.config import assign_tier, TIER_THRESHOLDS
    
    # Correct tier (from raw probability)
    correct_tier = assign_tier(probability)
    
    # What happens if SDG penalty applied first (WRONG ORDER)
    penalized_prob = probability - sdg_penalty
    wrong_tier = assign_tier(penalized_prob)
    
    result = {
        'raw_probability': probability,
        'sdg_penalty': sdg_penalty,
        'penalized_probability': penalized_prob,
        'correct_tier': correct_tier,
        'tier_if_penalized_first': wrong_tier,
        'is_mislabeled': correct_tier != wrong_tier,
        'fix': 'Apply SDG penalty to unit sizing, NOT to tier assignment',
    }
    
    if result['is_mislabeled']:
        print(f"\n  ⚠️  TIER MISLABEL DETECTED:")
        print(f"     {stat_type} {direction}")
        print(f"     Raw prob: {probability:.3f} → should be {correct_tier}")
        print(f"     After SDG penalty ({sdg_penalty:.3f}): {penalized_prob:.3f} → assigned {wrong_tier}")
        print(f"     FIX: Tier assignment uses RAW probability. SDG penalty affects unit sizing only.\n")
    
    return result


# =============================================================================
# CBB EXPERIMENTAL MODE BANNER
# =============================================================================

CBB_EXPERIMENTAL_BANNER = """
╔════════════════════════════════════════════════════════════════╗
║  ⚠️  EXPERIMENTAL MODE — CBB Model Untested                   ║
║                                                                ║
║  Status: ZERO historical performance data in picks.csv         ║
║  Direction gate: Recently wired (was bypassed prior)           ║
║  Tier assignment: Under investigation (possible SDG bug)       ║
║                                                                ║
║  Constraints applied:                                          ║
║    • All CBB picks capped at 0.5 units                         ║
║    • No auto-betting — manual tracking only                    ║
║    • Tracking mode active for next 10 slates                   ║
║    • Results will be logged to picks.csv for calibration       ║
║                                                                ║
║  Exit criteria: 50+ resolved CBB picks with Brier < 0.20      ║
╚════════════════════════════════════════════════════════════════╝
"""


def apply_cbb_experimental_mode(edges: List[Dict]) -> List[Dict]:
    """Cap CBB picks and add experimental warnings.
    
    Until CBB has historical calibration data (minimum 50 resolved picks),
    all CBB outputs are capped and flagged.
    
    Args:
        edges: List of CBB edge dicts
    
    Returns:
        Modified edges with caps and warnings
    """
    print(CBB_EXPERIMENTAL_BANNER)
    
    for edge in edges:
        edge['unit_size'] = min(edge.get('unit_size', 0.5), 0.5)
        edge['experimental'] = True
        edge['warning'] = '⚠️ EXPERIMENTAL — No historical calibration'
        edge['max_unit_cap'] = 0.5
    
    return edges


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == '__main__':
    print("=== CBB Direction Gate Wiring Test ===\n")
    
    # Test 1: Biased slate (should ABORT)
    print("--- Test 1: 75.9% UNDER bias (should abort) ---")
    biased_edges = []
    for i in range(88):
        biased_edges.append({'player': f'Player_{i}', 'direction': 'UNDER', 'stat_type': 'points'})
    for i in range(28):
        biased_edges.append({'player': f'Player_{88+i}', 'direction': 'OVER', 'stat_type': 'points'})
    
    result = apply_direction_gate(biased_edges)
    assert result == [], f"Expected empty list (abort), got {len(result)} edges"
    print("  ✅ Correctly aborted (returned empty list)\n")
    
    # Test 2: Balanced slate (should pass)
    print("--- Test 2: Balanced slate (should pass) ---")
    balanced_edges = []
    for i in range(55):
        balanced_edges.append({'player': f'Player_{i}', 'direction': 'UNDER', 'stat_type': 'points'})
    for i in range(45):
        balanced_edges.append({'player': f'Player_{55+i}', 'direction': 'OVER', 'stat_type': 'points'})
    
    result = apply_direction_gate(balanced_edges)
    assert len(result) == 100, f"Expected 100 edges, got {len(result)}"
    print("  ✅ Correctly passed (returned all 100 edges)\n")
    
    # Test 3: Tier mislabel debug
    print("--- Test 3: Tier mislabel detection ---")
    debug = debug_tier_assignment(
        probability=0.74,
        stat_type='points',
        direction='UNDER',
        sdg_penalty=0.10  # This would reduce 0.74 → 0.64 → LEAN instead of STRONG
    )
    assert debug['is_mislabeled'] == True
    print(f"  ✅ Detected mislabel: {debug['correct_tier']} → {debug['tier_if_penalized_first']}\n")
    
    # Test 4: Experimental mode
    print("--- Test 4: Experimental mode caps ---")
    test_edges = [
        {'player': 'Test', 'unit_size': 2.0, 'direction': 'UNDER'},
        {'player': 'Test2', 'unit_size': 1.0, 'direction': 'OVER'},
    ]
    capped = apply_cbb_experimental_mode(test_edges)
    assert all(e['unit_size'] <= 0.5 for e in capped)
    assert all(e.get('experimental') == True for e in capped)
    print("  ✅ All unit sizes capped at 0.5, experimental flag set\n")
    
    print("✅ All CBB direction gate tests passed")
