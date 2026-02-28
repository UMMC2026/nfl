#!/usr/bin/env python3
"""
GENERATE NARRATIVE REPORT - FUOOM DARK MATTER
Main entry point for generating narrative reports

Usage:
    python generate_narrative_report.py                                    # Auto-find latest JSON
    python generate_narrative_report.py outputs/SLATE_RISK_FIRST.json     # Specific file
    python generate_narrative_report.py --help                            # Show help

Output:
    - Saves to outputs/[SLATE]_NARRATIVE_[DATE].txt
    - Also saves to outputs/LATEST_NARRATIVE_REPORT.txt
"""

import sys
import os
import json
import glob
from datetime import datetime
from pathlib import Path

# Fix Windows terminal encoding for emoji
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Import the integration module
from fuoom_narrative_integration import generate_fuoom_narrative_report


def find_latest_risk_first_json(outputs_dir="outputs"):
    """
    Find the most recent RISK_FIRST JSON file in outputs directory
    """
    pattern = f"{outputs_dir}/*RISK_FIRST*.json"
    files = glob.glob(pattern)
    
    if not files:
        print(f"❌ No RISK_FIRST JSON files found in {outputs_dir}/")
        print(f"   Pattern searched: {pattern}")
        return None
    
    # Sort by modification time (most recent first)
    files.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
    
    print(f"📂 Found {len(files)} RISK_FIRST files")
    print(f"   Latest: {files[0]}")
    
    return files[0]


def extract_slate_name(filepath):
    """
    Extract slate name from filename
    e.g., "FRYDAY8DAT_RISK_FIRST_20260130_FROM_UD.json" -> "FRYDAY8DAT"
    """
    filename = Path(filepath).stem
    
    # Remove common suffixes
    for suffix in ['_RISK_FIRST', '_FROM_UD', '_FROM_UNDERDOG']:
        if suffix in filename:
            filename = filename.split(suffix)[0]
    
    # Remove date pattern (8 digits)
    import re
    filename = re.sub(r'_\d{8}', '', filename)
    
    return filename if filename else "NBA PICKS"


def main():
    """
    Main entry point
    """
    print("=" * 80)
    print("🎯 FUOOM NARRATIVE REPORT GENERATOR")
    print("=" * 80)
    print()
    
    # Check for help flag
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return
    
    # Determine input file
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        input_file = sys.argv[1]
        if not Path(input_file).exists():
            print(f"❌ File not found: {input_file}")
            return
    else:
        # Auto-find latest
        input_file = find_latest_risk_first_json()
        if not input_file:
            print("\n💡 Usage: python generate_narrative_report.py <path_to_json>")
            return
    
    print(f"\n📄 Input file: {input_file}")
    
    # Load and count picks
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        picks = data.get('results', data.get('picks', data.get('entries', [])))
    else:
        picks = data
    
    print(f"📊 Total picks in file: {len(picks)}")
    
    # Extract slate name for output
    slate_name = extract_slate_name(input_file)
    print(f"🏷️  Slate name: {slate_name}")
    
    # Generate narrative report
    print("\n⏳ Generating narrative report...")
    report = generate_fuoom_narrative_report(picks, slate_name)
    
    # Create output directory if needed
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    
    # Generate output filenames
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = outputs_dir / f"{slate_name}_NARRATIVE_{date_str}.txt"
    latest_file = outputs_dir / "LATEST_NARRATIVE_REPORT.txt"
    
    # Save report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    with open(latest_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # Helper to get confidence from various field names
    def get_conf(p):
        return (
            p.get('effective_confidence') or 
            p.get('status_confidence') or
            p.get('model_confidence') or 
            p.get('confidence') or 
            p.get('eff%') or 
            p.get('prob', 0)
        )
    
    # Count tiers for summary
    actionable = [p for p in picks if get_conf(p) >= 55]
    elite = len([p for p in actionable if get_conf(p) >= 80])
    strong = len([p for p in actionable if 65 <= get_conf(p) < 80])
    lean = len([p for p in actionable if 55 <= get_conf(p) < 65])
    
    print()
    print("=" * 80)
    print("✅ NARRATIVE REPORT GENERATED!")
    print("=" * 80)
    print()
    print(f"📁 Saved to: {output_file}")
    print(f"📁 Also saved: {latest_file}")
    print()
    print("📊 SUMMARY:")
    print(f"   💎 ELITE picks (80%+):    {elite}")
    print(f"   ✨ STRONG picks (65-79%): {strong}")
    print(f"   📈 LEAN picks (55-64%):   {lean}")
    print(f"   ─────────────────────────")
    print(f"   📋 Total actionable:      {len(actionable)}")
    print()
    print("🎯 Your subscribers are going to love this!")
    print("=" * 80)


if __name__ == "__main__":
    main()
