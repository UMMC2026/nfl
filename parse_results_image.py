"""
Parse game results from screenshot images.
Supports: Underdog results screenshots, ESPN box scores, etc.

Usage:
    python parse_results_image.py <image_path>
    python parse_results_image.py screenshots/results.png

Install OCR engine first:
    pip install easyocr  (recommended, no external binary needed)
"""

import re
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

PROJECT_ROOT = Path(__file__).parent


def extract_text_easyocr(image_path: str) -> str:
    """Extract text using EasyOCR (recommended)."""
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    results = reader.readtext(image_path)
    return '\n'.join([text for _, text, _ in results])


def extract_text_tesseract(image_path: str) -> str:
    """Extract text using Tesseract OCR."""
    img = Image.open(image_path)
    return pytesseract.image_to_string(img)


def normalize_stat(stat: str) -> str:
    """Normalize stat name to standard format."""
    stat = stat.lower().strip()
    mappings = {
        'pts': 'points',
        'point': 'points',
        'reb': 'rebounds',
        'rebound': 'rebounds',
        'ast': 'assists',
        'assist': 'assists',
        '3pm': '3pm',
        '3pt': '3pm',
        'threes': '3pm',
        'three pointers': '3pm',
        'stl': 'steals',
        'steal': 'steals',
        'blk': 'blocks',
        'block': 'blocks',
        'to': 'turnovers',
        'turnover': 'turnovers',
        'pra': 'pts+reb+ast',
        'pts+rebs+asts': 'pts+reb+ast',
        'rebs+asts': 'rebs+asts',
        'reb+ast': 'rebs+asts',
        'r+a': 'rebs+asts',
    }
    return mappings.get(stat, stat)


def normalize_player_name(name: str) -> str:
    """Normalize player name."""
    name = name.strip()
    # Handle "J. Smith" -> "J. Smith" (keep as is)
    # Handle "SMITH" -> "Smith"
    if name.isupper():
        name = name.title()
    return name


def normalize_line_value(value: float, stat: str = None) -> float:
    """
    Fix OCR decimal point misreads.
    Examples: 555 -> 5.5 (rebs+asts), 125 -> 12.5 (points), 295 -> 29.5 (pts+reb+ast)
    
    Prop lines typically end in .5, so we look for that pattern.
    OCR often doubles digits (5.5 -> 55, 555) so we also try dropping repeated digits.
    """
    # Max reasonable values for props (anything above is likely OCR error)
    MAX_REASONABLE = {
        'rebounds': 25, 'rebs': 25, 'reb': 25,
        'assists': 20, 'asts': 20, 'ast': 20,
        'steals': 5, 'stl': 5,
        'blocks': 6, 'blk': 6,
        'points': 60, 'pts': 60,
        'pts+reb+ast': 80, 'pra': 80,
        'rebs+asts': 30, 'reb+ast': 30,
        '3pm': 12, 'threes': 12,
        'turnovers': 10, 'to': 10,
    }
    
    stat_key = (stat or '').lower().replace(' ', '')
    max_val = MAX_REASONABLE.get(stat_key, 100)
    
    # If value exceeds reasonable max, try to fix decimal
    if value > max_val:
        str_val = str(int(value))
        candidates = []
        
        # Most prop lines end in .5 - try finding that pattern first
        if str_val.endswith('5') and len(str_val) >= 2:
            # Try standard .5 patterns: 125 -> 12.5, 295 -> 29.5
            for i in range(len(str_val) - 1, 0, -1):
                candidate = float(str_val[:i] + '.' + str_val[i:])
                if candidate <= max_val and str(candidate).endswith('.5'):
                    candidates.append(candidate)
            
            # OCR often doubles the 5: 5.5 -> 55 or 555. Try dropping a 5.
            # 555 -> 55 -> 5.5; 1255 -> 125 -> 12.5
            if str_val.endswith('55'):
                reduced = str_val[:-1]  # Drop one 5
                for i in range(len(reduced) - 1, 0, -1):
                    candidate = float(reduced[:i] + '.' + reduced[i:])
                    if candidate <= max_val and str(candidate).endswith('.5'):
                        candidates.append(candidate)
        
        # If we found .5 candidates, prefer the largest reasonable one
        if candidates:
            return max(candidates)
        
        # Fallback: try inserting decimal at various positions, prefer larger values
        for i in range(len(str_val) - 1, 0, -1):
            candidate = float(str_val[:i] + '.' + str_val[i:])
            if candidate <= max_val:
                return candidate
    
    return value


