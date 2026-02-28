"""
SUPER BOWL LIX QUICK PROJECTION
Generates probability projections for Super Bowl props
"""

import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_superbowl_config():
    """Load Super Bowl configuration."""
    config_file = PROJECT_ROOT / "config" / "nfl_superbowl.json"
    
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    
    return {}


def quick_analyze_superbowl():
    """Quick Super Bowl analysis tool."""
    
    print("\n" + "=" * 80)
    print("🏈 SUPER BOWL LIX - QUICK PROJECTION TOOL")
    print("=" * 80 + "\n")
    
    config = load_superbowl_config()
    
    print(f"Event: {config.get('event', 'Super Bowl LIX')}")
    print(f"Date: {config.get('date', '2026-02-09')}")
    print(f"Location: {config.get('location', 'Caesars Superdome, New Orleans')}")
    print(f"Venue Type: {config.get('venue_type', 'dome').upper()}")
    print(f"Weather Impact: {'NO' if not config.get('weather_impact') else 'YES'}")
    
    print("\n" + "-" * 80)
    print("TIER THRESHOLDS (Updated Feb 2026)")
    print("-" * 80)
    
    thresholds = config.get('tier_thresholds', {})
    print(f"  SLAM:   {thresholds.get('SLAM', 0.80):.0%}+  (Only bet if extremely confident)")
    print(f"  STRONG: {thresholds.get('STRONG', 0.70):.0%}+  (Recommended bet)")
    print(f"  LEAN:   {thresholds.get('LEAN', 0.58):.0%}+  (Marginal bet)")
    print(f"  Min Edge: {thresholds.get('min_edge', 0.03):.1%}  (Required edge over market)")
    
    print("\n" + "-" * 80)
    print("QUICK PROP ENTRY")
    print("-" * 80)
    print("\nEnter props to analyze (or press Enter to skip):")
    print("Format: Player,Stat,Line,Direction")
    print("Example: Patrick Mahomes,Pass Yards,275.5,OVER")
    print("(Type 'done' when finished)\n")
    
    props = []
    while True:
        entry = input("Enter prop: ").strip()
        if entry.lower() in ['done', 'exit', '']:
            break
        
        try:
            parts = [p.strip() for p in entry.split(',')]
            if len(parts) != 4:
                print("  [ERROR] Format: Player,Stat,Line,Direction")
                continue
            
            player, stat, line, direction = parts
            props.append({
                "player": player,
                "stat": stat,
                "line": float(line),
                "direction": direction.upper()
            })
            print(f"  [OK] Added: {player} {stat} {direction.upper()} {line}")
        
        except Exception as e:
            print(f"  [ERROR] Invalid format: {e}")
            continue
    
    if not props:
        print("\n[INFO] No props entered. Use nfl_menu.py for full analysis.")
        print("\nWorkflow:")
        print("  1. .venv\\Scripts\\python.exe nfl_menu.py")
        print("  2. Select [1] INGEST NFL SLATE")
        print("  3. Paste Underdog lines")
        print("  4. Select [2] ANALYZE NFL SLATE")
        print("  5. Review probabilities and tiers")
        return
    
    # Quick analysis using analyzer
    print("\n" + "=" * 80)
    print("ANALYZING PROPS...")
    print("=" * 80 + "\n")
    
    try:
        from analyze_nfl_props import load_nfl_role_mapping, analyze_nfl_slate, format_nfl_report
        
        role_mapping = load_nfl_role_mapping()
        results = analyze_nfl_slate(props, role_mapping)
        
        # Display results
        for result in results:
            player = result.get('player', 'Unknown')
            stat = result.get('stat', '')
            line = result.get('line', 0)
            direction = result.get('direction', '')
            prob = result.get('probability', 0)
            tier = result.get('tier', 'NO_PLAY')
            decision = result.get('decision', 'PASS')
            
            status_emoji = {
                'SLAM': '🔥',
                'STRONG': '💪',
                'LEAN': '📊',
                'NO_PLAY': '❌'
            }.get(tier, '❓')
            
            print(f"{status_emoji} {player} — {stat} {direction} {line}")
            print(f"   Probability: {prob:.1%}")
            print(f"   Tier: {tier}")
            print(f"   Decision: {decision}")
            
            if result.get('reason'):
                print(f"   Note: {result['reason']}")
            
            print()
        
        # Summary
        play_picks = [r for r in results if r.get('tier') in ['SLAM', 'STRONG']]
        lean_picks = [r for r in results if r.get('tier') == 'LEAN']
        
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total Props Analyzed: {len(results)}")
        print(f"Recommended Bets (SLAM/STRONG): {len(play_picks)}")
        print(f"Marginal Bets (LEAN): {len(lean_picks)}")
        print(f"No Play: {len(results) - len(play_picks) - len(lean_picks)}")
        
        if len(play_picks) > 0:
            print(f"\n⚠️ CAUTION: System has 33% historical win rate on NFL")
            print(f"   Reduce stake sizes by 50-75% compared to NBA bets")
        
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        print("\nFallback: Use nfl_menu.py for full analysis")
    
    print("\n" + "=" * 80)
    print(f"Analysis Complete - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    quick_analyze_superbowl()
