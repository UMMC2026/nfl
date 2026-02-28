"""
Super Bowl LX One-Off Analyzer
==============================
Standalone analyzer for Super Bowl props.
Does NOT modify frozen NFL v1.0 codebase.

Usage:
    python superbowl_analyzer.py
    
Then paste Underdog props when prompted.
"""

import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import re

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# SUPER BOWL LX CONFIG
# =============================================================================

SUPERBOWL_CONFIG = {
    "event": "Super Bowl LX",
    "date": "2026-02-02",
    "teams": {
        "KC": {"name": "Kansas City Chiefs", "seed": 1, "conf": "AFC"},
        "PHI": {"name": "Philadelphia Eagles", "seed": 1, "conf": "NFC"},
    },
    # Championship game adjustments
    "playoff_variance_mult": 1.15,  # Higher variance in playoffs
    "sharp_line_penalty": 0.03,     # Lines are sharper, reduce edge
    "min_edge_threshold": 0.02,     # Need 2% edge minimum
}

# Tier thresholds (conservative for championship)
TIERS = {
    "SLAM": None,      # DISABLED for Super Bowl (too risky)
    "STRONG": 0.64,    # Tighter than regular season
    "LEAN": 0.56,      # Tighter than regular season
}


@dataclass
class SuperBowlProp:
    """Single Super Bowl prop."""
    player: str
    team: str
    stat: str
    line: float
    direction: str  # higher/lower
    
    # Analysis fields
    mu: float = 0.0
    sigma: float = 0.0
    probability: float = 0.50
    tier: str = "NO_PLAY"
    edge: float = 0.0
    risk_tags: List[str] = field(default_factory=list)
    notes: str = ""


# =============================================================================
# PLAYER PROJECTIONS (Super Bowl LX specific)
# =============================================================================

# Based on playoff performance + season stats
PLAYER_PROJECTIONS = {
    # CHIEFS OFFENSE
    "Patrick Mahomes": {
        "passing_yards": {"mu": 285, "sigma": 55},
        "passing_tds": {"mu": 2.3, "sigma": 1.1},
        "completions": {"mu": 24, "sigma": 5},
        "attempts": {"mu": 38, "sigma": 6},
        "interceptions": {"mu": 0.8, "sigma": 0.9},
        "rushing_yards": {"mu": 22, "sigma": 15},
    },
    "Travis Kelce": {
        "receptions": {"mu": 7.5, "sigma": 2.5},
        "receiving_yards": {"mu": 78, "sigma": 28},
        "receiving_tds": {"mu": 0.6, "sigma": 0.7},
    },
    "Isiah Pacheco": {
        "rushing_yards": {"mu": 62, "sigma": 25},
        "rushing_attempts": {"mu": 15, "sigma": 4},
        "receptions": {"mu": 2.5, "sigma": 1.5},
    },
    "Rashee Rice": {
        "receptions": {"mu": 5.5, "sigma": 2.2},
        "receiving_yards": {"mu": 58, "sigma": 25},
    },
    "Xavier Worthy": {
        "receptions": {"mu": 3.5, "sigma": 1.8},
        "receiving_yards": {"mu": 42, "sigma": 22},
    },
    
    # EAGLES OFFENSE
    "Jalen Hurts": {
        "passing_yards": {"mu": 245, "sigma": 50},
        "passing_tds": {"mu": 1.8, "sigma": 1.0},
        "rushing_yards": {"mu": 45, "sigma": 22},
        "rushing_tds": {"mu": 0.7, "sigma": 0.7},
        "completions": {"mu": 20, "sigma": 5},
    },
    "Saquon Barkley": {
        "rushing_yards": {"mu": 95, "sigma": 35},
        "rushing_attempts": {"mu": 22, "sigma": 5},
        "receptions": {"mu": 3.5, "sigma": 2.0},
        "receiving_yards": {"mu": 28, "sigma": 18},
        "rushing_tds": {"mu": 0.9, "sigma": 0.8},
    },
    "AJ Brown": {
        "receptions": {"mu": 5.5, "sigma": 2.3},
        "receiving_yards": {"mu": 72, "sigma": 32},
        "receiving_tds": {"mu": 0.5, "sigma": 0.6},
    },
    "DeVonta Smith": {
        "receptions": {"mu": 5.0, "sigma": 2.0},
        "receiving_yards": {"mu": 58, "sigma": 25},
    },
    "Dallas Goedert": {
        "receptions": {"mu": 4.0, "sigma": 1.8},
        "receiving_yards": {"mu": 42, "sigma": 20},
    },
}

