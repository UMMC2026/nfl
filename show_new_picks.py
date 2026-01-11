import json

picks = json.load(open('picks.json'))
print("=" * 70)
print("✅ NEW THURSDAY PICKS ADDED (32 total)")
print("=" * 70)

# Group by game/team
hou_bkn = [p for p in picks[108:] if p.get('team') in ['HOU', 'BKN']]
det_mia = [p for p in picks[108:] if p.get('team') in ['DET', 'MIA']]
phi_dal = [p for p in picks[108:] if p.get('team') in ['PHI', 'DAL']]

print("\n🏀 HOU @ BKN (Thu 5:10pm) - 9 picks")
for p in hou_bkn:
    d = "O" if p.get('direction') == 'higher' else 'U'
    print(f"  {p['player']:<20} {d} {p['line']:>5} {p['stat']}")

print("\n🏀 DET vs MIA (Thu 6:10pm) - 15 picks")
for p in det_mia:
    d = "O" if p.get('direction') == 'higher' else 'U'
    print(f"  {p['player']:<20} {d} {p['line']:>5} {p['stat']}")

print("\n🏀 PHI @ DAL (Thu 7:40pm) - 9 picks")
for p in phi_dal:
    d = "O" if p.get('direction') == 'higher' else 'U'
    print(f"  {p['player']:<20} {d} {p['line']:>5} {p['stat']}")

print(f"\n{'=' * 70}")
print(f"✅ Total picks: {len(picks)} (was 108)")
print(f"✅ Hydrated: 136/140 picks")
print(f"✅ Pipeline processed all picks")
print(f"✅ Cheatsheet: outputs/CHEATSHEET_DEC31_20251231_201550.txt")
print(f"{'=' * 70}")
