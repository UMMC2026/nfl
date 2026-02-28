#!/usr/bin/env python3
"""
Rolling Backtest Engine - Phase 3 Implementation
==================================================
Simulates model performance using walk-forward validation.

Key concepts:
1. Walk-Forward: Train on N days, test on M days, roll forward
2. Out-of-Sample: Always test on data model hasn't seen
3. Stability: Track performance stability across windows

Metrics tracked:
- Hit rate per window
- Brier score per window
- ROI per window (with -110 juice assumption)
- Drawdown analysis

Version: 1.0.0
Created: 2026-02-04
"""

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import statistics

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class BacktestWindow:
    """Results for a single backtest window."""
    window_id: int
    start_date: datetime
    end_date: datetime
    
    # Core metrics
    total_picks: int
    hits: int
    misses: int
    hit_rate: float
    
    # Probabilistic metrics
    avg_predicted_prob: float
    brier_score: float
    log_loss: float
    
    # ROI (assuming -110 juice)
    units_wagered: float
    units_won: float
    roi_percent: float
    
    # Tier breakdown
    tier_breakdown: Dict[str, Dict] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "window_id": self.window_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_picks": self.total_picks,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "avg_predicted_prob": self.avg_predicted_prob,
            "brier_score": self.brier_score,
            "log_loss": self.log_loss,
            "units_wagered": self.units_wagered,
            "units_won": self.units_won,
            "roi_percent": self.roi_percent,
            "tier_breakdown": self.tier_breakdown,
        }


@dataclass
class BacktestSummary:
    """Summary of full backtest run."""
    total_windows: int
    total_picks: int
    
    # Aggregate metrics
    overall_hit_rate: float
    overall_brier: float
    overall_roi: float
    
    # Stability metrics
    hit_rate_std: float
    roi_std: float
    max_drawdown: float
    
    # Win/loss streaks
    max_win_streak: int
    max_loss_streak: int
    
    # Per-tier performance
    tier_summary: Dict[str, Dict] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "total_windows": self.total_windows,
            "total_picks": self.total_picks,
            "overall_hit_rate": self.overall_hit_rate,
            "overall_brier": self.overall_brier,
            "overall_roi": self.overall_roi,
            "hit_rate_std": self.hit_rate_std,
            "roi_std": self.roi_std,
            "max_drawdown": self.max_drawdown,
            "max_win_streak": self.max_win_streak,
            "max_loss_streak": self.max_loss_streak,
            "tier_summary": self.tier_summary,
        }


