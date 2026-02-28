#!/usr/bin/env python3
"""Extract props from all open Chrome tabs."""
from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import re

def parse_prop_text(raw, source):
    result = {'source': source, 'raw': raw, 'player': None, 'stat': None, 'line': None, 'direction': None, 'parsed': False}
    dir_match = re.search(r'\b(More|Less|Higher|Lower|Over|Under)\b', raw, re.IGNORECASE)
    if dir_match:
        d = dir_match.group(1).lower()
        result['direction'] = 'higher' if d in ['more', 'higher', 'over'] else 'lower'
    line_match = re.search(r'(\d+\.?\d*)', raw)
    if line_match:
        result['line'] = float(line_match.group(1))
    stat_patterns = [
        (r'\b(Points?|PTS)\b', 'points'), 
        (r'\b(Rebounds?|REB|REBS)\b', 'rebounds'), 
        (r'\b(Assists?|AST|ASTS)\b', 'assists'), 
        (r'\b(3PM|3-?Pointers?|Threes?)\b', '3pm'),
        (r'\b(Steals?|STL)\b', 'steals'),
        (r'\b(Blocks?|BLK)\b', 'blocks'),
        (r'\b(PRA|Pts\+Reb\+Ast)\b', 'pra'),
        (r'\b(PA|Pts\+Ast)\b', 'pts+ast'),
        (r'\b(PR|Pts\+Reb)\b', 'pts+reb'),
        (r'\b(RA|Reb\+Ast)\b', 'reb+ast'),
        (r'\b(Fantasy|FPTS)\b', 'fantasy'), 
        (r'\b(SOG|Shots? on Goal)\b', 'sog'), 
        (r'\b(Saves?)\b', 'saves'),
        (r'\b(Goals?)\b', 'goals'),
        (r'\b(Rushing|Rush Yards?)\b', 'rush_yards'),
        (r'\b(Receiving|Rec Yards?)\b', 'rec_yards'),
        (r'\b(Passing|Pass Yards?)\b', 'pass_yards'),
        (r'\b(Touchdowns?|TDs?)\b', 'touchdowns'),
        (r'\b(Aces?)\b', 'aces'),
    ]
    for pattern, stat_name in stat_patterns:
        if re.search(pattern, raw, re.IGNORECASE):
            result['stat'] = stat_name
            break
    name_match = re.match(r'^([A-Za-z\s\.\'\-]+?)(?=\s*\d|\s*(?:More|Less|Higher|Lower))', raw)
    if name_match:
        result['player'] = name_match.group(1).strip()
    if result['player'] and result['line'] is not None and result['direction']:
        result['parsed'] = True
    return result


def extract_from_page(page, source):
    """Extract props from a page."""
    # Scroll to load more content
    try:
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(500)
    except:
        pass
    
    all_text = page.inner_text('body')
    results = []
    
    # Split into lines and look for prop patterns
    for line in all_text.split('\n'):
        line = line.strip()
        if len(line) < 5:
            continue
            
        # Skip navigation/UI elements
        if line.lower().startswith('more picks') or line.lower() == 'more' or line.lower() == 'less':
            continue
        if 'sign in' in line.lower() or 'log in' in line.lower():
            continue
        if len(line) > 200:  # Skip very long text blocks
            continue
            
        # Look for prop patterns
        has_direction = any(kw in line.lower() for kw in ['more', 'less', 'over', 'under', 'higher', 'lower'])
        has_number = any(c.isdigit() for c in line)
        
        if has_direction and has_number:
            parsed = parse_prop_text(line, source)
            if parsed.get('line') and parsed['line'] > 0:
                results.append(parsed)
    
    # Also try to find structured prop elements
    try:
        # Common prop card selectors
        selectors = [
            "[class*='projection']",
            "[class*='pick-cell']", 
            "[class*='player-prop']",
            "[class*='stat-line']",
            "[class*='over-under']",
            "[data-testid*='pick']",
            "[data-testid*='prop']",
        ]
        
        for sel in selectors:
            try:
                elements = page.locator(sel).all()
                for elem in elements[:50]:  # Limit to first 50
                    try:
                        txt = elem.inner_text()
                        if txt and len(txt) > 3 and len(txt) < 200:
                            parsed = parse_prop_text(txt, source)
                            if parsed.get('line') and parsed['line'] > 0:
                                results.append(parsed)
                    except:
                        pass
            except:
                pass
    except:
        pass
    
    # Dedupe
    seen = set()
    unique = []
    for r in results:
        key = r.get('raw', '')
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def main():
    print("\n" + "=" * 60)
    print("🔌 EXTRACTING FROM ALL CHROME TABS")
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
    if not contexts:
        print("  ✗ No browser contexts found")
        p.stop()
        return
    
    pages = contexts[0].pages
    print(f"\n  Found {len(pages)} tabs:")
    
    all_props = []
    
    for i, pg in enumerate(pages):
        title = pg.title()[:40]
        url = pg.url[:50]
        print(f"\n  [{i+1}] {title}")
        
        # Determine source based on URL
        if 'underdog' in pg.url.lower():
            source = 'Underdog'
        elif 'draftkings' in pg.url.lower() or 'pick6' in pg.url.lower():
            source = 'DraftKings'
        elif 'prizepicks' in pg.url.lower():
            source = 'PrizePicks'
        else:
            print(f"      Skipping (not a prop site)")
            continue
        
        props = extract_from_page(pg, source)
        print(f"      ✓ {source}: {len(props)} props")
        all_props.extend(props)
    
    print(f"\n" + "=" * 60)
    print(f"  TOTAL: {len(all_props)} props extracted")
    print(f"  PARSED: {sum(1 for x in all_props if x.get('parsed'))} props")
    print("=" * 60)
    
    # Show sample
    parsed = [x for x in all_props if x.get('parsed')]
    if parsed:
        print("\n  Sample parsed props (first 25):")
        for r in parsed[:25]:
            player = (r.get('player') or '?')[:20]
            stat = r.get('stat') or '?'
            line = r.get('line') if r.get('line') is not None else '?'
            direction = r.get('direction') or '?'
            source = r.get('source', '?')[:3]
            print(f"    {source} | {player:<20} {stat:<12} {line:>6} {direction}")
    
    # Save
    if all_props:
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_props': len(all_props),
            'parsed_props': sum(1 for x in all_props if x.get('parsed')),
            'props': all_props
        }
        with open('outputs/props_latest.json', 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n  ✓ Saved to outputs/props_latest.json")
    
    p.stop()


if __name__ == "__main__":
    main()
