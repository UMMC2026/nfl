"""
Tennis Props Parser v2 - Parse Underdog paste format for tennis player props
Handles the exact Underdog copy-paste format
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json

TENNIS_DIR = Path(__file__).parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"

@dataclass
class TennisProp:
    """Single tennis prop from Underdog"""
    player: str
    opponent: str
    match_info: str
    stat: str
    line: float
    higher_mult: Optional[float] = None
    lower_mult: Optional[float] = None
    
    @property
    def value_side(self) -> Tuple[str, float]:
        """
        Returns (direction, edge) based on multiplier asymmetry
        Higher multiplier = better payout = potentially undervalued by market
        """
        h = self.higher_mult or 1.0
        l = self.lower_mult or 1.0
        
        edge = abs(h - l)
        
        if h > l + 0.05:
            return ("HIGHER", edge)
        elif l > h + 0.05:
            return ("LOWER", edge)
        return ("NEUTRAL", 0.0)
    
    def to_dict(self) -> dict:
        direction, edge = self.value_side
        return {
            "player": self.player,
            "opponent": self.opponent,
            "match": self.match_info,
            "stat": self.stat,
            "line": self.line,
            "higher_mult": self.higher_mult,
            "lower_mult": self.lower_mult,
            "value_side": direction,
            "mult_edge": round(edge, 3)
        }


# Valid tennis stats we care about - EXPANDED for all Underdog prop types
VALID_STATS = {
    # Match-level
    'Games Won', 'Games Played', 'Total Games Won', 'Total Games',
    '1st Set Games Won', '1st Set Games Played',
    'Sets Won', 'Sets Played',
    
    # Serve stats
    'Aces', 'Double Faults', 
    
    # Break/Return stats
    'Breakpoints Won', 'Break Points Won',
    
    # Tiebreakers
    'Tiebreakers Played', 'Tiebreakers',
    
    # Fantasy/Composite
    'Fantasy Score', 'Fantasy Points'
}

# Normalize stat names (handle variations)
STAT_NORMALIZATION = {
    'Total Games Won': 'Games Won',
    'Break Points Won': 'Breakpoints Won',
    'Fantasy Points': 'Fantasy Score',
    # Keep Underdog variants as-is for now
    'Games Played': 'Games Played',  # Maps to total_games in Monte Carlo
    '1st Set Games Won': '1st Set Games Won',
    '1st Set Games Played': '1st Set Games Played'
}


def parse_multiplier(text: str) -> Optional[float]:
    """Extract multiplier value from text like '1.06x'"""
    match = re.search(r'(\d+\.?\d*)x', text)
    if match:
        return float(match.group(1))
    return None


def parse_tennis_props(paste: str) -> List[TennisProp]:
    """
    Parse Underdog tennis props paste - Handles BOTH formats robustly.
    
    Format 1 (Verbose): "Player NameGoblin\nPlayer - Player\nPlayer Name\n@ Opponent Time\n\nLine\nAces\nMore"
    Format 2 (Compact): "athlete or team avatar\nPlayer Name\nName vs Name - Time\n\nLine\nAces\n\nHigher\n0.96x"
    """
    props = []
    lines = paste.strip().split('\n')
    
    current_player = None
    current_opponent = None
    current_match_info = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip pure noise lines
        if not line or line in ['athlete or team avatar', 'Fewer picks', 'Goblin', 'Demon', 'More picks', '']:
            i += 1
            continue
        
        # Clean Goblin/Demon suffixes inline
        line_cleaned = re.sub(r'(Goblin|Demon)$', '', line).strip()
        
        # PATTERN 1: Detect matchup lines
        # Matches: "Machac vs Musetti - 5:30PM CST" OR "Name vs Name - Time"
        match_vs = re.match(r'^([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+vs\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*[-–]\s*(.+)$', line_cleaned, re.IGNORECASE)
        if match_vs:
            p1 = match_vs.group(1).strip()
            p2 = match_vs.group(2).strip()
            time_info = match_vs.group(3).strip()
            current_match_info = f"{p1} vs {p2} - {time_info}"
            
            # Look BACK for full player name (should be 1-3 lines above)
            for j in range(i - 1, max(0, i - 4), -1):
                prev = lines[j].strip()
                prev_clean = re.sub(r'(Goblin|Demon|athlete or team avatar)$', '', prev).strip()
                
                # Must be a capitalized full name (First Last)
                if ' ' in prev_clean and re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', prev_clean):
                    # Avoid false positives ("Player - Player", "vs", etc.)
                    if not any(x in prev_clean for x in ['vs', ' - Player', '@']):
                        current_player = prev_clean
                        
                        # Determine opponent from p1/p2
                        # If player name contains p1, opponent is p2, else p1
                        if any(word.lower() in p1.lower() for word in current_player.split()):
                            current_opponent = p2
                        else:
                            current_opponent = p1
                        break
            
            i += 1
            continue
        
        # PATTERN 2: Detect @ opponent lines (verbose format)
        # Matches: "@ Lorenzo Musetti Fri 5:30pm"
        match_at = re.match(r'^[@]\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(.+)$', line_cleaned)
        if match_at and current_player:
            current_opponent = match_at.group(1).strip()
            time_info = match_at.group(2).strip()
            current_match_info = f"{current_player} @ {current_opponent} {time_info}"
            i += 1
            continue
        
        # PATTERN 3: Detect line value (number on its own line)
        try:
            line_value = float(line)
            
            # Look ahead for stat name (next 1-3 lines)
            stat_name = None
            stat_idx = None
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip()
                if next_line in VALID_STATS:
                    stat_name = next_line
                    stat_idx = j
                    break
            
            # Normalize stat name if needed
            if stat_name and stat_name in STAT_NORMALIZATION:
                stat_name = STAT_NORMALIZATION[stat_name]
            
            if stat_name and current_player:
                # Scan for multipliers (after stat name, next ~10 lines)
                higher_mult = None
                lower_mult = None
                
                in_higher = False
                in_lower = False
                
                for k in range(stat_idx + 1, min(stat_idx + 12, len(lines))):
                    scan = lines[k].strip()
                    
                    # Stop at next prop (another number)
                    try:
                        float(scan)
                        break
                    except:
                        pass
                    
                    # Detect direction markers
                    if scan in ['Higher', 'More']:
                        in_higher = True
                        in_lower = False
                    elif scan in ['Lower', 'Less']:
                        in_lower = True
                        in_higher = False
                    elif 'x' in scan:  # Multiplier like "0.96x"
                        mult = parse_multiplier(scan)
                        if mult:
                            if in_higher:
                                higher_mult = mult
                                in_higher = False
                            elif in_lower:
                                lower_mult = mult
                                in_lower = False
                
                # Create prop
                prop = TennisProp(
                    player=current_player,
                    opponent=current_opponent or "TBD",
                    match_info=current_match_info or "",
                    stat=stat_name,
                    line=line_value,
                    higher_mult=higher_mult,
                    lower_mult=lower_mult
                )
                props.append(prop)
                
        except ValueError:
            # Not a number, check if it's a player name candidate
            if ' ' in line_cleaned and re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', line_cleaned):
                # Could be setting current player for next prop
                if not any(x in line_cleaned for x in ['vs', ' - Player', '@', 'Higher', 'Lower', 'More', 'Less']):
                    # Only update if we don't have one yet or this looks fresher
                    if not current_player or i > 0:
                        potential_player = line_cleaned
                        # Validate it's not noise
                        if potential_player not in ['athlete or team avatar']:
                            current_player = potential_player
        
        i += 1
    
    return props


def analyze_tennis_props(props: List[TennisProp], save: bool = True) -> str:
    """Generate analysis report for tennis props with value identification"""
    
    if not props:
        return "No props parsed from input."
    
    report = []
    report.append("=" * 65)
    report.append("  TENNIS PROPS ANALYSIS")
    report.append(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("=" * 65)
    report.append("")
    
    # Group by player
    players = {}
    for prop in props:
        if prop.player not in players:
            players[prop.player] = []
        players[prop.player].append(prop)
    
    # Collect value plays
    value_plays = []
    
    for player, player_props in players.items():
        report.append("-" * 65)
        report.append(f"  {player}")
        if player_props:
            report.append(f"   vs {player_props[0].opponent}")
            report.append(f"   {player_props[0].match_info}")
        report.append("")
        
        for prop in player_props:
            h_mult = f"{prop.higher_mult:.2f}x" if prop.higher_mult else "---"
            l_mult = f"{prop.lower_mult:.2f}x" if prop.lower_mult else "---"
            
            direction, edge = prop.value_side
            value_marker = ""
            
            if direction == "HIGHER" and edge >= 0.15:
                value_marker = " << VALUE"
                value_plays.append((prop, direction, edge))
            elif direction == "LOWER" and edge >= 0.15:
                value_marker = " << VALUE"
                value_plays.append((prop, direction, edge))
            elif direction != "NEUTRAL" and edge >= 0.08:
                value_marker = " < lean"
                value_plays.append((prop, direction, edge))
            
            report.append(f"   {prop.stat}")
            report.append(f"      Line: {prop.line}")
            report.append(f"      Higher: {h_mult}  |  Lower: {l_mult}{value_marker}")
            report.append("")
    
    # Value Summary
    report.append("=" * 65)
    if value_plays:
        report.append("  VALUE PLAYS (Sorted by Edge)")
        report.append("=" * 65)
        
        # Sort by edge magnitude
        value_plays.sort(key=lambda x: x[2], reverse=True)
        
        for prop, direction, edge in value_plays:
            mult = prop.higher_mult if direction == "HIGHER" else prop.lower_mult
            mult_str = f"{mult:.2f}x" if mult else "1.00x"
            tier = "STRONG" if edge >= 0.25 else "LEAN" if edge >= 0.15 else "lean"
            
            report.append(f"")
            report.append(f"  [{tier}] {prop.player}")
            report.append(f"         {prop.stat} {direction} {prop.line}")
            report.append(f"         Mult: {mult_str} | Edge: {edge:.2f}")
    else:
        report.append("  No clear value plays found")
        report.append("   Multipliers roughly balanced on all props")
    
    report.append("")
    report.append("=" * 65)
    report.append("  DISCLAIMER")
    report.append("   Analysis based on multiplier asymmetry only.")
    report.append("   No historical player stats currently integrated.")
    report.append("   Use as directional signal, not primary edge.")
    report.append("=" * 65)
    
    report_text = "\n".join(report)
    
    # Save output
    if save:
        OUTPUTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        # Save JSON
        json_file = OUTPUTS_DIR / f"tennis_props_{timestamp}.json"
        json_data = {
            "generated": datetime.now().isoformat(),
            "props": [p.to_dict() for p in props],
            "value_plays": [
                {"player": p.player, "stat": p.stat, "line": p.line, 
                 "direction": d, "edge": e} 
                for p, d, e in value_plays
            ]
        }
        json_file.write_text(json.dumps(json_data, indent=2))
        
        # Save report
        report_file = OUTPUTS_DIR / f"tennis_props_report_{timestamp}.txt"
        report_file.write_text(report_text, encoding='utf-8')
        
        # Latest symlinks
        (OUTPUTS_DIR / "tennis_props_latest.json").write_text(json.dumps(json_data, indent=2))
        (OUTPUTS_DIR / "tennis_props_report_latest.txt").write_text(report_text, encoding='utf-8')
        
        print(f"  Saved: {json_file.name}")
        
        # === CROSS-SPORT DATABASE AUTO-SAVE ===
        try:
            from engine.daily_picks_db import save_top_picks
            # Convert value_plays to edge format for cross-sport DB
            tennis_edges = []
            for prop, direction, edge in value_plays:
                tier = "STRONG" if edge >= 0.25 else "LEAN" if edge >= 0.15 else None
                if tier:
                    tennis_edges.append({
                        'player': prop.player,
                        'stat': prop.stat,
                        'line': prop.line,
                        'direction': direction.lower(),
                        'probability': 50 + (edge * 100),  # Convert edge to probability
                        'tier': tier,
                        'team': 'Tennis'
                    })
            if tennis_edges:
                save_top_picks(tennis_edges, "Tennis", top_n=5)
                print(f"  ✅ Saved top {min(5, len(tennis_edges))} Tennis picks to cross-sport database")
        except Exception as e:
            print(f"  ⚠️ Cross-sport save failed: {e}")
    
    return report_text


def quick_analyze_props():
    """Interactive: paste props and analyze"""
    print("=" * 65)
    print("  TENNIS PROPS ANALYZER")
    print("=" * 65)
    print()
    print("Paste your Underdog tennis props below.")
    print("Press Enter twice when done.")
    print()
    
    lines = []
    empty_count = 0
    
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
            else:
                empty_count = 0
            lines.append(line)
        except EOFError:
            break
    
    paste = "\n".join(lines)
    props = parse_tennis_props(paste)
    
    print(f"\n  Parsed {len(props)} props")
    print()
    print(analyze_tennis_props(props))


if __name__ == "__main__":
    # Test with the user's exact paste
    test_paste = """