# Stat aliases
STAT_ALIASES = {
    "pass yds": "passing_yards",
    "pass yards": "passing_yards",
    "passing yds": "passing_yards",
    "pass tds": "passing_tds",
    "passing touchdowns": "passing_tds",
    "rush yds": "rushing_yards",
    "rush yards": "rushing_yards",
    "rushing yds": "rushing_yards",
    "rush tds": "rushing_tds",
    "rushing touchdowns": "rushing_tds",
    "rec": "receptions",
    "recs": "receptions",
    "catches": "receptions",
    "rec yds": "receiving_yards",
    "rec yards": "receiving_yards",
    "receiving yds": "receiving_yards",
    "rec tds": "receiving_tds",
    "receiving touchdowns": "receiving_tds",
    "comps": "completions",
    "comp": "completions",
    "ints": "interceptions",
    "int": "interceptions",
    "att": "attempts",
    "pass att": "attempts",
    "rush att": "rushing_attempts",
}


def normalize_stat(stat: str) -> str:
    """Normalize stat name."""
    stat_lower = stat.lower().strip()
    return STAT_ALIASES.get(stat_lower, stat_lower.replace(" ", "_"))


def normalize_player(name: str) -> str:
    """Normalize player name for matching."""
    # Common variations
    aliases = {
        "mahomes": "Patrick Mahomes",
        "pat mahomes": "Patrick Mahomes",
        "kelce": "Travis Kelce",
        "pacheco": "Isiah Pacheco",
        "rice": "Rashee Rice",
        "worthy": "Xavier Worthy",
        "hurts": "Jalen Hurts",
        "barkley": "Saquon Barkley",
        "saquon": "Saquon Barkley",
        "aj brown": "AJ Brown",
        "brown": "AJ Brown",
        "devonta smith": "DeVonta Smith",
        "smith": "DeVonta Smith",
        "goedert": "Dallas Goedert",
    }
    
    name_lower = name.lower().strip()
    if name_lower in aliases:
        return aliases[name_lower]
    
    # Try to match partial names
    for key, full_name in PLAYER_PROJECTIONS.items():
        if name_lower in key.lower():
            return key
    
    return name.title()


# =============================================================================
# PROBABILITY CALCULATION
# =============================================================================

def calculate_probability(mu: float, sigma: float, line: float, direction: str) -> float:
    """Calculate probability using normal distribution."""
    from math import erf, sqrt
    
    if sigma <= 0:
        return 0.50
    
    # Z-score
    z = (line - mu) / sigma
    
    # CDF using error function
    cdf = 0.5 * (1 + erf(z / sqrt(2)))
    
    if direction.lower() in ("higher", "over"):
        prob = 1 - cdf
    else:
        prob = cdf
    
    # Apply playoff variance adjustment
    prob = 0.5 + (prob - 0.5) * (1 / SUPERBOWL_CONFIG["playoff_variance_mult"])
    
    return max(0.01, min(0.99, prob))


def get_tier(probability: float) -> str:
    """Get tier based on probability."""
    if TIERS["SLAM"] and probability >= TIERS["SLAM"]:
        return "SLAM"
    elif probability >= TIERS["STRONG"]:
        return "STRONG"
    elif probability >= TIERS["LEAN"]:
        return "LEAN"
    else:
        return "NO_PLAY"


# =============================================================================
# PROP PARSING
# =============================================================================

def parse_underdog_props(text: str) -> List[SuperBowlProp]:
    """Parse Underdog-style prop text."""
    props = []
    lines = text.strip().split('\n')
    
    current_player = None
    current_team = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try to extract player name (usually starts with name)
        # Pattern: "Patrick Mahomes KC" or just name
        player_match = re.match(r'^([A-Za-z\.\'\-\s]+?)(?:\s+(KC|PHI))?$', line)
        if player_match and not any(char.isdigit() for char in line):
            potential_name = player_match.group(1).strip()
            if len(potential_name) > 3 and potential_name not in ['Higher', 'Lower', 'Over', 'Under']:
                current_player = normalize_player(potential_name)
                current_team = player_match.group(2) if player_match.group(2) else None
                continue
        
        # Try to extract prop line
        # Pattern: "Passing Yards 274.5" or "274.5 Passing Yards" or "Pass Yds Higher 274.5"
        prop_patterns = [
            r'([A-Za-z\s]+?)\s+(Higher|Lower|Over|Under)\s+([\d\.]+)',
            r'([\d\.]+)\s+([A-Za-z\s]+?)\s+(Higher|Lower|Over|Under)',
            r'([A-Za-z\s]+?)\s+([\d\.]+)',
        ]
        
        for pattern in prop_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match and current_player:
                groups = match.groups()
                
                if len(groups) == 3:
                    if groups[0].replace('.', '').isdigit():
                        # "274.5 Passing Yards Higher"
                        line_val = float(groups[0])
                        stat = groups[1]
                        direction = groups[2]
                    else:
                        # "Passing Yards Higher 274.5"
                        stat = groups[0]
                        direction = groups[1]
                        line_val = float(groups[2])
                else:
                    # "Passing Yards 274.5" - assume higher
                    stat = groups[0]
                    line_val = float(groups[1])
                    direction = "higher"
                
                prop = SuperBowlProp(
                    player=current_player,
                    team=current_team or "",
                    stat=normalize_stat(stat),
                    line=line_val,
                    direction=direction.lower(),
                )
                props.append(prop)
                break
    
    return props


