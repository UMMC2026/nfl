import json
from datetime import datetime
from .update_player_stats_db import update_player_stats_db

def update_from_estimates(estimate_props, db_path='player_stats_backup.json'):
    """
    Update player stats DB with new estimates from scraped props.
    Only updates assists for now, but can be extended.
    """
    new_stats = {}
    for prop in estimate_props:
        player = prop.get('player', '').lower().replace(' ', '_')
        assists = prop.get('avg_assists')
        if assists is not None:
            new_stats[player] = {'assists': assists, 'source': 'estimate', 'last_updated': datetime.now().isoformat()}
    if new_stats:
        update_player_stats_db(new_stats, db_path=db_path)

# Example usage:
# estimate_props = [
#     {'player': 'Nick Boyd', 'avg_assists': 0.1},
#     {'player': 'Kimani Hamilton', 'avg_assists': 0.1},
# ]
# update_from_estimates(estimate_props)
