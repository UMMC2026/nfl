"""
SOCCER: Update Player Stats from Props + ESPN API + CSV Backup
================================================================
Extracts player names from pasted props, fetches current stats from ESPN,
updates the player database, and saves to CSV for fallback.

Usage:
    python soccer/data/update_from_props.py --slate           # From latest slate
    python soccer/data/update_from_props.py --players "Pulisic, Leao"  # Manual
    python soccer/data/update_from_props.py --export          # Export to CSV
    python soccer/data/update_from_props.py --import CSV_FILE # Import from CSV
"""

import sys
import csv
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from soccer.data.player_database import PlayerStats, KNOWN_PLAYERS

# Paths
SOCCER_DIR = PROJECT_ROOT / "soccer"
DATA_DIR = SOCCER_DIR / "data"
INPUTS_DIR = SOCCER_DIR / "inputs"
OUTPUTS_DIR = SOCCER_DIR / "outputs"
BACKUP_DIR = PROJECT_ROOT / "backups" / "soccer"

CSV_BACKUP_FILE = DATA_DIR / "player_stats_backup.csv"
JSON_BACKUP_FILE = DATA_DIR / "player_stats_backup.json"

# Ensure directories
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# PROP PARSING — Extract player names from Underdog paste
# =============================================================================

def extract_players_from_slate(slate_text: str) -> Set[str]:
    """
    Extract unique player names from Underdog props paste.
    
    Expected format:
        athlete or team avatar
        Mike Maignan
        MIL @ BFC - 1:45PM CST
        2.5
        Saves
        ...
    """
    players = set()
    lines = slate_text.strip().split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip header markers
        if line.lower() == "athlete or team avatar":
            # Next line is the player name
            if i + 1 < len(lines):
                player_name = lines[i + 1].strip()
                if player_name and not _is_match_line(player_name):
                    players.add(player_name)
            i += 2
            continue
        
        i += 1
    
    return players


def _is_match_line(line: str) -> bool:
    """Check if line is a match info line (e.g., 'MIL @ BFC - 1:45PM CST')."""
    # Match patterns: "ABC @ DEF", "ABC vs DEF", time patterns
    patterns = [
        r'@',  # Away indicator
        r'\d{1,2}:\d{2}\s*(AM|PM|CST|EST|PST)',  # Time
        r'vs\.?',  # vs indicator
    ]
    for pattern in patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def load_latest_slate() -> Optional[str]:
    """Load the most recent slate file."""
    slates = list(INPUTS_DIR.glob("slate_*.txt"))
    if not slates:
        return None
    slates.sort(reverse=True)
    return slates[0].read_text(encoding='utf-8')


# =============================================================================
# API FETCH — Uses API-Football (RapidAPI) with fallback to ESPN
# =============================================================================

def fetch_player_stats(player_names: List[str]) -> Dict[str, Dict]:
    """Fetch player stats from API-Football (primary) or ESPN (fallback)."""
    
    # Try API-Football first (more reliable, but needs API key)
    try:
        from soccer.api_football_integration import fetch_soccer_stats_for_slate, get_api_key
        
        api_key = get_api_key()
        if api_key:
            print("🔌 Using API-Football (RapidAPI)...")
            return fetch_soccer_stats_for_slate(player_names)
        else:
            print("⚠️ No RAPIDAPI_KEY found, trying ESPN...")
    except ImportError:
        print("⚠️ API-Football module not available, trying ESPN...")
    
    # Fallback to ESPN (free but less reliable)
    try:
        from soccer.espn_soccer_integration import fetch_soccer_stats_for_slate
        print("🔌 Using ESPN API (free)...")
        return fetch_soccer_stats_for_slate(player_names)
    except ImportError as e:
        print(f"⚠️ ESPN integration not available: {e}")
        return {}


# =============================================================================
# DATABASE UPDATE — Add/update players in KNOWN_PLAYERS
# =============================================================================

