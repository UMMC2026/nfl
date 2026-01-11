"""Monte Carlo simulation and Bayesian analysis for prop picks."""
import json
import numpy as np
from scipy import stats
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class BayesianResult:
    """Results from Bayesian analysis."""
    posterior_mean: float
    posterior_std: float
    credible_interval_95: tuple
    prior_mean: float
    likelihood_mean: float
    effective_probability: float

@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""
    mean_roi: float
    median_roi: float
    std_roi: float
    percentile_5: float
    percentile_95: float
    win_rate: float
    simulations: int

def bayesian_update(prior_mean: float, prior_std: float, 
                   empirical_hit_rate: float, sample_size: int) -> BayesianResult:
    """
    Bayesian updating of probability estimate.
    
    Prior: Beta distribution from historical data
    Likelihood: Binomial from recent games
    Posterior: Updated Beta distribution
    """
    # Convert prior (Normal) to Beta parameters
    # Using method of moments for Beta distribution
    alpha_prior = ((1 - prior_mean) / prior_std**2 - 1 / prior_mean) * prior_mean**2
    beta_prior = alpha_prior * (1 / prior_mean - 1)
    
    # Ensure valid Beta parameters
    alpha_prior = max(1, alpha_prior)
    beta_prior = max(1, beta_prior)
    
    # Likelihood from empirical data
    hits = int(empirical_hit_rate * sample_size)
    misses = sample_size - hits
    
    # Posterior Beta parameters
    alpha_post = alpha_prior + hits
    beta_post = beta_prior + misses
    
    # Posterior statistics
    posterior_mean = alpha_post / (alpha_post + beta_post)
    posterior_var = (alpha_post * beta_post) / ((alpha_post + beta_post)**2 * (alpha_post + beta_post + 1))
    posterior_std = np.sqrt(posterior_var)
    
    # 95% credible interval
    credible_low = stats.beta.ppf(0.025, alpha_post, beta_post)
    credible_high = stats.beta.ppf(0.975, alpha_post, beta_post)
    
    return BayesianResult(
        posterior_mean=posterior_mean,
        posterior_std=posterior_std,
        credible_interval_95=(credible_low, credible_high),
        prior_mean=prior_mean,
        likelihood_mean=empirical_hit_rate,
        effective_probability=posterior_mean
    )

