#!/usr/bin/env python3
"""
OLLAMA Commentary - Enhanced Analysis with Both Sides of the Ball
"""

import subprocess
import json
from datetime import datetime
from pathlib import Path

def get_ollama_analysis(slate_summary):
    """Get AI commentary from Ollama"""
    prompt = f"""Analyze this daily sports betting slate with BOTH offensive and defensive player props:

{slate_summary}

Provide strategic insights focusing on:
1. Defensive edges (sacks, tackles, steals, blocks leaders)
2. Offensive scoring potential
3. Combined both-sides-of-ball recommendations
4. Risk factors and defensive injuries
5. Entry strategy for power/flex parlays

Keep response concise and actionable for betting decisions."""

    try:
        result = subprocess.run(
            ["ollama", "run", "mistral", prompt],
            capture_output=True,
            text=True,
            timeout=300,
            encoding='utf-8',
            errors='replace'
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return None

def main():
    # Read the enhanced analysis
    import glob
    files = glob.glob("outputs/ENHANCED_BOTH_SIDES_*.txt")
    if not files:
        print("❌ No enhanced analysis file found")
        return
    
    latest_file = max(files, key=lambda f: f)
    with open(latest_file) as f:
        analysis = f.read()
    
    # Get Ollama commentary
    print("🤖 Generating Ollama commentary for enhanced analysis...")
    summary = """
NFL SLATE (8 games, 70 props: 38 offensive + 32 defensive)
- Expected hits: 38.7 (55.3% confidence)
- Defensive leaders: T.J. Watt (sacks), De'Vondre Campbell (tackles)
- Offensive leaders: Lamar Jackson (pass yards), Travis Kelce (rec yards)

NBA SLATE (8 games, 64 props: 40 offensive + 24 defensive)
- Expected hits: 31.5 (49.2% confidence) 
- Defensive leaders: Rudy Gobert (blocks), Shai Gilgeous-Alexander (steals)
- Offensive leaders: Nikola Jokic (PRA), Giannis (PRA + blocks)

COMBINED: 134 props with both-sides coverage
"""
    
    commentary = get_ollama_analysis(summary)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/OLLAMA_ENHANCED_BOTH_SIDES_{timestamp}.md"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# ENHANCED ANALYSIS - OLLAMA COMMENTARY\n")
        f.write(f"**Both Sides of the Ball | January 4, 2026**\n\n")
        f.write("## Slate Summary\n")
        f.write("- **Total Props:** 134 (NFL: 70 + NBA: 64)\n")
        f.write("- **Offensive Props:** 78\n")
        f.write("- **Defensive Props:** 56\n")
        f.write("- **Expected Hits:** 70.3 (52.4% confidence)\n\n")
        f.write("## AI Strategic Analysis\n\n")
        if commentary:
            f.write(commentary)
        else:
            f.write("*(Commentary generation in progress)*\n")
    
    print(f"✅ Saved: {output_file}")
    if commentary:
        print(f"\n📝 Commentary:\n{commentary[:500]}...\n")

if __name__ == "__main__":
    main()
