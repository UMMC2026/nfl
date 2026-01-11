#!/usr/bin/env python
"""
Auto-detect and ingest Underdog game data from posted text.
Runs automatically when game data is detected.
"""

import json
import re
from pathlib import Path
from typing import Dict, List


class UnderDogIngester:
    """Auto-detect and parse Underdog player lines."""
    
    # Stat name mappings
    STAT_MAP = {
        'pass yards': 'pass_yards',
        'rush yards': 'rush_yards',
        'receiving yards': 'rec_yards',
        'rec yards': 'rec_yards',
        'receptions': 'receptions',
        'rush + rec tds': 'rush+rec_tds',
        'rush + rec yards': 'rush+rec_yards',
        'pass + rush yards': 'pass+rush_yards',
        'pass tds': 'pass_tds',
        'rush tds': 'rush_tds',
        'first td scorer': 'first_td',
        'points': 'points',
        'rebounds': 'rebounds',
        'assists': 'assists',
        'pts+reb+ast': 'pts+reb+ast',
    }
    
    @staticmethod
    def extract_game_info(text: str) -> Dict:
        """Extract game time and teams from text."""
        game_match = re.search(
            r'([A-Z]{3})\s*(?:@|vs)\s*([A-Z]{3})\s*-\s*([\d:]+[AP]M)',
            text,
            re.IGNORECASE
        )
        
        if game_match:
            return {
                'away': game_match.group(1).upper(),
                'home': game_match.group(2).upper(),
                'time': game_match.group(3),
            }
        return None
    
    @staticmethod
    def detect_game_data(text: str) -> bool:
        """Check if text contains Underdog game data."""
        # Look for patterns like "Higher/Lower", stats, multipliers
        patterns = [
            r'Higher|Lower',
            r'\d+\.\d+x',  # Multipliers like 1.04x
            r'\d+\.5',      # Props like 28.5 points
            r'First TD Scorer',
            r'Rush \+ Rec',
        ]
        
        return any(re.search(p, text) for p in patterns)
    
    @staticmethod
    def parse_player_block(block: str) -> List[Dict]:
        """Parse single player's props from a block."""
        picks = []
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        
        if len(lines) < 3:
            return picks
        
        player_name = lines[0]
        
        # Extract game info from lines 1-4
        game_info = None
        team = None
        for line in lines[1:5]:
            info = UnderDogIngester.extract_game_info(line)
            if info:
                game_info = info
                team = info['away']
                break
        
        if not game_info or not team:
            return picks
        
        # Parse props: look for DECIMAL STAT pattern
        i = 0
        current_line_value = None
        current_stat = None
        
        for i, line in enumerate(lines):
            # Check if line is a stat line (decimal number)
            if re.match(r'^\d+\.?\d*$', line):
                current_line_value = float(line)
                # Stat should be on next line
                if i + 1 < len(lines):
                    current_stat = lines[i + 1]
                continue
            
            # Check if this is a direction
            if line in ['Higher', 'Lower', 'Yes', 'No'] and current_line_value and current_stat:
                stat_norm = UnderDogIngester.normalize_stat(current_stat)
                dir_norm = UnderDogIngester.normalize_direction(line)
                
                if stat_norm and dir_norm:
                    pick = {
                        'player': player_name,
                        'team': team,
                        'stat': stat_norm,
                        'line': current_line_value,
                        'direction': dir_norm,
                    }
                    picks.append(pick)
                
                current_line_value = None
                current_stat = None
        
        return picks
    
    @staticmethod
    def normalize_stat(text: str) -> str:
        """Normalize stat names."""
        text_lower = text.lower()
        
        for key, val in UnderDogIngester.STAT_MAP.items():
            if key in text_lower:
                return val
        
        # Fallback: clean up text
        return text_lower.replace(' ', '_')
    
    @staticmethod
    def normalize_direction(text: str) -> str:
        """Convert direction to standard format."""
        if not text:
            return None
        
        text_lower = text.lower()
        if 'higher' in text_lower or 'over' in text_lower:
            return 'higher'
        elif 'lower' in text_lower or 'under' in text_lower:
            return 'lower'
        elif text_lower in ['yes']:
            return 'yes'
        elif text_lower in ['no']:
            return 'no'
        
        return None
    
    @staticmethod
    def ingest(text: str, auto_save: bool = True) -> List[Dict]:
        """Main ingestion pipeline."""
        
        # Check if it's game data
        if not UnderDogIngester.detect_game_data(text):
            print("⚠️ Text doesn't appear to contain Underdog game data")
            return []
        
        # Split by player sections
        blocks = re.split(r'athlete or team avatar\n', text)
        
        all_picks = []
        for block in blocks:
            if block.strip():
                picks = UnderDogIngester.parse_player_block(block)
                all_picks.extend(picks)
        
        if not all_picks:
            print("❌ No picks extracted")
            return []
        
        print(f"✅ Detected and extracted {len(all_picks)} picks")
        print(f"   Players: {len(set(p['player'] for p in all_picks))}")
        print(f"   Sample: {all_picks[0]['player']} - {all_picks[0]['stat']}")
        
        if auto_save:
            UnderDogIngester.save_picks(all_picks)
        
        return all_picks
    
    @staticmethod
    def save_picks(picks: List[Dict]):
        """Merge and save picks to picks.json."""
        picks_file = Path('picks.json')
        
        # Load existing
        if picks_file.exists():
            with open(picks_file, 'r') as f:
                existing = json.load(f)
        else:
            existing = []
        
        # Merge (new picks override old ones with same player+stat+line)
        key_func = lambda p: (p['player'], p['team'], p['stat'], p['line'])
        merged_dict = {key_func(p): p for p in existing}
        merged_dict.update({key_func(p): p for p in picks})
        
        merged = list(merged_dict.values())
        
        # Save
        with open(picks_file, 'w') as f:
            json.dump(merged, f, indent=2)
        
        print(f"💾 Saved {len(merged)} total picks to picks.json")


if __name__ == '__main__':
    # Can be called from command line with file
    import sys
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            text = f.read()
        UnderDogIngester.ingest(text)
    else:
        print("Usage: python auto_ingest.py <data.txt>")
        print("\nOr import and use:")
        print("  from auto_ingest import UnderDogIngester")
        print("  UnderDogIngester.ingest(text_data)")
