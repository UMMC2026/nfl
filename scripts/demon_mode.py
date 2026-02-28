"""
DEMON MODE — Star Scorer Overs (What Your Friends Do)

This bypasses the over-engineered penalty system and finds:
- Star scorers with predicted avg ABOVE the line
- Simple math: if mu > line by 10%+, that's a play

Your friends aren't using Monte Carlo with 15 penalty layers.
They're doing: "Embiid averages 30, line is 27.5, OVER."

Usage:
    python scripts/demon_mode.py                    # Latest analysis
    python scripts/demon_mode.py --min-edge 15     # Only 15%+ edge
    python scripts/demon_mode.py --top 10          # Top 10 plays
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))


def find_latest_risk_first() -> Optional[Path]:
    outputs_dir = Path("outputs")
    risk_files = sorted(
        outputs_dir.glob("*RISK_FIRST*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return risk_files[0] if risk_files else None


def demon_mode(
    mc_file: Path,
    min_edge_pct: float = 10.0,
    top_n: int = 15,
    stat_filter: str = None
) -> List[dict]:
    """
    Find star scorer OVERS using simple logic.
    
    Edge = (predicted_avg - line) / line * 100
    If edge > min_edge_pct, it's a play.
    """
    with open(mc_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    plays = []
    
    for r in data.get('results', []):
        stat = r.get('stat', '')
        direction = r.get('direction', '')
        mu = r.get('mu', 0)
        line = r.get('line', 0)
        player = r.get('player', '')
        
        if not mu or not line:
            continue
        
        # Filter by stat if specified
        if stat_filter and stat != stat_filter:
            continue
        
        # Calculate simple edge
        if direction == 'higher':
            edge_pct = ((mu - line) / line) * 100
        else:  # lower
            edge_pct = ((line - mu) / line) * 100
        
        # Only positive edges above threshold
        if edge_pct < min_edge_pct:
            continue
        
        # Get raw probability (before penalties destroyed it)
        raw_prob = r.get('edge_diagnostics', {}).get('penalties', {}).get('raw_probability', 0)
        final_prob = r.get('status_confidence', 0)
        penalty = raw_prob - final_prob if raw_prob else 0
        
        plays.append({
            'player': player,
            'stat': stat,
            'line': line,
            'direction': direction,
            'predicted': mu,
            'edge_pct': edge_pct,
            'raw_prob': raw_prob,
            'final_prob': final_prob,
            'penalty_pct': penalty,
            'system_status': r.get('status', 'UNK'),
            'sigma': r.get('sigma', 0),
            'z_score': r.get('z_score', 0),
        })
    
    # Sort by edge
    plays.sort(key=lambda x: x['edge_pct'], reverse=True)
    
    return plays[:top_n]


def format_demon_play(p: dict, rank: int) -> str:
    """Format a play for display"""
    direction = "OVER" if p['direction'] == 'higher' else "UNDER"
    emoji = "🔥" if p['edge_pct'] >= 20 else "💪" if p['edge_pct'] >= 15 else "📈"
    
    lines = [
        f"[{rank}] {emoji} {p['player']}",
        f"    {direction} {p['line']} {p['stat'].upper()}",
        f"    Predicted: {p['predicted']:.1f} | Edge: +{p['edge_pct']:.1f}%",
    ]
    
    # Show what the system did (if it killed it)
    if p['system_status'] == 'NO_PLAY' and p['penalty_pct'] > 5:
        lines.append(f"    ⚠️  System killed this: {p['raw_prob']:.0f}% → {p['final_prob']:.0f}% (-{p['penalty_pct']:.0f}%)")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="DEMON MODE - Star Scorer Overs"
    )
    parser.add_argument('--file', type=Path, help="RISK_FIRST JSON file")
    parser.add_argument('--min-edge', type=float, default=10.0, help="Minimum edge %% (default: 10)")
    parser.add_argument('--top', type=int, default=15, help="Top N plays (default: 15)")
    parser.add_argument('--stat', type=str, help="Filter by stat (points, rebounds, etc)")
    parser.add_argument('--json', action='store_true', help="Output as JSON")
    
    args = parser.parse_args()
    
    mc_file = args.file or find_latest_risk_first()
    if not mc_file or not mc_file.exists():
        print("❌ No RISK_FIRST file found")
        sys.exit(1)
    
    plays = demon_mode(mc_file, args.min_edge, args.top, args.stat)
    
    if args.json:
        print(json.dumps(plays, indent=2))
        return
    
    print("=" * 60)
    print("😈 DEMON MODE — STAR SCORER OVERS")
    print("=" * 60)
    print(f"Source: {mc_file.name}")
    print(f"Filter: {args.min_edge}%+ edge | Top {args.top}")
    print()
    print("Logic: If predicted avg > line by X%, it's a play.")
    print("       No penalty layers. No over-engineering.")
    print("       Just: 'He scores 30, line is 27.5, OVER.'")
    print("=" * 60)
    
    if not plays:
        print("\n⚠️  No plays found with that edge threshold")
        print("    Try: --min-edge 5")
        return
    
    # Separate by stat type
    points_plays = [p for p in plays if p['stat'] == 'points']
    other_plays = [p for p in plays if p['stat'] != 'points']
    
    if points_plays:
        print(f"\n🏀 POINTS OVERS ({len(points_plays)}):")
        print("-" * 50)
        for i, p in enumerate(points_plays, 1):
            print(format_demon_play(p, i))
            print()
    
    if other_plays:
        print(f"\n📊 OTHER STATS ({len(other_plays)}):")
        print("-" * 50)
        for i, p in enumerate(other_plays, 1):
            print(format_demon_play(p, i))
            print()
    
    # Quick copy section
    print("=" * 60)
    print("📋 QUICK COPY (Top 5):")
    print("=" * 60)
    for p in plays[:5]:
        d = "O" if p['direction'] == 'higher' else "U"
        print(f"• {p['player']} {d} {p['line']} {p['stat'].upper()} (+{p['edge_pct']:.0f}%)")
    
    print()
    print("⚠️  DEMON MODE = Simple logic, no overthinking")
    print("    This is what your friends do. And they're winning.")


if __name__ == "__main__":
    main()
