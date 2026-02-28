"""
Save Final Picks - Extract PLAY/LEAN picks to simple comparison file
=====================================================================
Creates picks/{SLATE}_{DATE}_FINAL.json for easy postgame comparison.

Usage:
    python save_final_picks.py                    # Latest analysis
    python save_final_picks.py --file results.json
    python save_final_picks.py --label CLE_PHI
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, date

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
PICKS_DIR = PROJECT_ROOT / "picks"
PICKS_DIR.mkdir(exist_ok=True)


def extract_final_picks(results_file: Path) -> dict:
    """Extract PLAY and LEAN picks from analysis results."""
    data = json.loads(results_file.read_text())
    
    picks = []
    for r in data.get("results", []):
        decision = r.get("decision", r.get("status", ""))
        if decision in ("PLAY", "LEAN"):
            picks.append({
                "player": r.get("player"),
                "team": r.get("team"),
                "stat": r.get("stat"),
                "line": r.get("line"),
                "direction": r.get("direction"),
                "decision": decision,
                "probability": round(r.get("probability", r.get("effective_confidence", 0)) * 100 
                                    if r.get("probability", r.get("effective_confidence", 0)) <= 1 
                                    else r.get("probability", r.get("effective_confidence", 0)), 1),
            })
    
    # Sort by decision (PLAY first) then probability
    picks.sort(key=lambda x: (0 if x["decision"] == "PLAY" else 1, -x["probability"]))
    
    # Extract label from filename
    label = results_file.stem.split("_RISK_FIRST")[0]
    
    return {
        "date": date.today().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "slate": label,
        "source_file": results_file.name,
        "summary": {
            "play_count": sum(1 for p in picks if p["decision"] == "PLAY"),
            "lean_count": sum(1 for p in picks if p["decision"] == "LEAN"),
            "total": len(picks),
        },
        "picks": picks,
    }


def save_final_picks(results_file: Path = None, label: str = None) -> Path:
    """Save final picks to picks/ directory."""
    
    # Find results file
    if results_file is None:
        pattern = f"*{label}*_RISK_FIRST_*.json" if label else "*_RISK_FIRST_*.json"
        results_files = sorted(OUTPUTS_DIR.glob(pattern), 
                              key=lambda p: p.stat().st_mtime, reverse=True)
        if not results_files:
            print(f"No analysis results found matching: {pattern}")
            return None
        results_file = results_files[0]
    
    print(f"Source: {results_file.name}")
    
    # Extract picks
    final = extract_final_picks(results_file)
    
    if not final["picks"]:
        print("No PLAY or LEAN picks found!")
        return None
    
    # Save to picks directory
    output_name = f"{final['slate']}_{date.today().strftime('%Y%m%d')}_FINAL.json"
    output_path = PICKS_DIR / output_name
    output_path.write_text(json.dumps(final, indent=2))
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"  FINAL PICKS SAVED: {output_name}")
    print(f"{'='*60}")
    print(f"  PLAY: {final['summary']['play_count']} | LEAN: {final['summary']['lean_count']}")
    print(f"{'='*60}")
    
    for p in final["picks"]:
        marker = "★" if p["decision"] == "PLAY" else "○"
        print(f"  {marker} {p['player']} {p['stat']} {p['direction']} {p['line']} ({p['probability']}%)")
    
    print(f"\nSaved to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Save final picks for comparison")
    parser.add_argument("--file", type=str, help="Specific results JSON file")
    parser.add_argument("--label", type=str, help="Slate label to find (e.g., CLE_PHI)")
    args = parser.parse_args()
    
    results_file = Path(args.file) if args.file else None
    save_final_picks(results_file, args.label)


if __name__ == "__main__":
    main()
