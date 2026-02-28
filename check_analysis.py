"""Check what's actually in ALL analysis files."""
import json
from pathlib import Path

# Check ALL NFL analysis files
files = sorted(Path("outputs").glob("nfl_analysis_*.json"), reverse=True)

for fpath in files:
    with open(fpath) as f:
        d = json.load(f)
    picks = d.get("results", d.get("picks", []))
    teams = set(p.get("team", "?") for p in picks)
    opponents = set(p.get("opponent", "") for p in picks if p.get("opponent"))
    print(f"\n{fpath.name}")
    print(f"  Label: {d.get('label', '?')}")
    print(f"  Picks: {len(picks)}")
    print(f"  Teams: {teams}")
    print(f"  Opponents: {opponents}")
    # Show first 3 picks
    for p in picks[:3]:
        print(f"    {p.get('player')} ({p.get('team')}) vs {p.get('opponent','')} | {p.get('stat')} {p.get('direction')} {p.get('line')}")

# Also check slate files
print("\n\n=== SLATE FILES ===")
slates = sorted(Path("outputs").glob("nfl_slate_*.json"), reverse=True)
for fpath in slates[:5]:
    with open(fpath) as f:
        d = json.load(f)
    picks = d.get("picks", [])
    teams = set(p.get("team", "?") for p in picks)
    print(f"\n{fpath.name}")
    print(f"  Label: {d.get('label', '?')}")
    print(f"  Picks: {len(picks)}")
    print(f"  Teams: {teams}")
