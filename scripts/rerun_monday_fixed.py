"""
Re-analyze the Monday CHA/DET slate with fixed SDG + hybrid reconciliation.
Uses the already-ingested slate JSON without needing full menu.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from risk_first_analyzer import analyze_slate

slate_path = "outputs/NBA6PMMOND_USERPASTE_20260209.json"

print("=" * 70)
print("RE-ANALYZING Monday CHA/DET slate with fixed penalties")
print("=" * 70)

# Load the ingested slate
with open(slate_path) as f:
    slate = json.load(f)

props = slate if isinstance(slate, list) else slate.get("plays", slate.get("props", slate.get("picks", [])))
print(f"Loaded {len(props)} props from {slate_path}")

# Run analysis
analysis = analyze_slate(props, verbose=False)

if analysis:
    results = analysis.get("results", [])
    plays = [r for r in results if r.get("decision") in ("PLAY", "STRONG", "LEAN")]
    blocked = [r for r in results if r.get("decision") == "BLOCKED"]
    no_play = [r for r in results if r.get("decision") == "NO_PLAY"]
    
    print()
    print("=" * 70)
    print(f"RESULTS: {len(plays)} actionable plays from {len(results)} props")
    print(f"  BLOCKED: {len(blocked)}")
    print(f"  NO_PLAY: {len(no_play)}")
    print("=" * 70)
    
    for p in plays:
        player = p.get("player", "?")
        stat = p.get("stat", "?")
        line = p.get("line", "?")
        direction = p.get("direction", "?")
        eff = p.get("effective_confidence", 0)
        decision = p.get("decision", "?")
        hybrid_override = p.get("hybrid_override", False)
        hybrid_detail = p.get("hybrid_override_detail", "")
        sdg = p.get("sdg_multiplier", 1.0)
        
        override_tag = " [HYBRID OVERRIDE]" if hybrid_override else ""
        print(f"  {decision:8s} {player:22s} {stat:10s} {line} {direction:8s} conf={eff:.1f}%  sdg={sdg}{override_tag}")
        if hybrid_detail:
            print(f"           {hybrid_detail}")
else:
    print("Analysis returned None!")
