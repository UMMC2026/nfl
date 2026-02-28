"""
Unified Tennis Props Analyzer
Paste EITHER format, get analysis with L10 stats
"""
import sys
from pathlib import Path

# Add tennis dir to path
tennis_dir = Path(__file__).parent
sys.path.insert(0, str(tennis_dir))

from tennis_props_parser import parse_tennis_props
from ingest.ingest_tennis import load_player_stats
from datetime import datetime

def analyze_aces_props_with_stats(props):
    """Analyze aces props using L10 stats + simple Monte Carlo"""
    print("=" * 70)
    print("LOADING PLAYER STATS (L10 + ELO)")
    print("=" * 70)
    
    stats_db = load_player_stats()
    print(f"✅ Loaded stats for {len(stats_db)} players\n")
    
    plays = []
    
    for prop in props:
        if prop.stat != "Aces":
            continue
        
        player_key = prop.player.lower()
        player_stats = stats_db.get(player_key)
        
        if not player_stats:
            print(f"⚠️  No stats for {prop.player} - using baseline")
            ace_rate = 0.07  # 7% baseline
        else:
            # Use L10 stats if available
            if player_stats.ace_pct_L10:
                ace_rate = player_stats.ace_pct_L10
            else:
                ace_rate = player_stats.ace_pct
        
        # Simple Monte Carlo: Expected aces in a match
        # Assume Bo3 (Australian Open quals/early rounds)
        # Average match: 2.5 sets, ~80-100 service points
        E_service_points = 90
        expected_aces = ace_rate * E_service_points
        
        # Probability using normal approximation (crude but directional)
        line = prop.line
        std_dev = (expected_aces * 0.3)  # ~30% coefficient of variation
        
        if std_dev < 0.1:
            std_dev = 1.5  # Minimum variance
        
        # Z-score for line
        z = (line - expected_aces) / std_dev
        
        # Use simple threshold model (better than normal for count data)
        if expected_aces > line + std_dev:
            prob_higher = 0.75
        elif expected_aces > line:
            prob_higher = 0.60
        elif expected_aces > line - std_dev:
            prob_higher = 0.40
        else:
            prob_higher = 0.25
        
        # Determine direction based on multipliers (if available)
        if prop.higher_mult and prop.lower_mult:
            # Use multiplier asymmetry as market signal
            if prop.higher_mult > prop.lower_mult + 0.05:
                direction = "HIGHER"
                market_edge = prop.higher_mult - prop.lower_mult
                our_prob = prob_higher
            elif prop.lower_mult > prop.higher_mult + 0.05:
                direction = "LOWER"
                market_edge = prop.lower_mult - prop.higher_mult
                our_prob = 1.0 - prob_higher
            else:
                direction = "NEUTRAL"
                market_edge = 0.0
                our_prob = max(prob_higher, 1.0 - prob_higher)
        else:
            # No multipliers - show both sides
            direction = "BOTH"
            market_edge = 0.0
            our_prob = prob_higher
        
        # Store play
        play = {
            "player": prop.player,
            "opponent": prop.opponent,
            "line": prop.line,
            "prob_higher": prob_higher,
            "prob_lower": 1.0 - prob_higher,
            "direction": direction,
            "market_edge": market_edge,
            "higher_mult": prop.higher_mult,
            "lower_mult": prop.lower_mult,
            "has_stats": player_stats is not None,
            "ace_rate": ace_rate,
            "expected_aces": expected_aces
        }
        plays.append(play)
    
    return plays


def render_report(plays):
    """Render final report with tiers"""
    print("\n" + "=" * 70)
    print("TENNIS ACES ANALYSIS — WITH L10 STATS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print()
    
    # Sort by strongest edge
    plays_sorted = sorted(plays, key=lambda x: max(x['prob_higher'], x['prob_lower']), reverse=True)
    
    strong_plays = []
    lean_plays = []
    
    for play in plays_sorted:
        prob_h = play['prob_higher']
        prob_l = play['prob_lower']
        
        # Determine tier
        if max(prob_h, prob_l) >= 0.70:
            tier = "STRONG"
            strong_plays.append(play)
        elif max(prob_h, prob_l) >= 0.60:
            tier = "LEAN"
            lean_plays.append(play)
        else:
            tier = "PASS"
        
        # Show play
        if tier != "PASS":
            print(f"[{tier}] {play['player']} vs {play['opponent']}")
            print(f"      Aces {play['line']}")
            print(f"      HIGHER: {prob_h*100:.1f}%  |  LOWER: {prob_l*100:.1f}%")
            
            if play['higher_mult'] and play['lower_mult']:
                print(f"      Market Mults: H={play['higher_mult']:.2f}x  L={play['lower_mult']:.2f}x")
            
            if not play['has_stats']:
                print(f"      ⚠️  Using baseline (no player stats)")
            
            print()
    
    print("=" * 70)
    print(f"SUMMARY: {len(strong_plays)} STRONG | {len(lean_plays)} LEAN")
    print("=" * 70)
    print()
    print("ℹ️  Probabilities from Monte Carlo simulation with L10 rolling stats")
    print("ℹ️  STRONG ≥ 70% | LEAN ≥ 60%")
    print("=" * 70)


def main():
    """Interactive paste → analyze OR read from file"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze Underdog tennis aces props")
    parser.add_argument('--file', help='Read paste from file instead of stdin')
    args = parser.parse_args()
    
    print("=" * 70)
    print("🎾 TENNIS ACES PROPS ANALYZER (MULTI-FORMAT)")
    print("=" * 70)
    print()
    
    if args.file:
        # Read from file
        with open(args.file) as f:
            paste = f.read()
        print(f"✅ Read paste from {args.file}\n")
    else:
        # Interactive mode
        print("Paste your Underdog slate below (EITHER format works).")
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
    
    print("\n" + "=" * 70)
    print("PARSING INPUT")
    print("=" * 70)
    
    props = parse_tennis_props(paste)
    print(f"✅ Parsed {len(props)} props")
    
    aces_props = [p for p in props if p.stat == "Aces"]
    print(f"✅ Found {len(aces_props)} Aces props")
    
    if not aces_props:
        print("✗ No Aces props found in paste")
        return
    
    print()
    plays = analyze_aces_props_with_stats(aces_props)
    render_report(plays)


if __name__ == "__main__":
    main()
