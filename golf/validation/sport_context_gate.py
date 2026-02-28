"""
Golf Sport Context Validation Gate
====================================

Prevents golf edges with invalid sport context from reaching output.
Detects when AI commentary flags sport mismatches (e.g., "This is not an NBA player").

Priority 3 fix from golf pipeline audit.
"""

from typing import Dict, Tuple, Optional
import re


# Known NBA/basketball keywords that should NOT appear in golf commentary
NBA_KEYWORDS = [
    r"not an nba",
    r"is a golfer, not",
    r"basketball player",
    r"matchup context is irrelevant",
    r"data error",
    r"mislabeled prop",
    r"incorrect sport",
]


def check_sport_context(
    edge: Dict,
    deepseek_commentary: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if edge has valid sport context.
    
    Args:
        edge: Edge dictionary
        deepseek_commentary: Optional AI commentary to scan for sport warnings
        
    Returns:
        (is_valid, reason_if_invalid)
        
    Examples:
        >>> check_sport_context({"sport": "GOLF", "player": "Scottie Scheffler"}, "This is not an NBA prop")
        (False, "Sport context mismatch detected in AI commentary")
        
        >>> check_sport_context({"sport": "GOLF"}, "This line is mispriced...")
        (True, None)
    """
    # Rule 1: Sport must be GOLF
    sport = edge.get("sport", "").upper()
    if sport != "GOLF":
        return False, f"Invalid sport: {sport} (expected GOLF)"
    
    # Rule 2: Scan AI commentary for sport mismatch warnings
    if deepseek_commentary:
        commentary_lower = deepseek_commentary.lower()
        for pattern in NBA_KEYWORDS:
            if re.search(pattern, commentary_lower):
                return False, f"Sport context mismatch detected: '{pattern}' found in commentary"
    
    return True, None


def apply_sport_context_gate(
    edge: Dict,
    deepseek_commentary: Optional[str] = None,
    block_invalid: bool = True
) -> Tuple[Dict, bool]:
    """
    Apply sport context gate to edge. If invalid, mark as VOID.
    
    Args:
        edge: Edge dictionary (will be modified if invalid)
        deepseek_commentary: Optional AI commentary
        block_invalid: If True, set pick_state=REJECTED. If False, just warn.
        
    Returns:
        (edge, passed_gate)
    """
    is_valid, reason = check_sport_context(edge, deepseek_commentary)
    
    if not is_valid:
        if block_invalid:
            edge["pick_state"] = "REJECTED"
            edge["avoid_reason"] = f"SPORT_CONTEXT_INVALID: {reason}"
            edge["tier"] = "AVOID"
            print(f"[SPORT CONTEXT GATE] BLOCKED: {edge.get('player', '?')} - {reason}")
        else:
            print(f"[SPORT CONTEXT GATE] WARNING: {edge.get('player', '?')} - {reason}")
        return edge, False
    
    return edge, True


if __name__ == "__main__":
    # Test cases
    test_edges = [
        {
            "sport": "GOLF",
            "player": "Scottie Scheffler",
            "market": "round_strokes",
            "pick_state": "OPTIMIZABLE",
        },
        {
            "sport": "NBA",
            "player": "Scottie Barnes",
            "market": "points",
            "pick_state": "OPTIMIZABLE",
        },
    ]
    
    test_commentary = [
        "This line is mispriced given Scheffler's recent form.",
        "This is not an NBA prop — Scottie Scheffler is a golfer, not a basketball player.",
    ]
    
    print("=" * 60)
    print("SPORT CONTEXT GATE TEST")
    print("=" * 60)
    
    for i, edge in enumerate(test_edges):
        commentary = test_commentary[i] if i < len(test_commentary) else None
        print(f"\nTest {i+1}: {edge.get('player', '?')} ({edge.get('sport', '?')})")
        print(f"Commentary: {commentary}")
        
        valid, reason = check_sport_context(edge, commentary)
        print(f"Result: {'✅ VALID' if valid else f'❌ INVALID - {reason}'}")