def parse_simple_format(text: str) -> List[SuperBowlProp]:
    """Parse simple format: Player, Stat, Line, Direction."""
    props = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Try CSV-ish format
        parts = re.split(r'[,\t]+', line)
        if len(parts) >= 3:
            player = normalize_player(parts[0])
            stat = normalize_stat(parts[1])
            
            try:
                line_val = float(parts[2].strip())
            except ValueError:
                continue
            
            direction = parts[3].strip().lower() if len(parts) > 3 else "higher"
            
            prop = SuperBowlProp(
                player=player,
                team="",
                stat=stat,
                line=line_val,
                direction=direction,
            )
            props.append(prop)
    
    return props


# =============================================================================
# ANALYSIS
# =============================================================================

def analyze_prop(prop: SuperBowlProp) -> SuperBowlProp:
    """Analyze a single prop."""
    
    # Get player projections
    player_data = PLAYER_PROJECTIONS.get(prop.player, {})
    stat_data = player_data.get(prop.stat, None)
    
    if not stat_data:
        prop.notes = f"No projection data for {prop.player} {prop.stat}"
        prop.tier = "NO_PLAY"
        prop.risk_tags.append("NO_DATA")
        return prop
    
    prop.mu = stat_data["mu"]
    prop.sigma = stat_data["sigma"] * SUPERBOWL_CONFIG["playoff_variance_mult"]
    
    # Calculate probability
    prop.probability = calculate_probability(
        prop.mu, prop.sigma, prop.line, prop.direction
    )
    
    # Calculate edge (vs implied 50%)
    prop.edge = prop.probability - 0.50
    
    # Apply sharp line penalty
    prop.probability -= SUPERBOWL_CONFIG["sharp_line_penalty"]
    prop.probability = max(0.01, min(0.99, prop.probability))
    
    # Get tier
    prop.tier = get_tier(prop.probability)
    
    # Risk tags
    if prop.stat in ["passing_tds", "rushing_tds", "receiving_tds"]:
        prop.risk_tags.append("TD_VOLATILE")
    
    if abs(prop.line - prop.mu) < prop.sigma * 0.3:
        prop.risk_tags.append("COIN_FLIP")
    
    if prop.edge < SUPERBOWL_CONFIG["min_edge_threshold"]:
        prop.risk_tags.append("THIN_EDGE")
        if prop.tier != "NO_PLAY":
            prop.tier = "LEAN"  # Downgrade thin edges
    
    # Notes
    z_score = (prop.line - prop.mu) / prop.sigma if prop.sigma > 0 else 0
    prop.notes = f"μ={prop.mu:.1f}, σ={prop.sigma:.1f}, z={z_score:+.2f}"
    
    return prop


def analyze_slate(props: List[SuperBowlProp]) -> List[SuperBowlProp]:
    """Analyze all props."""
    return [analyze_prop(p) for p in props]


# =============================================================================
# OUTPUT
# =============================================================================

