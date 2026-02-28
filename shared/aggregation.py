"""
FUOOM DARK MATTER — Aggregation & Correlation
=============================================
Version: 2.0.0 | SOP v2.1 (Truth-Enforced)
Audit Reference: FUOOM-AUDIT-001, Section 10

This module provides aggregation logic for team/player edges,
correlation checks, and advanced market logic.
"""

from typing import List, Dict

# ═══════════════════════════════════════════════════════════════
# 1. TEAM AGGREGATION
# ═══════════════════════════════════════════════════════════════

def aggregate_team_projection(player_projections: List[float]) -> float:
    """Sum player projections to get team total."""
    return sum(player_projections)

# ═══════════════════════════════════════════════════════════════
# 2. PLAYER-TEAM CORRELATION
# ═══════════════════════════════════════════════════════════════

def check_player_team_correlation(player_edges: List[dict], team_edge: dict) -> Dict:
    """
    Check for correlation conflicts between player props and team total/total market.
    Returns dict with summary and any detected conflicts.
    """
    over_ct = sum(1 for pe in player_edges if pe.get("stat") in ("points", "pts") and pe.get("direction", "").upper() in ("OVER", "HIGHER"))
    under_ct = sum(1 for pe in player_edges if pe.get("stat") in ("points", "pts") and pe.get("direction", "").upper() in ("UNDER", "LOWER"))
    td = team_edge.get("direction", "").upper()
    conflicts = []
    if over_ct > under_ct + 2 and td in ("UNDER", "LOWER"):
        conflicts.append("PLAYER-TEAM CONFLICT: too many OVERs for team UNDER")
    if under_ct > over_ct + 2 and td in ("OVER", "HIGHER"):
        conflicts.append("PLAYER-TEAM CONFLICT: too many UNDERs for team OVER")
    return {"over": over_ct, "under": under_ct, "team_dir": td, "conflicts": conflicts}

# ═══════════════════════════════════════════════════════════════
# 3. ADVANCED MARKET LOGIC (PLACEHOLDER)
# ═══════════════════════════════════════════════════════════════

def advanced_market_logic(*args, **kwargs):
    """Placeholder for future advanced aggregation/market logic."""
    pass

# ═══════════════════════════════════════════════════════════════
# 4. SELF-TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("FUOOM aggregation.py — Self-Test")
    print("=" * 60)
    # Team aggregation
    team_total = aggregate_team_projection([12.5, 15.0, 8.0, 10.5])
    print(f"Team total: {team_total:.1f} (should be 46.0)")
    # Correlation check
    pes = [
        {"stat": "points", "direction": "OVER"},
        {"stat": "points", "direction": "OVER"},
        {"stat": "points", "direction": "OVER"},
        {"stat": "points", "direction": "UNDER"},
    ]
    te = {"direction": "UNDER"}
    result = check_player_team_correlation(pes, te)
    print(f"Correlation result: {result}")
    print("Self-test complete.")
