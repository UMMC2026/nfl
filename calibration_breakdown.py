#!/usr/bin/env python3
"""
CALIBRATION BREAKDOWN BY STAT TYPE
Based on 97 resolved picks from calibration_history.csv
"""

import pandas as pd

def main():
    # Load calibration data
    df = pd.read_csv('calibration_history.csv')
    print('='*80)
    print('CALIBRATION BREAKDOWN BY STAT TYPE')
    print('='*80)

    # Filter to resolved picks only
    resolved = df[df['outcome'].isin(['HIT', 'MISS'])].copy()
    print(f'Total resolved picks: {len(resolved)}')

    # Normalize stat names
    def normalize_stat(s):
        s = str(s).lower().strip()
        mapping = {
            'points': 'pts', 'rebounds': 'reb', 'assists': 'ast',
            'pts+reb+ast': 'pra', '3ptm': '3pm', 'threes': '3pm',
        }
        return mapping.get(s, s)

    resolved['stat_normalized'] = resolved['stat'].apply(normalize_stat)

    # Calculate hit rate by stat
    print('\n' + '-'*80)
    print('HIT RATE BY STAT TYPE')
    print('-'*80)
    
    stat_groups = resolved.groupby('stat_normalized')
    stat_results = []
    for stat_name, group in stat_groups:
        hits = sum(group['outcome'] == 'HIT')
        total = len(group)
        hit_rate = hits / total * 100
        stat_results.append({
            'stat': stat_name,
            'hits': hits,
            'total': total,
            'hit_rate': hit_rate
        })
    
    stat_df = pd.DataFrame(stat_results).sort_values('hit_rate', ascending=False)
    
    print(f"{'Stat':<15} {'Hits':>6} {'Total':>6} {'Hit Rate':>10}  Status")
    print('-'*55)
    for _, row in stat_df.iterrows():
        if row['total'] >= 3:  # Only show stats with 3+ picks
            if row['hit_rate'] >= 55:
                status = '✅ PROFITABLE'
            elif row['hit_rate'] >= 45:
                status = '⚠️ BREAK-EVEN'
            else:
                status = '❌ LOSING'
            print(f"{row['stat']:<15} {int(row['hits']):>6} {int(row['total']):>6} {row['hit_rate']:>9.1f}%  {status}")

    # Direction breakdown
    print('\n' + '-'*80)
    print('HIT RATE BY DIRECTION')
    print('-'*80)
    
    dir_groups = resolved.groupby('direction')
    for dir_name, group in dir_groups:
        hits = sum(group['outcome'] == 'HIT')
        total = len(group)
        hit_rate = hits / total * 100
        print(f"{dir_name:<15} {hits:>6} {total:>6} {hit_rate:>9.1f}%")

    # Sport breakdown
    print('\n' + '-'*80)
    print('HIT RATE BY SPORT')
    print('-'*80)
    if 'sport' in resolved.columns:
        sport_groups = resolved.groupby('sport')
        for sport_name, group in sport_groups:
            hits = sum(group['outcome'] == 'HIT')
            total = len(group)
            hit_rate = hits / total * 100
            print(f"{sport_name:<15} {hits:>6} {total:>6} {hit_rate:>9.1f}%")

    # COMBO: Direction + Stat
    print('\n' + '-'*80)
    print('HIT RATE BY STAT + DIRECTION (3+ picks)')
    print('-'*80)
    
    combo_results = []
    for (stat, direction), group in resolved.groupby(['stat_normalized', 'direction']):
        if len(group) >= 3:
            hits = sum(group['outcome'] == 'HIT')
            total = len(group)
            hit_rate = hits / total * 100
            combo_results.append({
                'combo': f"{stat} {direction}",
                'hits': hits,
                'total': total,
                'hit_rate': hit_rate
            })
    
    combo_df = pd.DataFrame(combo_results).sort_values('hit_rate', ascending=False)
    print(f"{'Combo':<25} {'Hits':>6} {'Total':>6} {'Hit Rate':>10}")
    print('-'*55)
    for _, row in combo_df.iterrows():
        print(f"{row['combo']:<25} {int(row['hits']):>6} {int(row['total']):>6} {row['hit_rate']:>9.1f}%")

    # KEY FINDING
    print('\n' + '='*80)
    print('KEY FINDINGS')
    print('='*80)
    
    # Best performers
    profitable = stat_df[stat_df['hit_rate'] >= 55]
    if len(profitable) > 0:
        print("\n✅ FOCUS ON THESE STATS:")
        for _, row in profitable.iterrows():
            if row['total'] >= 3:
                print(f"   - {row['stat'].upper()}: {row['hit_rate']:.1f}% ({int(row['hits'])}/{int(row['total'])})")
    
    # Worst performers
    losing = stat_df[stat_df['hit_rate'] < 45]
    if len(losing) > 0:
        print("\n❌ AVOID THESE STATS:")
        for _, row in losing.iterrows():
            if row['total'] >= 3:
                print(f"   - {row['stat'].upper()}: {row['hit_rate']:.1f}% ({int(row['hits'])}/{int(row['total'])})")

if __name__ == '__main__':
    main()
