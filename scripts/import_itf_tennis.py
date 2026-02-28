"""Quick import WTA ITF data to tennis database."""
import csv
import sqlite3
from pathlib import Path

TENNIS_DIR = Path(__file__).parent.parent / "tennis"
DB_PATH = TENNIS_DIR / "data" / "tennis_stats.db"
CSV_PATH = TENNIS_DIR / "data" / "raw" / "wta_matches_qual_itf_2024.csv"

def import_itf_data():
    """Import ITF matches to database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get existing player IDs
    cur.execute("SELECT player_name, player_id FROM players")
    players = {row[0]: row[1] for row in cur.fetchall()}
    next_player_id = max(players.values()) + 1 if players else 1
    
    # Get existing match IDs
    cur.execute("SELECT MAX(match_id) FROM matches")
    next_match_id = (cur.fetchone()[0] or 0) + 1
    
    imported = 0
    new_players = []
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            winner = row.get('winner_name', '')
            loser = row.get('loser_name', '')
            
            # Add new players
            for player in [winner, loser]:
                if player and player not in players:
                    players[player] = next_player_id
                    new_players.append((next_player_id, player))
                    next_player_id += 1
            
            if not winner or not loser:
                continue
            
            # Insert match
            try:
                surface = row.get('surface', 'Hard')
                tourney_date = row.get('tourney_date', '')
                score = row.get('score', '')
                
                cur.execute("""
                    INSERT OR IGNORE INTO matches 
                    (match_id, tourney_name, surface, tourney_date, winner_id, loser_id, score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    next_match_id,
                    row.get('tourney_name', 'ITF'),
                    surface,
                    tourney_date,
                    players.get(winner),
                    players.get(loser),
                    score
                ))
                
                # Insert match stats for winner
                if row.get('w_ace'):
                    cur.execute("""
                        INSERT OR IGNORE INTO match_stats 
                        (match_id, player_id, aces, double_faults, first_serve_pct, first_serve_won_pct, break_points_faced, break_points_saved)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_match_id,
                        players.get(winner),
                        int(row.get('w_ace', 0) or 0),
                        int(row.get('w_df', 0) or 0),
                        float(row.get('w_1stIn', 0) or 0) / max(1, float(row.get('w_svpt', 1) or 1)),
                        float(row.get('w_1stWon', 0) or 0) / max(1, float(row.get('w_1stIn', 1) or 1)),
                        int(row.get('w_bpFaced', 0) or 0),
                        int(row.get('w_bpSaved', 0) or 0),
                    ))
                
                # Insert match stats for loser
                if row.get('l_ace'):
                    cur.execute("""
                        INSERT OR IGNORE INTO match_stats 
                        (match_id, player_id, aces, double_faults, first_serve_pct, first_serve_won_pct, break_points_faced, break_points_saved)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_match_id,
                        players.get(loser),
                        int(row.get('l_ace', 0) or 0),
                        int(row.get('l_df', 0) or 0),
                        float(row.get('l_1stIn', 0) or 0) / max(1, float(row.get('l_svpt', 1) or 1)),
                        float(row.get('l_1stWon', 0) or 0) / max(1, float(row.get('l_1stIn', 1) or 1)),
                        int(row.get('l_bpFaced', 0) or 0),
                        int(row.get('l_bpSaved', 0) or 0),
                    ))
                
                next_match_id += 1
                imported += 1
                
            except Exception as e:
                continue
    
    # Insert new players
    for player_id, player_name in new_players:
        cur.execute(
            "INSERT OR IGNORE INTO players (player_id, player_name) VALUES (?, ?)",
            (player_id, player_name)
        )
    
    conn.commit()
    conn.close()
    
    print(f"Imported {imported} ITF matches")
    print(f"Added {len(new_players)} new players")
    print(f"Database: {DB_PATH}")

if __name__ == "__main__":
    import_itf_data()