def monte_carlo_simulation(picks: List[Dict], n_simulations: int = 10000,
                          payout_multipliers: Dict[int, float] = None) -> Dict:
    """
    Run Monte Carlo simulation for portfolio of picks.
    
    Args:
        picks: List of pick dictionaries with probability estimates
        n_simulations: Number of simulation runs
        payout_multipliers: Dict mapping num_legs -> payout multiplier
    """
    if payout_multipliers is None:
        # Default Underdog Power payouts
        payout_multipliers = {
            2: 3.0,   # 2-pick power: 3x
            3: 6.0,   # 3-pick power: 6x
            4: 10.0,  # 4-pick power: 10x
            5: 20.0,  # 5-pick power: 20x
        }
    
    results = {}
    
    # Analyze individual picks
    for pick in picks:
        p = pick.get('effective_probability', pick['probability'])
        player = pick['player']
        
        # Simulate individual pick
        outcomes = np.random.binomial(1, p, n_simulations)
        win_rate = outcomes.mean()
        
        # ROI for single pick (assuming -110 odds approximation)
        roi_per_sim = np.where(outcomes == 1, 0.91, -1.0)  # Win $0.91 per $1, or lose $1
        
        results[player] = {
            'player': player,
            'stat': pick['stat'],
            'line': pick['line'],
            'direction': pick['direction'],
            'probability': p,
            'empirical_hit_rate': pick.get('prob_method', {}).get('empirical_hit_rate', p),
            'sample_size': pick.get('prob_method', {}).get('sample_size', 10),
            'simulated_win_rate': win_rate,
            'expected_roi_single': roi_per_sim.mean(),
            'roi_std': roi_per_sim.std(),
        }
    
    # Simulate 2-pick combos
    if len(picks) >= 2:
        combo_results = []
        for i in range(len(picks)):
            for j in range(i+1, len(picks)):
                pick1, pick2 = picks[i], picks[j]
                p1 = pick1.get('effective_probability', pick1['probability'])
                p2 = pick2.get('effective_probability', pick2['probability'])
                
                # Simulate both picks (assuming independence)
                outcomes1 = np.random.binomial(1, p1, n_simulations)
                outcomes2 = np.random.binomial(1, p2, n_simulations)
                both_hit = outcomes1 * outcomes2
                
                # ROI: Win 3x on $1 bet if both hit, lose $1 if either misses
                roi = np.where(both_hit == 1, 2.0, -1.0)  # 3x payout = $2 profit
                
                combo_results.append({
                    'picks': f"{pick1['player']} + {pick2['player']}",
                    'p_both_hit': (p1 * p2),
                    'simulated_both_hit': both_hit.mean(),
                    'expected_roi': roi.mean(),
                    'median_roi': np.median(roi),
                    'roi_std': roi.std(),
                    'percentile_5': np.percentile(roi, 5),
                    'percentile_95': np.percentile(roi, 95),
                })
        
        # Sort by expected ROI
        combo_results.sort(key=lambda x: x['expected_roi'], reverse=True)
        results['best_2pick_combos'] = combo_results[:10]  # Top 10
    
    # Simulate 3-pick combos (top probability picks only)
    if len(picks) >= 3:
        sorted_picks = sorted(picks, key=lambda x: x.get('effective_probability', x['probability']), reverse=True)
        top_picks = sorted_picks[:8]  # Use top 8 for 3-pick combos
        
        combo3_results = []
        for i in range(len(top_picks)):
            for j in range(i+1, len(top_picks)):
                for k in range(j+1, len(top_picks)):
                    pick1, pick2, pick3 = top_picks[i], top_picks[j], top_picks[k]
                    p1 = pick1.get('effective_probability', pick1['probability'])
                    p2 = pick2.get('effective_probability', pick2['probability'])
                    p3 = pick3.get('effective_probability', pick3['probability'])
                    
                    # Simulate all three picks
                    outcomes1 = np.random.binomial(1, p1, n_simulations)
                    outcomes2 = np.random.binomial(1, p2, n_simulations)
                    outcomes3 = np.random.binomial(1, p3, n_simulations)
                    all_hit = outcomes1 * outcomes2 * outcomes3
                    
                    # ROI: 6x payout = $5 profit if all hit
                    roi = np.where(all_hit == 1, 5.0, -1.0)
                    
                    combo3_results.append({
                        'picks': f"{pick1['player']} + {pick2['player']} + {pick3['player']}",
                        'p_all_hit': (p1 * p2 * p3),
                        'simulated_all_hit': all_hit.mean(),
                        'expected_roi': roi.mean(),
                        'median_roi': np.median(roi),
                        'roi_std': roi.std(),
                        'percentile_5': np.percentile(roi, 5),
                        'percentile_95': np.percentile(roi, 95),
                    })
        
        combo3_results.sort(key=lambda x: x['expected_roi'], reverse=True)
        results['best_3pick_combos'] = combo3_results[:10]
    
    return results

