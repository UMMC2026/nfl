#!/usr/bin/env python3
"""
Monte Carlo + Bayesian Analysis for January 8, 2026 Portfolio
Simulates 10,000 trials for each entry to calculate win probability and EV distribution
"""

import json
import random
from pathlib import Path
from collections import Counter
import statistics

# Payout multipliers
POWER_PAYOUTS = {
    2: 3.0,
    3: 6.0,
    4: 10.0,
    5: 15.0,
}

def bayesian_probability_distribution(empirical_rate, n_games=10):
    """Calculate Bayesian posterior distribution using Beta-Binomial"""
    # Prior: Beta(3, 3) - slightly informed prior
    prior_alpha = 3
    prior_beta = 3
    
    # Update with observed data
    hits = empirical_rate * n_games
    posterior_alpha = prior_alpha + hits
    posterior_beta = prior_beta + (n_games - hits)
    
    # Mean of Beta distribution
    mean_prob = posterior_alpha / (posterior_alpha + posterior_beta)
    
    # Variance and credible interval
    total = posterior_alpha + posterior_beta
    variance = (posterior_alpha * posterior_beta) / (total**2 * (total + 1))
    std_dev = variance ** 0.5
    
    # 90% credible interval (approximate)
    ci_lower = max(0, mean_prob - 1.645 * std_dev)
    ci_upper = min(1, mean_prob + 1.645 * std_dev)
    
    return {
        "mean": round(mean_prob, 3),
        "std_dev": round(std_dev, 3),
        "ci_90_lower": round(ci_lower, 3),
        "ci_90_upper": round(ci_upper, 3),
        "alpha": posterior_alpha,
        "beta": posterior_beta
    }

def simulate_pick(prob, n_simulations=10000):
    """Monte Carlo simulation for a single pick"""
    hits = sum(1 for _ in range(n_simulations) if random.random() < prob)
    return hits / n_simulations

def simulate_entry(picks, payout_multiplier, n_simulations=10000):
    """Monte Carlo simulation for an entry (all picks must hit)"""
    wins = 0
    payouts = []
    
    for _ in range(n_simulations):
        # Check if all picks hit
        all_hit = all(random.random() < pick["prob_final"] for pick in picks)
        if all_hit:
            wins += 1
            payouts.append(payout_multiplier)
        else:
            payouts.append(0)
    
    win_rate = wins / n_simulations
    avg_payout = statistics.mean(payouts)
    ev_units = avg_payout - 1.0
    
    # Calculate distribution stats
    payout_variance = statistics.variance(payouts) if len(payouts) > 1 else 0
    payout_std = payout_variance ** 0.5
    
    return {
        "win_rate": round(win_rate, 4),
        "wins": wins,
        "losses": n_simulations - wins,
        "avg_payout": round(avg_payout, 2),
        "ev_units": round(ev_units, 3),
        "ev_roi": round(ev_units * 100, 1),
        "std_dev": round(payout_std, 2),
        "sharpe_ratio": round(ev_units / payout_std, 3) if payout_std > 0 else 0
    }

def analyze_correlation_impact(picks):
    """Analyze potential correlation between picks"""
    teams = [p["team"] for p in picks]
    stats = [p["stat"] for p in picks]
    
    same_team = len(teams) != len(set(teams))
    same_stat = len(stats) != len(set(stats))
    
    correlation_risk = "LOW"
    if same_team and same_stat:
        correlation_risk = "HIGH"
    elif same_team or same_stat:
        correlation_risk = "MEDIUM"
    
    return {
        "same_team": same_team,
        "same_stat": same_stat,
        "risk_level": correlation_risk,
        "teams": teams,
        "stats": stats
    }

