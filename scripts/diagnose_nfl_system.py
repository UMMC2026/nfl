"""
NFL SYSTEM DIAGNOSTIC - Super Bowl LIX Readiness
Analyzes NFL calibration data and identifies system issues
"""

import pandas as pd
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_FILE = PROJECT_ROOT / "calibration" / "picks.csv"


def diagnose_nfl_system():
    """Main diagnostic function for NFL system."""
    
    print("\n" + "=" * 80)
    print("NFL SYSTEM DIAGNOSTIC - SUPER BOWL LIX READINESS")
    print("=" * 80)
    
    # Load calibration data
    try:
        df = pd.read_csv(CALIBRATION_FILE)
    except Exception as e:
        print(f"\n[ERROR] Could not load calibration data: {e}")
        return
    
    # Filter NFL picks
    nfl_df = df[df['sport'] == 'nfl'].copy()
    
    if len(nfl_df) == 0:
        print("\n[WARNING] No NFL picks found in calibration system")
        return
    
    print(f"\n[DATA SUMMARY]")
    print(f"   Total NFL picks: {len(nfl_df)}")
    
    # Completed picks only
    completed = nfl_df[nfl_df['hit'].notna()].copy()
    print(f"   Completed: {len(completed)}")
    
    if len(completed) == 0:
        print("\n[WARNING] No completed NFL picks to analyze")
        return
    
    # Overall performance
    win_rate = completed['hit'].astype(bool).mean()
    avg_prob = completed['probability'].mean()
    
    print(f"\n[OVERALL PERFORMANCE]")
    print(f"   Win Rate: {win_rate:.1%}")
    print(f"   Avg Predicted: {avg_prob:.1%}")
    print(f"   Calibration Error: {abs(win_rate - avg_prob):.1%}")
    
    if win_rate < 0.524:
        print(f"   [!] LOSING - Need 52.4% to break even")
    
    # Check probability distribution
    print(f"\n[PROBABILITY DISTRIBUTION]")
    prob_counts = completed['probability'].value_counts().sort_index()
    for prob, count in prob_counts.items():
        pct = (count / len(completed)) * 100
        print(f"   {prob:.0%}: {count} picks ({pct:.1f}%)")
    
    unique_probs = completed['probability'].nunique()
    if unique_probs <= 2:
        print(f"   [!] FLAT PROBABILITIES - Only {unique_probs} unique values")
        print(f"   [!] Model may not be differentiating between picks")
    
    # Direction bias
    print(f"\n[DIRECTION ANALYSIS]")
    for direction in ['over', 'under']:
        dir_picks = completed[completed['direction'] == direction]
        if len(dir_picks) > 0:
            dir_win_rate = dir_picks['hit'].astype(bool).mean()
            status = "[+] WINNING" if dir_win_rate >= 0.55 else ("[!] LOSING" if dir_win_rate < 0.50 else "")
            print(f"   {direction.upper():5s}: {dir_win_rate:5.1%} ({len(dir_picks):2d} picks) {status}")
    
    # Stat type analysis
    print(f"\n[STAT TYPE ANALYSIS]")
    stat_groups = completed.groupby('stat').agg({
        'hit': lambda x: x.astype(bool).mean(),
        'probability': 'count'
    }).sort_values('probability', ascending=False)
    
    for stat, row in stat_groups.iterrows():
        win_rate = row['hit']
        count = int(row['probability'])
        status = "[+] WINNING" if win_rate >= 0.55 else ("[!] LOSING" if win_rate < 0.50 else "")
        print(f"   {stat:15s} {win_rate:5.1%} ({count:2d} picks) {status}")
    
    # System health check
    print(f"\n[SYSTEM HEALTH CHECK]")
    
    issues = []
    
    # Check 1: Win rate
    if win_rate < 0.524:
        issues.append("Win rate below break-even (52.4%)")
    
    # Check 2: Flat probabilities
    if unique_probs <= 2:
        issues.append("Flat probabilities (model not differentiating)")
    
    # Check 3: Sample size
    if len(completed) < 50:
        issues.append(f"Small sample size ({len(completed)} picks)")
    
    # Check 4: Direction bias
    over_picks = completed[completed['direction'] == 'over']
    if len(over_picks) > len(completed) * 0.75:
        over_win_rate = over_picks['hit'].astype(bool).mean()
        if over_win_rate < 0.50:
            issues.append(f"OVER bias with {over_win_rate:.1%} win rate")
    
    if len(issues) == 0:
        print("   [OK] System appears healthy")
    else:
        print("   [!] ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"       {i}. {issue}")
    
    # Recommendations
    print(f"\n[RECOMMENDATIONS]")
    
    if win_rate < 0.50:
        print("   1. DO NOT BET with this model until fixed")
        print("   2. System needs recalibration")
    
    if unique_probs <= 2:
        print("   3. Fix probability calculation logic")
        print("   4. Ensure simulation engine is running properly")
        print("   5. Check for hardcoded probability values")
    
    if len(completed) < 50:
        print("   6. Collect more data before trusting results")
    
    # Check VERSION.lock
    version_lock = PROJECT_ROOT / "VERSION.lock"
    if version_lock.exists():
        with open(version_lock) as f:
            content = f.read()
            if "STATUS: FROZEN" in content:
                print("   7. System is FROZEN - unfreeze to make new predictions")
                print(f"      -> Remove or edit {version_lock}")
    
    print("\n" + "=" * 80)
    print(f"Diagnostic Complete - {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    diagnose_nfl_system()
