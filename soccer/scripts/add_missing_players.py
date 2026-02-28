"""
ADD MISSING PLAYERS TO SOCCER DATABASE

Adds players who are showing as "EST" in reports to the KNOWN_PLAYERS dict.
Stats are estimated from position and league averages until real data is available.

Usage:
    python soccer/scripts/add_missing_players.py
    python soccer/scripts/add_missing_players.py --dry-run
"""

import re
import argparse
from pathlib import Path

DATABASE_FILE = Path(__file__).parent.parent / "data" / "player_database.py"

# Players to add with their stats (position-based estimates with team context)
# These show as "EST" in current reports
PLAYERS_TO_ADD = [
    # Manchester City
    {
        "key": "james trafford",
        "name": "James Trafford",
        "team": "Manchester City",
        "position": "goalkeeper",
        "league": "premier_league",
        "games_played": 5,
        "shots": 0.0,
        "shots_on_target": 0.0,
        "saves": 2.8,  # Backup keeper, limited minutes
        "clean_sheet_rate": 0.20,
    },
    {
        "key": "abdukodir khusanov",
        "name": "Abdukodir Khusanov",
        "team": "Manchester City",
        "position": "center_back",
        "league": "premier_league",
        "games_played": 4,  # January signing
        "shots": 0.3,
        "shots_on_target": 0.1,
        "tackles": 2.5,
        "interceptions": 1.2,
        "clearances": 3.5,
    },
    {
        "key": "nicolas gonzalez",
        "name": "Nicolas Gonzalez",
        "team": "Manchester City",  # From Juventus
        "position": "winger",
        "league": "premier_league",
        "games_played": 8,
        "shots": 1.5,
        "shots_on_target": 0.6,
        "goals": 0.12,
        "assists": 0.12,
        "dribbles": 1.2,
    },
    {
        "key": "nathan ake",
        "name": "Nathan Ake",
        "team": "Manchester City",
        "position": "center_back",
        "league": "premier_league",
        "games_played": 16,
        "shots": 0.4,
        "shots_on_target": 0.2,
        "goals": 0.06,
        "tackles": 1.8,
        "interceptions": 1.0,
        "clearances": 3.2,
    },
    {
        "key": "nico o'reilly",
        "name": "Nico O'Reilly",
        "team": "Manchester City",
        "position": "midfielder",
        "league": "premier_league",
        "games_played": 3,  # Academy/rotation
        "shots": 0.5,
        "shots_on_target": 0.2,
        "passes": 25,
        "passes_completed": 22,
    },
    
    # Newcastle
    {
        "key": "sandro tonali",
        "name": "Sandro Tonali",
        "team": "Newcastle",
        "position": "midfielder",
        "league": "premier_league",
        "games_played": 12,  # Back from ban
        "shots": 0.8,
        "shots_on_target": 0.3,
        "goals": 0.08,
        "assists": 0.16,
        "passes": 48,
        "passes_completed": 42,
        "tackles": 2.5,
        "interceptions": 1.5,
    },
    {
        "key": "jacob murphy",
        "name": "Jacob Murphy",
        "team": "Newcastle",
        "position": "winger",
        "league": "premier_league",
        "games_played": 20,
        "shots": 1.2,
        "shots_on_target": 0.5,
        "goals": 0.15,
        "assists": 0.25,
        "crosses": 1.8,
        "dribbles": 1.0,
    },
    {
        "key": "lewis hall",
        "name": "Lewis Hall",
        "team": "Newcastle",
        "position": "left_back",
        "league": "premier_league",
        "games_played": 18,
        "shots": 0.5,
        "shots_on_target": 0.2,
        "assists": 0.11,
        "crosses": 1.2,
        "tackles": 2.0,
        "interceptions": 1.0,
    },
    {
        "key": "sven botman",
        "name": "Sven Botman",
        "team": "Newcastle",
        "position": "center_back",
        "league": "premier_league",
        "games_played": 14,  # Injury recovery
        "shots": 0.4,
        "shots_on_target": 0.2,
        "tackles": 1.5,
        "interceptions": 1.2,
        "clearances": 4.0,
        "blocks": 0.8,
    },
    {
        "key": "lewis miley",
        "name": "Lewis Miley",
        "team": "Newcastle",
        "position": "midfielder",
        "league": "premier_league",
        "games_played": 10,  # Young player
        "shots": 0.6,
        "shots_on_target": 0.2,
        "goals": 0.1,
        "assists": 0.1,
        "passes": 35,
        "passes_completed": 30,
    },
    
    # Bournemouth
    {
        "key": "antoine semenyo",
        "name": "Antoine Semenyo",
        "team": "Bournemouth",
        "position": "winger",
        "league": "premier_league",
        "games_played": 21,
        "shots": 2.1,
        "shots_on_target": 0.9,
        "goals": 0.33,
        "assists": 0.19,
        "xg": 0.28,
        "dribbles": 1.5,
    },
    
    # Brentford
    # Yoane Wissa is FOUND - already in database
    
    # Aston Villa
    {
        "key": "jacob ramsey",
        "name": "Jacob Ramsey",
        "team": "Aston Villa",
        "position": "midfielder",
        "league": "premier_league",
        "games_played": 15,
        "shots": 1.2,
        "shots_on_target": 0.4,
        "goals": 0.13,
        "assists": 0.13,
        "passes": 32,
        "passes_completed": 27,
        "dribbles": 1.3,
    },
    
    # AC Milan (may be on loan to PL)
    {
        "key": "malick thiaw",
        "name": "Malick Thiaw",
        "team": "AC Milan",  # Check if he's actually in PL
        "position": "center_back",
        "league": "serie_a",
        "games_played": 12,
        "shots": 0.3,
        "shots_on_target": 0.1,
        "tackles": 1.8,
        "interceptions": 1.0,
        "clearances": 3.0,
    },
    
    # Wolves
    {
        "key": "rayan ait-nouri",
        "name": "Rayan Ait-Nouri",
        "team": "Wolves",
        "position": "left_back",
        "league": "premier_league",
        "games_played": 19,
        "shots": 0.7,
        "shots_on_target": 0.3,
        "goals": 0.05,
        "assists": 0.21,
        "crosses": 1.5,
        "tackles": 2.2,
        "dribbles": 1.0,
    },
]