def main():
    print("\n" + "="*80)
    print("🎲 MONTE CARLO + BAYESIAN ANALYSIS - JANUARY 8, 2026")
    print("="*80)
    print("Running 10,000 simulations per entry...\n")
    
    # Load portfolio
    portfolio_file = Path("outputs/jan8_final_portfolio.json")
    if not portfolio_file.exists():
        print("❌ ERROR: Portfolio not found")
        return
    
    with open(portfolio_file, "r") as f:
        portfolio = json.load(f)
    
    # Load enhanced data for Bayesian analysis
    enhanced_file = Path("outputs/jan8_final_enhanced.json")
    with open(enhanced_file, "r") as f:
        enhanced_data = json.load(f)
    
    # Get primary edges for Bayesian distributions
    primary_edges = enhanced_data["primary_edges"]
    
    print("="*80)
    print("📊 BAYESIAN PROBABILITY DISTRIBUTIONS (Primary Edges)")
    print("="*80 + "\n")
    
    bayesian_results = {}
    for pick in primary_edges:
        player = pick["player"]
        stat = pick["stat"]
        empirical_rate = pick.get("empirical_rate", 0.5)
        
        bayes_dist = bayesian_probability_distribution(empirical_rate)
        bayesian_results[player] = bayes_dist
        
        print(f"{player} - {stat}")
        print(f"  Empirical Rate: {empirical_rate:.1%}")
        print(f"  Bayesian Mean:  {bayes_dist['mean']:.1%}")
        print(f"  90% Credible:   [{bayes_dist['ci_90_lower']:.1%}, {bayes_dist['ci_90_upper']:.1%}]")
        print(f"  Std Dev:        {bayes_dist['std_dev']:.3f}")
        print(f"  Beta({bayes_dist['alpha']:.1f}, {bayes_dist['beta']:.1f})")
        print()
    
    # Monte Carlo simulation for each entry
    print("="*80)
    print("🎲 MONTE CARLO SIMULATIONS (10,000 trials per entry)")
    print("="*80 + "\n")
    
    entries = portfolio["top_5_entries"]
    monte_carlo_results = []
    
    for i, entry in enumerate(entries, 1):
        entry_type = entry["entry_type"]
        legs = entry["legs"]
        picks = entry["picks"]
        payout = POWER_PAYOUTS[legs]
        
        # Run Monte Carlo
        mc_result = simulate_entry(picks, payout, n_simulations=10000)
        
        # Analyze correlation
        corr_analysis = analyze_correlation_impact(picks)
        
        # Calculate theoretical probability (for comparison)
        theoretical_prob = 1.0
        for pick in picks:
            theoretical_prob *= pick["prob_final"]
        
        print(f"{'='*80}")
        print(f"ENTRY {i}: {entry_type} ({legs} picks)")
        print(f"{'='*80}")
        
        for pick in picks:
            print(f"  • {pick['player']} ({pick['team']}): {pick['stat']} {pick['line']}+ [{pick['prob_final']:.1%}]")
        
        print()
        print(f"📈 SIMULATION RESULTS (10,000 trials):")
        print(f"   Wins:           {mc_result['wins']:,} / 10,000")
        print(f"   Win Rate:       {mc_result['win_rate']:.2%}")
        print(f"   Theoretical:    {theoretical_prob:.2%}")
        print(f"   Difference:     {(mc_result['win_rate'] - theoretical_prob)*100:+.2f}%")
        print()
        print(f"💰 EXPECTED VALUE:")
        print(f"   Avg Payout:     {mc_result['avg_payout']:.2f}x")
        print(f"   E[ROI]:         {mc_result['ev_roi']:+.1f}%")
        print(f"   Std Dev:        {mc_result['std_dev']:.2f}")
        print(f"   Sharpe Ratio:   {mc_result['sharpe_ratio']:.3f}")
        print()
        print(f"🔗 CORRELATION ANALYSIS:")
        print(f"   Risk Level:     {corr_analysis['risk_level']}")
        print(f"   Same Team:      {corr_analysis['same_team']}")
        print(f"   Same Stat:      {corr_analysis['same_stat']}")
        print(f"   Teams:          {', '.join(corr_analysis['teams'])}")
        print(f"   Stats:          {', '.join(corr_analysis['stats'])}")
        print()
        
        # Save results
        monte_carlo_results.append({
            "entry_num": i,
            "entry_type": entry_type,
            "legs": legs,
            "picks": picks,
            "monte_carlo": mc_result,
            "correlation": corr_analysis,
            "theoretical_prob": round(theoretical_prob, 4)
        })
    
    # Portfolio-level analysis
    print("="*80)
    print("📊 PORTFOLIO-LEVEL ANALYSIS")
    print("="*80)
    
    total_ev = sum(r["monte_carlo"]["ev_units"] for r in monte_carlo_results)
    avg_sharpe = statistics.mean([r["monte_carlo"]["sharpe_ratio"] for r in monte_carlo_results])
    
    print(f"\nTotal Expected Value (5 entries): {total_ev:+.2f} units")
    print(f"Average Sharpe Ratio:             {avg_sharpe:.3f}")
    print(f"Recommended Entry:                #{monte_carlo_results[0]['entry_num']}")
    print(f"Safest Entry (highest Sharpe):    #{max(monte_carlo_results, key=lambda r: r['monte_carlo']['sharpe_ratio'])['entry_num']}")
    
    # Low correlation entries
    low_corr_entries = [r for r in monte_carlo_results if r["correlation"]["risk_level"] == "LOW"]
    print(f"\nLow Correlation Entries:          {len(low_corr_entries)}/5")
    for entry in low_corr_entries:
        print(f"  • Entry #{entry['entry_num']}: {entry['entry_type']} (Win Rate: {entry['monte_carlo']['win_rate']:.1%})")
    
    # Save Monte Carlo results
    output = {
        "date": "2026-01-08",
        "simulations_per_entry": 10000,
        "bayesian_distributions": bayesian_results,
        "monte_carlo_results": monte_carlo_results,
        "portfolio_summary": {
            "total_ev_units": round(total_ev, 2),
            "avg_sharpe_ratio": round(avg_sharpe, 3),
            "low_correlation_count": len(low_corr_entries)
        }
    }
    
    output_file = Path("outputs/jan8_monte_carlo.json")
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved to: {output_file}")
    
    print("\n" + "="*80)
    print("✅ MONTE CARLO ANALYSIS COMPLETE")
    print("="*80)
    
    # Key insights
    print("\n🔑 KEY INSIGHTS:")
    print("="*80)
    
    best_entry = monte_carlo_results[0]
    print(f"\n1. HIGHEST EV: Entry #{best_entry['entry_num']} ({best_entry['entry_type']})")
    print(f"   - E[ROI]: {best_entry['monte_carlo']['ev_roi']:+.1f}%")
    print(f"   - Win Rate: {best_entry['monte_carlo']['win_rate']:.1%}")
    print(f"   - Sharpe: {best_entry['monte_carlo']['sharpe_ratio']:.3f}")
    
    safest = max(monte_carlo_results, key=lambda r: r["monte_carlo"]["sharpe_ratio"])
    print(f"\n2. BEST RISK-ADJUSTED: Entry #{safest['entry_num']} ({safest['entry_type']})")
    print(f"   - Sharpe Ratio: {safest['monte_carlo']['sharpe_ratio']:.3f}")
    print(f"   - Win Rate: {safest['monte_carlo']['win_rate']:.1%}")
    print(f"   - E[ROI]: {safest['monte_carlo']['ev_roi']:+.1f}%")
    
    print(f"\n3. CORRELATION STATUS:")
    for risk_level in ["LOW", "MEDIUM", "HIGH"]:
        count = sum(1 for r in monte_carlo_results if r["correlation"]["risk_level"] == risk_level)
        print(f"   - {risk_level}: {count}/5 entries")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    random.seed(42)  # For reproducibility
    main()
