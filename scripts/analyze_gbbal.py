"""
GB vs BAL - December 27, 2025 - 7:00 PM CST
Underdog Fantasy Props Analysis
"""
from collections import defaultdict

picks = []

# JOSH JACOBS (GB RB)
picks.extend([
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.06, 'lower_mult': 0.86},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Rush Yards', 'line': 52.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Receiving Yards', 'line': 8.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Receptions', 'line': 1.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Rush Attempts', 'line': 15.5, 'higher_mult': 1.03, 'lower_mult': 0.88},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Fantasy Points', 'line': 12.55, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Rush+Rec Yards', 'line': 60.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'Longest Rush', 'line': 11.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 2.77, 'lower_mult': None},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': '1H Receptions', 'line': 0.5, 'higher_mult': 0.80, 'lower_mult': 1.08},
    {'player': 'Josh Jacobs', 'team': 'GB', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.46, 'lower_mult': 0.64},
])

# DERRICK HENRY (BAL RB)
picks.extend([
    {'player': 'Derrick Henry', 'team': 'BAL', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Derrick Henry', 'team': 'BAL', 'stat': 'Rush Yards', 'line': 74.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Derrick Henry', 'team': 'BAL', 'stat': 'Receiving Yards', 'line': 3.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Derrick Henry', 'team': 'BAL', 'stat': 'Receptions', 'line': 0.5, 'higher_mult': 0.73, 'lower_mult': 1.17},
])

# ZAY FLOWERS (BAL WR)
picks.extend([
    {'player': 'Zay Flowers', 'team': 'BAL', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.86, 'lower_mult': 0.60},
    {'player': 'Zay Flowers', 'team': 'BAL', 'stat': 'Receiving Yards', 'line': 53.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Zay Flowers', 'team': 'BAL', 'stat': 'Receptions', 'line': 4.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Zay Flowers', 'team': 'BAL', 'stat': 'Fantasy Points', 'line': 8.15, 'higher_mult': 1.0, 'lower_mult': 1.0},
])

# JAYDEN REED (GB WR)
picks.extend([
    {'player': 'Jayden Reed', 'team': 'GB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.91, 'lower_mult': 0.60},
    {'player': 'Jayden Reed', 'team': 'GB', 'stat': 'Rush Yards', 'line': 2.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Jayden Reed', 'team': 'GB', 'stat': 'Receiving Yards', 'line': 27.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Jayden Reed', 'team': 'GB', 'stat': 'Receptions', 'line': 2.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Jayden Reed', 'team': 'GB', 'stat': 'Targets', 'line': 3.5, 'higher_mult': 0.78, 'lower_mult': 1.03},
    {'player': 'Jayden Reed', 'team': 'GB', 'stat': '1H Receptions', 'line': 1.5, 'higher_mult': 1.05, 'lower_mult': 0.82},
])

# MARK ANDREWS (BAL TE)
picks.extend([
    {'player': 'Mark Andrews', 'team': 'BAL', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.10, 'lower_mult': None},
    {'player': 'Mark Andrews', 'team': 'BAL', 'stat': 'Receiving Yards', 'line': 22.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Mark Andrews', 'team': 'BAL', 'stat': 'Receptions', 'line': 2.5, 'higher_mult': 0.86, 'lower_mult': 1.07},
    {'player': 'Mark Andrews', 'team': 'BAL', 'stat': 'Targets', 'line': 3.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
])

# ROMEO DOUBS (GB WR)
picks.extend([
    {'player': 'Romeo Doubs', 'team': 'GB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.94, 'lower_mult': 0.60},
    {'player': 'Romeo Doubs', 'team': 'GB', 'stat': 'Receiving Yards', 'line': 25.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Romeo Doubs', 'team': 'GB', 'stat': 'Receptions', 'line': 2.5, 'higher_mult': 1.07, 'lower_mult': 0.79},
    {'player': 'Romeo Doubs', 'team': 'GB', 'stat': 'Targets', 'line': 3.5, 'higher_mult': 0.88, 'lower_mult': 1.03},
])

# MALIK WILLIS (GB QB)
picks.extend([
    {'player': 'Malik Willis', 'team': 'GB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.89, 'lower_mult': 0.60},
    {'player': 'Malik Willis', 'team': 'GB', 'stat': 'Pass Yards', 'line': 164.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Malik Willis', 'team': 'GB', 'stat': 'Pass TDs', 'line': 0.5, 'higher_mult': 0.68, 'lower_mult': 1.36},
    {'player': 'Malik Willis', 'team': 'GB', 'stat': 'Rush Yards', 'line': 32.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
])

# BRANDON MCMANUS (GB K)
picks.extend([
    {'player': 'Brandon McManus', 'team': 'GB', 'stat': 'FG Made', 'line': 1.5, 'higher_mult': 0.86, 'lower_mult': 1.04},
    {'player': 'Brandon McManus', 'team': 'GB', 'stat': 'XP Made', 'line': 1.5, 'higher_mult': 0.76, 'lower_mult': 1.09},
    {'player': 'Brandon McManus', 'team': 'GB', 'stat': 'Kicking Points', 'line': 6.5, 'higher_mult': 0.85, 'lower_mult': 1.05},
])

print('=' * 90)
print('GB vs BAL - Tonight 7:00 PM CST - UNDERDOG PROPS ANALYSIS')
print('=' * 90)

# Group by player
by_player = defaultdict(list)
for p in picks:
    by_player[p['player']].append(p)

# Find BOOSTED plays (mult > 1.0 = getting extra value)
print('\n' + '🔥 BOOSTED PLAYS (Higher Multiplier = Potential Value)'.center(90))
print('=' * 90)

boosted = []
for p in picks:
    h = p.get('higher_mult') or 0
    l = p.get('lower_mult') or 0
    if h > 1.0:
        boosted.append((p['player'], p['stat'], p['line'], 'HIGHER', h))
    if l > 1.0:
        boosted.append((p['player'], p['stat'], p['line'], 'LOWER', l))

boosted.sort(key=lambda x: x[4], reverse=True)

print(f"{'Player':<20} {'Stat':<20} {'Line':<8} {'Pick':<8} {'Mult':<8}")
print('-' * 70)
for b in boosted[:15]:
    print(f"{b[0]:<20} {b[1]:<20} {b[2]:<8} {b[3]:<8} {b[4]:.2f}x")

# Best correlated picks (same game, different players)
print('\n' + '🎯 RECOMMENDED CORRELATED PLAYS'.center(90))
print('=' * 90)

print("""
STACK 1 - GB OFFENSE (Malik Willis game)
  • Malik Willis OVER 32.5 Rush Yards (mobile QB)
  • Josh Jacobs OVER 52.5 Rush Yards 
  • Jayden Reed OVER 27.5 Rec Yards
  
STACK 2 - BAL GROUND GAME  
  • Derrick Henry OVER 74.5 Rush Yards (workhorse)
  • Derrick Henry LOWER 0.5 Receptions (+17%)
  
STACK 3 - CONTRARIAN
  • Malik Willis LOWER 0.5 Pass TDs (+36%) - backup QB
  • Josh Jacobs LOWER 0.5 1H Receptions (+8%)

VALUE TD PLAYS (Boosted):
  • Josh Jacobs OVER 0.5 TDs (1.06x)
  • Josh Jacobs OVER 0.5 1H TDs (1.46x) 
""")

print('\n' + 'FULL BREAKDOWN BY PLAYER'.center(90))
print('=' * 90)

for player in ['Derrick Henry', 'Josh Jacobs', 'Zay Flowers', 'Jayden Reed', 'Mark Andrews', 'Romeo Doubs', 'Malik Willis', 'Brandon McManus']:
    if player not in by_player:
        continue
    team = by_player[player][0]['team']
    print(f'\n### {player} ({team})')
    print('-' * 70)
    print(f"{'Stat':<20} {'Line':<8} {'Higher':<10} {'Lower':<10} {'Edge?':<15}")
    print('-' * 70)
    for p in by_player[player]:
        h_mult = p.get('higher_mult') or 0
        l_mult = p.get('lower_mult') or 0
        
        edge = ''
        if h_mult > 1.0:
            edge = f'✅ HIGHER +{int((h_mult-1)*100)}%'
        elif l_mult > 1.0:
            edge = f'✅ LOWER +{int((l_mult-1)*100)}%'
        
        h_str = f'{h_mult:.2f}x' if h_mult else '-'
        l_str = f'{l_mult:.2f}x' if l_mult else '-'
        print(f"{p['stat']:<20} {p['line']:<8} {h_str:<10} {l_str:<10} {edge:<15}")
