"""
PRIZEPICKS TENNIS PARSER
Parses PrizePicks tennis props from copied text format

Format Example:
    Elina Svitolina - Player
    Elina Svitolina
    @ Aryna Sabalenka Thu 2:30am
    8.5
    Total Games Won
    Less More
    * 11.6K
"""

import re
from typing import List, Dict, Optional
from datetime import datetime
import json


# ============================================================================
# PRIZEPICKS MARKET NORMALIZATION
# ============================================================================

PRIZEPICKS_MARKET_ALIASES = {
    'total games won': 'games_won',
    'total games': 'games_played',
    'break points won': 'breakpoints_won',
    'aces': 'aces',
    'fantasy score': 'fantasy_score',
    'double faults': 'double_faults',
    'total sets': 'sets_played',
    'total tie breaks': 'tiebreakers_played',
    'total tiebreaks': 'tiebreakers_played'
}


# ============================================================================
# PRIZEPICKS PARSER CLASS
# ============================================================================

class PrizePicksParser:
    """Parse PrizePicks tennis props from text format"""
    
    def __init__(self):
        self.props_data = []
    
    
    def parse_file(self, filepath: str) -> List[Dict]:
        """Parse PrizePicks props from text file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_text(content)
    
    
    def parse_text(self, text: str) -> List[Dict]:
        """
        Parse PrizePicks props from raw text
        
        Text format:
            Elina Svitolina - Player
            Elina Svitolina
            @ Aryna Sabalenka Thu 2:30am
            8.5
            Total Games Won
            Less More
            * 11.6K
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
            
            # Look for player header (ends with "- Player")
            if line.endswith('- Player'):
                i = self._parse_player_block(lines, i)
            else:
                i += 1
        
        return self.props_data
    
    
    def _parse_player_block(self, lines: List[str], start_idx: int) -> int:
        """
        Parse a complete PrizePicks player block
        
        Format:
            Line 0: "Elina Svitolina - Player"
            Line 1: "Elina Svitolina"
            Line 2: "@ Aryna Sabalenka Thu 2:30am"
            Line 3: "8.5"
            Line 4: "Total Games Won"
            Line 5: "Less More" or "LessMore"
            Line 6: "* 11.6K" (popularity)
        """
        i = start_idx
        
        # Line 0: Header (skip, just marker)
        i += 1
        
        # Line 1: Player name
        if i >= len(lines):
            return i
        player_name = lines[i].strip()
        i += 1
        
        # Line 2: Matchup with opponent and time
        matchup = None
        opponent = None
        match_time = None
        if i < len(lines):
            matchup_line = lines[i].strip()
            matchup = matchup_line
            opponent = self._extract_opponent(matchup_line)
            match_time = self._extract_time(matchup_line)
            i += 1
        
        # Parse all props for this player
        markets = {}
        while i < len(lines):
            # Check if we hit next player
            if i < len(lines) and lines[i].strip().endswith('- Player'):
                break
            
            # Try to parse a prop
            if self._is_line_value(lines[i].strip()):
                prop_data, new_idx = self._parse_prop(lines, i)
                if prop_data:
                    market_type = prop_data['market_type']
                    markets[market_type] = {
                        'line': prop_data['line'],
                        'popularity': prop_data.get('popularity')
                    }
                i = new_idx
            else:
                i += 1
        
        # Store parsed player data
        if markets:
            self.props_data.append({
                'player_name': player_name,
                'opponent': opponent,
                'matchup': matchup,
                'match_time': match_time,
                'markets': markets,
                'platform': 'PrizePicks'
            })
        
        return i
    
    
    def _parse_prop(self, lines: List[str], start_idx: int) -> tuple:
        """
        Parse a single PrizePicks prop
        
        Format:
            Line i: "8.5" (line value)
            Line i+1: "Total Games Won" (market type)
            Line i+2: "Less More" or "LessMore"
            Line i+3: "* 11.6K" (optional popularity)
        """
        i = start_idx
        
        # Line value
        try:
            line_value = float(lines[i].strip())
        except ValueError:
            return None, i + 1
        i += 1
        
        # Market type
        if i >= len(lines):
            return None, i
        market_type_raw = lines[i].strip()
        market_type = self._normalize_market_type(market_type_raw)
        i += 1
        
        # "Less More" line (skip)
        if i < len(lines) and 'less' in lines[i].lower():
            i += 1
        
        # Popularity (optional)
        popularity = None
        if i < len(lines) and lines[i].strip().startswith('*'):
            popularity = self._parse_popularity(lines[i].strip())
            i += 1
        
        return {
            'line': line_value,
            'market_type': market_type,
            'popularity': popularity
        }, i
    
    
    def _is_line_value(self, text: str) -> bool:
        """Check if text is a line value"""
        try:
            float(text)
            return True
        except ValueError:
            return False
    
    
    def _normalize_market_type(self, raw_type: str) -> str:
        """Normalize market type to canonical form"""
        normalized = raw_type.lower().strip()
        return PRIZEPICKS_MARKET_ALIASES.get(normalized, normalized.replace(' ', '_'))
    
    
    def _extract_opponent(self, matchup_line: str) -> Optional[str]:
        """
        Extract opponent from matchup line
        
        Examples:
            "@ Aryna Sabalenka Thu 2:30am" → "Aryna Sabalenka"
            "vs Elena Rybakina Thu 3:40am" → "Elena Rybakina"
        """
        # Remove @ or vs prefix
        line = matchup_line.replace('@', '').replace('vs', '').strip()
        
        # Extract time pattern (e.g., "Thu 2:30am")
        time_match = re.search(r'[A-Z][a-z]{2}\s+\d{1,2}:\d{2}[ap]m', line)
        if time_match:
            # Opponent is everything before the time
            opponent = line[:time_match.start()].strip()
            return opponent
        
        # If no time found, try splitting by day abbreviation
        for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
            if day in line:
                opponent = line.split(day)[0].strip()
                return opponent
        
        return None
    
    
    def _extract_time(self, matchup_line: str) -> Optional[str]:
        """
        Extract match time from matchup line
        
        Example:
            "@ Aryna Sabalenka Thu 2:30am" → "Thu 2:30am"
        """
        match = re.search(r'([A-Z][a-z]{2}\s+\d{1,2}:\d{2}[ap]m)', matchup_line)
        if match:
            return match.group(1)
        return None
    
    
    def _parse_popularity(self, popularity_text: str) -> Optional[str]:
        """
        Parse popularity indicator
        
        Examples:
            "* 11.6K" → "11.6K"
            "* 5.3K" → "5.3K"
        """
        match = re.search(r'\*\s*([\d.]+K)', popularity_text)
        if match:
            return match.group(1)
        return None


