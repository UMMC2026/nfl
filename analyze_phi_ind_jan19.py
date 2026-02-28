"""
PHI vs IND - January 19, 2026
Quick Analysis using Risk-First Analyzer
"""
import json
from datetime import datetime
from pathlib import Path
from risk_first_analyzer import analyze_slate, print_summary
from ai_commentary import generate_full_report

def main():
    # Load the slate
    slate_file = "phi_ind_slate_20260119.json"
    
    with open(slate_file, "r") as f:
        props = json.load(f)
    
    print("=" * 70)
    print("PHI vs IND - January 19, 2026")
    print("RISK-FIRST ANALYSIS")
    print("=" * 70)
    print(f"Total props: {len(props)}")
    print("=" * 70)
    print()
    
    # Analyze with risk-first analyzer
    results = analyze_slate(props, game_context={})
    print_summary(results)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON output
    out_json = f"outputs/PHI_IND_ANALYSIS_{timestamp}.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results: {out_json}")
    
    # Generate AI commentary
    print("\n" + "=" * 70)
    print("GENERATING AI COMMENTARY...")
    print("=" * 70)
    
    game_context = {
        "matchup": "PHI vs IND",
        "time": "55m 35s",
        "notes": "Trending slate with 8.7K entries"
    }
    
    ai_report = generate_full_report(results, game_context=game_context)
    
    out_txt = f"outputs/PHI_IND_AI_COMMENTARY_{timestamp}.txt"
    with open(out_txt, "w") as f:
        f.write(ai_report)
    
    print(f"\nAI Commentary: {out_txt}")
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
