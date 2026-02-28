#!/usr/bin/env python3
"""
Smart prop extractor that understands Underdog's vertical format:
    Anthony Edwards
    MIN vs NOP - 7:00PM CST
    28.5
    Points
    Higher
    Lower
"""
from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import re

def extract_underdog_props(text):
    """Parse Underdog's vertical prop format."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    props = []
    i = 0
    
    # Known stat types
    stat_types = {
        'Points', 'Rebounds', 'Assists', '3-Pointers Made', 'Pts + Rebs + Asts',
        'Rebounds + Assists', 'Points + Rebounds', 'Points + Assists',
        'Fantasy Points', 'Steals', 'Blocks', 'Blocks + Steals', 'Turnovers',
        'Double Doubles', 'Triple Doubles', 'FT Made', 'Offensive Rebounds',
        '1Q Points', '1Q Rebounds', '1Q Assists', '1H Points', '1H Rebounds',
        'Aces', 'Double Faults', 'Games Won', 'Sets Won',
        'Shots on Goal', 'Goals', 'Saves', 'Assists', 
        'Rushing Yards', 'Receiving Yards', 'Passing Yards', 'Touchdowns',
        'Receptions', 'Rush + Rec Yards', 'Pass + Rush Yards',
    }
    
    current_player = None
    current_matchup = None
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this looks like a player name (letters, spaces, periods, hyphens)
        # Skip known UI elements
        skip_words = ['pick\'em', 'drafts', 'live', 'results', 'rankings', 'news', 
                      'featured', 'popular', 'apply', 'boost', 'add picks', 'entry',
                      'rewards', 'flex', 'play', 'standard', 'nba only', 'left']
        
        if any(sw in line.lower() for sw in skip_words):
            i += 1
            continue
            
        # Match: "MIN vs NOP - 7:00PM CST" or "MIA @ BOS - 6:30PM CST"
        matchup_match = re.match(r'^[A-Z]{2,3}\s*(?:vs?|@)\s*[A-Z]{2,3}\s*-\s*\d', line)
        if matchup_match:
            current_matchup = line
            i += 1
            continue
        
        # Check if it's a line number (like 28.5, 19.5)
        line_match = re.match(r'^(\d+\.?\d*)$', line)
        if line_match and i + 2 < len(lines):
            prop_line = float(line_match.group(1))
            
            # Next line should be stat type
            next_line = lines[i + 1]
            stat_found = None
            for st in stat_types:
                if next_line.lower() == st.lower():
                    stat_found = st
                    break
            
            if stat_found:
                # Check for Higher/Lower
                higher_lower = []
                for j in range(i + 2, min(i + 5, len(lines))):
                    if lines[j].lower() in ['higher', 'lower', 'more', 'less']:
                        higher_lower.append(lines[j].lower())
                
                if current_player and higher_lower:
                    # Create prop entries
                    for direction in higher_lower:
                        dir_norm = 'higher' if direction in ['higher', 'more'] else 'lower'
                        props.append({
                            'source': 'Underdog',
                            'player': current_player,
                            'matchup': current_matchup,
                            'stat': stat_found.lower().replace(' + ', '+').replace('-', '').replace('  ', ' '),
                            'line': prop_line,
                            'direction': dir_norm,
                            'parsed': True,
                            'raw': f"{current_player} {stat_found} {prop_line} {dir_norm}"
                        })
                
                i += 3  # Skip line, stat, higher/lower
                continue
        
        # Check if this looks like a player name
        # Player names: 2+ words, letters only, not a stat type, not a team abbrev
        if (re.match(r'^[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Za-z\-\']+)+$', line) 
            and line not in stat_types 
            and len(line) > 5
            and not re.match(r'^[A-Z]{2,3}$', line)):
            current_player = line
        
        i += 1
    
    return props


def extract_prizepicks_props(text):
    """Parse PrizePicks format."""
    # Similar vertical format to Underdog
    return extract_underdog_props(text.replace('More', 'Higher').replace('Less', 'Lower'))


def extract_dk_props(text):
    """Parse DraftKings Pick6 format."""
    # Similar processing
    return extract_underdog_props(text)


def main():
    print("\n" + "=" * 60)
    print("🎯 SMART PROP EXTRACTOR")
    print("=" * 60)
    
    p = sync_playwright().start()
    
    try:
        browser = p.chromium.connect_over_cdp('http://localhost:9222')
        print("  ✓ Connected to Chrome!")
    except Exception as e:
        print(f"  ✗ Could not connect: {e}")
        p.stop()
        return
    
    contexts = browser.contexts
    pages = contexts[0].pages
    
    all_props = []
    
    for i, pg in enumerate(pages):
        url = pg.url.lower()
        title = pg.title()
        
        if 'underdog' in url:
            print(f"\n  📊 Extracting from Underdog...")
            text = pg.inner_text('body')
            props = extract_underdog_props(text)
            print(f"     ✓ Found {len(props)} props")
            all_props.extend(props)
            
        elif 'prizepicks' in url:
            print(f"\n  📊 Extracting from PrizePicks...")
            text = pg.inner_text('body')
            props = extract_prizepicks_props(text)
            for p in props:
                p['source'] = 'PrizePicks'
            print(f"     ✓ Found {len(props)} props")
            all_props.extend(props)
            
        elif 'draftkings' in url or 'pick6' in url:
            print(f"\n  📊 Extracting from DraftKings...")
            text = pg.inner_text('body')
            props = extract_dk_props(text)
            for p in props:
                p['source'] = 'DraftKings'
            print(f"     ✓ Found {len(props)} props")
            all_props.extend(props)
    
    # Dedupe by player+stat+line+direction
    seen = set()
    unique = []
    for prop in all_props:
        key = (prop.get('player'), prop.get('stat'), prop.get('line'), prop.get('direction'))
        if key not in seen:
            seen.add(key)
            unique.append(prop)
    
    all_props = unique
    
    print(f"\n" + "=" * 60)
    print(f"  TOTAL UNIQUE PROPS: {len(all_props)}")
    print("=" * 60)
    
    # Show sample by player
    by_player = {}
    for p in all_props:
        player = p.get('player', 'Unknown')
        if player not in by_player:
            by_player[player] = []
        by_player[player].append(p)
    
    print(f"\n  Found {len(by_player)} players:")
    for player, props in list(by_player.items())[:15]:
        print(f"\n  {player}:")
        for prop in props[:4]:
            stat = prop.get('stat', '?')
            line = prop.get('line', '?')
            direction = prop.get('direction', '?')
            print(f"    • {stat:<20} {line:>6} {direction}")
    
    # Save
    if all_props:
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_props': len(all_props),
            'players': len(by_player),
            'props': all_props
        }
        with open('outputs/props_latest.json', 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n  ✓ Saved {len(all_props)} props to outputs/props_latest.json")
    
    p.stop()


if __name__ == "__main__":
    main()
