"""
Expand Tennis Data Coverage Script

Downloads additional years and tournament levels from Jeff Sackmann's GitHub:
- ATP/WTA main tour: 2023, 2024, 2025
- ATP/WTA Challengers
- ATP/WTA Qualifying rounds
- Futures (ITF) data

Usage:
    python tennis/scripts/expand_tennis_data.py --all
    python tennis/scripts/expand_tennis_data.py --years 2023 2024 2025
    python tennis/scripts/expand_tennis_data.py --challengers
    python tennis/scripts/expand_tennis_data.py --check-coverage

SOP v2.1 Compliant - Data Expansion Layer
"""

import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
import sqlite3
import csv
import json

# ============================================================================
# PATHS
# ============================================================================

TENNIS_DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = TENNIS_DATA_DIR / "raw"
BACKUP_DIR = TENNIS_DATA_DIR / "backups"
DB_PATH = TENNIS_DATA_DIR / "tennis_stats.db"

# Ensure directories exist
RAW_DIR.mkdir(exist_ok=True, parents=True)
BACKUP_DIR.mkdir(exist_ok=True, parents=True)

# ============================================================================
# DATA SOURCES
# ============================================================================

SACKMANN_BASE = "https://raw.githubusercontent.com/JeffSackmann"

# Main Tour Data
ATP_REPO = f"{SACKMANN_BASE}/tennis_atp/master"
WTA_REPO = f"{SACKMANN_BASE}/tennis_wta/master"

# Challenger/Qualifier Data (separate repos)
ATP_QUAL_REPO = f"{SACKMANN_BASE}/tennis_atp/master"  # qual matches in same file
WTA_QUAL_REPO = f"{SACKMANN_BASE}/tennis_wta/master"  # qual matches in same file

# Available years (Sackmann has data from 1968 for ATP, 1968 for WTA)
RECENT_YEARS = [2023, 2024, 2025]
HISTORICAL_YEARS = list(range(2018, 2023))  # 2018-2022

# Tournament level codes
LEVEL_MAP = {
    'G': 'Grand Slam',
    'M': 'Masters 1000',
    'A': 'ATP 500',
    'B': 'ATP 250',
    'F': 'Tour Finals',
    'D': 'Davis Cup/Billie Jean King Cup',
    'C': 'Challenger',
    'S': 'ITF/Satellite',
    'O': 'Olympics'
}


# ============================================================================
# DOWNLOAD FUNCTIONS
# ============================================================================

def download_file(url: str, output_path: Path) -> bool:
    """Download a file from URL to local path."""
    try:
        print(f"  Downloading: {url.split('/')[-1]}...")
        urllib.request.urlretrieve(url, output_path)
        
        if output_path.exists() and output_path.stat().st_size > 0:
            lines = len(output_path.read_text(encoding='utf-8', errors='replace').splitlines())
            size_kb = output_path.stat().st_size / 1024
            print(f"    ✓ {lines:,} rows ({size_kb:,.0f} KB)")
            return True
        return False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"    ⚠ File not found (normal for future years)")
        else:
            print(f"    ✗ HTTP Error: {e.code}")
        return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def download_main_tour(years: list[int], tours: list[str] = ['atp', 'wta']) -> dict:
    """Download main tour match files for specified years."""
    results = {'downloaded': [], 'failed': [], 'skipped': []}
    
    print("\n" + "="*60)
    print("DOWNLOADING MAIN TOUR DATA")
    print("="*60)
    
    for tour in tours:
        repo = ATP_REPO if tour == 'atp' else WTA_REPO
        
        for year in years:
            filename = f"{tour}_matches_{year}.csv"
            output_path = RAW_DIR / filename
            url = f"{repo}/{filename}"
            
            # Skip if already exists and recent
            if output_path.exists():
                mtime = datetime.fromtimestamp(output_path.stat().st_mtime)
                age_days = (datetime.now() - mtime).days
                if age_days < 1:
                    print(f"\n[{tour.upper()} {year}] Skipping (downloaded today)")
                    results['skipped'].append(filename)
                    continue
            
            print(f"\n[{tour.upper()} {year}]")
            if download_file(url, output_path):
                results['downloaded'].append(filename)
            else:
                results['failed'].append(filename)
    
    return results


