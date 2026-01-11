#!/usr/bin/env python3
"""
NFL EDGE GENERATION
===================

EDGE = (player_id, game_id, direction)

Lines are collapsed later.
No duplication allowed.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import sys

# Add workspace root to path for gating module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Daily Games Report Gating (SOP v2.1)
from gating.daily_games_report_gating import gate_nfl_edges


@dataclass
class NFLEdge:
    """An NFL edge (player, game, direction)."""
    player_name: str
    game_id: str
    stat: str  # "passing_yards", "rushing_yards", "receptions", etc.
    direction: str  # "OVER" or "UNDER"
    
    # Context
    team: str
    opponent: str
    position: str
    snap_pct: float
    
    # Metadata
    feature_complete: bool
    missing_features: List[str]
    
    def __hash__(self):
        return hash((self.player_name, self.game_id, self.stat, self.direction))
    
    def __eq__(self, other):
        if not isinstance(other, NFLEdge):
            return False
        return (self.player_name == other.player_name and 
                self.game_id == other.game_id and
                self.stat == other.stat and
                self.direction == other.direction)


class NFLEdgeGenerator:
    """Generate NFL edges from features."""
    
    # Approved stat categories
    STAT_CATEGORIES = {
        "passing_yards": ("QB", ["passing_yards"]),
        "passing_tds": ("QB", ["touchdowns"]),
        "rushing_yards": ("RB", ["rushing_yards"]),
        "rushing_tds": ("RB", ["touchdowns"]),
        "receiving_yards": ("WR,TE", ["receiving_yards"]),
        "receptions": ("WR,TE", ["receptions"]),
        "reception_tds": ("WR,TE", ["touchdowns"]),
        "rush_attempts": ("RB", ["carries"]),
        "targets": ("WR,TE", ["targets"]),
    }
    
    def generate_edges(self, 
                      game_id: str,
                      features_dict: Dict,
                      stats_dict: Dict) -> List[NFLEdge]:
        """
        Generate edges from features and stats.
        
        Rules:
        1. stat must be in STAT_CATEGORIES
        2. snap_pct >= 20% required
        3. feature_complete must be True
        4. position must match stat category
        """
        edges = []
        
        for player_name, features in features_dict.items():
            stats = stats_dict.get(player_name, {})
            
            # Gate 1: Feature completeness
            if not features.features_complete:
                print(f"  [SKIP] {player_name}: incomplete features {features.missing_features}")
                continue
            
            # Gate 2: Snap count
            snap_pct = float(stats.get("snap_pct", 0.0))
            if snap_pct < 0.20:
                print(f"  [SKIP] {player_name}: snap_pct {snap_pct*100:.1f}% < 20%")
                continue
            
            # Gate 3: Position match
            position = stats.get("position", "")
            
            # Generate edges for eligible stats
            for stat, (eligible_pos, _) in self.STAT_CATEGORIES.items():
                if position not in eligible_pos:
                    continue
                
                # Check if player has data for this stat
                if stat == "passing_yards" and stats.get("passing_yards", 0) <= 0:
                    continue
                if stat == "rushing_yards" and stats.get("rushing_yards", 0) <= 0:
                    continue
                if stat == "receiving_yards" and stats.get("receiving_yards", 0) <= 0:
                    continue
                if stat == "receptions" and stats.get("receptions", 0) <= 0:
                    continue
                if stat == "targets" and stats.get("targets", 0) <= 0:
                    continue
                
                # Generate OVER and UNDER edges
                for direction in ["OVER", "UNDER"]:
                    edge = NFLEdge(
                        player_name=player_name,
                        game_id=game_id,
                        stat=stat,
                        direction=direction,
                        team=stats.get("team", ""),
                        opponent=stats.get("opponent", ""),
                        position=position,
                        snap_pct=snap_pct,
                        feature_complete=features.features_complete,
                        missing_features=features.missing_features,
                    )
                    edges.append(edge)
                    print(f"  ✓ {player_name} {stat} {direction}")
        
        return edges
    
    def deduplicate_edges(self, edges: List[NFLEdge]) -> List[NFLEdge]:
        """
        Remove duplicate edges (same player, game, stat, direction).
        
        This is edge-collapse enforcement.
        """
        seen = set()
        dedup = []
        
        for edge in edges:
            edge_key = (edge.player_name, edge.game_id, edge.stat, edge.direction)
            if edge_key not in seen:
                seen.add(edge_key)
                dedup.append(edge)
            else:
                print(f"  [DUP] Removed duplicate: {edge.player_name} {edge.stat} {edge.direction}")
        
        return dedup


def generate_nfl_edges(game_id: str,
                      features_dict: Dict,
                      stats_dict: Dict) -> List[NFLEdge]:
    """
    Generate edges for NFL game.
    
    Returns:
        List of NFLEdge objects (deduplicated)
    """
    generator = NFLEdgeGenerator()
    
    edges = generator.generate_edges(game_id, features_dict, stats_dict)
    dedup_edges = generator.deduplicate_edges(edges)
    
    return dedup_edges


if __name__ == "__main__":
    # SOP v2.1 GATING CHECK: Verify Daily Games Report exists for today
    date = datetime.now().strftime("%Y-%m-%d")
    confidence_caps = gate_nfl_edges(date=date)  # Aborts if no report
    print(f"✅ Gating PASSED for {date}")
    print(f"   Confidence caps: core={confidence_caps['core']}, alt={confidence_caps['alt']}, td={confidence_caps['td']}")
    print("\n📊 NFL Edge Generator ready for pipeline integration.")
