"""
MEM @ ORL Full Slate Analysis - Risk-First System
1:00PM CST Thursday Jan 16, 2026
"""

import json
from risk_first_analyzer import analyze_slate, print_summary
from ai_commentary import generate_full_report

# Load game context
with open("game_context.json") as f:
    game_context = json.load(f)

# Load full slate
with open("mem_orl_full_slate.json") as f:
    slate_data = json.load(f)
    props = slate_data["plays"]

print("\n" + "="*70)
print("MEM @ ORL - 1:00PM CST THURSDAY")
print("RISK-FIRST ANALYSIS")
print("="*70)
print(f"Total props in slate: {len(props)}")
print(f"{'='*70}\n")

# Run analysis
results = analyze_slate(props, verbose=False)

# Print summary
print_summary(results)

# Save detailed results
output_file = "outputs/MEM_ORL_RISK_FIRST_20260115.json"
with open(output_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Full results saved to: {output_file}")

# Export PLAY picks only
play_picks = [r for r in results["results"] if r["decision"] == "PLAY"]

if play_picks:
    # Sort by edge (z_score)
    play_picks.sort(key=lambda x: abs(x.get("z_score", 0)), reverse=True)
    
    print(f"\n{'='*70}")
    print(f"📋 PLAY PICKS EXPORT - SORTED BY EDGE")
    print(f"{'='*70}\n")
    
    for i, pick in enumerate(play_picks, 1):
        edge_str = f"{pick['edge']:+.1f}" if pick['edge'] >= 0 else f"{pick['edge']:.1f}"
        z_str = f"{pick['z_score']:+.2f}σ"
        
        edge_emoji = {
            "ELITE": "🔥",
            "STRONG": "💎", 
            "MODERATE": "✨",
            "THIN": "⚪"
        }.get(pick['edge_quality'], "")
        
        print(f"{i}. {pick['player']}")
        print(f"   {pick['stat'].upper()} {pick['direction'].upper()} {pick['line']}")
        print(f"   Edge: {edge_str} ({z_str}) {edge_emoji} {pick['edge_quality']}")
        print(f"   Confidence: {pick['effective_confidence']:.1f}%")
        print(f"   (μ={pick['mu']:.1f}, σ={pick['sigma']:.1f})")
        print()

# Show gate effectiveness
print(f"\n{'='*70}")
print("GATE EFFECTIVENESS")
print(f"{'='*70}")
print(f"Total props analyzed:     {results['total_props']}")
print(f"Skipped (no data):        {results['skip']} ({results['skip']/results['total_props']*100:.1f}%)")
print(f"Blocked at gates:         {results['blocked']} ({results['blocked']/(results['total_props']-results['skip'])*100:.1f}% of analyzed)")
print(f"Failed confidence check:  {results['no_play']}")
print(f"LEAN (65-69%):           {results['lean']}")
print(f"PLAY (≥70%):             {results['play']}")
print(f"\n➜ {results['blocked']} props killed BEFORE probability calculation")
print(f"➜ System efficiency: {(results['blocked']/(results['total_props']-results['skip'])*100):.1f}% waste prevented")
print(f"{'='*70}\n")

# Generate AI-powered analysis report
print("\n🤖 Generating AI sports analysis & commentary...")
ai_report = generate_full_report(results, game_context)
print(ai_report)

# Save AI report
ai_output_file = "outputs/MEM_ORL_AI_REPORT_20260115.txt"
with open(ai_output_file, "w", encoding="utf-8") as f:
    f.write(ai_report)

print(f"\n✅ AI analysis report saved to: {ai_output_file}\n")
