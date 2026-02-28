"""Find players in WTA data."""
import csv

files = ['tennis/data/raw/wta_matches_2024.csv', 'tennis/data/raw/wta_matches_2023.csv']
players_found = {}

for f in files:
    try:
        for r in csv.DictReader(open(f, encoding='utf-8')):
            for name in [r.get('winner_name', ''), r.get('loser_name', '')]:
                lower = name.lower()
                if 'wang' in lower or 'matsuda' in lower or 'kuramochi' in lower:
                    if name not in players_found:
                        players_found[name] = {'count': 0, 'file': f.split('/')[-1]}
                    players_found[name]['count'] += 1
    except Exception as e:
        print(f"Error reading {f}: {e}")

print("Players found in WTA data:")
for name, info in sorted(players_found.items()):
    print(f"  {name}: {info['count']} matches in {info['file']}")

# Now check challengers/ITF if we have that data
print("\nChecking for ITF/Challenger data files...")
import os
raw_dir = 'tennis/data/raw'
for f in os.listdir(raw_dir):
    if 'chall' in f.lower() or 'itf' in f.lower() or 'future' in f.lower():
        print(f"  Found: {f}")
