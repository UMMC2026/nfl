"""
QUICK TENNIS PROPS ANALYZER
============================
1. Copy Underdog props to clipboard
2. Run this script
3. Paste when prompted
4. Press Ctrl+Z then Enter (Windows) to finish
5. Get your SLAM/STRONG/LEAN picks!
"""
import sys
sys.path.insert(0, 'tennis')

from tennis_props_pipeline import TennisPropsAnalysisPipeline
from generate_tennis_cheatsheet import generate_tennis_cheatsheet, save_cheatsheet

print("\n" + "=" * 90)
print("🎾 TENNIS PROPS - MONTE CARLO ANALYSIS (NBA-STYLE)")
print("=" * 90)
print("\nPaste your Underdog tennis props below.")
print("When done, press Ctrl+Z then Enter (Windows) or Ctrl+D (Mac/Linux)\n")

# Read from stdin
lines = []
try:
    while True:
        line = input()
        lines.append(line)
except EOFError:
    pass

paste = '\n'.join(lines)

if not paste.strip():
    print("\n❌ No props pasted!")
    sys.exit(1)

print("\n🔄 Running Monte Carlo analysis...")
print("   • Parsing props")
print("   • Fetching player stats")
print("   • Running 10,000 simulations per prop")
print("   • Detecting edges & assigning tiers\n")

pipeline = TennisPropsAnalysisPipeline()
results = pipeline.run_full_pipeline(paste)

if results['edges']:
    cheatsheet = generate_tennis_cheatsheet(results['edges'])
    print(cheatsheet)
    
    filepath = save_cheatsheet(results['edges'])
    
    tier_counts = results['tier_counts']
    print(f"\n📊 ANALYSIS SUMMARY:")
    print(f"   Total props analyzed: {len(results['raw_props'])}")
    print(f"   Unique props: {len(results['unique_props'])}")
    print(f"   Playable edges: {len(results['edges'])}")
    print(f"   SLAM: {tier_counts.get('SLAM', 0)} | STRONG: {tier_counts.get('STRONG', 0)} | LEAN: {tier_counts.get('LEAN', 0)}")
    print(f"\n✓ Saved to: {filepath}")
else:
    print("\n⚠️  No playable edges found (all props < 55% probability)")
    print("   Try different props or check player stats availability")

print("\n" + "=" * 90)