def download_challengers(years: list[int] = None) -> dict:
    """Download Challenger tour data (ATP Challengers, ITF tournaments)."""
    if years is None:
        years = RECENT_YEARS
        
    results = {'downloaded': [], 'failed': [], 'skipped': []}
    
    print("\n" + "="*60)
    print("DOWNLOADING CHALLENGER DATA")
    print("="*60)
    
    # ATP Challengers
    for year in years:
        filename = f"atp_matches_qual_chall_{year}.csv"
        output_path = RAW_DIR / filename
        url = f"{ATP_REPO}/{filename}"
        
        print(f"\n[ATP CHALLENGERS {year}]")
        if download_file(url, output_path):
            results['downloaded'].append(filename)
        else:
            results['failed'].append(filename)
    
    # WTA Challengers/ITF
    for year in years:
        for suffix in ['qual', 'itf']:
            filename = f"wta_matches_{suffix}_{year}.csv"
            output_path = RAW_DIR / filename
            url = f"{WTA_REPO}/{filename}"
            
            print(f"\n[WTA {suffix.upper()} {year}]")
            if download_file(url, output_path):
                results['downloaded'].append(filename)
            else:
                results['failed'].append(filename)
    
    return results


def download_futures(years: list[int] = None) -> dict:
    """Download ITF Futures data if available."""
    if years is None:
        years = RECENT_YEARS
    
    results = {'downloaded': [], 'failed': []}
    
    print("\n" + "="*60)
    print("DOWNLOADING FUTURES/ITF DATA")
    print("="*60)
    
    # Check for ITF Men's data
    for year in years:
        filename = f"atp_matches_futures_{year}.csv"
        output_path = RAW_DIR / filename
        url = f"{ATP_REPO}/{filename}"
        
        print(f"\n[ITF Men {year}]")
        if download_file(url, output_path):
            results['downloaded'].append(filename)
        else:
            results['failed'].append(filename)
    
    return results


# ============================================================================
# IMPORT TO DATABASE
# ============================================================================

