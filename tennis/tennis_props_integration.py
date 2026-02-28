"""
TENNIS PROPS INTEGRATION MODULE
Drop-in replacement for existing tennis pipeline to support DFS props

This module integrates with your existing:
- 5-stage pipeline structure
- JSON output format
- Validation gates
- Menu system

USAGE:
    Replace tennis/ingest_matches.py with this module's ingest_props()
    Add tennis/models/props_predictor.py for prop predictions
"""

import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

# Import the new edge schema for JSON ingest
try:
    from tennis.ingest.tennis_edge_schema import (
        TennisMatchIngest, 
        ingest_match_json, 
        collapse_tennis_edges,
        validate_parlay_correlations
    )
    HAS_EDGE_SCHEMA = True
except ImportError:
    HAS_EDGE_SCHEMA = False


# ============================================================================
# STAGE 1: PROPS INGESTION (Replaces match ingestion)
# ============================================================================

class PropsIngestor:
    """
    Ingests DFS props in PrizePicks/Underdog format
    Compatible with your existing pipeline structure
    """
    
    def __init__(self):
        self.platform = None
    
    
    def ingest_from_text(self, text: str) -> List[Dict]:
        """
        Main ingestion method - auto-detects platform
        
        Returns list of props in your pipeline's expected format
        """
        # Detect platform
        self.platform = self._detect_platform(text)
        
        if self.platform == 'prizepicks':
            return self._parse_prizepicks(text)
        elif self.platform == 'underdog':
            return self._parse_underdog(text)
        else:
            # Fall back to match winner parsing
            return self._parse_match_winners(text)
    
    
    def _detect_platform(self, text: str) -> str:
        """Detect which platform format"""
        # PrizePicks has "Less" and "More" direction labels
        if ('Less' in text and 'More' in text) or '- Player' in text:
            return 'prizepicks'
        elif 'Higher' in text and 'Lower' in text:
            return 'underdog'
        elif ' vs ' in text and '|' in text:
            return 'match_winner'
        return 'unknown'
    
    
    def _parse_prizepicks(self, text: str) -> List[Dict]:
        """Parse PrizePicks format"""
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        props = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Skip non-player lines
            if line in ['Less', 'More', 'END', ''] or line.lower().startswith('trending'):
                i += 1
                continue
            
            # Look for player name followed by matchup
            if i + 1 < len(lines) and ('@' in lines[i + 1] or 'vs' in lines[i + 1].lower()):
                prop = self._extract_prizepicks_prop(lines, i)
                if prop:
                    props.append(prop)
                    i += prop.get('lines_consumed', 6)
                    continue
            
            i += 1
        
        return props
    
    
    def _extract_prizepicks_prop(self, lines: List[str], start: int) -> Optional[Dict]:
        """
        Extract a single PrizePicks prop
        
        Format:
            Elina Svitolina
            @ Aryna Sabalenka Thu 2:30am
            8.5
            Total Games Won
            Less
            More
        """
        if start + 3 >= len(lines):
            return None
        
        try:
            player_name = lines[start]
            
            # Must have opponent line next
            if start + 1 >= len(lines):
                return None
            
            opponent_line = lines[start + 1]
            if '@' not in opponent_line and 'vs' not in opponent_line.lower():
                return None
            
            # Extract opponent and time
            opponent = self._extract_opponent(opponent_line)
            match_time = self._extract_time(opponent_line)
            
            # Find line value (should be next non-empty numeric line)
            line_value = None
            stat_type = None
            lines_consumed = 2
            
            for j in range(start + 2, min(start + 8, len(lines))):
                try:
                    # Try to parse as number
                    line_value = float(lines[j])
                    # Next line should be stat type
                    if j + 1 < len(lines):
                        potential_stat = lines[j + 1]
                        if potential_stat not in ['Less', 'More', '']:
                            stat_type = potential_stat
                            lines_consumed = j - start + 3  # Include Less/More
                            break
                except ValueError:
                    continue
            
            if line_value is None or not stat_type:
                return None
            
            # Normalize stat type
            market_type = self._normalize_market(stat_type)
            
            return {
                'player': player_name,
                'opponent': opponent,
                'match_time': match_time,
                'market': market_type,
                'line': line_value,
                'platform': 'prizepicks',
                'lines_consumed': lines_consumed
            }
            
        except Exception as e:
            return None
    
    
    def _parse_underdog(self, text: str) -> List[Dict]:
        """Parse Underdog format"""
        # Similar logic but for Underdog format
        # (Simplified version - use full parser for production)
        return []
    
    
    def _parse_match_winners(self, text: str) -> List[Dict]:
        """
        Parse traditional match winner format
        
        Format: "Sinner -180 vs Djokovic +150 | Hard | SF"
        """
        lines = text.strip().split('\n')
        matches = []
        
        for line in lines:
            line = line.strip()
            if not line or line.upper() == 'END':
                continue
            
            # Try to parse as match winner
            match = re.search(r'(\w+).*vs\s+(\w+)', line, re.IGNORECASE)
            if match:
                player1 = match.group(1)
                player2 = match.group(2)
                
                # Extract surface if present
                surface = 'Hard'  # Default
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) > 1:
                        surface = parts[1].strip()
                
                matches.append({
                    'player': player1,
                    'opponent': player2,
                    'market': 'match_winner',
                    'surface': surface,
                    'platform': 'match_betting'
                })
        
        return matches
    
    
    def _normalize_market(self, raw_market: str) -> str:
        """Normalize market type to canonical form"""
        market_map = {
            'total games won': 'games_won',
            'total games': 'games_played',
            'break points won': 'breakpoints_won',
            'fantasy score': 'fantasy_score',
            'aces': 'aces',
            'double faults': 'double_faults',
            'total sets': 'sets_played'
        }
        
        normalized = raw_market.lower().strip()
        return market_map.get(normalized, normalized.replace(' ', '_'))
    
    
    def _extract_opponent(self, matchup_line: str) -> str:
        """Extract opponent name from matchup line"""
        # Remove @ or vs
        line = matchup_line.replace('@', '').replace('vs', '').strip()
        
        # Extract opponent (before time)
        time_match = re.search(r'[A-Z][a-z]{2}\s+\d{1,2}:\d{2}[ap]m', line)
        if time_match:
            opponent = line[:time_match.start()].strip()
            return opponent
        
        return 'Unknown'
    
    
    def _extract_time(self, matchup_line: str) -> Optional[str]:
        """Extract match time"""
        match = re.search(r'([A-Z][a-z]{2}\s+\d{1,2}:\d{2}[ap]m)', matchup_line)
        if match:
            return match.group(1)
        return None


