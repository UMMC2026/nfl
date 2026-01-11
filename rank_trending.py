import json
from ufa.analysis.prob import prob_hit
from ufa.ingest.hydrate import hydrate_recent_values

# Load props
with open('hou_dal_props.json') as f:
    props = json.load(f)

ranked = []
for p in props:
    try:
        # Hydrate recent stats
        recent = hydrate_recent_values(p['sport'], p['player'], p['stat'], nba_season='2024-25')
        if recent:
            prob = prob_hit(p['line'], p['direction'], recent_values=recent)
            ranked.append({
                'player': p['player'],
                'stat': p['stat'],
                'line': p['line'],
                'direction': p['direction'],
                'prob': prob,
                'recent_avg': sum(recent)/len(recent),
                'recent': recent[-5:]
            })
    except Exception as e:
        print(f'Error hydrating {p["player"]} {p["stat"]}: {e}')

# Sort by probability (descending)
ranked.sort(key=lambda x: x['prob'], reverse=True)

print('\n=== HOU vs DAL (Sat 7:40pm) - Trending Props Ranked ===\n')
for i, r in enumerate(ranked, 1):
    print(f'{i}. {r["player"]} {r["stat"].upper()} {r["line"]} ({r["direction"].upper()})')
    print(f'   Hit Probability: {r["prob"]*100:.1f}%')
    print(f'   Recent Average: {r["recent_avg"]:.1f}')
    recent_rounded = [round(x, 1) for x in r["recent"]]
    print(f'   Last 5 games: {recent_rounded}')
    print()
