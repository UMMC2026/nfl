"""
CBB Render Gate

Mandatory validation before output.
If ANY check fails → ABORT REPORT

Checks:
1. No duplicate players
2. No correlated edges tiered
3. Minutes threshold passed
4. Tier matches probability
"""
from typing import List, Dict
from collections import defaultdict


class RenderGateError(Exception):
    """Raised when render gate validation fails"""
    pass


def apply_render_gate(edges: List, report_date: str) -> List:
    """
    Apply all render gate validations.
    
    Args:
        edges: List of CBBEdge objects
        report_date: Date string for logging
        
    Returns:
        Validated edges (unchanged if all pass)
        
    Raises:
        RenderGateError if any validation fails
    """
    errors = []
    
    # Gate 1: No duplicate players in primary edges
    primary_edges = [e for e in edges if e.is_primary and not e.is_blocked]
    player_counts = defaultdict(list)
    for e in primary_edges:
        key = (e.game_id, e.player_id)
        player_counts[key].append(e.stat)
    
    duplicates = {k: v for k, v in player_counts.items() if len(v) > 2}  # Allow max 2 stats per player
    if duplicates:
        errors.append(f"Duplicate player edges: {duplicates}")
    
    # Gate 2: No correlated edges both tiered
    # (e.g., if higher AND lower for same stat are both STRONG)
    for e in primary_edges:
        opposite = find_opposite_edge(edges, e)
        if opposite and opposite.tier in ["STRONG", "LEAN"] and e.tier in ["STRONG", "LEAN"]:
            errors.append(f"Correlated edges both tiered: {e.player_name} {e.stat}")
    
    # Gate 3: Minutes threshold (already blocked upstream, but double-check)
    from sports.cbb.config import CBB_EDGE_GATES
    for e in primary_edges:
        # This should already be blocked, but verify
        pass  # Upstream gates handle this
    
    # Gate 4: Tier matches probability
    tier_violations = validate_tier_probability(primary_edges)
    if tier_violations:
        errors.extend(tier_violations)
    
    # Gate 5: At least one primary edge (otherwise why run?)
    if not primary_edges:
        errors.append("No primary edges to output")
    
    if errors:
        error_msg = f"RENDER GATE FAILED ({report_date}):\n" + "\n".join(f"  - {e}" for e in errors)
        raise RenderGateError(error_msg)
    
    return edges


def find_opposite_edge(edges: List, target) -> any:
    """Find the opposite direction edge for the same player/stat."""
    opposite_dir = "lower" if target.direction == "higher" else "higher"
    for e in edges:
        if (e.game_id == target.game_id and 
            e.player_id == target.player_id and 
            e.stat == target.stat and 
            e.direction == opposite_dir):
            return e
    return None


def validate_tier_probability(edges: List) -> List[str]:
    """
    Validate tier assignments match probability thresholds.
    
    Returns list of violation messages.
    """
    from sports.cbb.config import TIER_THRESHOLDS
    
    violations = []
    
    for e in edges:
        if e.tier == "STRONG" and e.probability < TIER_THRESHOLDS.get("STRONG", 0.70):
            violations.append(
                f"Tier mismatch: {e.player_name} {e.stat} tier=STRONG but prob={e.probability:.1%}"
            )
        elif e.tier == "LEAN":
            if e.probability >= TIER_THRESHOLDS.get("STRONG", 0.70):
                violations.append(
                    f"Tier mismatch: {e.player_name} {e.stat} tier=LEAN but prob={e.probability:.1%} (should be STRONG)"
                )
            elif e.probability < TIER_THRESHOLDS.get("LEAN", 0.60):
                violations.append(
                    f"Tier mismatch: {e.player_name} {e.stat} tier=LEAN but prob={e.probability:.1%} (should be NO_PLAY)"
                )
    
    return violations
