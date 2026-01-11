"""
Show tonight's top picks
"""
import json
from pathlib import Path

picks_file = Path("outputs/validated_primary_edges.json")

if not picks_file.exists():
    print("❌ No picks file found. Run daily_pipeline.py first.")
    exit(1)

with open(picks_file, 'r') as f:
    picks = json.load(f)

# Group by confidence (since tier isn't in the output yet)
high_conf = [p for p in picks if p.get('probability', 0) >= 0.65]
med_conf = [p for p in picks if 0.55 <= p.get('probability', 0) < 0.65]
low_conf = [p for p in picks if p.get('probability', 0) < 0.55]

print(f"🎯 TONIGHT'S TOP PICKS")
print("=" * 70)

print(f"\n💎 HIGH CONFIDENCE ({len(high_conf)}) - 65%+ Probability")
print("-" * 70)
for p in sorted(high_conf, key=lambda x: x.get('probability', 0), reverse=True)[:10]:
    player = p.get('player', 'Unknown')
    team = p.get('team', '???')
    stat = p.get('stat', '???')
    direction = p.get('direction', '???')
    line = p.get('line', 0)
    prob = p.get('probability', 0)
    print(f"  {player:25} ({team:3}) - {stat:15} {direction:6} {line:5} ({prob:.0%})")

print(f"\n💪 MEDIUM CONFIDENCE ({len(med_conf)}) - 55-65% Probability")
print("-" * 70)
for p in sorted(med_conf, key=lambda x: x.get('probability', 0), reverse=True)[:10]:
    player = p.get('player', 'Unknown')
    team = p.get('team', '???')
    stat = p.get('stat', '???')
    direction = p.get('direction', '???')
    line = p.get('line', 0)
    prob = p.get('probability', 0)
    print(f"  {player:25} ({team:3}) - {stat:15} {direction:6} {line:5} ({prob:.0%})")

print(f"\n📊 LOWER CONFIDENCE ({len(low_conf)}) - Below 55%")
print("-" * 70)
for p in sorted(low_conf, key=lambda x: x.get('probability', 0), reverse=True)[:5]:
    player = p.get('player', 'Unknown')
    team = p.get('team', '???')
    stat = p.get('stat', '???')
    direction = p.get('direction', '???')
    line = p.get('line', 0)
    prob = p.get('probability', 0)
    print(f"  {player:25} ({team:3}) - {stat:15} {direction:6} {line:5} ({prob:.0%})")

print("\n" + "=" * 70)
print(f"Total validated picks: {len(picks)}")
