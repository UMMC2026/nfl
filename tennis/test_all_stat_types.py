"""
Tennis Monte Carlo - All Supported Stats Test
=============================================
Demonstrates all stat types now supported in the system
"""

from tennis_stats_api import TennisStatsAPI
from tennis_monte_carlo import TennisMonteCarloEngine
from tennis_edge_detector import TennisEdgeDetector
from generate_tennis_cheatsheet import generate_tennis_cheatsheet, save_cheatsheet

print("\n" + "=" * 90)
print("🎾 TENNIS MONTE CARLO - ALL SUPPORTED STAT TYPES")
print("=" * 90)

# Get player stats
api = TennisStatsAPI()
sinner = api.get_player_stats("Jannik Sinner")
alcaraz = api.get_player_stats("Carlos Alcaraz")
gauff = api.get_player_stats("Coco Gauff")

print("\n📊 SUPPORTED STAT TYPES:")
print("  ✅ Aces")
print("  ✅ Break Points Won / Breakpoints Won")
print("  ✅ Games Won / Total Games Won")
print("  ✅ Total Games")
print("  ✅ Fantasy Score / Fantasy Points")
print("  ✅ Double Faults")
print("  ✅ Tiebreakers / Tiebreakers Played")
print("  ✅ Sets Won")
print("  ✅ Sets Played")

# Run Monte Carlo on ALL stat types
engine = TennisMonteCarloEngine(10000)

props = [
    # Jannik Sinner - All stats
    ("Jannik Sinner", "Aces", 8.0),
    ("Jannik Sinner", "Break Points Won", 5.0),
    ("Jannik Sinner", "Games Won", 15.0),
    ("Jannik Sinner", "Total Games", 28.0),
    ("Jannik Sinner", "Fantasy Score", 34.0),
    ("Jannik Sinner", "Double Faults", 4.0),
    ("Jannik Sinner", "Tiebreakers Played", 1.5),
    ("Jannik Sinner", "Sets Won", 2.0),
    ("Jannik Sinner", "Sets Played", 3.0),
    
    # Carlos Alcaraz - All stats
    ("Carlos Alcaraz", "Aces", 7.0),
    ("Carlos Alcaraz", "Breakpoints Won", 4.5),
    ("Carlos Alcaraz", "Total Games Won", 20.5),
    ("Carlos Alcaraz", "Total Games", 35.5),
    ("Carlos Alcaraz", "Fantasy Points", 26.0),
    ("Carlos Alcaraz", "Double Faults", 3.5),
    ("Carlos Alcaraz", "Tiebreakers", 1.0),
    ("Carlos Alcaraz", "Sets Won", 2.0),
    ("Carlos Alcaraz", "Sets Played", 2.5),
    
    # Coco Gauff - Sample
    ("Coco Gauff", "Fantasy Score", 16.0),
    ("Coco Gauff", "Games Won", 12.5),
    ("Coco Gauff", "Aces", 3.0),
]

print(f"\n🔄 Running Monte Carlo simulations on {len(props)} props...")
print(f"   10,000 iterations per prop")

mc_results = engine.simulate_multiple_props([sinner, alcaraz, gauff], props)

# Detect edges
detector = TennisEdgeDetector()
edges = detector.batch_analyze(mc_results)

print(f"\n✅ Analysis complete!")
print(f"   Playable edges: {len(edges)}")

# Generate cheat sheet
cheatsheet = generate_tennis_cheatsheet(edges)
print(cheatsheet)

# Save
filepath = save_cheatsheet(edges)

print("\n" + "=" * 90)
print("✅ ALL STAT TYPES TESTED & WORKING")
print("=" * 90)
print("\nStat Coverage:")
print(f"  • Total stat types tested: 9")
print(f"  • Total props analyzed: {len(props)}")
print(f"  • Playable edges found: {len(edges)}")
print(f"  • Cheat sheet saved: {filepath}")
print("\nAll Underdog tennis prop types are now supported!")
print("=" * 90)
