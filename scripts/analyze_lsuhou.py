"""
LSU @ Houston - December 27, 2025 - 8:15 PM CST
Underdog Fantasy Props Analysis - Bowl Game
"""
from collections import defaultdict

picks = []

# MICHAEL VAN BUREN (LSU QB)
picks.extend([
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.56, 'lower_mult': None},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'Pass Yards', 'line': 207.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'Rush Yards', 'line': 7.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'Pass TDs', 'line': 1.5, 'higher_mult': 1.15, 'lower_mult': 0.73},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'INTs Thrown', 'line': 0.5, 'higher_mult': 0.81, 'lower_mult': 1.05},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 7.26, 'lower_mult': None},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'Pass+Rush Yards', 'line': 202.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'Fantasy Points', 'line': 14.05, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Michael Van Buren', 'team': 'LSU', 'stat': 'Longest Completion', 'line': 38.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
])

# HARLEM BERRY (LSU RB)
picks.extend([
    {'player': 'Harlem Berry', 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.08, 'lower_mult': None},
    {'player': 'Harlem Berry', 'team': 'LSU', 'stat': 'Rush Yards', 'line': 54.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Harlem Berry', 'team': 'LSU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 3.60, 'lower_mult': None},
    {'player': 'Harlem Berry', 'team': 'LSU', 'stat': 'Longest Rush', 'line': 16.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
])

# CADEN DURHAM (LSU RB)
picks.extend([
    {'player': 'Caden Durham', 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.33, 'lower_mult': None},
    {'player': 'Caden Durham', 'team': 'LSU', 'stat': 'Rush Yards', 'line': 27.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Caden Durham', 'team': 'LSU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 6.75, 'lower_mult': None},
    {'player': 'Caden Durham', 'team': 'LSU', 'stat': 'Longest Rush', 'line': 11.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
])

# KYLE PARKER (LSU)
picks.extend([
    {'player': 'Kyle Parker', 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.60, 'lower_mult': None},
    {'player': 'Kyle Parker', 'team': 'LSU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 12.54, 'lower_mult': None},
])

# ZAVION THOMAS (LSU WR)
picks.extend([
    {'player': 'Zavion Thomas', 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.31, 'lower_mult': None},
    {'player': 'Zavion Thomas', 'team': 'LSU', 'stat': 'Receiving Yards', 'line': 40.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Zavion Thomas', 'team': 'LSU', 'stat': 'Receptions', 'line': 3.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Zavion Thomas', 'team': 'LSU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 5.63, 'lower_mult': None},
    {'player': 'Zavion Thomas', 'team': 'LSU', 'stat': 'Longest Reception', 'line': 20.5, 'higher_mult': 1.0, 'lower_mult': None},
])

# BAUER SHARP (LSU)
picks.extend([
    {'player': 'Bauer Sharp', 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.89, 'lower_mult': None},
])

# BARION BROWN (LSU WR)
picks.extend([
    {'player': 'Barion Brown', 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.40, 'lower_mult': None},
    {'player': 'Barion Brown', 'team': 'LSU', 'stat': 'Receiving Yards', 'line': 37.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Barion Brown', 'team': 'LSU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 6.10, 'lower_mult': None},
    {'player': 'Barion Brown', 'team': 'LSU', 'stat': 'Longest Reception', 'line': 18.5, 'higher_mult': 1.0, 'lower_mult': None},
])

# TREY'DEZ GREEN (LSU WR)
picks.extend([
    {'player': "Trey'Dez Green", 'team': 'LSU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.61, 'lower_mult': None},
    {'player': "Trey'Dez Green", 'team': 'LSU', 'stat': 'Receiving Yards', 'line': 30.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': "Trey'Dez Green", 'team': 'LSU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 7.55, 'lower_mult': None},
    {'player': "Trey'Dez Green", 'team': 'LSU', 'stat': 'Longest Reception', 'line': 15.5, 'higher_mult': 1.0, 'lower_mult': None},
])

# DAMIAN RAMOS (LSU K)
picks.extend([
    {'player': 'Damian Ramos', 'team': 'LSU', 'stat': 'FG Made', 'line': 1.5, 'higher_mult': 1.12, 'lower_mult': 0.74},
    {'player': 'Damian Ramos', 'team': 'LSU', 'stat': 'XP Made', 'line': 2.5, 'higher_mult': 1.08, 'lower_mult': 0.83},
    {'player': 'Damian Ramos', 'team': 'LSU', 'stat': 'Kicking Points', 'line': 5.5, 'higher_mult': 0.86, 'lower_mult': 1.06},
])

# === HOUSTON PLAYERS ===

# CONNER WEIGMAN (HOU QB)
picks.extend([
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.08, 'lower_mult': None},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Pass Yards', 'line': 195.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Rush Yards', 'line': 44.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Pass TDs', 'line': 1.5, 'higher_mult': 1.05, 'lower_mult': 0.85},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Pass Attempts', 'line': 26.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Completions', 'line': 16.5, 'higher_mult': 0.87, 'lower_mult': 1.04},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'INTs Thrown', 'line': 0.5, 'higher_mult': 0.73, 'lower_mult': 1.13},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 4.20, 'lower_mult': None},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Pass+Rush Yards', 'line': 250.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Fantasy Points', 'line': 19.35, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Longest Completion', 'line': 39.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Conner Weigman', 'team': 'HOU', 'stat': 'Longest Rush', 'line': 14.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
])

# TANNER KOZIOL (HOU TE)
picks.extend([
    {'player': 'Tanner Koziol', 'team': 'HOU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.31, 'lower_mult': None},
    {'player': 'Tanner Koziol', 'team': 'HOU', 'stat': 'Receiving Yards', 'line': 41.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Tanner Koziol', 'team': 'HOU', 'stat': 'Receptions', 'line': 4.5, 'higher_mult': 1.09, 'lower_mult': 0.83},
    {'player': 'Tanner Koziol', 'team': 'HOU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 5.06, 'lower_mult': None},
    {'player': 'Tanner Koziol', 'team': 'HOU', 'stat': 'Longest Reception', 'line': 19.5, 'higher_mult': 1.0, 'lower_mult': None},
])

# DJ BUTLER (HOU)
picks.extend([
    {'player': 'DJ Butler', 'team': 'HOU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.37, 'lower_mult': None},
    {'player': 'DJ Butler', 'team': 'HOU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 12.37, 'lower_mult': None},
])

# DEAN CONNORS (HOU RB)
picks.extend([
    {'player': 'Dean Connors', 'team': 'HOU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.0, 'lower_mult': None},
    {'player': 'Dean Connors', 'team': 'HOU', 'stat': 'Rush Yards', 'line': 50.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Dean Connors', 'team': 'HOU', 'stat': 'Receiving Yards', 'line': 15.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Dean Connors', 'team': 'HOU', 'stat': 'Receptions', 'line': 2.5, 'higher_mult': 1.03, 'lower_mult': 0.88},
])

# AMARE THOMAS (HOU WR)
picks.extend([
    {'player': 'Amare Thomas', 'team': 'HOU', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.0, 'lower_mult': None},
    {'player': 'Amare Thomas', 'team': 'HOU', 'stat': 'Receiving Yards', 'line': 91.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Amare Thomas', 'team': 'HOU', 'stat': 'Receptions', 'line': 6.5, 'higher_mult': 1.04, 'lower_mult': 0.82},
    {'player': 'Amare Thomas', 'team': 'HOU', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 2.99, 'lower_mult': None},
])

# ETHAN SANCHEZ (HOU K)
picks.extend([
    {'player': 'Ethan Sanchez', 'team': 'HOU', 'stat': 'FG Made', 'line': 1.5, 'higher_mult': 1.23, 'lower_mult': 0.71},
    {'player': 'Ethan Sanchez', 'team': 'HOU', 'stat': 'XP Made', 'line': 2.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Ethan Sanchez', 'team': 'HOU', 'stat': 'Kicking Points', 'line': 5.5, 'higher_mult': 0.85, 'lower_mult': 1.05},
])

print('=' * 90)
print('LSU @ HOUSTON - Tonight 8:15 PM CST - BOWL GAME PROPS ANALYSIS')
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
        boosted.append((p['player'], p['team'], p['stat'], p['line'], 'HIGHER', h))
    if l > 1.0:
        boosted.append((p['player'], p['team'], p['stat'], p['line'], 'LOWER', l))

boosted.sort(key=lambda x: x[5], reverse=True)

print(f"{'Player':<22} {'Team':<5} {'Stat':<20} {'Line':<8} {'Pick':<8} {'Mult':<8}")
print('-' * 80)
for b in boosted[:20]:
    print(f"{b[0]:<22} {b[1]:<5} {b[2]:<20} {b[3]:<8} {b[4]:<8} {b[5]:.2f}x")

# Best VALUE plays - non-longshot boosted picks
print('\n' + '💰 BEST VALUE PLAYS (Boosted + Reasonable Lines)'.center(90))
print('=' * 90)

value_plays = [b for b in boosted if b[5] < 3.0 and b[5] > 1.0]
print(f"{'Player':<22} {'Team':<5} {'Stat':<20} {'Line':<8} {'Pick':<8} {'Mult':<8}")
print('-' * 80)
for b in value_plays[:15]:
    print(f"{b[0]:<22} {b[1]:<5} {b[2]:<20} {b[3]:<8} {b[4]:<8} {b[5]:.2f}x")

# Recommended stacks
print('\n' + '🎯 RECOMMENDED CORRELATED PLAYS'.center(90))
print('=' * 90)

print("""
STACK 1 - LSU OFFENSE
  • Michael Van Buren OVER 1.5 Pass TDs (+15%)
  • Harlem Berry OVER 0.5 Rush+Rec TDs (+8%)
  • Zavion Thomas OVER 40.5 Rec Yards

STACK 2 - HOUSTON OFFENSE  
  • Conner Weigman OVER 44.5 Rush Yards (mobile QB)
  • Conner Weigman LOWER 0.5 INTs (+13%)
  • Amare Thomas OVER 0.5 Receptions (+4%)
  
STACK 3 - FADE THE QBs
  • Michael Van Buren LOWER 0.5 INTs (+5%)
  • Conner Weigman LOWER 16.5 Completions (+4%)
  
VALUE TD PLAYS:
  • Harlem Berry OVER 0.5 TDs (+8%) - lead back
  • Conner Weigman OVER 0.5 Rush TDs (+8%) - mobile
  • Tanner Koziol OVER 0.5 TDs (+31%) - red zone TE
""")

# Compare QBs
print('\n' + 'QB COMPARISON'.center(90))
print('=' * 90)
print("""
┌─────────────────────┬─────────────────────┬─────────────────────┐
│                     │ Michael Van Buren   │ Conner Weigman      │
│                     │ (LSU)               │ (Houston)           │
├─────────────────────┼─────────────────────┼─────────────────────┤
│ Pass Yards Line     │ 207.5               │ 195.5               │
│ Rush Yards Line     │ 7.5                 │ 44.5                │
│ Pass TDs Line       │ 1.5 (OVER +15%)     │ 1.5 (OVER +5%)      │
│ INTs Line           │ 0.5 (LOWER +5%)     │ 0.5 (LOWER +13%)    │
│ Fantasy Points      │ 14.05               │ 19.35               │
│ Pass+Rush Yards     │ 202.5               │ 250.5               │
└─────────────────────┴─────────────────────┴─────────────────────┘

KEY: Weigman is the RUSHING QB (44.5 line vs 7.5)
     - His higher fantasy projection reflects dual-threat ability
     - Van Buren is more of a pocket passer
""")

print('\n' + 'FULL BREAKDOWN BY PLAYER'.center(90))
print('=' * 90)

# Order players by team
lsu_players = ['Michael Van Buren', 'Harlem Berry', 'Caden Durham', 'Kyle Parker', 'Zavion Thomas', 'Bauer Sharp', 'Barion Brown', "Trey'Dez Green", 'Damian Ramos']
hou_players = ['Conner Weigman', 'Tanner Koziol', 'DJ Butler', 'Dean Connors', 'Amare Thomas', 'Ethan Sanchez']

print('\n' + '--- LSU TIGERS ---'.center(90))
for player in lsu_players:
    if player not in by_player:
        continue
    team = by_player[player][0]['team']
    print(f'\n### {player} ({team})')
    print('-' * 70)
    print(f"{'Stat':<22} {'Line':<8} {'Higher':<10} {'Lower':<10} {'Edge?':<15}")
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
        print(f"{p['stat']:<22} {p['line']:<8} {h_str:<10} {l_str:<10} {edge:<15}")

print('\n' + '--- HOUSTON COUGARS ---'.center(90))
for player in hou_players:
    if player not in by_player:
        continue
    team = by_player[player][0]['team']
    print(f'\n### {player} ({team})')
    print('-' * 70)
    print(f"{'Stat':<22} {'Line':<8} {'Higher':<10} {'Lower':<10} {'Edge?':<15}")
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
        print(f"{p['stat']:<22} {p['line']:<8} {h_str:<10} {l_str:<10} {edge:<15}")
