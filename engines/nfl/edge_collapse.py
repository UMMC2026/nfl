"""
NFL Edge Collapse - Market Deduplication
NFL_AUTONOMOUS v1.0 Compatible

Implements edge deduplication per SOP:
- Primary line selection (OVER = highest, UNDER = lowest)
- Single edge per (player, game, market) tuple
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Import without relative imports
sys.path.insert(0, str(Path(__file__).parent))
from nfl_markets import NFLMarket


class Direction(Enum):
    OVER = "over"
    UNDER = "under"
    HIGHER = "higher"  # Alias for OVER
    LOWER = "lower"    # Alias for UNDER


@dataclass
class PropEdge:
    """Represents a single prop betting edge."""
    player_id: str
    player_name: str
    game_id: str
    market: NFLMarket
    line: float
    direction: Direction
    probability: float
    edge_strength: float  # probability - 0.5 (for 50/50 markets)
    
    def __hash__(self):
        return hash((self.player_id, self.game_id, self.market))
    
    def get_dedup_key(self) -> Tuple[str, str, NFLMarket]:
        """Return key for deduplication."""
        return (self.player_id, self.game_id, self.market)


class EdgeCollapser:
    """Collapse multiple lines per market into single primary edge."""
    
    def __init__(self, reasonable_threshold: float = 0.30):
        """
        Args:
            reasonable_threshold: Minimum probability to consider a line "reasonable"
        """
        self.reasonable_threshold = reasonable_threshold
    
    def collapse_edges(self, edges: List[PropEdge]) -> List[PropEdge]:
        """
        Collapse edges to one per (player, game, market).
        
        Selection rules:
        - OVER: Select highest reasonable line
        - UNDER: Select lowest reasonable line
        - Reasonable = probability >= threshold
        
        Args:
            edges: List of all prop edges
        
        Returns:
            List of collapsed edges (one per unique key)
        """
        # Group by dedup key
        edge_groups: Dict[Tuple, List[PropEdge]] = {}
        
        for edge in edges:
            key = edge.get_dedup_key()
            if key not in edge_groups:
                edge_groups[key] = []
            edge_groups[key].append(edge)
        
        # Select primary edge per group
        collapsed = []
        for key, group in edge_groups.items():
            primary = self._select_primary_edge(group)
            if primary:
                collapsed.append(primary)
        
        return collapsed
    
    def _select_primary_edge(self, edges: List[PropEdge]) -> PropEdge:
        """
        Select primary edge from group.
        
        Rules:
        1. Filter to "reasonable" edges (prob >= threshold)
        2. For OVER: pick highest line
        3. For UNDER: pick lowest line
        4. If tie, pick highest probability
        """
        if not edges:
            return None
        
        if len(edges) == 1:
            return edges[0]
        
        # Separate by direction
        overs = [e for e in edges if e.direction in (Direction.OVER, Direction.HIGHER)]
        unders = [e for e in edges if e.direction in (Direction.UNDER, Direction.LOWER)]
        
        # Filter to reasonable edges
        overs_reasonable = [e for e in overs if e.probability >= self.reasonable_threshold]
        unders_reasonable = [e for e in unders if e.probability >= self.reasonable_threshold]
        
        # Select primary OVER (highest line among reasonable)
        primary_over = None
        if overs_reasonable:
            primary_over = max(overs_reasonable, key=lambda e: (e.line, e.probability))
        
        # Select primary UNDER (lowest line among reasonable)
        primary_under = None
        if unders_reasonable:
            primary_under = min(unders_reasonable, key=lambda e: (e.line, -e.probability))
        
        # Choose between OVER and UNDER (prefer higher probability)
        if primary_over and primary_under:
            return primary_over if primary_over.probability >= primary_under.probability else primary_under
        elif primary_over:
            return primary_over
        elif primary_under:
            return primary_under
        else:
            # No reasonable edges - fall back to highest probability
            return max(edges, key=lambda e: e.probability)
    
    def detect_conflicts(self, edges: List[PropEdge]) -> List[Dict[str, Any]]:
        """
        Detect conflicting edges (same player/game/market with both OVER and UNDER).
        
        Returns list of conflicts with both sides for review.
        """
        edge_groups: Dict[Tuple, List[PropEdge]] = {}
        
        for edge in edges:
            key = edge.get_dedup_key()
            if key not in edge_groups:
                edge_groups[key] = []
            edge_groups[key].append(edge)
        
        conflicts = []
        for key, group in edge_groups.items():
            overs = [e for e in group if e.direction in (Direction.OVER, Direction.HIGHER)]
            unders = [e for e in group if e.direction in (Direction.UNDER, Direction.LOWER)]
            
            if overs and unders:
                conflicts.append({
                    "player_id": key[0],
                    "game_id": key[1],
                    "market": key[2],
                    "overs": overs,
                    "unders": unders,
                    "needs_review": True
                })
        
        return conflicts
    
    def rank_edges(self, edges: List[PropEdge], sort_by: str = "probability") -> List[PropEdge]:
        """
        Rank edges by quality.
        
        Args:
            edges: List of prop edges
            sort_by: 'probability', 'edge_strength', or 'composite'
        
        Returns:
            Sorted list (highest quality first)
        """
        if sort_by == "probability":
            return sorted(edges, key=lambda e: e.probability, reverse=True)
        
        elif sort_by == "edge_strength":
            return sorted(edges, key=lambda e: e.edge_strength, reverse=True)
        
        elif sort_by == "composite":
            # Composite score: probability * edge_strength
            return sorted(edges, key=lambda e: e.probability * e.edge_strength, reverse=True)
        
        else:
            return edges


def collapse_to_primary_lines(
    prop_data: List[Dict[str, Any]],
    reasonable_threshold: float = 0.30
) -> List[Dict[str, Any]]:
    """
    Convenience function: collapse raw prop data to primary lines.
    
    Args:
        prop_data: List of dicts with keys: player_id, player_name, game_id, 
                   market, line, direction, probability
        reasonable_threshold: Min probability for "reasonable" edge
    
    Returns:
        List of collapsed prop dicts (one per unique key)
    """
    # Convert to PropEdge objects
    edges = []
    for data in prop_data:
        try:
            edge = PropEdge(
                player_id=data['player_id'],
                player_name=data.get('player_name', ''),
                game_id=data['game_id'],
                market=NFLMarket(data['market']) if isinstance(data['market'], str) else data['market'],
                line=float(data['line']),
                direction=Direction(data['direction'].lower()),
                probability=float(data['probability']),
                edge_strength=float(data.get('edge_strength', data['probability'] - 0.5))
            )
            edges.append(edge)
        except Exception as e:
            print(f"Warning: Failed to process edge: {e}")
            continue
    
    # Collapse
    collapser = EdgeCollapser(reasonable_threshold)
    collapsed_edges = collapser.collapse_edges(edges)
    
    # Convert back to dicts
    return [
        {
            'player_id': e.player_id,
            'player_name': e.player_name,
            'game_id': e.game_id,
            'market': e.market.value,
            'line': e.line,
            'direction': e.direction.value,
            'probability': e.probability,
            'edge_strength': e.edge_strength
        }
        for e in collapsed_edges
    ]


# Example usage
if __name__ == "__main__":
    # Test edge collapse
    test_edges = [
        PropEdge("player1", "Patrick Mahomes", "game1", NFLMarket.PASS_YARDS, 275.5, Direction.OVER, 0.65, 0.15),
        PropEdge("player1", "Patrick Mahomes", "game1", NFLMarket.PASS_YARDS, 300.5, Direction.OVER, 0.55, 0.05),
        PropEdge("player1", "Patrick Mahomes", "game1", NFLMarket.PASS_YARDS, 250.5, Direction.UNDER, 0.45, -0.05),
        PropEdge("player2", "Christian McCaffrey", "game2", NFLMarket.RUSH_YARDS, 75.5, Direction.OVER, 0.70, 0.20),
    ]
    
    collapser = EdgeCollapser()
    collapsed = collapser.collapse_edges(test_edges)
    
    print("Collapsed edges:")
    for edge in collapsed:
        print(f"  {edge.player_name} {edge.market.value} {edge.direction.value} {edge.line} @ {edge.probability:.1%}")
    
    conflicts = collapser.detect_conflicts(test_edges)
    print(f"\nConflicts detected: {len(conflicts)}")