def print_analysis(props: List[SuperBowlProp]):
    """Print analysis results."""
    
    print("\n" + "=" * 70)
    print(f"  🏈 SUPER BOWL LX ANALYSIS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Chiefs vs Eagles | Championship Game Mode")
    print("=" * 70)
    
    # Sort by probability
    sorted_props = sorted(props, key=lambda p: p.probability, reverse=True)
    
    # Group by tier
    strong = [p for p in sorted_props if p.tier == "STRONG"]
    lean = [p for p in sorted_props if p.tier == "LEAN"]
    no_play = [p for p in sorted_props if p.tier == "NO_PLAY"]
    
    # STRONG picks
    if strong:
        print(f"\n  🟢 STRONG PICKS ({len(strong)})")
        print("  " + "-" * 66)
        for p in strong:
            dir_symbol = "O" if p.direction in ("higher", "over") else "U"
            risk_str = f" ⚠️ {', '.join(p.risk_tags)}" if p.risk_tags else ""
            print(f"    {p.player:<18} {p.stat:<16} {p.line:>6.1f} {dir_symbol}")
            print(f"      Prob: {p.probability:.1%} | Edge: {p.edge:+.1%} | {p.notes}{risk_str}")
            print()
    
    # LEAN picks
    if lean:
        print(f"\n  🟡 LEAN PICKS ({len(lean)})")
        print("  " + "-" * 66)
        for p in lean:
            dir_symbol = "O" if p.direction in ("higher", "over") else "U"
            risk_str = f" ⚠️ {', '.join(p.risk_tags)}" if p.risk_tags else ""
            print(f"    {p.player:<18} {p.stat:<16} {p.line:>6.1f} {dir_symbol}")
            print(f"      Prob: {p.probability:.1%} | Edge: {p.edge:+.1%} | {p.notes}{risk_str}")
            print()
    
    # NO PLAY summary
    if no_play:
        print(f"\n  ⛔ NO PLAY ({len(no_play)})")
        print("  " + "-" * 66)
        for p in no_play[:5]:  # Show first 5
            dir_symbol = "O" if p.direction in ("higher", "over") else "U"
            print(f"    {p.player:<18} {p.stat:<16} {p.line:>6.1f} {dir_symbol} — {p.notes}")
        if len(no_play) > 5:
            print(f"    ... and {len(no_play) - 5} more")
    
    # Summary
    print("\n" + "=" * 70)
    print(f"  SUMMARY: {len(strong)} STRONG | {len(lean)} LEAN | {len(no_play)} NO PLAY")
    print("=" * 70)
    
    # Save to cross-sport DB
    try:
        from engine.daily_picks_db import save_top_picks
        nfl_edges = []
        for p in sorted_props:
            if p.tier in ("STRONG", "LEAN"):
                nfl_edges.append({
                    "player": p.player,
                    "stat": p.stat,
                    "line": p.line,
                    "direction": p.direction,
                    "probability": p.probability,
                    "tier": p.tier,
                })
        if nfl_edges:
            save_top_picks(nfl_edges, "NFL", top_n=5)
            print(f"\n  📊 Cross-Sport DB: Saved top 5 Super Bowl picks")
    except ImportError:
        pass
    except Exception as e:
        print(f"\n  ⚠️ Cross-Sport DB save failed: {e}")
    
    return sorted_props


def save_report(props: List[SuperBowlProp]):
    """Save report to file."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = PROJECT_ROOT / "outputs" / f"SUPERBOWL_LX_ANALYSIS_{ts}.txt"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write(f"  SUPER BOWL LX ANALYSIS — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"  Chiefs vs Eagles | Generated by superbowl_analyzer.py\n")
        f.write("=" * 70 + "\n\n")
        
        sorted_props = sorted(props, key=lambda p: p.probability, reverse=True)
        
        for p in sorted_props:
            if p.tier != "NO_PLAY":
                dir_symbol = "OVER" if p.direction in ("higher", "over") else "UNDER"
                f.write(f"[{p.tier}] {p.player} — {p.stat} {dir_symbol} {p.line}\n")
                f.write(f"  Probability: {p.probability:.1%} | Edge: {p.edge:+.1%}\n")
                f.write(f"  Model: {p.notes}\n")
                if p.risk_tags:
                    f.write(f"  Risks: {', '.join(p.risk_tags)}\n")
                f.write("\n")
    
    print(f"\n  📁 Report saved: {output_path.name}")
    return output_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "=" * 70)
    print("  🏈 SUPER BOWL LX ANALYZER")
    print("  Chiefs vs Eagles — February 2, 2026")
    print("=" * 70)
    print("\n  Paste Underdog props below (Ctrl+Z or Ctrl+D when done):")
    print("  Format: Player name, then stat lines")
    print("  Example:")
    print("    Patrick Mahomes")
    print("    Passing Yards Higher 274.5")
    print("    Pass TDs Higher 1.5")
    print("-" * 70)
    
    try:
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        
        text = "\n".join(lines)
        
        if not text.strip():
            print("\n  No props entered. Using sample data...")
            # Sample props for demo
            text = """
Patrick Mahomes
Passing Yards Higher 274.5
Pass TDs Higher 1.5
Completions Higher 23.5

Travis Kelce
Receptions Higher 6.5
Receiving Yards Higher 72.5

Saquon Barkley
Rushing Yards Higher 89.5
Receptions Higher 3.5

Jalen Hurts
Passing Yards Higher 234.5
Rushing Yards Higher 39.5

AJ Brown
Receptions Higher 4.5
Receiving Yards Higher 64.5
"""
        
        # Parse props
        props = parse_underdog_props(text)
        
        if not props:
            props = parse_simple_format(text)
        
        if not props:
            print("\n  ❌ Could not parse any props. Check format.")
            return 1
        
        print(f"\n  ✅ Parsed {len(props)} props")
        
        # Analyze
        analyzed = analyze_slate(props)
        
        # Print results
        print_analysis(analyzed)
        
        # Save report
        save_report(analyzed)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n  Cancelled.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
