"""Analyze CBB pipeline output to understand tier distribution and SDG impact."""
import json
from collections import Counter

with open("sports/cbb/outputs/cbb_RISK_FIRST_20260209_190635_FROM_UD.json") as f:
    data = json.load(f)

edges = data if isinstance(data, list) else data.get("edges", data.get("results", data.get("picks", [])))
if isinstance(data, dict) and not edges:
    # Try top-level keys
    print("Top-level keys:", list(data.keys())[:15])

print(f"Total edges: {len(edges)}")
print()

# Tier distribution
tiers = Counter(e.get("tier", e.get("decision", "?")) for e in edges)
print("TIER DISTRIBUTION:")
for t, c in tiers.most_common():
    print(f"  {t:12s}: {c}")

# SDG results
print()
print("SDG PENALTY DISTRIBUTION:")
sdg_levels = Counter()
for e in edges:
    sdg = e.get("sdg_result", e.get("sdg", {}))
    if isinstance(sdg, dict):
        level = sdg.get("penalty_level", sdg.get("penalty", sdg.get("action", "?")))
        sdg_levels[str(level)] += 1
    else:
        sdg_levels["no_sdg_data"] += 1
for l, c in sdg_levels.most_common():
    print(f"  {l:20s}: {c}")

# Show actionable plays
print()
print("ACTIONABLE PLAYS:")
actionable = [e for e in edges if e.get("tier", "") in ("STRONG", "LEAN", "PLAY", "SLAM")]
for e in actionable:
    player = e.get("player", "?")
    stat = e.get("stat", e.get("market", "?"))
    line = e.get("line", "?")
    direction = e.get("direction", "?")
    prob = e.get("probability", e.get("effective_confidence", e.get("prob", 0)))
    tier = e.get("tier", "?")
    source = e.get("mean_source", e.get("data_source", "?"))
    mu = e.get("mu", e.get("mean", 0))
    sigma = e.get("sigma", e.get("std", 0))
    print(f"  [{tier:6s}] {player:25s} {stat:12s} {line:>6} {direction:8s} prob={prob:.1f}%  mu={mu:.1f} σ={sigma:.1f}  src={source}")

# Show SKIP edge probability brackets
print()
print("SKIP EDGES — PROBABILITY BRACKETS:")
skip_edges = [e for e in edges if e.get("tier", "") == "SKIP"]
brackets = {">=60": 0, "55-60": 0, "50-55": 0, "45-50": 0, "<45": 0}
for e in skip_edges:
    p = e.get("probability", e.get("effective_confidence", e.get("prob", 0)))
    if isinstance(p, (int, float)):
        if p >= 60: brackets[">=60"] += 1
        elif p >= 55: brackets["55-60"] += 1
        elif p >= 50: brackets["50-55"] += 1
        elif p >= 45: brackets["45-50"] += 1
        else: brackets["<45"] += 1
for b, c in brackets.items():
    print(f"  {b}%: {c}")

# Show top 10 SKIP edges by probability
print()
print("TOP 10 SKIP EDGES (closest to threshold):")
skip_edges.sort(key=lambda e: e.get("probability", e.get("effective_confidence", e.get("prob", 0))), reverse=True)
for e in skip_edges[:10]:
    player = e.get("player", "?")
    stat = e.get("stat", "?")
    line = e.get("line", "?")
    direction = e.get("direction", "?")
    prob = e.get("probability", e.get("effective_confidence", e.get("prob", 0)))
    mu = e.get("mu", e.get("mean", 0))
    source = e.get("mean_source", e.get("data_source", "?"))
    sdg = e.get("sdg_result", e.get("sdg", {}))
    sdg_action = sdg.get("action", sdg.get("penalty", "?")) if isinstance(sdg, dict) else "?"
    print(f"  {player:25s} {stat:12s} {line:>6} {direction:8s} prob={prob:.1f}%  mu={mu:.1f}  src={source}  sdg={sdg_action}")

# Sample edge keys
print()
print("SAMPLE EDGE KEYS:")
if edges:
    print(sorted(edges[0].keys()))