def import_csv_to_db(csv_path: Path, conn: sqlite3.Connection) -> int:
    """Import a Sackmann CSV file into the database."""
    
    # Check if file exists
    if not csv_path.exists():
        return 0
    
    cur = conn.cursor()
    imported = 0
    
    # Column mapping from Sackmann CSV to our schema
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Skip rows without match stats
                if not row.get('w_ace') or row.get('w_ace') == '':
                    continue
                
                # Extract data
                winner_name = row.get('winner_name', '')
                loser_name = row.get('loser_name', '')
                surface = row.get('surface', '')
                match_date = row.get('tourney_date', '')
                tourney_name = row.get('tourney_name', '')
                tourney_level = LEVEL_MAP.get(row.get('tourney_level', ''), 'Unknown')
                round_name = row.get('round', '')
                score = row.get('score', '')
                
                # Ensure players exist
                for name in [winner_name, loser_name]:
                    if name:
                        cur.execute('''
                            INSERT OR IGNORE INTO players (player_name) 
                            VALUES (?)
                        ''', (name,))
                
                # Get player IDs
                cur.execute('SELECT player_id FROM players WHERE player_name = ?', (winner_name,))
                winner_id = cur.fetchone()
                winner_id = winner_id[0] if winner_id else None
                
                cur.execute('SELECT player_id FROM players WHERE player_name = ?', (loser_name,))
                loser_id = cur.fetchone()
                loser_id = loser_id[0] if loser_id else None
                
                # Check if match already exists
                cur.execute('''
                    SELECT match_id FROM matches 
                    WHERE tournament_name = ? AND match_date = ? 
                    AND player1_id = ? AND player2_id = ?
                ''', (tourney_name, match_date, winner_id, loser_id))
                
                if cur.fetchone():
                    continue  # Skip duplicate
                
                # Insert match
                cur.execute('''
                    INSERT INTO matches (
                        tournament_name, tournament_level, surface, match_date, 
                        round, player1_id, player2_id, winner_id, score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (tourney_name, tourney_level, surface, match_date,
                      round_name, winner_id, loser_id, winner_id, score))
                
                match_id = cur.lastrowid
                
                # Helper function for safe int conversion
                def safe_int(val, default=0):
                    try:
                        return int(float(val)) if val else default
                    except:
                        return default
                
                # Insert match stats for winner
                cur.execute('''
                    INSERT INTO match_stats (
                        match_id, player_id, aces, double_faults,
                        first_serves_in, first_serves_total,
                        first_serve_points_won, first_serve_points_total,
                        second_serve_points_won, second_serve_points_total,
                        break_points_saved, break_points_faced,
                        service_games_won, service_games_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id, winner_id,
                    safe_int(row.get('w_ace')),
                    safe_int(row.get('w_df')),
                    safe_int(row.get('w_1stIn')),
                    safe_int(row.get('w_svpt')),
                    safe_int(row.get('w_1stWon')),
                    safe_int(row.get('w_1stIn')),  # First serve attempts
                    safe_int(row.get('w_2ndWon')),
                    safe_int(row.get('w_svpt', 0)) - safe_int(row.get('w_1stIn', 0)),
                    safe_int(row.get('w_bpSaved')),
                    safe_int(row.get('w_bpFaced')),
                    safe_int(row.get('w_SvGms')),
                    safe_int(row.get('w_SvGms'))
                ))
                
                # Insert match stats for loser
                cur.execute('''
                    INSERT INTO match_stats (
                        match_id, player_id, aces, double_faults,
                        first_serves_in, first_serves_total,
                        first_serve_points_won, first_serve_points_total,
                        second_serve_points_won, second_serve_points_total,
                        break_points_saved, break_points_faced,
                        service_games_won, service_games_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id, loser_id,
                    safe_int(row.get('l_ace')),
                    safe_int(row.get('l_df')),
                    safe_int(row.get('l_1stIn')),
                    safe_int(row.get('l_svpt')),
                    safe_int(row.get('l_1stWon')),
                    safe_int(row.get('l_1stIn')),
                    safe_int(row.get('l_2ndWon')),
                    safe_int(row.get('l_svpt', 0)) - safe_int(row.get('l_1stIn', 0)),
                    safe_int(row.get('l_bpSaved')),
                    safe_int(row.get('l_bpFaced')),
                    safe_int(row.get('l_SvGms')),
                    safe_int(row.get('l_SvGms'))
                ))
                
                imported += 1
                
            except Exception as e:
                continue  # Skip problematic rows
    
    conn.commit()
    return imported


def reimport_all_data():
    """Re-import all CSV files in raw directory to database."""
    
    print("\n" + "="*60)
    print("IMPORTING ALL CSV FILES TO DATABASE")
    print("="*60)
    
    if not DB_PATH.exists():
        print("Database not found! Run tennis setup first.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    total_imported = 0
    
    for csv_file in csv_files:
        print(f"\n[{csv_file.name}]")
        imported = import_csv_to_db(csv_file, conn)
        print(f"  → Imported {imported:,} matches")
        total_imported += imported
    
    conn.close()
    
    print("\n" + "="*60)
    print(f"TOTAL: {total_imported:,} new matches imported")
    print("="*60)


# ============================================================================
# COVERAGE CHECK
# ============================================================================

def check_coverage(players: list[str] = None):
    """Check database coverage for specific players or general stats."""
    
    print("\n" + "="*60)
    print("DATABASE COVERAGE CHECK")
    print("="*60)
    
    if not DB_PATH.exists():
        print("Database not found!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # General stats
    cur.execute('SELECT COUNT(*) FROM players')
    print(f"\nTotal Players: {cur.fetchone()[0]:,}")
    
    cur.execute('SELECT COUNT(*) FROM matches')
    print(f"Total Matches: {cur.fetchone()[0]:,}")
    
    cur.execute('SELECT MIN(match_date), MAX(match_date) FROM matches')
    dates = cur.fetchone()
    print(f"Date Range: {dates[0]} to {dates[1]}")
    
    # By tournament level
    cur.execute('''
        SELECT tournament_level, COUNT(*) 
        FROM matches 
        GROUP BY tournament_level 
        ORDER BY COUNT(*) DESC
    ''')
    print("\nMatches by Tournament Level:")
    for row in cur.fetchall():
        level = row[0] if row[0] else "Unknown"
        print(f"  {level:20}: {row[1]:,}")
    
    # By surface
    cur.execute('''
        SELECT surface, COUNT(*) 
        FROM matches 
        GROUP BY surface
    ''')
    print("\nMatches by Surface:")
    for row in cur.fetchall():
        print(f"  {row[0]:10}: {row[1]:,}")
    
    # Check specific players
    if players:
        print("\n" + "-"*60)
        print("PLAYER LOOKUP:")
        print("-"*60)
        
        for name in players:
            cur.execute('''
                SELECT p.player_name, COUNT(ms.stat_id)
                FROM players p
                LEFT JOIN match_stats ms ON p.player_id = ms.player_id
                WHERE p.player_name LIKE ?
                GROUP BY p.player_id
            ''', (f'%{name}%',))
            
            results = cur.fetchall()
            if results:
                for r in results:
                    status = "✓" if r[1] > 0 else "⚠ (no stats)"
                    print(f"  {status} {r[0]}: {r[1]} match records")
            else:
                print(f"  ✗ {name}: NOT FOUND")
    
    conn.close()


def list_available_files():
    """List all downloaded CSV files."""
    
    print("\n" + "="*60)
    print("AVAILABLE DATA FILES")
    print("="*60)
    
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    
    if not csv_files:
        print("\nNo CSV files found in raw directory.")
        print(f"Directory: {RAW_DIR}")
        return
    
    print(f"\nFound {len(csv_files)} files in {RAW_DIR}:\n")
    
    total_size = 0
    total_rows = 0
    
    for f in csv_files:
        size = f.stat().st_size / 1024
        try:
            rows = len(f.read_text(encoding='utf-8', errors='replace').splitlines()) - 1
        except:
            rows = 0
        
        total_size += size
        total_rows += rows
        
        print(f"  {f.name:40} | {rows:>7,} rows | {size:>8,.0f} KB")
    
    print(f"\n  {'TOTAL':40} | {total_rows:>7,} rows | {total_size:>8,.0f} KB")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Expand Tennis Data Coverage")
    parser.add_argument('--all', action='store_true', help='Download all available data')
    parser.add_argument('--years', nargs='+', type=int, help='Specific years to download')
    parser.add_argument('--challengers', action='store_true', help='Download challenger data')
    parser.add_argument('--futures', action='store_true', help='Download futures/ITF data')
    parser.add_argument('--reimport', action='store_true', help='Re-import all CSVs to database')
    parser.add_argument('--check-coverage', action='store_true', help='Check database coverage')
    parser.add_argument('--list-files', action='store_true', help='List downloaded files')
    parser.add_argument('--players', nargs='+', help='Check specific players')
    
    args = parser.parse_args()
    
    if args.list_files:
        list_available_files()
        return
    
    if args.check_coverage or args.players:
        check_coverage(args.players)
        return
    
    # Download data
    years = args.years if args.years else RECENT_YEARS
    
    if args.all:
        # Download everything
        download_main_tour(years + HISTORICAL_YEARS)
        download_challengers(years)
        download_futures(years)
    else:
        if args.years or not (args.challengers or args.futures):
            download_main_tour(years)
        
        if args.challengers:
            download_challengers(years)
        
        if args.futures:
            download_futures(years)
    
    # Re-import to database
    if args.reimport or args.all:
        reimport_all_data()
    
    # Show final coverage
    check_coverage()


if __name__ == "__main__":
    main()
