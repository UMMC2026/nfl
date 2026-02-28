#!/usr/bin/env python3
"""
Confidence Interval Tracker - Phase 3 Implementation
======================================================
Tracks prediction intervals and validates calibration coverage.

Key metrics:
1. Coverage Rate - % of outcomes within predicted CI
2. Interval Width - Average CI width (narrower = better if coverage holds)
3. Sharpness - Penalizes wide intervals
4. Calibration Curve - Expected vs observed by probability bucket

Target: 90% CI should contain 90% of outcomes.

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
from scipy import stats

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class ConfidenceInterval:
    """Confidence interval for a prediction."""
    lower: float
    upper: float
    confidence_level: float  # e.g., 0.90 for 90% CI
    
    @property
    def width(self) -> float:
        return self.upper - self.lower
    
    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


@dataclass
class PickWithCI:
    """A pick with confidence interval tracking."""
    pick_id: str
    player: str
    stat: str
    line: float
    direction: str
    probability: float
    
    # Prediction stats
    mu: float
    sigma: float
    
    # Confidence intervals
    ci_90: ConfidenceInterval
    ci_80: ConfidenceInterval
    ci_50: ConfidenceInterval
    
    # Outcome (filled after resolution)
    actual_value: Optional[float] = None
    hit: Optional[bool] = None
    
    def to_dict(self) -> dict:
        return {
            "pick_id": self.pick_id,
            "player": self.player,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "probability": self.probability,
            "mu": self.mu,
            "sigma": self.sigma,
            "ci_90": {"lower": self.ci_90.lower, "upper": self.ci_90.upper},
            "ci_80": {"lower": self.ci_80.lower, "upper": self.ci_80.upper},
            "ci_50": {"lower": self.ci_50.lower, "upper": self.ci_50.upper},
            "actual_value": self.actual_value,
            "hit": self.hit,
        }


@dataclass
class CoverageMetrics:
    """Coverage metrics for confidence intervals."""
    total_picks: int
    
    # Coverage rates (should match confidence level)
    coverage_90: float  # Should be ~90%
    coverage_80: float  # Should be ~80%
    coverage_50: float  # Should be ~50%
    
    # Width metrics
    avg_width_90: float
    avg_width_80: float
    avg_width_50: float
    
    # Calibration
    calibration_error_90: float  # |coverage_90 - 0.90|
    calibration_error_80: float
    calibration_error_50: float
    
    # Overall score (lower is better)
    sharpness_score: float  # Avg width penalty
    calibration_score: float  # Avg calibration error
    
    def to_dict(self) -> dict:
        return {
            "total_picks": self.total_picks,
            "coverage_90": self.coverage_90,
            "coverage_80": self.coverage_80,
            "coverage_50": self.coverage_50,
            "avg_width_90": self.avg_width_90,
            "avg_width_80": self.avg_width_80,
            "avg_width_50": self.avg_width_50,
            "calibration_error_90": self.calibration_error_90,
            "calibration_error_80": self.calibration_error_80,
            "calibration_error_50": self.calibration_error_50,
            "sharpness_score": self.sharpness_score,
            "calibration_score": self.calibration_score,
        }


class ConfidenceTracker:
    """
    Tracks confidence intervals and validates calibration coverage.
    """
    
    def __init__(self):
        self.picks_file = PROJECT_ROOT / "calibration" / "ci_picks.json"
        self.metrics_file = PROJECT_ROOT / "calibration" / "ci_metrics.json"
        self.picks: List[PickWithCI] = []
        
    def calculate_ci(
        self, 
        mu: float, 
        sigma: float, 
        confidence_level: float = 0.90
    ) -> ConfidenceInterval:
        """
        Calculate confidence interval for a prediction.
        
        Uses normal distribution assumption. For count stats,
        this is an approximation but works well for planning.
        """
        if sigma <= 0:
            sigma = max(0.5, abs(mu) * 0.15)
        
        # Z-score for confidence level
        alpha = 1 - confidence_level
        z = stats.norm.ppf(1 - alpha / 2)
        
        lower = max(0, mu - z * sigma)
        upper = mu + z * sigma
        
        return ConfidenceInterval(
            lower=round(lower, 2),
            upper=round(upper, 2),
            confidence_level=confidence_level
        )
    
    def create_pick_with_ci(
        self,
        pick_id: str,
        player: str,
        stat: str,
        line: float,
        direction: str,
        probability: float,
        mu: float,
        sigma: float
    ) -> PickWithCI:
        """Create a pick with all confidence intervals."""
        return PickWithCI(
            pick_id=pick_id,
            player=player,
            stat=stat,
            line=line,
            direction=direction,
            probability=probability,
            mu=mu,
            sigma=sigma,
            ci_90=self.calculate_ci(mu, sigma, 0.90),
            ci_80=self.calculate_ci(mu, sigma, 0.80),
            ci_50=self.calculate_ci(mu, sigma, 0.50),
        )
    
    def add_pick(self, pick: PickWithCI):
        """Add a pick to tracking."""
        self.picks.append(pick)
    
    def resolve_pick(self, pick_id: str, actual_value: float) -> Optional[PickWithCI]:
        """Resolve a pick with actual outcome."""
        for pick in self.picks:
            if pick.pick_id == pick_id:
                pick.actual_value = actual_value
                if pick.direction == "higher":
                    pick.hit = actual_value > pick.line
                else:
                    pick.hit = actual_value < pick.line
                return pick
        return None
    
    def calculate_coverage(self, resolved_only: bool = True) -> CoverageMetrics:
        """Calculate coverage metrics for all tracked picks."""
        picks = [p for p in self.picks if p.actual_value is not None] if resolved_only else self.picks
        
        if not picks:
            return CoverageMetrics(
                total_picks=0,
                coverage_90=0, coverage_80=0, coverage_50=0,
                avg_width_90=0, avg_width_80=0, avg_width_50=0,
                calibration_error_90=0, calibration_error_80=0, calibration_error_50=0,
                sharpness_score=0, calibration_score=0,
            )
        
        # Calculate coverage
        in_90 = sum(1 for p in picks if p.ci_90.contains(p.actual_value))
        in_80 = sum(1 for p in picks if p.ci_80.contains(p.actual_value))
        in_50 = sum(1 for p in picks if p.ci_50.contains(p.actual_value))
        
        n = len(picks)
        coverage_90 = in_90 / n
        coverage_80 = in_80 / n
        coverage_50 = in_50 / n
        
        # Calculate widths
        avg_width_90 = sum(p.ci_90.width for p in picks) / n
        avg_width_80 = sum(p.ci_80.width for p in picks) / n
        avg_width_50 = sum(p.ci_50.width for p in picks) / n
        
        # Calibration errors
        cal_err_90 = abs(coverage_90 - 0.90)
        cal_err_80 = abs(coverage_80 - 0.80)
        cal_err_50 = abs(coverage_50 - 0.50)
        
        # Composite scores
        sharpness = (avg_width_90 + avg_width_80 + avg_width_50) / 3
        calibration = (cal_err_90 + cal_err_80 + cal_err_50) / 3
        
        return CoverageMetrics(
            total_picks=n,
            coverage_90=round(coverage_90, 4),
            coverage_80=round(coverage_80, 4),
            coverage_50=round(coverage_50, 4),
            avg_width_90=round(avg_width_90, 2),
            avg_width_80=round(avg_width_80, 2),
            avg_width_50=round(avg_width_50, 2),
            calibration_error_90=round(cal_err_90, 4),
            calibration_error_80=round(cal_err_80, 4),
            calibration_error_50=round(cal_err_50, 4),
            sharpness_score=round(sharpness, 2),
            calibration_score=round(calibration, 4),
        )
    
    def load_from_calibration_history(self) -> int:
        """Load picks from calibration_history.csv and calculate CIs."""
        cal_file = PROJECT_ROOT / "calibration_history.csv"
        if not cal_file.exists():
            return 0
        
        loaded = 0
        with open(cal_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Extract fields
                    player = row.get("player", "")
                    stat = row.get("stat", "")
                    line = float(row.get("line", 0) or 0)
                    direction = row.get("direction", "higher")
                    prob_str = row.get("probability", "0.5")
                    
                    try:
                        prob = float(prob_str)
                        if prob > 1:
                            prob = prob / 100
                    except:
                        prob = 0.5
                    
                    # Estimate mu/sigma from line and probability
                    # This is approximate - in production, store actual mu/sigma
                    mu = line * 1.05 if direction == "higher" else line * 0.95
                    sigma = abs(line) * 0.20  # Approximate 20% CV
                    
                    actual_str = row.get("actual_value", "")
                    actual = float(actual_str) if actual_str else None
                    
                    pick_id = row.get("pick_id", f"{player}_{stat}_{loaded}")
                    
                    pick = self.create_pick_with_ci(
                        pick_id=pick_id,
                        player=player,
                        stat=stat,
                        line=line,
                        direction=direction,
                        probability=prob,
                        mu=mu,
                        sigma=sigma
                    )
                    
                    if actual is not None:
                        pick.actual_value = actual
                        if direction == "higher":
                            pick.hit = actual > line
                        else:
                            pick.hit = actual < line
                    
                    self.picks.append(pick)
                    loaded += 1
                    
                except Exception as e:
                    continue
        
        return loaded
    
    def save_picks(self):
        """Save picks to JSON."""
        self.picks_file.parent.mkdir(parents=True, exist_ok=True)
        data = [p.to_dict() for p in self.picks]
        with open(self.picks_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"💾 Saved {len(self.picks)} picks to {self.picks_file}")
    
    def save_metrics(self, metrics: CoverageMetrics):
        """Save metrics to JSON history."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        
        history = []
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, "r") as f:
                    history = json.load(f)
            except:
                history = []
        
        entry = metrics.to_dict()
        entry["timestamp"] = datetime.now().isoformat()
        history.append(entry)
        
        # Keep last 365 entries
        history = history[-365:]
        
        with open(self.metrics_file, "w") as f:
            json.dump(history, f, indent=2)
    
    def print_report(self):
        """Print coverage report."""
        metrics = self.calculate_coverage()
        
        print("\n" + "=" * 60)
        print("📊 CONFIDENCE INTERVAL COVERAGE REPORT")
        print("=" * 60)
        print(f"Total resolved picks: {metrics.total_picks}")
        print()
        
        # Coverage table
        print("┌─────────────┬──────────┬──────────┬───────────┐")
        print("│ CI Level    │ Expected │ Actual   │ Error     │")
        print("├─────────────┼──────────┼──────────┼───────────┤")
        
        def status(expected, actual):
            diff = abs(actual - expected)
            if diff < 0.05:
                return "✅"
            elif diff < 0.10:
                return "⚠️"
            else:
                return "❌"
        
        print(f"│ 90% CI      │ 90.0%    │ {metrics.coverage_90*100:5.1f}%   │ {metrics.calibration_error_90*100:5.1f}% {status(0.90, metrics.coverage_90)} │")
        print(f"│ 80% CI      │ 80.0%    │ {metrics.coverage_80*100:5.1f}%   │ {metrics.calibration_error_80*100:5.1f}% {status(0.80, metrics.coverage_80)} │")
        print(f"│ 50% CI      │ 50.0%    │ {metrics.coverage_50*100:5.1f}%   │ {metrics.calibration_error_50*100:5.1f}% {status(0.50, metrics.coverage_50)} │")
        print("└─────────────┴──────────┴──────────┴───────────┘")
        
        print()
        print("Average Interval Widths:")
        print(f"  90% CI: {metrics.avg_width_90:.1f} units")
        print(f"  80% CI: {metrics.avg_width_80:.1f} units")
        print(f"  50% CI: {metrics.avg_width_50:.1f} units")
        
        print()
        print("─" * 40)
        print(f"Sharpness Score:    {metrics.sharpness_score:.2f} (lower = better)")
        print(f"Calibration Score:  {metrics.calibration_score:.4f} (lower = better)")
        
        # Overall assessment
        print()
        if metrics.calibration_score < 0.05:
            print("✅ EXCELLENT: CIs are well-calibrated")
        elif metrics.calibration_score < 0.10:
            print("📊 GOOD: CIs are reasonably calibrated")
        elif metrics.calibration_score < 0.15:
            print("⚠️ MODERATE: CI calibration needs attention")
        else:
            print("❌ POOR: CI calibration requires recalibration")
        
        print("=" * 60)
        
        return metrics


def main():
    """CLI for confidence tracker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Confidence Interval Tracker")
    parser.add_argument("--load", action="store_true", help="Load from calibration history")
    parser.add_argument("--save", action="store_true", help="Save metrics")
    args = parser.parse_args()
    
    tracker = ConfidenceTracker()
    
    if args.load:
        loaded = tracker.load_from_calibration_history()
        print(f"📂 Loaded {loaded} picks from calibration history")
    
    metrics = tracker.print_report()
    
    if args.save:
        tracker.save_metrics(metrics)
        print("\n✅ Metrics saved")


if __name__ == "__main__":
    main()
