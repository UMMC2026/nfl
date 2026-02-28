"""Regression check: verify the larger slate still produces reasonable results."""
import json, sys, os
sys.path.insert(0, ".")
from risk_first_analyzer import analyze_slate

with open("outputs/NBAMONDA1ST_USERPASTE_20260209.json") as f:
    slate = json.load(f)
props = slate if isinstance(slate, list) else slate.get("plays", slate.get("props", []))
print(f"Loaded {len(props)} props")

analysis = analyze_slate(props, verbose=False)
results = analysis.get("results", [])
plays = [r for r in results if r.get("decision") in ("PLAY", "STRONG", "LEAN")]
hybrid_overrides = [r for r in plays if r.get("hybrid_override")]

print(f"Total plays: {len(plays)} (was 17 before fix), hybrid overrides: {len(hybrid_overrides)}")
print()

for p in plays:
    tag = " [HO]" if p.get("hybrid_override") else ""
    player = p.get("player", "?")
    stat = p.get("stat", "?")
    line = p.get("line", "?")
    direction = p.get("direction", "?")
    conf = p.get("effective_confidence", 0)
    decision = p.get("decision", "?")
    print(f"  {decision:8s} {player:22s} {stat:10s} {line} {direction:8s} conf={conf:.1f}%{tag}")
