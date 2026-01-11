"""Check Jan 6, 2026 game results from ESPN API"""
import requests

r = requests.get(
    'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
    params={'dates': '20260106'},
    timeout=10
)

games = r.json().get('events', [])

print(f"\n{'='*70}")
print(f"JAN 6, 2026 - {len(games)} COMPLETED GAMES")
print('='*70)

for g in games:
    comp = g['competitions'][0]
    away = comp['competitors'][1]
    home = comp['competitors'][0]
    status = g['status']['type']['detail']
    
    print(f"\n{away['team']['abbreviation']} {away['score']} @ {home['team']['abbreviation']} {home['score']} - {status}")

print(f"\n{'='*70}")

# Check if we have any verified picks
import csv
from pathlib import Path

cal_file = Path("calibration_jan6.csv")
if cal_file.exists():
    with open(cal_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        verified = [r for r in rows if r.get('outcome') in ['HIT', 'MISS']]
        skipped = [r for r in rows if r.get('outcome') == 'SKIPPED']
        pending = [r for r in rows if not r.get('outcome')]
        
        print(f"\nCALIBRATION STATUS:")
        print(f"  Total Picks: {len(rows)}")
        print(f"  Verified: {len(verified)} (HIT/MISS)")
        print(f"  Skipped: {len(skipped)} (team didn't play)")
        print(f"  Pending: {len(pending)}")
        
        if verified:
            hits = [r for r in verified if r['outcome'] == 'HIT']
            misses = [r for r in verified if r['outcome'] == 'MISS']
            print(f"\n  Results: {len(hits)} HITs, {len(misses)} MISSes")
            
            if hits:
                print("\n  Sample HITs:")
                for r in hits[:3]:
                    print(f"    ✅ {r['player']} {r['stat']} {r['direction']} {r['line']} (actual: {r.get('actual_value', '?')})")
else:
    print("\n⚠️  calibration_jan6.csv not found")

print('='*70)