def parse_prizepicks_results(text: str) -> list[dict]:
    """
    Parse PrizePicks results format where each pick is on multiple lines:
    Kevin Durant F
    245
    HOUIII 5AS1O6
    Final
    Points
    """
    results = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Detect lineup status (LOST or WON)
    lineup_status = None
    if any('LOST' in l.upper() for l in lines):
        lineup_status = False
    elif any('WON' in l.upper() or 'WIN' in l.upper() for l in lines):
        lineup_status = True
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Player name pattern: capitalized words, optionally followed by position
        player_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)*(?:\s+(?:Jr\.|Sr\.|III|II))?)\s*(?:[FGC][-]?[FC])?$', line)
        
        if player_match and i + 4 < len(lines):
            player = normalize_player_name(player_match.group(1))
            
            # Next line should be the line value
            next_line = lines[i+1]
            line_match = re.search(r'(\d+\.?\d*)', next_line)
            if not line_match:
                i += 1
                continue
            
            line_value = float(line_match.group(1))
            # Fix OCR decimal misreads (stat not known yet, use generic max)
            line_value = normalize_line_value(line_value)
            
            # Look for "Final" marker within next 4 lines
            stat = None
            for j in range(i+2, min(i+6, len(lines))):
                if 'Final' in lines[j]:
                    # Stat should be on next line
                    if j+1 < len(lines):
                        stat_text = lines[j+1]
                        stat = normalize_stat(stat_text)
                        break
            
            if stat:
                # For PrizePicks, we use lineup status as default
                # Individual picks don't show HIT/MISS, only overall lineup
                results.append({
                    'player': player,
                    'stat': stat,
                    'line': line_value,
                    'direction': None,  
                    'hit': lineup_status,  # Use overall lineup result
                    'raw_line': f"{player} {stat} {line_value}"
                })
                i = j + 2
                continue
        
        i += 1
    
    return results


