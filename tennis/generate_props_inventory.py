"""
Tennis Props Inventory Generator
Creates clean, actionable props list from Underdog paste
"""
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from tennis_props_parser import parse_tennis_props, TennisProp


def generate_inventory(props: list[TennisProp]) -> str:
    """Generate clean inventory of available props"""
    
    lines = []
    lines.append("=" * 80)
    lines.append("🎾 TENNIS PROPS INVENTORY")
    lines.append("=" * 80)
    
    # Deduplicate props
    unique_props = {}
    for prop in props:
        key = (prop.player, prop.stat, prop.line)
        if key not in unique_props:
            unique_props[key] = prop
    
    props = list(unique_props.values())
    
    lines.append(f"\n📊 TOTAL UNIQUE PROPS: {len(props)}")
    
    # Group by stat type
    by_stat = defaultdict(list)
    for prop in props:
        by_stat[prop.stat].append(prop)
    
    lines.append(f"📋 STAT TYPES: {len(by_stat)}")
    lines.append("")
    
    # Summary by stat
    lines.append("-" * 80)
    lines.append("BREAKDOWN BY STAT TYPE:")
    lines.append("-" * 80)
    for stat, stat_props in sorted(by_stat.items(), key=lambda x: -len(x[1])):
        lines.append(f"  • {stat:25s} {len(stat_props):>3} props")
    
    # Group by matchup
    lines.append("\n" + "=" * 80)
    lines.append("PROPS BY MATCHUP:")
    lines.append("=" * 80)
    
    by_matchup = defaultdict(list)
    for prop in props:
        if prop.opponent:
            matchup = f"{prop.player} vs {prop.opponent}"
        else:
            matchup = f"{prop.player} (opponent TBD)"
        by_matchup[matchup].append(prop)
    
    for matchup in sorted(by_matchup.keys()):
        matchup_props = by_matchup[matchup]
        lines.append(f"\n🎾 {matchup}")
        lines.append(f"   ({len(matchup_props)} props available)")
        lines.append("")
        
        # Group by stat within matchup
        by_stat_match = defaultdict(list)
        for p in matchup_props:
            by_stat_match[p.stat].append(p)
        
        for stat in sorted(by_stat_match.keys()):
            stat_props = by_stat_match[stat]
            for prop in stat_props:
                lines.append(f"   • {stat:20s} O/U {prop.line:>6.1f}")
    
    # Detailed player view
    lines.append("\n" + "=" * 80)
    lines.append("PROPS BY PLAYER:")
    lines.append("=" * 80)
    
    by_player = defaultdict(list)
    for prop in props:
        by_player[prop.player].append(prop)
    
    for player in sorted(by_player.keys()):
        player_props = by_player[player]
        opponent = player_props[0].opponent if player_props[0].opponent else "TBD"
        
        lines.append(f"\n🎾 {player} vs {opponent}")
        lines.append(f"   ({len(player_props)} props)")
        lines.append("")
        
        for prop in sorted(player_props, key=lambda p: p.stat):
            lines.append(f"   • {prop.stat:20s} O/U {prop.line:>6.1f}")
    
    lines.append("\n" + "=" * 80)
    lines.append("")
    
    return '\n'.join(lines)


def save_inventory(props: list[TennisProp], filename: str = None):
    """Save inventory report"""
    from datetime import datetime
    
    OUTPUTS_DIR = Path(__file__).parent / "outputs"
    OUTPUTS_DIR.mkdir(exist_ok=True)
    
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"tennis_props_inventory_{timestamp}.txt"
    
    filepath = OUTPUTS_DIR / filename
    
    report = generate_inventory(props)
    filepath.write_text(report, encoding='utf-8')
    
    print(f"\n✓ Inventory saved: {filepath}")
    return filepath


def main():
    """Interactive props inventory"""
    print("\n" + "=" * 80)
    print("🎾 TENNIS PROPS INVENTORY GENERATOR")
    print("=" * 80)
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
        print("\n[X] No valid props found")
        return
    
    # Generate and display
    report = generate_inventory(props)
    print(report)
    
    # Save
    save_inventory(props)


if __name__ == "__main__":
    main()
