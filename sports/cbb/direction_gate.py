"""
FUOOM DARK MATTER — CBB Direction Gate (Wired 2026-02-15)
===========================================================
CBB Direction Gate — Hard gate to prevent structural model bias

STATUS: 🔧 FIXED — Previously orphaned, now wired into pipeline
ROOT CAUSE: apply_cbb_gates() never imported/called this module
EFFECT: 75.9% UNDER bias passed through unchecked (threshold is 65%)

SOP v2.1 Section 6: Render Gate (Fail-Fast Rule)
Audit Reference: CBB Governance Failure Report, Finding #2

This is the HARD GATE version from FUOOM fix package.
If >65% picks are in same direction → ABORT PIPELINE (return [])
"""

import logging
from typing import List, Dict, Optional
from collections import Counter

logger = logging.getLogger(__name__)

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
    
    # Count directions (handle both 'higher'/'lower' and 'OVER'/'UNDER')
    directions = []
    for e in edges:
        direction = e.get('direction', '').upper()
        # Normalize to OVER/UNDER
        if direction in ('HIGHER', 'OVER'):
            directions.append('OVER')
        elif direction in ('LOWER', 'UNDER'):
            directions.append('UNDER')
    
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
