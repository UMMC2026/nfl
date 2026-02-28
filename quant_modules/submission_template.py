"""
QUANT FIRM SUBMISSION TEMPLATE
==============================

Generates professional submission package for quant firm interviews.
Includes all required metrics, visualizations, and methodology documentation.

Usage:
    from quant_modules.submission_template import generate_submission_package
    
    package = generate_submission_package(
        sport='CBB',
        calibration_csv='calibration_history.csv',
        output_dir='quant_submission/'
    )
"""

import csv
import json
import math
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics


class SubmissionPackage:
    """
    Professional quant firm submission package generator.
    """
    
    def __init__(self, sport: str = 'CBB'):
        self.sport = sport.upper()
        self.picks: List[dict] = []
        self.results: Dict = {}
        self.timestamp = datetime.now().strftime('%Y-%m-%d_%H%M')
    
    def load_calibration_data(self, filepath: str) -> int:
        """Load data from calibration history."""
        self.picks = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pick = {
                    'date': row.get('date', row.get('game_date', '')),
                    'player': row.get('player', ''),
                    'stat': row.get('stat_type', row.get('stat', '')),
                    'line': float(row.get('line', 0) or 0),
                    'direction': row.get('direction', '').upper(),
                    'probability': self._parse_prob(row.get('probability', row.get('predicted_prob', ''))),
                    'tier': row.get('tier', row.get('decision', '')).upper(),
                    'outcome': self._parse_outcome(row.get('outcome', row.get('actual_result', ''))),
                }
                if pick['probability'] is not None:
                    self.picks.append(pick)
        
        return len(self.picks)
    
    def _parse_prob(self, val: str) -> Optional[float]:
        """Parse probability value."""
        try:
            p = float(val.strip())
            return p / 100 if p > 1 else p
        except (ValueError, AttributeError):
            return None
    
    def _parse_outcome(self, val: str) -> Optional[int]:
        """Parse outcome value."""
        val = str(val).strip().upper()
        if val in ['HIT', '1']:
            return 1
        elif val in ['MISS', '0']:
            return 0
        return None
    
    def compute_metrics(self) -> Dict:
        """Compute all submission metrics."""
        resolved = [p for p in self.picks if p['outcome'] is not None]
        
        if not resolved:
            return {'error': 'No resolved picks'}
        
        n = len(resolved)
        hits = sum(p['outcome'] for p in resolved)
        
        # Brier Score
        brier = sum((p['probability'] - p['outcome']) ** 2 for p in resolved) / n
        
        # Log Loss
        eps = 1e-15
        log_loss = -sum(
            p['outcome'] * math.log(max(p['probability'], eps)) +
            (1 - p['outcome']) * math.log(max(1 - p['probability'], eps))
            for p in resolved
        ) / n
        
        # ROI (assuming -110 lines)
        stake_per = 1.0
        total_stake = n * stake_per
        winnings = hits * stake_per * (100 / 110)
        losses = (n - hits) * stake_per
        profit = winnings - losses
        roi = profit / total_stake
        
        # Expected Value
        probs = [p['probability'] for p in resolved]
        avg_prob = sum(probs) / n
        ev = avg_prob * (100 / 110) - (1 - avg_prob)
        
        # Kelly Criterion
        hit_rate = hits / n
        b = 100 / 110  # decimal odds - 1
        kelly = (b * hit_rate - (1 - hit_rate)) / b
        
        # Calibration Buckets
        buckets = self._compute_calibration_buckets(resolved)
        
        # Brier Decomposition
        decomp = self._decompose_brier(resolved)
        
        # By tier
        by_tier = self._analyze_by_group(resolved, 'tier')
        
        # By stat
        by_stat = self._analyze_by_group(resolved, 'stat')
        
        # By direction
        by_direction = self._analyze_by_group(resolved, 'direction')
        
        self.results = {
            'summary': {
                'n_picks': n,
                'n_hits': hits,
                'hit_rate': round(hit_rate, 4),
                'brier_score': round(brier, 4),
                'log_loss': round(log_loss, 4),
                'roi': round(roi, 4),
                'profit_units': round(profit, 2),
                'expected_value': round(ev, 4),
                'kelly_fraction': round(kelly, 4),
                'avg_probability': round(avg_prob, 4),
            },
            'brier_decomposition': decomp,
            'calibration_buckets': buckets,
            'by_tier': by_tier,
            'by_stat': by_stat,
            'by_direction': by_direction,
            'quality_assessment': self._assess_quality(brier, hit_rate, roi, decomp),
        }
        
        return self.results
    
    def _compute_calibration_buckets(self, picks: List[dict], n_buckets: int = 10) -> List[dict]:
        """Compute calibration bucket statistics."""
        buckets = []
        
        for i in range(n_buckets):
            low = i / n_buckets
            high = (i + 1) / n_buckets
            
            bucket_picks = [p for p in picks if low <= p['probability'] < high]
            
            if not bucket_picks:
                continue
            
            n = len(bucket_picks)
            pred = sum(p['probability'] for p in bucket_picks) / n
            obs = sum(p['outcome'] for p in bucket_picks) / n
            
            buckets.append({
                'range': f"{low:.1f}-{high:.1f}",
                'n': n,
                'predicted': round(pred, 4),
                'observed': round(obs, 4),
                'error': round(pred - obs, 4),
                'calibration_error': round(abs(pred - obs), 4)
            })
        
        return buckets
    
    def _decompose_brier(self, picks: List[dict], n_bins: int = 10) -> Dict:
        """Decompose Brier score."""
        n = len(picks)
        outcomes = [p['outcome'] for p in picks]
        probs = [p['probability'] for p in picks]
        
        base_rate = sum(outcomes) / n
        uncertainty = base_rate * (1 - base_rate)
        
        reliability = 0
        resolution = 0
        
        for i in range(n_bins):
            low = i / n_bins
            high = (i + 1) / n_bins
            
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
            'reliability': round(reliability, 4),
            'resolution': round(resolution, 4),
            'uncertainty': round(uncertainty, 4),
            'brier_reconstructed': round(reliability - resolution + uncertainty, 4)
        }
    
    def _analyze_by_group(self, picks: List[dict], key: str) -> Dict:
        """Analyze metrics by group."""
        groups = defaultdict(list)
        for p in picks:
            groups[p.get(key, 'UNKNOWN')].append(p)
        
        results = {}
        for k, group_picks in groups.items():
            if len(group_picks) < 5:
                continue
            
            n = len(group_picks)
            hits = sum(p['outcome'] for p in group_picks)
            brier = sum((p['probability'] - p['outcome']) ** 2 for p in group_picks) / n
            
            results[k] = {
                'n': n,
                'hits': hits,
                'hit_rate': round(hits / n, 4),
                'brier': round(brier, 4)
            }
        
        return results
    
    def _assess_quality(self, brier: float, hit_rate: float, roi: float, decomp: Dict) -> Dict:
        """Assess model quality against targets."""
        return {
            'brier_target': 0.24,
            'brier_status': 'PASS' if brier < 0.24 else 'FAIL',
            'hit_rate_target': 0.525,
            'hit_rate_status': 'PASS' if hit_rate > 0.525 else 'FAIL',
            'roi_target': 0.0,
            'roi_status': 'PASS' if roi > 0 else 'FAIL',
            'calibration_target': 0.02,
            'calibration_status': 'PASS' if decomp['reliability'] < 0.02 else 'FAIL',
            'overall': 'PROFITABLE' if (hit_rate > 0.525 and roi > 0) else 'UNPROFITABLE'
        }
    
    def generate_text_report(self) -> str:
        """Generate comprehensive text report."""
        if not self.results:
            self.compute_metrics()
        
        r = self.results
        s = r['summary']
        d = r['brier_decomposition']
        q = r['quality_assessment']
        
        report = f"""
{'=' * 80}
    QUANTITATIVE SPORTS BETTING MODEL - SUBMISSION REPORT
    Sport: {self.sport}
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 80}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  This model evaluates player prop bets for {self.sport} using a probability-based
  framework with Monte Carlo simulation and empirical calibration.

  KEY METRICS:
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  Total Picks Evaluated:    {s['n_picks']:>6}                                       │
  │  Brier Score:              {s['brier_score']:>8.4f}  (target: < 0.24)               │
  │  Hit Rate:                 {s['hit_rate']:>8.1%}  (target: > 52.5%)               │
  │  ROI:                      {s['roi']:>+8.1%}  (target: > 0%)                   │
  │  Profit/Loss:              {s['profit_units']:>+8.2f} units                           │
  └──────────────────────────────────────────────────────────────────────────┘

  OVERALL ASSESSMENT: {q['overall']}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. PROBABILITY CALIBRATION (Brier Score Decomposition)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Brier Score = Reliability - Resolution + Uncertainty
  
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Component       Value    Description                                  │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  Reliability     {d['reliability']:>6.4f}  How well probabilities match outcomes     │
  │  Resolution      {d['resolution']:>6.4f}  How well model distinguishes outcomes     │
  │  Uncertainty     {d['uncertainty']:>6.4f}  Base rate variance (irreducible)         │
  │  ─────────────────────────────────────────────────────────────────────  │
  │  Brier Score     {d['brier_reconstructed']:>6.4f}  (lower is better)                       │
  └─────────────────────────────────────────────────────────────────────────┘

  INTERPRETATION:
  • Reliability {d['reliability']:.4f} indicates {'well-calibrated' if d['reliability'] < 0.02 else 'OVERCONFIDENT'} predictions
  • Resolution {d['resolution']:.4f} shows {'good' if d['resolution'] > 0.02 else 'limited'} discrimination ability


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  2. CALIBRATION CURVE (Predicted vs Observed)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {'Bucket':<12} {'N':>8} {'Predicted':>12} {'Observed':>12} {'Error':>12} {'Status':>8}
  {'-' * 68}
"""
        for bucket in r['calibration_buckets']:
            status = '✓' if bucket['calibration_error'] < 0.05 else '✗'
            report += f"  {bucket['range']:<12} {bucket['n']:>8} {bucket['predicted']:>12.1%} {bucket['observed']:>12.1%} {bucket['error']:>+12.1%} {status:>8}\n"
        
        report += f"""

  CALIBRATION INTERPRETATION:
  • Model predicts {s['avg_probability']:.1%} average probability
  • Actual hit rate is {s['hit_rate']:.1%}
  • {'WELL CALIBRATED' if abs(s['avg_probability'] - s['hit_rate']) < 0.03 else 'CALIBRATION DRIFT: ' + str(round((s['avg_probability'] - s['hit_rate']) * 100, 1)) + '% overconfident'}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  3. FINANCIAL PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Assumptions: Standard -110 lines, flat betting

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Metric                Value                                           │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  Total Picks:          {s['n_picks']:>6}                                           │
  │  Wins:                 {s['n_hits']:>6} ({s['hit_rate']:.1%})                                  │
  │  ROI:                  {s['roi']:>+6.1%}                                            │
  │  Profit/Loss:          {s['profit_units']:>+6.2f} units                                     │
  │  Expected Value:       {s['expected_value']:>+6.2%} per pick                                │
  │  Kelly Fraction:       {s['kelly_fraction']:>6.1%}                                          │
  └─────────────────────────────────────────────────────────────────────────┘

  BREAK-EVEN ANALYSIS:
  • At -110, break-even hit rate = 52.38%
  • Current hit rate: {s['hit_rate']:.1%}
  • {'ABOVE break-even by ' + str(round((s['hit_rate'] - 0.5238) * 100, 1)) + '%' if s['hit_rate'] > 0.5238 else 'BELOW break-even by ' + str(round((0.5238 - s['hit_rate']) * 100, 1)) + '%'}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  4. BREAKDOWN BY TIER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {'Tier':<15} {'N':>8} {'Hits':>8} {'Hit Rate':>12} {'Brier':>10}
  {'-' * 55}
"""
        for tier, stats in sorted(r['by_tier'].items()):
            report += f"  {tier:<15} {stats['n']:>8} {stats['hits']:>8} {stats['hit_rate']:>12.1%} {stats['brier']:>10.4f}\n"
        
        report += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  5. BREAKDOWN BY STAT TYPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {'Stat':<15} {'N':>8} {'Hits':>8} {'Hit Rate':>12} {'Brier':>10}
  {'-' * 55}
