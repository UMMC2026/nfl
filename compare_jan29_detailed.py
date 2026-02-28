"""
JANUARY 29, 2026 — SYSTEM vs USER ANALYSIS
Compare system recommendations with actual betting results
"""

# SYSTEM PICKS (from cheatsheet)
system_picks = [
    # STRONG OVERS
    {'player': 'Isaiah Hartenstein', 'stat': 'REB', 'line': 6.5, 'direction': 'OVER', 'prob': 76.0, 'tier': 'STRONG'},
    {'player': 'Jalen Johnson', 'stat': 'AST', 'line': 6.5, 'direction': 'OVER', 'prob': 67.9, 'tier': 'STRONG'},
    # LEAN OVERS
    {'player': 'Royce O\'Neale', 'stat': 'REB', 'line': 4.5, 'direction': 'OVER', 'prob': 61.3, 'tier': 'LEAN'},
    {'player': 'Josh Giddey', 'stat': 'AST', 'line': 7.5, 'direction': 'OVER', 'prob': 60.5, 'tier': 'LEAN'},
    {'player': 'Andrew Wiggins', 'stat': 'REB', 'line': 4.5, 'direction': 'OVER', 'prob': 59.1, 'tier': 'LEAN'},
    {'player': 'Jaden Ivey', 'stat': 'REB', 'line': 1.5, 'direction': 'OVER', 'prob': 58.9, 'tier': 'LEAN'},
    # LEAN UNDERS
    {'player': 'Myles Turner', 'stat': 'REB', 'line': 6.5, 'direction': 'UNDER', 'prob': 62.3, 'tier': 'LEAN'},
    {'player': 'Jabari Smith Jr.', 'stat': 'REB', 'line': 7.5, 'direction': 'UNDER', 'prob': 61.8, 'tier': 'LEAN'},
    {'player': 'Mouhamed Gueye', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'prob': 59.3, 'tier': 'LEAN'},
]

