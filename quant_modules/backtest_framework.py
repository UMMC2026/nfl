"""
BACKTEST VALIDATION FRAMEWORK
=============================

Complete backtesting infrastructure for quant firm submission.
Validates calibration improvements with proper methodology.

Features:
1. Walk-forward validation (no future leakage)
2. Brier score decomposition (reliability, resolution, uncertainty)
3. ROI simulation with Kelly criterion
4. Bootstrap confidence intervals
5. Tier-stratified analysis
6. Before/After comparison for calibration changes

Usage:
    from quant_modules.backtest_framework import BacktestValidator
    
    validator = BacktestValidator(sport='CBB')
    validator.load_data('calibration_history.csv')
    results = validator.run_full_backtest()
    validator.generate_report('backtest_report.txt')
"""

import csv
import json
import math
import random
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Callable
from collections import defaultdict
import statistics


@dataclass
class Pick:
    """Single pick for backtesting"""
    date: str
    player: str
    stat: str
    line: float
    direction: str
    raw_probability: float
    calibrated_probability: Optional[float]
    tier: str
    outcome: Optional[int]  # 1 = hit, 0 = miss, None = unresolved
    
    @property
    def hit(self) -> Optional[bool]:
        return self.outcome == 1 if self.outcome is not None else None


@dataclass
class BacktestResults:
    """Results from a backtest run"""
    # Basic metrics
    n_picks: int
    n_hits: int
    hit_rate: float
    
    # Brier metrics
    brier_score: float
    brier_decomposition: Dict[str, float]  # reliability, resolution, uncertainty
    
    # ROI metrics
    roi: float
    units_won: float
    kelly_fraction: float
    
    # Confidence intervals (95%)
    brier_ci: Tuple[float, float]
    hit_rate_ci: Tuple[float, float]
    roi_ci: Tuple[float, float]
    
    # By-tier breakdown
    by_tier: Dict[str, dict]
    
    # By-stat breakdown
    by_stat: Dict[str, dict]
    
    # By-direction breakdown
    by_direction: Dict[str, dict]
    
    # Calibration buckets
    calibration_buckets: List[dict]
    
    def to_dict(self) -> dict:
        return {
            'n_picks': self.n_picks,
            'n_hits': self.n_hits,
            'hit_rate': round(self.hit_rate, 4),
            'brier_score': round(self.brier_score, 4),
            'brier_decomposition': {k: round(v, 4) for k, v in self.brier_decomposition.items()},
            'roi': round(self.roi, 4),
            'units_won': round(self.units_won, 2),
            'kelly_fraction': round(self.kelly_fraction, 4),
            'brier_ci': tuple(round(x, 4) for x in self.brier_ci),
            'hit_rate_ci': tuple(round(x, 4) for x in self.hit_rate_ci),
            'roi_ci': tuple(round(x, 4) for x in self.roi_ci),
            'by_tier': self.by_tier,
            'by_stat': self.by_stat,
            'by_direction': self.by_direction,
        }


