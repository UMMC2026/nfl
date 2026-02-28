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
    before = find_latest('outputs/MC_HOU_PIT_JAN12_*.json')
    after = find_latest('outputs/MC_HOU_PIT_JAN12_*.json')
    if not before or not after:
        print('Could not find MC simulation files.')
        return
    before_data = load_json(before)
    after_data = load_json(after)
    print('\n--- Monte Carlo Comparison (Before vs After Optimization) ---')
    print(f'Before: {before}')
    print(f'After:  {after}')
    print('\nTop 5 Props Before:')
    for prop in sorted(before_data, key=lambda x: x['prob_hit'], reverse=True)[:5]:
        print(f"{prop['player']} {prop['stat']} {prop['direction']} {prop['line']}: {prop['prob_hit']*100:.1f}%")
    print('\nTop 5 Props After:')
    for prop in sorted(after_data, key=lambda x: x['prob_hit'], reverse=True)[:5]:
        print(f"{prop['player']} {prop['stat']} {prop['direction']} {prop['line']}: {prop['prob_hit']*100:.1f}%")
    print('\n--- End of Comparison ---')

if __name__ == '__main__':
    main()
