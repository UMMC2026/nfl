"""
Parlay Auto-Blocking Logic (UI + Backend Flags)
================================================
ENFORCEMENT LAYER A — Prevents accidental correlation, rare-event stacking,
and NO PLAY leakage into parlays.

NO MATH CHANGES — This is enforcement + visibility only.

Auto-Block Rules (non-negotiable):
- ❌ Same correlated_group
- ❌ Any risk_tags includes rare_event
- ❌ Any confidence_tier = NO_PLAY
- ❌ More than 1 prop per player (default)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Project imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.correlation import market_family


class BlockReason(Enum):
    """Reason why edge is blocked from parlays."""
    NONE = "ALLOWED"
    CORRELATED_GROUP = "CORRELATED_GROUP"
    RARE_EVENT = "RARE_EVENT"
    NO_PLAY = "NO_PLAY"
    MULTI_PROP_SAME_PLAYER = "MULTI_PROP_SAME_PLAYER"
    COMPOSITE_STAT = "COMPOSITE_STAT"
    HIGH_CORRELATION = "HIGH_CORRELATION"


@dataclass
class ParlayEligibility:
    """Parlay eligibility determination for an edge."""
    allowed: bool
    reason: BlockReason = BlockReason.NONE
    details: Optional[str] = None
    conflicting_edge_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason.value,
            "details": self.details,
            "conflicting_edge_ids": self.conflicting_edge_ids
        }


# =============================================================================
# RISK TAG DETECTION
# =============================================================================

RARE_EVENT_TAGS = {
    "rare_event",
    "triple_double",
    "double_double",
    "low_sample",
    "extreme_outcome",
    "binary_outcome",
}

COMPOSITE_STAT_TAGS = {
    "composite_stat",
    "pra",
    "pts_reb",
    "pts_ast",
    "reb_ast",
    "stl_blk",
}

NO_PLAY_TIERS = {
    "NO_PLAY",
    "NO PLAY",
    "AVOID",
    "REJECTED",
}


def _has_rare_event(risk_tags: List[str]) -> bool:
    """Check if any risk tag indicates a rare event."""
    if not risk_tags:
        return False
    return any(tag.lower() in RARE_EVENT_TAGS for tag in risk_tags)


def _has_composite_stat(risk_tags: List[str]) -> bool:
    """Check if edge involves composite stat (PRA, etc.)."""
    if not risk_tags:
        return False
    return any(tag.lower() in COMPOSITE_STAT_TAGS for tag in risk_tags)


def _is_no_play(tier: str) -> bool:
    """Check if tier is NO_PLAY variant."""
    if not tier:
        return False
    return tier.upper() in NO_PLAY_TIERS


# =============================================================================
# CORRELATION DETECTION
# =============================================================================

def detect_correlation_groups(edges: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group edges by player+market_family for correlation detection.
    
    Returns dict: {group_id: [edges]}
    """
    groups = {}
    
    for edge in edges:
        player = edge.get("player", edge.get("entity", "")).lower().strip()
        stat = edge.get("stat", edge.get("market", "")).lower()
        
        if not player:
            continue
        
        # Primary grouping by player
        player_key = f"player:{player}"
        if player_key not in groups:
            groups[player_key] = []
        groups[player_key].append(edge)
        
        # Secondary grouping by player+family
        family = market_family(stat)
        family_key = f"family:{player}:{family}"
        if family_key not in groups:
            groups[family_key] = []
        groups[family_key].append(edge)
        
        # Check for explicit correlated_group in risk data
        risk = edge.get("risk", {})
        explicit_group = risk.get("correlated_group")
        if explicit_group:
            group_key = f"explicit:{explicit_group}"
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(edge)
    
    return groups


# =============================================================================
# SINGLE EDGE ELIGIBILITY
# =============================================================================

def evaluate_edge_eligibility(edge: Dict) -> ParlayEligibility:
    """
    Evaluate if a single edge is eligible for parlays.
    This checks edge-intrinsic properties only.
    
    Returns ParlayEligibility with allowed=False if:
    - Tier is NO_PLAY/AVOID
    - Risk tags include rare_event
    """
    # Check tier first
    tier = edge.get("tier", edge.get("confidence_tier", ""))
    if _is_no_play(tier):
        return ParlayEligibility(
            allowed=False,
            reason=BlockReason.NO_PLAY,
            details=f"Edge tier is {tier} — not eligible for parlays"
        )
    
    # Check risk tags
    risk = edge.get("risk", {})
    risk_tags = risk.get("risk_tags", edge.get("risk_tags", []))
    
    if _has_rare_event(risk_tags):
        return ParlayEligibility(
            allowed=False,
            reason=BlockReason.RARE_EVENT,
            details=f"Edge involves rare event: {risk_tags}"
        )
    
    # Check composite stat (still allowed, but flagged)
    if _has_composite_stat(risk_tags):
        return ParlayEligibility(
            allowed=True,  # Allowed but with warning
            reason=BlockReason.COMPOSITE_STAT,
            details="Composite stat — careful with stacking core stats"
        )
    
    return ParlayEligibility(allowed=True)


