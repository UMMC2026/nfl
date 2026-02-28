"""Quick check to see which players are in DB and their match_stats count."""
import sqlite3, os

db = 'tennis/data/tennis_stats.db'
if not os.path.exists(db):
    print('DB not found')
    exit()

conn = sqlite3.connect(db)
c = conn.cursor()

# Check for "No match data" players
print("=== No Match Data Players ===")
missing = ['Ivashka', 'Kinsey Crawford', 'Chukwumelije Clarke', 'Moise Kouame', 'Alexia']
for name in missing:
    c.execute('SELECT player_id, player_name FROM players WHERE player_name LIKE ?', (f'%{name}%',))
    rows = c.fetchall()
    if rows:
        for r in rows:
            c.execute('SELECT COUNT(*) FROM match_stats WHERE player_id=?', (r[0],))
            n = c.fetchone()[0]
            print(f"  FOUND: {r[1]} (id={r[0]}, match_stats={n})")
    else:
        print(f"  NOT IN DB: {name}")

# Check truncated name matching
print("\n=== Truncated Name Matching ===")
truncated = ['Tsitsipas', 'Lehecka', 'Tiafoe', 'Pegula', 'Bonzi', 'Svitolina', 'Kecmanovic', 
             'Berrettini', 'Fonseca', 'Etcheverry', 'Walton', 'Nagal', 'Landaluce', 'Dzumhur']
for name in truncated:
    c.execute('SELECT player_id, player_name FROM players WHERE player_name LIKE ?', (f'%{name}%',))
    rows = c.fetchall()
    names_found = [r[1] for r in rows]
    print(f"  {name}: {names_found if names_found else 'NOT FOUND'}")

conn.close()
