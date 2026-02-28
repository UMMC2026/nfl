"""Test Monte Carlo with real Underdog props"""
import sys
sys.path.insert(0, 'tennis')

from tennis_props_pipeline import TennisPropsAnalysisPipeline
from generate_tennis_cheatsheet import generate_tennis_cheatsheet, save_cheatsheet

# Read props from file
with open('test_tennis_props.txt', 'r', encoding='utf-8') as f:
    paste = f.read()

print('🔄 Running Monte Carlo analysis...')
print('   • Parsing props')
print('   • Fetching player stats')
print('   • Running 10,000 simulations per prop')
print('   • Detecting edges & assigning tiers\n')

pipeline = TennisPropsAnalysisPipeline()
results = pipeline.run_full_pipeline(paste)

if results['edges']:
    cheatsheet = generate_tennis_cheatsheet(results['edges'])
    print(cheatsheet)
    
    # Save
    filepath = save_cheatsheet(results['edges'])
    
    tier_counts = results['tier_counts']
    print(f'\n📊 ANALYSIS SUMMARY:')
    print(f'   Total props analyzed: {len(results["raw_props"])}')
    print(f'   Unique props: {len(results["unique_props"])}')
    print(f'   Playable edges: {len(results["edges"])}')
    print(f'   SLAM: {tier_counts.get("SLAM", 0)} | STRONG: {tier_counts.get("STRONG", 0)} | LEAN: {tier_counts.get("LEAN", 0)}')
    print(f'\n✓ Saved to: {filepath}')
else:
    print('⚠️ No edges found')
