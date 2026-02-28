"""Regenerate soccer report with avoid_reason tags"""
import json
import os
from soccer.soccer_slate_analyzer import analyze_scraped_props_structured

# Load Feb 15 scraped props
with open('soccer/inputs/scraped_props_20260215_103047.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

props = data.get('props', [])
print(f"[INFO] Loaded {len(props)} scraped props from Feb 15")

# Analyze with show_no_play=True to see AVOID section with tags
report, analyzed = analyze_scraped_props_structured(props, show_no_play=True)

# Display report
print(report)

# Save to outputs
output_path = 'soccer/outputs/soccer_scraped_report_UPDATED.txt'
os.makedirs('soccer/outputs', exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"\n{'='*70}")
print(f"✅ REPORT SAVED TO: {output_path}")
print(f"{'='*70}")

# Show avoid_reason stats
avoid_picks = [a for a in analyzed if a.tier == 'AVOID']
print(f"\n[AVOID BREAKDOWN] {len(avoid_picks)} props")
reason_counts = {}
for pick in avoid_picks:
    reason_counts[pick.avoid_reason] = reason_counts.get(pick.avoid_reason, 0) + 1

for reason, count in reason_counts.items():
    print(f"  {reason}: {count}")