Priscilla Hon
Hon vs Jovic - 4:05AM CST

7.5
Games Won

Higher

Lower
3.5
1st Set Games Won

Higher

Lower
0.5
Sets Won

Higher
1.1x

Lower
0.76x

4.5
Aces

Higher
1.06x

Lower
0.86x
2.5
Breakpoints Won

Higher
1.09x

Lower
0.83x
3.5
Double Faults

Higher
0.96x

Fewer picks
athlete or team avatar
Iva Jovic
Hon vs Jovic - 4:05AM CST


19.5
Games Played

Higher

Lower
12.5
Games Won

Higher
1.04x

Lower
0.81x
8.5
1st Set Games Played

Higher
0.77x

Lower
1.07x
5.5
1st Set Games Won

Higher
0.62x

Lower
1.64x
2.5
Sets Played

Higher
1.34x

Lower
0.67x

1.5
Aces

Higher
0.96x
4.5
Breakpoints Won

Higher
0.79x

Lower
1.07x

0.5
Tiebreakers Played

Higher
1.61x

Lower
0.62x
1.5
Double Faults

Higher
0.86x
"""
    
    props = parse_tennis_props(test_paste)
    print(f"  Parsed {len(props)} props\n")
    
    for p in props:
        print(f"  {p.player}: {p.stat} {p.line} (H:{p.higher_mult} L:{p.lower_mult})")
    
    print("\n" + analyze_tennis_props(props, save=False))
