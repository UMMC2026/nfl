import json

data = json.load(open('outputs/OKC_HOU_RISK_FIRST_20260115.json'))

hou_results = [r for r in data['results'] if r.get('team') == 'HOU']
print(f'Total HOU props analyzed: {len(hou_results)}')
print(f'HOU BLOCKED: {len([r for r in hou_results if r["decision"] == "BLOCKED"])}')
print(f'HOU NO_PLAY: {len([r for r in hou_results if r["decision"] == "NO_PLAY"])}')
print(f'HOU LEAN: {len([r for r in hou_results if r["decision"] == "LEAN"])}')
print(f'HOU PLAY: {len([r for r in hou_results if r["decision"] == "PLAY"])}')
print(f'HOU SKIP: {len([r for r in hou_results if r["decision"] == "SKIP"])}')

print(f'\nTop HOU block reasons:')
block_reasons = {}
for r in hou_results:
    if r['decision'] == 'BLOCKED':
        reason = r.get('block_reason', r.get('reasoning', 'Unknown'))
        block_reasons[reason] = block_reasons.get(reason, 0) + 1

for reason, count in sorted(block_reasons.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f'  {count}x - {reason[:100]}')

print(f'\nHOU NO_PLAY samples (low edges):')
no_play = [r for r in hou_results if r['decision'] == 'NO_PLAY']
for r in no_play[:5]:
    print(f"  {r['player']} {r['stat']} {r['direction']} {r['line']}: Edge={r['edge_quality']}, Conf={r['effective_confidence']:.1f}%")
