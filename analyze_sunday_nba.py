"""Analyze NBA Sunday Slate - Jan 18, 2026"""
import json
from pathlib import Path
from risk_first_analyzer import analyze_slate

slate = json.loads(Path('outputs/NBA_SLATE_20260118.json').read_text())
props = slate['plays']

# Filter to single stats (not PRA/Fantasy which are blocked)
single_stats = [p for p in props if p['stat'] in ['points', 'rebounds', 'assists', 'fg_attempted']]

output = analyze_slate(single_stats)
results = output.get('results', [])
print('='*70)
print('NBA SUNDAY JAN 18 - BALANCED REPORT')
print('NOP @ HOU | BKN @ CHI | CHA @ DEN')  
print('='*70)

# Print all analyzed picks sorted by confidence
analyzed = [r for r in results if r.get('tier') not in ['BLOCKED', 'SKIPPED']]
analyzed.sort(key=lambda x: x.get('conf_after_gates', 0), reverse=True)

print()
print('RANKED BY CONFIDENCE:')
print('-'*70)
for i, p in enumerate(analyzed[:15], 1):
    player = p.get('player', 'Unknown')
    stat = p.get('stat', '?')
    line = p.get('line', 0)
    direction = p.get('direction', '?').upper()
    conf = p.get('conf_after_gates', 0) * 100
    tier = p.get('tier', 'NO_PLAY')
    mu = p.get('mu', 0)
    sigma = p.get('sigma', 1)
    edge = line - mu if direction == 'LOWER' else mu - line
    print(f'{i:2}. {player:<18} {stat:<8} {direction:<6} {line:<5} | {conf:>5.1f}% {tier:<8} | mu={mu:.1f} edge={edge:+.1f}')

print()
print('='*70)
print('QUICK PICKS BY GAME:')
print('='*70)

games = {'NOP @ HOU': ['NOP', 'HOU'], 'BKN @ CHI': ['BKN', 'CHI'], 'CHA @ DEN': ['CHA', 'DEN']}
for game, teams in games.items():
    game_picks = [p for p in analyzed if p.get('team') in teams]
    game_picks.sort(key=lambda x: x.get('conf_after_gates', 0), reverse=True)
    print(f'\n{game}:')
    for p in game_picks[:4]:
        player = p.get('player', 'Unknown')
        stat = p.get('stat', '?')
        line = p.get('line', 0)
        direction = p.get('direction', '?').upper()
        conf = p.get('conf_after_gates', 0) * 100
        print(f'  {player} {stat} {direction} {line} ({conf:.0f}%)')

print()
print('='*70)
print('WARNINGS:')
print('='*70)
blocked = [r for r in results if r.get('tier') == 'BLOCKED']
skipped = [r for r in results if r.get('tier') == 'SKIPPED']
print(f'  BLOCKED: {len(blocked)} props (PRA/Fantasy/unclassified players)')
print(f'  SKIPPED: {len(skipped)} props (no historical data)')
print()
print('  ⚠️  Trey Murphy, Kon Knueppel not in player classification')
print('  ⚠️  Day\'Ron Sharpe PRA is a DEMON (non-standard payout)')
