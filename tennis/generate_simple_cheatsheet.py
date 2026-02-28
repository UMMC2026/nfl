"""
Tennis Props - SIMPLE CHEAT SHEET
Clean, easy-to-read format
"""
from collections import defaultdict
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from tennis_props_parser import parse_tennis_props, TennisProp


def generate_simple_cheatsheet(props: list[TennisProp]) -> str:
    """Generate super simple, clean cheat sheet"""
    
    lines = []
    lines.append("=" * 90)
    lines.append("🎾 TENNIS PROPS - SIMPLE CHEAT SHEET")
    lines.append("=" * 90)
    
    # Deduplicate
    unique_props = {}
    for prop in props:
        key = (prop.player, prop.stat, prop.line)
        if key not in unique_props:
            unique_props[key] = prop
    
    props = list(unique_props.values())
    lines.append(f"\nTotal Props: {len(props)}")
    lines.append("")
    
    # Group by player
    by_player = defaultdict(list)
    for prop in props:
        by_player[prop.player].append(prop)
    
    # Simple table format
    for player in sorted(by_player.keys()):
        player_props = by_player[player]
        opponent = player_props[0].opponent if player_props[0].opponent else "TBD"
        
        lines.append("-" * 90)
        lines.append(f"PLAYER: {player}")
        lines.append(f"vs {opponent}")
        lines.append("-" * 90)
        
        # Table header
        lines.append(f"{'STAT':<25} {'LINE':>8}   {'PICK':>10}")
        lines.append("-" * 90)
        
        # Sort by stat type
        for prop in sorted(player_props, key=lambda p: p.stat):
            stat = prop.stat
            line = f"{prop.line:.1f}"
            pick = "____"  # User fills this in
            
            lines.append(f"{stat:<25} {line:>8}   {pick:>10}")
        
        lines.append("")
    
    lines.append("=" * 90)
    lines.append("\nHOW TO USE:")
    lines.append("  1. Review each player's available props")
    lines.append("  2. Write HIGHER or LOWER in the PICK column")
    lines.append("  3. Focus on props you have research/confidence in")
    lines.append("=" * 90)
    
    return '\n'.join(lines)


def main():
    """Generate simple cheat sheet"""
    print("\n" + "=" * 90)
    print("🎾 TENNIS PROPS - SIMPLE CHEAT SHEET GENERATOR")
    print("=" * 90)
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
    
    # Generate cheat sheet
    cheatsheet = generate_simple_cheatsheet(props)
    print("\n" + cheatsheet)
    
    # Save
    OUTPUTS_DIR = Path(__file__).parent / "outputs"
    OUTPUTS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"tennis_props_CHEATSHEET_{timestamp}.txt"
    filepath = OUTPUTS_DIR / filename
    
    filepath.write_text(cheatsheet, encoding='utf-8')
    print(f"\n✓ Cheat sheet saved: {filepath}")


if __name__ == "__main__":
    main()
