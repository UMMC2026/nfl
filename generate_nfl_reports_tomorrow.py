import json
from datetime import datetime, timedelta
from pathlib import Path
from generate_game_reports import generate_nfl_game_report

# Placeholder: Replace with actual parsed props and matchups for tomorrow's games
TOMORROW = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

# Example structure for one game; expand for all games
GAMES_TOMORROW = [
    {
        "away": "BUF",
        "home": "JAX",
        "date": TOMORROW,
        "kickoff": "12:00PM CST",
        "venue": "TIAA Bank Field",
        "window": "Early",
        "weather": "Clear",
        "intensity": "High",
        # Advanced stats (populate with real data or placeholders)
        "drive_chart": "BUF: 8 drives, 3 TDs, 2 FGs; JAX: 9 drives, 2 TDs, 3 FGs",
        "epa_per_play": "BUF: 0.18, JAX: 0.12",
        "success_rates": "BUF: 48%, JAX: 45%",
        "on_off_splits": "BUF Offense w/ Allen: +7.2 PPG; w/o: -5.1 PPG",
        "team_synergy": "BUF: Pass-heavy, JAX: Balanced",
        "redzone_stats": "BUF: 62% TD rate, JAX: 54% TD rate",
        "clutch_stats": "BUF: 4th Q +EPA, JAX: -EPA",
        "personnel_groupings": "BUF: 11 personnel 72%, JAX: 12 personnel 38%",
        "expected_pace": "Fast",
        "expected_play_volume": "BUF: 68, JAX: 65",
        "tempo": "Up-tempo",
        "expected_drives": "BUF: 11, JAX: 10",
        "injury_report": "Allen (Q) - limited, Etienne (P) - probable",
        "market_edges": "BUF RBs undervalued, JAX WRs chalk",
        "chalk_contrarian": "BUF pass game chalk, JAX TE contrarian",
        "approved_bets": "Rush + Rec TDs | 0.5 | Higher | 78% | SLAM | Cook red zone usage\nRush Yards | 78.5 | Lower | 61% | PLAYABLE | JAX run D strong",
        "blocked_bets": "Receiving Yards | Injury risk | Shakir questionable",
    },
    # Add other games here in same format
]

reports_dir = Path("reports/games/NFL")
reports_dir.mkdir(parents=True, exist_ok=True)

for game in GAMES_TOMORROW:
    filename = f"GAME_REPORT_NFL_{game['away']}_AT_{game['home']}_{game['date']}.md"
    filepath = reports_dir / filename
    content = generate_nfl_game_report(game)
    filepath.write_text(content, encoding='utf-8')
    print(f"✅ {filename} generated.")

print("All NFL reports for tomorrow generated!")
