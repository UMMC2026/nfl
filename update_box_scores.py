"""
Update Box Scores from ESPN Official API

Fetches final game results from ESPN's official JSON endpoints and updates
the ResultsTracker with HIT/MISS/PUSH outcomes for yesterday's picks.

Only processes games that are FINAL (status.type.state == "post").
"""

import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import ResultsTracker
from ufa.analysis.results_tracker import ResultsTracker


def fetch_espn_scoreboard(date: str) -> Optional[Dict]:
    """
    Fetch ESPN scoreboard for a specific date.
    
    Args:
        date: Date in YYYYMMDD format
        
    Returns:
        Scoreboard JSON or None if failed
    """
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to fetch scoreboard for {date}: {e}")
        return None


def fetch_espn_box_score(game_id: str) -> Optional[Dict]:
    """
    Fetch ESPN box score for a specific game.
    
    Args:
        game_id: ESPN game ID
        
    Returns:
        Box score JSON or None if failed
    """
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"Fetched box score for game {game_id}")
        return data
    except Exception as e:
        print(f"Failed to fetch box score for game {game_id}: {e}")
        return None


def extract_player_stats(box_score: Dict) -> Dict[str, Dict]:
    """
    Extract player statistics from ESPN box score.
    
    Args:
        box_score: ESPN box score JSON
        
    Returns:
        Dict mapping player name to stats dict
    """
    player_stats = {}
    
    print(f"Box score keys: {list(box_score.keys())}")
    
    # Check if boxscore exists
    boxscore_data = box_score.get('boxscore', {})
    print(f"Boxscore keys: {list(boxscore_data.keys()) if isinstance(boxscore_data, dict) else type(boxscore_data)}")
    
    teams = boxscore_data.get('teams', [])
    print(f"Found {len(teams)} teams in boxscore")
    for i, team in enumerate(teams):
        print(f"Team {i}: keys = {list(team.keys()) if isinstance(team, dict) else type(team)}")
        if isinstance(team, dict):
            team_info = team.get('team', {})
            home_away = team.get('homeAway', 'unknown')
            print(f"Team {i} info: {team_info.get('displayName', 'unknown')} (homeAway: {home_away})")
    
    teams = boxscore_data.get('teams', [])
    players = boxscore_data.get('players', [])
    print(f"Found {len(teams)} teams and {len(players)} players in boxscore")
    
    # Process players instead of athletes in teams
    for player in players:
        print(f"Player data keys: {list(player.keys()) if isinstance(player, dict) else type(player)}")
        if not isinstance(player, dict):
            continue
            
        team_info = player.get('team', {})
        print(f"Team info keys: {list(team_info.keys()) if isinstance(team_info, dict) else type(team_info)}")
        player_name = team_info.get('displayName', '').strip()
        print(f"Processing player/team: '{player_name}'")
        
        statistics = player.get('statistics', [])
        print(f"Statistics: {len(statistics)} items")
        if statistics:
            print(f"First stat item keys: {list(statistics[0].keys()) if isinstance(statistics[0], dict) else type(statistics[0])}")
            if isinstance(statistics[0], dict):
                athletes = statistics[0].get('athletes', [])
                print(f"Athletes in statistics: {len(athletes)}")
                if athletes:
                    print(f"First athlete keys: {list(athletes[0].keys()) if isinstance(athletes[0], dict) else type(athletes[0])}")
        
        if not player_name:
            continue
            
        # Get stats for this player
        stats = player.get('stats', [])
        print(f"Player {player_name} has {len(stats)} stats")
        stat_dict = {}
        
        # Map ESPN stat names to our internal names
        stat_mapping = {
            'points': 'points',
            'rebounds': 'rebounds', 
            'assists': 'assists',
            'steals': 'steals',
            'blocks': 'blocks',
            'turnovers': 'turnovers',
            'threePointFieldGoalsMade': '3pm',
            'fieldGoalsMade': 'fgm',
            'fieldGoalsAttempted': 'fga',
            'freeThrowsMade': 'ftm',
            'freeThrowsAttempted': 'fta',
            'minutes': 'minutes'
        }
        
        for stat in stats:
            espn_name = stat.get('name', '')
            value = stat.get('value', 0)
            print(f"  Stat: {espn_name} = {value}")
            
            if espn_name in stat_mapping:
                try:
                    stat_dict[stat_mapping[espn_name]] = float(value)
                except (ValueError, TypeError):
                    stat_dict[stat_mapping[espn_name]] = 0.0
        
        print(f"  Final stat_dict: {stat_dict}")
        if stat_dict:
            player_stats[player_name] = stat_dict
    
    return player_stats