# ============================================================================
# STAGE 2: PROPS EDGE GENERATION
# ============================================================================

class PropsEdgeGenerator:
    """
    Generates betting edges for props
    Compatible with your existing edge format
    """
    
    def __init__(self):
        self.player_stats = self._load_player_stats()
    
    
    def generate_edges(self, props: List[Dict]) -> List[Dict]:
        """
        Generate edges for all props
        
        Returns edges in your pipeline's expected JSON format
        """
        edges = []
        
        for prop in props:
            if prop.get('market') == 'match_winner':
                # Skip match winners for now (use existing Elo)
                continue
            
            edge = self._generate_prop_edge(prop)
            if edge:
                edges.append(edge)
        
        return edges
    
    
    def _generate_prop_edge(self, prop: Dict) -> Optional[Dict]:
        """Generate edge for single prop"""
        player = prop['player']
        opponent = prop['opponent']
        market = prop['market']
        line = prop['line']
        
        # Get player stats
        player_stats = self.player_stats.get(player, self._default_stats())
        opponent_stats = self.player_stats.get(opponent, self._default_stats())
        
        # Generate prediction based on market type
        prediction = self._predict_market(
            player_stats, 
            opponent_stats, 
            market, 
            line
        )
        
        if not prediction:
            return None
        
        # Determine direction and probability
        if prediction['probability_over'] > prediction['probability_under']:
            direction = 'MORE/HIGHER'
            probability = prediction['probability_over']
        else:
            direction = 'LESS/LOWER'
            probability = prediction['probability_under']
        
        # Calculate edge
        edge_value = abs(prediction['prediction'] - line)
        
        # Assign tier (your existing tier logic)
        tier = self._assign_tier(probability)
        
        # Format in your pipeline's expected structure
        return {
            'player': player,
            'opponent': opponent,
            'market': market,
            'line': line,
            'prediction': prediction['prediction'],
            'probability': probability,
            'direction': direction,
            'tier': tier,
            'edge': edge_value,
            'platform': prop.get('platform', 'unknown'),
            'match_time': prop.get('match_time')
        }
    
    
    def _predict_market(self, player_stats: Dict, opponent_stats: Dict, 
                       market: str, line: float) -> Optional[Dict]:
        """Predict based on market type"""
        
        if market == 'games_won':
            return self._predict_games_won(player_stats, opponent_stats, line)
        elif market == 'aces':
            return self._predict_aces(player_stats, opponent_stats, line)
        elif market == 'breakpoints_won':
            return self._predict_breakpoints(player_stats, opponent_stats, line)
        elif market == 'fantasy_score':
            return self._predict_fantasy_score(player_stats, opponent_stats, line)
        else:
            return None
    
    
    def _predict_games_won(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """Predict games won"""
        base = player.get('avg_games', 12.0)
        
        # Adjust for opponent strength
        if opponent.get('avg_games', 12.0) < 11.0:
            base += 1.5
        elif opponent.get('avg_games', 12.0) > 15.0:
            base -= 1.0
        
        diff = base - line
        
        # Simple probability calculation
        if diff >= 2.0:
            prob_over = 0.75
        elif diff >= 1.0:
            prob_over = 0.68
        elif diff >= 0.5:
            prob_over = 0.62
        elif diff >= 0:
            prob_over = 0.56
        else:
            prob_over = 0.45
        
        return {
            'prediction': base,
            'probability_over': prob_over,
            'probability_under': 1.0 - prob_over
        }
    
    
    def _predict_aces(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """Predict aces"""
        base = player.get('avg_aces', 4.0)
        
        # Surface adjustment (if available)
        surface = player.get('surface', 'hard')
        if surface == 'grass':
            base *= 1.4
        elif surface == 'clay':
            base *= 0.7
        
        diff = base - line
        
        if diff >= 2.0:
            prob_over = 0.72
        elif diff >= 1.0:
            prob_over = 0.66
        elif diff >= 0.5:
            prob_over = 0.60
        else:
            prob_over = 0.50
        
        return {
            'prediction': base,
            'probability_over': prob_over,
            'probability_under': 1.0 - prob_over
        }
    
    
    def _predict_breakpoints(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """Predict breakpoints won"""
        base = player.get('avg_breakpoints', 2.5)
        
        diff = base - line
        
        if diff >= 1.0:
            prob_over = 0.65
        elif diff >= 0.5:
            prob_over = 0.58
        else:
            prob_over = 0.50
        
        return {
            'prediction': base,
            'probability_over': prob_over,
            'probability_under': 1.0 - prob_over
        }
    
    
    def _predict_fantasy_score(self, player: Dict, opponent: Dict, line: float) -> Dict:
        """Predict PrizePicks fantasy score"""
        base = player.get('avg_fantasy_score', 18.0)
        
        diff = base - line
        
        if diff >= 3.0:
            prob_over = 0.70
        elif diff >= 2.0:
            prob_over = 0.64
        elif diff >= 1.0:
            prob_over = 0.58
        else:
            prob_over = 0.50
        
        return {
            'prediction': base,
            'probability_over': prob_over,
            'probability_under': 1.0 - prob_over
        }
    
    
    def _assign_tier(self, probability: float) -> str:
        """Assign tier based on probability (SOP v2.1 compliant)"""
        if probability >= 0.75:
            return 'SLAM'
        elif probability >= 0.65:
            return 'STRONG'
        elif probability >= 0.55:
            return 'LEAN'
        else:
            return 'NO_PLAY'
    
    
    def _load_player_stats(self) -> Dict:
        """
        Load player stats database
        
        TODO: Replace with actual database query
        """
        return {
            'Aryna Sabalenka': {
                'avg_games': 14.2,
                'avg_aces': 5.8,
                'avg_breakpoints': 3.8,
                'avg_fantasy_score': 22.5
            },
            'Elina Svitolina': {
                'avg_games': 11.2,
                'avg_aces': 1.8,
                'avg_breakpoints': 2.2,
                'avg_fantasy_score': 15.3
            },
            'Elena Rybakina': {
                'avg_games': 13.8,
                'avg_aces': 7.8,
                'avg_breakpoints': 3.6,
                'avg_fantasy_score': 22.9
            },
            'Jessica Pegula': {
                'avg_games': 12.4,
                'avg_aces': 2.1,
                'avg_breakpoints': 2.8,
                'avg_fantasy_score': 18.2
            },
            'Carlos Alcaraz': {
                'avg_games': 16.2,
                'avg_aces': 6.5,
                'avg_breakpoints': 4.8,
                'avg_fantasy_score': 28.1
            },
            'Alexander Zverev': {
                'avg_games': 14.8,
                'avg_aces': 9.2,
                'avg_breakpoints': 3.5,
                'avg_fantasy_score': 25.4
            }
        }
    
    
    def _default_stats(self) -> Dict:
        """Default stats for unknown players"""
        return {
            'avg_games': 12.0,
            'avg_aces': 4.0,
            'avg_breakpoints': 2.5,
            'avg_fantasy_score': 18.0
        }


# ============================================================================
# CONVENIENCE FUNCTIONS FOR YOUR PIPELINE
# ============================================================================

def ingest_props_from_text(text: str) -> List[Dict]:
    """
    Convenience function for Stage 1
    
    Drop-in replacement for your ingest_matches() function
    """
    ingestor = PropsIngestor()
    return ingestor.ingest_from_text(text)


def ingest_props_from_json(data: Any) -> List[Dict]:
    """
    Ingest props from JSON format (SOP v2.1 compliant).
    
    Accepts:
    - Dict with match metadata and edges
    - JSON string  
    - File path to JSON file
    
    Returns list of props with correlation tracking.
    """
    if not HAS_EDGE_SCHEMA:
        raise ImportError("tennis.ingest.tennis_edge_schema required for JSON ingest")
    
    # Parse match JSON
    match = ingest_match_json(data)
    
    # Validate
    validation = match.validate()
    if not validation["passed"]:
        for error in validation["errors"]:
            print(f"[ERROR] {error}")
        raise ValueError("Validation failed - see errors above")
    
    # Convert to edge format
    edges = match.to_edges()
    
    # Collapse edges per SOP
    collapsed = collapse_tennis_edges(edges)
    
    return collapsed


def generate_props_edges(props: List[Dict]) -> List[Dict]:
    """
    Convenience function for Stage 2
    
    Works alongside your existing edge generation
    """
    generator = PropsEdgeGenerator()
    return generator.generate_edges(props)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test with sample PrizePicks data
    sample_text = """
Elina Svitolina
@ Aryna Sabalenka Thu 2:30am
8.5
Total Games Won
Less
More

Carlos Alcaraz
vs Alexander Zverev Thu 9:30pm
36.5
Total Games
Less
More

Alexander Zverev
@ Carlos Alcaraz Thu 9:30pm
10
Aces
Less
More
"""
    
    print("="*60)
    print("TESTING PROPS INTEGRATION")
    print("="*60)
    
    # Stage 1: Ingest
    print("\n[Stage 1] Ingesting props...")
    props = ingest_props_from_text(sample_text)
    print(f"✓ Ingested {len(props)} props")
    for prop in props:
        print(f"  - {prop['player']} vs {prop['opponent']}: {prop['market']} {prop['line']}")
    
    # Stage 2: Generate Edges
    print("\n[Stage 2] Generating edges...")
    edges = generate_props_edges(props)
    print(f"✓ Generated {len(edges)} edges")
    for edge in edges:
        print(f"  - {edge['player']}: {edge['market']} {edge['line']} → {edge['direction']} ({edge['tier']})")
    
    print("\n" + "="*60)
    print("✅ INTEGRATION TEST COMPLETE")
    print("="*60)
