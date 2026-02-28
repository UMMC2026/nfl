"""
TENNIS EDGE DETECTOR - COMPLETE REPLACEMENT
SOP v2.1 Compliant with Tennis-Specific Confidence Caps

Drop-in replacement for tennis/tennis_edge_detector.py
Fixes: NameError: name 'CONFIDENCE_CAPS' is not defined
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIDENCE CAPS (SOP v2.1 Section 2.4 Compliant)
# ============================================================================

# Canonical caps (from config/thresholds.py)
CONFIDENCE_CAPS = {
    'HIGH': 0.75,
    'MEDIUM': 0.65,
    'LOW': 0.60,
    # Alternate keys for compatibility
    'core': 0.75,
    'volume_micro': 0.65,
    'sequence_early': 0.60,
    'event_binary': 0.55
}

# Tennis-specific market caps
TENNIS_MARKET_CAPS = {
    'games_won': 0.70,
    'total_games_won': 0.70,
    'aces': 0.65,
    'breakpoints_won': 0.60,
    'break_points_won': 0.60,
    'fantasy_score': 0.62,
    'total_games': 0.68,
    'double_faults': 0.56,
    'sets_played': 0.58,
    'tiebreakers_played': 0.55
}


# ============================================================================
# TIER THRESHOLDS (SOP v2.1 Section 5 Rule C2)
# ============================================================================

TIER_THRESHOLDS = {
    'SLAM': 0.75,
    'STRONG': 0.65,
    'LEAN': 0.55,
    'NO_PLAY': 0.00
}


# ============================================================================
# TENNIS EDGE DETECTOR CLASS
# ============================================================================

class TennisEdgeDetector:
    """
    Tennis edge detector with Monte Carlo integration
    
    Compatible with your existing Monte Carlo pipeline while adding
    proper confidence caps and SOP v2.1 compliance
    """
    
    def __init__(self):
        self.confidence_caps = CONFIDENCE_CAPS
        self.market_caps = TENNIS_MARKET_CAPS
        self.tier_thresholds = TIER_THRESHOLDS
    
    
    def batch_analyze(self, mc_results: List[Dict]) -> List[Dict]:
        """
        Analyze batch of Monte Carlo results
        
        Compatible with your existing pipeline structure
        """
        edges = []
        
        for mc_result in mc_results:
            try:
                edge = self.analyze_result(mc_result)
                if edge:
                    edges.append(edge)
            except Exception as e:
                logger.error(f"Error analyzing result: {e}")
                continue
        
        return edges
    
    
    def analyze_result(self, mc_result: Dict) -> Optional[Dict]:
        """
        Analyze single Monte Carlo result and generate edge
        
        Args:
            mc_result: Dict with keys:
                - player: str
                - opponent: str
                - market: str
                - line: float
                - probability: float (from Monte Carlo)
                - confidence: str (HIGH/MEDIUM/LOW)
                - simulation_stats: dict
        
        Returns:
            Edge dict or None if no edge detected
        """
        # Extract data from Monte Carlo result
        player = mc_result.get('player')
        opponent = mc_result.get('opponent')
        market = mc_result.get('market', '').lower()
        line = mc_result.get('line')
        probability = mc_result.get('probability', 0.5)
        confidence = mc_result.get('confidence', 'LOW')
        
        # Validate inputs
        if not player or not market or line is None:
            return None
        
        # Apply confidence cap
        capped_prob = self._apply_confidence_cap(probability, confidence, market)
        
        # Determine direction
        if capped_prob > 0.5:
            direction = 'MORE/HIGHER'
            final_prob = capped_prob
        else:
            direction = 'LESS/LOWER'
            final_prob = 1.0 - capped_prob
        
        # Assign tier
        tier = self._assign_tier(final_prob)
        
        # Only return edges that meet minimum threshold
        if tier == 'NO_PLAY':
            return None
        
        # Calculate edge value
        prediction = mc_result.get('prediction', line)
        edge_value = abs(prediction - line)
        
        # Build edge structure
        edge = {
            'player': player,
            'opponent': opponent,
            'market': market,
            'line': line,
            'prediction': prediction,
            'probability': final_prob,
            'direction': direction,
            'tier': tier,
            'edge': edge_value,
            'confidence_raw': confidence,
            'confidence_capped': capped_prob,
            'simulation_stats': mc_result.get('simulation_stats', {})
        }
        
        return edge
    
    
    def _apply_confidence_cap(self, probability: float, confidence: str, 
                             market: str = '') -> float:
        """
        Apply confidence cap based on confidence level and market type
        
        SOP v2.1 Section 2.4: "Confidence Is Earned, Not Assumed"
        """
        # Get market-specific cap if available
        if market:
            market_cap = self.market_caps.get(market)
            if market_cap:
                return min(probability, market_cap)
        
        # Fall back to generic confidence cap
        cap = self.confidence_caps.get(confidence, 0.60)
        return min(probability, cap)
    
    
    def _assign_tier(self, probability: float) -> str:
        """
        Assign tier based on probability
        
        SOP v2.1 Section 5 Rule C2: Tier Alignment
        
        Args:
            probability: Final probability (0.0 to 1.0)
            
        Returns:
            Tier string: SLAM, STRONG, LEAN, or NO_PLAY
        """
        if probability >= self.tier_thresholds['SLAM']:
            return 'SLAM'
        elif probability >= self.tier_thresholds['STRONG']:
            return 'STRONG'
        elif probability >= self.tier_thresholds['LEAN']:
            return 'LEAN'
        else:
            return 'NO_PLAY'
    
    
    def validate_edge(self, edge: Dict) -> bool:
        """
        Validate edge structure and tier alignment
        
        SOP v2.1 Section 6: Render Gate validation
        """
        required_fields = ['player', 'market', 'line', 'probability', 'tier']
        
        # Check required fields
        for field in required_fields:
            if field not in edge:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate tier matches probability
        probability = edge['probability']
        tier = edge['tier']
        expected_tier = self._assign_tier(probability)
        
        if tier != expected_tier:
            logger.warning(
                f"Tier mismatch: {tier} assigned but probability "
                f"{probability:.3f} suggests {expected_tier}"
            )
            return False
        
        return True


# ============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# ============================================================================

def create_edge_detector() -> TennisEdgeDetector:
    """Factory function for backward compatibility"""
    return TennisEdgeDetector()


def analyze_monte_carlo_results(results: List[Dict]) -> List[Dict]:
    """
    Convenience function for batch analysis
    
    Compatible with your existing Monte Carlo pipeline
    """
    detector = TennisEdgeDetector()
    return detector.batch_analyze(results)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test with sample Monte Carlo results
    sample_results = [
        {
            'player': 'Aryna Sabalenka',
            'opponent': 'Elina Svitolina',
            'market': 'total_games_won',
            'line': 8.5,
            'probability': 0.72,
            'prediction': 11.2,
            'confidence': 'HIGH',
            'simulation_stats': {
                'mean': 11.2,
                'std': 2.1,
                'percentile_75': 12.5
            }
        },
        {
            'player': 'Carlos Alcaraz',
            'opponent': 'Alexander Zverev',
            'market': 'total_games',
            'line': 36.5,
            'probability': 0.45,
            'prediction': 34.2,
            'confidence': 'MEDIUM',
            'simulation_stats': {
                'mean': 34.2,
                'std': 3.8
            }
        },
        {
            'player': 'Alexander Zverev',
            'opponent': 'Carlos Alcaraz',
            'market': 'aces',
            'line': 10.0,
            'probability': 0.68,
            'prediction': 9.2,
            'confidence': 'HIGH',
            'simulation_stats': {
                'mean': 9.2,
                'std': 1.5
            }
        }
    ]
    
    print("="*60)
    print("TESTING TENNIS EDGE DETECTOR")
    print("="*60)
    
    detector = TennisEdgeDetector()
    edges = detector.batch_analyze(sample_results)
    
    print(f"\n✓ Analyzed {len(sample_results)} Monte Carlo results")
    print(f"✓ Generated {len(edges)} edges\n")
    
    for i, edge in enumerate(edges, 1):
        print(f"Edge {i}:")
        print(f"  Player: {edge['player']}")
        print(f"  Market: {edge['market']} {edge['line']}")
        print(f"  Direction: {edge['direction']}")
        print(f"  Probability: {edge['probability']:.1%}")
        print(f"  Tier: {edge['tier']}")
        print(f"  Edge Value: {edge['edge']:.2f}")
        print()
    
    print("="*60)
    print("✅ TEST COMPLETE")
    print("="*60)
