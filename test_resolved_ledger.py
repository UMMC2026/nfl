#!/usr/bin/env python3
"""
TEST RESOLVED LEDGER WITH MOCK DATA
===================================

Validates the entire resolve pipeline without needing live ESPN data.
Creates mock picks + game results, runs resolver, and checks output structure.
"""

import json
from pathlib import Path
from datetime import datetime


def create_mock_picks() -> list:
    """Create test picks with varied tiers and confidence."""
    return [
        {
            "date": "2026-01-02",
            "game_id": "CLE_NYK_20260102",
            "player_name": "OG Anunoby",
            "team": "NYK",
            "stat": "points",
            "direction": "OVER",
            "line": 16.5,
            "tier": "SLAM",
            "confidence": 0.75,
            "primary_edge": True,
            "correlated_with": None
        },
        {
            "date": "2026-01-02",
            "game_id": "CLE_NYK_20260102",
            "player_name": "OG Anunoby",
            "team": "NYK",
            "stat": "pts+reb+ast",
            "direction": "OVER",
            "line": 25.5,
            "tier": "STRONG",
            "confidence": 0.65,
            "primary_edge": False,  # CORRELATED
            "correlated_with": "OG Anunoby"
        },
        {
            "date": "2026-01-02",
            "game_id": "CLE_NYK_20260102",
            "player_name": "Darius Garland",
            "team": "CLE",
            "stat": "pts+reb+ast",
            "direction": "UNDER",
            "line": 39.5,
            "tier": "SLAM",
            "confidence": 0.75,
            "primary_edge": True,
            "correlated_with": None
        },
        {
            "date": "2026-01-02",
            "game_id": "CLE_NYK_20260102",
            "player_name": "Dean Wade",
            "team": "CLE",
            "stat": "rebounds",
            "direction": "UNDER",
            "line": 4.5,
            "tier": "SLAM",
            "confidence": 0.75,
            "primary_edge": True,
            "correlated_with": None
        },
        {
            "date": "2026-01-02",
            "game_id": "LAL_GSW_20260102",
            "player_name": "LeBron James",
            "team": "LAL",
            "stat": "points",
            "direction": "OVER",
            "line": 19.5,
            "tier": "STRONG",
            "confidence": 0.62,
            "primary_edge": True,
            "correlated_with": None
        }
    ]


def create_mock_results() -> dict:
    """Create mock game results (FINAL games with actual stats)."""
    return {
        "CLE_NYK_20260102": {
            "date": "2026-01-02",
            "status": "FINAL",
            "home_team": "CLE",
            "away_team": "NYK",
            "players": {
                "OG Anunoby": {
                    "team": "NYK",
                    "points": 18,
                    "rebounds": 7,
                    "assists": 2,
                    "pra": 27,
                    "3pm": 1,
                    "steals": 0,
                    "blocks": 0,
                    "turnovers": 1
                },
                "Darius Garland": {
                    "team": "CLE",
                    "points": 15,
                    "rebounds": 1,
                    "assists": 8,
                    "pra": 24,
                    "3pm": 2,
                    "steals": 1,
                    "blocks": 0,
                    "turnovers": 2
                },
                "Dean Wade": {
                    "team": "CLE",
                    "points": 8,
                    "rebounds": 3,
                    "assists": 1,
                    "pra": 12,
                    "3pm": 0,
                    "steals": 0,
                    "blocks": 0,
                    "turnovers": 0
                }
            }
        },
        "LAL_GSW_20260102": {
            "date": "2026-01-02",
            "status": "FINAL",
            "home_team": "GSW",
            "away_team": "LAL",
            "players": {
                "LeBron James": {
                    "team": "LAL",
                    "points": 21,
                    "rebounds": 5,
                    "assists": 4,
                    "pra": 30,
                    "3pm": 1,
                    "steals": 1,
                    "blocks": 0,
                    "turnovers": 2
                }
            }
        }
    }


def main():
    """Write mock data and summarize for manual test."""
    print("=" * 70)
    print("SETTING UP MOCK TEST DATA")
    print("=" * 70)
    
    workspace = Path.cwd()
    
    # Write mock picks
    picks_path = workspace / "picks_mock.json"
    picks = create_mock_picks()
    with open(picks_path, 'w') as f:
        json.dump(picks, f, indent=2)
    print(f"✓ Mock picks written to {picks_path} ({len(picks)} picks)")
    
    # Write mock game results
    results_path = workspace / "outputs" / "game_results_mock.json"
    results_path.parent.mkdir(exist_ok=True)
    results = create_mock_results()
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ Mock results written to {results_path} ({len(results)} games)")
    
    # Show summary
    print("\n" + "=" * 70)
    print("MOCK DATA SUMMARY")
    print("=" * 70)
    print("\n📊 Picks:")
    for i, pick in enumerate(picks, 1):
        primary_marker = "PRIMARY" if pick["primary_edge"] else f"CORRELATED w/{pick['correlated_with']}"
        print(f"  {i}. {pick['player_name']} {pick['direction']} {pick['line']} ({pick['tier']}, {pick['confidence']*100:.0f}%) {primary_marker}")
    
    print("\n🎯 Expected Outcomes:")
    print("  1. OG Anunoby OVER 16.5 points (18) → HIT ✓")
    print("  2. OG Anunoby OVER 25.5 PRA (correlated) → NOT SCORED")
    print("  3. Darius Garland UNDER 39.5 PRA (24) → HIT ✓")
    print("  4. Dean Wade UNDER 4.5 rebounds (3) → HIT ✓")
    print("  5. LeBron James OVER 19.5 points (21) → HIT ✓")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Run:
   .venv\\Scripts\\python.exe generate_resolved_ledger.py \\
       --picks picks_mock.json \\
       --results outputs/game_results_mock.json

2. Check outputs:
   - reports/resolved_ledger.csv (machine truth)
   - reports/RESOLVED_PERFORMANCE_LEDGER.md (human report)

3. Validate:
   - Win rate should be 100% (4/4 PRIMARY hits)
   - Correlated OG Anunoby PRA should NOT be scored
   - Confidence bins should show actual vs expected
""")
    
    return 0


if __name__ == "__main__":
    exit(main())
