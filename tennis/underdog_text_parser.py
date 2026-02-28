"""
UNDERDOG FANTASY TEXT FORMAT PARSER
Parses Underdog Tennis props from copied text format

Handles both formats:
1. Clean text with player headers
2. Structured JSON-like data

Example Input:
    Thiago Agustin Tirante
    Tirante vs Schwaerz… - 2:00AM CST
    Round of 16
    
    21.5
    Games Played
    Higher
    Lower
    
    5.5
    1st Set Games Won
    Higher 0.62x
    Lower 1.67x
"""

import re
from datetime import datetime
from typing import List, Dict, Optional
import json


# ============================================================================
# MARKET TYPE NORMALIZATION
# ============================================================================

MARKET_ALIASES = {
    'games played': 'games_played',
    'games won': 'games_won',
    '1st set games played': 'first_set_games_played',
    '1st set games won': 'first_set_games_won',
    'sets played': 'sets_played',
    'sets won': 'sets_won',
    'aces': 'aces',
    'breakpoints won': 'breakpoints_won',
    'tiebreakers played': 'tiebreakers_played',
    'double faults': 'double_faults'
}


# ============================================================================
# MAIN PARSER CLASS
# ============================================================================

class UnderdogTextParser:
    """Parse Underdog Fantasy tennis props from text format"""
    
    def __init__(self):
        self.current_player = None
        self.current_matchup = None
        self.current_time = None
        self.current_round = None
        self.props_data = []
    
    
    def parse_file(self, filepath: str) -> List[Dict]:
        """
        Parse Underdog props from text file
        
        Args:
            filepath: Path to text file with Underdog data
            
        Returns:
            List of parsed player prop dictionaries
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_text(content)
    
    
    def parse_text(self, text: str) -> List[Dict]:
        """
        Parse Underdog props from raw text
        
        Args:
            text: Raw text content from Underdog
            
        Returns:
            List of parsed player props
        """
        lines = text.strip().split('\n')
        self.props_data = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Check if this is a player header (name or matchup)
            if self._is_player_header(line, lines, i):
                i = self._parse_player_block(lines, i)
            else:
                i += 1
        
        return self.props_data
    
    
    def _is_player_header(self, line: str, lines: List[str], idx: int) -> bool:
        """
        Detect if current line is a player header
        
        Player headers look like:
        - "Thiago Agustin Tirante"
        - "Tirante vs Schwaerz… - 2:00AM CST"
        """
        # Check for matchup format (contains "vs")
        if 'vs' in line.lower():
            return True
        
        # Check if next line is a matchup
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if 'vs' in next_line.lower() or any(x in next_line.lower() for x in ['am cst', 'pm cst']):
                return True
        
        # Check for player name pattern (capitalized words)
        words = line.split()
        if len(words) >= 2 and all(w[0].isupper() for w in words if w):
            return True
        
        return False
    
    
    def _parse_player_block(self, lines: List[str], start_idx: int) -> int:
        """
        Parse a complete player block (header + all props)
        
        Returns:
            Index of next line to process
        """
        i = start_idx
        
        # Parse player header
        player_name = lines[i].strip()
        i += 1
        
        # Parse matchup line (if exists)
        matchup = None
        match_time = None
        if i < len(lines):
            matchup_line = lines[i].strip()
            if 'vs' in matchup_line.lower():
                matchup = matchup_line
                match_time = self._extract_time(matchup_line)
                i += 1
        
        # Parse round (if exists)
        tournament_round = None
        if i < len(lines):
            potential_round = lines[i].strip()
            if any(x in potential_round.lower() for x in ['round', 'final', 'quarterfinal', 'semifinal']):
                tournament_round = potential_round
                i += 1
        
        # Skip "Popular Picks" header if present
        if i < len(lines) and 'popular picks' in lines[i].lower():
            i += 1
        
        # Parse all markets for this player
        markets = {}
        while i < len(lines):
            line = lines[i].strip()
            
            # Stop if we hit next player
            if self._is_player_header(line, lines, i):
                break
            
            # Stop if we hit "Fewer picks"
            if 'fewer picks' in line.lower():
                i += 1
                break
            
            # Try to parse as market
            if line and not line.lower() in ['higher', 'lower']:
                # Check if this looks like a line value (number with optional .5)
                if self._is_line_value(line):
                    market_data, new_idx = self._parse_market(lines, i)
                    if market_data:
                        market_type = market_data['market_type']
                        markets[market_type] = {
                            'line': market_data['line'],
                            'higher_odds': market_data.get('higher_odds'),
                            'lower_odds': market_data.get('lower_odds')
                        }
                    i = new_idx
                    continue
            
            i += 1
        
        # Store parsed player data
        if markets:
            opponent = self._extract_opponent(player_name, matchup)
            
            self.props_data.append({
                'player_name': player_name,
                'opponent': opponent,
                'matchup': matchup,
                'match_time': match_time,
                'tournament_round': tournament_round,
                'markets': markets
            })
        
        return i
    
    
    def _parse_market(self, lines: List[str], start_idx: int) -> tuple:
        """
        Parse a single market (line + type + odds)
        
        Returns:
            (market_data dict, next_index)
        """
        i = start_idx
        
        # Line 1: Line value (e.g., "21.5")
        line_value = float(lines[i].strip())
        i += 1
        
        # Line 2: Market type (e.g., "Games Played")
        if i >= len(lines):
            return None, i
        
        market_type_raw = lines[i].strip()
        market_type = self._normalize_market_type(market_type_raw)
        i += 1
        
        # Line 3: Higher (with optional odds)
        higher_odds = None
        if i < len(lines):
            higher_line = lines[i].strip()
            if 'higher' in higher_line.lower():
                higher_odds = self._extract_odds(higher_line)
                i += 1
        
        # Line 4: Lower (with optional odds)
        lower_odds = None
        if i < len(lines):
            lower_line = lines[i].strip()
            if 'lower' in lower_line.lower():
                lower_odds = self._extract_odds(lower_line)
                i += 1
        
        return {
            'line': line_value,
            'market_type': market_type,
            'higher_odds': higher_odds,
            'lower_odds': lower_odds
        }, i
    
    
    def _is_line_value(self, text: str) -> bool:
        """Check if text looks like a line value (e.g., '21.5', '0.5')"""
        try:
            float(text)
            return True
        except ValueError:
            return False
    
    
    def _normalize_market_type(self, raw_type: str) -> str:
        """Normalize market type to canonical form"""
        normalized = raw_type.lower().strip()
        return MARKET_ALIASES.get(normalized, normalized.replace(' ', '_'))
    
    
    def _extract_odds(self, text: str) -> Optional[float]:
        """
        Extract odds multiplier from text
        
        Examples:
            "Higher 0.62x" → 0.62
            "Lower 1.67x" → 1.67
            "Higher" → None
        """
        match = re.search(r'(\d+\.?\d*)x', text)
        if match:
            return float(match.group(1))
        return None
    
    
    def _extract_time(self, matchup_line: str) -> Optional[str]:
        """
        Extract match time from matchup line
        
        Example:
            "Tirante vs Schwaerz… - 2:00AM CST" → "2:00AM CST"
        """
        match = re.search(r'(\d{1,2}:\d{2}[AP]M\s+\w+)', matchup_line)
        if match:
            return match.group(1)
        return None
    
    
    def _extract_opponent(self, player_name: str, matchup: str) -> Optional[str]:
        """
        Extract opponent name from matchup string
        
        Example:
            player_name: "Thiago Agustin Tirante"
            matchup: "Tirante vs Schwaerz… - 2:00AM CST"
            → "Schwaerzler"
        """
        if not matchup:
            return None
        
        # Split by "vs"
        parts = matchup.split(' vs ')
        if len(parts) < 2:
            return None
        
        # Get opponent part (after vs)
        opponent_part = parts[1].split(' - ')[0].strip()
        
        # Clean up truncation (e.g., "Schwaerz…")
        opponent_part = opponent_part.replace('…', '').strip()
        
        return opponent_part


# ============================================================================
# DATA EXPORT & ANALYSIS
# ============================================================================

class UnderdogPropsAnalyzer:
    """Analyze parsed Underdog props data"""
    
    @staticmethod
    def get_all_players(props: List[Dict]) -> List[str]:
        """Get list of all players"""
        return [p['player_name'] for p in props]
    
    
    @staticmethod
    def get_markets_for_player(props: List[Dict], player_name: str) -> Dict:
        """Get all markets for specific player"""
        for prop in props:
            if prop['player_name'] == player_name:
                return prop['markets']
        return {}
    
    
    @staticmethod
    def get_market_distribution(props: List[Dict]) -> Dict[str, int]:
        """Count how many players have each market type"""
        distribution = {}
        
        for prop in props:
            for market_type in prop['markets'].keys():
                distribution[market_type] = distribution.get(market_type, 0) + 1
        
        return distribution
    
    
    @staticmethod
    def filter_by_market(props: List[Dict], market_type: str) -> List[Dict]:
        """Get all players who have a specific market available"""
        filtered = []
        
        for prop in props:
            if market_type in prop['markets']:
                filtered.append({
                    'player_name': prop['player_name'],
                    'opponent': prop['opponent'],
                    'match_time': prop['match_time'],
                    'line': prop['markets'][market_type]['line'],
                    'higher_odds': prop['markets'][market_type].get('higher_odds'),
                    'lower_odds': prop['markets'][market_type].get('lower_odds')
                })
        
        return filtered
    
    
    @staticmethod
    def export_to_json(props: List[Dict], filepath: str):
        """Export parsed props to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(props, f, indent=2)
    
    
    @staticmethod
    def print_summary(props: List[Dict]):
        """Print analysis summary"""
        print("\n" + "="*70)
        print("UNDERDOG TENNIS PROPS SUMMARY")
        print("="*70 + "\n")
        
        print(f"Total Players: {len(props)}")
        
        # Market distribution
        distribution = UnderdogPropsAnalyzer.get_market_distribution(props)
        print(f"\nMarket Distribution:")
        for market, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
            print(f"  {market:30} {count:2} players")
        
        # Show sample player
        if props:
            print(f"\nSample Player: {props[0]['player_name']}")
            print(f"  Opponent: {props[0]['opponent']}")
            print(f"  Match Time: {props[0]['match_time']}")
            print(f"  Markets Available: {len(props[0]['markets'])}")


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main CLI for parsing Underdog props"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python underdog_text_parser.py <input_file> [output_json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Parse the file
    parser = UnderdogTextParser()
    props = parser.parse_file(input_file)
    
    # Print summary
    analyzer = UnderdogPropsAnalyzer()
    analyzer.print_summary(props)
    
    # Export to JSON if requested
    if output_file:
        analyzer.export_to_json(props, output_file)
        print(f"\n✅ Exported to {output_file}")
    
    # Show detailed data for first player
    if props:
        print("\n" + "="*70)
        print("SAMPLE PLAYER DETAILS")
        print("="*70)
        print(json.dumps(props[0], indent=2))


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # If called with file argument, run CLI
    import sys
    if len(sys.argv) > 1:
        main()
    else:
        # Run test with sample data
        sample_text = """
Thiago Agustin Tirante
Tirante vs Schwaerz… - 2:00AM CST
Round of 16

21.5
Games Played
Higher
Lower

12.5
Games Won
Higher
Lower

5.5
1st Set Games Won
Higher 0.62x
Lower 1.67x

0.5
Tiebreakers Played
Higher 1.28x
Lower 0.68x

Fewer picks

Joel Schwaerzler
Tirante vs Schwaerz… - 2:00AM CST

9.5
Games Won
Higher
Lower

4.5
1st Set Games Won
Higher 1.04x
Lower 0.87x

Fewer picks
"""
        
        parser = UnderdogTextParser()
        props = parser.parse_text(sample_text)
        
        analyzer = UnderdogPropsAnalyzer()
        analyzer.print_summary(props)
        
        print("\n" + "="*70)
        print("PARSED DATA")
        print("="*70)
        print(json.dumps(props, indent=2))