# =============================================================================
# PARLAY COMBINATION ELIGIBILITY
# =============================================================================

def evaluate_parlay_combination(
    edges: List[Dict],
    max_per_player: int = 1,
    allow_same_family: bool = False
) -> Tuple[bool, List[str]]:
    """
    Evaluate if a combination of edges can form a valid parlay.
    
    Returns (is_valid, list_of_blocking_reasons)
    """
    blocking_reasons = []
    
    # Check each edge individually first
    for edge in edges:
        eligibility = evaluate_edge_eligibility(edge)
        if not eligibility.allowed and eligibility.reason in {
            BlockReason.NO_PLAY, BlockReason.RARE_EVENT
        }:
            player = edge.get("player", edge.get("entity", "Unknown"))
            stat = edge.get("stat", edge.get("market", ""))
            blocking_reasons.append(
                f"{player} {stat}: {eligibility.reason.value}"
            )
    
    if blocking_reasons:
        return False, blocking_reasons
    
    # Check player limits
    player_counts = {}
    for edge in edges:
        player = edge.get("player", edge.get("entity", "")).lower().strip()
        if not player:
            continue
        player_counts[player] = player_counts.get(player, 0) + 1
    
    for player, count in player_counts.items():
        if count > max_per_player:
            blocking_reasons.append(
                f"Player {player}: {count} props exceeds limit of {max_per_player}"
            )
    
    if blocking_reasons:
        return False, blocking_reasons
    
    # Check market family correlation
    if not allow_same_family:
        family_sets = {}
        for edge in edges:
            player = edge.get("player", edge.get("entity", "")).lower().strip()
            stat = edge.get("stat", edge.get("market", ""))
            family = market_family(stat)
            
            key = (player, family)
            if key in family_sets and family != stat.lower():
                # Same player, same family, different stats
                blocking_reasons.append(
                    f"Correlated: {player} has multiple {family} stats"
                )
            family_sets[key] = edge
    
    # Check explicit correlation groups
    explicit_groups = {}
    for edge in edges:
        risk = edge.get("risk", {})
        group = risk.get("correlated_group")
        if group:
            if group in explicit_groups:
                blocking_reasons.append(
                    f"Explicit correlation group: {group}"
                )
            explicit_groups[group] = edge
    
    return len(blocking_reasons) == 0, blocking_reasons


# =============================================================================
# ENRICH EDGES WITH PARLAY DATA
# =============================================================================

def enrich_edges_with_parlay_data(edges: List[Dict]) -> List[Dict]:
    """
    Add parlay eligibility data to each edge.
    
    Adds:
    - edge["parlay"]["allowed"]: bool
    - edge["parlay"]["reason"]: str
    - edge["parlay"]["conflicting_edge_ids"]: list
    """
    enriched = []
    
    # Build correlation groups first
    groups = detect_correlation_groups(edges)
    
    for edge in edges:
        # Get individual eligibility
        eligibility = evaluate_edge_eligibility(edge)
        
        # Find potential conflicts
        player = edge.get("player", edge.get("entity", "")).lower().strip()
        player_key = f"player:{player}"
        player_edges = groups.get(player_key, [])
        
        conflicting_ids = []
        if len(player_edges) > 1:
            # Multiple edges for same player
            edge_id = edge.get("edge_id", edge.get("id", ""))
            for other in player_edges:
                other_id = other.get("edge_id", other.get("id", ""))
                if other_id and other_id != edge_id:
                    conflicting_ids.append(other_id)
            
            if conflicting_ids and eligibility.allowed:
                # Downgrade to warning
                eligibility.reason = BlockReason.MULTI_PROP_SAME_PLAYER
                eligibility.details = f"{len(player_edges)} props for {player}"
        
        eligibility.conflicting_edge_ids = conflicting_ids
        
        # Add to edge
        edge_copy = edge.copy()
        edge_copy["parlay"] = eligibility.to_dict()
        enriched.append(edge_copy)
    
    return enriched


