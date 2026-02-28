import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class NFLUnderdogBacktest:
    def __init__(self):
        self.results = {}
        
    def load_data(self):
        """Load NFL data for HOU vs PIT game"""
        try:
            # Load from JSON file
            with open('hou_pit_data_jan12.json', 'r') as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            print("Data file not found. Creating sample data...")
            return self.create_sample_data()
    
    def create_sample_data(self):
        """Create sample data if file doesn't exist"""
        sample_data = {
            "game_info": {
                "home_team": "Pittsburgh Steelers",
                "away_team": "Houston Texans",
                "date": "2025-01-12",
                "home_spread": -3.5,
                "away_spread": 3.5,
                "over_under": 40.5
            },
            "historical_stats": {
                "houston": {
                    "avg_points_for": 23.1,
                    "avg_points_against": 20.8,
                    "offensive_rank": 12,
                    "defensive_rank": 7,
                    "turnover_margin": 0.5,
                    "redzone_efficiency": 0.55
                },
                "pittsburgh": {
                    "avg_points_for": 20.3,
                    "avg_points_against": 19.1,
                    "offensive_rank": 21,
                    "defensive_rank": 6,
                    "turnover_margin": -0.2,
                    "redzone_efficiency": 0.48
                }
            },
            "player_projections": {
                "houston": {
                    "QB": {"CJ_Stroud": {"pass_yards": 265, "tds": 1.8, "ints": 0.7}},
                    "RB": {"Dameon_Pierce": {"rush_yards": 68, "tds": 0.5}},
                    "WR": {"Nico_Collins": {"rec_yards": 85, "tds": 0.6}}
                },
                "pittsburgh": {
                    "QB": {"Kenny_Pickett": {"pass_yards": 210, "tds": 1.2, "ints": 0.9}},
                    "RB": {"Najee_Harris": {"rush_yards": 72, "tds": 0.6}},
                    "WR": {"George_Pickens": {"rec_yards": 65, "tds": 0.4}}
                }
            }
        }
        
        # Save sample data
        with open('hou_pit_data_jan12.json', 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        return sample_data
    
    def calculate_baseline_prediction(self, data):
        """Calculate baseline score prediction"""
        hou = data['historical_stats']['houston']
        pit = data['historical_stats']['pittsburgh']
        
        # Home field advantage: ~3 points
        home_advantage = 3.0
        
        # Houston projected points
        hou_off = hou['avg_points_for']
        pit_def = pit['avg_points_against']
        hou_score = (hou_off + pit_def) / 2
        
        # Pittsburgh projected points
        pit_off = pit['avg_points_for']
        hou_def = hou['avg_points_against']
        pit_score = (pit_off + hou_def) / 2 + home_advantage
        
        # Adjust for defensive ranks
        rank_adjustment = (hou['defensive_rank'] - pit['defensive_rank']) / 10
        hou_score -= rank_adjustment
        pit_score += rank_adjustment
        
        # Adjust for turnover margin
        turnover_adjust = (hou['turnover_margin'] - pit['turnover_margin']) * 1.5
        hou_score += turnover_adjust
        pit_score -= turnover_adjust
        
        return {
            "houston_score": round(hou_score, 1),
            "pittsburgh_score": round(pit_score, 1),
            "point_spread": round(pit_score - hou_score, 1),
            "total_points": round(hou_score + pit_score, 1)
        }
    
    def simulate_game(self, prediction, n_simulations=1000):
        """Simulate game outcomes"""
        hou_mean = prediction['houston_score']
        pit_mean = prediction['pittsburgh_score']
        
        # Add randomness
        np.random.seed(42)
        hou_scores = np.random.normal(hou_mean, 7, n_simulations)
        pit_scores = np.random.normal(pit_mean, 7, n_simulations)
        
        # Ensure positive scores
        hou_scores = np.maximum(hou_scores, 0)
        pit_scores = np.maximum(pit_scores, 0)
        
        # Calculate outcomes
        spreads = pit_scores - hou_scores
        totals = hou_scores + pit_scores
        
        return {
            "hou_scores": hou_scores.tolist(),
            "pit_scores": pit_scores.tolist(),
            "spreads": spreads.tolist(),
            "totals": totals.tolist()
        }
    
    def analyze_results(self, simulations, actual_spread=-3.5, actual_total=40.5):
        """Analyze simulation results"""
        spreads = np.array(simulations['spreads'])
        totals = np.array(simulations['totals'])
        
        # Spread analysis
        cover_prob = {
            "houston": np.mean(spreads > actual_spread),  # HOU +3.5
            "pittsburgh": np.mean(spreads < actual_spread)  # PIT -3.5
        }
        
        # Total analysis
        over_prob = np.mean(totals > actual_total)
        under_prob = np.mean(totals < actual_total)
        
        # Confidence intervals
        spread_ci = np.percentile(spreads, [2.5, 97.5])
        total_ci = np.percentile(totals, [2.5, 97.5])
        
        return {
            "cover_probabilities": {
                "houston": round(cover_prob['houston'] * 100, 1),
                "pittsburgh": round(cover_prob['pittsburgh'] * 100, 1)
            },
            "total_probabilities": {
                "over": round(over_prob * 100, 1),
                "under": round(under_prob * 100, 1)
            },
            "confidence_intervals": {
                "spread": [round(spread_ci[0], 1), round(spread_ci[1], 1)],
                "total": [round(total_ci[0], 1), round(total_ci[1], 1)]
            },
            "expected_value": {
                "houston_ev": round((cover_prob['houston'] * 1.91 - 1) * 100, 1),
                "pittsburgh_ev": round((cover_prob['pittsburgh'] * 1.91 - 1) * 100, 1)
            }
        }
    
    def run_backtest(self):
        """Main backtest function"""
        print("Running NFL Underdog Backtest for HOU vs PIT (Jan 12)...")
        print("=" * 60)
        
        # Load data
        data = self.load_data()
        
        # Calculate baseline prediction
        prediction = self.calculate_baseline_prediction(data)
        
        # Display prediction
        print("\nBASELINE PREDICTION:")
        print(f"Houston Texans: {prediction['houston_score']}")
        print(f"Pittsburgh Steelers: {prediction['pittsburgh_score']}")
        print(f"Predicted Spread: PIT {prediction['point_spread']:+.1f}")
        print(f"Predicted Total: {prediction['total_points']}")
        print(f"Actual Spread: PIT -3.5")
        print(f"Actual Total: 40.5")
        
        # Run simulations
        print("\nRunning 10,000 game simulations...")
        simulations = self.simulate_game(prediction, n_simulations=10000)
        
        # Analyze results
        analysis = self.analyze_results(simulations)
        
        # Display analysis
        print("\nANALYSIS RESULTS:")
        print(f"HOU +3.5 Cover Probability: {analysis['cover_probabilities']['houston']}%")
        print(f"PIT -3.5 Cover Probability: {analysis['cover_probabilities']['pittsburgh']}%")
        print(f"Over 40.5 Probability: {analysis['total_probabilities']['over']}%")
        print(f"Under 40.5 Probability: {analysis['total_probabilities']['under']}%")
        
        print("\nEXPECTED VALUE (EV):")
        print(f"HOU +3.5 EV: {analysis['expected_value']['houston_ev']}%")
        print(f"PIT -3.5 EV: {analysis['expected_value']['pittsburgh_ev']}%")
        
        print("\n95% CONFIDENCE INTERVALS:")
        print(f"Spread: {analysis['confidence_intervals']['spread'][0]} to {analysis['confidence_intervals']['spread'][1]}")
        print(f"Total: {analysis['confidence_intervals']['total'][0]} to {analysis['confidence_intervals']['total'][1]}")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"backtest_results_hou_pit_{timestamp}.json"
        
        results = {
            "timestamp": timestamp,
            "game_info": data['game_info'],
            "baseline_prediction": prediction,
            "analysis": analysis,
            "metadata": {
                "simulations": 10000,
                "version": "1.0"
            }
        }
        
        # Ensure outputs directory exists
        os.makedirs('outputs', exist_ok=True)
        
        with open(f'outputs/{results_file}', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: outputs/{results_file}")
        
        # Store for return
        self.results = results
        
        return results

    def get_top_overs_unders(self, mc_output_path=None, top_n=5):
        """Extract top N overs and unders from MC sim output"""
        import glob
        if mc_output_path is None:
            files = glob.glob("outputs/MC_HOU_PIT_JAN12_*.json")
            if not files:
                return [], []
            mc_output_path = max(files, key=os.path.getmtime)
        with open(mc_output_path, "r") as f:
            props = json.load(f)
        overs = [p for p in props if p.get("direction") == "higher"]
        unders = [p for p in props if p.get("direction") == "lower"]
        overs_sorted = sorted(overs, key=lambda x: x.get("prob_hit", 0), reverse=True)[:top_n]
        unders_sorted = sorted(unders, key=lambda x: x.get("prob_hit", 0), reverse=True)[:top_n]
        return overs_sorted, unders_sorted

if __name__ == "__main__":
    backtest = NFLUnderdogBacktest()
    results = backtest.run_backtest()

    # --- Add Top 5 Overs/Unders to terminal and summary ---
    overs, unders = backtest.get_top_overs_unders()
    def fmt_prop(p):
        pct = round(100 * p.get("prob_hit", 0), 1)
        return f"{p.get('player','?')} {p.get('stat','?')} {p.get('direction','?')} {p.get('line','?')}: {pct}%"

    print("\nTOP 5 OVERS (Highest Prob > Line):")
    for p in overs:
        print("  ", fmt_prop(p))
    print("\nTOP 5 UNDERS (Highest Prob < Line):")
    for p in unders:
        print("  ", fmt_prop(p))

    # Also append to summary file if it exists
    try:
        summary_path = None
        for fname in os.listdir("outputs"):
            if fname.startswith("summary_hou_pit_") and fname.endswith(".txt"):
                summary_path = os.path.join("outputs", fname)
        if summary_path:
            with open(summary_path, "a") as f:
                f.write("\n\nTOP 5 OVERS (Highest Prob > Line):\n")
                for p in overs:
                    f.write("  " + fmt_prop(p) + "\n")
                f.write("\nTOP 5 UNDERS (Highest Prob < Line):\n")
                for p in unders:
                    f.write("  " + fmt_prop(p) + "\n")
    except Exception as e:
        print(f"[WARN] Could not update summary file: {e}")