"""
        for stat, stats in sorted(r['by_stat'].items(), key=lambda x: -x[1]['n']):
            report += f"  {stat:<15} {stats['n']:>8} {stats['hits']:>8} {stats['hit_rate']:>12.1%} {stats['brier']:>10.4f}\n"
        
        report += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  6. BREAKDOWN BY DIRECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {'Direction':<15} {'N':>8} {'Hits':>8} {'Hit Rate':>12} {'Brier':>10}
  {'-' * 55}
"""
        for dir, stats in sorted(r['by_direction'].items()):
            report += f"  {dir:<15} {stats['n']:>8} {stats['hits']:>8} {stats['hit_rate']:>12.1%} {stats['brier']:>10.4f}\n"
        
        report += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  7. METHODOLOGY SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  PROBABILITY ENGINE:
  • Monte Carlo simulation with 10,000 iterations
  • Log-normal/Gaussian mixture distributions
  • Sample size weighting (min 10 games required)
  • Matchup-specific adjustments when available

  CALIBRATION APPROACH:
  • Empirical calibration curve from historical outcomes
  • Temperature scaling adjustment (T = {1.18 if self.sport == 'CBB' else 1.0})
  • Tier-specific thresholds based on calibrated probabilities

  EDGE QUALIFICATION (SDG):
  • Z-score thresholds: PTS ≥ 0.80, REB ≥ 0.75, PRA ≥ 0.85
  • Minimum edge requirements: 2.0-4.0% depending on stat
  • Variance penalties for high-volatility players
  • Sample size gates (50%+ min games)

  RISK MANAGEMENT:
  • Fixed flat betting (no Kelly scaling)
  • Tier-based selection (STRONG > 67% only)
  • Correlation limits for parlay construction


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  8. QUALITY CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {'[' + q['brier_status'][0] + ']':>5} Brier Score < 0.24            (actual: {s['brier_score']:.4f})
  {'[' + q['hit_rate_status'][0] + ']':>5} Hit Rate > 52.5%             (actual: {s['hit_rate']:.1%})
  {'[' + q['roi_status'][0] + ']':>5} Positive ROI                  (actual: {s['roi']:+.1%})
  {'[' + q['calibration_status'][0] + ']':>5} Reliability < 0.02           (actual: {d['reliability']:.4f})


