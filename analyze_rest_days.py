"""Analyze rest days for all top Monte Carlo picks."""
import json
from datetime import datetime, timedelta
import numpy as np

def analyze_rest_days_from_gamelog(player_name: str, stat_key: str, season: str = "2024-25"):
    """Extract rest day analytics from NBA game log."""
    try:
        from nba_api.stats.static import players
        from nba_api.stats.endpoints import playergamelog
        import pandas as pd
    except ImportError as e:
        return {"error": str(e)}
    
    from ufa.ingest.stat_map import NBA_STAT_KEYS
    
    col = NBA_STAT_KEYS.get(stat_key)
    if not col:
        return {"error": f"Unknown stat: {stat_key}"}
    
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        return {"error": f"Player not found: {player_name}"}
    
    try:
        pid = int(matches[0]["id"])
        gl = playergamelog.PlayerGameLog(player_id=pid, season=season)
        df = gl.get_data_frames()[0]
        
        if df.empty or len(df) < 3:
            return {"error": "Not enough games"}
        
        # Get stat values
        if isinstance(col, list):
            df['STAT_VALUE'] = df[col].sum(axis=1)
        else:
            df['STAT_VALUE'] = df[col]
        
        # Parse dates
        df['GAME_DATE_DT'] = pd.to_datetime(df['GAME_DATE'])
        df = df.sort_values('GAME_DATE_DT', ascending=False).head(10)
        
        # Calculate rest days
        rest_data = []
        for i in range(len(df) - 1):
            current_game = df.iloc[i]
            prev_game = df.iloc[i + 1]
            
            days_between = (current_game['GAME_DATE_DT'] - prev_game['GAME_DATE_DT']).days - 1
            rest_days = max(0, days_between)
            
            rest_data.append({
                'date': current_game['GAME_DATE_DT'].strftime('%Y-%m-%d'),
                'value': float(current_game['STAT_VALUE']),
                'rest': rest_days
            })
        
        # Categorize by rest
        b2b = [r['value'] for r in rest_data if r['rest'] == 0]
        one_day = [r['value'] for r in rest_data if r['rest'] == 1]
        two_plus = [r['value'] for r in rest_data if r['rest'] >= 2]
        
        # Calculate upcoming rest
        most_recent = df.iloc[0]['GAME_DATE_DT']
        today = datetime.now()
        upcoming_rest = (today - most_recent).days - 1
        
        return {
            'player': player_name,
            'stat': stat_key,
            'b2b_avg': round(np.mean(b2b), 2) if b2b else None,
            'b2b_games': len(b2b),
            'one_day_avg': round(np.mean(one_day), 2) if one_day else None,
            'one_day_games': len(one_day),
            'two_plus_avg': round(np.mean(two_plus), 2) if two_plus else None,
            'two_plus_games': len(two_plus),
            'upcoming_rest': upcoming_rest,
            'last_game': most_recent.strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        return {"error": str(e)}


# Analyze all top picks from Monte Carlo
top_picks = [
    ("AJ Green", "rebounds"),
    ("Deni Avdija", "3pm"),
    ("Al Horford", "3pm"),
    ("Myles Turner", "assists"),
    ("Shaedon Sharpe", "rebounds"),
    ("Gary Harris", "rebounds"),
    ("Dorian Finney-Smith", "3pm"),
    ("Brandin Podziemski", "3pm"),
    ("Bobby Portis", "assists"),
]

print("="*90)
print("REST DAY ANALYTICS - TOP MONTE CARLO PICKS")
print("="*90)
print()

results = []
for player, stat in top_picks:
    analysis = analyze_rest_days_from_gamelog(player, stat)
    results.append(analysis)
    
    if 'error' in analysis:
        print(f"❌ {player} ({stat}): {analysis['error']}")
        continue
    
    print(f"🏀 {player} - {stat.upper()}")
    print(f"   Last Game: {analysis['last_game']} ({analysis['upcoming_rest']} days ago)")
    print(f"   Back-to-back (0 rest): {analysis['b2b_avg']} avg ({analysis['b2b_games']} games)")
    print(f"   Standard rest (1 day): {analysis['one_day_avg']} avg ({analysis['one_day_games']} games)")
    print(f"   Extra rest (2+ days): {analysis['two_plus_avg']} avg ({analysis['two_plus_games']} games)")
    
    # Calculate rest advantage
    if analysis['b2b_avg'] and analysis['one_day_avg']:
        advantage = analysis['one_day_avg'] - analysis['b2b_avg']
        pct = (advantage / analysis['b2b_avg'] * 100) if analysis['b2b_avg'] > 0 else 0
        
        if abs(advantage) >= 0.5:
            direction = "BETTER" if advantage > 0 else "WORSE"
            print(f"   📊 Rest Impact: {abs(advantage):.1f} {stat} {direction} with rest ({pct:+.1f}%)")
    
    # Upcoming game context
    if analysis['upcoming_rest'] == 0:
        print(f"   ⚡️ ALERT: Playing on back-to-back tonight")
    elif analysis['upcoming_rest'] == 1:
        print(f"   ✅ Standard rest situation")
    elif analysis['upcoming_rest'] >= 2:
        print(f"   🔋 EXTRA MOTIVATION: {analysis['upcoming_rest']} days rest")
    
    print()

# Generate Telegram-ready commentary
print("="*90)
print("TELEGRAM COMMENTARY - REST DAY INSIGHTS")
print("="*90)
print()

telegram_commentary = "📅 *REST DAY ANALYSIS*\n\n"

for analysis in results:
    if 'error' in analysis:
        continue
    
    p = analysis['player']
    s = analysis['stat'].upper()
    
    telegram_commentary += f"🏀 *{p} ({s})*\n"
    
    # Rest performance
    if analysis['b2b_avg'] and analysis['one_day_avg']:
        telegram_commentary += f"• B2B: {analysis['b2b_avg']} avg | "
        telegram_commentary += f"Rested: {analysis['one_day_avg']} avg\n"
        
        advantage = analysis['one_day_avg'] - analysis['b2b_avg']
        if abs(advantage) >= 0.5:
            pct = (advantage / analysis['b2b_avg'] * 100) if analysis['b2b_avg'] > 0 else 0
            direction = "↗️" if advantage > 0 else "↘️"
            telegram_commentary += f"  {direction} {abs(advantage):.1f} {s} difference ({pct:+.1f}%)\n"
    
    # Upcoming context
    if analysis['upcoming_rest'] == 0:
        telegram_commentary += f"⚡️ *B2B game tonight - fatigue risk*\n"
    elif analysis['upcoming_rest'] >= 2:
        telegram_commentary += f"🔋 *{analysis['upcoming_rest']} days rest - fresh legs*\n"
    
    telegram_commentary += "\n"

print(telegram_commentary)

# Save to file
with open('outputs/rest_day_analysis.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)

print("\n✅ Saved to: outputs/rest_day_analysis.json")
