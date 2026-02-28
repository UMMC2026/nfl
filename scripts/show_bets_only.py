"""
STRONG-ONLY Betting Filter — Shows ONLY what the quant system recommends betting

This is your DISCIPLINE ENFORCER. Only bet what shows up here.

Usage:
    python scripts/show_bets_only.py                    # Latest RISK_FIRST file
    python scripts/show_bets_only.py --file outputs/X.json
    python scripts/show_bets_only.py --min-prob 70     # Only 70%+ confidence
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add project root
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


def extract_tier(result: dict) -> str:
    """Extract tier from result"""
    status = result.get('status', '').upper()
    tier_label = result.get('tier_label', '').upper()
    
    for val in [status, tier_label]:
        if val in ['SLAM', 'STRONG', 'LEAN', 'NO_PLAY', 'BLOCKED', 'PASS']:
            return val
    
    confidence = result.get('status_confidence', result.get('effective_confidence', 0))
    if confidence >= 80:
        return 'SLAM'
    elif confidence >= 65:
        return 'STRONG'
    elif confidence >= 55:
        return 'LEAN'
    return 'NO_PLAY'


def extract_prob(result: dict) -> float:
    """Extract probability"""
    for field in ['status_confidence', 'effective_confidence', 'model_confidence']:
        val = result.get(field)
        if val is not None and val > 0:
            return float(val)
    return 0.0


def show_bets_only(
    mc_file: Path,
    min_prob: float = 55.0,
    include_lean: bool = False
) -> List[dict]:
    """
    Show ONLY the picks you should bet.
    
    Args:
        mc_file: Path to RISK_FIRST JSON
        min_prob: Minimum probability threshold
        include_lean: Include LEAN tier (default: STRONG/SLAM only)
    """
    with open(mc_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    
    # Filter to betting picks
    betting_tiers = {'SLAM', 'STRONG'}
    if include_lean:
        betting_tiers.add('LEAN')
    
    bets = []
    for r in results:
        tier = extract_tier(r)
        prob = extract_prob(r)
        
        if tier in betting_tiers and prob >= min_prob:
            bets.append({
                'player': r.get('player'),
                'stat': r.get('stat'),
                'line': r.get('line'),
                'direction': r.get('direction'),
                'probability': prob,
                'tier': tier,
                'edge_pct': r.get('edge_percent', 0),
                'z_score': r.get('z_score', 0),
            })
    
    # Sort by probability descending
    bets.sort(key=lambda x: x['probability'], reverse=True)
    
    return bets


def format_bet_card(bet: dict) -> str:
    """Format a single bet for display"""
    emoji = "🔥" if bet['tier'] == 'SLAM' else "💪" if bet['tier'] == 'STRONG' else "📊"
    direction = bet['direction'].upper()
    
    return (
        f"{emoji} {bet['player']}\n"
        f"   {direction} {bet['line']} {bet['stat'].upper()}\n"
        f"   Confidence: {bet['probability']:.1f}% | Tier: {bet['tier']}\n"
        f"   Edge: {bet['edge_pct']:.1f}% | Z-score: {bet['z_score']:.2f}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Show ONLY the picks you should bet"
    )
    parser.add_argument(
        '--file',
        type=Path,
        help="Path to RISK_FIRST JSON file"
    )
    parser.add_argument(
        '--min-prob',
        type=float,
        default=55.0,
        help="Minimum probability (default: 55)"
    )
    parser.add_argument(
        '--include-lean',
        action='store_true',
        help="Include LEAN tier picks"
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    # Find file
    mc_file = args.file or find_latest_risk_first()
    if not mc_file or not mc_file.exists():
        print("❌ No RISK_FIRST file found")
        sys.exit(1)
    
    # Get bets
    bets = show_bets_only(mc_file, args.min_prob, args.include_lean)
    
    if args.json:
        print(json.dumps(bets, indent=2))
        return
    
    # Display
    print("=" * 60)
    print("🎯 YOUR BETS — STRONG/SLAM ONLY")
    print("=" * 60)
    print(f"Source: {mc_file.name}")
    print(f"Filter: {args.min_prob}%+ confidence")
    print(f"Tiers: SLAM, STRONG" + (", LEAN" if args.include_lean else ""))
    print("=" * 60)
    
    if not bets:
        print("\n⚠️  NO QUALIFYING BETS")
        print("   The quant system has no high-confidence plays.")
        print("   This means: DON'T BET TODAY.")
        print("\n   Your friends might bet anyway.")
        print("   The quant system says PASS.")
        return
    
    print(f"\n✅ {len(bets)} QUALIFYING BETS:\n")
    
    for i, bet in enumerate(bets, 1):
        print(f"[{i}] {format_bet_card(bet)}")
        print()
    
    # Summary
    print("=" * 60)
    print("📋 QUICK COPY:")
    print("=" * 60)
    for bet in bets:
        d = bet['direction'].upper()[:1]  # H or L
        print(f"• {bet['player']} {d} {bet['line']} {bet['stat'].upper()} ({bet['probability']:.0f}%)")
    
    print("\n⚠️  ONLY BET THESE. NOTHING ELSE.")
    print("    If it's not on this list, the system says NO.")


if __name__ == "__main__":
    main()
