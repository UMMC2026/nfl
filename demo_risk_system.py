"""
Demo: Risk-First System with Custom Props
Shows how to use the system in your workflow
"""

from risk_first_analyzer import analyze_slate, print_summary

# Your custom props list
props = [
    # PLAY picks (should pass all gates)
    {"player": "Franz Wagner", "team": "ORL", "opponent": "MEM", 
     "stat": "points", "line": 15.5, "direction": "higher"},
    
    {"player": "Tyrese Maxey", "team": "PHI", "opponent": "CLE",
     "stat": "assists", "line": 4.5, "direction": "higher"},
    
    {"player": "Desmond Bane", "team": "MEM", "opponent": "ORL",
     "stat": "3pm", "line": 1.5, "direction": "higher"},
    
    # BLOCKED picks (will fail gates)
    {"player": "Joel Embiid", "team": "PHI", "opponent": "CLE",
     "stat": "assists", "line": 3.5, "direction": "higher"},  # BANNED
    
    {"player": "Tyrese Maxey", "team": "PHI", "opponent": "CLE",
     "stat": "pra", "line": 31.5, "direction": "higher"},  # BANNED + Composite
    
    {"player": "Nikola Vucevic", "team": "CHI", "opponent": "UTA",
     "stat": "assists", "line": 3.5, "direction": "higher"},  # BIG role forbids assists
    
    {"player": "Franz Wagner", "team": "ORL", "opponent": "MEM",
     "stat": "pra", "line": 23.5, "direction": "higher"},  # Composite block
]

print("\n" + "="*70)
print("CUSTOM DEMO: Risk-First System")
print("="*70)
print(f"Testing {len(props)} props\n")

# Run analysis (verbose=True to see gate execution)
results = analyze_slate(props, verbose=True)

# Print summary
print_summary(results)

# Show only PLAY picks
play_picks = [r for r in results["results"] if r["decision"] == "PLAY"]
print(f"\n{'='*70}")
print(f"✅ READY TO PLAY: {len(play_picks)} picks")
print(f"{'='*70}\n")

for pick in play_picks:
    print(f"✓ {pick['player']} - {pick['stat'].upper()} {pick['direction'].upper()} {pick['line']}")
    print(f"  Confidence: {pick['effective_confidence']:.1f}% (model: {pick['model_confidence']:.1f}%)\n")