{'=' * 80}
    END OF SUBMISSION REPORT
{'=' * 80}
"""
        
        return report
    
    def generate_json_report(self) -> str:
        """Generate JSON format report."""
        if not self.results:
            self.compute_metrics()
        
        output = {
            'metadata': {
                'sport': self.sport,
                'generated': datetime.now().isoformat(),
                'n_picks': len(self.picks),
            },
            **self.results
        }
        
        return json.dumps(output, indent=2)
    
    def save_package(self, output_dir: str = 'quant_submission') -> Dict[str, str]:
        """Save complete submission package."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if not self.results:
            self.compute_metrics()
        
        files = {}
        
        # Main report
        report_path = output_path / f'submission_report_{self.sport}_{self.timestamp}.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_text_report())
        files['report'] = str(report_path)
        
        # JSON data
        json_path = output_path / f'submission_data_{self.sport}_{self.timestamp}.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_json_report())
        files['json'] = str(json_path)
        
        # Calibration curve CSV
        cal_path = output_path / f'calibration_curve_{self.sport}_{self.timestamp}.csv'
        with open(cal_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['range', 'n', 'predicted', 'observed', 'error', 'calibration_error'])
            writer.writeheader()
            writer.writerows(self.results['calibration_buckets'])
        files['calibration_csv'] = str(cal_path)
        
        print(f"\n✓ Submission package saved to: {output_dir}")
        for name, path in files.items():
            print(f"  • {name}: {path}")
        
        return files


