"""
NBA 48.5% Win Rate Diagnostic — Find What's Broken
"""
import sys
from pathlib import Path
from datetime import datetime
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))
from calibration.unified_tracker import UnifiedCalibration

def diagnose_nba_calibration():
    print("=" * 70)
    print("NBA 48.5% WIN RATE DIAGNOSTIC")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    db = UnifiedCalibration(Path("calibration/picks.csv"))
    nba_picks = [p for p in db.picks if p.sport == "nba"]
    completed = [p for p in nba_picks if p.hit is not None]
    
    if not completed:
        print("\n[!] No completed NBA picks found!")
        return
    
    print(f"\n[DATA SUMMARY]")
    print(f"   Total NBA picks: {len(nba_picks)}")
    print(f"   Completed: {len(completed)}")
    
    overall_win_rate = sum(1 for p in completed if p.hit) / len(completed)
    avg_predicted = statistics.mean([p.probability / 100.0 for p in completed])
    
    print(f"\n[OVERALL PERFORMANCE]")
    print(f"   Win Rate: {overall_win_rate:.1%}")
    print(f"   Avg Predicted: {avg_predicted:.1%}")
    print(f"   Calibration Error: {abs(overall_win_rate - avg_predicted):.1%}")
    
    if overall_win_rate < 0.50:
        print(f"   [!] WARNING: Below 50% (losing money)")
    
    # Market analysis
    print(f"\n[MARKET x DIRECTION ANALYSIS]")
    markets = {}
    for pick in completed:
        key = (pick.stat, pick.direction)
        if key not in markets:
            markets[key] = []
        markets[key].append(pick)
    
    problem_markets = []
    for (market, direction), picks in sorted(markets.items(), key=lambda x: len(x[1]), reverse=True):
        if len(picks) < 3:
            continue
        win_rate = sum(1 for p in picks if p.hit) / len(picks)
        avg_prob = statistics.mean([p.probability / 100.0 for p in picks])
        status = " [!] LOSING" if win_rate < 0.48 else (" [+] WINNING" if win_rate > 0.58 else "")
        print(f"   {market:<12} {direction:<8} {win_rate:>6.1%} ({len(picks):>2}){status}")
        if win_rate < 0.48:
            problem_markets.append((market, direction, win_rate, len(picks)))
    
    # Edge threshold analysis
    print(f"\n[EDGE THRESHOLD ANALYSIS]")
    for threshold in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
        subset = [p for p in completed if abs(p.edge) >= threshold]
        if len(subset) < 3:
            continue
        win_rate = sum(1 for p in subset if p.hit) / len(subset)
        status = " [+] PROFITABLE" if win_rate >= 0.55 else (" [!] LOSING" if win_rate < 0.50 else "")
        print(f"   Edge >= {threshold:.1f}: {win_rate:>6.1%} ({len(subset):>2} picks){status}")
    
    # Recommendations
    print(f"\n[RECOMMENDED ACTIONS]")
    if problem_markets:
        print(f"\n1. BLOCK/DOWNGRADE LOSING MARKETS:")
        for market, direction, wr, n in problem_markets[:3]:
            print(f"   • {market} {direction}: {wr:.1%} ({n} picks)")
            print(f"     → Add penalty in config/data_driven_penalties.py")

if __name__ == "__main__":
    diagnose_nba_calibration()
