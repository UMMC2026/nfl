"""Check tennis database for missing players."""
import sqlite3

conn = sqlite3.connect('tennis/data/tennis_stats.db')
cur = conn.cursor()

targets = ['Wang', 'Matsuda', 'Kuramochi']
for t in targets:
    cur.execute("SELECT player_name FROM players WHERE player_name LIKE ?", (f'%{t}%',))
    results = [r[0] for r in cur.fetchall()]
    print(f"{t}: {results}")

# Count matches for specific players
print("\nMatch counts:")
for name in ['Misaki Matsuda', 'Miho Kuramochi', 'Xin Yu Wang', 'Xinyu Wang']:
    cur.execute("""
        SELECT COUNT(*) FROM match_stats ms
        JOIN players p ON ms.player_id = p.player_id
        WHERE p.player_name = ?
    """, (name,))
    count = cur.fetchone()[0]
    print(f"  {name}: {count} match records")

conn.close()
