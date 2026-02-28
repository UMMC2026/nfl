"""
Soccer Edge Generator
=====================
Converts parsed props into edges with Monte Carlo probabilities.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..config.soccer_config import get_tier, MARKET_CONFIDENCE_CAPS
from .soccer_monte_carlo import SoccerMonteCarloSimulator


@dataclass
class SoccerEdge:
    """Represents a soccer betting edge."""
    edge_id: str
    player: str
    team: str
    opponent: str
    match: str
    stat: str
    line: float
    direction: str
    probability: float
    tier: str
    pick_state: str  # OPTIMIZABLE, VETTED, REJECTED
    
    # Additional context
    player_avg: Optional[float] = None
    games_played: int = 10
    position: Optional[str] = None
    league: str = "premier_league"
    distribution: str = "unknown"
    confidence_cap: Optional[float] = None
    
    # Metadata
    data_sources: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "edge_id": self.edge_id,
            "player": self.player,
            "team": self.team,
            "opponent": self.opponent,
            "match": self.match,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "probability": self.probability,
            "tier": self.tier,
            "pick_state": self.pick_state,
            "player_avg": self.player_avg,
            "games_played": self.games_played,
            "position": self.position,
            "league": self.league,
            "distribution": self.distribution,
            "confidence_cap": self.confidence_cap,
            "data_sources": self.data_sources,
            "generated_at": self.generated_at,
        }


def generate_edge_from_prop(
    prop,
    player_stats: Optional[Dict] = None,
    simulator: Optional[SoccerMonteCarloSimulator] = None,
) -> List[SoccerEdge]:
    """
    Generate edges (both directions) from a parsed prop.
    
    Args:
        prop: Parsed SoccerProp object
        player_stats: Optional dict with player's historical stats
        simulator: Monte Carlo simulator instance
        
    Returns:
        List of SoccerEdge objects (one for each direction with edge)
    """
    if simulator is None:
        simulator = SoccerMonteCarloSimulator()
    
    edges = []
    
    # Get player stats or use defaults
    if player_stats:
        player_avg = player_stats.get(prop.stat, {}).get("avg", None)
        games_played = player_stats.get("games_played", 10)
        position = player_stats.get("position")
        player_std = player_stats.get(prop.stat, {}).get("std")
    else:
        # Use position-based defaults if no player data
        player_avg = None
        games_played = 10
        position = None
        player_std = None
    
    # If no player avg, we can't generate meaningful edge
    if player_avg is None:
        # Create "unknown" edge marked as VETTED
        edge_id = f"{prop.player}_{prop.stat}_{prop.line}_unknown"
        return [SoccerEdge(
            edge_id=edge_id,
            player=prop.player,
            team=prop.team,
            opponent=prop.opponent,
            match=prop.match,
            stat=prop.stat,
            line=prop.line,
            direction="unknown",
            probability=0.50,
            tier="AVOID",
            pick_state="REJECTED",
            player_avg=None,
            games_played=0,
            position=position,
            league=prop.league,
            data_sources=["no_data"],
        )]
    
    # Run Monte Carlo simulation
    result = simulator.simulate_stat(
        stat=prop.stat,
        player_avg=player_avg,
        line=prop.line,
        player_std=player_std,
        position=position,
        league=prop.league,
        games_played=games_played,
    )
    
    # Get confidence cap for this stat
    confidence_cap = MARKET_CONFIDENCE_CAPS.get(prop.stat.lower(), 0.75)
    
    # Generate OVER edge
    prob_over = min(result.probability_over, confidence_cap)
    tier_over = get_tier(prob_over)
    state_over = _determine_pick_state(prob_over, tier_over, games_played)
    
    if prob_over >= 0.50:  # Only create edge if there's positive expectation
        edges.append(SoccerEdge(
            edge_id=f"{prop.player}_{prop.stat}_{prop.line}_over",
            player=prop.player,
            team=prop.team,
            opponent=prop.opponent,
            match=prop.match,
            stat=prop.stat,
            line=prop.line,
            direction="higher",
            probability=round(prob_over, 4),
            tier=tier_over,
            pick_state=state_over,
            player_avg=round(player_avg, 2),
            games_played=games_played,
            position=position,
            league=prop.league,
            distribution=result.distribution,
            confidence_cap=confidence_cap,
            data_sources=["player_database"],
        ))
    
    # Generate UNDER edge
    prob_under = min(result.probability_under, confidence_cap)
    tier_under = get_tier(prob_under)
    state_under = _determine_pick_state(prob_under, tier_under, games_played)
    
    if prob_under >= 0.50:
        edges.append(SoccerEdge(
            edge_id=f"{prop.player}_{prop.stat}_{prop.line}_under",
            player=prop.player,
            team=prop.team,
            opponent=prop.opponent,
            match=prop.match,
            stat=prop.stat,
            line=prop.line,
            direction="lower",
            probability=round(prob_under, 4),
            tier=tier_under,
            pick_state=state_under,
            player_avg=round(player_avg, 2),
            games_played=games_played,
            position=position,
            league=prop.league,
            distribution=result.distribution,
            confidence_cap=confidence_cap,
            data_sources=["player_database"],
        ))
    
    return edges


def _determine_pick_state(probability: float, tier: str, games_played: int) -> str:
    """
    Determine pick state based on governance rules.
    
    Returns: OPTIMIZABLE, VETTED, or REJECTED
    """
    # Reject low probability
    if probability < 0.50:
        return "REJECTED"
    
    # Reject insufficient data
    if games_played < 3:
        return "REJECTED"
    
    # Vette marginal picks with low sample
    if games_played < 5 and probability < 0.58:
        return "VETTED"
    
    # AVOID tier is vetted, not optimizable
    if tier == "AVOID":
        return "REJECTED"
    
    # SPEC tier is vetted (speculative)
    if tier == "SPEC":
        return "VETTED"
    
    return "OPTIMIZABLE"


def filter_optimizable(edges: List[SoccerEdge]) -> List[SoccerEdge]:
    """Filter to only OPTIMIZABLE edges."""
    return [e for e in edges if e.pick_state == "OPTIMIZABLE"]


def sort_by_probability(edges: List[SoccerEdge], descending: bool = True) -> List[SoccerEdge]:
    """Sort edges by probability."""
    return sorted(edges, key=lambda e: e.probability, reverse=descending)