def parse_underdog_results(text: str) -> list[dict]:
    """
    Parse Underdog Pick'em results from screenshot.
    Enhanced to handle Underdog's actual OCR output format:
    - Player line on one row, WON/LOST on adjacent lines
    - "J. Randle 23.5 39 PTS ... WON"
    """
    results = []
    lines = text.split('\n')
    
    # First pass: Build context by looking at consecutive lines
    # Underdog format: Player info line, then actual value, then WON/LOST
    full_text = ' '.join(lines)  # For context matching
    
    # Pattern for Underdog app format:
    # "PlayerName line_value actual_value STAT WON/LOST"
    # e.g., "J. Randle 23.5 39 PTS WON" or "R Gobert 10.5 13 REB WON"
    underdog_pattern = re.compile(
        r'([A-Z][.:]?\s*[A-Za-z]+(?:-[A-Za-z]+)?(?:\s+[A-Za-z]+)?)'  # Player name (J. Randle, S. Gilgeous-Alex)
        r'\s+(\d+\.?\d*)\s+'  # Line value (23.5)
        r'(\d+)\s+'            # Actual value (39)
        r'(PTS|REB|AST|3PM|STL|BLK|TO|P\+R\+A|REB\+AST|REBS\+ASTS|R\+A|1H\s*PTS)\s*'  # Stat type
        r'.*?(WON|LOST|PENDING|CANCEL)',  # Result
        re.IGNORECASE
    )
    
    for match in underdog_pattern.finditer(full_text):
        player = match.group(1).strip()
        # Clean up player name: "J. Randle" -> "J. Randle", "R Gobert" -> "R. Gobert"
        player = re.sub(r'^([A-Z])\s+', r'\1. ', player)  # "R Gobert" -> "R. Gobert"
        player = re.sub(r'[_:]', '', player)  # Remove artifacts
        
        line_val = float(match.group(2))
        actual_val = int(match.group(3))
        stat_raw = match.group(4).upper().replace(' ', '')
        result_str = match.group(5).upper()
        
        # Normalize stat
        stat_map = {
            'PTS': 'points', 'REB': 'rebounds', 'AST': 'assists',
            '3PM': '3pm', 'STL': 'steals', 'BLK': 'blocks', 'TO': 'turnovers',
            'P+R+A': 'pts+reb+ast', '1HPTS': '1h_points',
            'REB+AST': 'rebs+asts', 'REBS+ASTS': 'rebs+asts', 'R+A': 'rebs+asts'
        }
        stat = stat_map.get(stat_raw, stat_raw.lower())
        
        # Fix OCR decimal misreads (e.g., 555.0 -> 5.5)
        line_val = normalize_line_value(line_val, stat)
        
        # Determine hit
        hit = None
        if result_str == 'WON':
            hit = True
        elif result_str == 'LOST':
            hit = False
        elif result_str in ('PENDING', 'CANCEL'):
            continue  # Skip pending/cancelled
        
        # Infer direction from actual vs line
        direction = 'higher' if actual_val > line_val else 'lower'
        
        results.append({
            'player': player,
            'stat': stat,
            'line': line_val,
            'actual': actual_val,
            'direction': direction,
            'hit': hit,
            'raw_line': match.group(0)
        })
    
    # Fallback: Original line-by-line parsing for other formats
    if not results:
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Determine hit/miss
            hit = None
            if any(x in line for x in ['✓', '✅', '☑', 'HIT', 'WON', 'WIN', 'CORRECT']):
                hit = True
            elif any(x in line for x in ['✗', '❌', '☒', 'MISS', 'LOST', 'LOSE', 'INCORRECT', 'PUSH']):
                hit = False
            
            if hit is None:
                continue
                
            player = None
            stat = None
            line_value = None
            direction = None
            
            # Pattern: "Player Name stat direction line"
            match = re.search(
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s+(?:Jr\.|Sr\.|III|II))?)\s+'
                r'(points?|rebounds?|assists?|3pm|steals?|blocks?|turnovers?|pra|rebs?\+asts?|reb\+ast)\s+'
                r'(higher|lower|over|under)\s+'
                r'([\d.]+)',
                line, re.IGNORECASE
            )
            if match:
                player = normalize_player_name(match.group(1))
                stat = normalize_stat(match.group(2))
                direction = 'higher' if match.group(3).lower() in ['higher', 'over'] else 'lower'
                line_value = float(match.group(4))
                # Fix OCR decimal misreads
                line_value = normalize_line_value(line_value, stat)
            
            # Fallback: Just player name detection
            if not player:
                name_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|II))?)', line)
                if name_match:
                    player = normalize_player_name(name_match.group(1))
            
            if player:
                results.append({
                    'player': player,
                    'stat': stat,
                    'line': line_value,
                    'direction': direction,
                    'hit': hit,
                    'raw_line': line
                })
    
    return results


def parse_box_score(text: str) -> list[dict]:
    """
    Parse ESPN/standard box score format.
    Returns actual stat values for players.
    """
    results = []
    lines = text.split('\n')
    
    for line in lines:
        # Pattern: "Player Name    PTS  REB  AST  STL  BLK  TO"
        # Common box score format
        match = re.search(
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+'
            r'(\d+)\s+(\d+)\s+(\d+)',
            line
        )
        if match:
            results.append({
                'player': normalize_player_name(match.group(1)),
                'points': int(match.group(2)),
                'rebounds': int(match.group(3)),
                'assists': int(match.group(4)),
                'raw_line': line
            })
    
    return results


