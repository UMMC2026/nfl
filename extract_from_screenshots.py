"""
Extract props from screenshot images using OCR
Requires: pip install pytesseract pillow
Also needs Tesseract-OCR installed: https://github.com/UB-Mannheim/tesseract/wiki
"""
import json
import re
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("⚠️  pytesseract or Pillow not installed")
    print("Install with: pip install pytesseract pillow")
    print("Also install Tesseract-OCR: https://github.com/UB-Mannheim/tesseract/wiki")

def parse_underdog_screenshot(image_path):
    """Extract props from Underdog screenshot"""
    if not HAS_OCR:
        return []
    
    # OCR the image
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    
    print(f"\n{'='*70}")
    print(f"Processing: {Path(image_path).name}")
    print(f"{'='*70}")
    print("Raw OCR text:")
    print(text)
    print(f"{'='*70}\n")
    
    # Parse Underdog format
    lines = text.strip().split('\n')
    props = []
    
    i = 0
    while i < len(lines):
        # Look for player name pattern
        if i + 4 < len(lines):
            potential_player = lines[i].strip()
            team_pos = lines[i+1].strip()
            stat_or_line = lines[i+2].strip()
            stat_name = lines[i+3].strip()
            direction = lines[i+4].strip()
            
            # Basic validation
            if potential_player and team_pos and stat_name:
                # Extract team (3-letter code)
                team_match = re.search(r'\b([A-Z]{3})\b', team_pos)
                team = team_match.group(1) if team_match else "UNK"
                
                # Extract line (number)
                line_match = re.search(r'(\d+\.?\d*)', stat_or_line)
                line = float(line_match.group(1)) if line_match else 0
                
                # Map stat name
                stat_map = {
                    'Points': 'points',
                    'Rebounds': 'rebounds',
                    'Assists': 'assists',
                    'Pts+Rebs+Asts': 'pts+reb+ast',
                    '3-PT Made': '3pm',
                    'Blocks': 'blocks',
                    'Steals': 'steals'
                }
                stat = stat_map.get(stat_name, stat_name.lower().replace(' ', '_'))
                
                # Direction
                dir_clean = "higher" if "More" in direction or "Over" in direction else "lower"
                
                prop = {
                    "player": potential_player,
                    "team": team,
                    "stat": stat,
                    "line": line,
                    "direction": dir_clean
                }
                props.append(prop)
                i += 5  # Move past this prop
            else:
                i += 1
        else:
            i += 1
    
    return props

def main():
    screenshot_dir = Path("screenshots")
    all_props = []
    
    if not HAS_OCR:
        print("\n" + "="*70)
        print("MANUAL EXTRACTION MODE")
        print("="*70)
        print("\nSince OCR is not installed, please:")
        print("1. Open each screenshot")
        print("2. Copy the text (player, team, line, stat, direction)")
        print("3. Paste it when I analyze")
        print("\nOr install OCR:")
        print("  pip install pytesseract pillow")
        print("  Download Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
        return
    
    # Process all images
    for img_file in sorted(screenshot_dir.glob("image*.jpeg")):
        props = parse_underdog_screenshot(img_file)
        if props:
            print(f"✓ Extracted {len(props)} props from {img_file.name}")
            all_props.extend(props)
        else:
            print(f"⚠️  No props found in {img_file.name}")
    
    if all_props:
        # Save combined slate
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"screenshots_slate_{timestamp}.json"
        
        with open(output_file, "w") as f:
            json.dump(all_props, f, indent=2)
        
        print(f"\n{'='*70}")
        print(f"✓ COMBINED SLATE: {len(all_props)} props")
        print(f"✓ Saved to: {output_file}")
        print(f"{'='*70}")
        
        # Quick preview
        print("\nPreview:")
        for i, p in enumerate(all_props[:10], 1):
            print(f"  {i}. {p['player']:20} {p['stat']:12} {p['line']:>5.1f} {p['direction']:6}")
        
        if len(all_props) > 10:
            print(f"  ... and {len(all_props)-10} more")
        
        print(f"\nNext step: Run analysis")
        print(f"  python analyze_from_underdog_json.py --slate {output_file} --label SCREENSHOTS")
    else:
        print("\n❌ No props extracted from any screenshot")

if __name__ == "__main__":
    main()
