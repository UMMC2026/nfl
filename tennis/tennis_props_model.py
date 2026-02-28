"""
TENNIS PROPS PREDICTION MODEL
Market-specific prediction models for player props

Integrates with existing tennis pipeline while adding props support
Compatible with SOP v2.1 tier thresholds
"""

from typing import Dict, Optional
from core.kalman_filter import KalmanFilter
from core.bayesian_smoothing import bayesian_shrinkage
from player_stats_database import PlayerStatsDatabase


# ============================================================================
# PROPS PREDICTION MODEL
# ============================================================================

class TennisPropsModel:
    """
    Predict player prop outcomes using historical stats and matchup data
    
    Supports markets:
    - Games Won
    - Aces
    - Breakpoints Won
    - Fantasy Score (PrizePicks)
    - Games Played
    - Sets Won/Played
    - Double Faults
    - Tiebreakers
    """
    
    def __init__(self, surface: str = 'hard'):
        self.player_db = PlayerStatsDatabase()
        self.surface = surface
    
    
    def predict_prop(self, player_name: str, opponent_name: str, 
                    market_type: str, line: float) -> Dict:
        """
        Unified prediction interface for any market type
        
        Args:
            player_name: Player name
            opponent_name: Opponent name
            market_type: Market (e.g., 'games_won', 'aces')
            line: DFS platform line value
            
        Returns:
            {
                'prediction': float,
                'probability_over': float,
                'probability_under': float,
                'edge_value': float,
                'confidence': str  # HIGH/MEDIUM/LOW
            }
        """
        # Get player data
        player_stats = self.player_db.get_player(player_name, self.surface)
        opponent_stats = self.player_db.get_player(opponent_name, self.surface)
        
        # Route to market-specific prediction
        if market_type == 'games_won':
            return self._predict_games_won(player_stats, opponent_stats, line)
        elif market_type == 'aces':
            return self._predict_aces(player_stats, opponent_stats, line)
        elif market_type == 'breakpoints_won':
            return self._predict_breakpoints(player_stats, opponent_stats, line)
        elif market_type == 'fantasy_score':
            return self._predict_fantasy_score(player_stats, opponent_stats, line)
        elif market_type in ['games_played', 'total_games']:
            return self._predict_games_played(player_stats, opponent_stats, line)
        elif market_type == 'first_set_games_won':
            return self._predict_first_set_games(player_stats, opponent_stats, line)
        elif market_type == 'double_faults':
            return self._predict_double_faults(player_stats, opponent_stats, line)
        elif market_type == 'sets_won':
            return self._predict_sets_won(player_stats, opponent_stats, line)
        elif market_type == 'tiebreakers_played':
            return self._predict_tiebreakers(player_stats, opponent_stats, line)
        else:
            # Generic fallback
            return self._predict_generic(line)
    
    
    def _predict_games_won(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict games won by player
        
        Confidence: HIGH (most stable market)
        """
        # Use last N matches for Kalman filtering
        games_history = player.get('games_history', [])
        if games_history and len(games_history) >= 3:
            initial_mean = sum(games_history[:3]) / 3
            initial_var = 2.0
            process_var = 1.0
            measurement_var = 2.0
            kf = KalmanFilter(initial_mean, initial_var, process_var, measurement_var)
            kalman_means = []
            kalman_vars = []
            for obs in games_history:
                mean, var, _ = kf.update(obs)
                kalman_means.append(mean)
                kalman_vars.append(var)
            kalman_games_mean = kalman_means[-1]
            kalman_games_var = kalman_vars[-1]
        else:
            kalman_games_mean = player['avg_games_per_match']
            kalman_games_var = 2.0

        # Bayesian smoothing for low sample
        player_n = len(games_history) if games_history else 0
        prior_mean = 12.0
        prior_n = 8
        if player_n < 8:
            filtered_games_mean = bayesian_shrinkage(kalman_games_mean, player_n, prior_mean, prior_n)
        else:
            filtered_games_mean = kalman_games_mean

        # Adjust for opponent strength
        opponent_avg = opponent['avg_games_per_match']
        adj_mean = filtered_games_mean
        if opponent_avg < 11.0:
            adj_mean += 1.5
        elif opponent_avg > 15.0:
            adj_mean -= 1.2
        # Adjust for player style matchup
        if player['player_style'] == 'big_server' and opponent['player_style'] == 'baseline_grinder':
            adj_mean += 0.8
        elif player['player_style'] == 'baseline_grinder' and opponent['player_style'] == 'big_server':
            adj_mean -= 0.8

        diff = adj_mean - line
        probability = self._calculate_probability(diff, variance=kalman_games_var)

        return {
            'prediction': adj_mean,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': self._assign_confidence('games_won', abs(diff)),
            'filtered_games_mean': filtered_games_mean,
            'kalman_games_var': kalman_games_var,
            'raw_games_mean': player['avg_games_per_match']
        }
    
    
    def _predict_aces(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict aces
        
        Confidence: MEDIUM (player-dependent, surface-dependent)
        """
        # Use last N matches for Kalman filtering
        aces_history = player.get('aces_history', [])
        if aces_history and len(aces_history) >= 3:
            initial_mean = sum(aces_history[:3]) / 3
            initial_var = 2.0
            process_var = 1.0
            measurement_var = 2.0
            kf = KalmanFilter(initial_mean, initial_var, process_var, measurement_var)
            kalman_means = []
            kalman_vars = []
            for obs in aces_history:
                mean, var, _ = kf.update(obs)
                kalman_means.append(mean)
                kalman_vars.append(var)
            kalman_aces_mean = kalman_means[-1]
            kalman_aces_var = kalman_vars[-1]
        else:
            kalman_aces_mean = player['avg_aces']
            kalman_aces_var = 2.0

        # Bayesian smoothing for low sample
        player_n = len(aces_history) if aces_history else 0
        prior_mean = 4.0
        prior_n = 8
        if player_n < 8:
            filtered_aces_mean = bayesian_shrinkage(kalman_aces_mean, player_n, prior_mean, prior_n)
        else:
            filtered_aces_mean = kalman_aces_mean

        # Already surface-adjusted by player_db
        base = filtered_aces_mean
        opponent_style = opponent['player_style']
        if opponent_style == 'aggressive_returner':
            base *= 0.85

        diff = base - line
        probability = self._calculate_probability(diff, variance=kalman_aces_var)

        return {
            'prediction': base,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': self._assign_confidence('aces', abs(diff)),
            'filtered_aces_mean': filtered_aces_mean,
            'kalman_aces_var': kalman_aces_var,
            'raw_aces_mean': player['avg_aces']
        }
    
    
    def _predict_breakpoints(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict breakpoints won
        
        Confidence: MEDIUM (matchup-dependent)
        """
        base = player['avg_breakpoints_won']
        
        # Adjust based on opponent serve strength
        opponent_style = opponent['player_style']
        
        if opponent_style == 'big_server':
            base *= 0.75  # Harder to break big server
        elif opponent_style == 'baseline_grinder':
            base *= 1.15  # Easier to break grinder
        
        diff = base - line
        probability = self._calculate_probability(diff, variance=1.8)
        
        return {
            'prediction': base,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': self._assign_confidence('breakpoints_won', abs(diff))
        }
    
    
    def _predict_fantasy_score(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict PrizePicks fantasy score
        
        Confidence: MEDIUM-LOW (platform-specific scoring)
        """
        base = player.get('fantasy_score_avg', 18.0)
        
        # Adjust based on opponent quality
        opponent_rank = opponent.get('ranking', 100)
        
        if opponent_rank > 80:  # Weak opponent
            base += 2.5
        elif opponent_rank < 20:  # Top opponent
            base -= 1.8
        
        diff = base - line
        probability = self._calculate_probability(diff, variance=2.5)
        
        return {
            'prediction': base,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': self._assign_confidence('fantasy_score', abs(diff))
        }
    
    
    def _predict_games_played(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict total games in match
        
        Confidence: MEDIUM (depends on competitiveness)
        """
        # Sum both players' averages
        base = player['avg_games_per_match'] + opponent['avg_games_per_match']
        
        # Adjust for ranking difference (blowout vs competitive)
        rank_diff = abs(player.get('ranking', 50) - opponent.get('ranking', 50))
        
        if rank_diff > 60:
            base -= 2.5  # Blowout expected
        elif rank_diff < 10:
            base += 1.5  # Competitive match
        
        diff = base - line
        probability = self._calculate_probability(diff, variance=3.0)
        
        return {
            'prediction': base,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': self._assign_confidence('games_played', abs(diff))
        }
    
    
    def _predict_first_set_games(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict first set games won
        
        Confidence: MEDIUM-HIGH
        """
        # Approximately 42% of total match games
        total_games = player['avg_games_per_match']
        base = total_games * 0.42
        
        # Boost if strong first set player
        first_set_rate = player.get('first_set_win_rate', 0.60)
        if first_set_rate > 0.68:
            base += 0.6
        elif first_set_rate < 0.55:
            base -= 0.4
        
        diff = base - line
        probability = self._calculate_probability(diff, variance=1.2)
        
        return {
            'prediction': base,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': self._assign_confidence('first_set_games_won', abs(diff))
        }
    
    
    def _predict_double_faults(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict double faults
        
        Confidence: LOW (high variance)
        """
        base = player.get('avg_double_faults', 2.5)
        
        # Surface adjustment
        if self.surface == 'grass':
            base *= 0.9  # Fewer DFs on grass
        elif self.surface == 'clay':
            base *= 1.1  # More DFs on clay
        
        diff = base - line
        probability = self._calculate_probability(diff, variance=2.5)
        
        return {
            'prediction': base,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': 'LOW'  # Always low confidence for DFs
        }
    
    
    def _predict_sets_won(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict sets won (usually 0.5, 1.5, or 2.5)
        
        Confidence: MEDIUM
        """
        # Use first set win rate as proxy
        first_set_rate = player.get('first_set_win_rate', 0.60)
        
        # Expected sets won (0-2 in best of 3, 0-3 in best of 5)
        # Assume best of 3 for most matches
        expected_sets = 1.2 if first_set_rate > 0.65 else 0.9
        
        diff = expected_sets - line
        probability = self._calculate_probability(diff, variance=0.8)
        
        return {
            'prediction': expected_sets,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': self._assign_confidence('sets_won', abs(diff))
        }
    
    
    def _predict_tiebreakers(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """
        Predict tiebreakers played
        
        Confidence: LOW (rare event, high variance)
        """
        # Very simple model: big servers more likely to have TBs
        player_style = player['player_style']
        opponent_style = opponent['player_style']
        
        base = 0.3  # Low baseline
        
        if player_style == 'big_server' and opponent_style == 'big_server':
            base = 0.8  # Both hold serve well
        elif player_style == 'big_server' or opponent_style == 'big_server':
            base = 0.5
        
        diff = base - line
        probability = self._calculate_probability(diff, variance=0.5)
        
        return {
            'prediction': base,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(diff),
            'confidence': 'LOW'  # Always low for tiebreakers
        }
    
    
    def _predict_generic(self, line: float) -> Dict:
        """Generic prediction for unknown markets"""
        return {
            'prediction': line,
            'probability_over': 0.50,
            'probability_under': 0.50,
            'edge_value': 0.0,
            'confidence': 'LOW'
        }
    
    
    def _calculate_probability(self, diff: float, variance: float) -> float:
        """
        Calculate probability based on prediction vs line difference
        
        Args:
            diff: prediction - line
            variance: Market-specific variance
            
        Returns:
            Probability of OVER (0.0 to 1.0)
        """
        # Sigmoid-like probability curve adjusted for variance
        normalized_diff = diff / variance
        
        if normalized_diff >= 2.0:
            return 0.80
        elif normalized_diff >= 1.5:
            return 0.75
        elif normalized_diff >= 1.0:
            return 0.68
        elif normalized_diff >= 0.5:
            return 0.62
        elif normalized_diff >= 0.25:
            return 0.58
        elif normalized_diff >= 0:
            return 0.54
        elif normalized_diff >= -0.25:
            return 0.48
        elif normalized_diff >= -0.5:
            return 0.42
        elif normalized_diff >= -1.0:
            return 0.35
        elif normalized_diff >= -1.5:
            return 0.28
        else:
            return 0.22
    
    
    def _assign_confidence(self, market_type: str, edge: float) -> str:
        """
        Assign confidence level based on market type and edge
        
        Returns: 'HIGH', 'MEDIUM', or 'LOW'
        """
        # Market-specific confidence caps
        high_confidence_markets = ['games_won', 'first_set_games_won']
        medium_confidence_markets = ['aces', 'breakpoints_won', 'games_played', 'sets_won']
        low_confidence_markets = ['double_faults', 'tiebreakers_played', 'fantasy_score']
        
        if market_type in low_confidence_markets:
            return 'LOW'
        
        if market_type in high_confidence_markets:
            if edge >= 1.5:
                return 'HIGH'
            elif edge >= 0.8:
                return 'MEDIUM'
            else:
                return 'LOW'
        
        if market_type in medium_confidence_markets:
            if edge >= 2.0:
                return 'HIGH'
            elif edge >= 1.0:
                return 'MEDIUM'
            else:
                return 'LOW'
        
        return 'MEDIUM'  # Default


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def predict_tennis_prop(player_name: str, opponent_name: str, 
                       market_type: str, line: float, surface: str = 'hard') -> Dict:
    """
    Convenience function for quick prop prediction
    
    Args:
        player_name: Player name
        opponent_name: Opponent name
        market_type: Market (e.g., 'games_won')
        line: DFS line value
        surface: Court surface
        
    Returns:
        Prediction result
    """
    model = TennisPropsModel(surface=surface)
    return model.predict_prop(player_name, opponent_name, market_type, line)


# ============================================================================
# CLI FOR TESTING
# ============================================================================

def main():
    """Test props model"""
    import sys
    
    if len(sys.argv) < 5:
        print("Usage: python tennis_props_model.py <player> <opponent> <market> <line> [surface]")
        print("\nExample: python tennis_props_model.py 'Aryna Sabalenka' 'Elina Svitolina' games_won 11.5 hard")
        sys.exit(1)
    
    player = sys.argv[1]
    opponent = sys.argv[2]
    market = sys.argv[3]
    line = float(sys.argv[4])
    surface = sys.argv[5] if len(sys.argv) > 5 else 'hard'
    
    # Predict
    result = predict_tennis_prop(player, opponent, market, line, surface)
    
    # Display
    print(f"\n{'='*70}")
    print(f"TENNIS PROPS PREDICTION")
    print(f"{'='*70}\n")
    
    print(f"Player: {player} vs {opponent}")
    print(f"Market: {market}")
    print(f"Line: {line}")
    print(f"Surface: {surface.upper()}\n")
    
    print(f"Prediction: {result['prediction']:.2f}")
    print(f"Edge: {result['edge_value']:.2f}\n")
    
    print(f"Probability OVER: {result['probability_over']:.1%}")
    print(f"Probability UNDER: {result['probability_under']:.1%}\n")
    
    print(f"Confidence: {result['confidence']}")
    
    # Recommendation
    if result['probability_over'] > result['probability_under']:
        direction = 'MORE/HIGHER'
        prob = result['probability_over']
    else:
        direction = 'LESS/LOWER'
        prob = result['probability_under']
    
    # Tier
    if prob >= 0.75:
        tier = 'SLAM'
    elif prob >= 0.65:
        tier = 'STRONG'
    elif prob >= 0.55:
        tier = 'LEAN'
    else:
        tier = 'NO PLAY'
    
    print(f"\nRecommendation: Bet {direction}")
    print(f"Tier: {tier}")


if __name__ == "__main__":
    main()
