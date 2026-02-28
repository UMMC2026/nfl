"""
Validate User Picks Against MC Recommendations

PURPOSE: Check if the picks you're about to bet were actually recommended by the quant system.
         This catches "gut feel" overrides that bypass the Monte Carlo.

Usage:
    python calibration/validate_user_picks.py "Joel Embiid PTS 27.5 higher"
    python calibration/validate_user_picks.py --file my_picks.txt
    python calibration/validate_user_picks.py --interactive
"""
import argparse
import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent.parent))


def find_latest_risk_first() -> Optional[Path]:
    """Find the most recent RISK_FIRST output file"""
    outputs_dir = Path("outputs")
    risk_files = sorted(
        outputs_dir.glob("*RISK_FIRST*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return risk_files[0] if risk_files else None


def load_mc_recommendations(mc_file: Path) -> Dict[str, dict]:
    """Load MC results indexed by player+stat+direction"""
    with open(mc_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    index = {}
    for r in data.get('results', []):
        player = r.get('player', '').lower().strip()
        stat = r.get('stat', '').lower().strip()
        direction = r.get('direction', '').lower().strip()
        line = r.get('line', 0)
        
        # Create normalized key
        key = f"{player}|{stat}|{direction}"
        
        # Extract confidence
        confidence = 0
        for field in ['status_confidence', 'effective_confidence', 'model_confidence']:
            if r.get(field):
                confidence = r[field]
                break
        
        # Extract tier/status
        status = r.get('status', r.get('tier_label', 'NO_PLAY')).upper()
        
        index[key] = {
            'player': r.get('player'),
            'stat': stat,
            'line': line,
            'direction': direction,
            'confidence': confidence,
            'status': status,
            'edge_pct': r.get('edge_percent', 0),
            'approved': status in ['SLAM', 'STRONG'],
            'lean': status == 'LEAN',
        }
    
    return index


def parse_pick_string(pick_str: str) -> Optional[dict]:
    """Parse a pick string like 'Joel Embiid PTS 27.5 higher'"""
    pick_str = pick_str.strip().lower()
    
    # Common patterns
    patterns = [
        # "Player Name STAT LINE DIRECTION"
        r'^(.+?)\s+(pts|points|reb|rebounds|ast|assists|3pm|threes|blk|stl|pra|pts\+reb\+ast)\s+(\d+\.?\d*)\s+(higher|lower|over|under)$',
        # "Player Name DIRECTION LINE STAT"
        r'^(.+?)\s+(higher|lower|over|under)\s+(\d+\.?\d*)\s+(pts|points|reb|rebounds|ast|assists|3pm|threes)$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, pick_str, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 4:
                if groups[1].lower() in ['higher', 'lower', 'over', 'under']:
                    # Pattern 2
                    player, direction, line, stat = groups
                else:
                    # Pattern 1
                    player, stat, line, direction = groups
                
                # Normalize direction
                direction = 'higher' if direction in ['higher', 'over'] else 'lower'
                
                # Normalize stat
                stat_map = {
                    'pts': 'points', 'points': 'points',
                    'reb': 'rebounds', 'rebounds': 'rebounds',
                    'ast': 'assists', 'assists': 'assists',
                    '3pm': '3pm', 'threes': '3pm',
                    'pra': 'pts+reb+ast',
                }
                stat = stat_map.get(stat.lower(), stat.lower())
                
                return {
                    'player': player.strip(),
                    'stat': stat,
                    'line': float(line),
                    'direction': direction
                }
    
    return None


def fuzzy_match_player(input_name: str, mc_players: List[str]) -> Optional[str]:
    """Find best matching player name"""
    input_name = input_name.lower()
    best_match = None
    best_ratio = 0.6  # Minimum threshold
    
    for player in mc_players:
        ratio = SequenceMatcher(None, input_name, player.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = player
    
    return best_match


def validate_pick(pick: dict, mc_index: Dict[str, dict]) -> Tuple[str, Optional[dict]]:
    """
    Validate a single pick against MC recommendations.
    
    Returns: (status, mc_match)
        status: 'APPROVED', 'LEAN', 'NO_PLAY', 'NOT_FOUND'
        mc_match: The MC result if found
    """
    player = pick['player'].lower()
    stat = pick['stat'].lower()
    direction = pick['direction'].lower()
    
    # Direct lookup
    key = f"{player}|{stat}|{direction}"
    if key in mc_index:
        mc = mc_index[key]
        if mc['approved']:
            return 'APPROVED', mc
        elif mc['lean']:
            return 'LEAN', mc
        else:
            return 'NO_PLAY', mc
    
    # Try fuzzy player match
    all_players = list(set(k.split('|')[0] for k in mc_index.keys()))
    matched_player = fuzzy_match_player(player, all_players)
    
    if matched_player:
        key = f"{matched_player}|{stat}|{direction}"
        if key in mc_index:
            mc = mc_index[key]
            if mc['approved']:
                return 'APPROVED', mc
            elif mc['lean']:
                return 'LEAN', mc
            else:
                return 'NO_PLAY', mc
    
    return 'NOT_FOUND', None


def validate_picks(picks: List[dict], mc_file: Path) -> Dict:
    """Validate multiple picks"""
    mc_index = load_mc_recommendations(mc_file)
    
    results = {
        'approved': [],
        'lean': [],
        'rejected': [],
        'not_found': [],
    }
    
    for pick in picks:
        status, mc_match = validate_pick(pick, mc_index)
        
        entry = {
            'input': pick,
            'mc_match': mc_match,
            'status': status
        }
        
        if status == 'APPROVED':
            results['approved'].append(entry)
        elif status == 'LEAN':
            results['lean'].append(entry)
        elif status == 'NO_PLAY':
            results['rejected'].append(entry)
        else:
            results['not_found'].append(entry)
    
    return results


def print_validation_report(results: Dict):
    """Print validation report"""
    print("\n" + "=" * 60)
    print("🔍 PICK VALIDATION REPORT")
    print("=" * 60)
    
    # Approved
    if results['approved']:
        print(f"\n✅ APPROVED ({len(results['approved'])})")
        for r in results['approved']:
            mc = r['mc_match']
            print(f"   {mc['player']} | {mc['stat']} {mc['direction']} {mc['line']}")
            print(f"   → {mc['confidence']:.1f}% confidence | {mc['status']}")
    
    # Lean (warning)
    if results['lean']:
        print(f"\n⚠️  LEAN - Lower confidence ({len(results['lean'])})")
        for r in results['lean']:
            mc = r['mc_match']
            print(f"   {mc['player']} | {mc['stat']} {mc['direction']} {mc['line']}")
            print(f"   → {mc['confidence']:.1f}% confidence | LEAN tier")
        print("   ⚠️  LEAN picks are riskier - consider smaller units")
    
    # Rejected
    if results['rejected']:
        print(f"\n🚫 REJECTED BY SYSTEM ({len(results['rejected'])})")
        for r in results['rejected']:
            mc = r['mc_match']
            inp = r['input']
            print(f"   {inp['player']} | {inp['stat']} {inp['direction']} {inp['line']}")
            print(f"   → System says: {mc['status']} ({mc['confidence']:.1f}%)")
            print(f"   ❌ DO NOT BET - System explicitly rejected this")
    
    # Not found
    if results['not_found']:
        print(f"\n❓ NOT IN SYSTEM ({len(results['not_found'])})")
        for r in results['not_found']:
            inp = r['input']
            print(f"   {inp['player']} | {inp['stat']} {inp['direction']} {inp['line']}")
            print(f"   ⚠️  Not analyzed - cannot validate")
    
    # Summary
    print("\n" + "=" * 60)
    total = len(results['approved']) + len(results['lean']) + len(results['rejected']) + len(results['not_found'])
    approved = len(results['approved'])
    
    if approved == total and total > 0:
        print("✅ ALL PICKS APPROVED - Good to bet!")
    elif results['rejected']:
        print(f"🚫 {len(results['rejected'])} REJECTED - Remove these picks!")
    elif results['not_found']:
        print(f"⚠️  {len(results['not_found'])} NOT VALIDATED - Proceed with caution")
    else:
        print("⚠️  Some picks are LEAN tier - Consider smaller units")


def interactive_mode(mc_file: Path):
    """Interactive pick validation"""
    print("\n" + "=" * 60)
    print("🎯 INTERACTIVE PICK VALIDATOR")
    print("=" * 60)
    print(f"Checking against: {mc_file.name}")
    print("Enter picks like: 'Joel Embiid PTS 27.5 higher'")
    print("Type 'quit' to exit\n")
    
    mc_index = load_mc_recommendations(mc_file)
    
    while True:
        try:
            pick_str = input("Pick: ").strip()
            if pick_str.lower() in ['quit', 'exit', 'q']:
                break
            
            pick = parse_pick_string(pick_str)
            if not pick:
                print("❌ Could not parse. Format: 'Player STAT LINE DIRECTION'")
                continue
            
            status, mc_match = validate_pick(pick, mc_index)
            
            if status == 'APPROVED':
                print(f"✅ APPROVED | {mc_match['confidence']:.1f}% | {mc_match['status']}")
            elif status == 'LEAN':
                print(f"⚠️  LEAN | {mc_match['confidence']:.1f}% | Riskier play")
            elif status == 'NO_PLAY':
                print(f"🚫 REJECTED | {mc_match['confidence']:.1f}% | System says NO")
            else:
                print(f"❓ NOT FOUND | Not in today's analysis")
            
            print()
            
        except KeyboardInterrupt:
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description="Validate picks against MC recommendations"
    )
    parser.add_argument(
        'picks',
        nargs='*',
        help="Pick strings to validate"
    )
    parser.add_argument(
        '--file',
        type=Path,
        help="File with picks (one per line)"
    )
    parser.add_argument(
        '--mc-file',
        type=Path,
        help="RISK_FIRST JSON file to check against"
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help="Interactive mode"
    )
    
    args = parser.parse_args()
    
    # Find MC file
    mc_file = args.mc_file or find_latest_risk_first()
    if not mc_file or not mc_file.exists():
        print("❌ No RISK_FIRST file found")
        sys.exit(1)
    
    if args.interactive:
        interactive_mode(mc_file)
        return
    
    # Collect picks
    picks = []
    
    # From command line
    if args.picks:
        for pick_str in args.picks:
            pick = parse_pick_string(pick_str)
            if pick:
                picks.append(pick)
            else:
                print(f"⚠️  Could not parse: {pick_str}")
    
    # From file
    if args.file and args.file.exists():
        with open(args.file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    pick = parse_pick_string(line)
                    if pick:
                        picks.append(pick)
    
    if not picks:
        parser.print_help()
        sys.exit(1)
    
    # Validate
    results = validate_picks(picks, mc_file)
    print_validation_report(results)
    
    # Exit code based on results
    if results['rejected']:
        sys.exit(1)  # Has rejected picks


if __name__ == "__main__":
    main()
