"""
Quick test of risk-first system on Wednesday/Thursday props
Compares OLD system (probability-first) vs NEW system (risk-first)
"""

import json
from risk_first_analyzer import analyze_slate, print_summary

# Load Wednesday props
with open("nba_full_wednesday_comprehensive.json") as f:
    wed_data = json.load(f)
    wed_props = wed_data["plays"]

# Load Thursday props
with open("nba_thursday_mem_orl.json") as f:
    thu_data = json.load(f)
    thu_props = thu_data["plays"]

# Combine all props
all_props = wed_props + thu_props

print(f"\n{'='*70}")
print(f"RISK-FIRST SYSTEM TEST")
print(f"Analyzing {len(all_props)} props from Wednesday + Thursday")
print(f"{'='*70}\n")

# Run analysis
analysis = analyze_slate(all_props, verbose=False)

# Print summary
print_summary(analysis)

# Save detailed results
output_file = "outputs/RISK_FIRST_ANALYSIS_20260115.json"
with open(output_file, "w") as f:
    json.dump(analysis, f, indent=2)

print(f"✅ Detailed results saved to: {output_file}\n")

# Key comparisons
print(f"\n{'='*70}")
print("SYSTEM COMPARISON")
print(f"{'='*70}")
print(f"OLD SYSTEM (Probability-First):")
print(f"  Wednesday: 40 qualified picks (≥65%)")
print(f"  Thursday:  29 qualified picks (≥65%)")
print(f"  TOTAL:     69 picks")
print(f"\nNEW SYSTEM (Risk-First):")
print(f"  PLAY/SLAM: {analysis['play']} picks (≥80% effective)")
print(f"  STRONG:    {analysis.get('strong', 0)} picks (65-79% effective)")
print(f"  LEAN:      {analysis['lean']} picks (55-64% effective)")
print(f"  BLOCKED:   {analysis['blocked']} picks (failed gates)")
print(f"  NO PLAY:   {analysis['no_play']} picks (<55% effective)")
print(f"\nREDUCTION: {69 - analysis['play']} fewer PLAY picks")
print(f"EXPECTED:  Higher hit rate, lower fragility")
print(f"{'='*70}\n")
