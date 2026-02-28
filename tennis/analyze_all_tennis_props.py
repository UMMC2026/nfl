"""
Unified Tennis Props Analyzer - Handles ALL Underdog tennis prop types
Supports: Fantasy Score, Break Points Won, Total Games, Aces, Games Won, etc.
"""
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add parent to path
TENNIS_DIR = Path(__file__).parent
sys.path.insert(0, str(TENNIS_DIR.parent))

from tennis.tennis_props_parser import parse_tennis_props, TennisProp


def analyze_all_props(props: list[TennisProp]) -> dict:
    """
    Analyze ALL tennis prop types with simple heuristics
    Returns structured analysis by stat type
    """
    results = {
        'total_props': len(props),
        'by_stat': defaultdict(list),
        'by_player': defaultdict(list),
        'value_plays': [],
        'timestamp': datetime.now().isoformat()
    }
    
    for prop in props:
        # Group by stat type
        results['by_stat'][prop.stat].append(prop)
        results['by_player'][prop.player].append(prop)
        
        # Identify value plays based on multiplier asymmetry
        direction, edge = prop.value_side
        if edge >= 0.05:  # 5% edge threshold
            results['value_plays'].append({
                'player': prop.player,
                'opponent': prop.opponent,
                'stat': prop.stat,
                'line': prop.line,
                'direction': direction,
                'edge': round(edge, 3),
                'match': prop.match_info
            })
    
    return results


def generate_report(props: list[TennisProp]) -> str:
    """Generate human-readable analysis report for all prop types"""
    
    if not props:
        return "\n[!] No props found in input\n"
    
    analysis = analyze_all_props(props)
    
    lines = []
    lines.append("\n" + "=" * 70)
    lines.append("  🎾 TENNIS PROPS ANALYSIS - ALL STAT TYPES")
    lines.append(f"     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append(f"\n📊 TOTAL PROPS ANALYZED: {analysis['total_props']}")
    lines.append(f"🎯 VALUE PLAYS IDENTIFIED: {len(analysis['value_plays'])}")
    
    # Breakdown by stat type
    lines.append("\n" + "-" * 70)
    lines.append("PROPS BY STAT TYPE:")
    lines.append("-" * 70)
    for stat, stat_props in sorted(analysis['by_stat'].items()):
        lines.append(f"  • {stat:20s} : {len(stat_props)} props")
    
    # Value plays
    if analysis['value_plays']:
        lines.append("\n" + "=" * 70)
        lines.append("💎 VALUE PLAYS (Multiplier Edge ≥ 0.05)")
        lines.append("=" * 70)
        
        for i, play in enumerate(sorted(analysis['value_plays'], 
                                       key=lambda x: x['edge'], 
                                       reverse=True), 1):
            lines.append(f"\n[{i}] {play['player']} vs {play['opponent']}")
            lines.append(f"    {play['stat']}: {play['direction']} {play['line']}")
            lines.append(f"    Multiplier Edge: {play['edge']:.3f}")
            lines.append(f"    Match: {play['match']}")
    
    # Player breakdown
    lines.append("\n" + "=" * 70)
    lines.append("PROPS BY PLAYER:")
    lines.append("=" * 70)
    
    for player, player_props in sorted(analysis['by_player'].items()):
        lines.append(f"\n{player} ({len(player_props)} props)")
        if player_props:
            lines.append(f"  vs {player_props[0].opponent}")
            lines.append(f"  {player_props[0].match_info}")
        
        # Group player's props by stat
        player_stats = defaultdict(list)
        for p in player_props:
            player_stats[p.stat].append(p)
        
        for stat, stat_props in sorted(player_stats.items()):
            for prop in stat_props:
                direction, edge = prop.value_side
                edge_str = f" [EDGE: {edge:.3f}]" if edge >= 0.05 else ""
                
                higher_str = f"Higher: {prop.higher_mult}x" if prop.higher_mult else "Higher: --"
                lower_str = f"Lower: {prop.lower_mult}x" if prop.lower_mult else "Lower: --"
                
                lines.append(f"  • {stat:20s} {prop.line:>6.1f}  |  {higher_str:15s} {lower_str:15s}{edge_str}")
    
    lines.append("\n" + "=" * 70)
    lines.append("")
    
    return '\n'.join(lines)


def save_analysis(props: list[TennisProp], filename: str = None):
    """Save analysis to tennis outputs folder"""
    from tennis.tennis_props_parser import OUTPUTS_DIR
    import json
    
    OUTPUTS_DIR.mkdir(exist_ok=True)
    
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"tennis_props_analysis_{timestamp}.txt"
    
    filepath = OUTPUTS_DIR / filename
    
    report = generate_report(props)
    filepath.write_text(report, encoding='utf-8')
    
    # Also save JSON for programmatic access
    json_file = filepath.with_suffix('.json')
    analysis = analyze_all_props(props)
    
    # Convert defaultdicts to regular dicts for JSON
    json_data = {
        'total_props': analysis['total_props'],
        'by_stat': {k: [p.to_dict() for p in v] for k, v in analysis['by_stat'].items()},
        'by_player': {k: [p.to_dict() for p in v] for k, v in analysis['by_player'].items()},
        'value_plays': analysis['value_plays'],
        'timestamp': analysis['timestamp']
    }
    
    json_file.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
    
    print(f"\n✓ Report saved: {filepath}")
    print(f"✓ Data saved: {json_file}")
    
    return filepath, json_file


def main():
    """Interactive tennis props analysis"""
    print("\n" + "=" * 70)
    print("  🎾 TENNIS PROPS ANALYZER (ALL STAT TYPES)")
    print("=" * 70)
    print("\nSupported stats:")
    print("  • Fantasy Score / Fantasy Points")
    print("  • Break Points Won / Breakpoints Won")
    print("  • Total Games / Total Games Won / Games Won")
    print("  • Aces / Double Faults")
    print("  • Sets Won / Sets Played")
    print("  • Tiebreakers Played")
    print("\nPaste Underdog tennis props below (Press Enter twice when done):\n")
    
    lines = []
    empty_count = 0
    
    while empty_count < 2:
        try:
            line = input()
            if not line.strip():
                empty_count += 1
            else:
                empty_count = 0
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break
    
    if not lines:
        print("\n[!] No input received")
        return
    
    paste = '\n'.join(lines)
    props = parse_tennis_props(paste)
    
    print(f"\n✓ Parsed {len(props)} props from paste")
    
    if not props:
        print("\n[X] No valid props found. Check format.")
        print("\nExpected format example:")
        print("  Jannik Sinner")
        print("  vs Luciano Darderi Mon 1:00am")
        print("  34")
        print("  Fantasy Score")
        print("  Less")
        print("  More")
        return
    
    # Generate and display report
    report = generate_report(props)
    print(report)
    
    # Save to file
    save_analysis(props)


if __name__ == "__main__":
    main()