def determine_pick_outcome(pick: Dict, player_stats: Dict[str, Dict]) -> Optional[str]:
    """
    Determine if a pick HIT, MISSED, or PUSHED based on final stats.
    
    Args:
        pick: Pick dict with player, stat, line, direction
        player_stats: Player stats from box score
        
    Returns:
        'HIT', 'MISS', or 'PUSH', or None if cannot determine
    """
    player_name = pick.get('player', '').strip()
    stat_key = pick.get('stat', '')
    line = pick.get('line')
    direction = pick.get('direction', '').lower()
    
    if not player_name or not stat_key or line is None:
        return None
    
    # Normalize direction
    if direction in ['over', 'higher']:
        direction = 'higher'
    elif direction in ['under', 'lower']:
        direction = 'lower'
    else:
        return None
    
    # Get player's actual stat value
    player_data = player_stats.get(player_name, {})
    actual_value = player_data.get(stat_key)
    
    if actual_value is None:
        # Player didn't play or stat not available
        return None
    
    # Determine outcome
    if direction == 'higher':
        if actual_value > line:
            return 'HIT'
        elif actual_value < line:
            return 'MISS'
        else:
            return 'PUSH'
    else:  # lower
        if actual_value < line:
            return 'HIT'
        elif actual_value > line:
            return 'MISS'
        else:
            return 'PUSH'


def update_yesterday_results():
    """
    Main function to update results for yesterday's picks.
    """
    # Get yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Fetching final results for {yesterday}...")
    
    # Fetch scoreboard for yesterday
    scoreboard = fetch_espn_scoreboard(yesterday)
    if not scoreboard:
        print("❌ Could not fetch scoreboard. Aborting.")
        return
    
    # Get list of events (games)
    events = scoreboard.get('events', [])
    if not events:
        print(f"ℹ️ No games found for {yesterday}.")
        return
    
    print(f"Found {len(events)} games. Processing final games only...")
    
    # Collect all player stats from final games
    all_player_stats = {}
    
    for event in events:
        game_id = event.get('id', '')
        status = event.get('status', {})
        state = status.get('type', {}).get('state', '')
        
        if state != 'post':
            print(f"Game {game_id} status: {state} (skipping)")
            continue
            
        print(f"Processing final game {game_id}...")
        
        # Fetch box score
        box_score = fetch_espn_box_score(game_id)
        if not box_score:
            print(f"Failed to fetch box score for game {game_id}")
            continue
            
        # Extract player stats
        game_player_stats = extract_player_stats(box_score)
        print(f"Extracted {len(game_player_stats)} player stats for game {game_id}")
        
        # Merge into all_player_stats (player names should be unique across games in a day)
        for player_name, stats in game_player_stats.items():
            if player_name in all_player_stats:
                print(f"Player {player_name} appears in multiple games - using first occurrence")
                continue
            all_player_stats[player_name] = stats
    
    if not all_player_stats:
        print("No player stats found in any final games.")
        return
    
    print(f"Collected stats for {len(all_player_stats)} players")
    
    # Initialize results tracker
    tracker = ResultsTracker()
    
    # Load yesterday's picks
    picks = tracker.load_picks(date_str)
    if not picks:
        print(f"No picks found for {date_str}")
        return
    
    print(f"Found {len(picks)} picks to resolve")
    
    updated_count = 0
    
    # Update each pick
    for pick in picks:
        if pick.result not in ["PENDING", "UNKNOWN"]:
            continue  # Already resolved
        
        outcome = determine_pick_outcome({
            'player': pick.player,
            'stat': pick.stat,
            'line': pick.line,
            'direction': pick.direction
        }, all_player_stats)
        
        if outcome:
            # Get actual value for the stat
            player_stats = all_player_stats.get(pick.player, {})
            actual_value = player_stats.get(pick.stat)
            
            if actual_value is not None:
                tracker.update_result(
                    date=date_str,
                    player=pick.player,
                    stat=pick.stat,
                    result=outcome,
                    actual_value=actual_value
                )
                
                print(f"{pick.player} {pick.stat}: {actual_value:.1f} {outcome}")
                updated_count += 1
            else:
                print(f"No stat data for {pick.player} {pick.stat}")
        else:
            print(f"Could not determine outcome for {pick.player} {pick.stat}")
    
    print(f"Updated {updated_count} picks")
    print("Results tracker updated. Run cheatsheet generation to see win rates.")


if __name__ == "__main__":
    update_yesterday_results()