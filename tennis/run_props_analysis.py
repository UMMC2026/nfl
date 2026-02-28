"""
Tennis Props Analysis - Standalone Runner
Run Monte Carlo analysis on pasted Underdog tennis props
"""
import sys
from pathlib import Path

# Setup paths
TENNIS_DIR = Path(__file__).parent
PROJECT_ROOT = TENNIS_DIR.parent
sys.path.insert(0, str(TENNIS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from tennis_props_pipeline import TennisPropsAnalysisPipeline
from generate_tennis_cheatsheet import generate_tennis_cheatsheet, save_cheatsheet

def main():
    # Read from file
    input_file = TENNIS_DIR / "inputs" / "underdog_props_jan29.txt"
    
    if not input_file.exists():
        print(f"✗ Input file not found: {input_file}")
        return
    
    paste = input_file.read_text()
    
    print("=" * 90)
    print("🎾 TENNIS PROPS - MONTE CARLO ANALYSIS")
    print("=" * 90)
    print(f"\n📥 Reading from: {input_file}")
    print("\n🔄 Running Monte Carlo analysis...")
    print("   • Parsing props")
    print("   • Fetching player stats")
    print("   • Running 2,000 simulations per prop")
    print("   • Detecting edges & assigning tiers\n")
    
    pipeline = TennisPropsAnalysisPipeline()
    
    try:
        results = pipeline.run_full_pipeline(paste)
        
        if results['edges']:
            # Generate and display cheat sheet
            cheatsheet = generate_tennis_cheatsheet(results['edges'])
            print(cheatsheet)
            
            # Save to file
            filepath = save_cheatsheet(results['edges'])
            print(f"\n✓ Monte Carlo cheat sheet saved: {filepath}")
            
            # Summary
            tier_counts = results['tier_counts']
            print(f"\n📊 ANALYSIS SUMMARY:")
            print(f"   Total props analyzed: {len(results['raw_props'])}")
            print(f"   Unique props: {len(results['unique_props'])}")
            print(f"   Playable edges: {len(results['edges'])}")
            print(f"   SLAM: {tier_counts.get('SLAM', 0)} | STRONG: {tier_counts.get('STRONG', 0)} | LEAN: {tier_counts.get('LEAN', 0)}")
        else:
            print("\n⚠️  No playable edges found (all props < 55% probability)")
            print("   Try different props or check player stats availability")
    
    except Exception as e:
        print(f"\n✗ Error running Monte Carlo analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
