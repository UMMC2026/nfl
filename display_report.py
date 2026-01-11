import json

with open('reports/DAILY_GAMES_REPORT_2026-01-03.json', 'r') as f:
    report = json.load(f)

print('╔════════════════════════════════════════════════════════════════════╗')
print('║          DAILY GAMES INTELLIGENCE REPORT — TONIGHT                ║')
print('║                      January 3, 2026                               ║')
print('╚════════════════════════════════════════════════════════════════════╝\n')

# NFL Games
print('🏈 NFL — WILD CARD PLAYOFF GAMES\n')
print('=' * 70)
for i, game in enumerate(report['nfl']['games'], 1):
    matchup = game['matchup'].upper()
    kickoff = game['kickoff']
    window = game['window']
    script = game['expected_script'][:80]
    suppression = game['volume_suppression']
    variance = game['variance']
    print(f"\n{i}. {matchup}")
    print(f"   Kickoff:  {kickoff}")
    print(f"   Window:   {window}")
    print(f"   Script:   {script}...")
    print(f"   Volume:   {suppression} suppression")
    print(f"   Variance: {variance}")

# NBA Games
print('\n\n🏀 NBA — REGULAR SEASON\n')
print('=' * 70)
for i, game in enumerate(report['nba']['games'], 1):
    matchup = game['matchup'].upper()
    tipoff = game['kickoff']
    script = game['expected_script'][:80]
    suppression = game['volume_suppression']
    print(f"\n{i}. {matchup}")
    print(f"   Tipoff:   {tipoff}")
    print(f"   Script:   {script}...")
    print(f"   Volume:   {suppression} suppression")

print('\n' + '=' * 70)
print('\n✅ Report Status: OPERATIONAL')
print('🔒 Confidence Caps: core=70%, alt=65%, td=52%')
print('📊 All systems gated on report')
