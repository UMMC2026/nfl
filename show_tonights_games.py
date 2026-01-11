"""
Show tonight's NBA games
"""
import requests
from datetime import datetime

def get_tonights_games():
    """Fetch tonight's NBA games from ESPN."""
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        games = data.get('events', [])
        
        if not games:
            print(f"📅 No NBA games scheduled for tonight ({datetime.now().strftime('%B %d, %Y')})")
            return
        
        print(f"🏀 NBA GAMES - {datetime.now().strftime('%A, %B %d, %Y')}")
        print("=" * 60)
        
        for game in games:
            # Get teams
            competitions = game.get('competitions', [{}])[0]
            competitors = competitions.get('competitors', [])
            
            if len(competitors) >= 2:
                away_team = competitors[1]
                home_team = competitors[0]
                
                away_name = away_team.get('team', {}).get('displayName', 'Unknown')
                home_name = home_team.get('team', {}).get('displayName', 'Unknown')
                
                away_abbr = away_team.get('team', {}).get('abbreviation', '???')
                home_abbr = home_team.get('team', {}).get('abbreviation', '???')
                
                # Get status
                status = game.get('status', {})
                status_type = status.get('type', {}).get('name', 'Unknown')
                status_detail = status.get('type', {}).get('detail', '')
                
                # Get scores if available
                away_score = away_team.get('score', '')
                home_score = home_team.get('score', '')
                
                # Get time
                game_time = game.get('date', '')
                if game_time:
                    game_dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                    time_str = game_dt.strftime('%I:%M %p ET')
                else:
                    time_str = 'TBD'
                
                print(f"\n{away_abbr} @ {home_abbr}")
                print(f"  {away_name} @ {home_name}")
                
                if away_score and home_score:
                    print(f"  Score: {away_abbr} {away_score}, {home_abbr} {home_score}")
                
                print(f"  Status: {status_detail}")
                print(f"  Time: {time_str}")
        
        print("\n" + "=" * 60)
        print(f"Total games: {len(games)}")
        
    except Exception as e:
        print(f"❌ Failed to fetch games: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    get_tonights_games()