class RollingBacktester:
    """
    Performs rolling window backtest on historical picks.
    """
    
    # Betting constants
    JUICE = 0.10  # -110 odds = 10% juice
    WIN_PAYOUT = 1.0 / 1.10  # Win $0.909 per $1 at -110
    LOSS_COST = 1.0  # Lose $1 per $1 wagered
    
    def __init__(self, window_days: int = 7, min_picks_per_window: int = 10):
        self.window_days = window_days
        self.min_picks = min_picks_per_window
        self.history: List[dict] = []
        self.windows: List[BacktestWindow] = []
        self.results_file = PROJECT_ROOT / "calibration" / "backtest_results.json"
        
    def load_history(self, cal_file: Optional[Path] = None) -> int:
        """Load calibration history."""
        cal_file = cal_file or PROJECT_ROOT / "calibration_history.csv"
        
        if not cal_file.exists():
            print(f"⚠️ Calibration file not found: {cal_file}")
            return 0
        
        history = []
        with open(cal_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse date
                date_str = row.get("game_date") or row.get("date") or ""
                if not date_str.strip():
                    continue
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    try:
                        date = datetime.strptime(date_str, "%m/%d/%Y")
                    except ValueError:
                        continue
                
                # Parse outcome
                outcome_str = (row.get("outcome") or row.get("result") or "").strip().upper()
                if outcome_str not in ("HIT", "WIN", "W", "1", "TRUE", "MISS", "LOSS", "L", "0", "FALSE"):
                    continue  # Skip unresolved
                
                hit = outcome_str in ("HIT", "WIN", "W", "1", "TRUE")
                
                # Parse probability
                prob_str = row.get("probability", "0.5")
                try:
                    prob = float(prob_str)
                    if prob > 1:
                        prob = prob / 100
                except:
                    prob = 0.5
                
                # Parse tier
                tier = (row.get("tier") or "LEAN").upper()
                
                history.append({
                    "date": date,
                    "hit": hit,
                    "probability": prob,
                    "tier": tier,
                    "player": row.get("player", ""),
                    "stat": row.get("stat", ""),
                    "line": float(row.get("line", 0) or 0),
                })
        
        self.history = sorted(history, key=lambda x: x["date"])
        print(f"📊 Loaded {len(self.history)} resolved picks")
        return len(self.history)
    
    def run_backtest(self) -> List[BacktestWindow]:
        """Run rolling window backtest."""
        if not self.history:
            self.load_history()
        
        if len(self.history) < self.min_picks:
            print(f"⚠️ Need at least {self.min_picks} picks for backtest")
            return []
        
        # Find date range
        start = self.history[0]["date"]
        end = self.history[-1]["date"]
        
        windows = []
        window_id = 1
        current_start = start
        
        while current_start + timedelta(days=self.window_days) <= end:
            current_end = current_start + timedelta(days=self.window_days)
            
            # Get picks in window
            window_picks = [
                p for p in self.history
                if current_start <= p["date"] < current_end
            ]
            
            if len(window_picks) >= self.min_picks // 2:  # Allow half minimum per window
                window = self._calculate_window_metrics(
                    window_id, current_start, current_end, window_picks
                )
                windows.append(window)
                window_id += 1
            
            # Roll forward
            current_start = current_end
        
        self.windows = windows
        return windows
    
    def _calculate_window_metrics(
        self,
        window_id: int,
        start: datetime,
        end: datetime,
        picks: List[dict]
    ) -> BacktestWindow:
        """Calculate metrics for a single window."""
        n = len(picks)
        hits = sum(1 for p in picks if p["hit"])
        misses = n - hits
        hit_rate = hits / n if n > 0 else 0
        
        # Predicted probabilities
        probs = [p["probability"] for p in picks]
        avg_prob = sum(probs) / len(probs) if probs else 0.5
        
        # Brier score
        brier = sum((p["probability"] - (1 if p["hit"] else 0)) ** 2 for p in picks) / n if n > 0 else 0
        
        # Log loss (with clipping to avoid inf)
        def safe_log(p):
            return math.log(max(0.01, min(0.99, p)))
        
        log_loss = -sum(
            safe_log(p["probability"]) if p["hit"] else safe_log(1 - p["probability"])
            for p in picks
        ) / n if n > 0 else 0
        
        # ROI calculation (flat bet 1 unit per pick)
        units_wagered = n
        units_won = hits * self.WIN_PAYOUT - misses * self.LOSS_COST
        roi = (units_won / units_wagered * 100) if units_wagered > 0 else 0
        
        # Tier breakdown
        tier_breakdown = {}
        for tier in ["SLAM", "STRONG", "LEAN"]:
            tier_picks = [p for p in picks if p["tier"] == tier]
            if tier_picks:
                t_hits = sum(1 for p in tier_picks if p["hit"])
                tier_breakdown[tier] = {
                    "count": len(tier_picks),
                    "hits": t_hits,
                    "hit_rate": t_hits / len(tier_picks),
                }
        
        return BacktestWindow(
            window_id=window_id,
            start_date=start,
            end_date=end,
            total_picks=n,
            hits=hits,
            misses=misses,
            hit_rate=round(hit_rate, 4),
            avg_predicted_prob=round(avg_prob, 4),
            brier_score=round(brier, 4),
            log_loss=round(log_loss, 4),
            units_wagered=units_wagered,
            units_won=round(units_won, 2),
            roi_percent=round(roi, 2),
            tier_breakdown=tier_breakdown,
        )
    
    def calculate_summary(self) -> BacktestSummary:
        """Calculate overall backtest summary."""
        if not self.windows:
            self.run_backtest()
        
        if not self.windows:
            return BacktestSummary(
                total_windows=0, total_picks=0,
                overall_hit_rate=0, overall_brier=0, overall_roi=0,
                hit_rate_std=0, roi_std=0, max_drawdown=0,
                max_win_streak=0, max_loss_streak=0,
            )
        
        # Aggregate metrics
        total_picks = sum(w.total_picks for w in self.windows)
        total_hits = sum(w.hits for w in self.windows)
        overall_hit_rate = total_hits / total_picks if total_picks > 0 else 0
        
        # Weighted Brier
        overall_brier = sum(w.brier_score * w.total_picks for w in self.windows) / total_picks if total_picks > 0 else 0
        
        # Overall ROI
        total_wagered = sum(w.units_wagered for w in self.windows)
        total_won = sum(w.units_won for w in self.windows)
        overall_roi = (total_won / total_wagered * 100) if total_wagered > 0 else 0
        
        # Stability
        hit_rates = [w.hit_rate for w in self.windows]
        rois = [w.roi_percent for w in self.windows]
        
        hit_rate_std = statistics.stdev(hit_rates) if len(hit_rates) > 1 else 0
        roi_std = statistics.stdev(rois) if len(rois) > 1 else 0
        
        # Drawdown (cumulative ROI)
        cumulative = 0
        peak = 0
        max_dd = 0
        for w in self.windows:
            cumulative += w.units_won
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        
        # Win/loss streaks from all picks
        all_results = []
        for p in sorted(self.history, key=lambda x: x["date"]):
            all_results.append(p["hit"])
        
        max_win = max_loss = 0
        current_win = current_loss = 0
        for hit in all_results:
            if hit:
                current_win += 1
                current_loss = 0
                max_win = max(max_win, current_win)
            else:
                current_loss += 1
                current_win = 0
                max_loss = max(max_loss, current_loss)
        
        # Tier summary
        tier_summary = {}
        for tier in ["SLAM", "STRONG", "LEAN"]:
            tier_picks = [p for p in self.history if p["tier"] == tier]
            if tier_picks:
                t_hits = sum(1 for p in tier_picks if p["hit"])
                tier_summary[tier] = {
                    "total": len(tier_picks),
                    "hits": t_hits,
                    "hit_rate": round(t_hits / len(tier_picks), 4),
                }
        
        return BacktestSummary(
            total_windows=len(self.windows),
            total_picks=total_picks,
            overall_hit_rate=round(overall_hit_rate, 4),
            overall_brier=round(overall_brier, 4),
            overall_roi=round(overall_roi, 2),
            hit_rate_std=round(hit_rate_std, 4),
            roi_std=round(roi_std, 2),
            max_drawdown=round(max_dd, 2),
            max_win_streak=max_win,
            max_loss_streak=max_loss,
            tier_summary=tier_summary,
        )
    
    def save_results(self):
        """Save backtest results to JSON."""
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "window_days": self.window_days,
            "summary": self.calculate_summary().to_dict(),
            "windows": [w.to_dict() for w in self.windows],
        }
        
        with open(self.results_file, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Saved backtest results to {self.results_file}")
    
    def print_report(self):
        """Print backtest report."""
        summary = self.calculate_summary()
        
        print("\n" + "=" * 70)
        print("📈 ROLLING BACKTEST REPORT")
        print("=" * 70)
        print(f"Window Size: {self.window_days} days")
        print(f"Total Windows: {summary.total_windows}")
        print(f"Total Picks: {summary.total_picks}")
        print()
        
        # Overall metrics
        print("─" * 40)
        print("OVERALL PERFORMANCE:")
        print(f"  Hit Rate:     {summary.overall_hit_rate:.1%}")
        print(f"  Brier Score:  {summary.overall_brier:.4f}")
        print(f"  ROI:          {summary.overall_roi:+.1f}%")
        print()
        
        # Stability
        print("─" * 40)
        print("STABILITY METRICS:")
        print(f"  Hit Rate Std:  {summary.hit_rate_std:.1%}")
        print(f"  ROI Std:       {summary.roi_std:.1f}%")
        print(f"  Max Drawdown:  {summary.max_drawdown:.1f} units")
        print(f"  Max Win Streak:  {summary.max_win_streak}")
        print(f"  Max Loss Streak: {summary.max_loss_streak}")
        print()
        
        # Tier breakdown
        print("─" * 40)
        print("TIER PERFORMANCE:")
        for tier, data in summary.tier_summary.items():
            expected = {"SLAM": 0.80, "STRONG": 0.65, "LEAN": 0.55}.get(tier, 0.55)
            actual = data["hit_rate"]
            status = "✅" if abs(actual - expected) < 0.05 else "⚠️" if abs(actual - expected) < 0.10 else "❌"
            print(f"  {tier:8s} n={data['total']:3d}  hit_rate={actual:.1%}  expected={expected:.0%}  {status}")
        print()
        
        # Window-by-window (last 5)
        if self.windows:
            print("─" * 40)
            print("RECENT WINDOWS:")
            for w in self.windows[-5:]:
                print(f"  #{w.window_id:2d} [{w.start_date.strftime('%m/%d')}-{w.end_date.strftime('%m/%d')}] "
                      f"n={w.total_picks:2d} hit={w.hit_rate:.0%} ROI={w.roi_percent:+.0f}%")
        
        print()
        print("=" * 70)
        
        # Overall assessment
        if summary.overall_roi > 0:
            print("✅ PROFITABLE: Positive ROI over backtest period")
        elif summary.overall_roi > -5:
            print("📊 BREAKEVEN: Near-zero ROI, within juice margin")
        else:
            print("❌ UNPROFITABLE: Negative ROI, needs recalibration")
        
        return summary


def main():
    """CLI for rolling backtester."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Rolling Backtest Engine")
    parser.add_argument("--window", type=int, default=7, help="Window size in days")
    parser.add_argument("--min-picks", type=int, default=10, help="Minimum picks per window")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    args = parser.parse_args()
    
    backtester = RollingBacktester(
        window_days=args.window,
        min_picks_per_window=args.min_picks
    )
    backtester.load_history()
    backtester.run_backtest()
    summary = backtester.print_report()
    
    if args.save:
        backtester.save_results()


if __name__ == "__main__":
    main()
