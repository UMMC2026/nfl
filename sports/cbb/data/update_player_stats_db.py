import json
import os
from datetime import datetime

def update_player_stats_db(new_stats: dict, db_path='player_stats.json'):
    """
    Merge new player stats into canonical player_stats.json.
    - Updates only fields with new data
    - Adds new players
    - Sets last_updated timestamp per player
    """
    db_path = os.path.join(os.path.dirname(__file__), db_path)
    if os.path.exists(db_path):
        with open(db_path) as f:
            db = json.load(f)
    else:
        db = {}
    for player, stats in new_stats.items():
        if player in db:
            db[player].update(stats)
        else:
            db[player] = stats
        db[player]['last_updated'] = datetime.now().isoformat()
    with open(db_path, 'w') as f:
        json.dump(db, f, indent=2)

# Example usage:
# new_stats = {
#     'dylan_andrews': {'points': 15.2, 'rebounds': 3.1, 'assists': 2.0},
#     'fatt_hill': {'points': 14.0, 'rebounds': 4.5}
# }
# update_player_stats_db(new_stats)
