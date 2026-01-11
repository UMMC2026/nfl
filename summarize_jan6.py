"""Summary of Jan 6 verification results"""
import csv
from pathlib import Path
from collections import defaultdict

# Read results
results_file = Path("calibration_jan6.csv")
if not results_file.exists():
    print("❌ File not found")
    exit(1)

with open(results_file) as f:
    rows = list(csv.DictReader(f))

# Count by outcome
teams_skipped = defaultdict(int)
verified = []
failed = []
pending = []

for row in rows:
    if row['outcome'] == 'HIT':
        verified.append((row['player'], row['stat'], row['line'], row['actual_value'], 'HIT'))
    elif row['outcome'] == 'MISS':
        verified.append((row['player'], row['stat'], row['line'], row['actual_value'], 'MISS'))
    elif not row['actual_value']:
        # Check if team didn't play
        team = row['team']
        teams_to_skip = ['CHI', 'MIL', 'PHX', 'ATL', 'BKN', 'BOS', 'CHA', 'DEN', 'DET', 'GS', 'HOU', 'LAC', 'NY', 'OKC', 'ORL', 'PHI', 'POR', 'TOR', 'UTAH']
        if team in ['IND', 'CLE', 'WSH', 'ORL', 'MEM', 'SA', 'MIN', 'MIA', 'LAL', 'NO', 'SAC', 'DAL']:
            pending.append((row['player'], row['team'], row['stat']))
        else:
            teams_skipped[team] += 1

print("=" * 80)
print(f"JAN 6 VERIFICATION SUMMARY")
print("=" * 80)
print(f"\n✅ VERIFIED: {len(verified)} picks")
print(f"⏳ PENDING: {len(pending)} picks (teams that played but couldn't fetch stats)")
print(f"⚠️  SKIPPED: {sum(teams_skipped.values())} picks (teams didn't play)")

if verified:
    print(f"\n📊 VERIFIED RESULTS:")
    hits = [v for v in verified if v[4] == 'HIT']
    misses = [v for v in verified if v[4] == 'MISS']
    
    print(f"   HITS: {len(hits)}")
    print(f"   MISSES: {len(misses)}")
    print(f"   HIT RATE: {len(hits)/len(verified)*100:.1f}%")
    
    if hits:
        print(f"\n✅ HITS:")
        for player, stat, line, actual, _ in hits[:10]:
            print(f"   {player} {stat} U {line} (actual: {actual})")
    
    if misses:
        print(f"\n❌ MISSES:")
        for player, stat, line, actual, _ in misses[:10]:
            print(f"   {player} {stat} U {line} (actual: {actual})")

print(f"\n⚠️  TEAMS SKIPPED (didn't play on Jan 6):")
for team, count in sorted(teams_skipped.items(), key=lambda x: x[1], reverse=True):
    print(f"   {team}: {count} picks")

print("\n" + "=" * 80)
