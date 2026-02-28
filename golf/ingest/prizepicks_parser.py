"""
PrizePicks Golf Parser
======================
Parses PrizePicks golf props from text format.

Format Example:
    Hideki Matsuyama
    Farmers Insura... R2 - 11:32AM CST
    71.5
    Round Strokes
    Higher1.04x
    Lower0.87x
"""

import re
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import json
import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# Market type normalization
GOLF_MARKET_ALIASES = {
    'round strokes': 'round_strokes',
    'strokes': 'round_strokes',
    'tourney finishing position': 'finishing_position',
    'tournament finishing position': 'finishing_position',
    'birdies or better matchup': 'matchup',  # MATCHUP market
    'birdies or better': 'birdies',
    'pars or better': 'pars',
    'pars': 'pars',
    'eagles': 'eagles',
    'total strokes': 'tournament_total',
    'made cut': 'made_cut',
}


class PrizePicksGolfParser:
    """Parse PrizePicks golf props from text format."""
    
    def __init__(self):
        self.props = []
    
    def parse_text(self, text: str) -> List[Dict]:
        """
        Parse PrizePicks golf props from text.
        
        Returns:
            List of prop dicts
        """
        lines = text.strip().split('\n')
        self.props = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and avatar markers
            if not line or line.lower() == 'athlete or team avatar':
                i += 1
                continue
            
            # Check if this is a player name
            if self._is_player_name(line, lines, i):
                i = self._parse_player_block(lines, i)
            else:
                i += 1
        
        return self.props
    
    def _is_player_name(self, line: str, all_lines: List[str], idx: int) -> bool:
        """Detect if line is a player name."""
        # Skip known non-names
        if line.lower() in ['higher', 'lower', 'better', 'worse', 'over', 'under', 'less', 'more', 'trending']:
            return False
        
        # Skip if starts with number (prop value)
        if re.match(r'^\d', line):
            return False
        
        # Skip "- G" suffix lines (Underdog UI artifact)
        if line.endswith(' - G') or line.endswith('-G'):
            return False
        
        # Skip abbreviated names like "H.Matsuyama - G", "H.English - G"
        if re.search(r'\.\w+\s*-\s*G$', line):
            return False
        
        # Skip "X.YK" format (e.g. "2.6K" popularity numbers)
        if re.match(r'^[\d.]+K?$', line, re.I):
            return False
        
        # Skip if contains multiplier
        if re.search(r'\d+\.?\d*x', line.lower()):
            return False
        
        # Skip market types
        for market in GOLF_MARKET_ALIASES.keys():
            if market in line.lower():
                return False
        
        # Player names: 2+ words, starts with capital
        words = line.split()
        if len(words) >= 2:
            if all(w[0].isupper() for w in words if w and w[0].isalpha()):
                return True
        
        # Single word with tournament info on next line
        if len(words) == 1 and line[0].isupper():
            if idx + 1 < len(all_lines):
                next_line = all_lines[idx + 1].lower()
                if any(x in next_line for x in ['r1', 'r2', 'r3', 'r4', 'rd', 'am', 'pm', 'cst', 'est', 'vs ']):
                    return True
        
        return False
    
    def _parse_player_block(self, lines: List[str], start_idx: int) -> int:
        """Parse complete player prop block."""
        i = start_idx
        
        # Line 0: Player name
        player_name = lines[i].strip()
        i += 1
        
        # Line 1: Tournament info (or matchup info)
        tournament_name = None
        round_num = None
        tee_time = None
        opponent = None  # For matchup props
        
        if i < len(lines):
            tournament_line = lines[i].strip()
            
            # Skip if this looks like a prop value
            if not self._is_line_value(tournament_line):
                # Check if this is a MATCHUP (vs PLAYER_NAME)
                if tournament_line.lower().startswith('vs '):
                    # Extract opponent name
                    vs_match = re.match(r'vs\s+(.+?)\s+(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat|\d{1,2}:)', tournament_line, re.I)
                    if vs_match:
                        potential_opponent = vs_match.group(1).strip()
                        # Check if it's a course name
                        course_indicators = ["pines", "national", "club", "country", "golf", "resort", 
                                           "links", "beach", "hills", "south", "north", "east", "west"]
                        is_course = any(ind in potential_opponent.lower() for ind in course_indicators)
                        
                        if not is_course:
                            opponent = potential_opponent.title()
                            tournament_name = "Matchup"
                
                # Extract tournament name (if not a matchup)
                if opponent is None:
                    if '...' in tournament_line:
                        tournament_name = tournament_line.split('...')[0].strip()
                    elif tournament_line.lower().startswith('vs '):
                        # Course-based "vs" line
                        parts = tournament_line[3:].split(' RD')
                        if parts:
                            tournament_name = parts[0].strip()
                    else:
                        tournament_name = tournament_line.split(' R')[0].strip() if ' R' in tournament_line else tournament_line
                    
                    # Expand common abbreviations
                    expansions = {
                        "Farmers Insura": "Farmers Insurance Open",
                        "AT&T Pebble": "AT&T Pebble Beach Pro-Am",
                        "WM Phoenix": "WM Phoenix Open",
                        "Genesis Invit": "Genesis Invitational",
                        "Torrey Pines": "Farmers Insurance Open",
                        "Torrey Pines - South": "Farmers Insurance Open",
                    }
                    if tournament_name:
                        for abbrev, full in expansions.items():
                            if abbrev.lower() in tournament_name.lower():
                                tournament_name = full
                                break
                
                # Extract round number (RD 4 or R2 format)
                round_match = re.search(r'R(?:D)?\s*(\d+)', tournament_line, re.I)
                if round_match:
                    round_num = int(round_match.group(1))
                
                # Extract tee time
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]?[Mm]?)', tournament_line, re.I)
                if time_match:
                    tee_time = time_match.group(1)
                
                i += 1
        
        # Parse all props for this player
        player_props = []
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty
            if not line:
                i += 1
                continue
            
            # Skip avatar marker
            if line.lower() == 'athlete or team avatar':
                i += 1
                continue
            
            # Stop if we hit next player
            if self._is_player_name(line, lines, i):
                break
            
            # Try to parse as prop
            if self._is_line_value(line):
                prop_data, new_idx = self._parse_prop(lines, i)
                
                if prop_data:
                    prop_data['player'] = player_name
                    prop_data['tournament'] = tournament_name
                    prop_data['round'] = round_num
                    prop_data['tee_time'] = tee_time
                    
                    # Add opponent for matchup markets
                    if opponent:
                        prop_data['opponent'] = opponent
                        # Override market to matchup if this has an opponent
                        if 'matchup' in prop_data.get('market', '').lower():
                            prop_data['market'] = 'matchup'
                    
                    player_props.append(prop_data)
                
                i = new_idx
            else:
                i += 1
        
        self.props.extend(player_props)
        return i
    
    def _parse_prop(self, lines: List[str], start_idx: int) -> tuple:
        """Parse single prop."""
        i = start_idx
        
        # Line value
        try:
            line_value = float(lines[i].strip())
        except ValueError:
            return None, i + 1
        
        # Skip "Trending" numbers (like 907, 836, etc.) - these are popularity metrics
        # Typically > 100 and followed by a player name
        if line_value > 100 and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # If next line looks like a player name, this is a trending number
            if self._looks_like_player_name(next_line):
                return None, i + 1
        
        i += 1
        
        # Market type
        if i >= len(lines):
            return None, i
        
        market_type_raw = lines[i].strip()
        
        # REJECT if market type looks like a player name
        if self._looks_like_player_name(market_type_raw):
            return None, i
        
        market_type = self._normalize_market_type(market_type_raw)
        i += 1
        
        # Parse Higher/Lower/Better with odds
        higher_mult = None
        lower_mult = None
        better_mult = None
        
        # Look for direction + odds on next few lines
        for _ in range(4):
            if i >= len(lines):
                break
            
            current_line = lines[i].strip().lower()
            
            # Check for combined format "Higher1.04x"
            if current_line.startswith('higher'):
                higher_mult = self._extract_odds(current_line)
                i += 1
            elif current_line.startswith('lower'):
                lower_mult = self._extract_odds(current_line)
                i += 1
            elif current_line.startswith('better'):
                better_mult = self._extract_odds(current_line)
                i += 1
            elif current_line.startswith('worse'):
                i += 1  # Skip worse, we use better
            elif self._is_line_value(lines[i].strip()) or self._is_player_name(lines[i].strip(), lines, i):
                break
            else:
                # Check if line is just "Higher" or "Lower" without odds
                if current_line in ['higher', 'lower', 'better', 'worse']:
                    i += 1
                else:
                    break
        
        return {
            'line': line_value,
            'market': market_type,
            'market_raw': market_type_raw,
            'higher_mult': higher_mult,
            'lower_mult': lower_mult,
            'better_mult': better_mult,
            'platform': 'prizepicks',
        }, i
    
    def _looks_like_player_name(self, text: str) -> bool:
        """Check if text looks like a player name (2+ capitalized words)."""
        words = text.split()
        if len(words) >= 2:
            # Check if all words start with capital
            if all(w[0].isupper() for w in words if w and w[0].isalpha()):
                # Not a market type
                for market in GOLF_MARKET_ALIASES.keys():
                    if market in text.lower():
                        return False
                return True
        return False
    
    def _is_line_value(self, text: str) -> bool:
        """Check if text is a line value."""
        try:
            float(text)
            return True
        except ValueError:
            return False
    
    def _normalize_market_type(self, raw_type: str) -> str:
        """Normalize market type to canonical form."""
        normalized = raw_type.lower().strip()
        return GOLF_MARKET_ALIASES.get(normalized, normalized.replace(' ', '_'))
    
    def _extract_odds(self, text: str) -> Optional[float]:
        """Extract odds multiplier from text like 'Higher1.04x'."""
        match = re.search(r'(\d+\.?\d*)x', text)
        if match:
            return float(match.group(1))
        return None


