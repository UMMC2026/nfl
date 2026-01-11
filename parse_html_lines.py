#!/usr/bin/env python3
"""
Parse Underdog Fantasy HTML content and extract player prop lines.
Handles multi-line format from web interface.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

def parse_html_lines(html_content: str) -> List[Dict]:
    """
    Parse HTML content from Underdog Fantasy with multi-line stat format.
    
    Format:
    Player Name
    Team vs Team - TIME
    Line_Value
    Stat_Name
    Direction (Higher/Lower/Yes/No)
    [optional multiplier]
    """
    picks = []
    seen_picks = set()
    
    lines = html_content.split('\n')
    
    # Team abbreviations
    all_teams = {'NYG', 'DAL', 'CIN', 'CLE', 'JAX', 'TEN', 'DET', 'CHI', 'NE', 'MIA', 'NO', 'ATL', 
                 'HOU', 'IND', 'BAL', 'PIT', 'LV', 'KC', 'DEN', 'LAC', 'ARI', 'LAR', 'PHX', 'SEA',
                 'SF', 'GB', 'MIN', 'TB', 'WSH', 'PHI',
                 'BOS', 'NYK', 'ORL', 'TOR', 'SAS', 'POR', 'UTA', 'GSW', 'BKN',
                 'WAS', 'OKC', 'MIL', 'SAC', 'LAL', 'MEM'}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Skip section headers and UI text
        if any(skip in line for skip in ['Find teams', 'Pre-game', "Pick'em", 'athlete or team', 'More picks', 
                                          'Fewer picks', 'Signal-Callers', 'Pass Catchers', 'Ground and Pound',
                                          'Bucket Getters', 'Sharpshooters', 'Glass Cleaners', 'Popular',
                                          'Ravens', 'Steelers', 'In-game']):
            i += 1
            continue
        
        # Try to match player name (capitalized words, not team abbr, not stat keywords)
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z\'-]+)*$', line) and line not in all_teams:
            player_name = line
            current_player = player_name
            current_team = None
            
            # Look ahead for game line
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                
                # Check for game format: "TEAM vs/@ TEAM - TIME"
                game_match = re.search(r'([A-Z]{2,3})\s+(?:vs|@)\s+([A-Z]{2,3})\s*-', next_line)
                if game_match:
                    team1, team2 = game_match.groups()
                    if team1 in all_teams:
                        current_team = team1
                        i += 1
                        break
                
                # If we hit another player name or section, move back
                if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z\'-]+)*$', next_line) and next_line not in all_teams:
                    break
                
                i += 1
            
            # Now extract stats for this player
            if current_team:
                i += 1
                while i < len(lines):
                    current_line = lines[i].strip()
                    
                    # Stop if we hit another player or empty section
                    if not current_line:
                        i += 1
                        if i < len(lines) and re.match(r'^[A-Z][a-z]+', lines[i].strip()):
                            break
                        continue
                    
                    # Stop at next player
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z\'-]+)*$', current_line) and current_line not in all_teams:
                        break
                    
                    # Stop at section markers
                    if any(x in current_line for x in ['Signal-Callers', 'Bucket Getters', 'More picks', 'Fewer picks',
                                                       'Pass Catchers', 'Ground and Pound', 'Glass Cleaners', 'Sharpshooters']):
                        break
                    
                    # Try to match a line value (decimal number)
                    if re.match(r'^[\d.]+$', current_line):
                        try:
                            line_value = float(current_line)
                        except:
                            i += 1
                            continue
                        
                        # Next line should be stat name
                        i += 1
                        stat_name = None
                        while i < len(lines):
                            stat_line = lines[i].strip()
                            if stat_line and stat_line not in ['Higher', 'Lower', 'Yes', 'No'] and not re.match(r'^[\d.]+x?$', stat_line):
                                stat_name = stat_line.lower().replace(' ', '_').replace('+', 'plus')
                                i += 1
                                break
                            elif not stat_line:
                                i += 1
                                continue
                            else:
                                i += 1
                                break
                        
                        # Next line should be direction
                        direction = None
                        while i < len(lines):
                            dir_line = lines[i].strip()
                            if dir_line in ['Higher', 'Lower', 'Yes', 'No']:
                                direction = dir_line.lower()
                                i += 1
                                break
                            elif not dir_line:
                                i += 1
                                continue
                            else:
                                break
                        
                        # Create pick if we have all components
                        if stat_name and direction:
                            pick_key = (current_player, current_team, stat_name, line_value, direction)
                            if pick_key not in seen_picks:
                                pick = {
                                    "player": current_player,
                                    "team": current_team,
                                    "stat": stat_name,
                                    "line": line_value,
                                    "direction": direction
                                }
                                picks.append(pick)
                                seen_picks.add(pick_key)
                    else:
                        i += 1
        else:
            i += 1
    
    return picks


def merge_picks(existing_picks: List[Dict], new_picks: List[Dict]) -> List[Dict]:
    """
    Merge new picks with existing ones, avoiding duplicates.
    """
    existing_keys = set()
    for p in existing_picks:
        key = (p['player'], p.get('team', ''), p['stat'], p['line'], p['direction'])
        existing_keys.add(key)
    
    merged = existing_picks.copy()
    added_count = 0
    
    for pick in new_picks:
        key = (pick['player'], pick.get('team', ''), pick['stat'], pick['line'], pick['direction'])
        if key not in existing_keys:
            merged.append(pick)
            added_count += 1
            existing_keys.add(key)
    
    return merged, added_count

def main():
    # Read the HTML content from user
    html_file = Path("underdog_lines.txt")
    
    if not html_file.exists():
        print("❌ File 'underdog_lines.txt' not found. Paste Underdog lines there first.")
        return
    
    with open(html_file, 'r') as f:
        html_content = f.read()
    
    print("📊 Parsing Underdog Fantasy lines...")
    new_picks = parse_html_lines(html_content)
    
    print(f"✅ Extracted {len(new_picks)} picks from HTML")
    
    # Load existing picks
    picks_file = Path("picks.json")
    if picks_file.exists():
        with open(picks_file, 'r') as f:
            existing_picks = json.load(f)
    else:
        existing_picks = []
    
    print(f"📦 Found {len(existing_picks)} existing picks")
    
    # Merge
    merged, added = merge_picks(existing_picks, new_picks)
    
    print(f"🔀 Added {added} new unique picks")
    print(f"📝 Total picks now: {len(merged)}")
    
    # Show breakdown by team
    team_counts = {}
    for pick in new_picks:
        team = pick['team']
        team_counts[team] = team_counts.get(team, 0) + 1
    
    print(f"\n🎮 New picks by team:")
    for team, count in sorted(team_counts.items(), key=lambda x: -x[1]):
        print(f"   {team}: {count} picks")
    
    # Save merged picks
    with open(picks_file, 'w') as f:
        json.dump(merged, f, indent=2)
    
    print(f"\n✅ Saved {len(merged)} total picks to picks.json")

if __name__ == "__main__":
    main()
