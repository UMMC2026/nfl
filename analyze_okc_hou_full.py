"""
OKC @ HOU - 6:30PM CST THURSDAY
RISK-FIRST ANALYSIS WITH AI COMMENTARY
"""

import json
from risk_first_analyzer import analyze_slate, print_summary
from ai_commentary import generate_full_report

# Load props
with open("okc_hou_props.json") as f:
    props = json.load(f)

# Load game context
with open("game_context_okc_hou.json") as f:
    game_context = json.load(f)

print("="*70)
print("OKC @ HOU - 6:30PM CST THURSDAY")
print("RISK-FIRST ANALYSIS")
print("="*70)
print(f"Total props in slate: {len(props)}")
print("="*70)
print("\n")

# Run full risk-first analysis
results = analyze_slate(props, game_context=game_context)

# Print statistical summary
print_summary(results)

# Save statistical results
output_file = "outputs/OKC_HOU_RISK_FIRST_20260115.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"\nFull results saved to: {output_file}\n")

# Generate AI sports analysis report
print("Generating AI sports analysis & commentary...\n")

ai_report = generate_full_report(results, game_context)

# Do not print full AI report to console (may contain Unicode emojis and cause encoding issues on Windows).
# The report is always written to UTF-8 output file below.

# Save AI report
ai_output_file = "outputs/OKC_HOU_AI_REPORT_20260115.txt"
with open(ai_output_file, "w", encoding="utf-8") as f:
    f.write(ai_report)

print(f"\nAI analysis report saved to: {ai_output_file}")
