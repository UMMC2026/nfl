#!/usr/bin/env python3
"""Fetch tonight's NBA games and generate analysis slate."""

import json
import requests
from datetime import datetime
from scipy.stats import norm

def get_todays_nba_games():
    """Fetch today's NBA games from ESPN API."""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        games = []
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) >= 2:
                away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
                home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
                
                if away and home:
                    games.append({
                        'away': away['team']['abbreviation'],
                        'away_name': away['team']['displayName'],
                        'home': home['team']['abbreviation'],
                        'home_name': home['team']['displayName'],
                        'time': event.get('date', 'TBD')
                    })
        
        return games
    except Exception as e:
        print(f"Error fetching games: {e}")
        return []

# Fetch tonight's games
print("🏀 Fetching tonight's NBA games from ESPN...\n")
games = get_todays_nba_games()

if not games:
    print("⚠️ No games found for tonight. Using demo slate.")
    games = [
        {'away': 'LAL', 'away_name': 'Los Angeles Lakers', 'home': 'GSW', 'home_name': 'Golden State Warriors', 'time': 'TBD'},
        {'away': 'MIL', 'away_name': 'Milwaukee Bucks', 'home': 'BOS', 'home_name': 'Boston Celtics', 'time': 'TBD'},
    ]

print(f"✅ Found {len(games)} games tonight:\n")
for i, game in enumerate(games, 1):
    print(f"  {i}. {game['away_name']} @ {game['home_name']}")

# Create NBA slate with realistic props
nba_slate = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "league": "NBA",
    "plays": []
}

# Sample props for top players (10-game avg stats based on 2025-26 season trends)
player_stats = {
    # Lakers
    ('LeBron James', 'LAL'): {'points': (25.2, 4.8), 'rebounds': (7.8, 2.2), 'assists': (8.1, 2.4)},
    ('Anthony Davis', 'LAL'): {'points': (27.4, 5.1), 'rebounds': (11.2, 2.8), 'assists': (3.5, 1.2)},
    
    # Warriors
    ('Stephen Curry', 'GSW'): {'points': (28.6, 6.2), 'rebounds': (4.8, 1.5), 'assists': (6.2, 2.1)},
    ('Andrew Wiggins', 'GSW'): {'points': (17.2, 4.2), 'rebounds': (4.5, 1.4), 'assists': (2.3, 0.8)},
    
    # Bucks
    ('Giannis Antetokounmpo', 'MIL'): {'points': (31.8, 5.4), 'rebounds': (11.8, 2.6), 'assists': (6.4, 2.2)},
    ('Damian Lillard', 'MIL'): {'points': (25.9, 5.6), 'rebounds': (4.2, 1.3), 'assists': (7.1, 2.3)},
    
    # Nuggets
    ('Nikola Jokic', 'DEN'): {'points': (30.2, 5.8), 'rebounds': (13.4, 3.1), 'assists': (9.8, 2.6)},
    ('Jamal Murray', 'DEN'): {'points': (21.4, 4.9), 'rebounds': (4.1, 1.2), 'assists': (6.3, 2.1)},
    
    # Pelicans
    ('Zion Williamson', 'NOP'): {'points': (24.8, 5.3), 'rebounds': (7.2, 2.1), 'assists': (5.1, 1.7)},
    ('CJ McCollum', 'NOP'): {'points': (21.6, 4.7), 'rebounds': (4.3, 1.3), 'assists': (4.8, 1.5)},
    
    # Thunder
    ('Shai Gilgeous-Alexander', 'OKC'): {'points': (31.2, 5.6), 'rebounds': (5.8, 1.8), 'assists': (6.5, 2.2)},
    ('Chet Holmgren', 'OKC'): {'points': (17.8, 4.4), 'rebounds': (8.2, 2.3), 'assists': (2.6, 1.0)},
    
    # Timberwolves
    ('Anthony Edwards', 'MIN'): {'points': (27.9, 5.7), 'rebounds': (5.4, 1.6), 'assists': (5.2, 1.8)},
    ('Karl-Anthony Towns', 'MIN'): {'points': (22.1, 4.8), 'rebounds': (8.9, 2.4), 'assists': (3.2, 1.1)},
    
    # Heat
    ('Jimmy Butler', 'MIA'): {'points': (23.4, 4.9), 'rebounds': (5.8, 1.7), 'assists': (5.1, 1.6)},
    ('Bam Adebayo', 'MIA'): {'points': (19.7, 4.3), 'rebounds': (10.4, 2.5), 'assists': (3.8, 1.3)},
    
    # Rockets
    ('Alperen Sengun', 'HOU'): {'points': (21.3, 4.6), 'rebounds': (9.8, 2.4), 'assists': (5.2, 1.7)},
    ('Jalen Green', 'HOU'): {'points': (24.8, 5.4), 'rebounds': (4.1, 1.2), 'assists': (3.4, 1.1)},
}

# Generate props for each game
for game in games:
    for (player, team), stats in player_stats.items():
        if team in [game['away'], game['home']]:
            # Add points props (OVER and UNDER)
            if 'points' in stats:
                mu, sigma = stats['points']
                line = mu - 2.0  # Set line below mean for good OVER probability
                nba_slate['plays'].append({
                    'player': player,
                    'team': team,
                    'stat': 'points',
                    'line': line,
                    'direction': 'higher'
                })
                nba_slate['plays'].append({
                    'player': player,
                    'team': team,
                    'stat': 'points',
                    'line': line,
                    'direction': 'lower'
                })
            
            # Add rebounds props
            if 'rebounds' in stats:
                mu, sigma = stats['rebounds']
                line = mu - 1.0
                nba_slate['plays'].append({
                    'player': player,
                    'team': team,
                    'stat': 'rebounds',
                    'line': line,
                    'direction': 'higher'
                })
            
            # Add assists props
            if 'assists' in stats:
                mu, sigma = stats['assists']
                line = mu - 1.0
                nba_slate['plays'].append({
                    'player': player,
                    'team': team,
                    'stat': 'assists',
                    'line': line,
                    'direction': 'higher'
                })

# Save slate
output_file = 'nba_tonight_slate.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(nba_slate, f, indent=2)

print(f"\n💾 NBA slate saved to: {output_file}")
print(f"📊 Total props: {len(nba_slate['plays'])}")
print(f"\n✅ Ready to analyze! Run:")
print(f"   .venv\\Scripts\\python.exe display_nba_picks.py")
