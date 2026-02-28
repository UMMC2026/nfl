"""Check Cam Thomas actual stats from NBA API"""
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
import time

# Find Cam Thomas
matches = players.find_players_by_full_name('Cam Thomas')
print(f'Found: {matches}')

if matches:
    pid = matches[0]['id']
    time.sleep(0.5)  # Rate limit
    gl = playergamelog.PlayerGameLog(player_id=pid, season='2024-25', timeout=30)
    df = gl.get_data_frames()[0]
    
    print('\nLast 10 games points:')
    print(df[['GAME_DATE', 'MATCHUP', 'MIN', 'PTS']].head(10).to_string())
    print(f'\nAverage: {df["PTS"].head(10).mean():.1f} PPG')
    print(f'Season Average: {df["PTS"].mean():.1f} PPG in {len(df)} games')
