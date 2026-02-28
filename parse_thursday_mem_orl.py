#!/usr/bin/env python3
"""
Parse Thursday MEM @ ORL slate (1:00PM CST)
All props with complete stat type coverage
"""

import json

# Thursday MEM @ ORL props
THURSDAY_MEM_ORL_PROPS = [
    # Paolo Banchero (ORL)
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': 'points', 'line': 22.5, 'direction': 'higher'},
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': 'pra', 'line': 36.5, 'direction': 'higher'},
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': 'rebounds', 'line': 8.5, 'direction': 'higher'},
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': 'assists', 'line': 5.5, 'direction': 'higher'},
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': '3pm', 'line': 0.5, 'direction': 'higher'},
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': 'ra', 'line': 13.5, 'direction': 'higher'},
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': 'pr', 'line': 31.5, 'direction': 'higher'},
    {'player': 'Paolo Banchero', 'team': 'ORL', 'stat': 'pa', 'line': 27.5, 'direction': 'higher'},
    
    # Franz Wagner (ORL)
    {'player': 'Franz Wagner', 'team': 'ORL', 'stat': 'points', 'line': 15.5, 'direction': 'higher'},
    {'player': 'Franz Wagner', 'team': 'ORL', 'stat': 'pra', 'line': 23.5, 'direction': 'higher'},
    {'player': 'Franz Wagner', 'team': 'ORL', 'stat': 'rebounds', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Franz Wagner', 'team': 'ORL', 'stat': 'assists', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Franz Wagner', 'team': 'ORL', 'stat': '3pm', 'line': 0.5, 'direction': 'higher'},
    {'player': 'Franz Wagner', 'team': 'ORL', 'stat': 'ra', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Franz Wagner', 'team': 'ORL', 'stat': 'pr', 'line': 20.5, 'direction': 'higher'},
    
    # Wendell Carter Jr (ORL)
    {'player': 'Wendell Carter Jr', 'team': 'ORL', 'stat': 'points', 'line': 11.5, 'direction': 'higher'},
    {'player': 'Wendell Carter Jr', 'team': 'ORL', 'stat': 'pra', 'line': 21.5, 'direction': 'higher'},
    {'player': 'Wendell Carter Jr', 'team': 'ORL', 'stat': 'rebounds', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Wendell Carter Jr', 'team': 'ORL', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Wendell Carter Jr', 'team': 'ORL', 'stat': '3pm', 'line': 0.5, 'direction': 'higher'},
    {'player': 'Wendell Carter Jr', 'team': 'ORL', 'stat': 'ra', 'line': 10.5, 'direction': 'higher'},
    {'player': 'Wendell Carter Jr', 'team': 'ORL', 'stat': 'pr', 'line': 19.5, 'direction': 'higher'},
    
    # Anthony Black (ORL)
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'points', 'line': 15.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'pra', 'line': 24.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'rebounds', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'assists', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'ra', 'line': 8.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'pr', 'line': 20.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'pa', 'line': 20.5, 'direction': 'higher'},
    {'player': 'Anthony Black', 'team': 'ORL', 'stat': 'steals', 'line': 1.5, 'direction': 'higher'},
    
    # Tristan da Silva (ORL)
    {'player': 'Tristan da Silva', 'team': 'ORL', 'stat': 'points', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Tristan da Silva', 'team': 'ORL', 'stat': 'pra', 'line': 11.5, 'direction': 'higher'},
    {'player': 'Tristan da Silva', 'team': 'ORL', 'stat': 'rebounds', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Tristan da Silva', 'team': 'ORL', 'stat': 'assists', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Tristan da Silva', 'team': 'ORL', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    
    # Noah Penda (ORL)
    {'player': 'Noah Penda', 'team': 'ORL', 'stat': 'points', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Noah Penda', 'team': 'ORL', 'stat': 'pra', 'line': 10.5, 'direction': 'higher'},
    {'player': 'Noah Penda', 'team': 'ORL', 'stat': 'rebounds', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Noah Penda', 'team': 'ORL', 'stat': 'assists', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Noah Penda', 'team': 'ORL', 'stat': '3pm', 'line': 0.5, 'direction': 'higher'},
    
    # Desmond Bane (MEM)
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': 'points', 'line': 19.5, 'direction': 'higher'},
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': 'pra', 'line': 28.5, 'direction': 'higher'},
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': 'rebounds', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': 'assists', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': 'ra', 'line': 8.5, 'direction': 'higher'},
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': 'pr', 'line': 24.5, 'direction': 'higher'},
    {'player': 'Desmond Bane', 'team': 'MEM', 'stat': 'pa', 'line': 24.5, 'direction': 'higher'},
    
    # Jaren Jackson Jr (MEM)
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'points', 'line': 19.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'pra', 'line': 27.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'rebounds', 'line': 5.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'ra', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'pr', 'line': 25.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'pa', 'line': 21.5, 'direction': 'higher'},
    {'player': 'Jaren Jackson Jr', 'team': 'MEM', 'stat': 'blocks', 'line': 1.5, 'direction': 'higher'},
    
    # Santi Aldama (MEM)
    {'player': 'Santi Aldama', 'team': 'MEM', 'stat': 'points', 'line': 14.5, 'direction': 'higher'},
    {'player': 'Santi Aldama', 'team': 'MEM', 'stat': 'pra', 'line': 24.5, 'direction': 'higher'},
    {'player': 'Santi Aldama', 'team': 'MEM', 'stat': 'rebounds', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Santi Aldama', 'team': 'MEM', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Santi Aldama', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Santi Aldama', 'team': 'MEM', 'stat': 'ra', 'line': 10.5, 'direction': 'higher'},
    {'player': 'Santi Aldama', 'team': 'MEM', 'stat': 'pr', 'line': 21.5, 'direction': 'higher'},
    
    # Vince Williams Jr (MEM)
    {'player': 'Vince Williams Jr', 'team': 'MEM', 'stat': 'points', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Vince Williams Jr', 'team': 'MEM', 'stat': 'pra', 'line': 15.5, 'direction': 'higher'},
    {'player': 'Vince Williams Jr', 'team': 'MEM', 'stat': 'rebounds', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Vince Williams Jr', 'team': 'MEM', 'stat': 'assists', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Vince Williams Jr', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Vince Williams Jr', 'team': 'MEM', 'stat': 'ra', 'line': 8.5, 'direction': 'higher'},
    
    # Cam Spencer (MEM)
    {'player': 'Cam Spencer', 'team': 'MEM', 'stat': 'points', 'line': 12.5, 'direction': 'higher'},
    {'player': 'Cam Spencer', 'team': 'MEM', 'stat': 'pra', 'line': 23.5, 'direction': 'higher'},
    {'player': 'Cam Spencer', 'team': 'MEM', 'stat': 'rebounds', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Cam Spencer', 'team': 'MEM', 'stat': 'assists', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Cam Spencer', 'team': 'MEM', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Cam Spencer', 'team': 'MEM', 'stat': 'ra', 'line': 10.5, 'direction': 'higher'},
    {'player': 'Cam Spencer', 'team': 'MEM', 'stat': 'pa', 'line': 20.5, 'direction': 'higher'},
    
    # Jock Landale (MEM)
    {'player': 'Jock Landale', 'team': 'MEM', 'stat': 'points', 'line': 11.5, 'direction': 'higher'},
    {'player': 'Jock Landale', 'team': 'MEM', 'stat': 'pra', 'line': 20.5, 'direction': 'higher'},
    {'player': 'Jock Landale', 'team': 'MEM', 'stat': 'rebounds', 'line': 6.5, 'direction': 'higher'},
    {'player': 'Jock Landale', 'team': 'MEM', 'stat': 'assists', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Jock Landale', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    
    # Kentavious Caldwell-Pope (MEM)
    {'player': 'Kentavious Caldwell-Pope', 'team': 'MEM', 'stat': 'points', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Kentavious Caldwell-Pope', 'team': 'MEM', 'stat': 'pra', 'line': 11.5, 'direction': 'higher'},
    {'player': 'Kentavious Caldwell-Pope', 'team': 'MEM', 'stat': 'rebounds', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Kentavious Caldwell-Pope', 'team': 'MEM', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Kentavious Caldwell-Pope', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    
    # Cedric Coward (MEM)
    {'player': 'Cedric Coward', 'team': 'MEM', 'stat': 'points', 'line': 13.5, 'direction': 'higher'},
    {'player': 'Cedric Coward', 'team': 'MEM', 'stat': 'pra', 'line': 22.5, 'direction': 'higher'},
    {'player': 'Cedric Coward', 'team': 'MEM', 'stat': 'rebounds', 'line': 6.5, 'direction': 'higher'},
    {'player': 'Cedric Coward', 'team': 'MEM', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Cedric Coward', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Cedric Coward', 'team': 'MEM', 'stat': 'ra', 'line': 9.5, 'direction': 'higher'},
    {'player': 'Cedric Coward', 'team': 'MEM', 'stat': 'pr', 'line': 19.5, 'direction': 'higher'},
    
    # Jaylen Wells (MEM)
    {'player': 'Jaylen Wells', 'team': 'MEM', 'stat': 'points', 'line': 11.5, 'direction': 'higher'},
    {'player': 'Jaylen Wells', 'team': 'MEM', 'stat': 'pra', 'line': 16.5, 'direction': 'higher'},
    {'player': 'Jaylen Wells', 'team': 'MEM', 'stat': 'rebounds', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Jaylen Wells', 'team': 'MEM', 'stat': 'assists', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Jaylen Wells', 'team': 'MEM', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
]

# Save to JSON
output_file = "nba_thursday_mem_orl.json"
output_data = {
    "slate": "Thursday Jan 16, 2026 - 1:00PM CST",
    "game": "MEM @ ORL",
    "total_props": len(THURSDAY_MEM_ORL_PROPS),
    "plays": THURSDAY_MEM_ORL_PROPS
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, indent=2)

print(f"✅ Parsed {len(THURSDAY_MEM_ORL_PROPS)} props for MEM @ ORL")
print(f"📄 Saved to: {output_file}")

# Show breakdown
from collections import Counter
stat_counts = Counter([p['stat'] for p in THURSDAY_MEM_ORL_PROPS])
player_counts = Counter([p['player'] for p in THURSDAY_MEM_ORL_PROPS])

print(f"\n📊 STAT TYPE BREAKDOWN:")
for stat, count in sorted(stat_counts.items(), key=lambda x: -x[1]):
    print(f"  {stat.upper()}: {count} props")

print(f"\n👤 PLAYER BREAKDOWN:")
for player, count in sorted(player_counts.items(), key=lambda x: -x[1])[:10]:
    print(f"  {player}: {count} props")
