"""
UNDERDOG TENNIS ANALYSIS PIPELINE
Complete end-to-end workflow from text file → recommendations

Usage:
    python underdog_tennis_pipeline.py underdog_props.txt
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import parsers and analyzers
from underdog_text_parser import UnderdogTextParser, UnderdogPropsAnalyzer

# Add config to path for imports
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.underdog_tennis_thresholds import (
    get_underdog_threshold,
    get_market_priority,
    validate_underdog_market,
    UNDERDOG_TENNIS_CAPS
)


# ============================================================================
# MOCK PLAYER DATABASE (Replace with your actual database)
# ============================================================================

MOCK_PLAYER_DATA = {
    'Aryna Sabalenka': {
        'avg_games_per_match': 14.2,
        'avg_aces': 5.8,
        'first_set_win_rate': 0.72,
        'player_style': 'big_server',
        'surface': 'hard'
    },
    'Novak Djokovic': {
        'avg_games_per_match': 13.5,
        'avg_aces': 4.2,
        'first_set_win_rate': 0.68,
        'player_style': 'all_court',
        'surface': 'hard'
    },
    'Jannik Sinner': {
        'avg_games_per_match': 15.1,
        'avg_aces': 8.3,
        'first_set_win_rate': 0.65,
        'player_style': 'aggressive_returner',
        'surface': 'hard'
    },
    'Carlos Alcaraz': {
        'avg_games_per_match': 16.2,
        'avg_aces': 6.5,
        'first_set_win_rate': 0.70,
        'player_style': 'all_court',
        'surface': 'hard'
    },
    'Alexander Zverev': {
        'avg_games_per_match': 14.8,
        'avg_aces': 9.2,
        'first_set_win_rate': 0.64,
        'player_style': 'big_server',
        'surface': 'hard'
    },
    'Jessica Pegula': {
        'avg_games_per_match': 12.4,
        'avg_aces': 2.1,
        'first_set_win_rate': 0.61,
        'player_style': 'baseline_grinder',
        'surface': 'hard'
    },
    'Elena Rybakina': {
        'avg_games_per_match': 13.8,
        'avg_aces': 7.8,
        'first_set_win_rate': 0.69,
        'player_style': 'big_server',
        'surface': 'hard'
    },
    'Elina Svitolina': {
        'avg_games_per_match': 11.2,
        'avg_aces': 1.8,
        'first_set_win_rate': 0.58,
        'player_style': 'baseline_grinder',
        'surface': 'hard'
    }
}


def get_player_data(player_name: str) -> dict:
    """
    Get player data (mock - replace with your database)
    """
    # Try exact match first
    if player_name in MOCK_PLAYER_DATA:
        return MOCK_PLAYER_DATA[player_name]
    
    # Try partial match (e.g., "Thiago Agustin Tirante" → match by last name)
    last_name = player_name.split()[-1].lower()
    for full_name, data in MOCK_PLAYER_DATA.items():
        if last_name in full_name.lower():
            return data
    
    # Default for unknown players
    return {
        'avg_games_per_match': 12.0,
        'avg_aces': 4.0,
        'first_set_win_rate': 0.60,
        'player_style': 'all_court',
        'surface': 'hard'
    }


# ============================================================================
# SIMPLE PREDICTION MODEL (Replace with your actual model)
# ============================================================================

class SimpleTennisPredictionModel:
    """
    Simple prediction model for demonstration
    
    Replace with your actual model that uses:
    - Historical player stats
    - Opponent matchup data
    - Surface adjustments
    - Recent form
    - H2H history
    """
    
    @staticmethod
    def predict_games_won(player_data: dict, opponent_data: dict, 
                         underdog_line: float) -> dict:
        """
        Predict games won
        
        Simple model: player avg + slight boost if opponent weak
        """
        base_prediction = player_data['avg_games_per_match']
        
        # Slight adjustment based on opponent
        opponent_avg = opponent_data.get('avg_games_per_match', 12.0)
        if opponent_avg < 11.0:  # Weak opponent
            base_prediction += 1.5
        elif opponent_avg > 15.0:  # Strong opponent
            base_prediction -= 1.0
        
        # Calculate probability of going OVER underdog line
        diff = base_prediction - underdog_line
        
        # Simple sigmoid-like probability
        if diff >= 2.0:
            probability = 0.75
        elif diff >= 1.0:
            probability = 0.68
        elif diff >= 0.5:
            probability = 0.62
        elif diff >= 0:
            probability = 0.56
        elif diff >= -1.0:
            probability = 0.45
        else:
            probability = 0.38
        
        return {
            'prediction': base_prediction,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(base_prediction - underdog_line)
        }
    
    
    @staticmethod
    def predict_aces(player_data: dict, opponent_data: dict,
                    underdog_line: float) -> dict:
        """Predict aces"""
        base_prediction = player_data.get('avg_aces', 4.0)
        
        # Surface boost (if grass court, increase aces)
        surface = player_data.get('surface', 'hard')
        if surface == 'grass':
            base_prediction *= 1.4
        elif surface == 'clay':
            base_prediction *= 0.7
        
        diff = base_prediction - underdog_line
        
        if diff >= 2.0:
            probability = 0.72
        elif diff >= 1.0:
            probability = 0.66
        elif diff >= 0.5:
            probability = 0.60
        elif diff >= 0:
            probability = 0.54
        else:
            probability = 0.42
        
        return {
            'prediction': base_prediction,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(base_prediction - underdog_line)
        }
    
    
    @staticmethod
    def predict_first_set_games(player_data: dict, opponent_data: dict,
                               underdog_line: float) -> dict:
        """Predict first set games won"""
        # Simpler - about 40% of total games
        total_games_pred = player_data['avg_games_per_match']
        base_prediction = total_games_pred * 0.42
        
        # Boost if strong first set player
        first_set_rate = player_data.get('first_set_win_rate', 0.60)
        if first_set_rate > 0.68:
            base_prediction += 0.5
        
        diff = base_prediction - underdog_line
        
        if diff >= 1.0:
            probability = 0.70
        elif diff >= 0.5:
            probability = 0.64
        elif diff >= 0:
            probability = 0.58
        else:
            probability = 0.45
        
        return {
            'prediction': base_prediction,
            'probability_over': probability,
            'probability_under': 1.0 - probability,
            'edge_value': abs(base_prediction - underdog_line)
        }


# ============================================================================
# RECOMMENDATION ENGINE
# ============================================================================

class UnderdogRecommendationEngine:
    """Generate betting recommendations from predictions"""
    
    def __init__(self, min_edge: float = 0.5, min_probability: float = 0.60):
        self.min_edge = min_edge
        self.min_probability = min_probability
        self.model = SimpleTennisPredictionModel()
    
    
    def analyze_props(self, props: list) -> list:
        """
        Analyze all props and generate recommendations
        
        Returns list of recommendations sorted by quality
        """
        recommendations = []
        
        for prop in props:
            player_name = prop['player_name']
            opponent = prop.get('opponent', 'Unknown')
            
            # Get player data
            player_data = get_player_data(player_name)
            opponent_data = get_player_data(opponent)
            
            # Analyze each market
            for market_type, market_data in prop['markets'].items():
                rec = self._analyze_market(
                    player_name=player_name,
                    opponent=opponent,
                    market_type=market_type,
                    underdog_line=market_data['line'],
                    player_data=player_data,
                    opponent_data=opponent_data,
                    match_time=prop.get('match_time'),
                    tournament_round=prop.get('tournament_round')
                )
                
                if rec:
                    recommendations.append(rec)
        
        # Sort by priority and probability
        recommendations.sort(
            key=lambda x: (x['priority_rank'], -x['probability'], -x['edge']),
            reverse=False
        )
        
        return recommendations
    
    
    def _analyze_market(self, player_name: str, opponent: str,
                       market_type: str, underdog_line: float,
                       player_data: dict, opponent_data: dict,
                       match_time: str, tournament_round: str) -> dict:
        """Analyze single market and generate recommendation"""
        
        # Get market priority
        priority = get_market_priority(market_type)
        
        # Get prediction based on market type
        if market_type == 'games_won':
            prediction = self.model.predict_games_won(
                player_data, opponent_data, underdog_line
            )
        elif market_type == 'aces':
            prediction = self.model.predict_aces(
                player_data, opponent_data, underdog_line
            )
        elif market_type == 'first_set_games_won':
            prediction = self.model.predict_first_set_games(
                player_data, opponent_data, underdog_line
            )
        else:
            # Skip low-priority markets for now
            return None
        
        # Check if meets minimum criteria
        max_prob = max(prediction['probability_over'], prediction['probability_under'])
        edge = prediction['edge_value']
        
        if max_prob < self.min_probability or edge < self.min_edge:
            return None
        
        # Determine direction
        if prediction['probability_over'] > prediction['probability_under']:
            direction = 'HIGHER'
            probability = prediction['probability_over']
        else:
            direction = 'LOWER'
            probability = prediction['probability_under']
        
        # Assign tier
        tier = self._assign_tier(probability)
        
        # Get threshold for this market
        threshold = get_underdog_threshold(
            market_type=market_type,
            player_style=player_data.get('player_style'),
            tournament_stage=tournament_round or 'early_rounds',
            surface=player_data.get('surface', 'hard')
        )
        
        # Build recommendation
        return {
            'player': player_name,
            'opponent': opponent,
            'match_time': match_time,
            'tournament_round': tournament_round,
            'market': market_type,
            'underdog_line': underdog_line,
            'model_prediction': prediction['prediction'],
            'probability': probability,
            'direction': direction,
            'tier': tier,
            'edge': edge,
            'priority': priority,
            'priority_rank': {'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}[priority],
            'threshold': threshold
        }
    
    
    def _assign_tier(self, probability: float) -> str:
        """Assign tier based on probability (SOP v2.1 Section 5 Rule C2)"""
        if probability >= 0.75:
            return 'SLAM'
        elif probability >= 0.65:
            return 'STRONG'
        elif probability >= 0.55:
            return 'LEAN'
        else:
            return 'NO PLAY'


# ============================================================================
# REPORT GENERATOR
# ============================================================================

def generate_report(recommendations: list, output_file: str = None):
    """Generate formatted report of recommendations"""
    
    report = []
    report.append("\n" + "="*80)
    report.append("🎾 UNDERDOG TENNIS BETTING RECOMMENDATIONS")
    report.append("="*80)
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Recommendations: {len(recommendations)}\n")
    
    # Group by tier
    tiers = {}
    for rec in recommendations:
        tier = rec['tier']
        if tier not in tiers:
            tiers[tier] = []
        tiers[tier].append(rec)
    
    # Display by tier
    for tier in ['SLAM', 'STRONG', 'LEAN']:
        if tier not in tiers:
            continue
        
        report.append("\n" + "-"*80)
        report.append(f"{'🔥' if tier == 'SLAM' else '✅' if tier == 'STRONG' else '⚠️'} {tier} TIER ({len(tiers[tier])} picks)")
        report.append("-"*80)
        
        for rec in tiers[tier]:
            report.append(f"\n🎯 {rec['player']} vs {rec['opponent']}")
            report.append(f"   Match: {rec['match_time']} | {rec['tournament_round'] or 'N/A'}")
            report.append(f"   Market: {rec['market']}")
            report.append(f"   Underdog Line: {rec['underdog_line']}")
            report.append(f"   Model Prediction: {rec['model_prediction']:.2f}")
            report.append(f"   Recommendation: Bet {rec['direction']}")
            report.append(f"   Probability: {rec['probability']:.1%}")
            report.append(f"   Edge: {rec['edge']:.2f}")
            report.append(f"   Priority: {rec['priority']}")
    
    # Join and print
    report_text = '\n'.join(report)
    print(report_text)
    
    # Save to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
        print(f"\n✅ Report saved to {output_file}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main analysis pipeline"""
    
    if len(sys.argv) < 2:
        print("Usage: python underdog_tennis_pipeline.py <underdog_props.txt> [--output report.txt]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == '--output' else None
    
    print("🎾 Starting Underdog Tennis Analysis Pipeline...")
    print(f"📂 Input: {input_file}\n")
    
    # Step 1: Parse Underdog props
    print("Step 1: Parsing Underdog props...")
    parser = UnderdogTextParser()
    props = parser.parse_file(input_file)
    print(f"✅ Parsed {len(props)} players\n")
    
    # Step 2: Analyze and generate recommendations
    print("Step 2: Generating recommendations...")
    engine = UnderdogRecommendationEngine(
        min_edge=0.5,
        min_probability=0.60
    )
    recommendations = engine.analyze_props(props)
    print(f"✅ Generated {len(recommendations)} recommendations\n")
    
    # Step 3: Generate report
    print("Step 3: Generating report...")
    generate_report(recommendations, output_file)


if __name__ == "__main__":
    main()
