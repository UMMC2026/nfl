"""Quick Brier Score Calculation"""
import csv

picks = []
with open('calibration_history.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        outcome = row.get('outcome', '').strip().upper()
        prob_str = row.get('probability', '').strip()
        
        if outcome in ['HIT', 'MISS'] and prob_str:
            try:
                prob = float(prob_str)
                if prob > 1:
                    prob = prob / 100
                o = 1 if outcome == 'HIT' else 0
                picks.append({
                    'prob': prob,
                    'outcome': o,
                    'tier': row.get('tier', ''),
                    'stat': row.get('stat_type', row.get('stat', ''))
                })
            except ValueError:
                pass

print(f"Scorable picks: {len(picks)}")
print(f"Hits: {sum(p['outcome'] for p in picks)}/{len(picks)} = {sum(p['outcome'] for p in picks)/len(picks):.1%}")
print()

# Brier score
brier = sum((p['prob'] - p['outcome'])**2 for p in picks) / len(picks)
print(f"IN-SAMPLE BRIER SCORE: {brier:.4f}")

if brier < 0.20:
    quality = "EXCELLENT"
elif brier < 0.22:
    quality = "GOOD"
elif brier < 0.25:
    quality = "FAIR (better than random)"
else:
    quality = "NEEDS IMPROVEMENT"

print(f"Quality: {quality}")
print(f"(Reference: 0.25 = random guessing)")
print()

# By tier
print("BRIER BY TIER:")
for tier in ['SLAM', 'STRONG', 'LEAN']:
    tier_picks = [p for p in picks if tier in p['tier'].upper()]
    if tier_picks:
        b = sum((p['prob'] - p['outcome'])**2 for p in tier_picks) / len(tier_picks)
        hr = sum(p['outcome'] for p in tier_picks) / len(tier_picks)
        print(f"  {tier}: Brier={b:.4f}, n={len(tier_picks)}, HitRate={hr:.1%}")
