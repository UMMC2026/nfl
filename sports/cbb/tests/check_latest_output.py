"""Quick check of latest CBB output."""
import json, glob, os

files = sorted(glob.glob('sports/cbb/outputs/cbb_RISK_FIRST_20260209*'), key=os.path.getmtime, reverse=True)
if not files:
    print("No CBB output files found for today")
    exit()

f = files[0]
print(f"Latest: {f}")
print(f"Modified: {os.path.getmtime(f)}")

data = json.load(open(f))
picks = data.get("picks", [])
print(f"Total picks: {len(picks)}")

# Tier distribution
tiers = {}
for p in picks:
    t = p.get("tier", "?")
    tiers[t] = tiers.get(t, 0) + 1
print(f"Tiers: {tiers}")

# Show STRONG and LEAN
for tier_name in ["STRONG", "LEAN"]:
    subset = [p for p in picks if p.get("tier") == tier_name]
    print(f"\n{tier_name} ({len(subset)}):")
    for p in subset:
        print(f"  {p['player']:20s} {p['stat']:12s} {p['line']:>6} {p['direction']:>6}"
              f"  prob={p['probability']:.1%}  src={p.get('mean_source', '?')}"
              f"  model={p.get('model_used', '?')}")

# Show SKIP reasons sample
skips = [p for p in picks if p.get("tier") == "SKIP"]
reasons = {}
for p in skips:
    r = p.get("skip_reason", "NO_REASON")
    reasons[r] = reasons.get(r, 0) + 1
print(f"\nSKIP breakdown ({len(skips)} total):")
for r, c in sorted(reasons.items(), key=lambda x: -x[1])[:10]:
    print(f"  {c:>4}x  {r}")

# Check for commence_time / freshness info
has_commence = sum(1 for p in picks if p.get("commence_time"))
print(f"\nPicks with commence_time: {has_commence}/{len(picks)}")
if has_commence:
    times = set(p.get("commence_time") for p in picks if p.get("commence_time"))
    print(f"Unique commence_times: {sorted(times)[:5]}")

# Check metadata
meta = data.get("metadata", data.get("meta", {}))
if meta:
    print(f"\nMetadata: {json.dumps(meta, indent=2)[:500]}")
