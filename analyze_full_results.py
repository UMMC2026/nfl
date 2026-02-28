"""
COMPREHENSIVE BETTING RESULTS ANALYSIS
All sports: NBA, NFL, CBB, Tennis
"""

results = [
    {'player': 'Ayo Dosunmu', 'stat': '3PM', 'line': 1.5, 'direction': 'UNDER', 'actual': 2, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Coby White', 'stat': '3PM', 'line': 2.5, 'direction': 'UNDER', 'actual': 5, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Cody Williams', 'stat': '3PM', 'line': 0.5, 'direction': 'UNDER', 'actual': 0, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Alperen Sengun', 'stat': 'PRA', 'line': 34.5, 'direction': 'UNDER', 'actual': 25, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Cade Cunningham', 'stat': 'PRA', 'line': 38.5, 'direction': 'UNDER', 'actual': 21, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Jaden Ivey', 'stat': 'PRA', 'line': 12.5, 'direction': 'UNDER', 'actual': 11, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Evan Mobley', 'stat': 'PRA', 'line': 31.5, 'direction': 'UNDER', 'actual': 49, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Precious Achiuwa', 'stat': 'PRA', 'line': 13.5, 'direction': 'UNDER', 'actual': 14, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Zach LaVine', 'stat': 'PRA', 'line': 23.5, 'direction': 'UNDER', 'actual': 10, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Ausar Thompson', 'stat': 'REB', 'line': 5.5, 'direction': 'OVER', 'actual': 5, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Domantas Sabonis', 'stat': 'BLK+STL', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Duncan Robinson', 'stat': 'PRA', 'line': 16.5, 'direction': 'OVER', 'actual': 14, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Malik Monk', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 3, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Derik Queen', 'stat': 'AST', 'line': 4.5, 'direction': 'OVER', 'actual': 1, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'direction': 'OVER', 'actual': 3, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Julian Champagnie', 'stat': 'PTS', 'line': 11.0, 'direction': 'OVER', 'actual': 13, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Saddiq Bey', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 10, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Zion Williamson', 'stat': 'AST', 'line': 2.5, 'direction': 'OVER', 'actual': 4, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Jaden McDaniels', 'stat': 'PRA', 'line': 25.5, 'direction': 'OVER', 'actual': 7, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Kyren Williams', 'stat': 'Recs', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NFL'},
    {'player': 'Matthew Stafford', 'stat': 'Rush Yards', 'line': 0.5, 'direction': 'OVER', 'actual': 16, 'result': 'WON', 'league': 'NFL'},
    {'player': 'Tyler Higbee', 'stat': 'Rec Yards', 'line': 19.5, 'direction': 'OVER', 'actual': 12, 'result': 'LOST', 'league': 'NFL'},
    {'player': 'Scottie Barnes', 'stat': '2-PT Att', 'line': 12.5, 'direction': 'OVER', 'actual': 6, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Julian Champagnie', 'stat': 'PTS', 'line': 12.5, 'direction': 'OVER', 'actual': 13, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Kayshon Boutte', 'stat': 'Rec Yards', 'line': 31.5, 'direction': 'OVER', 'actual': 6, 'result': 'LOST', 'league': 'NFL'},
    {'player': 'RJ Harvey', 'stat': 'Rush Yards', 'line': 40.5, 'direction': 'OVER', 'actual': 37, 'result': 'LOST', 'league': 'NFL'},
    {'player': 'Ausar Thompson', 'stat': 'PRA', 'line': 20.5, 'direction': 'OVER', 'actual': 16, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'DeMar DeRozan', 'stat': 'PTS+AST', 'line': 24.5, 'direction': 'OVER', 'actual': 20, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Domantas Sabonis', 'stat': 'PRA', 'line': 33.5, 'direction': 'OVER', 'actual': 27, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Tobias Harris', 'stat': 'PRA', 'line': 21.5, 'direction': 'OVER', 'actual': 21, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Cooper Kupp', 'stat': 'Recs', 'line': 3.0, 'direction': 'UNDER', 'actual': 4, 'result': 'LOST', 'league': 'NFL'},
    {'player': 'Kyren Williams', 'stat': 'Recs', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NFL'},
    {'player': 'Blake Corum', 'stat': 'Rec Yards', 'line': 0.5, 'direction': 'OVER', 'actual': 24, 'result': 'WON', 'league': 'NFL'},
    {'player': 'Colby Parkinson', 'stat': 'Recs', 'line': 1.5, 'direction': 'OVER', 'actual': 3, 'result': 'WON', 'league': 'NFL'},
    {'player': 'Terrance Ferguson', 'stat': 'Recs', 'line': 0.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NFL'},
    {'player': 'Dylan Harper', 'stat': 'PTS', 'line': 11.5, 'direction': 'OVER', 'actual': 5, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Dylan Harper', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 6, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Harrison Barnes', 'stat': '2-PT Made', 'line': 1.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Luke Kornet', 'stat': 'PTS+AST', 'line': 9.5, 'direction': 'OVER', 'actual': 6, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Victor Wembanyama', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Yves Missi', 'stat': 'FG Made', 'line': 2.5, 'direction': 'OVER', 'actual': 4, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Dailyn Swain', 'stat': 'PTS', 'line': 14.5, 'direction': 'UNDER', 'actual': 29, 'result': 'LOST', 'league': 'CBB'},
    {'player': 'Otega Oweh', 'stat': 'PTS', 'line': 17.5, 'direction': 'UNDER', 'actual': 18, 'result': 'LOST', 'league': 'CBB'},
    {'player': 'Tramon Mark', 'stat': 'PTS', 'line': 14.5, 'direction': 'UNDER', 'actual': 12, 'result': 'WON', 'league': 'CBB'},
    {'player': 'Cayden Vasko', 'stat': 'REB', 'line': 4.5, 'direction': 'UNDER', 'actual': 2, 'result': 'WON', 'league': 'CBB'},
    {'player': 'Dylan Faulkner', 'stat': 'REB', 'line': 7.5, 'direction': 'UNDER', 'actual': 4, 'result': 'WON', 'league': 'CBB'},
    {'player': 'Kahmare Holmes', 'stat': 'REB', 'line': 5.5, 'direction': 'OVER', 'actual': 4, 'result': 'LOST', 'league': 'CBB'},
    {'player': 'Nils Machowski', 'stat': 'REB', 'line': 4.5, 'direction': 'OVER', 'actual': 4, 'result': 'LOST', 'league': 'CBB'},
    {'player': 'Madison Keys', 'stat': 'Total Games', 'line': 20.5, 'direction': 'OVER', 'actual': 19, 'result': 'LOST', 'league': 'Tennis'},
    {'player': 'Paula Badosa', 'stat': 'Aces', 'line': 3.5, 'direction': 'OVER', 'actual': 4, 'result': 'WON', 'league': 'Tennis'},
    {'player': 'Amen Thompson', 'stat': 'PRA', 'line': 24.5, 'direction': 'OVER', 'actual': 32, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Clint Capela', 'stat': 'PRA', 'line': 8.5, 'direction': 'UNDER', 'actual': 8, 'result': 'WON', 'league': 'NBA'},
    {'player': "De'Aaron Fox", 'stat': 'AST', 'line': 3.5, 'direction': 'OVER', 'actual': 5, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Kevin Durant', 'stat': 'PTS', 'line': 24.5, 'direction': 'OVER', 'actual': 18, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Tari Eason', 'stat': 'PRA', 'line': 15.5, 'direction': 'OVER', 'actual': 13, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Anfernee Simons', 'stat': 'PTS', 'line': 13.5, 'direction': 'OVER', 'actual': 9, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Jaylen Brown', 'stat': 'PTS', 'line': 24.5, 'direction': 'OVER', 'actual': 30, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Neemias Queta', 'stat': 'PTS', 'line': 8.5, 'direction': 'OVER', 'actual': 17, 'result': 'WON', 'league': 'NBA'},
    {'player': 'CJ McCollum', 'stat': 'PTS', 'line': 16.5, 'direction': 'OVER', 'actual': 15, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Ausar Thompson', 'stat': 'PTS', 'line': 10.5, 'direction': 'UNDER', 'actual': 12, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Yves Missi', 'stat': 'PTS', 'line': 4.5, 'direction': 'OVER', 'actual': 4, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'AJ Green', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 6, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Corey Kispert', 'stat': '3PM', 'line': 0.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Kyle Kuzma', 'stat': '3PM', 'line': 0.5, 'direction': 'OVER', 'actual': 1, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Bobby Portis', 'stat': 'PTS', 'line': 11.5, 'direction': 'OVER', 'actual': 19, 'result': 'WON', 'league': 'NBA'},
    {'player': 'CJ McCollum', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Duncan Robinson', 'stat': 'PTS', 'line': 10.5, 'direction': 'OVER', 'actual': 15, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Bam Adebayo', 'stat': 'AST', 'line': 3.5, 'direction': 'OVER', 'actual': 3, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Al Horford', 'stat': 'PRA', 'line': 9.5, 'direction': 'OVER', 'actual': 20, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Bam Adebayo', 'stat': 'REB+AST', 'line': 11.5, 'direction': 'OVER', 'actual': 15, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Jimmy Butler', 'stat': 'PTS', 'line': 19.5, 'direction': 'OVER', 'actual': 17, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Norman Powell', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Jalen Johnson', 'stat': 'AST', 'line': 7.5, 'direction': 'UNDER', 'actual': 6, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Kevin Porter', 'stat': 'PRA', 'line': 28.5, 'direction': 'UNDER', 'actual': 22, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Nickeil Alexander-Walker', 'stat': 'PTS', 'line': 19.5, 'direction': 'OVER', 'actual': 32, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Jaylen Brown', 'stat': '3PM', 'line': 1.0, 'direction': 'OVER', 'actual': 1, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Jaden McDaniels', 'stat': 'PTS+AST', 'line': 16.5, 'direction': 'OVER', 'actual': 17, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Matas Buzelis', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Marcus Smart', 'stat': 'PTS', 'line': 9.5, 'direction': 'OVER', 'actual': 12, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Amen Thompson', 'stat': 'PTS+AST', 'line': 23.5, 'direction': 'UNDER', 'actual': 22, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Rudy Gobert', 'stat': 'REB', 'line': 11.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Alperen Sengun', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'UNDER', 'actual': 39, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Domantas Sabonis', 'stat': 'PRA', 'line': 31.5, 'direction': 'UNDER', 'actual': 30, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Kyle Kuzma', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 8, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Ryan Rollins', 'stat': 'PRA', 'line': 32.5, 'direction': 'UNDER', 'actual': 36, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Aaron Wiggins', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 5, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Jaden Ivey', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Kelly Oubre Jr.', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 4, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Bobby Portis', 'stat': 'REB', 'line': 8.5, 'direction': 'UNDER', 'actual': 12, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Tobias Harris', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Duncan Robinson', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Isaiah Collier', 'stat': 'PTS', 'line': 13.5, 'direction': 'UNDER', 'actual': 12, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Isaiah Stewart', 'stat': 'PTS', 'line': 7.5, 'direction': 'UNDER', 'actual': 7, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Jonas Valanciunas', 'stat': 'PTS', 'line': 12.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Kyle Filipowski', 'stat': 'PTS+AST', 'line': 15.5, 'direction': 'UNDER', 'actual': 10, 'result': 'WON', 'league': 'NBA'},
    {'player': 'Kris Dunn', 'stat': 'PTS+AST', 'line': 9.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Lauri Markkanen', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'OVER', 'actual': 23, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Jonas Valanciunas', 'stat': 'AST+REB', 'line': 10.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST', 'league': 'NBA'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NBA'},
]

print("="*80)
print("  COMPREHENSIVE BETTING RESULTS ANALYSIS")
print("="*80)
print()

# Overall stats
total = len(results)
wins = sum(1 for r in results if r['result'] == 'WON')
losses = total - wins

print(f"OVERALL: {wins}-{losses} ({wins/total*100:.1f}% hit rate)")
print()

# By league
print("BY LEAGUE:")
print("-"*50)
leagues = {}
for r in results:
    league = r['league']
    if league not in leagues:
        leagues[league] = {'wins': 0, 'losses': 0}
    if r['result'] == 'WON':
        leagues[league]['wins'] += 1
    else:
        leagues[league]['losses'] += 1

for league, data in sorted(leagues.items(), key=lambda x: (x[1]['wins']+x[1]['losses']), reverse=True):
    total_l = data['wins'] + data['losses']
    pct = data['wins']/total_l*100 if total_l > 0 else 0
    bar = '█' * int(pct/5) + '░' * (20 - int(pct/5))
    print(f"  {league:8s}: {data['wins']:2d}-{data['losses']:2d} ({pct:5.1f}%) {bar}")

print()
print("BY DIRECTION:")
print("-"*50)
overs = [r for r in results if r['direction'] == 'OVER']
unders = [r for r in results if r['direction'] == 'UNDER']
over_wins = sum(1 for r in overs if r['result'] == 'WON')
under_wins = sum(1 for r in unders if r['result'] == 'WON')

over_pct = over_wins/len(overs)*100 if overs else 0
under_pct = under_wins/len(unders)*100 if unders else 0

print(f"  OVERS:  {over_wins:2d}-{len(overs)-over_wins:2d} ({over_pct:5.1f}%) {'█' * int(over_pct/5) + '░' * (20 - int(over_pct/5))}")
print(f"  UNDERS: {under_wins:2d}-{len(unders)-under_wins:2d} ({under_pct:5.1f}%) {'█' * int(under_pct/5) + '░' * (20 - int(under_pct/5))}")

print()
print("BY STAT TYPE (NBA only):")
print("-"*50)

nba_results = [r for r in results if r['league'] == 'NBA']
stats = {}
for r in nba_results:
    stat = r['stat']
    if stat not in stats:
        stats[stat] = {'wins': 0, 'losses': 0, 'overs': 0, 'over_wins': 0, 'unders': 0, 'under_wins': 0}
    if r['result'] == 'WON':
        stats[stat]['wins'] += 1
    else:
        stats[stat]['losses'] += 1
    if r['direction'] == 'OVER':
        stats[stat]['overs'] += 1
        if r['result'] == 'WON':
            stats[stat]['over_wins'] += 1
    else:
        stats[stat]['unders'] += 1
        if r['result'] == 'WON':
            stats[stat]['under_wins'] += 1

# Sort by total picks
for stat, data in sorted(stats.items(), key=lambda x: (x[1]['wins']+x[1]['losses']), reverse=True):
    total_s = data['wins'] + data['losses']
    if total_s < 2:
        continue
    pct = data['wins']/total_s*100 if total_s > 0 else 0
    status = '✅' if pct >= 55 else ('⚠️' if pct >= 45 else '❌')
    print(f"  {status} {stat:12s}: {data['wins']:2d}-{data['losses']:2d} ({pct:5.1f}%)", end='')
    if data['overs'] > 0 and data['unders'] > 0:
        o_pct = data['over_wins']/data['overs']*100
        u_pct = data['under_wins']/data['unders']*100
        print(f"  [O: {data['over_wins']}/{data['overs']} ({o_pct:.0f}%) | U: {data['under_wins']}/{data['unders']} ({u_pct:.0f}%)]")
    else:
        print()

print()
print("="*80)
print("  DANGER ZONES (stat types losing money)")
print("="*80)
print()

danger_zones = []
for stat, data in stats.items():
    total_s = data['wins'] + data['losses']
    if total_s >= 3:
        pct = data['wins']/total_s*100
        if pct < 45:
            danger_zones.append((stat, data['wins'], data['losses'], pct))

if danger_zones:
    for stat, w, l, pct in sorted(danger_zones, key=lambda x: x[3]):
        print(f"  ❌ {stat}: {w}-{l} ({pct:.0f}%) — AVOID THIS STAT TYPE")
else:
    print("  No major danger zones identified")

print()
print("="*80)
print("  PROFITABLE PATTERNS")
print("="*80)
print()

# Find profitable combos
print("Combo stats (PRA, PTS+AST, etc) by direction:")
combo_stats = [r for r in nba_results if '+' in r['stat'] or r['stat'] == 'PRA']
combo_overs = [r for r in combo_stats if r['direction'] == 'OVER']
combo_unders = [r for r in combo_stats if r['direction'] == 'UNDER']

co_wins = sum(1 for r in combo_overs if r['result'] == 'WON')
cu_wins = sum(1 for r in combo_unders if r['result'] == 'WON')

print(f"  Combo OVERS:  {co_wins}/{len(combo_overs)} ({co_wins/len(combo_overs)*100:.0f}%)" if combo_overs else "  No combo overs")
print(f"  Combo UNDERS: {cu_wins}/{len(combo_unders)} ({cu_wins/len(combo_unders)*100:.0f}%)" if combo_unders else "  No combo unders")

print()
print("3PM picks by direction:")
three_pm = [r for r in nba_results if r['stat'] == '3PM']
three_overs = [r for r in three_pm if r['direction'] == 'OVER']
three_unders = [r for r in three_pm if r['direction'] == 'UNDER']

to_wins = sum(1 for r in three_overs if r['result'] == 'WON')
tu_wins = sum(1 for r in three_unders if r['result'] == 'WON')

print(f"  3PM OVERS:  {to_wins}/{len(three_overs)} ({to_wins/len(three_overs)*100:.0f}%)" if three_overs else "  No 3PM overs")
print(f"  3PM UNDERS: {tu_wins}/{len(three_unders)} ({tu_wins/len(three_unders)*100:.0f}%)" if three_unders else "  No 3PM unders")

print()
print("="*80)
print("  RECOMMENDATIONS BASED ON YOUR DATA")
print("="*80)
print()

# Calculate overall direction bias
print("DIRECTION BIAS:")
if over_pct > under_pct + 10:
    print(f"  ✅ OVERS are hitting better ({over_pct:.0f}% vs {under_pct:.0f}%) — lean OVER")
elif under_pct > over_pct + 10:
    print(f"  ✅ UNDERS are hitting better ({under_pct:.0f}% vs {over_pct:.0f}%) — lean UNDER")
else:
    print(f"  ⚖️ Both directions similar ({over_pct:.0f}% vs {under_pct:.0f}%) — no strong bias")

print()
print("STAT RECOMMENDATIONS:")
for stat, data in stats.items():
    total_s = data['wins'] + data['losses']
    if total_s >= 4:
        pct = data['wins']/total_s*100
        if pct >= 60:
            print(f"  ✅ {stat}: Keep playing ({pct:.0f}% hit rate)")
        elif pct < 40:
            print(f"  ❌ {stat}: STOP playing ({pct:.0f}% hit rate)")

print()
print("BLOWOUT LOSSES (missed by >3):")
blowouts = []
for r in results:
    if r['result'] == 'LOST':
        margin = abs(r['actual'] - r['line'])
        if margin > 3:
            blowouts.append((r['player'], r['stat'], r['direction'], r['line'], r['actual'], margin))

blowouts.sort(key=lambda x: x[5], reverse=True)
for player, stat, direction, line, actual, margin in blowouts[:10]:
    print(f"  • {player}: {stat} {direction} {line} → actual {actual} (off by {margin:.1f})")
