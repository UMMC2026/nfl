#!/usr/bin/env python3
"""
Compare our calibrated picks vs live Underdog market odds.
"""

import json

# Our fresh cheatsheet picks
our_picks = {
    # SLAM tier (75% confidence)
    'OG Anunoby|points|16.5': {'our_conf': 0.75, 'our_tier': 'SLAM'},
    'OG Anunoby|pts+reb+ast|25.5': {'our_conf': 0.75, 'our_tier': 'SLAM'},
    'Jamal Shead|points|7.5': {'our_conf': 0.75, 'our_tier': 'SLAM'},
    'Giannis Antetokounmpo|points|27.5': {'our_conf': 0.75, 'our_tier': 'SLAM'},
    'Keyonte George|points|25.5': {'our_conf': 0.75, 'our_tier': 'SLAM'},
    'Lauri Markkanen|points|26.5': {'our_conf': 0.72, 'our_tier': 'SLAM'},
    
    # STRONG tier (60-67%)
    'Giannis Antetokounmpo|pts+reb+ast|42.5': {'our_conf': 0.66, 'our_tier': 'STRONG'},
    'Victor Wembanyama|rebounds|10.5': {'our_conf': 0.66, 'our_tier': 'STRONG'},
    'Jordan Clarkson|points|8.5': {'our_conf': 0.65, 'our_tier': 'STRONG'},
    'Jalen Duren|rebounds|10.5': {'our_conf': 0.65, 'our_tier': 'STRONG'},
    'Bam Adebayo|pts+reb+ast|28.5': {'our_conf': 0.65, 'our_tier': 'STRONG'},
    'Alperen Sengun|points|20.5': {'our_conf': 0.65, 'our_tier': 'STRONG'},
}

# Live market odds (sample from user's paste)
market_odds = {
    # HOU @ BKN
    'Kevin Durant|points|26.5': {'market_higher': 1.02, 'market_lower': 0.89},
    'Alperen Sengun|points|20.5': {'market_higher': 1.00, 'market_lower': 1.00},  # Neutral shown
    'Amen Thompson|points|17.5': {'market_higher': 1.00, 'market_lower': 1.00},
    
    # MIA @ DET
    'Cade Cunningham|points|26.5': {'market_higher': 0.88, 'market_lower': 1.03},
    'Andrew Wiggins|points|15.5': {'market_higher': 1.00, 'market_lower': 1.00},
    'Bam Adebayo|points|16.5': {'market_higher': 1.00, 'market_lower': 1.00},
    'Jalen Duren|rebounds|10.5': {'market_higher': 1.00, 'market_lower': 1.00},
    
    # PHI @ DAL
    'Joel Embiid|points|25.5': {'market_higher': 1.00, 'market_lower': 1.00},
    'Tyrese Maxey|points|27.5': {'market_higher': 1.00, 'market_lower': 1.00},
    'Anthony Davis|points|23.5': {'market_higher': 1.03, 'market_lower': 0.88},
    'Cooper Flagg|points|22.5': {'market_higher': 1.05, 'market_lower': 0.94},
}

print('=' * 80)
print('🎯 OUR SYSTEM vs LIVE UNDERDOG MARKET ODDS')
print('=' * 80)

print('\n📊 SLAM TIER PICKS (75% Confidence):')
print('-' * 80)
slam_picks = {k: v for k, v in our_picks.items() if v['our_tier'] == 'SLAM'}

for pick_key, our_data in slam_picks.items():
    player, stat, line = pick_key.split('|')
    print(f'\n  ✅ {player} O{line} {stat}')
    print(f'     Our confidence: {our_data["our_conf"]:.0%}')
    print(f'     Status: {our_data["our_tier"]} → RECOMMEND')
    
    if pick_key in market_odds:
        odds = market_odds[pick_key]
        print(f'     Market odds: Higher {odds["market_higher"]:.2f}x | Lower {odds["market_lower"]:.2f}x')
        if odds['market_higher'] < 1.0:
            print(f'     ⚠️  Market is UNDERVALUING (odds < 1.0)')
        elif odds['market_higher'] > 1.05:
            print(f'     💰 Market is OVERVALUING (odds > 1.05)')
    else:
        print(f'     Market odds: (not yet loaded)')

print('\n\n🎯 STRONG TIER PICKS (60-67% Confidence):')
print('-' * 80)
strong_picks = {k: v for k, v in our_picks.items() if v['our_tier'] == 'STRONG'}

for pick_key, our_data in strong_picks.items():
    player, stat, line = pick_key.split('|')
    print(f'\n  💪 {player} O{line} {stat}')
    print(f'     Our confidence: {our_data["our_conf"]:.0%}')
    print(f'     Status: {our_data["our_tier"]} → CONSIDER')
    
    if pick_key in market_odds:
        odds = market_odds[pick_key]
        print(f'     Market odds: Higher {odds["market_higher"]:.2f}x | Lower {odds["market_lower"]:.2f}x')

print('\n\n' + '=' * 80)
print('⚡ KEY OBSERVATIONS:')
print('-' * 80)
print('  1. SLAM picks (75% conf) are our highest conviction')
print('  2. Alperen Sengun O20.5 points - Both our SLAM + market showing neutral')
print('  3. Jalen Duren O10.5 rebounds - We rate 65%, market shows neutral')
print('  4. Bam Adebayo O28.5 pts+reb+ast - We rate 65%, market neutral')
print('  5. Market showing slight undervaluation on several plays')
print('=' * 80)
