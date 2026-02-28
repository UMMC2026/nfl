"""
CBB Edge Collapse

Enforces: ONE EDGE → ONE PRIMARY LINE

Collapse rules:
1. One edge per (player, stat, game)
2. Select primary based on probability and tier
3. Mark non-primary edges as correlated
"""
from typing import Dict, List
from collections import defaultdict
from .edge_generator import CBBEdge


def collapse_edges(edges: List[CBBEdge]) -> List[CBBEdge]:
    """
    Collapse edges to one primary per (player, stat, game).
    
    Rules:
    1. Group edges by (game_id, player_id, stat)
    2. Select highest probability edge as primary
    3. Mark others as correlated (not primary)
    
    Args:
        edges: List of CBBEdge objects
        
    Returns:
        List of edges with is_primary set correctly
    """
    # Filter out blocked edges first
    active_edges = [e for e in edges if not e.is_blocked]
    blocked_edges = [e for e in edges if e.is_blocked]
    
    # Group by (game_id, player_id, stat)
    groups: Dict[tuple, List[CBBEdge]] = defaultdict(list)
    for edge in active_edges:
        key = (edge.game_id, edge.player_id, edge.stat)
        groups[key].append(edge)
    
    # Select primary for each group
    collapsed = []
    for key, group in groups.items():
        # Sort by probability descending
        sorted_group = sorted(group, key=lambda e: e.probability, reverse=True)
        
        # First edge is primary
        for i, edge in enumerate(sorted_group):
            edge.is_primary = (i == 0)
            collapsed.append(edge)
    
    # Return blocked edges too (for audit)
    return collapsed + blocked_edges


def validate_collapse(edges: List[CBBEdge]) -> Dict:
    """
    Validate collapse rules were applied correctly.
    
    Checks:
    1. Exactly one primary per (game_id, player_id, stat)
    2. No blocked edges are marked primary
    """
    errors = []
    
    # Check primary counts
    primary_counts: Dict[tuple, int] = defaultdict(int)
    for edge in edges:
        if edge.is_primary and not edge.is_blocked:
            key = (edge.game_id, edge.player_id, edge.stat)
            primary_counts[key] += 1
    
    # Report violations
    for key, count in primary_counts.items():
        if count != 1:
            errors.append(f"Invalid primary count for {key}: {count}")
    
    # Check blocked edges
    blocked_primaries = [e for e in edges if e.is_blocked and e.is_primary]
    if blocked_primaries:
        errors.append(f"Blocked edges marked as primary: {len(blocked_primaries)}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "total_edges": len(edges),
        "primary_edges": sum(1 for e in edges if e.is_primary),
        "blocked_edges": sum(1 for e in edges if e.is_blocked),
    }


def dedupe_player_edges(edges: List[CBBEdge], max_per_player: int = 2) -> List[CBBEdge]:
    """
    Limit edges per player to prevent over-concentration.
    
    Args:
        edges: List of collapsed edges
        max_per_player: Maximum primary edges per player
        
    Returns:
        List with excess edges demoted to non-primary
    """
    # Group primaries by player
    player_primaries: Dict[str, List[CBBEdge]] = defaultdict(list)
    for edge in edges:
        if edge.is_primary and not edge.is_blocked:
            player_primaries[edge.player_id].append(edge)
    
    # Demote excess
    for player_id, player_edges in player_primaries.items():
        if len(player_edges) > max_per_player:
            # Sort by probability, keep top N
            sorted_edges = sorted(player_edges, key=lambda e: e.probability, reverse=True)
            for edge in sorted_edges[max_per_player:]:
                edge.is_primary = False
    
    return edges
