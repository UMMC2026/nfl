"""
Generate fresh analysis with NBA Role Layer enabled
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime

print("🚀 GENERATING FRESH ANALYSIS WITH NBA ROLE LAYER")
print("=" * 70)

# Find latest slate file
slate_file = sorted(Path("outputs").glob("IND_ATL*_USERPASTE_*.json"), 
                   key=lambda p: p.stat().st_mtime, reverse=True)[0]

print(f"📄 Input: {slate_file.name}")

# Run analysis
print(f"⚙️  Running analyze_from_underdog_json.py...")
result = subprocess.run(
    [
        ".venv\\Scripts\\python.exe", 
        "analyze_from_underdog_json.py",
        "--slate", str(slate_file),
        "--label", "TEST_NBA_ROLE"
    ],
    capture_output=True,
    text=True,
    cwd="."
)

# Check for NBA messages in output
output_lines = result.stdout.split('\n')
nba_messages = [line for line in output_lines if 'NBA' in line or 'Enriched' in line or 'Normalized' in line]

print("\n📊 NBA ROLE LAYER MESSAGES:")
for msg in nba_messages:
    print(f"   {msg.strip()}")

if result.returncode != 0:
    print(f"\n❌ Analysis failed with code {result.returncode}")
    print("STDERR:", result.stderr[:500])
else:
    print(f"\n✅ Analysis completed successfully")
    
    # Find output file
    output_file = sorted(Path("outputs").glob("IND_ATL*_RISK_FIRST_*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)[0]
    
    print(f"📤 Output: {output_file.name}")
    print(f"   Modified: {datetime.fromtimestamp(output_file.stat().st_mtime)}")
    
    # Verify NBA fields
    data = json.loads(output_file.read_text())
    picks = data.get("results", [])
    
    with_nba = sum(1 for p in picks if p.get("nba_role_archetype"))
    print(f"\n✅ {with_nba}/{len(picks)} picks have NBA Role Layer fields")
    
    if with_nba > 0:
        # Show CJ McCollum
        cj_picks = [p for p in picks if "McCollum" in p.get("player", "")]
        if cj_picks:
            print(f"\n🎯 CJ McCollum (BENCH_MICROWAVE archetype):")
            for pick in cj_picks[:2]:
                print(f"\n   {pick['player']} {pick['stat']} {'>' if pick['direction']=='higher' else '<'}{pick['line']}")
                print(f"      Archetype: {pick.get('nba_role_archetype')}")
                print(f"      Cap Adjustment: {pick.get('nba_confidence_cap_adjustment'):.1f}%")
                print(f"      Flags: {', '.join(pick.get('nba_role_flags', []))}")
                print(f"      Effective Confidence: {pick.get('effective_confidence'):.1f}%")

print("\n" + "=" * 70)
