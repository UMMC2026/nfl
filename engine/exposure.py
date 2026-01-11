"""
Parlay Exposure Governor - Prevents over-concentration of risk.

Enforces diversification rules:
- Max legs per player
- Max legs per team
- Max legs per game
- Correlation penalties
"""
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from itertools import combinations
import math


@dataclass
class ExposureConfig:
    """Configuration for exposure limits."""
    max_legs_per_player: int = 1      # Max props from same player in parlay
    max_legs_per_team: int = 2        # Max props from same team
    max_legs_per_game: int = 3        # Max props from same game
    min_unique_teams: int = 2         # Minimum different teams required
    max_same_stat_type: int = 2       # Max legs of same stat type (e.g., points)
    correlation_penalty: float = 0.15 # EV penalty for correlated legs


@dataclass 
class Signal:
    """Signal data for exposure calculations."""
    player: str
    team: str
    opponent: str
    stat: str
    line: float
    direction: str
    probability: float
    tier: str
    
    @property
    def game_key(self) -> str:
        """Unique identifier for the game."""
        teams = sorted([self.team, self.opponent]) if self.opponent else [self.team]
        return "-".join(teams)


class ExposureGovernor:
    """
    Validates and scores parlays based on exposure rules.
    """
    
    def __init__(self, config: ExposureConfig = None):
        self.config = config or ExposureConfig()
        
        # Known correlation groups (same player, same game outcome)
        self.correlated_stats = {
            "pts_combo": {"points", "pts+reb+ast", "pts+reb", "pts+ast"},
            "reb_combo": {"rebounds", "pts+reb+ast", "pts+reb", "reb+ast"},
            "ast_combo": {"assists", "pts+reb+ast", "pts+ast", "reb+ast"},
            "def_combo": {"steals", "blocks", "stl+blk"},
        }
    
    def validate_parlay(self, legs: List[Signal]) -> Tuple[bool, List[str]]:
        """
        Validate a parlay against exposure rules.
        Returns: (is_valid, list_of_violations)
        """
        violations = []
        
        # Check player exposure
        player_counts = {}
        for leg in legs:
            player_counts[leg.player] = player_counts.get(leg.player, 0) + 1
        
        for player, count in player_counts.items():
            if count > self.config.max_legs_per_player:
                violations.append(
                    f"Player {player} appears {count}x (max: {self.config.max_legs_per_player})"
                )
        
        # Check team exposure
        team_counts = {}
        for leg in legs:
            team_counts[leg.team] = team_counts.get(leg.team, 0) + 1
        
        for team, count in team_counts.items():
            if count > self.config.max_legs_per_team:
                violations.append(
                    f"Team {team} appears {count}x (max: {self.config.max_legs_per_team})"
                )
        
        # Check minimum unique teams
        unique_teams = set(leg.team for leg in legs)
        if len(unique_teams) < self.config.min_unique_teams:
            violations.append(
                f"Only {len(unique_teams)} unique teams (min: {self.config.min_unique_teams})"
            )
        
        # Check game exposure
        game_counts = {}
        for leg in legs:
            game_counts[leg.game_key] = game_counts.get(leg.game_key, 0) + 1
        
        for game, count in game_counts.items():
            if count > self.config.max_legs_per_game:
                violations.append(
                    f"Game {game} has {count} legs (max: {self.config.max_legs_per_game})"
                )
        
        # Check stat type concentration
        stat_counts = {}
        for leg in legs:
            base_stat = leg.stat.split("+")[0] if "+" in leg.stat else leg.stat
            stat_counts[base_stat] = stat_counts.get(base_stat, 0) + 1
        
        for stat, count in stat_counts.items():
            if count > self.config.max_same_stat_type:
                violations.append(
                    f"Stat '{stat}' appears {count}x (max: {self.config.max_same_stat_type})"
                )
        
        return len(violations) == 0, violations
    
    def calculate_correlation_penalty(self, legs: List[Signal]) -> float:
        """
        Calculate EV penalty for correlated legs.
        Returns penalty multiplier (0.0 - 1.0, where 1.0 = no penalty).
        """
        penalty = 0.0
        
        # Check each pair of legs
        for i, leg1 in enumerate(legs):
            for leg2 in legs[i+1:]:
                # Same player = high correlation
                if leg1.player == leg2.player:
                    penalty += self.config.correlation_penalty * 2
                    continue
                
                # Same game, opposite outcomes = medium correlation
                if leg1.game_key == leg2.game_key:
                    if leg1.team != leg2.team:
                        # Different teams in same game - negatively correlated
                        penalty += self.config.correlation_penalty * 0.5
                    else:
                        # Same team - positively correlated
                        penalty += self.config.correlation_penalty
                
                # Check stat correlations
                for group_name, stat_group in self.correlated_stats.items():
                    if leg1.stat in stat_group and leg2.stat in stat_group:
                        if leg1.player == leg2.player:
                            penalty += self.config.correlation_penalty
                        break
        
        # Cap penalty at 50%
        return max(0.5, 1.0 - penalty)
    
    def score_parlay(self, legs: List[Signal]) -> Dict:
        """
        Score a parlay with exposure and correlation analysis.
        """
        is_valid, violations = self.validate_parlay(legs)
        
        # Calculate base probability
        base_prob = 1.0
        for leg in legs:
            base_prob *= leg.probability
        
        # Apply correlation penalty
        correlation_mult = self.calculate_correlation_penalty(legs)
        adjusted_prob = base_prob * correlation_mult
        
        # Calculate diversity score (0-100)
        unique_teams = len(set(leg.team for leg in legs))
        unique_games = len(set(leg.game_key for leg in legs))
        unique_stats = len(set(leg.stat for leg in legs))
        
        diversity_score = (
            (unique_teams / len(legs)) * 40 +
            (unique_games / len(legs)) * 30 +
            (unique_stats / len(legs)) * 30
        )
        
        return {
            "is_valid": is_valid,
            "violations": violations,
            "leg_count": len(legs),
            "base_probability": base_prob,
            "correlation_multiplier": correlation_mult,
            "adjusted_probability": adjusted_prob,
            "diversity_score": round(diversity_score, 1),
            "unique_teams": unique_teams,
            "unique_games": unique_games,
            "legs": [
                {
                    "player": leg.player,
                    "team": leg.team,
                    "stat": leg.stat,
                    "line": leg.line,
                    "direction": leg.direction,
                    "probability": leg.probability,
                }
                for leg in legs
            ],
        }
    
    def find_optimal_parlays(
        self, 
        signals: List[Signal], 
        leg_count: int = 3,
        top_n: int = 10,
        min_probability: float = 0.5,
    ) -> List[Dict]:
        """
        Find optimal parlay combinations that pass exposure rules.
        """
        valid_parlays = []
        
        # Generate all combinations of specified size
        for combo in combinations(signals, leg_count):
            legs = list(combo)
            
            # Validate
            is_valid, _ = self.validate_parlay(legs)
            if not is_valid:
                continue
            
            # Score
            score = self.score_parlay(legs)
            
            # Filter by probability
            if score["adjusted_probability"] < min_probability:
                continue
            
            valid_parlays.append(score)
        
        # Sort by adjusted probability
        valid_parlays.sort(key=lambda x: x["adjusted_probability"], reverse=True)
        
        return valid_parlays[:top_n]


