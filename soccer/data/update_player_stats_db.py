import json
import os
from datetime import datetime

def update_player_stats_db(new_stats: dict, db_path='player_stats_backup.json'):
    """
    Merge new player stats into canonical player_stats_backup.json.
    - Updates only fields with new data
    - Adds new players
    - Sets last_updated timestamp per player
    """
    db_path = os.path.join(os.path.dirname(__file__), db_path)
    if os.path.exists(db_path):
        with open(db_path) as f:
            db = json.load(f)
        players = db.get('players', {})
    else:
        players = {}
    for player, stats in new_stats.items():
        if player in players:
            players[player].update(stats)
        else:
            players[player] = stats
        players[player]['last_updated'] = datetime.now().isoformat()
    db = {
        'exported_at': datetime.now().isoformat(),
        'player_count': len(players),
        'players': players
    }
    with open(db_path, 'w') as f:
        json.dump(db, f, indent=2)

# Example usage:
# new_stats = {
#     'erling haaland': {'goals': 1.02, 'shots': 4.5},
#     'bukayo saka': {'assists': 0.55}
# }
# update_player_stats_db(new_stats)
