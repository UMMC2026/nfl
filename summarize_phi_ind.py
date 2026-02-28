"""
PHI vs IND Analysis Summary - January 19, 2026
Generated from outputs/PHI_IND_ANALYSIS_20260119_170756.json
"""
import json
from pathlib import Path

# Load results
with open("outputs/PHI_IND_ANALYSIS_20260119_170756.json", "r") as f:
    data = json.load(f)

results = data["results"]

print("=" * 80)
print("PHI vs IND - COMPLETE ANALYSIS SUMMARY")
print("Trending (8.7K entries) - Game starts in 55m 35s")
print("=" * 80)
print()

# All props ranked by confidence
print("ALL PROPS - RANKED BY CONFIDENCE:")
print("-" * 80)
print(f"{'#':<3} {'Player':<20} {'Stat':<8} {'Line':<6} {'Dir':<6} {'P%':<7} {'Tier':<10} {'Notes':<20}")
print("-" * 80)

# Sort by effective confidence
sorted_results = sorted(results, key=lambda x: x.get('effective_confidence', 0), reverse=True)

for i, r in enumerate(sorted_results, 1):
    player = r.get('player', 'Unknown')[:18]
    stat = r.get('stat', '?')[:7]
    line = r.get('line', 0)
    direction = "OVER" if r.get('direction') == 'higher' else "UNDER"
    conf = r.get('effective_confidence', 0)
    tier = r.get('decision', 'SKIP')
    
    # Build notes
    notes = []
    if r.get('status') == 'SKIP' or not r.get('mu'):
        notes.append("NO DATA")
    elif r.get('gate_details'):
        warnings = [g for g in r['gate_details'] if g.get('severity') == 'WARNING']
        if warnings:
            notes.append(f"{len(warnings)} warn")
    
    if r.get('mu'):
        mu = r['mu']
        edge = r.get('edge', 0)
        notes.append(f"µ={mu:.1f}")
        notes.append(f"edge={edge:+.1f}")
    
    notes_str = " | ".join(notes[:2]) if notes else ""
    
    print(f"{i:<3} {player:<20} {stat:<8} {line:<6.1f} {direction:<6} {conf:<6.1f}% {tier:<10} {notes_str}")

print()
print("=" * 80)
print("BREAKDOWN BY TIER:")
print("=" * 80)

# Count by tier
tier_counts = {}
for r in results:
    tier = r.get('decision', 'SKIP')
    tier_counts[tier] = tier_counts.get(tier, 0) + 1

for tier, count in sorted(tier_counts.items()):
    print(f"{tier:<15} : {count:>2} props")

print()
print("=" * 80)
print("TOP PICKS (NO_PLAY threshold = 25%):")
print("=" * 80)

playable = [r for r in sorted_results if r.get('effective_confidence', 0) >= 25]

if playable:
    for i, r in enumerate(playable, 1):
        print(f"\n{i}. {r['player']} ({r['team']})")
        print(f"   {r['stat'].upper()} {'OVER' if r['direction'] == 'higher' else 'UNDER'} {r['line']}")
        print(f"   Confidence: {r.get('effective_confidence', 0):.1f}%")
        print(f"   Mean = {r.get('mu', 0):.1f}, StdDev = {r.get('sigma', 1):.1f}")
        print(f"   Edge: {r.get('edge', 0):+.1f}")
        if r.get('context_warnings'):
            print(f"   WARNING: {', '.join(r['context_warnings'])}")
else:
    print("\n❌ NO PROPS MEET PLAYABLE THRESHOLD")
    print("\nHighest confidence picks (all below threshold):")
    for i, r in enumerate(sorted_results[:5], 1):
        conf = r.get('effective_confidence', 0)
        print(f"  {i}. {r['player']} - {r['stat']} {r['direction'][:4].upper()} {r['line']} ({conf:.1f}%)")

print()
print("=" * 80)
print("SYSTEM NOTES:")
print("=" * 80)
print(f"* Total props analyzed: {data['total_props']}")
print(f"* Props skipped (no data): {data['skip']}")
print(f"* Blocked by risk gates: {data['blocked']}")
print("* Many rotation players missing recent data")
print("* Bench/role player lines are high variance")
print("* Consider waiting for lineup confirmations")
print()
print("WARNING: RECOMMENDATION: SKIP THIS SLATE")
print("   - Too many unknown/bench players")
print("   - Insufficient data for confident picks")
print("   - High variance game environment")
print()
print("=" * 80)
