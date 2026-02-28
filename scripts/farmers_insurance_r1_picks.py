"""
Farmers Insurance Open - Round 1 Prop Picks
Generates Underdog Fantasy golf prop predictions for today's tournament.
"""

from golf_agents.round_prediction import RoundPredictionAgent
import pandas as pd
import os

# List of players and Underdog lines for today (mock example)
players = [
    {"id": "scheffler_s", "name": "Scottie Scheffler", "birdies_line": 3.5, "strokes_line": 71.5, "fairways_line": 7.5},
    {"id": "mcilroy_r", "name": "Rory McIlroy", "birdies_line": 3.5, "strokes_line": 71.5, "fairways_line": 7.5},
    {"id": "cantlay_p", "name": "Patrick Cantlay", "birdies_line": 3.5, "strokes_line": 71.5, "fairways_line": 7.5},
    {"id": "rahm_j", "name": "Jon Rahm", "birdies_line": 3.5, "strokes_line": 71.5, "fairways_line": 7.5},
    {"id": "schauffele_x", "name": "Xander Schauffele", "birdies_line": 3.5, "strokes_line": 71.5, "fairways_line": 7.5},
    {"id": "morikawa_c", "name": "Collin Morikawa", "birdies_line": 3.5, "strokes_line": 71.5, "fairways_line": 7.5},
]

agent = RoundPredictionAgent()

results = []

for p in players:
    pred = agent.predict_round(p["id"])
    if not pred:
        continue
    # Evaluate props
    birdies_prob = agent.evaluate_prop(pred['expected_birdies'], pred['birdie_std'], p['birdies_line'], "higher")
    strokes_prob = agent.evaluate_prop(pred['expected_score'], pred['score_std'], p['strokes_line'], "lower")
    fairways_prob = agent.evaluate_prop(pred['expected_fairways'], pred['fairway_std'], p['fairways_line'], "higher")
    results.append({
        "player": p["name"],
        "birdies_model": pred['expected_birdies'],
        "birdies_line": p['birdies_line'],
        "birdies_prob": birdies_prob,
        "strokes_model": pred['expected_score'],
        "strokes_line": p['strokes_line'],
        "strokes_prob": strokes_prob,
        "fairways_model": pred['expected_fairways'],
        "fairways_line": p['fairways_line'],
        "fairways_prob": fairways_prob
    })

# Output to DataFrame and CSV
out_df = pd.DataFrame(results)
outputs_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(outputs_dir, exist_ok=True)
out_path = os.path.join(outputs_dir, "farmers_insurance_r1_picks.csv")
out_df.to_csv(out_path, index=False)

print("\nFARMERS INSURANCE OPEN - ROUND 1 PROP PICKS")
print(out_df.to_string(index=False, float_format="{:.2f}".format))
print(f"\nResults saved to {out_path}")