def parse_prizepicks_slate(text: str) -> List[Dict]:
    """Quick parse function for PrizePicks golf slate."""
    parser = PrizePicksGolfParser()
    return parser.parse_text(text)


def display_parsed_props(props: List[Dict]):
    """Display parsed props in readable format."""
    print(f"\n{'='*60}")
    print(f"⛳ PARSED PRIZEPICKS GOLF PROPS: {len(props)} props")
    print(f"{'='*60}")
    
    if not props:
        print("No props parsed.")
        return
    
    # Get tournament info
    tournament = props[0].get('tournament', 'Unknown')
    round_num = props[0].get('round', '?')
    print(f"\n🏆 {tournament} | Round {round_num}")
    
    # Group by player
    players = {}
    for prop in props:
        player = prop['player']
        if player not in players:
            players[player] = []
        players[player].append(prop)
    
    print(f"\n📋 {len(players)} Players:")
    
    for player, player_props in players.items():
        tee_time = player_props[0].get('tee_time', '')
        print(f"\n  {player}", end="")
        if tee_time:
            print(f" ({tee_time})")
        else:
            print()
        
        for prop in player_props:
            market = prop.get('market', 'unknown')
            line = prop.get('line', 0)
            
            mults = []
            if prop.get('higher_mult'):
                mults.append(f"H:{prop['higher_mult']}x")
            if prop.get('lower_mult'):
                mults.append(f"L:{prop['lower_mult']}x")
            if prop.get('better_mult'):
                mults.append(f"B:{prop['better_mult']}x")
            
            mult_str = " ".join(mults) if mults else ""
            print(f"    • {market}: {line} {mult_str}")
    
    # Market summary
    market_counts = {}
    for prop in props:
        market = prop.get('market_raw', prop.get('market', 'unknown'))
        market_counts[market] = market_counts.get(market, 0) + 1
    
    print(f"\n📊 Market Distribution:")
    for market, count in sorted(market_counts.items(), key=lambda x: -x[1]):
        print(f"    {market}: {count}")