def build_safe_parlay(
    signals: List[dict],
    leg_count: int = 3,
    config: ExposureConfig = None,
) -> Dict:
    """
    Convenience function to build a safe parlay from signal dicts.
    """
    # Convert dicts to Signal objects
    signal_objs = [
        Signal(
            player=s.get("player", ""),
            team=s.get("team", ""),
            opponent=s.get("opponent", ""),
            stat=s.get("stat", ""),
            line=s.get("line", 0),
            direction=s.get("direction", "higher"),
            probability=s.get("probability", 0),
            tier=s.get("tier", ""),
        )
        for s in signals
    ]
    
    governor = ExposureGovernor(config)
    parlays = governor.find_optimal_parlays(
        signal_objs,
        leg_count=leg_count,
        top_n=5,
    )
    
    return parlays[0] if parlays else None


# Example usage
if __name__ == "__main__":
    # Test with sample signals
    test_signals = [
        Signal("Ja Morant", "MEM", "HOU", "points", 20.5, "higher", 0.925, "SLAM"),
        Signal("Ja Morant", "MEM", "HOU", "pts+reb+ast", 31.5, "higher", 0.911, "SLAM"),
        Signal("Jock Landale", "HOU", "MEM", "rebounds", 6.5, "lower", 0.893, "SLAM"),
        Signal("Lauri Markkanen", "UTA", "NOP", "assists", 1.5, "lower", 0.892, "SLAM"),
        Signal("Jaylen Brown", "BOS", "IND", "assists", 5.5, "lower", 0.853, "SLAM"),
        Signal("Jaden Ivey", "DET", "MIA", "points", 11.5, "higher", 0.828, "STRONG"),
    ]
    
    governor = ExposureGovernor()
    
    print("=== Testing Exposure Governor ===\n")
    
    # Test invalid parlay (same player twice)
    invalid_legs = test_signals[:2]  # Two Ja Morant props
    is_valid, violations = governor.validate_parlay(invalid_legs)
    print(f"Invalid parlay test: valid={is_valid}")
    print(f"Violations: {violations}\n")
    
    # Find optimal parlays
    print("=== Optimal 3-Leg Parlays ===\n")
    optimal = governor.find_optimal_parlays(test_signals, leg_count=3, top_n=3)
    
    for i, parlay in enumerate(optimal, 1):
        print(f"Parlay #{i}:")
        print(f"  Probability: {parlay['adjusted_probability']:.1%}")
        print(f"  Diversity Score: {parlay['diversity_score']}")
        print(f"  Teams: {parlay['unique_teams']}")
        for leg in parlay["legs"]:
            dir_text = "O" if leg["direction"] == "higher" else "U"
            print(f"    - {leg['player']} {dir_text}{leg['line']} {leg['stat']} ({leg['probability']:.0%})")
        print()