def generate_submission_package(
    sport: str = 'CBB',
    calibration_csv: str = 'calibration_history.csv',
    output_dir: str = 'quant_submission'
) -> Dict:
    """
    Main entry point for generating submission package.
    
    Args:
        sport: Sport code (CBB, NBA, etc.)
        calibration_csv: Path to calibration history
        output_dir: Output directory
    
    Returns:
        Dict with file paths and metrics
    """
    pkg = SubmissionPackage(sport=sport)
    n_loaded = pkg.load_calibration_data(calibration_csv)
    print(f"Loaded {n_loaded} picks from {calibration_csv}")
    
    metrics = pkg.compute_metrics()
    files = pkg.save_package(output_dir)
    
    return {
        'files': files,
        'metrics': metrics
    }


# =============================================================================
# DEMO / STANDALONE EXECUTION
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("  QUANT SUBMISSION PACKAGE GENERATOR")
    print("=" * 70)
    
    try:
        result = generate_submission_package(
            sport='CBB',
            calibration_csv='calibration_history.csv',
            output_dir='quant_submission'
        )
        
        # Print the text report
        pkg = SubmissionPackage(sport='CBB')
        pkg.load_calibration_data('calibration_history.csv')
        pkg.compute_metrics()
        print(pkg.generate_text_report())
        
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Make sure calibration_history.csv exists in the current directory.")