# =============================================================================
# PARLAY BUILDER WITH ENFORCEMENT
# =============================================================================

def build_safe_parlays(
    edges: List[Dict],
    legs: int = 2,
    max_per_player: int = 1,
    min_probability: float = 0.55
) -> List[Dict]:
    """
    Build valid parlay combinations with enforcement.
    
    Returns list of parlay dicts with:
    - legs: list of edges
    - combined_probability: float
    - all_passing: bool
    """
    from itertools import combinations
    
    def get_probability(e: Dict) -> float:
        """Extract probability from edge, handling various field names and formats."""
        # Try probability first (0-1 scale)
        prob = e.get("probability", None)
        if prob is not None and prob > 0:
            return prob if prob <= 1 else prob / 100
        
        # Try effective_confidence (usually 0-100 scale)
        conf = e.get("effective_confidence", None)
        if conf is not None and conf > 0:
            return conf / 100 if conf > 1 else conf
        
        # Try model_confidence (usually 0-100 scale)
        conf = e.get("model_confidence", None)
        if conf is not None and conf > 0:
            return conf / 100 if conf > 1 else conf
        
        return 0
    
    # Filter to eligible edges
    eligible = [
        e for e in edges
        if evaluate_edge_eligibility(e).allowed
        and get_probability(e) >= min_probability
    ]
    
    # Sort by probability descending
    eligible = sorted(
        eligible,
        key=lambda x: get_probability(x),
        reverse=True
    )
    
    valid_parlays = []
    
    for combo in combinations(eligible[:20], legs):  # Top 20 only
        is_valid, reasons = evaluate_parlay_combination(
            list(combo),
            max_per_player=max_per_player
        )
        
        if is_valid:
            combined_prob = 1.0
            for edge in combo:
                combined_prob *= get_probability(edge)
            
            valid_parlays.append({
                "legs": list(combo),
                "leg_count": legs,
                "combined_probability": round(combined_prob, 4),
                "combined_pct": f"{combined_prob * 100:.1f}%",
                "all_passing": True,
            })
    
    # Sort by combined probability
    valid_parlays = sorted(
        valid_parlays,
        key=lambda x: x["combined_probability"],
        reverse=True
    )
    
    return valid_parlays[:10]  # Top 10


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    # Test with sample edges
    test_edges = [
        {
            "edge_id": "sengun_pts_1",
            "player": "Alperen Sengun",
            "stat": "points",
            "line": 20.5,
            "direction": "higher",
            "probability": 0.65,
            "tier": "STRONG",
        },
        {
            "edge_id": "sengun_reb_1",
            "player": "Alperen Sengun",
            "stat": "rebounds",
            "line": 10.5,
            "direction": "higher",
            "probability": 0.62,
            "tier": "STRONG",
        },
        {
            "edge_id": "sengun_td_1",
            "player": "Alperen Sengun",
            "stat": "triple_double",
            "line": 0.5,
            "direction": "under",
            "probability": 0.09,
            "tier": "NO_PLAY",
            "risk_tags": ["rare_event", "triple_double"],
        },
        {
            "edge_id": "maxey_pts_1",
            "player": "Tyrese Maxey",
            "stat": "points",
            "line": 25.5,
            "direction": "higher",
            "probability": 0.68,
            "tier": "STRONG",
        },
    ]
    
    print("=" * 60)
    print("PARLAY ELIGIBILITY TEST")
    print("=" * 60)
    
    enriched = enrich_edges_with_parlay_data(test_edges)
    
    for edge in enriched:
        player = edge.get("player", "")
        stat = edge.get("stat", "")
        parlay = edge.get("parlay", {})
        
        status = "✅" if parlay.get("allowed") else "❌"
        reason = parlay.get("reason", "ALLOWED")
        
        print(f"{status} {player} – {stat}: {reason}")
        if parlay.get("conflicting_edge_ids"):
            print(f"   Conflicts: {parlay['conflicting_edge_ids']}")
    
    print("\n" + "=" * 60)
    print("SAFE PARLAYS (2-leg)")
    print("=" * 60)
    
    parlays = build_safe_parlays(test_edges, legs=2)
    
    for i, parlay in enumerate(parlays, 1):
        print(f"\nParlay #{i} ({parlay['combined_pct']})")
        for leg in parlay["legs"]:
            player = leg.get("player", "")
            stat = leg.get("stat", "")
            prob = leg.get("probability", 0)
            print(f"  • {player} – {stat} ({prob*100:.0f}%)")