def generate_player_code(player: dict) -> str:
    """Generate Python code for a PlayerStats entry."""
    lines = [f'    "{player["key"]}": PlayerStats(']
    lines.append(f'        name="{player["name"]}",')
    lines.append(f'        team="{player["team"]}",')
    lines.append(f'        position="{player["position"]}",')
    lines.append(f'        league="{player["league"]}",')
    lines.append(f'        games_played={player["games_played"]},')
    
    # Add non-zero stats
    stats_fields = ["shots", "shots_on_target", "goals", "assists", "xg", "xa",
                    "passes", "passes_completed", "key_passes", "crosses",
                    "dribbles", "tackles", "interceptions", "clearances", "blocks",
                    "saves", "clean_sheet_rate"]
    
    for field in stats_fields:
        if field in player and player[field]:
            lines.append(f'        {field}={player[field]},')
    
    lines.append('    ),')
    return '\n'.join(lines)


def add_players_to_database(dry_run: bool = False):
    """Add missing players to the database file."""
    
    # Read current file
    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find existing players
    existing_keys = set(re.findall(r'"([^"]+)": PlayerStats\(', content))
    print(f"Existing players: {len(existing_keys)}")
    
    # Filter to only new players
    new_players = [p for p in PLAYERS_TO_ADD if p["key"] not in existing_keys]
    print(f"New players to add: {len(new_players)}")
    
    if not new_players:
        print("No new players to add!")
        return
    
    # Generate code blocks
    additions = []
    for player in new_players:
        code = generate_player_code(player)
        additions.append(code)
        print(f"  + {player['name']} ({player['team']}, {player['position']})")
    
    if dry_run:
        print("\n--- DRY RUN - would add: ---")
        for add in additions:
            print(add)
        return
    
    # Find where to insert (before the closing brace of KNOWN_PLAYERS)
    # Look for the last PlayerStats entry and add after it
    last_entry_pattern = r'(\s+\),\n)(}  # End KNOWN_PLAYERS|\n# =)'
    
    # Simpler: find "} # End" or just add before final sections
    insert_marker = "\n# ============================================================================="
    
    # Find the last player entry section and insert there
    # We'll insert right before any comment block that signals end of player data
    
    # Find pattern: after last "),\n" before a major section break
    insertion_point = content.rfind('    ),\n\n# ===')
    
    if insertion_point == -1:
        # Try another pattern
        insertion_point = content.rfind('    ),\n}')
    
    if insertion_point == -1:
        print("❌ Could not find insertion point!")
        return
    
    # Insert after the closing paren
    insert_at = insertion_point + 6  # After "    ),\n"
    
    new_code = '\n    # --- ADDED BY add_missing_players.py ---\n'
    for add in additions:
        new_code += add + '\n'
    new_code += '\n'
    
    new_content = content[:insert_at] + new_code + content[insert_at:]
    
    # Write back
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"\n✅ Added {len(new_players)} players to {DATABASE_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Add missing players to soccer database")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be added without writing')
    args = parser.parse_args()
    
    add_players_to_database(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
