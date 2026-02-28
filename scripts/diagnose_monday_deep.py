"""Deep diagnostic: why are all over_prob/under_prob = 0.0?"""
import json

with open("outputs/NBA6PMMOND_RISK_FIRST_20260209_FROM_UD.json") as f:
    data = json.load(f)

results = data["results"]

# Show ALL probability-related fields for the first few props
print("=" * 80)
print("FULL PROBABILITY FIELD DUMP (first 5 props)")
print("=" * 80)
for i, r in enumerate(results[:5]):
    print(f"\n--- {r['player']} | {r['stat']} {r['line']} {r.get('direction','?')} ---")
    prob_keys = [k for k in r.keys() if any(w in k.lower() for w in 
        ["prob", "conf", "tier", "decision", "status", "edge", "over", "under", "hybrid", "model"])]
    for k in sorted(prob_keys):
        print(f"  {k}: {r[k]}")

print()
print("=" * 80)
print("CHECKING data_driven_adjustments FOR ALL PROPS")
print("=" * 80)

# Look at how data_driven_adjustments is crushing probabilities
for r in results[:10]:
    dda = r.get("data_driven_adjustments", {})
    sdg = r.get("sdg_multiplier", 1.0)
    sdg_applied = r.get("sdg_penalty_applied", False)
    stat_adj = r.get("stat_adjustment", {})
    
    print(f"\n{r['player']:20s} | {r['stat']:10s} | line={r['line']} | dir={r.get('direction','?')}")
    print(f"  mu={r.get('mu',0):.1f}, sigma={r.get('sigma',0):.1f}, mu_raw={r.get('mu_raw',0):.1f}, sigma_raw={r.get('sigma_raw',0):.1f}")
    if dda:
        sdm = dda.get("stat_direction_multiplier", {})
        sss = dda.get("sample_size_scaling", {})
        print(f"  stat_dir_mult: {sdm.get('multiplier','?')} (before={sdm.get('before',0):.1f} -> after={sdm.get('after',0):.1f})")
        print(f"  sample_size_scale: {sss.get('scale','?')} (before={sss.get('before',0):.1f} -> after={sss.get('after',0):.1f})")
    print(f"  sdg_multiplier={sdg}, sdg_penalty_applied={sdg_applied}")
    print(f"  stat_adj raw_conf={stat_adj.get('raw_confidence',0):.1f}, adj_conf={stat_adj.get('adjusted_confidence',0):.1f}")
    print(f"  model_confidence={r.get('model_confidence',0)}, effective_confidence={r.get('effective_confidence',0)}")
    print(f"  hybrid_confidence={r.get('hybrid_confidence',0)}, hybrid_tier={r.get('hybrid_tier','?')}")
    print(f"  over_prob={r.get('over_prob',0)}, under_prob={r.get('under_prob',0)}")
    print(f"  decision={r.get('decision','?')}, status={r.get('status','?')}")
    print(f"  tier_label={r.get('tier_label','?')}, tier_label_final={r.get('tier_label_final','?')}")

# Check if the prob_method is the issue
print()
print("=" * 80)
print("PROB METHODS IN USE:")
from collections import Counter
methods = Counter(r.get("prob_method", "unknown") for r in results)
for m, c in methods.most_common():
    print(f"  {m}: {c}")

# Check decisions
print()
print("DECISIONS:")
decisions = Counter(r.get("decision", "unknown") for r in results)
for d, c in decisions.most_common():
    print(f"  {d}: {c}")

# Check statuses
print()
print("STATUSES:")
statuses = Counter(r.get("status", "unknown") for r in results)
for s, c in statuses.most_common():
    print(f"  {s}: {c}")