def update_player_database(stats: Dict[str, Dict]) -> int:
    """
    Update KNOWN_PLAYERS with fetched stats.
    
    Returns count of players updated.
    """
    updated = 0
    
    for player_name, data in stats.items():
        if data.get('error') or not data.get('games_played'):
            continue
        
        key = player_name.lower().strip()
        
        # Determine position
        pos = data.get('position', 'unknown')
        pos_map = {
            'F': 'striker', 'FW': 'striker',
            'M': 'midfielder', 'MF': 'midfielder',
            'D': 'defender', 'DF': 'defender',
            'G': 'goalkeeper', 'GK': 'goalkeeper',
        }
        position = pos_map.get(pos.upper(), pos.lower())
        
        # Determine league from team
        league = detect_league(data.get('team', ''))
        
        # Create/update player stats
        player = PlayerStats(
            name=player_name,
            team=data.get('team', 'Unknown'),
            position=position,
            league=league,
            games_played=data.get('games_played', 0),
            shots=data.get('avg_shots', 0.0),
            shots_on_target=data.get('avg_shots_on_target', 0.0),
            goals=data.get('avg_goals', 0.0),
            assists=data.get('avg_assists', 0.0),
            tackles=data.get('avg_tackles', 0.0),
            passes=data.get('avg_passes', 0.0),
            saves=data.get('avg_saves', 0.0),
        )
        
        KNOWN_PLAYERS[key] = player
        updated += 1
        print(f"  ✅ Updated: {player_name} ({player.team})")
    
    return updated


def detect_league(team_name: str) -> str:
    """Detect league from team name."""
    team = team_name.lower()
    
    # Premier League
    pl_teams = ['arsenal', 'aston villa', 'bournemouth', 'brentford', 'brighton',
                'chelsea', 'crystal palace', 'everton', 'fulham', 'ipswich',
                'leicester', 'liverpool', 'manchester city', 'manchester united',
                'newcastle', 'nottingham forest', 'southampton', 'tottenham',
                'west ham', 'wolverhampton', 'wolves']
    if any(t in team for t in pl_teams):
        return 'premier_league'
    
    # Serie A
    seria_teams = ['milan', 'inter', 'juventus', 'napoli', 'roma', 'lazio',
                   'atalanta', 'fiorentina', 'bologna', 'torino', 'monza',
                   'udinese', 'empoli', 'genoa', 'cagliari', 'parma', 
                   'verona', 'lecce', 'como', 'venezia']
    if any(t in team for t in seria_teams):
        return 'serie_a'
    
    # La Liga
    laliga_teams = ['barcelona', 'real madrid', 'atletico', 'sevilla', 'villarreal',
                    'real sociedad', 'betis', 'athletic bilbao', 'valencia',
                    'girona', 'celta', 'osasuna', 'mallorca', 'getafe',
                    'rayo vallecano', 'alaves', 'las palmas', 'valladolid',
                    'espanyol', 'leganes']
    if any(t in team for t in laliga_teams):
        return 'la_liga'
    
    # Bundesliga
    bundes_teams = ['bayern', 'dortmund', 'leverkusen', 'leipzig', 'frankfurt',
                    'stuttgart', 'wolfsburg', 'freiburg', 'hoffenheim', 'mainz',
                    'monchengladbach', 'werder bremen', 'augsburg', 'union berlin',
                    'bochum', 'heidenheim', 'st. pauli', 'holstein kiel']
    if any(t in team for t in bundes_teams):
        return 'bundesliga'
    
    # Ligue 1
    ligue1_teams = ['psg', 'paris saint-germain', 'marseille', 'lyon', 'monaco',
                    'lille', 'lens', 'nice', 'rennes', 'strasbourg', 'toulouse',
                    'nantes', 'montpellier', 'reims', 'brest', 'le havre',
                    'auxerre', 'angers', 'saint-etienne']
    if any(t in team for t in ligue1_teams):
        return 'ligue_1'
    
    # MLS
    mls_teams = ['atlanta', 'austin', 'charlotte', 'chicago fire', 'cincinnati',
                 'colorado rapids', 'columbus', 'dc united', 'houston dynamo',
                 'inter miami', 'la galaxy', 'lafc', 'minnesota', 'montreal',
                 'nashville', 'new england', 'nycfc', 'red bulls', 'orlando',
                 'philadelphia', 'portland', 'real salt lake', 'san jose',
                 'seattle', 'sporting kc', 'st. louis', 'toronto', 'vancouver']
    if any(t in team for t in mls_teams):
        return 'mls'
    
    return 'other'


