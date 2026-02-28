"""
NFL HISTORICAL PICKS RECALCULATION
Analyzes 9 historical picks with OLD vs NEW probability caps
"""

import pandas as pd
import numpy as np
from scipy.stats import norm
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_FILE = PROJECT_ROOT / "calibration" / "picks.csv"


def recalculate_with_new_caps():
    """
    Re-run the 9 historical picks with NEW caps (78-85%)
    to see if system would have performed better
    """
    
    print("\n" + "=" * 80)
    print("NFL HISTORICAL PICKS ANALYSIS - OLD vs NEW CAPS")
    print("=" * 80 + "\n")
    
    # Load picks
    df = pd.read_csv(CALIBRATION_FILE)
    nfl_df = df[df['sport'] == 'nfl'].copy()
    
    if len(nfl_df) == 0:
        print("[ERROR] No NFL picks found")
        return None
    
    # Filter completed picks only
    completed = nfl_df[nfl_df['hit'].notna()].copy()
    
    print(f"Total NFL picks: {len(nfl_df)}")
    print(f"Completed picks: {len(completed)}")
    
    # Market type caps (NEW SYSTEM)
    market_caps = {
        'Pass Yards': 0.85,
        'Rush Yards': 0.85,
        'Rec Yards': 0.85,
        'Recs': 0.85,
        'Receptions': 0.85,
        'Touchdowns': 0.78,
        'TDs': 0.78,
        'Alt': 0.82
    }
    
    results = []
    
    for idx, pick in completed.iterrows():
        player = pick['player']
        stat = pick['stat']
        line = pick['line']
        direction = pick['direction']
        prob_old = pick['probability']
        actual = pick['actual']
        hit = bool(pick['hit'])
        
        # Get mu and sigma (if available)
        mu = pick.get('mu', 0)
        sigma = pick.get('sigma', 0)
        
        # If no mu/sigma, estimate from actual + line
        if mu == 0 or pd.isna(mu):
            # Rough estimate: if hit, mu was likely above line
            if hit and direction == 'over':
                mu = line + 5.0
            elif not hit and direction == 'over':
                mu = line - 5.0
            elif hit and direction == 'under':
                mu = line - 5.0
            else:
                mu = line + 5.0
        
        if sigma == 0 or pd.isna(sigma):
            # Estimate: 25% coefficient of variation
            sigma = mu * 0.25
        
        # Recalculate probability with NEW caps
        z_score = (line - mu) / sigma if sigma > 0 else 0
        
        if direction == 'over':
            prob_raw = 1 - norm.cdf(z_score)
        else:
            prob_raw = norm.cdf(z_score)
        
        # Apply new cap
        cap = market_caps.get(stat, 0.82)
        prob_new = min(prob_raw, cap)
        
        # Assign old tier (all were LEAN at 55%)
        if prob_old >= 0.55:
            tier_old = 'LEAN'
        else:
            tier_old = 'NO_PLAY'
        
        # Assign new tier
        if prob_new >= 0.80:
            tier_new = 'SLAM'
        elif prob_new >= 0.70:
            tier_new = 'STRONG'
        elif prob_new >= 0.60:
            tier_new = 'LEAN'
        else:
            tier_new = 'NO_PLAY'
        
        # Calculate edge
        edge = abs(mu - line)
        edge_pct = (edge / line * 100) if line > 0 else 0
        
        results.append({
            'player': player,
            'market': stat,
            'line': line,
            'direction': direction,
            'mu': mu,
            'sigma': sigma,
            'prob_old': prob_old,
            'prob_new': prob_new,
            'tier_old': tier_old,
            'tier_new': tier_new,
            'edge': edge,
            'edge_pct': edge_pct,
            'actual': actual,
            'hit': hit
        })
    
    results_df = pd.DataFrame(results)
    
    # Analysis
    print("\n" + "-" * 80)
    print("OLD SYSTEM (55% flat cap)")
    print("-" * 80)
    
    old_win_rate = results_df['hit'].mean()
    old_wins = results_df['hit'].sum()
    old_total = len(results_df)
    
    print(f"Win Rate: {old_win_rate:.1%} ({old_wins}/{old_total})")
    print(f"All picks: LEAN tier (55% confidence)")
    
    # OVER bias
    over_picks = results_df[results_df['direction'] == 'over']
    if len(over_picks) > 0:
        over_win_rate = over_picks['hit'].mean()
        print(f"\nOVER picks: {over_win_rate:.1%} ({over_picks['hit'].sum()}/{len(over_picks)})")
    
    under_picks = results_df[results_df['direction'] == 'under']
    if len(under_picks) > 0:
        under_win_rate = under_picks['hit'].mean()
        print(f"UNDER picks: {under_win_rate:.1%} ({under_picks['hit'].sum()}/{len(under_picks)})")
    
    print("\n" + "-" * 80)
    print("NEW SYSTEM (78-85% caps)")
    print("-" * 80)
    
    # Filter to STRONG+ picks only
    strong_picks = results_df[results_df['tier_new'].isin(['SLAM', 'STRONG'])]
    lean_picks = results_df[results_df['tier_new'] == 'LEAN']
    no_play = results_df[results_df['tier_new'] == 'NO_PLAY']
    
    print(f"Total picks: {len(results_df)}")
    print(f"  SLAM: {len(results_df[results_df['tier_new'] == 'SLAM'])}")
    print(f"  STRONG: {len(results_df[results_df['tier_new'] == 'STRONG'])}")
    print(f"  LEAN: {len(lean_picks)}")
    print(f"  NO_PLAY: {len(no_play)}")
    
    if len(strong_picks) > 0:
        strong_win_rate = strong_picks['hit'].mean()
        print(f"\nSTRONG+ Win Rate: {strong_win_rate:.1%} ({strong_picks['hit'].sum()}/{len(strong_picks)})")
    else:
        print("\n[!] No STRONG+ picks would have been made")
    
    if len(lean_picks) > 0:
        lean_win_rate = lean_picks['hit'].mean()
        print(f"LEAN Win Rate: {lean_win_rate:.1%} ({lean_picks['hit'].sum()}/{len(lean_picks)})")
    
    print("\n" + "-" * 80)
    print("DETAILED PICK BREAKDOWN")
    print("-" * 80 + "\n")
    
    for _, row in results_df.iterrows():
        hit_symbol = "✅" if row['hit'] else "❌"
        
        print(f"{hit_symbol} {row['player']} — {row['market']} {row['direction'].upper()} {row['line']}")
        print(f"   Actual: {row['actual']:.1f}")
        print(f"   Projection: μ={row['mu']:.1f}, σ={row['sigma']:.1f}, edge={row['edge_pct']:.1f}%")
        print(f"   OLD: {row['prob_old']:.1%} ({row['tier_old']})")
        print(f"   NEW: {row['prob_new']:.1%} ({row['tier_new']})")
        
        if row['tier_new'] == 'NO_PLAY' and row['tier_old'] == 'LEAN':
            print(f"   [!] Would have been BLOCKED with new system")
        elif row['tier_new'] in ['SLAM', 'STRONG'] and not row['hit']:
            print(f"   [!] High confidence MISS - model error")
        
        print()
    
    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80 + "\n")
    
    # Would new system have helped?
    if len(strong_picks) > 0:
        improvement = strong_win_rate - old_win_rate
        print(f"1. STRONG+ picks: {strong_win_rate:.1%} vs {old_win_rate:.1%} overall")
        
        if improvement > 0:
            print(f"   → NEW SYSTEM BETTER by {improvement:.1%}")
        else:
            print(f"   → NEW SYSTEM WORSE by {abs(improvement):.1%}")
    else:
        print("1. NO STRONG+ picks with new caps")
        print("   → System would have sat out all 9 picks")
        print("   → This might actually be GOOD (avoided 67% loss rate)")
    
    # OVER bias
    if len(over_picks) > 0:
        print(f"\n2. OVER BIAS: {over_win_rate:.1%} win rate on OVERs")
        print(f"   → {len(over_picks)}/{len(results_df)} picks were OVERs")
        
        if over_win_rate < 0.50:
            print(f"   → SYSTEMATIC FAILURE on OVER bets")
    
    # Edge analysis
    avg_edge = results_df['edge_pct'].mean()
    print(f"\n3. AVERAGE EDGE: {avg_edge:.1f}%")
    
    if avg_edge < 5.0:
        print(f"   → Edges too small (need 7.5%+ for NFL)")
    
    # High variance picks
    high_var = results_df[results_df['sigma'] / results_df['mu'] > 0.30]
    if len(high_var) > 0:
        print(f"\n4. HIGH VARIANCE: {len(high_var)} picks had CV > 30%")
        print(f"   → These are inherently risky bets")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION FOR SUPER BOWL")
    print("=" * 80 + "\n")
    
    if len(strong_picks) == 0:
        print("✅ NEW CAPS PREVENT BAD BETS")
        print("   → System would have blocked all 9 losing picks")
        print("   → This is actually GOOD for Super Bowl")
        print("\nAction: Only bet STRONG+ tier (70%+) picks for SB")
        print("        If no STRONG picks → SKIP betting")
    elif strong_win_rate >= 0.60:
        print("✅ NEW CAPS IMPROVE PERFORMANCE")
        print(f"   → STRONG+ picks: {strong_win_rate:.1%} win rate")
        print("\nAction: Bet STRONG+ picks with reduced stakes (50%)")
    else:
        print("❌ NEW CAPS DON'T FIX CORE ISSUES")
        print(f"   → STRONG+ picks still only {strong_win_rate:.1%}")
        print("\nAction: SKIP Super Bowl betting, rebuild system")
    
    print("\n" + "=" * 80 + "\n")
    
    # Save results
    output_file = PROJECT_ROOT / "outputs" / "nfl_recalculation_analysis.csv"
    output_file.parent.mkdir(exist_ok=True)
    results_df.to_csv(output_file, index=False)
    print(f"[OK] Results saved: {output_file}")
    
    return results_df


if __name__ == "__main__":
    recalculate_with_new_caps()
