import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from scipy import optimize
import warnings
warnings.filterwarnings('ignore')

class NFLOptimizer:
    def __init__(self):
        self.results = {}
        
    def load_backtest_results(self):
        """Load previous backtest results"""
        try:
            # Find latest backtest file
            output_dir = 'outputs'
            backtest_files = [f for f in os.listdir(output_dir) if f.startswith('backtest_results')]
            
            if not backtest_files:
                print("No backtest results found. Running backtest first...")
                return None
            
            latest_file = max(backtest_files)
            with open(f'{output_dir}/{latest_file}', 'r') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"Error loading backtest results: {e}")
            return None
    
    def load_historical_data(self):
        """Load historical data for optimization"""
        try:
            with open('hou_pit_data_jan12.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Data file not found. Please run backtest first.")
            return None
    
    def calculate_weights(self, data):
        """Calculate optimal weights for different statistics"""
        hou = data['historical_stats']['houston']
        pit = data['historical_stats']['pittsburgh']
        
        # Define objective function to minimize prediction error
        def objective(weights):
            # Normalize weights
            weights = np.maximum(weights, 0)
            weights = weights / np.sum(weights)
            
            # Calculate weighted score for each team
            hou_features = np.array([
                hou['avg_points_for'],
                hou['defensive_rank'],  # Lower is better
                hou['turnover_margin'],
                hou['redzone_efficiency']
            ])
            
            pit_features = np.array([
                pit['avg_points_for'],
                pit['defensive_rank'],
                pit['turnover_margin'],
                pit['redzone_efficiency']
            ])
            
            # Transform defensive rank (lower rank = better defense)
            hou_features[1] = 33 - hou_features[1]  # Convert to positive scale
            pit_features[1] = 33 - pit_features[1]
            
            # Normalize features
            hou_norm = hou_features / np.max(np.abs(hou_features))
            pit_norm = pit_features / np.max(np.abs(pit_features))
            
            # Calculate weighted scores
            hou_score = np.dot(hou_norm, weights)
            pit_score = np.dot(pit_norm, weights)
            
            # Add home field advantage (3 points)
            pit_score += 0.1  # Arbitrary adjustment for home field
            
            # Return difference from expected (we want close game)
            return abs(pit_score - hou_score - 0.5)  # Target spread of 0.5
        
        # Initial weights (equal)
        initial_weights = np.array([0.25, 0.25, 0.25, 0.25])
        
        # Bounds for weights (0 to 1)
        bounds = [(0, 1) for _ in range(4)]
        
        # Constraint: weights sum to 1
        constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        
        # Optimize
        result = optimize.minimize(objective, initial_weights, 
                                  bounds=bounds, constraints=constraints,
                                  method='SLSQP')
        
        optimal_weights = np.maximum(result.x, 0)
        optimal_weights = optimal_weights / np.sum(optimal_weights)
        
        return optimal_weights
    
    def optimize_predictions(self, data, optimal_weights):
        """Make optimized predictions using calculated weights"""
        hou = data['historical_stats']['houston']
        pit = data['historical_stats']['pittsburgh']
        
        # Prepare features
        hou_features = np.array([
            hou['avg_points_for'],
            33 - hou['defensive_rank'],  # Convert to positive scale
            hou['turnover_margin'],
            hou['redzone_efficiency']
        ])
        
        pit_features = np.array([
            pit['avg_points_for'],
            33 - pit['defensive_rank'],
            pit['turnover_margin'],
            pit['redzone_efficiency']
        ])
        
        # Normalize features
        all_features = np.vstack([hou_features, pit_features])
        max_vals = np.max(np.abs(all_features), axis=0)
        max_vals[max_vals == 0] = 1  # Avoid division by zero
        
        hou_norm = hou_features / max_vals
        pit_norm = pit_features / max_vals
        
        # Calculate base scores
        hou_base = np.dot(hou_norm, optimal_weights)
        pit_base = np.dot(pit_norm, optimal_weights)
        
        # Scale to realistic point totals
        scale_factor = 20  # Arbitrary scaling factor
        hou_score = hou_base * scale_factor
        pit_score = pit_base * scale_factor
        
        # Add home field advantage
        pit_score += 3.0
        
        # Add noise for realism
        np.random.seed(42)
        hou_score += np.random.normal(0, 1)
        pit_score += np.random.normal(0, 1)
        
        # Ensure positive scores
        hou_score = max(10, hou_score)
        pit_score = max(10, pit_score)
        
        return {
            "houston_score": round(hou_score, 1),
            "pittsburgh_score": round(pit_score, 1),
            "point_spread": round(pit_score - hou_score, 1),
            "total_points": round(hou_score + pit_score, 1),
            "weights_used": optimal_weights.tolist()
        }
    
    def run_monte_carlo_optimized(self, prediction, n_simulations=10000):
        """Run Monte Carlo simulation with optimized parameters"""
        hou_mean = prediction['houston_score']
        pit_mean = prediction['pittsburgh_score']
        
        # Reduced variance due to optimization
        np.random.seed(42)
        hou_scores = np.random.normal(hou_mean, 5, n_simulations)
        pit_scores = np.random.normal(pit_mean, 5, n_simulations)
        
        # Ensure positive scores
        hou_scores = np.maximum(hou_scores, 0)
        pit_scores = np.maximum(pit_scores, 0)
        
        spreads = pit_scores - hou_scores
        totals = hou_scores + pit_scores
        
        return {
            "hou_scores": hou_scores.tolist(),
            "pit_scores": pit_scores.tolist(),
            "spreads": spreads.tolist(),
            "totals": totals.tolist()
        }
    
    def analyze_optimized_results(self, simulations, actual_spread=-3.5, actual_total=40.5):
        """Analyze optimized simulation results"""
        spreads = np.array(simulations['spreads'])
        totals = np.array(simulations['totals'])
        
        # Cover probabilities
        cover_prob = {
            "houston": np.mean(spreads > actual_spread),
            "pittsburgh": np.mean(spreads < actual_spread)
        }
        
        # Total probabilities
        over_prob = np.mean(totals > actual_total)
        under_prob = np.mean(totals < actual_total)
        
        # Confidence intervals
        spread_ci = np.percentile(spreads, [2.5, 97.5])
        total_ci = np.percentile(totals, [2.5, 97.5])
        
        # Expected value
        hou_ev = (cover_prob['houston'] * 1.91 - 1) * 100
        pit_ev = (cover_prob['pittsburgh'] * 1.91 - 1) * 100
        
        # Calculate edge (probability - breakeven)
        breakeven = 1 / 1.91  # For -110 odds
        hou_edge = cover_prob['houston'] - breakeven
        pit_edge = cover_prob['pittsburgh'] - breakeven
        
        return {
            "cover_probabilities": {
                "houston": round(cover_prob['houston'] * 100, 2),
                "pittsburgh": round(cover_prob['pittsburgh'] * 100, 2)
            },
            "total_probabilities": {
                "over": round(over_prob * 100, 2),
                "under": round(under_prob * 100, 2)
            },
            "expected_value": {
                "houston": round(hou_ev, 2),
                "pittsburgh": round(pit_ev, 2)
            },
            "edge": {
                "houston": round(hou_edge * 100, 2),
                "pittsburgh": round(pit_edge * 100, 2)
            },
            "confidence_intervals": {
                "spread": [round(spread_ci[0], 2), round(spread_ci[1], 2)],
                "total": [round(total_ci[0], 2), round(total_ci[1], 2)]
            }
        }
    
    def compare_results(self, original_results, optimized_results):
        """Compare original vs optimized results"""
        comparison = {}
        
        # Extract key metrics
        metrics = ['houston', 'pittsburgh']
        
        for metric in metrics:
            comparison[f"{metric}_cover_prob"] = {
                "original": original_results['cover_probabilities'][metric],
                "optimized": optimized_results['cover_probabilities'][metric],
                "improvement": round(
                    optimized_results['cover_probabilities'][metric] - 
                    original_results['cover_probabilities'][metric], 2
                )
            }
            
            comparison[f"{metric}_ev"] = {
                "original": original_results['expected_value'][f"{metric}_ev"],
                "optimized": optimized_results['expected_value'][metric],
                "improvement": round(
                    optimized_results['expected_value'][metric] - 
                    original_results['expected_value'][f"{metric}_ev"], 2
                )
            }
        
        return comparison
    
    def run_optimization(self):
        """Main optimization function"""
        print("Running NFL Statistics Optimization for HOU vs PIT...")
        print("=" * 60)
        
        # Load data
        data = self.load_historical_data()
        if data is None:
            return
        
        # Load original backtest results
        original = self.load_backtest_results()
        
        # Calculate optimal weights
        print("\nCalculating optimal weights for statistics...")
        optimal_weights = self.calculate_weights(data)
        
        print("\nOPTIMAL WEIGHTS:")
        stats = ['Offensive PPG', 'Defensive Rank', 'Turnover Margin', 'Redzone Efficiency']
        for stat, weight in zip(stats, optimal_weights):
            print(f"{stat}: {weight:.2%}")
        
        # Make optimized predictions
        optimized_prediction = self.optimize_predictions(data, optimal_weights)
        
        print("\nOPTIMIZED PREDICTION:")
        print(f"Houston Texans: {optimized_prediction['houston_score']}")
        print(f"Pittsburgh Steelers: {optimized_prediction['pittsburgh_score']}")
        print(f"Optimized Spread: PIT {optimized_prediction['point_spread']:+.1f}")
        print(f"Optimized Total: {optimized_prediction['total_points']}")
        
        # Run optimized Monte Carlo
        print("\nRunning optimized Monte Carlo simulation (10,000 iterations)...")
        optimized_simulations = self.run_monte_carlo_optimized(optimized_prediction)
        
        # Analyze optimized results
        optimized_analysis = self.analyze_optimized_results(optimized_simulations)
        
        print("\nOPTIMIZED ANALYSIS:")
        print(f"HOU +3.5 Cover Probability: {optimized_analysis['cover_probabilities']['houston']}%")
        print(f"PIT -3.5 Cover Probability: {optimized_analysis['cover_probabilities']['pittsburgh']}%")
        print(f"Over 40.5 Probability: {optimized_analysis['total_probabilities']['over']}%")
        print(f"Under 40.5 Probability: {optimized_analysis['total_probabilities']['under']}%")
        
        print("\nOPTIMIZED EXPECTED VALUE:")
        print(f"HOU +3.5 EV: {optimized_analysis['expected_value']['houston']}%")
        print(f"PIT -3.5 EV: {optimized_analysis['expected_value']['pittsburgh']}%")
        
        print("\nEDGE OVER BREAKEVEN:")
        print(f"HOU +3.5 Edge: {optimized_analysis['edge']['houston']}%")
        print(f"PIT -3.5 Edge: {optimized_analysis['edge']['pittsburgh']}%")
        
        # Compare with original if available
        if original:
            print("\n" + "=" * 60)
            print("COMPARISON: ORIGINAL vs OPTIMIZED")
            print("=" * 60)
            
            comparison = self.compare_results(
                original['analysis'],
                optimized_analysis
            )
            
            for metric, values in comparison.items():
                team = "HOU" if "houston" in metric else "PIT"
                metric_type = "Cover Probability" if "prob" in metric else "Expected Value"
                
                if "prob" in metric:
                    print(f"\n{team} {metric_type}:")
                    print(f"  Original: {values['original']}%")
                    print(f"  Optimized: {values['optimized']}%")
                    print(f"  Improvement: {values['improvement']:+}%")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"optimized_results_hou_pit_{timestamp}.json"
        
        results = {
            "timestamp": timestamp,
            "optimized_prediction": optimized_prediction,
            "optimized_analysis": optimized_analysis,
            "optimal_weights": optimal_weights.tolist(),
            "metadata": {
                "simulations": 10000,
                "optimization_method": "weighted_statistics",
                "version": "1.0"
            }
        }
        
        # Ensure outputs directory exists
        os.makedirs('outputs', exist_ok=True)
        
        with open(f'outputs/{results_file}', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nOptimized results saved to: outputs/{results_file}")
        
        # Store for return
        self.results = results
        
        return results

if __name__ == "__main__":
    optimizer = NFLOptimizer()
    results = optimizer.run_optimization()