# =============================================================================
# CSV BACKUP — Export/Import for fallback
# =============================================================================

def export_to_csv(output_path: Path = None) -> str:
    """
    Export KNOWN_PLAYERS to CSV for backup/fallback.
    
    Returns path to CSV file.
    """
    output_path = output_path or CSV_BACKUP_FILE
    
    # Define CSV columns
    fieldnames = [
        'name', 'team', 'position', 'league', 'games_played',
        'shots', 'shots_on_target', 'goals', 'assists', 'xg', 'xa',
        'passes', 'passes_completed', 'key_passes', 'crosses', 'dribbles',
        'tackles', 'interceptions', 'clearances', 'blocks',
        'saves', 'clean_sheet_rate'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for player in KNOWN_PLAYERS.values():
            row = asdict(player)
            writer.writerow(row)
    
    print(f"✅ Exported {len(KNOWN_PLAYERS)} players to {output_path}")
    return str(output_path)


def export_to_json(output_path: Path = None) -> str:
    """Export KNOWN_PLAYERS to JSON for backup."""
    output_path = output_path or JSON_BACKUP_FILE
    
    data = {
        'exported_at': datetime.now().isoformat(),
        'player_count': len(KNOWN_PLAYERS),
        'players': {k: asdict(v) for k, v in KNOWN_PLAYERS.items()}
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Exported {len(KNOWN_PLAYERS)} players to {output_path}")
    return str(output_path)


def import_from_csv(csv_path: Path) -> int:
    """
    Import players from CSV backup.
    
    Returns count of players imported.
    """
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        return 0
    
    imported = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                player = PlayerStats(
                    name=row['name'],
                    team=row['team'],
                    position=row['position'],
                    league=row['league'],
                    games_played=int(row.get('games_played', 0)),
                    shots=float(row.get('shots', 0)),
                    shots_on_target=float(row.get('shots_on_target', 0)),
                    goals=float(row.get('goals', 0)),
                    assists=float(row.get('assists', 0)),
                    xg=float(row.get('xg', 0)),
                    xa=float(row.get('xa', 0)),
                    passes=float(row.get('passes', 0)),
                    passes_completed=float(row.get('passes_completed', 0)),
                    key_passes=float(row.get('key_passes', 0)),
                    crosses=float(row.get('crosses', 0)),
                    dribbles=float(row.get('dribbles', 0)),
                    tackles=float(row.get('tackles', 0)),
                    interceptions=float(row.get('interceptions', 0)),
                    clearances=float(row.get('clearances', 0)),
                    blocks=float(row.get('blocks', 0)),
                    saves=float(row.get('saves', 0)),
                    clean_sheet_rate=float(row.get('clean_sheet_rate', 0)),
                )
                
                key = row['name'].lower().strip()
                KNOWN_PLAYERS[key] = player
                imported += 1
            except Exception as e:
                print(f"  ⚠️ Skipped row: {e}")
    
    print(f"✅ Imported {imported} players from {csv_path}")
    return imported


# =============================================================================
# MAIN WORKFLOW
# =============================================================================

def update_from_slate(slate_text: str = None) -> Dict:
    """
    Main workflow: Extract players from slate → Fetch ESPN → Update DB → Backup CSV
    
    Returns summary dict.
    """
    print("\n" + "=" * 60)
    print("⚽ SOCCER PLAYER STATS UPDATE")
    print("=" * 60)
    
    # Step 1: Load slate
    if slate_text is None:
        slate_text = load_latest_slate()
        if not slate_text:
            print("❌ No slate file found in soccer/inputs/")
            return {'error': 'NO_SLATE'}
    
    # Step 2: Extract player names
    print("\n📋 Extracting players from slate...")
    players = extract_players_from_slate(slate_text)
    
    if not players:
        print("❌ No player names found in slate")
        return {'error': 'NO_PLAYERS'}
    
    print(f"   Found {len(players)} players: {', '.join(list(players)[:5])}{'...' if len(players) > 5 else ''}")
    
    # Step 3: Check which players need update
    existing = sum(1 for p in players if p.lower().strip() in KNOWN_PLAYERS)
    new = len(players) - existing
    print(f"   {existing} already in database, {new} new players")
    
    # Step 4: Fetch from API
    print("\n🌐 Fetching stats from API...")
    stats = fetch_player_stats(list(players))
    
    if not stats:
        print("⚠️ ESPN API returned no results")
    
    # Step 5: Update database
    if stats:
        print("\n📊 Updating player database...")
        updated = update_player_database(stats)
        print(f"   Updated {updated} players")
    else:
        updated = 0
    
    # Step 6: Export to CSV backup
    print("\n💾 Creating CSV backup...")
    csv_path = export_to_csv()
    
    # Step 7: Also export JSON backup
    json_path = export_to_json()
    
    # Summary
    summary = {
        'players_in_slate': len(players),
        'already_in_db': existing,
        'new_players': new,
        'updated_from_api': updated,
        'csv_backup': csv_path,
        'json_backup': json_path,
        'db_total': len(KNOWN_PLAYERS)
    }
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"   Players in slate: {summary['players_in_slate']}")
    print(f"   Updated from API: {summary['updated_from_api']}")
    print(f"   Total in DB:      {summary['db_total']}")
    print(f"   CSV backup:       {summary['csv_backup']}")
    
    return summary


def update_specific_players(player_names: List[str]) -> Dict:
    """Update specific players by name."""
    print("\n" + "=" * 60)
    print("⚽ UPDATING SPECIFIC PLAYERS")
    print("=" * 60)
    
    print(f"\n🌐 Fetching stats for {len(player_names)} players...")
    stats = fetch_player_stats(player_names)
    
    if not stats:
        print("❌ ESPN API returned no results")
        return {'error': 'NO_RESULTS'}
    
    print("\n📊 Updating player database...")
    updated = update_player_database(stats)
    
    print("\n💾 Creating CSV backup...")
    csv_path = export_to_csv()
    
    return {
        'requested': len(player_names),
        'updated': updated,
        'csv_backup': csv_path
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Update soccer player stats from props/API")
    parser.add_argument('--slate', action='store_true', help='Update from latest slate file')
    parser.add_argument('--players', type=str, help='Comma-separated player names')
    parser.add_argument('--export', action='store_true', help='Export database to CSV')
    parser.add_argument('--import-csv', type=str, dest='import_csv', help='Import from CSV file')
    parser.add_argument('--status', action='store_true', help='Show database status')
    
    args = parser.parse_args()
    
    if args.status:
        print(f"\n⚽ SOCCER PLAYER DATABASE STATUS")
        print("=" * 60)
        print(f"Total players: {len(KNOWN_PLAYERS)}")
        
        # Count by league
        by_league = {}
        for p in KNOWN_PLAYERS.values():
            league = p.league
            by_league[league] = by_league.get(league, 0) + 1
        
        print("\nBy league:")
        for league, count in sorted(by_league.items(), key=lambda x: -x[1]):
            print(f"  {league}: {count}")
        
        # Check backup files
        print("\nBackup files:")
        if CSV_BACKUP_FILE.exists():
            print(f"  ✅ CSV: {CSV_BACKUP_FILE} ({CSV_BACKUP_FILE.stat().st_size:,} bytes)")
        else:
            print(f"  ❌ CSV: Not found")
        
        if JSON_BACKUP_FILE.exists():
            print(f"  ✅ JSON: {JSON_BACKUP_FILE} ({JSON_BACKUP_FILE.stat().st_size:,} bytes)")
        else:
            print(f"  ❌ JSON: Not found")
    
    elif args.slate:
        update_from_slate()
    
    elif args.players:
        names = [n.strip() for n in args.players.split(',') if n.strip()]
        update_specific_players(names)
    
    elif args.export:
        export_to_csv()
        export_to_json()
    
    elif args.import_csv:
        import_from_csv(Path(args.import_csv))
        export_to_csv()  # Re-export as backup
    
    else:
        parser.print_help()
        print("\n💡 Examples:")
        print("   python soccer/data/update_from_props.py --slate")
        print("   python soccer/data/update_from_props.py --players 'Pulisic, Leao, Maignan'")
        print("   python soccer/data/update_from_props.py --export")
        print("   python soccer/data/update_from_props.py --status")


if __name__ == "__main__":
    main()