def main():
    """Run Bayesian and Monte Carlo analysis on both 3PM and rebounds picks."""
    
    # Load scored picks (before bias calibration)
    with open('outputs/scored_picks_before_calibration.json', encoding='utf-8') as f:
        all_picks = json.load(f)
    
    # Separate by stat type
    threepm_picks = [p for p in all_picks if p['stat'] == '3pm']
    rebounds_picks = [p for p in all_picks if p['stat'] == 'rebounds']
    
    print("="*80)
    print("BAYESIAN UPDATING & MONTE CARLO SIMULATION")
    print("="*80)
    
    # Process each stat type
    for stat_type, picks in [('3PM', threepm_picks), ('REBOUNDS', rebounds_picks)]:
        if not picks:
            continue
            
        print(f"\n{'='*80}")
        print(f"{stat_type} ANALYSIS ({len(picks)} picks)")
        print(f"{'='*80}\n")
        
        # Apply Bayesian updating
        bayesian_picks = []
        for pick in picks:
            empirical_rate = pick['prob_method']['empirical_hit_rate']
            sample_size = pick['prob_method']['sample_size']
            prior_p = pick['probability']
            
            # Bayesian update with conservative prior (0.5, 0.15 std)
            bayesian = bayesian_update(
                prior_mean=0.5,
                prior_std=0.15,
                empirical_hit_rate=empirical_rate,
                sample_size=sample_size
            )
            
            pick['effective_probability'] = bayesian.effective_probability
            pick['bayesian'] = {
                'posterior_mean': bayesian.posterior_mean,
                'posterior_std': bayesian.posterior_std,
                'credible_interval_95': bayesian.credible_interval_95,
                'prior_mean': bayesian.prior_mean,
                'likelihood_mean': bayesian.likelihood_mean,
            }
            bayesian_picks.append(pick)
        
        # Sort by effective probability
        bayesian_picks.sort(key=lambda x: x['effective_probability'], reverse=True)
        
        # Display Bayesian results
        print("BAYESIAN UPDATED PROBABILITIES:")
        print("-" * 80)
        print(f"{'Player':<20} {'Stat':<12} {'Prior':>8} {'Empirical':>10} {'Posterior':>10} {'95% CI':>18}")
        print("-" * 80)
        
        for pick in bayesian_picks[:15]:  # Top 15
            b = pick['bayesian']
            ci_str = f"[{b['credible_interval_95'][0]:.2f}, {b['credible_interval_95'][1]:.2f}]"
            print(f"{pick['player']:<20} {pick['line']:>4}+ {pick['stat']:<6} "
                  f"{b['prior_mean']:>7.1%} {b['likelihood_mean']:>10.1%} "
                  f"{b['posterior_mean']:>10.1%} {ci_str:>18}")
        
        # Run Monte Carlo
        print(f"\n\nMONTE CARLO SIMULATION (10,000 runs):")
        print("-" * 80)
        
        mc_results = monte_carlo_simulation(bayesian_picks[:12], n_simulations=10000)  # Use top 12
        
        # Display individual pick results
        print("\nINDIVIDUAL PICK PERFORMANCE:")
        print("-" * 80)
        print(f"{'Player':<20} {'Stat':<12} {'P(Hit)':>8} {'Sim Win%':>10} {'E[ROI]':>10} {'ROI Std':>10}")
        print("-" * 80)
        
        for player, result in list(mc_results.items())[:12]:
            if player in ['best_2pick_combos', 'best_3pick_combos']:
                continue
            print(f"{result['player']:<20} {result['line']:>4}+ {result['stat']:<6} "
                  f"{result['probability']:>7.1%} {result['simulated_win_rate']:>10.1%} "
                  f"{result['expected_roi_single']:>9.2%} {result['roi_std']:>10.2f}")
        
        # Display 2-pick combos
        if 'best_2pick_combos' in mc_results:
            print("\n\nBEST 2-PICK POWER COMBOS (3x payout):")
            print("-" * 80)
            print(f"{'Combo':<50} {'P(Both)':>8} {'E[ROI]':>10} {'5th %ile':>10} {'95th %ile':>10}")
            print("-" * 80)
            
            for combo in mc_results['best_2pick_combos'][:8]:
                print(f"{combo['picks']:<50} {combo['p_both_hit']:>7.1%} "
                      f"{combo['expected_roi']:>9.2%} {combo['percentile_5']:>10.2f} "
                      f"{combo['percentile_95']:>10.2f}")
        
        # Display 3-pick combos
        if 'best_3pick_combos' in mc_results:
            print("\n\nBEST 3-PICK POWER COMBOS (6x payout):")
            print("-" * 80)
            print(f"{'Combo':<70} {'P(All)':>8} {'E[ROI]':>10} {'5th %ile':>10}")
            print("-" * 80)
            
            for combo in mc_results['best_3pick_combos'][:5]:
                print(f"{combo['picks']:<70} {combo['p_all_hit']:>7.1%} "
                      f"{combo['expected_roi']:>9.2%} {combo['percentile_5']:>10.2f}")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
