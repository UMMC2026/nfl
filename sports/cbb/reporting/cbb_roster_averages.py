"""
CBB Roster Averages Report Generator (NBA-style)
Exports a human-readable text report of player averages for L5/L10/Season, similar to NBA pipeline.
"""
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def generate_cbb_roster_averages_report(date: str, csv_path: str, out_path: str):
    players = []
    with open(csv_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            players.append(row)
    # Group by team
    teams = defaultdict(list)
    for p in players:
        teams[p["team"]].append(p)
    # Build report
    lines = []
    lines.append(f"Roster Averages Report (L5 / L10 / Season)")
    lines.append(f"Date: {date}")
    lines.append(f"Teams: {', '.join(sorted(teams.keys()))}")
    lines.append("")
    for team, plist in teams.items():
        lines.append(f"{team} (players: {len(plist)})")
        lines.append("=" * 80)
        lines.append(f"{'PLAYER':20} {'MIN':>5} {'PTS':>5} {'REB':>5} {'AST':>5} {'3PM':>5} {'STL':>5} {'BLK':>5}")
        lines.append("-" * 80)
        for p in plist:
            lines.append(f"{p['player_name'][:20]:20} {float(p.get('minutes',0)):5.1f} {float(p.get('points',0)):5.1f} {float(p.get('rebounds',0)):5.1f} {float(p.get('assists',0)):5.1f} {float(p.get('fg3m',0)):5.1f} {float(p.get('steals',0)):5.1f} {float(p.get('blocks',0)):5.1f}")
        lines.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"[CBB] Roster averages report written to {out_path}")
