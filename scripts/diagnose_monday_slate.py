"""Diagnose why Monday CHA/DET slate produced 0 actionable plays."""
import json

with open("outputs/NBA6PMMOND_RISK_FIRST_20260209_FROM_UD.json") as f:
    data = json.load(f)

results = data["results"]
blocked = [r for r in results if r.get("blocked", False)]
non_blocked = [r for r in results if not r.get("blocked", False)]

print(f"Total: {len(results)}, Blocked: {len(blocked)}, Non-blocked: {len(non_blocked)}")
print()

# Block reasons
from collections import Counter
block_reasons = Counter(r.get("block_reason", "unknown") for r in blocked)
print("BLOCK REASONS:")
for reason, count in block_reasons.most_common():
    print(f"  {count}x - {reason}")
print()

# Sort non-blocked by max prob
for r in non_blocked:
    r["_max_prob"] = max(r.get("over_prob", 0) or 0, r.get("under_prob", 0) or 0)
non_blocked.sort(key=lambda x: x["_max_prob"], reverse=True)

print("TOP 30 NON-BLOCKED PROPS (sorted by best probability):")
print(f"{'Player':22s} {'Stat':10s} {'Line':>6s} {'Dir':8s} {'Over%':>6s} {'Under%':>6s} {'mu':>7s} {'sigma':>7s} {'Tier':10s}")
print("-" * 100)
for r in non_blocked[:30]:
    player = r.get("player", "?")
    stat = r.get("stat", "?")
    line = str(r.get("line", "?"))
    direction = r.get("direction", "?")
    over_p = r.get("over_prob", 0) or 0
    under_p = r.get("under_prob", 0) or 0
    mu = r.get("mu", 0) or 0
    sigma = r.get("sigma", 0) or 0
    tier = r.get("tier", "?")
    print(f"{player:22s} {stat:10s} {line:>6s} {direction:8s} {over_p:6.1f} {under_p:6.1f} {mu:7.1f} {sigma:7.1f} {tier:10s}")

print()
print("PROBABILITY BRACKETS:")
brackets = {"55-60": 0, "50-55": 0, "45-50": 0, "40-45": 0, "<40": 0}
for r in non_blocked:
    p = r["_max_prob"]
    if p >= 55: brackets["55-60"] += 1
    elif p >= 50: brackets["50-55"] += 1
    elif p >= 45: brackets["45-50"] += 1
    elif p >= 40: brackets["40-45"] += 1
    else: brackets["<40"] += 1
for bracket, count in brackets.items():
    print(f"  {bracket}%: {count}")

# Check what keys are available for penalty inspection
print()
print("SAMPLE EDGE KEYS:")
if non_blocked:
    print(list(non_blocked[0].keys()))

# Check for penalty-related fields
print()
print("PENALTY/ADJUSTMENT FIELDS (first non-blocked prop):")
if non_blocked:
    r = non_blocked[0]
    for k in sorted(r.keys()):
        if any(word in k.lower() for word in ["penalty", "mult", "adjust", "factor", "data_driven", "cap", "specialist"]):
            print(f"  {k}: {r[k]}")
