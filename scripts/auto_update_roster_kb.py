"""Auto-update LocalValidator roster knowledge from picks.json (source of truth)."""
import json
import os
import re
from datetime import datetime


def update_roster_from_picks():
    """Update roster knowledge base from picks.json - your source of truth."""
    
    # Load current picks
    try:
        with open('picks.json', 'r', encoding='utf-8') as f:
            picks_data = json.load(f)
    except FileNotFoundError:
        print("❌ picks.json not found - skipping auto-update")
        return 0
    
    # Load current knowledge base
    kb_path = 'cache/nba_roster_kb.json'
    if os.path.exists(kb_path):
        with open(kb_path, 'r', encoding='utf-8') as f:
            kb = json.load(f)
    else:
        kb = {"rosters": {}, "last_updated": "", "source": "picks.json"}
    
    # Extract player-team mappings from picks
    updated_count = 0
    for pick in picks_data:
        player_name = pick.get('player', '').lower()
        team = pick.get('team', '')
        
        if player_name and team and team != "TBD":
            # Update KB with latest info from Underdog
            kb["rosters"][player_name] = team
            updated_count += 1
    
    # Update metadata
    kb["last_updated"] = datetime.now().isoformat()
    kb["source"] = "picks.json (Underdog manual entry)"
    kb["player_count"] = len(kb["rosters"])
    
    # Save updated KB
    os.makedirs('cache', exist_ok=True)
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2)
    
    print(f"✅ Updated roster KB with {updated_count} players from picks.json")
    return updated_count


def update_local_validator():
    """Sync the LocalValidator TEAM_KNOWLEDGE with picks.json."""
    
    # Load picks to get current teams
    try:
        with open('picks.json', 'r', encoding='utf-8') as f:
            picks_data = json.load(f)
    except FileNotFoundError:
        print("❌ picks.json not found")
        return 0
    
    # Build current team mappings
    current_teams = {}
    for pick in picks_data:
        player_name = pick.get('player', '').lower()
        team = pick.get('team', '')
        
        if player_name and team and team != "TBD":
            current_teams[player_name] = team
    
    # Generate updated TEAM_KNOWLEDGE dictionary
    team_knowledge_lines = ["    TEAM_KNOWLEDGE = {"]
    for player, team in sorted(current_teams.items()):
        team_knowledge_lines.append(f'        "{player}": "{team}",')
    team_knowledge_lines.append("    }")
    team_knowledge_str = "\n".join(team_knowledge_lines)
    
    # Read current local_validator.py
    validator_path = 'local_validator.py'
    with open(validator_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace TEAM_KNOWLEDGE section (find between comments)
    pattern = r'(# TEAM_KNOWLEDGE START.*?# TEAM_KNOWLEDGE END)'
    replacement = f"# TEAM_KNOWLEDGE START (auto-updated from picks.json)\n{team_knowledge_str}\n    # TEAM_KNOWLEDGE END"
    
    if '# TEAM_KNOWLEDGE START' in content:
        # Markers exist, do replacement
        updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        # No markers, replace the TEAM_KNOWLEDGE dict directly
        pattern = r'    TEAM_KNOWLEDGE = \{[^}]+\}'
        replacement = team_knowledge_str
        updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write back
    with open(validator_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"✅ Updated LocalValidator with {len(current_teams)} current players from picks.json")
    return len(current_teams)


if __name__ == "__main__":
    print("="*80)
    print("AUTO-UPDATING ROSTER KB FROM PICKS.JSON (SOURCE OF TRUTH)")
    print("="*80)
    
    # Update both the cache and the validator
    kb_count = update_roster_from_picks()
    lv_count = update_local_validator()
    
    print("\n✅ Update complete!")
    print(f"   Roster KB: {kb_count} players")
    print(f"   LocalValidator: {lv_count} players")
    print("\n💡 This KB now matches exactly what you see on Underdog!")
