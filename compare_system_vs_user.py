"""Compare system picks with actual results"""
import json

data = json.load(open('outputs/THUREND_RISK_FIRST_20260129_FROM_UD.json'))

# Your actual results
your_picks = [
    {'player': 'Jaylen Brown', 'stat': '3PM', 'line': 1.0, 'direction': 'OVER', 'result': 'WON'},
    {'player': 'Jaden McDaniels', 'stat': 'PTS+AST', 'line': 16.5, 'direction': 'OVER', 'result': 'WON'},
    {'player': 'Matas Buzelis', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'result': 'WON'},
    {'player': 'Marcus Smart', 'stat': 'PTS', 'line': 9.5, 'direction': 'OVER', 'result': 'WON'},
    {'player': 'Amen Thompson', 'stat': 'PTS+AST', 'line': 23.5, 'direction': 'UNDER', 'result': 'WON'},
    {'player': 'Rudy Gobert', 'stat': 'REB', 'line': 11.5, 'direction': 'UNDER', 'result': 'LOST'},
    {'player': 'Alperen Sengun', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'UNDER', 'result': 'LOST'},
    {'player': 'Domantas Sabonis', 'stat': 'PRA', 'line': 31.5, 'direction': 'UNDER', 'result': 'WON'},
    {'player': 'Kyle Kuzma', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'result': 'LOST'},
    {'player': 'Ryan Rollins', 'stat': 'PRA', 'line': 32.5, 'direction': 'UNDER', 'result': 'LOST'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'direction': 'OVER', 'result': 'LOST'},
    {'player': 'Aaron Wiggins', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'result': 'WON'},
    {'player': 'Jaden Ivey', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'result': 'WON'},
    {'player': 'Kelly Oubre Jr.', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'result': 'WON'},
    {'player': 'Bobby Portis', 'stat': 'REB', 'line': 8.5, 'direction': 'UNDER', 'result': 'LOST'},
    {'player': 'Tobias Harris', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'result': 'LOST'},
    {'player': 'Duncan Robinson', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'result': 'LOST'},
    {'player': 'Isaiah Collier', 'stat': 'PTS', 'line': 13.5, 'direction': 'UNDER', 'result': 'WON'},
    {'player': 'Isaiah Stewart', 'stat': 'PTS', 'line': 7.5, 'direction': 'UNDER', 'result': 'WON'},
    {'player': 'Jonas Valanciunas', 'stat': 'PTS', 'line': 12.5, 'direction': 'UNDER', 'result': 'LOST'},
    {'player': 'Kyle Filipowski', 'stat': 'PTS+AST', 'line': 15.5, 'direction': 'UNDER', 'result': 'WON'},
    {'player': 'Kris Dunn', 'stat': 'PTS+AST', 'line': 9.5, 'direction': 'UNDER', 'result': 'LOST'},
    {'player': 'Lauri Markkanen', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'OVER', 'result': 'LOST'},
    {'player': 'Jonas Valanciunas', 'stat': 'AST+REB', 'line': 10.5, 'direction': 'UNDER', 'result': 'LOST'},
]

print('SYSTEM PICKS (LEAN+):')
print('='*70)

# Collect all system picks
system_picks = []
for tier in ['play', 'strong', 'lean']:
    picks = data.get(tier, [])
    for p in picks:
        if isinstance(p, dict):
            system_picks.append({
                'player': p.get('entity', p.get('player', '')),
                'stat': p.get('market', p.get('stat', '')),
                'line': p.get('line', 0),
                'direction': p.get('direction', ''),
                'prob': p.get('probability', p.get('prob_over', 0)),
                'tier': tier.upper()
            })

for sp in system_picks:
    prob = sp['prob']
    if prob > 1:
        prob = prob / 100
    print(f"{sp['tier']:8s} {sp['player']:25s} {sp['stat']:12s} {sp['direction']:6s} {sp['line']} ({prob*100:.0f}%)")

print()
print('='*70)
print('COMPARING WITH YOUR ACTUAL PLAYS:')
print('='*70)

system_matched = []
user_only = []

for yp in your_picks:
    matched = False
    for sp in system_picks:
        # Normalize comparison
        sp_player = sp['player'].lower().strip()
        yp_player = yp['player'].lower().strip()
        sp_stat = sp['stat'].upper().replace('REBOUNDS', 'REB').replace('POINTS', 'PTS').replace('ASSISTS', 'AST')
        yp_stat = yp['stat'].upper()
        
        if (sp_player == yp_player and 
            sp_stat == yp_stat and
            sp['direction'].upper() == yp['direction'].upper()):
            matched = True
            system_matched.append({**yp, 'system_tier': sp['tier'], 'system_prob': sp['prob']})
            break
    
    if not matched:
        user_only.append(yp)

print()
print("SYSTEM PICKS YOU PLAYED:")
sys_wins = sum(1 for p in system_matched if p['result'] == 'WON')
sys_total = len(system_matched)
for p in system_matched:
    status = '✅' if p['result'] == 'WON' else '❌'
    print(f"  {status} {p['player']:20s} {p['stat']:10s} {p['direction']:6s} {p['line']} -> {p['result']}")

print(f"\nSYSTEM PICK RECORD: {sys_wins}/{sys_total} ({sys_wins/sys_total*100:.0f}%)" if sys_total > 0 else "No system picks played")

print()
print("USER-ONLY PICKS (not system recommended):")
user_wins = sum(1 for p in user_only if p['result'] == 'WON')
user_total = len(user_only)
for p in user_only:
    status = '✅' if p['result'] == 'WON' else '❌'
    print(f"  {status} {p['player']:20s} {p['stat']:10s} {p['direction']:6s} {p['line']} -> {p['result']}")

print(f"\nUSER-ONLY RECORD: {user_wins}/{user_total} ({user_wins/user_total*100:.0f}%)" if user_total > 0 else "All picks were system picks")

print()
print('='*70)
print('SYSTEM PICKS YOU DID NOT PLAY:')
print('='*70)

# Find system picks not in your plays
for sp in system_picks:
    found = False
    for yp in your_picks:
        sp_player = sp['player'].lower().strip()
        yp_player = yp['player'].lower().strip()
        sp_stat = sp['stat'].upper().replace('REBOUNDS', 'REB').replace('POINTS', 'PTS').replace('ASSISTS', 'AST')
        yp_stat = yp['stat'].upper()
        
        if (sp_player == yp_player and sp_stat == yp_stat and 
            sp['direction'].upper() == yp['direction'].upper()):
            found = True
            break
    
    if not found:
        prob = sp['prob'] if sp['prob'] <= 1 else sp['prob']/100
        print(f"  [{sp['tier']}] {sp['player']:20s} {sp['stat']:10s} {sp['direction']:6s} {sp['line']} ({prob*100:.0f}%)")