def match_results_to_picks(results: list[dict], picks_file: Optional[str] = None) -> list[dict]:
    """
    Match OCR results to our picks for calibration.
    """
    if not picks_file:
        # Try to find most recent picks file
        outputs_dir = PROJECT_ROOT / "outputs"
        pick_files = sorted(outputs_dir.glob("*_RISK_FIRST_*.json"), reverse=True)
        if pick_files:
            picks_file = pick_files[0]
    
    if not picks_file or not Path(picks_file).exists():
        return results
    
    with open(picks_file, 'r', encoding='utf-8') as f:
        picks_data = json.load(f)
    
    # Build lookup by player name
    picks_lookup = {}
    for pick in picks_data.get('results', []):
        player = pick.get('player', '').lower()
        stat = pick.get('stat', '').lower()
        key = f"{player}_{stat}"
        picks_lookup[key] = pick
    
    # Match results
    matched = []
    for result in results:
        player = (result.get('player') or '').lower()
        stat = (result.get('stat') or '').lower()
        key = f"{player}_{stat}"
        
        if key in picks_lookup:
            pick = picks_lookup[key]
            matched.append({
                **result,
                'predicted_prob': pick.get('effective_confidence', pick.get('confidence')),
                'decision': pick.get('decision'),
                'matched': True
            })
        else:
            matched.append({**result, 'matched': False})
    
    return matched


