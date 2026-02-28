"""
run_parlay_analysis.py

Loads structured NBA slate JSON and runs SmartParlayBuilder to generate a safe parlay.
"""
import json
from types import SimpleNamespace
from integrations.parlay_constructor import SmartParlayBuilder

SLATE_FILE = "nba_slate_structured.json"

# Load structured props
with open(SLATE_FILE, "r", encoding="utf-8") as f:
    players = json.load(f)

# Flatten all props into candidate legs
candidate_legs = []
for player in players:
    name = player["name"]
    for prop in player["props"]:
        # Map prop type to stat code
        stat_map = {
            "points": "PTS",
            "rebounds": "REB",
            "assists": "AST",
            "pra": "PRA",
            "threes": "3PM",
            "points_rebounds": "PTS+REB",
        }
        stat = stat_map.get(prop["type"], prop["type"].upper())
        # Add both higher/lower as candidate legs if available
        if prop.get("higher") is not None:
            candidate_legs.append(SimpleNamespace(
                player=name,
                stat=stat,
                line=prop["line"],
                direction="OVER",
                player_role="STARTER",  # Placeholder, can be improved
                minutes_prob=0.95,      # Placeholder
                stat_variance=1.0,      # Placeholder
                game_script_risk="LOW",# Placeholder
                edge=0.70,              # Placeholder
                game_id="",            # Placeholder
            ))
        if prop.get("lower") is not None:
            candidate_legs.append(SimpleNamespace(
                player=name,
                stat=stat,
                line=prop["line"],
                direction="UNDER",
                player_role="STARTER",
                minutes_prob=0.95,
                stat_variance=1.0,
                game_script_risk="LOW",
                edge=0.70,
                game_id="",
            ))

builder = SmartParlayBuilder(min_edge=0.65, max_size=3)
parlay, status, reason = builder.build_parlay(candidate_legs)

print("\n=== LIVE PARLAY ANALYSIS ===\n")
if status == 'SUCCESS':
    print("SAFE PARLAY FOUND:")
    for leg in parlay:
        print(f"  - {leg.player} {leg.stat} {leg.direction} {leg.line}")
else:
    print(f"NO SAFE PARLAY: {reason}")