def save_parsed_slate(props: List[Dict], output_path: Path):
    """Save parsed slate to JSON."""
    data = {
        "parsed_at": datetime.now().isoformat(),
        "platform": "prizepicks",
        "sport": "GOLF",
        "prop_count": len(props),
        "props": props,
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    return output_path


if __name__ == "__main__":
    # Test with sample data
    sample_text = """
athlete or team avatar
Hideki Matsuyama
Farmers Insura... R2 - 11:32AM CST

71.5
Round Strokes

Higher
1.04x

Lower
0.87x

20.5
Tourney Finishing Position

Better
0.67x
3.5
Birdies or Better

Higher
0.83x

Lower
1.08x
athlete or team avatar
Justin Rose
Farmers Insura... R2 - 11:32AM CST

71.5
Round Strokes

Higher

Lower

20.5
Tourney Finishing Position

Better
0.62x
3.5
Birdies or Better

Higher

Lower
athlete or team avatar
Si Woo Kim
Farmers Insura... R2 - 12:27PM CST

68.5
Round Strokes

Higher
1.03x

Lower
0.94x

20.5
Tourney Finishing Position

Better
0.72x
4.5
Birdies or Better

Higher
0.77x

Lower
1.06x
athlete or team avatar
Patrick Cantlay
Farmers Insura... R2 - 11:32AM CST

68.5
Round Strokes

Higher
1.03x

Lower
0.94x

20.5
Tourney Finishing Position

Better
1.32x
athlete or team avatar
Cameron Young
Farmers Insura... R2 - 11:32AM CST

68.5
Round Strokes

Higher
1.03x

Lower
0.88x

20.5
Tourney Finishing Position

Better
0.97x
5.5
Birdies or Better

Higher

Lower
"""
    
    print("=" * 60)
    print("PRIZEPICKS GOLF PARSER TEST")
    print("=" * 60)
    
    props = parse_prizepicks_slate(sample_text)
    display_parsed_props(props)
    
    # Save to file
    output_dir = Path(__file__).parent.parent / "outputs"
    output_file = output_dir / f"prizepicks_parsed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_parsed_slate(props, output_file)
    print(f"\n✓ Saved to {output_file}")
