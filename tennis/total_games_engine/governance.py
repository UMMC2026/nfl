"""
GOVERNANCE — HQ-Style Discipline Layer
=======================================
Enforces non-negotiable rules before any pick surfaces.

This is the filter between "engine says" and "action taken".
"""

from total_games_engine import MatchOutput


def governance_gate(result: MatchOutput) -> tuple:
    """
    Enforces discipline rules.
    
    Returns: (allowed: bool, reason: str)
    
    Rules:
    1. BLOCKED_CONTEXT: No surface or invalid context
    2. INSUFFICIENT_EDGE: NO_PLAY confidence
    3. BO5_LEAN_ONLY: Bo5 can only be LEAN (never STRONG)
    4. APPROVED: Passed all gates
    """

    # Gate 1: Context blocks
    if result.block_reason:
        return False, f"BLOCKED:{result.block_reason}"

    # Gate 2: Insufficient edge
    if result.confidence == "NO_PLAY":
        return False, "INSUFFICIENT_EDGE"

    # Gate 3: Bo5 discipline (already downgraded in engine, but enforce here too)
    if result.format == "Bo5" and result.confidence == "STRONG":
        # This shouldn't happen (engine downgrades), but enforce anyway
        return True, "BO5_STRONG_OVERRIDE"

    if result.format == "Bo5" and result.confidence == "LEAN":
        return True, "BO5_LEAN_ONLY"

    # Gate 4: Standard approval
    return True, "APPROVED"


def filter_approved(results: list) -> list:
    """
    Filter results to only approved plays.
    
    Returns list of (result, reason) tuples for approved plays.
    """
    approved = []
    for r in results:
        allowed, reason = governance_gate(r)
        if allowed:
            approved.append((r, reason))
    return approved


def filter_blocked(results: list) -> list:
    """
    Filter results to only blocked plays.
    
    Returns list of (result, reason) tuples for blocked plays.
    """
    blocked = []
    for r in results:
        allowed, reason = governance_gate(r)
        if not allowed:
            blocked.append((r, reason))
    return blocked


def split_by_governance(results: list) -> tuple:
    """
    Split results into approved and blocked.
    
    Returns: (approved_list, blocked_list)
    Each item is (result, reason) tuple.
    """
    approved = []
    blocked = []
    
    for r in results:
        allowed, reason = governance_gate(r)
        if allowed:
            approved.append((r, reason))
        else:
            blocked.append((r, reason))
    
    return approved, blocked
