import json

picks = json.load(open('picks.json'))
game_picks = [p for p in picks if p.get('team') in ['IND', 'HOU']]

print(f'IND/HOU picks: {len(game_picks)}')
print()
for p in game_picks[:15]:
    print(f"{p['player']:25} ({p['team']}) - {p['stat']:20}: {p['line']:6} {p['direction']}")