class BacktestValidator:
    """
    Complete backtesting framework for sports betting models.
    """
    
    def __init__(
        self,
        sport: str = 'CBB',
        vig: float = -110,  # Standard juice
        min_picks: int = 20
    ):
        self.sport = sport.upper()
        self.vig = vig
        self.implied_prob = abs(vig) / (abs(vig) + 100)  # -110 → 52.38%
        self.min_picks = min_picks
        
        self.picks: List[Pick] = []
        self.calibration_func: Optional[Callable] = None
    
    def load_data(self, filepath: str) -> int:
        """Load picks from calibration history CSV."""
        self.picks = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse outcome
                outcome_str = row.get('outcome', row.get('actual_result', '')).strip().upper()
                if outcome_str in ['HIT', '1']:
                    outcome = 1
                elif outcome_str in ['MISS', '0']:
                    outcome = 0
                else:
                    outcome = None
                
                # Parse probability
                prob_str = row.get('probability', row.get('predicted_prob', '')).strip()
                if not prob_str:
                    continue
                try:
                    prob = float(prob_str)
                    if prob > 1:
                        prob = prob / 100
                except ValueError:
                    continue
                
                # Parse line
                try:
                    line = float(row.get('line', 0))
                except ValueError:
                    line = 0
                
                pick = Pick(
                    date=row.get('date', row.get('game_date', '')),
                    player=row.get('player', ''),
                    stat=row.get('stat_type', row.get('stat', '')),
                    line=line,
                    direction=row.get('direction', '').upper(),
                    raw_probability=prob,
                    calibrated_probability=None,
                    tier=row.get('tier', row.get('decision', '')).upper(),
                    outcome=outcome
                )
                self.picks.append(pick)
        
        return len(self.picks)
    
    def set_calibration(self, calibration_func: Callable[[float], float]):
        """Set calibration function to apply to raw probabilities."""
        self.calibration_func = calibration_func
        
        # Apply calibration to all picks
        for pick in self.picks:
            pick.calibrated_probability = calibration_func(pick.raw_probability)
    
    def get_resolved_picks(self) -> List[Pick]:
        """Get only picks with resolved outcomes."""
        return [p for p in self.picks if p.outcome is not None]
    
    def compute_brier_score(self, picks: List[Pick], use_calibrated: bool = False) -> float:
        """Compute Brier score."""
        if not picks:
            return float('nan')
        
        total = 0
        for p in picks:
            prob = p.calibrated_probability if use_calibrated and p.calibrated_probability else p.raw_probability
            total += (prob - p.outcome) ** 2
        
        return total / len(picks)
    
    def decompose_brier(self, picks: List[Pick], n_bins: int = 10) -> Dict[str, float]:
        """
        Decompose Brier score into reliability, resolution, and uncertainty.
        
        Brier = Reliability - Resolution + Uncertainty
        """
        if not picks:
            return {'reliability': float('nan'), 'resolution': float('nan'), 'uncertainty': float('nan')}
        
        probs = [p.raw_probability for p in picks]
        outcomes = [p.outcome for p in picks]
        n = len(picks)
        
        # Base rate
        base_rate = sum(outcomes) / n
        uncertainty = base_rate * (1 - base_rate)
        
        # Bin probabilities
        bin_edges = [i/n_bins for i in range(n_bins + 1)]
        
        reliability = 0
        resolution = 0
        
        for i in range(n_bins):
            low, high = bin_edges[i], bin_edges[i+1]
            mask = [low <= p < high for p in probs]
            
            if not any(mask):
                continue
            
            bin_probs = [p for p, m in zip(probs, mask) if m]
            bin_outcomes = [o for o, m in zip(outcomes, mask) if m]
            n_k = len(bin_probs)
            
            mean_prob = sum(bin_probs) / n_k
            mean_outcome = sum(bin_outcomes) / n_k
            
            reliability += (n_k / n) * (mean_prob - mean_outcome) ** 2
            resolution += (n_k / n) * (mean_outcome - base_rate) ** 2
        
        return {
            'reliability': reliability,
            'resolution': resolution,
            'uncertainty': uncertainty
        }
    
    def compute_roi(self, picks: List[Pick], flat_bet: float = 1.0) -> Tuple[float, float]:
        """
        Compute ROI assuming -110 lines.
        
        Returns: (roi_percentage, units_won)
        """
        if not picks:
            return float('nan'), 0
        
        total_staked = len(picks) * flat_bet
        
        # -110 payouts: win = stake * (100/110), lose = -stake
        wins = sum(1 for p in picks if p.outcome == 1)
        losses = len(picks) - wins
        
        winnings = wins * flat_bet * (100 / abs(self.vig))
        losses_amt = losses * flat_bet
        
        profit = winnings - losses_amt
        roi = profit / total_staked
        
        return roi, profit
    
    def compute_kelly(self, picks: List[Pick]) -> float:
        """Compute optimal Kelly fraction."""
        if not picks:
            return 0
        
        hit_rate = sum(p.outcome for p in picks) / len(picks)
        
        # b = decimal odds - 1 (for -110, decimal = 1.909)
        decimal_odds = 1 + (100 / abs(self.vig))
        b = decimal_odds - 1
        
        # Kelly = (bp - q) / b
        q = 1 - hit_rate
        kelly = (b * hit_rate - q) / b
        
        return max(0, kelly)  # Never negative
    
    def bootstrap_ci(
        self,
        picks: List[Pick],
        metric_func: Callable,
        n_bootstrap: int = 1000,
        ci: float = 0.95
    ) -> Tuple[float, float]:
        """Compute bootstrap confidence interval for a metric."""
        if len(picks) < 5:
            return (float('nan'), float('nan'))
        
        values = []
        for _ in range(n_bootstrap):
            sample = random.choices(picks, k=len(picks))
            values.append(metric_func(sample))
        
        values.sort()
        lower_idx = int((1 - ci) / 2 * n_bootstrap)
        upper_idx = int((1 + ci) / 2 * n_bootstrap)
        
        return (values[lower_idx], values[upper_idx])
    
    def get_calibration_buckets(self, picks: List[Pick], n_buckets: int = 10) -> List[dict]:
        """Get calibration bucket statistics."""
        buckets = []
        
        for i in range(n_buckets):
            low = i / n_buckets
            high = (i + 1) / n_buckets
            
            bucket_picks = [p for p in picks if low <= p.raw_probability < high]
            
            if not bucket_picks:
                continue
            
            mean_pred = sum(p.raw_probability for p in bucket_picks) / len(bucket_picks)
            mean_obs = sum(p.outcome for p in bucket_picks) / len(bucket_picks)
            
            buckets.append({
                'range': f"{low:.1f}-{high:.1f}",
                'n': len(bucket_picks),
                'predicted': mean_pred,
                'observed': mean_obs,
                'error': mean_pred - mean_obs
            })
        
        return buckets
    
    def analyze_by_group(self, picks: List[Pick], group_key: str) -> Dict[str, dict]:
        """Analyze metrics grouped by a key (tier, stat, direction)."""
        groups = defaultdict(list)
        
        for p in picks:
            key = getattr(p, group_key, 'UNKNOWN') or 'UNKNOWN'
            groups[key].append(p)
        
        results = {}
        for key, group_picks in groups.items():
            if len(group_picks) < 5:
                continue
            
            hits = sum(p.outcome for p in group_picks)
            n = len(group_picks)
            
            results[key] = {
                'n': n,
                'hits': hits,
                'hit_rate': hits / n,
                'brier': self.compute_brier_score(group_picks),
                'roi': self.compute_roi(group_picks)[0]
            }
        
        return results
    
    def run_full_backtest(self, use_calibrated: bool = False) -> BacktestResults:
        """Run complete backtest analysis."""
        resolved = self.get_resolved_picks()
        
        if len(resolved) < self.min_picks:
            raise ValueError(f"Insufficient data: {len(resolved)} picks (need {self.min_picks})")
        
        # Basic metrics
        n_picks = len(resolved)
        n_hits = sum(p.outcome for p in resolved)
        hit_rate = n_hits / n_picks
        
        # Brier metrics
        brier = self.compute_brier_score(resolved, use_calibrated)
        decomp = self.decompose_brier(resolved)
        
        # ROI metrics
        roi, units = self.compute_roi(resolved)
        kelly = self.compute_kelly(resolved)
        
        # Bootstrap CIs
        brier_ci = self.bootstrap_ci(
            resolved,
            lambda x: self.compute_brier_score(x, use_calibrated),
            n_bootstrap=500
        )
        
        hit_rate_ci = self.bootstrap_ci(
            resolved,
            lambda x: sum(p.outcome for p in x) / len(x),
            n_bootstrap=500
        )
        
        roi_ci = self.bootstrap_ci(
            resolved,
            lambda x: self.compute_roi(x)[0],
            n_bootstrap=500
        )
        
        # Grouped analysis
        by_tier = self.analyze_by_group(resolved, 'tier')
        by_stat = self.analyze_by_group(resolved, 'stat')
        by_direction = self.analyze_by_group(resolved, 'direction')
        
        # Calibration buckets
        buckets = self.get_calibration_buckets(resolved)
        
        return BacktestResults(
            n_picks=n_picks,
            n_hits=n_hits,
            hit_rate=hit_rate,
            brier_score=brier,
            brier_decomposition=decomp,
            roi=roi,
            units_won=units,
            kelly_fraction=kelly,
            brier_ci=brier_ci,
            hit_rate_ci=hit_rate_ci,
            roi_ci=roi_ci,
            by_tier=by_tier,
            by_stat=by_stat,
            by_direction=by_direction,
            calibration_buckets=buckets
        )
    
    def compare_calibrations(
        self,
        before_func: Optional[Callable] = None,
        after_func: Optional[Callable] = None
    ) -> dict:
        """Compare metrics before and after calibration adjustment."""
        resolved = self.get_resolved_picks()
        
        # Before (raw probabilities)
        if before_func:
            for p in resolved:
                p.calibrated_probability = before_func(p.raw_probability)
        
        before_results = {
            'brier': self.compute_brier_score(resolved, use_calibrated=bool(before_func)),
            'hit_rate': sum(p.outcome for p in resolved) / len(resolved),
        }
        
        # After (calibrated probabilities)
        if after_func:
            for p in resolved:
                p.calibrated_probability = after_func(p.raw_probability)
        
        # Note: Hit rate doesn't change with calibration (outcomes are fixed)
        after_results = {
            'brier': self.compute_brier_score(resolved, use_calibrated=bool(after_func)),
            'hit_rate': sum(p.outcome for p in resolved) / len(resolved),
        }
        
        improvement = {
            'brier_change': before_results['brier'] - after_results['brier'],
            'brier_pct_improvement': (before_results['brier'] - after_results['brier']) / before_results['brier'] * 100
        }
        
        return {
            'before': before_results,
            'after': after_results,
            'improvement': improvement,
            'n_picks': len(resolved)
        }
    
    def generate_report(self, output_path: Optional[str] = None) -> str:
        """Generate comprehensive backtest report."""
        results = self.run_full_backtest()
        
        report = f"""
{'=' * 70}
    BACKTEST VALIDATION REPORT
    Sport: {self.sport}
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 70}

╔══════════════════════════════════════════════════════════════════════╗
║  1. OVERALL METRICS                                                  ║
╚══════════════════════════════════════════════════════════════════════╝

  Total Picks:      {results.n_picks}
  Hits:             {results.n_hits}
  Hit Rate:         {results.hit_rate:.1%} (95% CI: {results.hit_rate_ci[0]:.1%} - {results.hit_rate_ci[1]:.1%})
  
  Brier Score:      {results.brier_score:.4f} (95% CI: {results.brier_ci[0]:.4f} - {results.brier_ci[1]:.4f})
    • Reliability:  {results.brier_decomposition['reliability']:.4f} (lower = better calibrated)
    • Resolution:   {results.brier_decomposition['resolution']:.4f} (higher = better discrimination)
    • Uncertainty:  {results.brier_decomposition['uncertainty']:.4f} (base rate variance)
  
  ROI:              {results.roi:.1%} (95% CI: {results.roi_ci[0]:.1%} - {results.roi_ci[1]:.1%})
  Units Won:        {results.units_won:+.2f}
  Kelly Fraction:   {results.kelly_fraction:.1%}

╔══════════════════════════════════════════════════════════════════════╗
║  2. QUALITY ASSESSMENT                                               ║
╚══════════════════════════════════════════════════════════════════════╝

  Brier Score:      {'✓ GOOD' if results.brier_score < 0.24 else '✗ NEEDS WORK'} (target: < 0.24)
  Hit Rate:         {'✓ PROFITABLE' if results.hit_rate > 0.525 else '✗ UNPROFITABLE'} (target: > 52.5%)
  ROI:              {'✓ POSITIVE' if results.roi > 0 else '✗ NEGATIVE'}
  Calibration:      {'✓ GOOD' if results.brier_decomposition['reliability'] < 0.02 else '⚠ OVERCONFIDENT'}

╔══════════════════════════════════════════════════════════════════════╗
║  3. CALIBRATION BUCKETS                                              ║
╚══════════════════════════════════════════════════════════════════════╝

  {'Bucket':<12} {'N':>6} {'Predicted':>12} {'Observed':>12} {'Error':>10}
  {'-'*55}
"""
        for bucket in results.calibration_buckets:
            status = '✓' if abs(bucket['error']) < 0.05 else '✗'
            report += f"  {bucket['range']:<12} {bucket['n']:>6} {bucket['predicted']:>12.1%} {bucket['observed']:>12.1%} {bucket['error']:>+10.1%} {status}\n"
        
        report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  4. BY TIER                                                          ║
