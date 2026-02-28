"""Show full edge detail for a CBB actionable and skip edge."""
import json

with open("sports/cbb/outputs/cbb_RISK_FIRST_20260209_190635_FROM_UD.json") as f:
    data = json.load(f)

edges = data if isinstance(data, list) else data.get("edges", data.get("results", []))

# Find first STRONG and first SKIP
strong = None
skip = None
for e in edges:
    t = e.get("tier", "")
    if t == "STRONG" and not strong:
        strong = e
    if t == "SKIP" and not skip:
        skip = e
    if strong and skip:
        break

for label, edge in [("STRONG", strong), ("SKIP", skip)]:
    if edge:
        print(f"=== {label} ===")
        for k in sorted(edge.keys()):
            print(f"  {k}: {edge[k]}")
        print()

# Check player_mean and raw_probability fields for all edges
print("DATA QUALITY CHECK:")
zero_mu = sum(1 for e in edges if (e.get("player_mean") or 0) == 0)
has_mu = sum(1 for e in edges if (e.get("player_mean") or 0) > 0)
print(f"  player_mean=0: {zero_mu}")
print(f"  player_mean>0: {has_mu}")

# Check data sources
from collections import Counter
sources = Counter(e.get("data_source", e.get("mean_source", "?")) for e in edges)
print("  DATA SOURCES:")
for s, c in sources.most_common():
    print(f"    {s}: {c}")

# Check decision traces
print()
print("SAMPLE DECISION TRACES (first 3):")
for e in edges[:3]:
    print(f"  {e.get('player', '?')} {e.get('stat', '?')} {e.get('line', '?')} {e.get('direction', '?')}")
    print(f"    decision_trace: {e.get('decision_trace', '?')}")
    print(f"    raw_probability: {e.get('raw_probability', '?')}")
    print(f"    probability: {e.get('probability', '?')}")
    print(f"    player_mean: {e.get('player_mean', '?')}")
    print(f"    model_used: {e.get('model_used', '?')}")
    print(f"    confidence_flag: {e.get('confidence_flag', '?')}")
    print(f"    skip_reason: {e.get('skip_reason', '?')}")
    print()
