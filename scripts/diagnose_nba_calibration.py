"""
NBA Calibration Diagnostic - Find Root Cause of 48.5% Win Rate
Analyzes lambda accuracy, calibration by market/direction, and edge thresholds
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from calibration.unified_tracker import UnifiedCalibration


def diagnose_nba_calibration(output_file: str = None):
    """
    Comprehensive NBA calibration diagnostic
    
    Analyzes:
    - Overall win rate vs expected
    - Market + Direction breakdown (PRA HIGHER vs LOWER, etc.)
    - Lambda (anchor) accuracy by market
    - Edge threshold analysis
    - Probability bucket calibration
    - Tier integrity
    """
    cal = UnifiedCalibration()
    
    # Convert picks to DataFrame
    df = pd.DataFrame([vars(p) for p in cal.picks if p.sport.lower() == "nba"])
    
    # Filter to completed picks only
    completed = df[df['hit'].notnull()].copy()
    
    if len(completed) == 0:
        print("\n" + "=" * 70)
        print("ERROR: No completed NBA picks found!")
        print("=" * 70)
        print("\nYou need to run resolve_picks() first to populate outcomes.")
        print("\nQuick fix:")
        print("  1. Run: .venv\\Scripts\\python.exe scripts\\auto_resolve_nba.py")
        print("  2. Or manually: .venv\\Scripts\\python.exe menu.py → [6] Resolve Picks → [A] Auto-fetch")
        print()
        return
    
    # Start report
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("NBA CALIBRATION DIAGNOSTIC REPORT")
    report_lines.append("=" * 70)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Total NBA picks: {len(df)}")
    report_lines.append(f"Completed picks: {len(completed)}")
    report_lines.append(f"Pending picks: {len(df) - len(completed)}")
    report_lines.append("")
    
    # =========================================================================
    # OVERALL WIN RATE
    # =========================================================================
    overall_win_rate = completed['hit'].mean()
    overall_expected = completed['probability'].mean() / 100
    overall_error = (overall_win_rate - overall_expected) * 100
    
    report_lines.append("=" * 70)
    report_lines.append("OVERALL PERFORMANCE")
    report_lines.append("=" * 70)
    report_lines.append(f"Win Rate:        {overall_win_rate:.1%} ({int(completed['hit'].sum())} / {len(completed)})")
    report_lines.append(f"Expected Rate:   {overall_expected:.1%}")
    report_lines.append(f"Calibration Error: {overall_error:+.1f}%")
    
    if overall_win_rate < 0.50:
        report_lines.append("")
        report_lines.append("⚠️  WARNING: WIN RATE BELOW 50% (losing money)")
    
    if abs(overall_error) > 5.0:
        report_lines.append("")
        report_lines.append("⚠️  WARNING: CALIBRATION ERROR > 5% (model miscalibrated)")
    
    report_lines.append("")
    
    # =========================================================================
    # BY MARKET + DIRECTION (CRITICAL FOR FINDING BROKEN MARKETS)
    # =========================================================================
    report_lines.append("=" * 70)
    report_lines.append("PERFORMANCE BY MARKET + DIRECTION")
    report_lines.append("=" * 70)
    report_lines.append(f"{'Market':<15} {'Dir':<8} {'WinRate':<10} {'N':<5} {'Expected':<10} {'Error':<10}")
    report_lines.append("-" * 70)
    
    market_issues = []
    
    for market in sorted(completed['stat'].unique()):
        for direction in ['higher', 'lower']:
            subset = completed[
                (completed['stat'].str.lower() == market.lower()) &
                (completed['direction'].str.lower() == direction)
            ]
            
            if len(subset) == 0:
                continue
            
            win_rate = subset['hit'].mean()
            n_picks = len(subset)
            avg_prob = subset['probability'].mean() / 100
            calibration_error = (win_rate - avg_prob) * 100
            
            # Flag issues
            issue_flag = ""
            if win_rate < 0.45:
                issue_flag = " ⚠️ LOSING"
                market_issues.append(f"{market} {direction}: {win_rate:.1%} (expected {avg_prob:.1%})")
            elif abs(calibration_error) > 10:
                issue_flag = " ⚠️ MISCALIBRATED"
                market_issues.append(f"{market} {direction}: Error {calibration_error:+.1f}%")
            
            report_lines.append(
                f"{market:<15} {direction:<8} {win_rate:.1%}      {n_picks:<5} "
                f"{avg_prob:.1%}      {calibration_error:+.1f}%{issue_flag}"
            )
    
    report_lines.append("")
    
    if market_issues:
        report_lines.append("IDENTIFIED ISSUES:")
        for issue in market_issues:
            report_lines.append(f"  • {issue}")
        report_lines.append("")
    
    # =========================================================================
    # LAMBDA (ANCHOR) ACCURACY - THE KEY DIAGNOSTIC
    # =========================================================================
    report_lines.append("=" * 70)
    report_lines.append("LAMBDA (ANCHOR) ACCURACY")
    report_lines.append("=" * 70)
    
    # Calculate lambda error (actual - predicted lambda)
    completed['lambda_error'] = completed['actual'] - completed['lambda_player']
    overall_lambda_error = completed['lambda_error'].mean()
    lambda_rmse = np.sqrt((completed['lambda_error'] ** 2).mean())
    
    report_lines.append(f"Mean Lambda Error:  {overall_lambda_error:+.2f}")
    report_lines.append(f"Lambda RMSE:        {lambda_rmse:.2f}")
    report_lines.append("")
    
    if abs(overall_lambda_error) > 1.0:
        report_lines.append("⚠️  WARNING: Anchors systematically BIASED by >1.0 units!")
        report_lines.append("    → Model is consistently over/under-projecting")
        report_lines.append("")
    
    report_lines.append("By Market:")
    report_lines.append(f"{'Market':<15} {'Mean Error':<12} {'RMSE':<10} {'N':<5}")
    report_lines.append("-" * 50)
    
    lambda_issues = []
    
    for market in sorted(completed['stat'].unique()):
        market_subset = completed[completed['stat'].str.lower() == market.lower()]
        if len(market_subset) < 3:
            continue
        
        market_error = market_subset['lambda_error'].mean()
        market_rmse = np.sqrt((market_subset['lambda_error'] ** 2).mean())
        n = len(market_subset)
        
        issue_flag = ""
        if abs(market_error) > 2.0:
            issue_flag = " ⚠️"
            lambda_issues.append(f"{market}: {market_error:+.2f} (adjust lambda calculation)")
        
        report_lines.append(f"{market:<15} {market_error:+.2f}         {market_rmse:.2f}       {n:<5}{issue_flag}")
    
    report_lines.append("")
    
    if lambda_issues:
        report_lines.append("LAMBDA FIXES NEEDED:")
        for issue in lambda_issues:
            report_lines.append(f"  • {issue}")
        report_lines.append("")
    
    # =========================================================================
    # EDGE THRESHOLD ANALYSIS (Find optimal edge cutoff)
    # =========================================================================
    report_lines.append("=" * 70)
    report_lines.append("EDGE THRESHOLD ANALYSIS")
    report_lines.append("=" * 70)
    report_lines.append(f"{'Min Edge':<12} {'Win Rate':<12} {'N Picks':<10} {'Profitable?'}")
    report_lines.append("-" * 50)
    
    optimal_edge = None
    
    for edge_threshold in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
        subset = completed[abs(completed['edge']) >= edge_threshold]
        
        if len(subset) < 3:
            continue
        
        win_rate = subset['hit'].mean()
        n = len(subset)
        
        # Rough profitability estimate (assuming -110 odds)
        profit_flag = "✅ YES" if win_rate > 0.524 else "❌ NO"
        
        if win_rate > 0.55 and optimal_edge is None:
            optimal_edge = edge_threshold
        
        report_lines.append(f">= {edge_threshold:.1f}       {win_rate:.1%}       {n:<10} {profit_flag}")
    
    report_lines.append("")
    
    if optimal_edge:
        report_lines.append(f"💡 RECOMMENDATION: Set minimum edge to {optimal_edge:.1f}")
        report_lines.append(f"   (This gives {completed[abs(completed['edge']) >= optimal_edge]['hit'].mean():.1%} win rate)")
        report_lines.append("")
    
    # =========================================================================
    # CALIBRATION BY PROBABILITY BUCKET
    # =========================================================================
    report_lines.append("=" * 70)
    report_lines.append("CALIBRATION BY PROBABILITY BUCKET")
    report_lines.append("=" * 70)
    report_lines.append(f"{'Bucket':<10} {'Expected':<12} {'Actual':<12} {'Error':<12} {'N':<5}")
    report_lines.append("-" * 55)
    
    for prob_bucket in [55, 60, 65, 70, 75, 80, 85]:
        bucket = completed[
            (completed['probability'] >= prob_bucket - 2.5) &
            (completed['probability'] < prob_bucket + 2.5)
        ]
        
        if len(bucket) < 3:
            continue
        
        expected = prob_bucket / 100
        actual = bucket['hit'].mean()
        error = (actual - expected) * 100
        n = len(bucket)
        
        issue_flag = " ⚠️" if abs(error) > 10 else ""
        
        report_lines.append(f"{prob_bucket}%       {expected:.1%}       {actual:.1%}       {error:+.1f}%       {n:<5}{issue_flag}")
    
    report_lines.append("")
    
    # =========================================================================
    # TIER INTEGRITY CHECK
    # =========================================================================
    report_lines.append("=" * 70)
    report_lines.append("TIER INTEGRITY CHECK")
    report_lines.append("=" * 70)
    report_lines.append(f"{'Tier':<12} {'Win Rate':<12} {'Expected':<12} {'N':<5}")
    report_lines.append("-" * 45)
    
    for tier in ['SLAM', 'STRONG', 'LEAN']:
        tier_subset = completed[completed['tier'].str.upper() == tier]
        if len(tier_subset) == 0:
            continue
        
        win_rate = tier_subset['hit'].mean()
        expected = tier_subset['probability'].mean() / 100
        n = len(tier_subset)
        
        report_lines.append(f"{tier:<12} {win_rate:.1%}       {expected:.1%}       {n:<5}")
    
    report_lines.append("")
    
    # =========================================================================
    # SUMMARY & RECOMMENDATIONS
    # =========================================================================
    report_lines.append("=" * 70)
    report_lines.append("SUMMARY & RECOMMENDATIONS")
    report_lines.append("=" * 70)
    report_lines.append("")
    
    if overall_win_rate < 0.50:
        report_lines.append("🚨 CRITICAL ISSUE: Sub-50% win rate (losing money)")
        report_lines.append("")
        report_lines.append("Immediate Actions:")
        
        if market_issues:
            report_lines.append("  1. DISABLE broken markets:")
            for issue in market_issues[:3]:
                report_lines.append(f"     → {issue}")
        
        if lambda_issues:
            report_lines.append("  2. FIX lambda calculations:")
            for issue in lambda_issues[:3]:
                report_lines.append(f"     → {issue}")
        
        if optimal_edge:
            report_lines.append(f"  3. RAISE edge threshold to {optimal_edge:.1f}")
        
        report_lines.append("")
    
    elif abs(overall_error) > 5.0:
        report_lines.append("⚠️  Calibration needs tuning (but not losing money yet)")
        report_lines.append("")
        
        if lambda_issues:
            report_lines.append("Priority: Fix lambda calculations:")
            for issue in lambda_issues[:3]:
                report_lines.append(f"  → {issue}")
            report_lines.append("")
    
    else:
        report_lines.append("✅ Model is reasonably calibrated")
        report_lines.append("")
        if optimal_edge and optimal_edge > 2.0:
            report_lines.append(f"💡 Tip: Tightening edge to {optimal_edge:.1f} could improve profitability")
            report_lines.append("")
    
    report_lines.append("=" * 70)
    report_lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 70)
    
    # Print to console
    report_text = "\n".join(report_lines)
    print(report_text)
    
    # Save to file if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"\n✅ Report saved to: {output_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnose NBA calibration issues")
    parser.add_argument("--output", "-o", help="Save report to file")
    
    args = parser.parse_args()
    
    diagnose_nba_calibration(output_file=args.output)
