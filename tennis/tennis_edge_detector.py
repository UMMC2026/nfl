"""
TENNIS EDGE DETECTOR v2.0 - SOP v2.1 COMPLIANT
================================================
Upgraded with:
- Correlation group tracking (prevents betting correlated stats)
- Edge collapse logic (HIGHER→highest line, LOWER→lowest line)
- Validation gate (hard fail on duplicate edges)

Drop-in replacement for tennis/tennis_edge_detector.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# TENNIS EDGE DATACLASS
# ============================================================================

@dataclass
class TennisEdge:
    """
    Represents a detected tennis betting edge.
    
    Used by TennisEdgeDetector.batch_analyze() to return structured edge data.
    """
    player: str
    opponent: str = ""
    market: str = ""
    line: float = 0.0
    prediction: float = 0.0
    probability: float = 0.5
    direction: str = "HIGHER"  # HIGHER or LOWER
    tier: str = "NO_PLAY"      # SLAM, STRONG, LEAN, NO_PLAY
    edge: float = 0.0          # Difference between prediction and line
    confidence_raw: str = "LOW"
    confidence_capped: float = 0.5
    simulation_stats: Dict[str, Any] = field(default_factory=dict)
    
    # NEW: Correlation tracking
    correlation_group: str = ""
    is_correlated_with: List[str] = field(default_factory=list)
    is_primary: bool = True  # True if this is the selected edge (not collapsed)
    match_id: str = ""
    
    # Backward compatibility attributes
    stat_type: str = ""
    mean: float = 0.0
    std: float = 0.0
    confidence: str = "LOW"
    
    def __post_init__(self):
        # Sync stat_type with market for backward compatibility
        if not self.stat_type and self.market:
            self.stat_type = self.market
        if not self.market and self.stat_type:
            self.market = self.stat_type
        # Sync confidence
        if not self.confidence:
            self.confidence = self.confidence_raw
        # Sync mean/std from simulation_stats
        if self.simulation_stats:
            if not self.mean:
                self.mean = self.simulation_stats.get('mean', 0.0)
            if not self.std:
                self.std = self.simulation_stats.get('std', 0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary for JSON serialization."""
        return {
            'player': self.player,
            'opponent': self.opponent,
            'market': self.market,
            'stat_type': self.stat_type or self.market,
            'line': self.line,
            'prediction': self.prediction,
            'probability': self.probability,
            'direction': self.direction,
            'tier': self.tier,
            'edge': self.edge,
            'confidence_raw': self.confidence_raw,
            'confidence': self.confidence or self.confidence_raw,
            'confidence_capped': self.confidence_capped,
            'simulation_stats': self.simulation_stats,
            'correlation_group': self.correlation_group,
            'is_correlated_with': self.is_correlated_with,
            'is_primary': self.is_primary,
            'match_id': self.match_id,
            'mean': self.mean,
            'std': self.std
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TennisEdge':
        """Create TennisEdge from dictionary."""
        return cls(
            player=data.get('player', ''),
            opponent=data.get('opponent', ''),
            market=data.get('market', data.get('stat_type', '')),
            line=data.get('line', 0.0),
            prediction=data.get('prediction', 0.0),
            probability=data.get('probability', 0.5),
            direction=data.get('direction', 'HIGHER'),
            tier=data.get('tier', 'NO_PLAY'),
            edge=data.get('edge', 0.0),
            confidence_raw=data.get('confidence_raw', data.get('confidence', 'LOW')),
            confidence_capped=data.get('confidence_capped', 0.5),
            simulation_stats=data.get('simulation_stats', {}),
            correlation_group=data.get('correlation_group', ''),
            is_correlated_with=data.get('is_correlated_with', []),
            is_primary=data.get('is_primary', True),
            match_id=data.get('match_id', ''),
            stat_type=data.get('stat_type', data.get('market', '')),
            mean=data.get('mean', 0.0),
            std=data.get('std', 0.0),
            confidence=data.get('confidence', data.get('confidence_raw', 'LOW'))
        )


# ============================================================================
# CORRELATION GROUPS (SOP v2.1 - Prevents Correlated Bets)
# ============================================================================

TENNIS_CORRELATION_GROUPS = {
    # Group 1: Match duration stats (highly correlated)
    "match_duration": [
        "games_played", "total_games", "sets_played", "games played", "total games", "sets played"
    ],
    # Group 2: Player games won chain
    "player_games": [
        "games_won", "total_games_won", "1st_set_games_won", 
        "games won", "total games won", "1st set games won"
    ],
    # Group 3: First set specific
    "first_set": [
        "1st_set_games_played", "1st_set_games_won",
        "1st set games played", "1st set games won"
    ],
    # Group 4: Serve stats
    "serve_stats": [
        "aces", "double_faults", "double faults"
    ]
}

# Stats that are independent (can combine freely)
TENNIS_INDEPENDENT_STATS = [
    "breakpoints_won", "break_points_won", "breakpoints won", "break points won",
    "tiebreakers_played", "tiebreakers played", "tiebreakers",
    "fantasy_score", "fantasy score", "fantasy points"
]


# ============================================================================
# CONFIDENCE CAPS (SOP v2.1 Section 2.4 Compliant)
# ============================================================================

CONFIDENCE_CAPS = {
    'HIGH': 0.75,
    'MEDIUM': 0.65,
    'LOW': 0.60,
    'core': 0.75,
    'volume_micro': 0.65,
    'sequence_early': 0.60,
    'event_binary': 0.55
}

# Tennis-specific market caps (variance-adjusted)
TENNIS_MARKET_CAPS = {
    'games_won': 0.70,
    'games won': 0.70,
    'total_games_won': 0.70,
    'total games won': 0.70,
    'games_played': 0.70,
    'games played': 0.70,
    'total_games': 0.68,
    'total games': 0.68,
    '1st_set_games_won': 0.68,
    '1st set games won': 0.68,
    '1st_set_games_played': 0.68,
    '1st set games played': 0.68,
    'sets_won': 0.68,
    'sets won': 0.68,
    'sets_played': 0.65,
    'sets played': 0.65,
    'aces': 0.65,           # High variance (serve dependent)
    'double_faults': 0.56,   # Very high variance
    'double faults': 0.56,
    'breakpoints_won': 0.60,
    'breakpoints won': 0.60,
    'break_points_won': 0.60,
    'break points won': 0.60,
    'tiebreakers_played': 0.55,  # Binary, nearly unpredictable
    'tiebreakers played': 0.55,
    'tiebreakers': 0.55,
    'fantasy_score': 0.62,
    'fantasy score': 0.62,
    'fantasy points': 0.62,
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
# TENNIS EDGE DETECTOR CLASS v2.0
# ============================================================================

class TennisEdgeDetector:
    """
    Tennis edge detector with Monte Carlo integration
    
    v2.0 UPGRADES:
    - Correlation group tracking
    - Edge collapse (same player/stat/direction → pick best line)
    - Validation gate before render
    """
    
    def __init__(self):
        self.confidence_caps = CONFIDENCE_CAPS
        self.market_caps = TENNIS_MARKET_CAPS
        self.tier_thresholds = TIER_THRESHOLDS
        self.correlation_groups = TENNIS_CORRELATION_GROUPS
    
    
    def batch_analyze(self, mc_results: List) -> List:
        """
        Analyze batch of Monte Carlo results with edge collapse.
        
        Steps:
        1. Analyze each result
        2. Collapse duplicate edges (same player/stat/direction)
        3. Mark correlations
        4. Return only primary edges
        
        Accepts both Dict and MonteCarloResult objects for backward compatibility.
        """
        raw_edges = []
        
        for mc_result in mc_results:
            try:
                edge = self.analyze_result(mc_result)
                if edge:
                    raw_edges.append(edge)
            except Exception as e:
                logger.error(f"Error analyzing result: {e}")
                continue
        
        # Collapse edges & mark correlations
        collapsed_edges = self._collapse_edges(raw_edges)
        self._mark_correlations(collapsed_edges)
        
        return collapsed_edges
    
    
    def _collapse_edges(self, edges: List[Dict]) -> List[Dict]:
        """
        SOP v2.1 Edge Collapse Rules:
        - EDGE = unique(player, market, direction)
        - If multiple lines: HIGHER→highest line, LOWER→lowest line
        """
        edge_map: Dict[str, List[Dict]] = {}
        
        for edge in edges:
            # Create edge key (normalize market name)
            market = edge.get('market', edge.get('stat_type', '')).lower()
            player = edge.get('player', '')
            direction = edge.get('direction', 'HIGHER').upper()
            
            key = f"{player}|{market}|{direction}"
            
            if key not in edge_map:
                edge_map[key] = []
            edge_map[key].append(edge)
        
        # Select primary for each group
        collapsed = []
        for key, group in edge_map.items():
            if len(group) == 1:
                group[0]['is_primary'] = True
                collapsed.append(group[0])
            else:
                # Sort by line
                sorted_group = sorted(group, key=lambda x: x.get('line', 0))
                
                # HIGHER → highest line (more conservative)
                # LOWER → lowest line (more conservative)
                direction = group[0].get('direction', 'HIGHER').upper()
                if 'HIGHER' in direction or 'MORE' in direction or 'OVER' in direction:
                    primary = sorted_group[-1]
                else:
                    primary = sorted_group[0]
                
                primary['is_primary'] = True
                collapsed.append(primary)
                
                logger.info(f"Collapsed {len(group)} edges for {key} → line {primary.get('line')}")
        
        return collapsed
    
    
    def _mark_correlations(self, edges: List[Dict]) -> None:
        """Mark edges that are correlated with each other."""
        
        # Group edges by player
        player_edges: Dict[str, List[Dict]] = {}
        
        for edge in edges:
            player = edge.get('player', '')
            if player not in player_edges:
                player_edges[player] = []
            player_edges[player].append(edge)
        
        # Within each player, mark correlations
        for player, p_edges in player_edges.items():
            for i, edge1 in enumerate(p_edges):
                market1 = edge1.get('market', edge1.get('stat_type', '')).lower()
                
                # Find correlation group for this market
                group1 = self._get_correlation_group(market1)
                edge1['correlation_group'] = group1 or ''
                
                for edge2 in p_edges[i+1:]:
                    market2 = edge2.get('market', edge2.get('stat_type', '')).lower()
                    group2 = self._get_correlation_group(market2)
                    
                    # If same group, mark as correlated
                    if group1 and group1 == group2:
                        edge1_id = f"{edge1['player']}|{market1}|{edge1.get('direction', '')}"
                        edge2_id = f"{edge2['player']}|{market2}|{edge2.get('direction', '')}"
                        
                        if 'is_correlated_with' not in edge1:
                            edge1['is_correlated_with'] = []
                        if 'is_correlated_with' not in edge2:
                            edge2['is_correlated_with'] = []
                        
                        edge1['is_correlated_with'].append(edge2_id)
                        edge2['is_correlated_with'].append(edge1_id)
    
    
    def _get_correlation_group(self, market: str) -> Optional[str]:
        """Get correlation group for a market."""
        market_lower = market.lower().replace('_', ' ')
        
        for group_name, group_markets in self.correlation_groups.items():
            for gm in group_markets:
                if market_lower == gm.lower() or market_lower.replace(' ', '_') == gm:
                    return group_name
        
        return None
    
    
    def analyze_result(self, mc_result) -> Optional[Dict]:
        """
        Analyze single Monte Carlo result and generate edge.
        
        Accepts both Dict and MonteCarloResult objects.
        """
        # Handle MonteCarloResult object or dict
        if hasattr(mc_result, 'player'):
            # It's a MonteCarloResult object
            player = mc_result.player
            market = getattr(mc_result, 'stat_type', '')
            line = mc_result.line
            prob_over = getattr(mc_result, 'prob_over', 0.5)
            prob_under = getattr(mc_result, 'prob_under', 0.5)
            confidence = getattr(mc_result, 'confidence', 'LOW')
            mean = getattr(mc_result, 'mean', line)
            std = getattr(mc_result, 'std', 0)
            
            # Determine direction based on probabilities
            if prob_over > prob_under:
                probability = prob_over
                direction_hint = 'HIGHER'
            else:
                probability = prob_under
                direction_hint = 'LOWER'
        else:
            # It's a dict
            player = mc_result.get('player')
            market = mc_result.get('market', mc_result.get('stat_type', '')).lower()
            line = mc_result.get('line')
            probability = mc_result.get('probability', 0.5)
            confidence = mc_result.get('confidence', 'LOW')
            mean = mc_result.get('prediction', mc_result.get('mean', line))
            std = mc_result.get('std', 0)
            direction_hint = mc_result.get('direction', None)
        
        if not player or not market or line is None:
            return None
        
        # Apply confidence cap
        capped_prob = self._apply_confidence_cap(probability, confidence, market)
        
        # Determine direction
        if direction_hint:
            direction = direction_hint.upper()
            if 'HIGHER' in direction or 'MORE' in direction or 'OVER' in direction:
                direction = 'MORE/HIGHER'
                final_prob = capped_prob
            else:
                direction = 'LESS/LOWER'
                final_prob = capped_prob
        elif capped_prob > 0.5:
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
        
        edge_value = abs(mean - line) if mean else 0
        
        edge = {
            'player': player,
            'opponent': '',
            'market': market,
            'stat_type': market,
            'line': line,
            'prediction': mean,
            'mean': mean,
            'std': std,
            'probability': final_prob,
            'direction': direction,
            'tier': tier,
            'edge': edge_value,
            'confidence_raw': confidence,
            'confidence': confidence,
            'confidence_capped': capped_prob,
            'simulation_stats': {'mean': mean, 'std': std},
            'is_primary': True,
            'correlation_group': '',
            'is_correlated_with': []
        }
        
        return edge
    
    
    def _apply_confidence_cap(self, probability: float, confidence: str, 
                             market: str = '') -> float:
        """Apply confidence cap based on confidence level and market type."""
        if market:
            market_key = market.lower()
            market_cap = self.market_caps.get(market_key)
            if market_cap:
                return min(probability, market_cap)
        
        cap = self.confidence_caps.get(confidence, 0.60)
        return min(probability, cap)
    
    
    def _assign_tier(self, probability: float) -> str:
        """Assign tier based on probability."""
        if probability >= self.tier_thresholds['SLAM']:
            return 'SLAM'
        elif probability >= self.tier_thresholds['STRONG']:
            return 'STRONG'
        elif probability >= self.tier_thresholds['LEAN']:
            return 'LEAN'
        else:
            return 'NO_PLAY'
    
    
    def validate_edges(self, edges: List[Dict]) -> tuple:
        """
        SOP v2.1 VALIDATION GATE - Must pass before render.
        
        Checks:
        1. No duplicate edges (same player/market/direction)
        2. No SLAM tier with correlations
        3. Tier matches probability
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check 1: No duplicate edges
        seen_edges = set()
        for edge in edges:
            market = edge.get('market', edge.get('stat_type', ''))
            key = (edge.get('player'), market, edge.get('direction'))
            if key in seen_edges:
                errors.append(f"DUPLICATE_EDGE: {edge.get('player')} {market} {edge.get('direction')}")
            seen_edges.add(key)
        
        # Check 2: No SLAM with correlations
        for edge in edges:
            if edge.get('tier') == 'SLAM' and edge.get('is_correlated_with'):
                market = edge.get('market', edge.get('stat_type', ''))
                errors.append(f"CORRELATED_SLAM: {edge.get('player')} {market} - correlated edges cannot be SLAM")
        
        # Check 3: Tier matches probability
        for edge in edges:
            prob = edge.get('probability', 0)
            tier = edge.get('tier', 'NO_PLAY')
            expected = self._assign_tier(prob)
            if tier != expected:
                market = edge.get('market', edge.get('stat_type', ''))
                errors.append(f"TIER_MISMATCH: {edge.get('player')} {market} is {tier} but probability {prob:.1%} expects {expected}")
        
        return (len(errors) == 0, errors)


# ============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# ============================================================================

def create_edge_detector() -> TennisEdgeDetector:
    """Factory function for backward compatibility."""
    return TennisEdgeDetector()


def analyze_monte_carlo_results(results: List) -> List:
    """Convenience function for batch analysis."""
    detector = TennisEdgeDetector()
    return detector.batch_analyze(results)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    sample_results = [
        {
            'player': 'Aryna Sabalenka',
            'opponent': 'Elina Svitolina',
            'market': 'games_won',
            'line': 8.5,
            'probability': 0.72,
            'prediction': 11.2,
            'confidence': 'HIGH',
        },
        {
            'player': 'Aryna Sabalenka',
            'opponent': 'Elina Svitolina',
            'market': '1st_set_games_won',  # CORRELATED with games_won
            'line': 4.5,
            'probability': 0.68,
            'prediction': 5.2,
            'confidence': 'HIGH',
        },
        {
            'player': 'Carlos Alcaraz',
            'opponent': 'Alexander Zverev',
            'market': 'aces',
            'line': 10.0,
            'probability': 0.68,
            'prediction': 9.2,
            'confidence': 'HIGH',
        }
    ]
    
    print("=" * 60)
    print("TESTING TENNIS EDGE DETECTOR v2.0")
    print("=" * 60)
    
    detector = TennisEdgeDetector()
    edges = detector.batch_analyze(sample_results)
    
    print(f"\n✓ Analyzed {len(sample_results)} Monte Carlo results")
    print(f"✓ Generated {len(edges)} edges\n")
    
    for i, edge in enumerate(edges, 1):
        corr_flag = " ⚠️CORR" if edge.get('is_correlated_with') else ""
        print(f"Edge {i}:{corr_flag}")
        print(f"  Player: {edge['player']}")
        print(f"  Market: {edge['market']} {edge['line']}")
        print(f"  Direction: {edge['direction']}")
        print(f"  Probability: {edge['probability']:.1%}")
        print(f"  Tier: {edge['tier']}")
        if edge.get('correlation_group'):
            print(f"  Correlation Group: {edge['correlation_group']}")
        print()
    
    # Validate
    is_valid, errors = detector.validate_edges(edges)
    print("=" * 60)
    print(f"VALIDATION: {'✅ PASSED' if is_valid else '❌ FAILED'}")
    for err in errors:
        print(f"  - {err}")
    print("=" * 60)
