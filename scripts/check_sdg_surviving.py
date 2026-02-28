"""Check SDG values for the 17 plays that survived in the larger slate."""
import json

with open("outputs/NBAMONDA1ST_RISK_FIRST_20260209_FROM_UD.json") as f:
    d = json.load(f)

results = d.get("results", [])
plays = [r for r in results if r.get("decision") in ("PLAY", "STRONG", "LEAN")]
print(f"Actionable plays: {len(plays)}")
print()

for p in plays[:8]:
    sdg = p.get("sdg_result", {})
    hybrid = p.get("hybrid_confidence", {})
    player = p.get("player", "?")
    stat = p.get("stat", "?")
    line = p.get("line", "?")
    direction = p.get("direction", "?")
    
    print(f"{player:20s} {stat:10s} {line} {direction}")
    print(f"  sdg_mult={p.get('sdg_multiplier', '?')}, z={sdg.get('z_stat', '?')}, penalty={sdg.get('penalty_level', '?')}")
    print(f"  model_conf={p.get('model_confidence', 0):.1f}, eff_conf={p.get('effective_confidence', 0):.1f}")
    print(f"  hybrid: eff_prob={hybrid.get('effective_probability', 0)}, tier={hybrid.get('tier', '?')}")
    print(f"  decision={p.get('decision', '?')}")
    print()

# Distribution of SDG penalties across ALL props
from collections import Counter
sdg_dist = Counter()
for r in results:
    sdg_dist[r.get("sdg_multiplier", 1.0)] += 1
print("SDG MULTIPLIER DISTRIBUTION (all 360 props):")
for mult, cnt in sdg_dist.most_common():
    print(f"  {mult}: {cnt}")
