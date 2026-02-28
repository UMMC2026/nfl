"""
Commit MC-Backed Picks to Calibration — ONLY tracks what the quant system recommends

PURPOSE: This is the ONLY proper way to add picks to calibration tracking.
         It ensures every tracked pick has:
         - Monte Carlo probability attached
         - Proper tier (STRONG/SLAM/LEAN)
         - Full audit trail

GOVERNANCE: 
- ONLY STRONG/SLAM picks are tracked for betting
- LEAN picks tracked separately as "watch only"
- NO_PLAY/BLOCKED picks are NOT tracked

Usage:
    python calibration/commit_mc_picks.py outputs/SLATE_RISK_FIRST_20260129_FROM_UD.json
    python calibration/commit_mc_picks.py --latest  # Uses most recent RISK_FIRST file
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import hashlib

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.thresholds import TIERS

# Calibration file paths
CALIBRATION_DIR = Path(__file__).parent
PICKS_CSV = CALIBRATION_DIR / "picks.csv"
HISTORY_CSV = Path(__file__).parent.parent / "calibration_history.csv"

# Tier acceptance for betting vs watching
BETTING_TIERS = {"SLAM", "STRONG"}
WATCHING_TIERS = {"LEAN"}
EXCLUDED_STATUSES = {"NO_PLAY", "BLOCKED", "SKIP"}


def generate_pick_id(result: dict, date_str: str) -> str:
    """Generate unique pick ID from MC result"""
    player = result.get('player', 'unknown')
    stat = result.get('stat', 'unk')
    line = result.get('line', 0)
    direction = result.get('direction', 'unk')
    
    key = f"{date_str}_{player}_{stat}_{line}_{direction}"
    short_hash = hashlib.md5(key.encode()).hexdigest()[:8]
    return f"mc_{short_hash}"


def extract_tier_from_result(result: dict) -> str:
    """Extract the proper tier from MC result structure"""
    # Check multiple fields where tier might be stored
    status = result.get('status', '').upper()
    tier_label = result.get('tier_label', '').upper()
    decision = result.get('decision', '').upper()
    
    # Priority: explicit status > tier_label > decision
    for val in [status, tier_label, decision]:
        if val in ['SLAM', 'STRONG', 'LEAN', 'NO_PLAY', 'BLOCKED', 'SKIP', 'PASS']:
            return val
    
    # Infer from confidence if no explicit tier
    confidence = result.get('status_confidence', result.get('effective_confidence', 0))
    if confidence >= 80:
        return 'SLAM'
    elif confidence >= 65:
        return 'STRONG'
    elif confidence >= 55:
        return 'LEAN'
    else:
        return 'NO_PLAY'


def extract_probability(result: dict) -> float:
    """Extract the final probability from MC result"""
    # Try various fields where probability is stored
    for field in ['status_confidence', 'effective_confidence', 'model_confidence', 'final_probability']:
        val = result.get(field)
        if val is not None and val > 0:
            return float(val)
    return 0.0


def find_latest_risk_first() -> Optional[Path]:
    """Find the most recent RISK_FIRST output file"""
    outputs_dir = Path("outputs")
    risk_files = sorted(
        outputs_dir.glob("*RISK_FIRST*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return risk_files[0] if risk_files else None


def load_existing_pick_ids() -> set:
    """Load existing pick IDs to avoid duplicates"""
    existing = set()
    
    for csv_path in [PICKS_CSV, HISTORY_CSV]:
        if csv_path.exists():
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('pick_id'):
                        existing.add(row['pick_id'])
    
    return existing


def commit_picks(
    mc_file: Path,
    bet_only: bool = False,
    dry_run: bool = False
) -> Dict:
    """
    Commit MC-backed picks to calibration tracking.
    
    Args:
        mc_file: Path to RISK_FIRST JSON output
        bet_only: If True, only commit STRONG/SLAM (betting picks)
        dry_run: If True, don't write, just show what would be committed
    
    Returns:
        Summary dict with counts
    """
    # Load MC output
    with open(mc_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    if not results:
        print(f"⚠️  No results in {mc_file}")
        return {"committed": 0, "skipped": 0}
    
    # Extract date from filename or use today
    date_match = mc_file.stem.split('_')
    date_str = datetime.now().strftime('%Y-%m-%d')
    for part in date_match:
        if part.isdigit() and len(part) == 8:
            date_str = f"{part[:4]}-{part[4:6]}-{part[6:8]}"
            break
    
    # Load existing to avoid duplicates
    existing_ids = load_existing_pick_ids()
    
    # Process results
    committed = []
    skipped = []
    
    for result in results:
        tier = extract_tier_from_result(result)
        probability = extract_probability(result)
        
        # Skip excluded statuses
        if tier in EXCLUDED_STATUSES:
            skipped.append((result.get('player'), tier, "excluded status"))
            continue
        
        # If bet_only, skip non-betting tiers
        if bet_only and tier not in BETTING_TIERS:
            skipped.append((result.get('player'), tier, "not betting tier"))
            continue
        
        # Generate pick ID
        pick_id = generate_pick_id(result, date_str)
        
        # Skip duplicates
        if pick_id in existing_ids:
            skipped.append((result.get('player'), tier, "duplicate"))
            continue
        
        # Build calibration row
        row = {
            'pick_id': pick_id,
            'date': date_str,
            'sport': 'nba',  # TODO: detect from file
            'player': result.get('player', ''),
            'stat': result.get('stat', ''),
            'line': result.get('line', 0),
            'direction': result.get('direction', '').capitalize(),
            'probability': probability,
            'tier': tier,
            'actual': '',
            'hit': '',
            'brier': '',
            # Extended metadata
            'mc_source': str(mc_file.name),
            'edge_percent': result.get('edge_percent', ''),
            'z_score': result.get('z_score', ''),
        }
        
        committed.append(row)
        existing_ids.add(pick_id)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"MC PICK COMMIT — {mc_file.name}")
    print(f"{'='*60}")
    print(f"Total results in file: {len(results)}")
    print(f"Commits: {len(committed)}")
    print(f"Skipped: {len(skipped)}")
    
    if committed:
        print(f"\n✅ COMMITTED PICKS ({len(committed)}):")
        for row in committed:
            print(f"   {row['player']} | {row['stat']} {row['direction']} {row['line']} | {row['probability']:.1f}% | {row['tier']}")
    
    if skipped and len(skipped) <= 20:
        print(f"\n⏭️  SKIPPED ({len(skipped)}):")
        for player, tier, reason in skipped[:20]:
            print(f"   {player} | {tier} | {reason}")
    elif skipped:
        print(f"\n⏭️  Skipped {len(skipped)} picks (NO_PLAY/BLOCKED/duplicates)")
    
    # Write if not dry run
    if not dry_run and committed:
        _write_to_picks_csv(committed)
        _write_to_history_csv(committed)
        print(f"\n✅ Written to calibration/picks.csv and calibration_history.csv")
    elif dry_run:
        print(f"\n🔍 DRY RUN - no files written")
    
    return {
        "committed": len(committed),
        "skipped": len(skipped),
        "picks": committed
    }


def _write_to_picks_csv(rows: List[dict]):
    """Append to calibration/picks.csv"""
    fieldnames = ['pick_id', 'date', 'sport', 'player', 'stat', 'line', 
                  'direction', 'probability', 'tier', 'actual', 'hit', 'brier']
    
    existing_rows = []
    if PICKS_CSV.exists():
        with open(PICKS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)
    
    # Add new rows
    for row in rows:
        filtered = {k: row.get(k, '') for k in fieldnames}
        existing_rows.append(filtered)
    
    # Write back
    with open(PICKS_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)


def _write_to_history_csv(rows: List[dict]):
    """Append to calibration_history.csv (legacy format)"""
    fieldnames = ['pick_id', 'game_date', 'player', 'team', 'opponent', 'stat', 'line', 
                  'direction', 'probability', 'tier', 'actual_value', 'outcome', 
                  'added_utc', 'league', 'source']
    
    existing_rows = []
    if HISTORY_CSV.exists():
        with open(HISTORY_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filtered = {k: row.get(k, '') for k in fieldnames}
                existing_rows.append(filtered)
    
    # Add new rows in history format
    for row in rows:
        history_row = {
            'pick_id': row['pick_id'],
            'game_date': row['date'],
            'player': row['player'],
            'team': '',  # Not in MC output
            'opponent': '',  # Not in MC output
            'stat': row['stat'],
            'line': row['line'],
            'direction': row['direction'].lower(),
            'probability': row['probability'],
            'tier': row['tier'],
            'actual_value': '',
            'outcome': '',
            'added_utc': datetime.utcnow().isoformat(),
            'league': row.get('sport', 'nba').upper(),
            'source': row.get('mc_source', 'MC_COMMIT')
        }
        existing_rows.append(history_row)
    
    # Write back
    with open(HISTORY_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)


def main():
    parser = argparse.ArgumentParser(
        description="Commit MC-backed picks to calibration tracking"
    )
    parser.add_argument(
        'mc_file', 
        nargs='?',
        help="Path to RISK_FIRST JSON file"
    )
    parser.add_argument(
        '--latest', 
        action='store_true',
        help="Use the most recent RISK_FIRST file"
    )
    parser.add_argument(
        '--bet-only', 
        action='store_true',
        help="Only commit STRONG/SLAM betting picks"
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help="Show what would be committed without writing"
    )
    
    args = parser.parse_args()
    
    # Determine input file
    if args.latest:
        mc_file = find_latest_risk_first()
        if not mc_file:
            print("❌ No RISK_FIRST files found in outputs/")
            sys.exit(1)
        print(f"Using latest: {mc_file}")
    elif args.mc_file:
        mc_file = Path(args.mc_file)
        if not mc_file.exists():
            print(f"❌ File not found: {mc_file}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    # Commit
    result = commit_picks(mc_file, bet_only=args.bet_only, dry_run=args.dry_run)
    
    if result['committed'] > 0:
        print(f"\n🎯 {result['committed']} picks ready for tracking")
        print("   Run auto_verify_results.py after games to record outcomes")


if __name__ == "__main__":
    main()
