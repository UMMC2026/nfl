"""Quick debug script to check SDG floor logic on Wagler/DeVries."""
import json
from pathlib import Path

# Load existing edges
f = sorted(Path("sports/cbb/outputs").glob("cbb_RISK_FIRST_*.json"), reverse=True)[0]
print(f"Loading: {f.name}")
data = json.load(open(f, encoding="utf-8"))
edges = data.get("picks", data) if isinstance(data, dict) else data

# Find Wagler and DeVries 3PM HIGHER
targets = []
for e in edges:
    p = e.get("player", "")
    if ("Wagler" in p or "DeVries" in p) and "3pm" in e.get("stat", "").lower() and e.get("direction", "").lower() == "higher":
        targets.append(e)
        print(f"\n{'='*60}")
        print(f"{p} | {e['stat']} {e['direction']} {e['line']}")
        print(f"  probability:       {e.get('probability')}")
        print(f"  raw_probability:   {e.get('raw_probability')}")
        print(f"  sdg_penalty:       {e.get('sdg_penalty')}")
        print(f"  sdg_passed:        {e.get('sdg_passed')}")
        print(f"  sdg_reasons:       {e.get('sdg_reasons')}")
        print(f"  sdg_floor_applied: {e.get('sdg_floor_applied')}")
        print(f"  tier:              {e.get('tier')}")
        print(f"  player_mean (mu):  {e.get('player_mean')}")
        cv_details = (e.get("sdg_details") or {}).get("cv", {})
        print(f"  cv_ratio:          {cv_details.get('cv_ratio')}")
        print(f"  cv_threshold:      {cv_details.get('cv_threshold')}")
        print(f"  player_role:       {cv_details.get('player_role')}")

if not targets:
    print("No Wagler/DeVries 3PM HIGHER edges found!")
else:
    # Now simulate what the floor fix would do
    print(f"\n{'='*60}")
    print("FLOOR SIMULATION:")
    LEAN_FLOOR = 0.60
    for e in targets:
        raw = e.get("raw_probability", e.get("probability", 0))
        penalty = e.get("sdg_penalty", 1.0)
        adjusted = raw * penalty
        mu = e.get("player_mean", 0) or 0
        line = e.get("line", 0)
        is_over = e.get("direction", "").lower() in ["higher", "over"]
        dir_aligned = (is_over and mu > line) or (not is_over and mu < line)
        
        print(f"\n  {e['player']} {e['stat']} {e['direction']} {e['line']}")
        print(f"    raw_prob={raw:.4f}, penalty={penalty}, adjusted={adjusted:.4f}")
        print(f"    mu={mu}, line={line}, is_over={is_over}, dir_aligned={dir_aligned}")
        print(f"    raw >= LEAN? {raw >= LEAN_FLOOR}")
        print(f"    adjusted < LEAN? {adjusted < LEAN_FLOOR}")
        if dir_aligned and raw >= LEAN_FLOOR and adjusted < LEAN_FLOOR:
            print(f"    >>> FLOOR WOULD APPLY: {adjusted:.4f} → {LEAN_FLOOR}")
        else:
            print(f"    >>> Floor not needed (adjusted={adjusted:.4f})")
