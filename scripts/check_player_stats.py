"""Check player stats after update."""
import json

with open('tennis/data/player_stats.json', 'r', encoding='utf-8') as f:
    stats = json.load(f)

targets = ['Xinyu Wang', 'Xin Yu Wang', 'Xiyu Wang', 'Misaki Matsuda', 'Miho Kuramochi']
print('Player stats found:')
for t in targets:
    if t in stats:
        s = stats[t]
        print(f"  {t}: {s.get('matches_analyzed', 0)} matches, win% = {s.get('win_pct_L10', 0):.1%}")
    else:
        # Try case-insensitive search
        found = None
        for name in stats:
            if t.lower() == name.lower():
                found = name
                break
        if found:
            s = stats[found]
            print(f"  {found}: {s.get('matches_analyzed', 0)} matches, win% = {s.get('win_pct_L10', 0):.1%}")
        else:
            print(f"  {t}: NOT FOUND")

print(f"\nTotal players in database: {len(stats)}")
