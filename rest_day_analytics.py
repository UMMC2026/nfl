"""Enhanced hydration with rest day analytics."""
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import numpy as np

def nba_recent_values_with_rest_analysis(player_name: str, stat_key: str, season: str, last_n: int = 10) -> Dict:
    """
    Pull recent NBA game log WITH rest day analytics.
    Returns: {
        'recent_values': [float],
        'game_dates': [datetime],
        'rest_days': [int],
        'rest_analysis': {
            'avg_on_b2b': float,
            'avg_on_rest': float,
            'rest_advantage': float,
            'upcoming_rest': int
        }
    }
    """
    try:
        from nba_api.stats.static import players
        from nba_api.stats.endpoints import playergamelog
    except Exception as e:
        raise RuntimeError("nba_api not installed.") from e
    
    from ufa.ingest.stat_map import NBA_STAT_KEYS
    
    col = NBA_STAT_KEYS.get(stat_key)
    if not col:
        raise ValueError(f"Unsupported stat_key: {stat_key}")
    
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        raise ValueError(f"Player not found: {player_name}")
    
    pid = int(matches[0]["id"])
    gl = playergamelog.PlayerGameLog(player_id=pid, season=season)
    df = gl.get_data_frames()[0]
    
    if df.empty or len(df) < 2:
        raise ValueError("Not enough games returned.")
    
    # Get stat values
    if isinstance(col, list):
        vals = df[col].head(last_n).sum(axis=1).astype(float).tolist()
    else:
        vals = df[col].head(last_n).astype(float).tolist()
    
    # Parse game dates
    df_subset = df.head(last_n).copy()
    df_subset['GAME_DATE_DT'] = pd.to_datetime(df_subset['GAME_DATE'])
    game_dates = df_subset['GAME_DATE_DT'].tolist()
    
    # Calculate rest days between games
    rest_days = []
    for i in range(len(game_dates)):
        if i == 0:
            rest_days.append(None)  # Most recent game, no "previous" game
        else:
            days_diff = (game_dates[i-1] - game_dates[i]).days - 1
            rest_days.append(max(0, days_diff))
    
    # Analyze performance by rest
    b2b_vals = []  # Back-to-back (0 days rest)
    rest_vals = []  # 1+ days rest
    
    for i, (val, rest) in enumerate(zip(vals, rest_days)):
        if rest is None:
            continue  # Skip most recent game (no rest data)
        if rest == 0:
            b2b_vals.append(val)
        else:
            rest_vals.append(val)
    
    # Calculate averages
    avg_on_b2b = np.mean(b2b_vals) if b2b_vals else None
    avg_on_rest = np.mean(rest_vals) if rest_vals else None
    
    # Rest advantage (how much better with rest)
    if avg_on_b2b is not None and avg_on_rest is not None:
        rest_advantage = avg_on_rest - avg_on_b2b
        rest_advantage_pct = (rest_advantage / avg_on_b2b * 100) if avg_on_b2b > 0 else 0
    else:
        rest_advantage = None
        rest_advantage_pct = None
    
    # Calculate upcoming rest (days since most recent game)
    most_recent_game = game_dates[0]
    today = datetime.now()
    upcoming_rest = (today - most_recent_game).days - 1
    
    return {
        'recent_values': vals,
        'game_dates': [d.strftime('%Y-%m-%d') for d in game_dates],
        'rest_days': rest_days,
        'rest_analysis': {
            'avg_on_b2b': round(avg_on_b2b, 1) if avg_on_b2b else None,
            'avg_on_rest': round(avg_on_rest, 1) if avg_on_rest else None,
            'rest_advantage': round(rest_advantage, 1) if rest_advantage else None,
            'rest_advantage_pct': round(rest_advantage_pct, 1) if rest_advantage_pct else None,
            'b2b_games': len(b2b_vals),
            'rested_games': len(rest_vals),
            'upcoming_rest': upcoming_rest
        }
    }


def format_rest_commentary(rest_analysis: Dict, player: str, stat: str) -> str:
    """Generate human-readable rest day commentary."""
    ra = rest_analysis
    
    if ra['avg_on_b2b'] is None or ra['avg_on_rest'] is None:
        return f"⚠️ Insufficient rest data for {player}"
    
    commentary = f"📅 *Rest Day Analysis - {player}*\n"
    commentary += f"Last {ra['b2b_games'] + ra['rested_games']} games:\n"
    commentary += f"  • Back-to-back (0 rest): {ra['avg_on_b2b']} {stat} avg ({ra['b2b_games']} games)\n"
    commentary += f"  • With rest (1+ days): {ra['avg_on_rest']} {stat} avg ({ra['rested_games']} games)\n"
    
    if ra['rest_advantage'] and abs(ra['rest_advantage']) >= 1.0:
        direction = "better" if ra['rest_advantage'] > 0 else "worse"
        commentary += f"\n📊 Rest Impact: {abs(ra['rest_advantage'])} {stat} {direction} with rest "
        commentary += f"({ra['rest_advantage_pct']:+.1f}%)\n"
    
    # Upcoming game context
    if ra['upcoming_rest'] == 0:
        commentary += f"\n⚡️ ALERT: Playing on back-to-back (0 days rest)"
    elif ra['upcoming_rest'] == 1:
        commentary += f"\n✅ Standard rest (1 day)"
    elif ra['upcoming_rest'] >= 2:
        commentary += f"\n🔋 EXTRA REST: {ra['upcoming_rest']} days since last game"
    
    return commentary


# Example usage
if __name__ == "__main__":
    import pandas as pd
    
    # Test with a known player
    try:
        result = nba_recent_values_with_rest_analysis(
            player_name="Deni Avdija",
            stat_key="3pm",
            season="2024-25",
            last_n=10
        )
        
        print("Recent Values:", result['recent_values'])
        print("\nGame Dates:", result['game_dates'])
        print("Rest Days:", result['rest_days'])
        print("\nRest Analysis:")
        for k, v in result['rest_analysis'].items():
            print(f"  {k}: {v}")
        
        print("\n" + "="*60)
        print(format_rest_commentary(result['rest_analysis'], "Deni Avdija", "3PM"))
        
    except Exception as e:
        print(f"Error: {e}")
