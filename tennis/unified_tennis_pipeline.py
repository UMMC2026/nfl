"""
UNIFIED TENNIS ANALYSIS PIPELINE
Handles PrizePicks, Underdog, and other DFS platforms

Usage:
    python unified_tennis_pipeline.py prizepicks_props.txt
    python unified_tennis_pipeline.py underdog_props.txt
    python unified_tennis_pipeline.py both_platforms.txt --output recommendations.txt
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Add project root to path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import parsers
from prizepicks_parser import UnifiedTennisParser


# ============================================================================
# PLATFORM-SPECIFIC THRESHOLDS
# ============================================================================

PLATFORM_ADJUSTMENTS = {
    'prizepicks': {
        'fantasy_score': {
            'threshold': 0.62,
            'description': 'PrizePicks unique scoring system'
        },
        'games_won': {
            'threshold': 0.70,
            'notes': 'Align with Underdog'
        }
    },
    'underdog': {
        'games_won': {
            'threshold': 0.70
        },
        'aces': {
            'threshold': 0.65
        }
    }
}


# ============================================================================
# MOCK PLAYER DATABASE
# ============================================================================

PLAYER_DATABASE = {
    'Aryna Sabalenka': {
        'avg_games_per_match': 14.2,
        'avg_aces': 5.8,
        'avg_breakpoints_won': 3.8,
        'first_set_win_rate': 0.72,
        'player_style': 'big_server',
        'surface': 'hard',
        'fantasy_score_avg': 22.5
    },
    'Elina Svitolina': {
        'avg_games_per_match': 11.2,
        'avg_aces': 1.8,
        'avg_breakpoints_won': 2.2,
        'first_set_win_rate': 0.58,
        'player_style': 'baseline_grinder',
        'surface': 'hard',
        'fantasy_score_avg': 15.3
    },
    'Novak Djokovic': {
        'avg_games_per_match': 13.5,
        'avg_aces': 4.2,
        'avg_breakpoints_won': 3.1,
        'first_set_win_rate': 0.68,
        'player_style': 'all_court',
        'surface': 'hard',
        'fantasy_score_avg': 24.8
    },
    'Jannik Sinner': {
        'avg_games_per_match': 15.1,
        'avg_aces': 8.3,
        'avg_breakpoints_won': 4.2,
        'first_set_win_rate': 0.65,
        'player_style': 'aggressive_returner',
        'surface': 'hard',
        'fantasy_score_avg': 26.2
    },
    'Carlos Alcaraz': {
        'avg_games_per_match': 16.2,
        'avg_aces': 6.5,
        'avg_breakpoints_won': 4.8,
        'first_set_win_rate': 0.70,
        'player_style': 'all_court',
        'surface': 'hard',
        'fantasy_score_avg': 28.1
    },
    'Alexander Zverev': {
        'avg_games_per_match': 14.8,
        'avg_aces': 9.2,
        'avg_breakpoints_won': 3.5,
        'first_set_win_rate': 0.64,
        'player_style': 'big_server',
        'surface': 'hard',
        'fantasy_score_avg': 25.4
    },
    'Jessica Pegula': {
        'avg_games_per_match': 12.4,
        'avg_aces': 2.1,
        'avg_breakpoints_won': 2.8,
        'first_set_win_rate': 0.61,
        'player_style': 'baseline_grinder',
        'surface': 'hard',
        'fantasy_score_avg': 18.2
    },
    'Elena Rybakina': {
        'avg_games_per_match': 13.8,
        'avg_aces': 7.8,
        'avg_breakpoints_won': 3.6,
        'first_set_win_rate': 0.69,
        'player_style': 'big_server',
        'surface': 'hard',
        'fantasy_score_avg': 22.9
    },
    'Donna Vekic': {
        'avg_games_per_match': 12.1,
        'avg_aces': 4.2,
        'avg_breakpoints_won': 2.9,
        'first_set_win_rate': 0.59,
        'player_style': 'all_court',
        'surface': 'hard',
        'fantasy_score_avg': 17.8
    },
    'Lin Zhu': {
        'avg_games_per_match': 10.5,
        'avg_aces': 1.2,
        'avg_breakpoints_won': 1.8,
        'first_set_win_rate': 0.52,
        'player_style': 'baseline_grinder',
        'surface': 'hard',
        'fantasy_score_avg': 13.4
    }
}


def get_player_data(player_name: str) -> dict:
    """Get player data with fuzzy matching"""
    # Exact match
    if player_name in PLAYER_DATABASE:
        return PLAYER_DATABASE[player_name]
    
    # Fuzzy match by last name
    last_name = player_name.split()[-1].lower()
    for full_name, data in PLAYER_DATABASE.items():
        if last_name in full_name.lower():
            return data
    
    # Default for unknown players
    return {
        'avg_games_per_match': 12.0,
        'avg_aces': 4.0,
        'avg_breakpoints_won': 2.5,
        'first_set_win_rate': 0.60,
        'player_style': 'all_court',
        'surface': 'hard',
        'fantasy_score_avg': 18.0
    }


# ============================================================================
# UNIFIED PREDICTION MODEL
# ============================================================================

class UnifiedTennisPredictionModel:
    """Prediction model that works across all platforms"""
    
    @staticmethod
    def predict_market(player_data: dict, opponent_data: dict,
                      market_type: str, line: float) -> dict:
        """
        Unified prediction for any market type
        """
        # Route to specific prediction method
        if market_type == 'games_won':
            return UnifiedTennisPredictionModel._predict_games_won(
                player_data, opponent_data, line
            )
        elif market_type == 'aces':
            return UnifiedTennisPredictionModel._predict_aces(
                player_data, opponent_data, line
            )
        elif market_type == 'breakpoints_won':
            return UnifiedTennisPredictionModel._predict_breakpoints(
                player_data, opponent_data, line
            )
        elif market_type == 'fantasy_score':
            return UnifiedTennisPredictionModel._predict_fantasy_score(
                player_data, opponent_data, line
            )
        elif market_type == 'games_played':
            return UnifiedTennisPredictionModel._predict_games_played(
                player_data, opponent_data, line
            )
        else:
            # Generic prediction for unknown markets
            return {
                'prediction': line,
                'probability_over': 0.50,
                'probability_under': 0.50,
                'edge_value': 0.0
            }
    
    
    @staticmethod
    def _predict_games_won(player_data: dict, opponent_data: dict, line: float) -> dict:
        """Predict games won"""
        base = player_data['avg_games_per_match']
        opponent_avg = opponent_data['avg_games_per_match']
        
        # Adjust based on opponent strength
        if opponent_avg < 11.0:
            base += 1.5
        elif opponent_avg > 15.0:
            base -= 1.0
        
        diff = base - line
        
        if diff >= 2.0:
            prob = 0.75
        elif diff >= 1.0:
            prob = 0.68
        elif diff >= 0.5:
            prob = 0.62
        elif diff >= 0:
            prob = 0.56
        else:
            prob = 0.45
        
        return {
            'prediction': base,
            'probability_over': prob,
            'probability_under': 1.0 - prob,
            'edge_value': abs(diff)
        }
    
    
    @staticmethod
    def _predict_aces(player_data: dict, opponent_data: dict, line: float) -> dict:
        """Predict aces"""
        base = player_data['avg_aces']
        
        # Surface adjustment
        surface = player_data.get('surface', 'hard')
        if surface == 'grass':
            base *= 1.4
        elif surface == 'clay':
            base *= 0.7
        
        diff = base - line
        
        if diff >= 2.0:
            prob = 0.72
        elif diff >= 1.0:
            prob = 0.66
        elif diff >= 0.5:
            prob = 0.60
        elif diff >= 0:
            prob = 0.54
        else:
            prob = 0.42
        
        return {
            'prediction': base,
            'probability_over': prob,
            'probability_under': 1.0 - prob,
            'edge_value': abs(diff)
        }
    
    
    @staticmethod
    def _predict_breakpoints(player_data: dict, opponent_data: dict, line: float) -> dict:
        """Predict breakpoints won"""
        base = player_data['avg_breakpoints_won']
        opponent_serve = opponent_data.get('player_style', 'all_court')
        
        # Adjust based on opponent serve quality
        if opponent_serve == 'big_server':
            base *= 0.8  # Harder to break
        
        diff = base - line
        
        if diff >= 1.5:
            prob = 0.70
        elif diff >= 1.0:
            prob = 0.64
        elif diff >= 0.5:
            prob = 0.58
        elif diff >= 0:
            prob = 0.52
        else:
            prob = 0.44
        
        return {
            'prediction': base,
            'probability_over': prob,
            'probability_under': 1.0 - prob,
            'edge_value': abs(diff)
        }
    
    
    @staticmethod
    def _predict_fantasy_score(player_data: dict, opponent_data: dict, line: float) -> dict:
        """Predict PrizePicks fantasy score"""
        base = player_data.get('fantasy_score_avg', 18.0)
        opponent_avg = opponent_data.get('fantasy_score_avg', 18.0)
        
        # Adjust based on opponent quality
        if opponent_avg < 15.0:
            base += 2.0
        elif opponent_avg > 25.0:
            base -= 1.5
        
        diff = base - line
        
        if diff >= 3.0:
            prob = 0.72
        elif diff >= 2.0:
            prob = 0.66
        elif diff >= 1.0:
            prob = 0.60
        elif diff >= 0:
            prob = 0.54
        else:
            prob = 0.45
        
        return {
            'prediction': base,
            'probability_over': prob,
            'probability_under': 1.0 - prob,
            'edge_value': abs(diff)
        }
    
    
    @staticmethod
    def _predict_games_played(player_data: dict, opponent_data: dict, line: float) -> dict:
        """Predict total games in match"""
        # Sum both players' averages
        base = player_data['avg_games_per_match'] + opponent_data['avg_games_per_match']
        
        # Adjust for competitiveness
        rank_diff = abs(player_data.get('ranking', 50) - opponent_data.get('ranking', 50))
        if rank_diff > 50:
            base -= 2.0  # Blowout expected
        
        diff = base - line
        
        if diff >= 3.0:
            prob = 0.68
        elif diff >= 2.0:
            prob = 0.62
        elif diff >= 1.0:
            prob = 0.56
        elif diff >= 0:
            prob = 0.52
        else:
            prob = 0.46
        
        return {
            'prediction': base,
            'probability_over': prob,
            'probability_under': 1.0 - prob,
            'edge_value': abs(diff)
        }


# ============================================================================
# UNIFIED RECOMMENDATION ENGINE
# ============================================================================

class UnifiedRecommendationEngine:
    """Generate recommendations across all platforms"""
    
    def __init__(self, min_edge: float = 0.5, min_probability: float = 0.58):
        self.min_edge = min_edge
        self.min_probability = min_probability
        self.model = UnifiedTennisPredictionModel()
    
    
    def analyze_props(self, props: List[Dict]) -> List[Dict]:
        """Analyze props from any platform"""
        recommendations = []
        
        for prop in props:
            platform = prop.get('platform', 'unknown')
            player_name = prop['player_name']
            opponent = prop.get('opponent', 'Unknown')
            
            # Get player data
            player_data = get_player_data(player_name)
            opponent_data = get_player_data(opponent)
            
            # Analyze each market
            for market_type, market_data in prop['markets'].items():
                rec = self._analyze_market(
                    platform=platform,
                    player_name=player_name,
                    opponent=opponent,
                    market_type=market_type,
                    line=market_data['line'],
                    player_data=player_data,
                    opponent_data=opponent_data,
                    match_time=prop.get('match_time'),
                    popularity=market_data.get('popularity')
                )
                
                if rec:
                    recommendations.append(rec)
        
        # Sort by quality
        recommendations.sort(
            key=lambda x: (-x['probability'], -x['edge']),
            reverse=False
        )
        
        return recommendations
    
    
    def _analyze_market(self, platform: str, player_name: str, opponent: str,
                       market_type: str, line: float, player_data: dict,
                       opponent_data: dict, match_time: str, popularity: str) -> dict:
        """Analyze single market"""
        
        # Get prediction
        prediction = self.model.predict_market(
            player_data, opponent_data, market_type, line
        )
        
        # Check minimum criteria
        max_prob = max(prediction['probability_over'], prediction['probability_under'])
        edge = prediction['edge_value']
        
        if max_prob < self.min_probability or edge < self.min_edge:
            return None
        
        # Determine direction
        if prediction['probability_over'] > prediction['probability_under']:
            direction = 'MORE/HIGHER'
            probability = prediction['probability_over']
        else:
            direction = 'LESS/LOWER'
            probability = prediction['probability_under']
        
        # Assign tier
        tier = self._assign_tier(probability)
        
        return {
            'platform': platform,
            'player': player_name,
            'opponent': opponent,
            'match_time': match_time,
            'market': market_type,
            'line': line,
            'prediction': prediction['prediction'],
            'probability': probability,
            'direction': direction,
            'tier': tier,
            'edge': edge,
            'popularity': popularity
        }
    
    
    def _assign_tier(self, probability: float) -> str:
        """Assign SOP v2.1 tier"""
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

def generate_unified_report(recommendations: List[Dict], output_file: str = None):
    """Generate formatted recommendation report"""
    
    report = []
    report.append("\n" + "="*80)
    report.append("🎾 UNIFIED TENNIS BETTING RECOMMENDATIONS")
    report.append("="*80)
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Recommendations: {len(recommendations)}\n")
    
    # Group by platform
    platforms = {}
    for rec in recommendations:
        platform = rec['platform']
        if platform not in platforms:
            platforms[platform] = []
        platforms[platform].append(rec)
    
    # Display by platform
    for platform, recs in platforms.items():
        report.append(f"\n{'='*80}")
        report.append(f"📱 {platform.upper()} ({len(recs)} recommendations)")
        report.append(f"{'='*80}")
        
        # Group by tier
        tiers = {}
        for rec in recs:
            tier = rec['tier']
            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append(rec)
        
        for tier in ['SLAM', 'STRONG', 'LEAN']:
            if tier not in tiers:
                continue
            
            report.append(f"\n{'-'*80}")
            report.append(f"{'🔥' if tier == 'SLAM' else '✅' if tier == 'STRONG' else '⚠️'} {tier} TIER ({len(tiers[tier])} picks)")
            report.append(f"{'-'*80}")
            
            for rec in tiers[tier]:
                report.append(f"\n🎯 {rec['player']} vs {rec['opponent']}")
                report.append(f"   Match: {rec['match_time']}")
                report.append(f"   Market: {rec['market']}")
                report.append(f"   Line: {rec['line']}")
                report.append(f"   Prediction: {rec['prediction']:.2f}")
                report.append(f"   Recommendation: Bet {rec['direction']}")
                report.append(f"   Probability: {rec['probability']:.1%}")
                report.append(f"   Edge: {rec['edge']:.2f}")
                if rec.get('popularity'):
                    report.append(f"   Popularity: {rec['popularity']}")
    
    report_text = '\n'.join(report)
    print(report_text)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
        print(f"\n✅ Report saved to {output_file}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main unified pipeline"""
    
    if len(sys.argv) < 2:
        print("Usage: python unified_tennis_pipeline.py <props_file.txt> [--output report.txt]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == '--output' else None
    
    print("🎾 Starting Unified Tennis Analysis Pipeline...")
    print(f"📂 Input: {input_file}\n")
    
    # Step 1: Parse (auto-detect platform)
    print("Step 1: Parsing props (auto-detecting platform)...")
    props = UnifiedTennisParser.parse_file(input_file)
    platform = props[0].get('platform', 'Unknown') if props else 'Unknown'
    print(f"✅ Platform detected: {platform}")
    print(f"✅ Parsed {len(props)} players\n")
    
    # Step 2: Generate recommendations
    print("Step 2: Generating recommendations...")
    engine = UnifiedRecommendationEngine(
        min_edge=0.5,
        min_probability=0.58
    )
    recommendations = engine.analyze_props(props)
    print(f"✅ Generated {len(recommendations)} recommendations\n")
    
    # Step 3: Generate report
    print("Step 3: Generating unified report...")
    generate_unified_report(recommendations, output_file)


if __name__ == "__main__":
    main()
