"""
CBB Team Features

Team-level features for edge generation context.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TeamFeatures:
    """CBB team feature set"""
    team_id: str
    team_name: str
    conference: str
    
    # Pace metrics
    possessions_per_game: float = 0.0
    tempo_rank: int = 0
    
    # Efficiency
    offensive_efficiency: float = 0.0
    defensive_efficiency: float = 0.0
    
    # Scoring
    points_per_game: float = 0.0
    points_allowed: float = 0.0
    
    # Record
    wins: int = 0
    losses: int = 0
    conference_wins: int = 0
    conference_losses: int = 0
    
    # Context
    games_played: int = 0
    home_record: str = ""
    away_record: str = ""


def build_team_features(
    team_id: str,
    team_stats: Dict,
    opponent_stats: Optional[Dict] = None
) -> TeamFeatures:
    """
    Build team features from aggregated stats.
    
    Args:
        team_id: Team identifier
        team_stats: Dictionary of team statistics
        opponent_stats: Optional opponent stats for matchup context
        
    Returns:
        TeamFeatures dataclass
    """
    features = TeamFeatures(
        team_id=team_id,
        team_name=team_stats.get("team_name", team_id),
        conference=team_stats.get("conference", "Unknown"),
        
        possessions_per_game=team_stats.get("possessions_pg", 0.0),
        tempo_rank=team_stats.get("tempo_rank", 0),
        
        offensive_efficiency=team_stats.get("off_efficiency", 0.0),
        defensive_efficiency=team_stats.get("def_efficiency", 0.0),
        
        points_per_game=team_stats.get("ppg", 0.0),
        points_allowed=team_stats.get("ppg_allowed", 0.0),
        
        wins=team_stats.get("wins", 0),
        losses=team_stats.get("losses", 0),
        conference_wins=team_stats.get("conf_wins", 0),
        conference_losses=team_stats.get("conf_losses", 0),
        
        games_played=team_stats.get("games_played", 0),
    )
    
    return features


def compute_matchup_adjustment(
    team: TeamFeatures,
    opponent: TeamFeatures
) -> Dict[str, float]:
    """
    Compute pace and efficiency adjustments for a specific matchup.
    
    Returns adjustment factors for player projections.
    """
    # Pace adjustment
    avg_tempo = (team.possessions_per_game + opponent.possessions_per_game) / 2
    league_avg_tempo = 70.0  # NCAA average possessions per game
    pace_factor = avg_tempo / league_avg_tempo if league_avg_tempo > 0 else 1.0
    
    # Defensive adjustment
    league_avg_def = 100.0
    def_factor = opponent.defensive_efficiency / league_avg_def if league_avg_def > 0 else 1.0
    
    return {
        "pace_factor": round(pace_factor, 3),
        "defensive_factor": round(def_factor, 3),
        "combined_factor": round(pace_factor * (2 - def_factor), 3),  # Higher vs bad defense
    }
