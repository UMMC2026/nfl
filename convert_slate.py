#!/usr/bin/env python3
"""Convert simplified slate format to JSON."""

import json

def parse_slate_file(filename):
    """Parse simplified slate format."""
    plays = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '@' in line:  # Skip empty lines and game headers
                continue
            
            parts = line.split()
            if len(parts) < 5:
                continue
            
            # Extract player name (all parts until we hit a team abbreviation)
            player_parts = []
            team = None
            remaining = []
            
            for i, part in enumerate(parts):
                if part.isupper() and len(part) == 3:  # Team abbreviation
                    team = part
                    remaining = parts[i+1:]
                    break
                player_parts.append(part)
            
            if not team or not remaining:
                continue
            
            player = ' '.join(player_parts)
            
            # Parse line value and stat
            try:
                line_value = float(remaining[0])
            except:
                continue
            
            # Get stat name (everything between line value and Higher/Lower)
            stat_parts = []
            for part in remaining[1:]:
                if part in ['Higher', 'Lower']:
                    break
                stat_parts.append(part)
            
            stat_name = ' '.join(stat_parts)
            
            # Map stat name
            stat_key = map_stat(stat_name)
            if not stat_key:
                continue
            
            # Check for Higher and Lower
            has_higher = 'Higher' in line
            has_lower = 'Lower' in line
            
            if has_higher:
                plays.append({
                    'player': player,
                    'team': team,
                    'stat': stat_key,
                    'line': line_value,
                    'direction': 'higher'
                })
            
            if has_lower:
                plays.append({
                    'player': player,
                    'team': team,
                    'stat': stat_key,
                    'line': line_value,
                    'direction': 'lower'
                })
    
    return {
        'date': '2026-01-13',
        'league': 'NBA',
        'plays': plays
    }

def map_stat(stat_name):
    """Map stat names."""
    stat_name_lower = stat_name.lower().replace('+', '').replace(' ', '')
    
    if 'ptsrebsasts' in stat_name_lower or 'pra' in stat_name_lower:
        return 'pra'
    elif 'ptsreb' in stat_name_lower:
        return 'pts+reb'
    elif 'ptsast' in stat_name_lower:
        return 'pts+ast'
    elif 'points' in stat_name_lower:
        return 'points'
    elif 'rebounds' in stat_name_lower:
        return 'rebounds'
    elif 'assists' in stat_name_lower:
        return 'assists'
    elif '3pm' in stat_name_lower or '3-pointers' in stat_name_lower:
        return '3pm'
    
    return None

if __name__ == '__main__':
    result = parse_slate_file('slate_simplified.txt')
    
    with open('nba_tonight_slate.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ Parsed {len(result['plays'])} props")
    print(f"💾 Saved to: nba_tonight_slate.json")
    print(f"\n🎯 Run: .venv\\Scripts\\python.exe display_nba_picks.py")
