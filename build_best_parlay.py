import json
import os
from glob import glob

def find_latest(pattern):
    files = glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def main():
    mc_file = find_latest('outputs/MC_HOU_PIT_JAN12_*.json')
    if not mc_file:
        print('No MC simulation file found.')
        return
    data = load_json(mc_file)
    # Top 5 overs (highest prob_hit, direction == 'higher')
    overs = sorted([p for p in data if p['direction'] == 'higher'], key=lambda x: x['prob_hit'], reverse=True)[:5]
    # Top 5 unders (lowest prob_hit, direction == 'higher')
    unders = sorted([p for p in data if p['direction'] == 'higher'], key=lambda x: x['prob_hit'])[:5]
    # Best parlay (top 5 unique players, highest prob_hit)
    best = []
    seen = set()
    for prop in sorted(data, key=lambda x: x['prob_hit'], reverse=True):
        if prop['player'] not in seen:
            best.append(prop)
            seen.add(prop['player'])
        if len(best) == 5:
            break
    print('\n--- Best Parlay (Top 5 Unique Players) ---')
    for prop in best:
        print(f"{prop['player']} {prop['stat']} {prop['direction']} {prop['line']}: {prop['prob_hit']*100:.1f}%")
    print('--- End of Parlay ---')
    print('\n--- Top 5 Overs ---')
    for prop in overs:
        print(f"{prop['player']} {prop['stat']} OVER {prop['line']}: {prop['prob_hit']*100:.1f}%")
    print('--- End of Overs ---')
    print('\n--- Top 5 Unders ---')
    for prop in unders:
        print(f"{prop['player']} {prop['stat']} UNDER {prop['line']}: {(1-prop['prob_hit'])*100:.1f}%")
    print('--- End of Unders ---')
    # Save to file
    with open('outputs/BEST_PARLAY.txt', 'w') as f:
        f.write('--- Best Parlay (Top 5 Unique Players) ---\n')
        for prop in best:
            f.write(f"{prop['player']} {prop['stat']} {prop['direction']} {prop['line']}: {prop['prob_hit']*100:.1f}%\n")
        f.write('--- End of Parlay ---\n\n')
        f.write('--- Top 5 Overs ---\n')
        for prop in overs:
            f.write(f"{prop['player']} {prop['stat']} OVER {prop['line']}: {prop['prob_hit']*100:.1f}%\n")
        f.write('--- End of Overs ---\n\n')
        f.write('--- Top 5 Unders ---\n')
        for prop in unders:
            f.write(f"{prop['player']} {prop['stat']} UNDER {prop['line']}: {(1-prop['prob_hit'])*100:.1f}%\n")
        f.write('--- End of Unders ---\n')
    print('Saved to outputs/BEST_PARLAY.txt')

if __name__ == '__main__':
    main()
