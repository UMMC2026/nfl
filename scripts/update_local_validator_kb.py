"""Auto-update LocalValidator knowledge base from live NBA data."""
import json
import re
from nba_api.stats.endpoints import commonallplayers
from nba_api.stats.static import teams
import time


def fetch_current_nba_rosters():
    """Fetch current NBA rosters and generate LocalValidator TEAM_KNOWLEDGE dict."""
    print("🏀 Fetching current NBA rosters from nba_api...")
    
    # Get all players (not just current season to avoid filtering out stars)
    all_players = commonallplayers.CommonAllPlayers(
        is_only_current_season=0,  # Get all players, we'll filter by team
        league_id='00',
        season='2024-25'
    ).get_normalized_dict()
    
    time.sleep(0.6)  # Rate limiting
    
    # Build team mapping
    nba_teams = teams.get_teams()
    team_abbrev_map = {t['id']: t['abbreviation'] for t in nba_teams}
    
    # Build roster knowledge base (lowercase player names)
    # Only include players with valid team IDs (exclude FA/retired)
    roster_kb = {}
    for player_dict in all_players['CommonAllPlayers']:
        player_name = player_dict['DISPLAY_FIRST_LAST'].lower()
        team_id = player_dict['TEAM_ID']
        
        # Only include if they have a valid NBA team
        if team_id in team_abbrev_map:
            team_abbrev = team_abbrev_map[team_id]
            roster_kb[player_name] = team_abbrev
    
    print(f"✅ Fetched {len(roster_kb)} active NBA players")
    return roster_kb


def update_local_validator_file(roster_kb, top_n=50):
    """Update local_validator.py with current roster data."""
    # Prioritize high-profile players (common in Underdog slates)
    priority_players = [
        'lebron james', 'stephen curry', 'kevin durant', 'giannis antetokounmpo',
        'luka doncic', 'nikola jokic', 'joel embiid', 'jayson tatum', 'anthony davis',
        'damian lillard', 'anthony edwards', 'shai gilgeous-alexander', 'devin booker',
        'donovan mitchell', 'kyrie irving', 'jimmy butler', 'kawhi leonard', 'paul george',
        'victor wembanyama', 'ja morant', 'trae young', 'lamelo ball', 'tyrese haliburton',
        'domantas sabonis', 'bam adebayo', 'julius randle', 'james harden', 'bradley beal',
        'demar derozan', 'kristaps porzingis', 'karl-anthony towns', 'og anunoby',
        'mikal bridges', 'jalen brunson', 'tyrese maxey', 'alperen sengun', 'cade cunningham',
        'franz wagner', 'paolo banchero', 'scottie barnes', 'evan mobley', 'jarrett allen',
        'jonas valanciunas', 'chris paul', 'russell westbrook', 'klay thompson', 'draymond green'
    ]
    
    # Read current file
    with open('local_validator.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Generate new TEAM_KNOWLEDGE dict (priority players first, then fill remaining)
    kb_lines = ["    TEAM_KNOWLEDGE = {"]
    
    added_players = set()
    
    # Add priority players first
    for player in priority_players:
        if player in roster_kb:
            kb_lines.append(f'        "{player}": "{roster_kb[player]}",')
            added_players.add(player)
    
    # Fill remaining slots with other players
    remaining = top_n - len(added_players)
    for player, team in sorted(roster_kb.items()):
        if len(added_players) >= top_n:
            break
        if player not in added_players:
            kb_lines.append(f'        "{player}": "{team}",')
            added_players.add(player)
    
    kb_lines.append("    }")
    new_kb_block = "\n".join(kb_lines)
    
    # Replace TEAM_KNOWLEDGE block
    pattern = r'    TEAM_KNOWLEDGE = \{[^}]+\}'
    updated_content = re.sub(pattern, new_kb_block, content, flags=re.DOTALL)
    
    # Write back
    with open('local_validator.py', 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"✅ Updated local_validator.py with {len(added_players)} players")
    print(f"   Priority players: {len([p for p in priority_players if p in roster_kb])}/{len(priority_players)}")



def generate_kb_json_for_ollama(roster_kb):
    """Save roster KB as JSON for Ollama prompt injection."""
    output = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'season': '2024-25',
        'player_count': len(roster_kb),
        'rosters': roster_kb
    }
    
    with open('cache/nba_roster_kb.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Saved roster KB to cache/nba_roster_kb.json")


if __name__ == '__main__':
    print("="*80)
    print("AUTO-UPDATING LOCALVALIDATOR KNOWLEDGE BASE")
    print("="*80)
    
    # Fetch current rosters
    roster_kb = fetch_current_nba_rosters()
    
    # Option 1: Update LocalValidator file with top 50 players
    update_local_validator_file(roster_kb, top_n=50)
    
    # Option 2: Save full roster KB for Ollama prompt injection
    generate_kb_json_for_ollama(roster_kb)
    
    print("\n✅ Update complete!")
    print("\nNext steps:")
    print("1. Review local_validator.py to ensure key players are included")
    print("2. Run generate_cheatsheet.py to validate with updated KB")
    print("3. For Ollama: load cache/nba_roster_kb.json in prompts")
