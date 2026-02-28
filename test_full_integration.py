"""
Full end-to-end test: Run menu analysis and verify NBA Role Layer fields in output
"""

import subprocess
import json
from pathlib import Path

print("🧪 FULL END-TO-END NBA ROLE LAYER TEST")
print("=" * 60)

# Find the latest IND vs ATL slate file
slate_files = sorted(Path("outputs").glob("IND_ATL*_USERPASTE_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not slate_files:
    print("❌ No IND vs ATL slate file found")
    exit(1)

slate_file = slate_files[0]
print(f"📄 Using slate: {slate_file.name}")

# Load slate to check what we're analyzing
slate_data = json.loads(slate_file.read_text())
props = slate_data.get("plays", [])
print(f"📊 Slate has {len(props)} props")

# Get a few player names for verification
players = list(set(p.get("player") for p in props[:20] if isinstance(p, dict)))[:5]
print(f"🎯 Key players: {', '.join(players)}")

# Run analyze_from_underdog_json.py directly
print(f"\n🔧 Running analysis...")
result = subprocess.run(
    [".venv\\Scripts\\python.exe", "analyze_from_underdog_json.py", str(slate_file)],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"❌ Analysis failed:")
    print(result.stderr)
    exit(1)

print("✅ Analysis completed")

# Find the output file
output_files = sorted(Path("outputs").glob("IND_ATL*_RISK_FIRST_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not output_files:
    print("❌ No output file found")
    exit(1)

output_file = output_files[0]
print(f"📤 Output file: {output_file.name}")

# Load and check output
output_data = json.loads(output_file.read_text())
print(f"📊 Output has {len(output_data)} picks")

# Check for NBA Role Layer fields
nba_fields_count = 0
cj_found = False
sample_results = []

for pick in output_data:
    if not isinstance(pick, dict):
        continue
    
    player = pick.get("player", "")
    
    # Count picks with NBA fields
    if pick.get("nba_role_archetype"):
        nba_fields_count += 1
    
    # Track CJ McCollum specifically
    if "CJ McCollum" in player or "McCollum" in player:
        cj_found = True
        sample_results.append({
            "player": player,
            "stat": pick.get("stat"),
            "archetype": pick.get("nba_role_archetype"),
            "cap_adjustment": pick.get("nba_confidence_cap_adjustment"),
            "flags": pick.get("nba_role_flags"),
            "effective_confidence": pick.get("effective_confidence"),
            "nba_cap_applied": pick.get("nba_cap_adjustment_applied")
        })

print(f"\n📈 RESULTS:")
print(f"   {nba_fields_count}/{len(output_data)} picks have nba_role_archetype")

if sample_results:
    print(f"\n🎯 CJ McCollum picks:")
    for result in sample_results[:3]:
        print(f"\n   {result['player']} {result['stat']}:")
        print(f"      Archetype: {result['archetype']}")
        print(f"      Cap Adjustment: {result['cap_adjustment']}")
        print(f"      Flags: {result['flags']}")
        print(f"      Effective Confidence: {result['effective_confidence']}")
        print(f"      Cap Applied: {result.get('nba_cap_applied', 'N/A')}")
else:
    print("   ⚠️ CJ McCollum not found in output")

# Final verdict
if nba_fields_count > 0:
    print(f"\n✅ SUCCESS: NBA Role Layer is working in production!")
    print(f"   {nba_fields_count} picks normalized and saved to output")
else:
    print(f"\n❌ FAILURE: No NBA Role Layer fields found in output")

print("\n" + "=" * 60)