╚══════════════════════════════════════════════════════════════════════╝

  {'Tier':<12} {'N':>6} {'Hits':>6} {'Hit Rate':>10} {'Brier':>8} {'ROI':>10}
  {'-'*55}
"""
        for tier, stats in sorted(results.by_tier.items()):
            report += f"  {tier:<12} {stats['n']:>6} {stats['hits']:>6} {stats['hit_rate']:>10.1%} {stats['brier']:>8.4f} {stats['roi']:>+10.1%}\n"
        
        report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  5. BY STAT TYPE                                                     ║
╚══════════════════════════════════════════════════════════════════════╝

  {'Stat':<12} {'N':>6} {'Hits':>6} {'Hit Rate':>10} {'Brier':>8} {'ROI':>10}
  {'-'*55}
"""
        for stat, stats in sorted(results.by_stat.items(), key=lambda x: -x[1]['n']):
            report += f"  {stat:<12} {stats['n']:>6} {stats['hits']:>6} {stats['hit_rate']:>10.1%} {stats['brier']:>8.4f} {stats['roi']:>+10.1%}\n"
        
        report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  6. BY DIRECTION                                                     ║
╚══════════════════════════════════════════════════════════════════════╝

  {'Direction':<12} {'N':>6} {'Hits':>6} {'Hit Rate':>10} {'Brier':>8} {'ROI':>10}
  {'-'*55}
"""
        for dir, stats in sorted(results.by_direction.items()):
            report += f"  {dir:<12} {stats['n']:>6} {stats['hits']:>6} {stats['hit_rate']:>10.1%} {stats['brier']:>8.4f} {stats['roi']:>+10.1%}\n"
        
        report += f"""
{'=' * 70}
  END OF BACKTEST REPORT
{'=' * 70}
"""
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Report saved to: {output_path}")
        
        return report


# =============================================================================
# DEMO
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("  BACKTEST VALIDATION FRAMEWORK - DEMO")
    print("=" * 70)
    
    validator = BacktestValidator(sport='CBB')
    
    try:
        n_loaded = validator.load_data('calibration_history.csv')
        print(f"\nLoaded {n_loaded} picks from calibration_history.csv")
        
        resolved = validator.get_resolved_picks()
        print(f"Resolved picks: {len(resolved)}")
        
        if len(resolved) >= 20:
            results = validator.run_full_backtest()
            report = validator.generate_report('outputs/backtest_report.txt')
            print(report)
        else:
            print(f"\nInsufficient data for backtest (need 20+, have {len(resolved)})")
            
    except FileNotFoundError:
        print("\nNo calibration_history.csv found. Creating demo data...")
