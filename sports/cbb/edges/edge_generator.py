"""
CBB Edge Generator

Creates edges from player features and lines.
Applies CBB-specific gates before edge creation.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import hashlib
from datetime import datetime


@dataclass
class CBBEdge:
    """Single CBB betting edge"""
    edge_id: str
    game_id: str
    player_id: str
    player_name: str
    team: str
    opponent: str
    
    stat: str
    line: float
    direction: str  # "higher" or "lower"
    
    probability: float = 0.0
    tier: str = "NO_PLAY"
    
    # Context
    is_conference_game: bool = False
    blowout_probability: float = 0.0
    
    # Data quality
    sample_size: int = 0
    data_sources: List[str] = None
    
    # Blocking
    is_blocked: bool = False
    block_reason: Optional[str] = None
    
    # Primary selection
    is_primary: bool = False
    
    def __post_init__(self):
        if self.data_sources is None:
            self.data_sources = []


def generate_edge_id(game_id: str, player_id: str, stat: str, direction: str) -> str:
    """Generate deterministic edge ID."""
    raw = f"{game_id}:{player_id}:{stat}:{direction}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def generate_edges(
    lines: List[Dict],
    player_features: Dict[str, any],
    game_context: any,
    probabilities: Dict[str, Dict[str, float]]
) -> List[CBBEdge]:
    """
    Generate CBB edges from lines and features.
    
    Args:
        lines: List of prop lines {player_id, stat, line, ...}
        player_features: Dict mapping player_id to PlayerFeatures
        game_context: GameContext for the game
        probabilities: Dict mapping (player_id, stat, direction) to probability
        
    Returns:
        List of CBBEdge objects (some may be blocked)
    """
    from sports.cbb.config import BLOCKED_STATS, TIER_THRESHOLDS
    from .edge_gates import apply_cbb_edge_gates
    
    edges = []
    
    for line in lines:
        player_id = line.get("player_id")
        stat = line.get("stat", "").lower()
        line_value = line.get("line", 0)
        
        # Skip blocked stats
        if stat in BLOCKED_STATS:
            continue
        
        # Get player features
        pf = player_features.get(player_id)
        if pf is None or pf.is_blocked:
            continue
        
        # Generate both directions
        for direction in ["higher", "lower"]:
            edge_id = generate_edge_id(
                game_context.game_id, player_id, stat, direction
            )
            
            # Get probability
            prob_key = (player_id, stat, direction)
            prob = probabilities.get(prob_key, {}).get("probability", 0.0)
            
            # Assign tier
            tier = assign_tier(prob)
            
            edge = CBBEdge(
                edge_id=edge_id,
                game_id=game_context.game_id,
                player_id=player_id,
                player_name=pf.player_name,
                team=pf.team,
                opponent=game_context.away_team if pf.team == game_context.home_team else game_context.home_team,
                
                stat=stat,
                line=line_value,
                direction=direction,
                
                probability=prob,
                tier=tier,
                
                is_conference_game=game_context.is_conference_game,
                blowout_probability=game_context.blowout_probability,
                
                sample_size=pf.games_played,
                data_sources=["sportsreference"],  # TODO: track actual sources
            )
            
            # Apply CBB-specific gates
            edge = apply_cbb_edge_gates(edge, pf, game_context)
            
            edges.append(edge)
    
    return edges


def assign_tier(probability: float) -> str:
    """Assign tier based on probability (CBB thresholds).
    
    GOVERNANCE: Uses canonical thresholds from config/thresholds.py
    CBB-specific: SLAM disabled, STRONG ≥70%, LEAN ≥60%
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from config.thresholds import implied_tier
    
    return implied_tier(probability, 'CBB')