def save_to_calibration_history(results: list[dict], date: Optional[str] = None):
    """
    Save results to calibration_history.csv for backtesting.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # Best-effort: if OCR results don't already include predicted_prob/decision,
    # try matching against the correct daily analysis file for the same date.
    try:
        needs_enrich = any(
            (r.get("hit") is not None)
            and (not str(r.get("predicted_prob", "")).strip() or not str(r.get("decision", "")).strip())
            for r in results
            if isinstance(r, dict)
        )
    except Exception:
        needs_enrich = False

    if needs_enrich:
        outputs_dir = PROJECT_ROOT / "outputs"
        yyyymmdd = str(date).replace("-", "").strip()
        pick_files = []
        if outputs_dir.exists() and len(yyyymmdd) == 8:
            pick_files = sorted(outputs_dir.glob(f"*_RISK_FIRST_*{yyyymmdd}*.json"), reverse=True)
        if pick_files:
            results = match_results_to_picks(results, picks_file=str(pick_files[0]))
    
    history_path = PROJECT_ROOT / "calibration_history.csv"
    
    # Check if file exists and has headers
    file_exists = history_path.exists() and history_path.stat().st_size > 0
    
    with open(history_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow([
                "date", "player", "stat", "line", "direction",
                "predicted_prob", "decision", "actual_result",
                "role", "gate_warnings", "stat_type"
            ])
        
        for result in results:
            if result.get('hit') is not None:
                writer.writerow([
                    date,
                    result.get('player', ''),
                    result.get('stat', ''),
                    result.get('line', ''),
                    result.get('direction', ''),
                    result.get('predicted_prob', ''),
                    result.get('decision', ''),
                    'hit' if result.get('hit') else 'miss',
                    '',  # role
                    '',  # gate_warnings
                    ''   # stat_type
                ])
    
    print(f"Saved {len(results)} results to {history_path}")


def process_image(image_path: str) -> dict:
    """Process image and extract results."""
    path = Path(image_path)
    if not path.exists():
        return {'error': f'File not found: {image_path}'}
    
    # Extract text
    if HAS_EASYOCR:
        print("Using EasyOCR engine...")
        text = extract_text_easyocr(image_path)
        engine = 'easyocr'
    elif HAS_TESSERACT:
        print("Using Tesseract engine...")
        text = extract_text_tesseract(image_path)
        engine = 'tesseract'
    else:
        return {'error': 'No OCR engine available. Install: pip install easyocr'}
    
    # Parse results - try PrizePicks format first, then Underdog
    underdog_results = parse_prizepicks_results(text)
    if not underdog_results:
        underdog_results = parse_underdog_results(text)
    
    box_score = parse_box_score(text)
    
    # Match to our picks
    matched_results = match_results_to_picks(underdog_results)
    
    return {
        'engine': engine,
        'raw_text': text,
        'underdog_results': matched_results,
        'box_score': box_score
    }


def interactive_mode():
    """Interactive mode for manual verification of OCR results."""
    print("\n" + "="*60)
    print("INTERACTIVE RESULTS PARSER")
    print("="*60)
    print("\nDrag and drop image file path, or type path:")
    
    image_path = input("> ").strip().strip('"').strip("'")
    
    if not image_path:
        print("No path provided.")
        return
    
    result = process_image(image_path)
    
    if 'error' in result:
        print(f"\nError: {result['error']}")
        return
    
    print(f"\n=== OCR Engine: {result['engine']} ===")
    print(f"\n=== Raw Text ===\n{result['raw_text'][:500]}...")
    
    results = result['underdog_results']
    
    if not results:
        print("\nNo results detected. Enter manually:")
        results = manual_entry()
    else:
        print(f"\n=== Detected Results ({len(results)}) ===")
        for i, r in enumerate(results):
            status = "✓ HIT" if r['hit'] else "✗ MISS"
            matched = " [MATCHED]" if r.get('matched') else ""
            print(f"  {i+1}. {r['player']} - {r.get('stat', '?')} - {status}{matched}")
        
        print("\nVerify results? [Y/n]")
        if input("> ").strip().lower() != 'n':
            results = verify_results(results)
    
    if results:
        print("\nSave to calibration history? [Y/n]")
        if input("> ").strip().lower() != 'n':
            save_to_calibration_history(results)
            print("✓ Saved!")


def manual_entry() -> list[dict]:
    """Manually enter results."""
    results = []
    print("\nEnter results (blank player name to finish):")
    
    while True:
        player = input("Player name: ").strip()
        if not player:
            break
        
        stat = input("Stat (points/rebounds/assists/3pm): ").strip()
        hit_str = input("Hit? (y/n): ").strip().lower()
        hit = hit_str in ['y', 'yes', '1', 'true']
        
        results.append({
            'player': player,
            'stat': normalize_stat(stat),
            'hit': hit
        })
    
    return results


def verify_results(results: list[dict]) -> list[dict]:
    """Verify and correct OCR results."""
    verified = []
    
    for r in results:
        print(f"\n{r['player']} - {r.get('stat', '?')} - {'HIT' if r['hit'] else 'MISS'}")
        print("  [Enter] to accept, [s] to skip, or type correction:")
        
        correction = input("  > ").strip()
        
        if correction.lower() == 's':
            continue
        elif correction == '':
            verified.append(r)
        else:
            # Parse correction
            if correction.lower() in ['hit', 'h', 'y', '1']:
                r['hit'] = True
            elif correction.lower() in ['miss', 'm', 'n', '0']:
                r['hit'] = False
            verified.append(r)
    
    return verified


def batch_process_folder(folder_path: str, save_results: bool = True) -> dict:
    """
    Process all images in a folder and aggregate results.
    Returns summary statistics.
    """
    folder = Path(folder_path)
    if not folder.exists():
        return {'error': f'Folder not found: {folder_path}'}
    
    # Find all images
    image_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
        image_files.extend(folder.glob(ext))
    image_files = sorted(image_files, key=lambda p: p.name)
    
    if not image_files:
        return {'error': f'No images found in {folder_path}'}
    
    print(f"\n{'='*60}")
    print(f"BATCH PROCESSING: {len(image_files)} images")
    print(f"{'='*60}")
    
    all_results = []
    total_hits = 0
    total_misses = 0
    
    for img_path in image_files:
        print(f"\n>>> Processing: {img_path.name}")
        result = process_image(str(img_path))
        
        if 'error' in result:
            print(f"    Error: {result['error']}")
            continue
        
        picks = result.get('underdog_results', [])
        if picks:
            hits = sum(1 for p in picks if p.get('hit') is True)
            misses = sum(1 for p in picks if p.get('hit') is False)
            total_hits += hits
            total_misses += misses
            
            print(f"    Found {len(picks)} picks: {hits} WON, {misses} LOST")
            for p in picks:
                status = "✓" if p.get('hit') else "✗"
                actual = p.get('actual', '?')
                print(f"      {status} {p['player']} {p.get('stat', '')} {p.get('line', '')} -> {actual}")
            
            all_results.extend(picks)
        else:
            print(f"    No results detected")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"BATCH SUMMARY")
    print(f"{'='*60}")
    total = total_hits + total_misses
    if total > 0:
        rate = 100 * total_hits / total
        print(f"  Total Picks: {total}")
        print(f"  Hits: {total_hits} ({rate:.1f}%)")
        print(f"  Misses: {total_misses}")
    else:
        print(f"  No resolved picks found")
    
    # Save all results
    if save_results and all_results:
        print(f"\nSaving {len(all_results)} results to calibration_history.csv...")
        save_to_calibration_history(all_results)
    
    return {
        'total_images': len(image_files),
        'total_picks': total,
        'hits': total_hits,
        'misses': total_misses,
        'win_rate': (100 * total_hits / total) if total > 0 else 0,
        'results': all_results
    }


def main():
    if len(sys.argv) < 2:
        # Interactive mode
        interactive_mode()
        return
    
    image_path = sys.argv[1]
    
    if image_path in ['-h', '--help']:
        print("Usage: python parse_results_image.py <image_path>")
        print("       python parse_results_image.py --batch <folder_path>")
        print("       python parse_results_image.py  (interactive mode)")
        print("\nSupported formats: PNG, JPG, JPEG, BMP, GIF")
        print("\nInstall OCR engine first:")
        print("  pip install easyocr  (recommended)")
        print("  pip install pytesseract Pillow  (requires Tesseract binary)")
        return
    
    # Batch mode
    if image_path == '--batch':
        folder = sys.argv[2] if len(sys.argv) > 2 else str(PROJECT_ROOT / 'screenshots')
        batch_process_folder(folder)
        return
    
    print(f"Processing: {image_path}")
    
    result = process_image(image_path)
    
    if 'error' in result:
        print(f"Error: {result['error']}")
        return
    
    print(f"\n{'='*60}")
    print(f"OCR Engine: {result['engine']}")
    print(f"{'='*60}")
    
    print(f"\n=== Raw Text ===\n{result['raw_text']}")
    
    if result['underdog_results']:
        print(f"\n=== Underdog Results ({len(result['underdog_results'])}) ===")
        hits = sum(1 for r in result['underdog_results'] if r['hit'])
        total = len(result['underdog_results'])
        print(f"Record: {hits}/{total} ({100*hits/total:.1f}%)")
        print()
        for r in result['underdog_results']:
            status = "✓ HIT" if r['hit'] else "✗ MISS"
            matched = " [MATCHED]" if r.get('matched') else ""
            stat_info = f" | {r.get('stat', '')} {r.get('direction', '')} {r.get('line', '')}" if r.get('stat') else ""
            print(f"  {r['player']}: {status}{stat_info}{matched}")
    
    if result['box_score']:
        print(f"\n=== Box Score ({len(result['box_score'])}) ===")
        for s in result['box_score']:
            print(f"  {s['player']}: {s['points']} PTS, {s['rebounds']} REB, {s['assists']} AST")
    
    # Offer to save
    if result['underdog_results']:
        print("\n" + "="*60)
        print("Save to calibration history? [y/N]")
        try:
            if input("> ").strip().lower() == 'y':
                save_to_calibration_history(result['underdog_results'])
        except EOFError:
            pass


if __name__ == "__main__":
    main()