# ============================================================================
# UNIFIED PARSER (Handles Both PrizePicks and Underdog)
# ============================================================================

class UnifiedTennisParser:
    """
    Unified parser that detects and parses both PrizePicks and Underdog formats
    """
    
    @staticmethod
    def detect_platform(text: str) -> str:
        """
        Detect which platform the data is from
        
        Returns:
            'prizepicks', 'underdog', or 'unknown'
        """
        # PrizePicks indicators
        if '- Player' in text and ('Less' in text or 'More' in text):
            return 'prizepicks'
        
        # Underdog indicators
        if 'Higher' in text and 'Lower' in text:
            return 'underdog'
        
        return 'unknown'
    
    
    @staticmethod
    def parse_file(filepath: str) -> List[Dict]:
        """
        Auto-detect platform and parse file
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return UnifiedTennisParser.parse_text(content)
    
    
    @staticmethod
    def parse_text(text: str) -> List[Dict]:
        """
        Auto-detect platform and parse text
        """
        platform = UnifiedTennisParser.detect_platform(text)
        
        if platform == 'prizepicks':
            parser = PrizePicksParser()
            return parser.parse_text(text)
        
        elif platform == 'underdog':
            # Import Underdog parser
            from underdog_text_parser import UnderdogTextParser
            parser = UnderdogTextParser()
            return parser.parse_text(text)
        
        else:
            raise ValueError(
                "Could not detect platform. Text must be from PrizePicks or Underdog."
            )


# ============================================================================
# DATA ANALYSIS & EXPORT
# ============================================================================

class PrizePicksAnalyzer:
    """Analyze parsed PrizePicks data"""
    
    @staticmethod
    def print_summary(props: List[Dict]):
        """Print analysis summary"""
        print("\n" + "="*70)
        print("PRIZEPICKS TENNIS PROPS SUMMARY")
        print("="*70 + "\n")
        
        print(f"Total Players: {len(props)}")
        
        # Market distribution
        market_counts = {}
        for prop in props:
            for market in prop['markets'].keys():
                market_counts[market] = market_counts.get(market, 0) + 1
        
        print(f"\nMarket Distribution:")
        for market, count in sorted(market_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {market:30} {count:2} players")
        
        # Show sample player
        if props:
            print(f"\nSample Player: {props[0]['player_name']}")
            print(f"  Opponent: {props[0]['opponent']}")
            print(f"  Match Time: {props[0]['match_time']}")
            print(f"  Markets Available: {len(props[0]['markets'])}")
    
    
    @staticmethod
    def export_to_json(props: List[Dict], filepath: str):
        """Export to JSON"""
        with open(filepath, 'w') as f:
            json.dump(props, f, indent=2)


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """CLI for parsing PrizePicks props"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python prizepicks_parser.py <input_file> [output_json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Auto-detect and parse
    props = UnifiedTennisParser.parse_file(input_file)
    
    # Print summary
    analyzer = PrizePicksAnalyzer()
    analyzer.print_summary(props)
    
    # Export if requested
    if output_file:
        analyzer.export_to_json(props, output_file)
        print(f"\n✅ Exported to {output_file}")
    
    # Show sample
    if props:
        print("\n" + "="*70)
        print("SAMPLE PLAYER DATA")
        print("="*70)
        print(json.dumps(props[0], indent=2))


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        main()
    else:
        # Test with sample data
        sample_text = """
Elina Svitolina - Player
Elina Svitolina
@ Aryna Sabalenka Thu 2:30am
8.5
Total Games Won
LessMore
* 11.6K

Carlos Alcaraz - Player
Carlos Alcaraz
vs Alexander Zverev Thu 9:30pm
36.5
Total Games
LessMore
* 9.2K

Alexander Zverev - Player
Alexander Zverev
@ Carlos Alcaraz Thu 9:30pm
10
Aces
LessMore
* 2.9K
"""
        
        parser = PrizePicksParser()
        props = parser.parse_text(sample_text)
        
        analyzer = PrizePicksAnalyzer()
        analyzer.print_summary(props)
        
        print("\n" + "="*70)
        print("PARSED DATA")
        print("="*70)
        print(json.dumps(props, indent=2))