# YOUR ACTUAL PICKS WITH RESULTS (Jan 29, 2026)
your_picks = [
    {'player': 'Jaylen Brown', 'stat': '3PM', 'line': 1.0, 'direction': 'OVER', 'actual': 1, 'result': 'WON'},
    {'player': 'Jaden McDaniels', 'stat': 'PTS+AST', 'line': 16.5, 'direction': 'OVER', 'actual': 17, 'result': 'WON'},
    {'player': 'Matas Buzelis', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON'},
    {'player': 'Marcus Smart', 'stat': 'PTS', 'line': 9.5, 'direction': 'OVER', 'actual': 12, 'result': 'WON'},
    {'player': 'Amen Thompson', 'stat': 'PTS+AST', 'line': 23.5, 'direction': 'UNDER', 'actual': 22, 'result': 'WON'},
    {'player': 'Rudy Gobert', 'stat': 'REB', 'line': 11.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST'},
    {'player': 'Alperen Sengun', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'UNDER', 'actual': 39, 'result': 'LOST'},
    {'player': 'Domantas Sabonis', 'stat': 'PRA', 'line': 31.5, 'direction': 'UNDER', 'actual': 30, 'result': 'WON'},
    {'player': 'Kyle Kuzma', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 8, 'result': 'LOST'},
    {'player': 'Ryan Rollins', 'stat': 'PRA', 'line': 32.5, 'direction': 'UNDER', 'actual': 36, 'result': 'LOST'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST'},
    {'player': 'Aaron Wiggins', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 5, 'result': 'WON'},
    {'player': 'Jaden Ivey', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON'},
    {'player': 'Kelly Oubre Jr.', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 4, 'result': 'WON'},
    {'player': 'Bobby Portis', 'stat': 'REB', 'line': 8.5, 'direction': 'UNDER', 'actual': 12, 'result': 'LOST'},
    {'player': 'Tobias Harris', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST'},
    {'player': 'Duncan Robinson', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST'},
    {'player': 'Isaiah Collier', 'stat': 'PTS', 'line': 13.5, 'direction': 'UNDER', 'actual': 12, 'result': 'WON'},
    {'player': 'Isaiah Stewart', 'stat': 'PTS', 'line': 7.5, 'direction': 'UNDER', 'actual': 7, 'result': 'WON'},
    {'player': 'Jonas Valanciunas', 'stat': 'PTS', 'line': 12.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST'},
    {'player': 'Kyle Filipowski', 'stat': 'PTS+AST', 'line': 15.5, 'direction': 'UNDER', 'actual': 10, 'result': 'WON'},
    {'player': 'Kris Dunn', 'stat': 'PTS+AST', 'line': 9.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST'},
    {'player': 'Lauri Markkanen', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'OVER', 'actual': 23, 'result': 'LOST'},
    {'player': 'Jonas Valanciunas', 'stat': 'AST+REB', 'line': 10.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST'},
]

print("="*80)
print("  JANUARY 29, 2026 — SYSTEM vs USER COMPARISON")
print("="*80)
print()

# Find overlaps
def normalize_stat(s):
    return s.upper().replace('REBOUNDS', 'REB').replace('POINTS', 'PTS').replace('ASSISTS', 'AST')

def normalize_player(p):
    return p.lower().strip()

overlapping = []
for yp in your_picks:
    for sp in system_picks:
        if (normalize_player(sp['player']) == normalize_player(yp['player']) and
            normalize_stat(sp['stat']) == normalize_stat(yp['stat']) and
            sp['direction'].upper() == yp['direction'].upper()):
            overlapping.append({**yp, 'system_prob': sp['prob'], 'system_tier': sp['tier']})
            break

print("PICKS YOU MADE THAT WERE SYSTEM RECOMMENDED:")
print("-"*80)
if overlapping:
    for p in overlapping:
        status = '✅' if p['result'] == 'WON' else '❌'
        print(f"  {status} [{p['system_tier']}] {p['player']:20s} {p['stat']:8s} {p['direction']:6s} {p['line']} → {p['result']} (System: {p['system_prob']:.0f}%)")
    
    sys_wins = sum(1 for p in overlapping if p['result'] == 'WON')
    print(f"\n  RECORD ON SYSTEM PICKS: {sys_wins}/{len(overlapping)} ({sys_wins/len(overlapping)*100:.0f}%)")
else:
    print("  NONE — You did not play any system-recommended picks!")

print()
print("="*80)
print("SYSTEM PICKS YOU DID NOT PLAY:")
print("-"*80)

# Find system picks not played
not_played = []
for sp in system_picks:
    found = False
    for yp in your_picks:
        if (normalize_player(sp['player']) == normalize_player(yp['player']) and
            normalize_stat(sp['stat']) == normalize_stat(yp['stat']) and
            sp['direction'].upper() == yp['direction'].upper()):
            found = True
            break
    if not found:
        not_played.append(sp)

for sp in not_played:
    print(f"  [{sp['tier']}] {sp['player']:25s} {sp['stat']:8s} {sp['direction']:6s} {sp['line']} ({sp['prob']:.0f}%)")

print(f"\n  {len(not_played)} system picks were NOT played")

print()
print("="*80)
print("YOUR PICKS THAT WERE NOT SYSTEM RECOMMENDED:")
print("-"*80)

# Find user picks not in system
user_only = []
for yp in your_picks:
    found = False
    for sp in system_picks:
        if (normalize_player(sp['player']) == normalize_player(yp['player']) and
            normalize_stat(sp['stat']) == normalize_stat(yp['stat']) and
            sp['direction'].upper() == yp['direction'].upper()):
            found = True
            break
    if not found:
        user_only.append(yp)

for p in user_only:
    status = '✅' if p['result'] == 'WON' else '❌'
    print(f"  {status} {p['player']:25s} {p['stat']:10s} {p['direction']:6s} {p['line']} → {p['result']}")

user_wins = sum(1 for p in user_only if p['result'] == 'WON')
print(f"\n  USER-ONLY RECORD: {user_wins}/{len(user_only)} ({user_wins/len(user_only)*100:.0f}%)")

print()
print("="*80)
print("  SUMMARY")
print("="*80)
print()

total = len(your_picks)
total_wins = sum(1 for p in your_picks if p['result'] == 'WON')

print(f"  YOUR TOTAL RECORD: {total_wins}/{total} ({total_wins/total*100:.1f}%)")
print()

if overlapping:
    sys_record = sum(1 for p in overlapping if p['result'] == 'WON')
    print(f"  SYSTEM PICKS PLAYED: {sys_record}/{len(overlapping)} ({sys_record/len(overlapping)*100:.0f}%)")
else:
    print(f"  SYSTEM PICKS PLAYED: 0/0 (N/A)")

print(f"  USER-ONLY PICKS:     {user_wins}/{len(user_only)} ({user_wins/len(user_only)*100:.0f}%)")

print()
print("="*80)
print("  KEY INSIGHT")
print("="*80)
print()
if len(overlapping) == 0:
    print("  ⚠️  You made 0 system-recommended picks!")
    print("  ⚠️  All 24 of your picks were your own selections.")
    print()
    print("  The system had 9 LEAN+ plays available:")
    print("    - Isaiah Hartenstein REB O6.5 (76% STRONG)")
    print("    - Jalen Johnson AST O6.5 (68% STRONG)")
    print("    - Jaden Ivey REB O1.5 (59% LEAN)")  # You played 3PM instead!
    print("    - And 6 more...")
    print()
    print("  Your user-selected picks hit at 50%, which is break-even.")
    print("  Consider incorporating system picks for higher edge.")
else:
    print("  You played some system picks. See above for comparison.")
