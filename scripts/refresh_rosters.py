"""
Refresh NBA Active Roster from Live Data
Ensures roster files are current for verification gate
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from nba_api.stats.static import players
from nba_api.stats.endpoints import commonteamroster
import time


NBA_TEAMS = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766,
    "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
    "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "WAS": 1610612764,
}


def fetch_team_roster(team_abbr: str, team_id: int) -> list:
    """Fetch current roster for a team"""
    try:
        roster = commonteamroster.CommonTeamRoster(team_id=team_id)
        players_df = roster.get_data_frames()[0]
        
        roster_entries = []
        for _, player in players_df.iterrows():
            roster_entries.append({
                'player_name': player['PLAYER'],
                'team': team_abbr,
                'status': 'ACTIVE',  # Will update with injury data later
                'game_id': f'{team_abbr}-ROSTER',
                'updated_utc': datetime.now(timezone.utc).isoformat()
            })
        
        return roster_entries
        
    except Exception as e:
        print(f"⚠️  Failed to fetch {team_abbr} roster: {e}")
        return []


def main():
    print("\n" + "="*70)
    print("  🔄 REFRESHING NBA ACTIVE ROSTERS")
    print("="*70 + "\n")
    
    all_rosters = []
    teams_fetched = 0
    
    for team_abbr, team_id in NBA_TEAMS.items():
        print(f"Fetching {team_abbr}...", end=" ")
        roster = fetch_team_roster(team_abbr, team_id)
        
        if roster:
            all_rosters.extend(roster)
            teams_fetched += 1
            print(f"✅ {len(roster)} players")
        else:
            print("❌ Failed")
        
        time.sleep(0.6)  # Rate limiting
    
    # Save to CSV
    output_dir = Path('data_center/rosters')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d')
    output_path = output_dir / f'NBA_active_roster_{timestamp}.csv'
    current_path = output_dir / 'NBA_active_roster_current.csv'
    
    if all_rosters:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['player_name', 'team', 'status', 'game_id', 'updated_utc'])
            writer.writeheader()
            writer.writerows(all_rosters)
        
        # Also update "current" symlink/copy
        with open(current_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['player_name', 'team', 'status', 'game_id', 'updated_utc'])
            writer.writeheader()
            writer.writerows(all_rosters)
        
        print("\n" + "="*70)
        print(f"✅ SUCCESS: {len(all_rosters)} players from {teams_fetched}/30 teams")
        print(f"📁 Saved to: {output_path}")
        print(f"📁 Updated: {current_path}")
        print("="*70 + "\n")
    else:
        print("\n❌ No roster data fetched!")
        return False
    
    return True


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
