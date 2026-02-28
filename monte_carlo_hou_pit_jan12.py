import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class NFLMonteCarlo:
    def __init__(self):
        self.results = {}
        
    def load_data(self):
        """Load data for Monte Carlo simulation"""
        try:
            with open('hou_pit_data_jan12.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Data file not found. Please create hou_pit_data_jan12.json")
            return None
    
    def run_monte_carlo(self, n_simulations=10000, use_optimized=False):
        """Run Monte Carlo simulation"""
        data = self.load_data()
        if data is None:
            return
        
        hou = data['historical_stats']['houston']
        pit = data['historical_stats']['pittsburgh']
        
        # Base predictions
        if use_optimized:
            # Use optimized parameters (smaller variance)
            hou_mean = 21.5
            pit_mean = 20.8
            std_dev = 4.5
        else:
            # Use historical averages
            hou_mean = hou['avg_points_for']
            pit_mean = pit['avg_points_for'] + 3  # Home field advantage
            std_dev = 7.0
        
        np.random.seed(42)
        
        # Simulate scores
        hou_scores = np.random.normal(hou_mean, std_dev, n_simulations)
        pit_scores = np.random.normal(pit_mean, std_dev, n_simulations)
        
        # Apply constraints
        hou_scores = np.maximum(hou_scores, 0)
        pit_scores = np.maximum(pit_scores, 0)
        
        # Apply correlation (teams often score similarly in low-scoring games)
        correlation = 0.3
        hou_scores = hou_scores * (1 - correlation) + pit_scores * correlation
        pit_scores = pit_scores * (1 - correlation) + hou_scores * correlation
        
        # Calculate game outcomes
        spreads = pit_scores - hou_scores
        totals = hou_scores + pit_scores
        
        # Actual betting lines
        actual_spread = -3.5  # PIT -3.5
        actual_total = 40.5
        
        # Calculate probabilities
        hou_cover = np.mean(spreads > actual_spread)  # HOU +3.5
        pit_cover = np.mean(spreads < actual_spread)  # PIT -3.5
        over_prob = np.mean(totals > actual_total)
        under_prob = np.mean(totals < actual_total)
        
        # Calculate expected value
        hou_ev = (hou_cover * 1.91 - 1) * 100
        pit_ev = (pit_cover * 1.91 - 1) * 100
        
        # Calculate edge
        breakeven = 1 / 1.91
        hou_edge = (hou_cover - breakeven) * 100
        pit_edge = (pit_cover - breakeven) * 100
        
        # Calculate confidence intervals
        spread_ci = np.percentile(spreads, [2.5, 50, 97.5])
        total_ci = np.percentile(totals, [2.5, 50, 97.5])
        
        # Create results dictionary
        results = {
            "simulation_type": "optimized" if use_optimized else "baseline",
            "parameters": {
                "n_simulations": n_simulations,
                "hou_mean": hou_mean,
                "pit_mean": pit_mean,
                "std_dev": std_dev
            },
            "probabilities": {
                "hou_cover": round(hou_cover * 100, 2),
                "pit_cover": round(pit_cover * 100, 2),
                "over": round(over_prob * 100, 2),
                "under": round(under_prob * 100, 2)
            },
            "expected_value": {
                "hou_ev": round(hou_ev, 2),
                "pit_ev": round(pit_ev, 2)
            },
            "edge": {
                "hou_edge": round(hou_edge, 2),
                "pit_edge": round(pit_edge, 2)
            },
            "confidence_intervals": {
                "spread_95ci": [round(spread_ci[0], 2), round(spread_ci[2], 2)],
                "spread_median": round(spread_ci[1], 2),
                "total_95ci": [round(total_ci[0], 2), round(total_ci[2], 2)],
                "total_median": round(total_ci[1], 2)
            },
            "simulation_data": {
                "hou_scores": hou_scores.tolist()[:1000],  # Save first 1000 for plotting
                "pit_scores": pit_scores.tolist()[:1000],
                "spreads": spreads.tolist()[:1000],
                "totals": totals.tolist()[:1000]
            }
        }
        
        return results
    
    def save_results(self, results, prefix="MC"):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"outputs/{prefix}_HOU_PIT_JAN12_{timestamp}.json"
        
        os.makedirs('outputs', exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        return filename
    
    def run_baseline_mc(self):
        """Run baseline Monte Carlo simulation"""
        print("Running Baseline Monte Carlo Simulation...")
        print("=" * 60)
        
        results = self.run_monte_carlo(n_simulations=10000, use_optimized=False)
        
        if results:
            print("\nBASELINE MONTE CARLO RESULTS:")
            print(f"HOU +3.5 Cover Probability: {results['probabilities']['hou_cover']}%")
            print(f"PIT -3.5 Cover Probability: {results['probabilities']['pit_cover']}%")
            print(f"Over 40.5 Probability: {results['probabilities']['over']}%")
            print(f"Under 40.5 Probability: {results['probabilities']['under']}%")
            
            print(f"\nExpected Value:")
            print(f"HOU +3.5 EV: {results['expected_value']['hou_ev']}%")
            print(f"PIT -3.5 EV: {results['expected_value']['pit_ev']}%")
            
            print(f"\nEdge Over Breakeven:")
            print(f"HOU +3.5 Edge: {results['edge']['hou_edge']}%")
            print(f"PIT -3.5 Edge: {results['edge']['pit_edge']}%")
            
            print(f"\n95% Confidence Intervals:")
            print(f"Spread: {results['confidence_intervals']['spread_95ci'][0]} to {results['confidence_intervals']['spread_95ci'][1]}")
            print(f"Total: {results['confidence_intervals']['total_95ci'][0]} to {results['confidence_intervals']['total_95ci'][1]}")
            
            filename = self.save_results(results, prefix="MC_baseline")
            print(f"\nResults saved to: {filename}")
            
            self.results['baseline'] = results
            return results
    
    def run_optimized_mc(self):
        """Run optimized Monte Carlo simulation"""
        print("\n" + "=" * 60)
        print("Running Optimized Monte Carlo Simulation...")
        print("=" * 60)
        
        results = self.run_monte_carlo(n_simulations=10000, use_optimized=True)
        
        if results:
            print("\nOPTIMIZED MONTE CARLO RESULTS:")
            print(f"HOU +3.5 Cover Probability: {results['probabilities']['hou_cover']}%")
            print(f"PIT -3.5 Cover Probability: {results['probabilities']['pit_cover']}%")
            print(f"Over 40.5 Probability: {results['probabilities']['over']}%")
            print(f"Under 40.5 Probability: {results['probabilities']['under']}%")
            
            print(f"\nExpected Value:")
            print(f"HOU +3.5 EV: {results['expected_value']['hou_ev']}%")
            print(f"PIT -3.5 EV: {results['expected_value']['pit_ev']}%")
            
            print(f"\nEdge Over Breakeven:")
            print(f"HOU +3.5 Edge: {results['edge']['hou_edge']}%")
            print(f"PIT -3.5 Edge: {results['edge']['pit_edge']}%")
            
            print(f"\n95% Confidence Intervals:")
            print(f"Spread: {results['confidence_intervals']['spread_95ci'][0]} to {results['confidence_intervals']['spread_95ci'][1]}")
            print(f"Total: {results['confidence_intervals']['total_95ci'][0]} to {results['confidence_intervals']['total_95ci'][1]}")
            
            filename = self.save_results(results, prefix="MC_optimized")
            print(f"\nResults saved to: {filename}")
            
            self.results['optimized'] = results
            return results
    
    def compare_results(self):
        """Compare baseline vs optimized results"""
        if 'baseline' not in self.results or 'optimized' not in self.results:
            print("Please run both baseline and optimized simulations first.")
            return
        
        baseline = self.results['baseline']
        optimized = self.results['optimized']
        
        print("\n" + "=" * 60)
        print("COMPARISON: BASELINE vs OPTIMIZED")
        print("=" * 60)
        
        print("\nCOVER PROBABILITIES:")
        print(f"HOU +3.5: {baseline['probabilities']['hou_cover']}% → {optimized['probabilities']['hou_cover']}% " +
              f"({optimized['probabilities']['hou_cover'] - baseline['probabilities']['hou_cover']:+.2f}%)")
        print(f"PIT -3.5: {baseline['probabilities']['pit_cover']}% → {optimized['probabilities']['pit_cover']}% " +
              f"({optimized['probabilities']['pit_cover'] - baseline['probabilities']['pit_cover']:+.2f}%)")
        
        print("\nEXPECTED VALUE:")
        print(f"HOU +3.5 EV: {baseline['expected_value']['hou_ev']}% → {optimized['expected_value']['hou_ev']}% " +
              f"({optimized['expected_value']['hou_ev'] - baseline['expected_value']['hou_ev']:+.2f}%)")
        print(f"PIT -3.5 EV: {baseline['expected_value']['pit_ev']}% → {optimized['expected_value']['pit_ev']}% " +
              f"({optimized['expected_value']['pit_ev'] - baseline['expected_value']['pit_ev']:+.2f}%)")
        
        print("\nEDGE:")
        print(f"HOU +3.5 Edge: {baseline['edge']['hou_edge']}% → {optimized['edge']['hou_edge']}% " +
              f"({optimized['edge']['hou_edge'] - baseline['edge']['hou_edge']:+.2f}%)")
        print(f"PIT -3.5 Edge: {baseline['edge']['pit_edge']}% → {optimized['edge']['pit_edge']}% " +
              f"({optimized['edge']['pit_edge'] - baseline['edge']['pit_edge']:+.2f}%)")
        
        print("\nCONFIDENCE INTERVAL WIDTH:")
        baseline_spread_width = baseline['confidence_intervals']['spread_95ci'][1] - baseline['confidence_intervals']['spread_95ci'][0]
        optimized_spread_width = optimized['confidence_intervals']['spread_95ci'][1] - optimized['confidence_intervals']['spread_95ci'][0]
        print(f"Spread 95% CI Width: {baseline_spread_width:.2f} → {optimized_spread_width:.2f} " +
              f"({optimized_spread_width - baseline_spread_width:+.2f})")
        
        # Save comparison
        comparison = {
            "baseline": baseline,
            "optimized": optimized,
            "improvements": {
                "hou_cover_prob_change": optimized['probabilities']['hou_cover'] - baseline['probabilities']['hou_cover'],
                "pit_cover_prob_change": optimized['probabilities']['pit_cover'] - baseline['probabilities']['pit_cover'],
                "hou_ev_change": optimized['expected_value']['hou_ev'] - baseline['expected_value']['hou_ev'],
                "pit_ev_change": optimized['expected_value']['pit_ev'] - baseline['expected_value']['pit_ev']
            }
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"outputs/comparison_HOU_PIT_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(comparison, f, indent=2)
        
        print(f"\nComparison saved to: {filename}")
        
        return comparison

if __name__ == "__main__":
    mc = NFLMonteCarlo()
    
    # Run both simulations
    mc.run_baseline_mc()
    mc.run_optimized_mc()
    
    # Compare results
    mc.compare_results()
