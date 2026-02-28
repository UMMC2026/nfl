"""
Walk-Forward Validation Framework for Quant Interview Readiness
================================================================

This module implements proper out-of-sample testing to answer:
"What's your out-of-sample Brier score?"

Key Features:
1. Time-series cross-validation (no future leakage)
2. Brier score decomposition (reliability, resolution, uncertainty)
3. Expanding window and rolling window strategies
4. Proper train/test splits with calendar-based gaps

For quant interviews, this demonstrates:
- Rigorous backtesting methodology
- Understanding of overfitting risks
- Proper performance measurement
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable
from collections import defaultdict
from datetime import datetime, timedelta
import json
import os


@dataclass
class ValidationFold:
    """Single fold in walk-forward validation"""
    fold_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_size: int
    test_size: int
    
    # Results
    brier_score: Optional[float] = None
    reliability: Optional[float] = None
    resolution: Optional[float] = None
    uncertainty: Optional[float] = None
    n_correct: int = 0
    n_total: int = 0


@dataclass
class ValidationResult:
    """Complete walk-forward validation results"""
    strategy: str  # 'expanding' or 'rolling'
    n_folds: int
    total_test_samples: int
    
    # Aggregate metrics
    oos_brier_score: float
    oos_brier_std: float
    oos_accuracy: float
    
    # Decomposition (averaged across folds)
    avg_reliability: float
    avg_resolution: float
    avg_uncertainty: float
    
    # Per-fold details
    folds: List[ValidationFold] = field(default_factory=list)
    
    # By tier/stat breakdowns
    by_tier: Dict[str, float] = field(default_factory=dict)
    by_stat: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            'strategy': self.strategy,
            'n_folds': self.n_folds,
            'total_test_samples': self.total_test_samples,
            'oos_brier_score': round(self.oos_brier_score, 4),
            'oos_brier_std': round(self.oos_brier_std, 4),
            'oos_accuracy': round(self.oos_accuracy, 4),
            'avg_reliability': round(self.avg_reliability, 4),
            'avg_resolution': round(self.avg_resolution, 4),
            'avg_uncertainty': round(self.avg_uncertainty, 4),
            'by_tier': self.by_tier,
            'by_stat': self.by_stat,
            'fold_brier_scores': [f.brier_score for f in self.folds if f.brier_score is not None]
        }


class WalkForwardValidator:
    """
    Walk-forward validation for sports betting models.
    
    Implements proper time-series cross-validation:
    - Training window → Gap period → Test window
    - No future information leakage
    - Proper Brier score decomposition
    """
    
    def __init__(
        self,
        min_train_samples: int = 30,
        test_window_days: int = 7,
        gap_days: int = 0,  # Embargo period to prevent leakage
        strategy: str = 'expanding'  # 'expanding' or 'rolling'
    ):
        self.min_train_samples = min_train_samples
        self.test_window_days = test_window_days
        self.gap_days = gap_days
        self.strategy = strategy
        
    def compute_brier_score(
        self, 
        probabilities: List[float], 
        outcomes: List[int]
    ) -> float:
        """
        Compute Brier score: mean squared error of probability forecasts.
        
        Lower is better: 0 = perfect, 0.25 = random, 0.5 = always wrong
        """
        if len(probabilities) == 0:
            return float('nan')
        return np.mean([(p - o) ** 2 for p, o in zip(probabilities, outcomes)])
    
    def decompose_brier_score(
        self,
        probabilities: List[float],
        outcomes: List[int],
        n_bins: int = 10
    ) -> Tuple[float, float, float]:
        """
        Decompose Brier score into components:
        
        Brier = Reliability - Resolution + Uncertainty
        
        - Reliability: Calibration error (lower is better)
        - Resolution: How well forecasts discriminate (higher is better)
        - Uncertainty: Base rate variance (fixed for given outcomes)
        
        Returns: (reliability, resolution, uncertainty)
        """
        if len(probabilities) == 0:
            return float('nan'), float('nan'), float('nan')
            
        probs = np.array(probabilities)
        outs = np.array(outcomes)
        n = len(probs)
        
        # Base rate (climatological probability)
        base_rate = np.mean(outs)
        uncertainty = base_rate * (1 - base_rate)
        
        # Bin probabilities for reliability/resolution calculation
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(probs, bin_edges[1:-1])
        
        reliability = 0.0
        resolution = 0.0
        
        for i in range(n_bins):
            mask = (bin_indices == i)
            if not np.any(mask):
                continue
                
            n_k = np.sum(mask)
            p_k = np.mean(probs[mask])  # Mean forecast in bin
            o_k = np.mean(outs[mask])   # Observed frequency in bin
            
            # Reliability: squared difference between forecast and observed
            reliability += (n_k / n) * (p_k - o_k) ** 2
            
            # Resolution: squared difference between observed and base rate
            resolution += (n_k / n) * (o_k - base_rate) ** 2
            
        return reliability, resolution, uncertainty
    
    def create_folds(
        self,
        picks: List[dict],
        date_field: str = 'date'
    ) -> List[Tuple[List[dict], List[dict], ValidationFold]]:
        """
        Create walk-forward folds from pick history.
        
        Returns: List of (train_picks, test_picks, fold_metadata)
        """
        # Sort by date
        sorted_picks = sorted(
            picks, 
            key=lambda p: self._parse_date(p.get(date_field, ''))
        )
        
        if len(sorted_picks) < self.min_train_samples + 5:
            return []
            
        # Get date range
        dates = [self._parse_date(p.get(date_field, '')) for p in sorted_picks]
        min_date = min(d for d in dates if d is not None)
        max_date = max(d for d in dates if d is not None)
        
        if min_date is None or max_date is None:
            return []
            
        folds = []
        fold_id = 0
        
        # Start after we have minimum training samples
        current_date = min_date + timedelta(days=30)  # Allow 30 days for initial training
        
        while current_date + timedelta(days=self.test_window_days) <= max_date:
            # Training window
            if self.strategy == 'expanding':
                train_start = min_date
            else:  # rolling
                train_start = current_date - timedelta(days=60)  # 60-day rolling window
                
            train_end = current_date - timedelta(days=self.gap_days)
            
            # Test window
            test_start = current_date
            test_end = current_date + timedelta(days=self.test_window_days)
            
            # Get picks for each window
            train_picks = [
                p for p in sorted_picks
                if train_start <= self._parse_date(p.get(date_field, '')) <= train_end
            ]
            
            test_picks = [
                p for p in sorted_picks
                if test_start <= self._parse_date(p.get(date_field, '')) < test_end
            ]
            
            if len(train_picks) >= self.min_train_samples and len(test_picks) >= 5:
                fold = ValidationFold(
                    fold_id=fold_id,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_size=len(train_picks),
                    test_size=len(test_picks)
                )
                folds.append((train_picks, test_picks, fold))
                fold_id += 1
                
            # Move to next test window
            current_date += timedelta(days=self.test_window_days)
            
        return folds
    
    def validate(
        self,
        picks: List[dict],
        probability_field: str = 'probability',
        outcome_field: str = 'outcome',  # 1 = hit, 0 = miss
        date_field: str = 'date',
        tier_field: str = 'tier',
        stat_field: str = 'stat_type'
    ) -> ValidationResult:
        """
        Run walk-forward validation on historical picks.
        
        Returns comprehensive validation results including:
        - Out-of-sample Brier score with uncertainty
        - Brier decomposition (reliability, resolution, uncertainty)
        - By-tier and by-stat breakdowns
        """
        folds = self.create_folds(picks, date_field)
        
        if len(folds) == 0:
            return ValidationResult(
                strategy=self.strategy,
                n_folds=0,
                total_test_samples=0,
                oos_brier_score=float('nan'),
                oos_brier_std=float('nan'),
                oos_accuracy=float('nan'),
                avg_reliability=float('nan'),
                avg_resolution=float('nan'),
                avg_uncertainty=float('nan')
            )
        
        all_test_probs = []
        all_test_outcomes = []
        fold_briers = []
        fold_reliabilities = []
        fold_resolutions = []
        fold_uncertainties = []
        
        # By-tier and by-stat tracking
        tier_probs = defaultdict(list)
        tier_outcomes = defaultdict(list)
        stat_probs = defaultdict(list)
        stat_outcomes = defaultdict(list)
        
        completed_folds = []
        
        for train_picks, test_picks, fold in folds:
            # Extract test probabilities and outcomes
            test_data = [
                (p.get(probability_field), p.get(outcome_field))
                for p in test_picks
                if p.get(probability_field) is not None and p.get(outcome_field) is not None
            ]
            
            if len(test_data) < 5:
                continue
                
            probs, outcomes = zip(*test_data)
            probs = [float(p) for p in probs]
            outcomes = [int(o) for o in outcomes]
            
            # Compute fold metrics
            fold.brier_score = self.compute_brier_score(probs, outcomes)
            fold.reliability, fold.resolution, fold.uncertainty = self.decompose_brier_score(probs, outcomes)
            fold.n_correct = sum(1 for p, o in zip(probs, outcomes) if (p >= 0.5) == o)
            fold.n_total = len(probs)
            
            fold_briers.append(fold.brier_score)
            if not np.isnan(fold.reliability):
                fold_reliabilities.append(fold.reliability)
                fold_resolutions.append(fold.resolution)
                fold_uncertainties.append(fold.uncertainty)
            
            all_test_probs.extend(probs)
            all_test_outcomes.extend(outcomes)
            
            # Track by tier and stat
            for p in test_picks:
                prob = p.get(probability_field)
                outcome = p.get(outcome_field)
                if prob is None or outcome is None:
                    continue
                    
                tier = p.get(tier_field, 'UNKNOWN')
                stat = p.get(stat_field, 'UNKNOWN')
                
                tier_probs[tier].append(float(prob))
                tier_outcomes[tier].append(int(outcome))
                stat_probs[stat].append(float(prob))
                stat_outcomes[stat].append(int(outcome))
                
            completed_folds.append(fold)
        
        # Aggregate metrics
        if len(all_test_probs) == 0:
            return ValidationResult(
                strategy=self.strategy,
                n_folds=0,
                total_test_samples=0,
                oos_brier_score=float('nan'),
                oos_brier_std=float('nan'),
                oos_accuracy=float('nan'),
                avg_reliability=float('nan'),
                avg_resolution=float('nan'),
                avg_uncertainty=float('nan')
            )
        
        overall_brier = self.compute_brier_score(all_test_probs, all_test_outcomes)
        overall_accuracy = sum(
            1 for p, o in zip(all_test_probs, all_test_outcomes) 
            if (p >= 0.5) == o
        ) / len(all_test_probs)
        
        # By-tier Brier scores
        by_tier = {}
        for tier, probs in tier_probs.items():
            if len(probs) >= 10:
                by_tier[tier] = round(self.compute_brier_score(probs, tier_outcomes[tier]), 4)
                
        # By-stat Brier scores
        by_stat = {}
        for stat, probs in stat_probs.items():
            if len(probs) >= 10:
                by_stat[stat] = round(self.compute_brier_score(probs, stat_outcomes[stat]), 4)
        
        return ValidationResult(
            strategy=self.strategy,
            n_folds=len(completed_folds),
            total_test_samples=len(all_test_probs),
            oos_brier_score=overall_brier,
            oos_brier_std=np.std(fold_briers) if len(fold_briers) > 1 else 0.0,
            oos_accuracy=overall_accuracy,
            avg_reliability=np.mean(fold_reliabilities) if fold_reliabilities else float('nan'),
            avg_resolution=np.mean(fold_resolutions) if fold_resolutions else float('nan'),
            avg_uncertainty=np.mean(fold_uncertainties) if fold_uncertainties else float('nan'),
            folds=completed_folds,
            by_tier=by_tier,
            by_stat=by_stat
        )
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats"""
        if not date_str:
            return None
            
        for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%Y%m%d']:
            try:
                return datetime.strptime(str(date_str).split()[0], fmt)
            except ValueError:
                continue
        return None


class PenaltyCoefficientValidator:
    """
    Validate that penalty coefficients aren't overfitted.
    
    Key methodology for quant interview:
    1. Bootstrap confidence intervals
    2. Cross-validated performance
    3. Sensitivity analysis
    """
    
    def __init__(self, n_bootstrap: int = 1000):
        self.n_bootstrap = n_bootstrap
        
    def bootstrap_penalty_validation(
        self,
        picks: List[dict],
        penalty_coefficients: Dict[str, float],
        probability_field: str = 'probability',
        outcome_field: str = 'outcome',
        penalty_fields: Optional[Dict[str, str]] = None
    ) -> Dict[str, dict]:
        """
        Bootstrap validation of penalty coefficients.
        
        Tests whether each penalty actually improves calibration with statistical significance.
        
        Returns: Dict[penalty_name -> {improvement, ci_lower, ci_upper, p_value, significant}]
        """
        if penalty_fields is None:
            penalty_fields = {
                'sdg_penalty': 'sdg_multiplier',
                'market_penalty': 'market_multiplier',
                'opponent_penalty': 'opponent_multiplier'
            }
            
        results = {}
        
        for penalty_name, field_name in penalty_fields.items():
            # Get picks where penalty was applied
            penalized = [
                p for p in picks 
                if p.get(field_name, 1.0) != 1.0 and
                p.get(probability_field) is not None and
                p.get(outcome_field) is not None
            ]
            
            if len(penalized) < 20:
                results[penalty_name] = {
                    'n_samples': len(penalized),
                    'significant': False,
                    'note': 'Insufficient samples (need 20+)'
                }
                continue
            
            # Compare Brier with and without penalty
            improvements = []
            
            for _ in range(self.n_bootstrap):
                # Bootstrap sample
                indices = np.random.choice(len(penalized), len(penalized), replace=True)
                sample = [penalized[i] for i in indices]
                
                # Brier with penalty (as-is)
                probs_with = [p.get(probability_field) for p in sample]
                outcomes = [p.get(outcome_field) for p in sample]
                brier_with = np.mean([(p - o) ** 2 for p, o in zip(probs_with, outcomes)])
                
                # Brier without penalty (reconstruct)
                probs_without = []
                for p in sample:
                    original_prob = p.get(probability_field)
                    multiplier = p.get(field_name, 1.0)
                    if multiplier != 0:
                        probs_without.append(min(original_prob / multiplier, 0.95))
                    else:
                        probs_without.append(original_prob)
                        
                brier_without = np.mean([(p - o) ** 2 for p, o in zip(probs_without, outcomes)])
                
                improvements.append(brier_without - brier_with)
            
            improvements = np.array(improvements)
            mean_improvement = np.mean(improvements)
            ci_lower, ci_upper = np.percentile(improvements, [2.5, 97.5])
            
            # p-value: proportion of bootstraps showing no improvement
            p_value = np.mean(improvements <= 0)
            
            results[penalty_name] = {
                'n_samples': len(penalized),
                'mean_improvement': round(mean_improvement, 5),
                'ci_95': (round(ci_lower, 5), round(ci_upper, 5)),
                'p_value': round(p_value, 4),
                'significant': ci_lower > 0,  # 95% CI doesn't include 0
                'verdict': 'VALIDATED' if ci_lower > 0 else 'NOT SIGNIFICANT'
            }
            
        return results
    
    def sensitivity_analysis(
        self,
        picks: List[dict],
        penalty_name: str,
        current_value: float,
        field_name: str,
        probability_field: str = 'probability',
        outcome_field: str = 'outcome',
        test_range: Optional[Tuple[float, float]] = None
    ) -> Dict[str, float]:
        """
        Sensitivity analysis for a penalty coefficient.
        
        Tests model performance across a range of coefficient values
        to ensure we're not at an overfitted local optimum.
        
        Returns: {coefficient_value -> Brier score}
        """
        if test_range is None:
            # Test ±50% around current value
            test_range = (current_value * 0.5, current_value * 1.5)
            
        test_values = np.linspace(test_range[0], test_range[1], 11)
        
        relevant_picks = [
            p for p in picks
            if p.get(field_name, 1.0) != 1.0 and
            p.get(probability_field) is not None and
            p.get(outcome_field) is not None
        ]
        
        if len(relevant_picks) < 10:
            return {str(current_value): float('nan')}
            
        results = {}
        
        for test_value in test_values:
            adjusted_probs = []
            outcomes = []
            
            for p in relevant_picks:
                original_prob = p.get(probability_field)
                original_mult = p.get(field_name, 1.0)
                
                if original_mult != 0:
                    base_prob = original_prob / original_mult
                else:
                    base_prob = original_prob
                    
                new_prob = min(base_prob * (test_value / current_value), 0.95)
                adjusted_probs.append(new_prob)
                outcomes.append(p.get(outcome_field))
                
            brier = np.mean([(p - o) ** 2 for p, o in zip(adjusted_probs, outcomes)])
            results[round(test_value, 3)] = round(brier, 5)
            
        return results


def load_calibration_data(
    calibration_path: str = 'calibration_history.csv'
) -> List[dict]:
    """Load calibration history and prepare for validation"""
    import csv
    
    picks = []
    
    try:
        with open(calibration_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only include resolved picks with probabilities
                outcome = row.get('outcome', '').strip().upper()
                prob = row.get('probability', '')
                
                if outcome not in ['HIT', 'MISS', '1', '0']:
                    continue
                if not prob:
                    continue
                    
                try:
                    prob_float = float(prob)
                except ValueError:
                    continue
                    
                pick = {
                    'date': row.get('date', row.get('game_date', '')),
                    'probability': prob_float,
                    'outcome': 1 if outcome in ['HIT', '1'] else 0,
                    'tier': row.get('tier', 'UNKNOWN'),
                    'stat_type': row.get('stat_type', row.get('stat', 'UNKNOWN')),
                    'player': row.get('player', ''),
                    'sport': row.get('sport', 'NBA')
                }
                picks.append(pick)
                
    except FileNotFoundError:
        print(f"[!] Calibration file not found: {calibration_path}")
        
    return picks


def run_full_validation(
    calibration_path: str = 'calibration_history.csv',
    output_path: Optional[str] = None
) -> ValidationResult:
    """
    Run complete walk-forward validation and output results.
    
    This is what you show in a quant interview when asked:
    "What's your out-of-sample Brier score?"
    """
    print("=" * 70)
    print("  WALK-FORWARD VALIDATION - QUANT INTERVIEW METRICS")
    print("=" * 70)
    
    picks = load_calibration_data(calibration_path)
    
    print(f"\n[1] LOADED DATA")
    print(f"    Total picks with probability + outcome: {len(picks)}")
    
    if len(picks) < 50:
        print(f"\n[!] INSUFFICIENT DATA")
        print(f"    Need 50+ resolved picks with probabilities for meaningful validation")
        print(f"    Currently have: {len(picks)}")
        print(f"\n    RECOMMENDATION: Record probabilities at pick creation time")
        return ValidationResult(
            strategy='expanding',
            n_folds=0,
            total_test_samples=len(picks),
            oos_brier_score=float('nan'),
            oos_brier_std=float('nan'),
            oos_accuracy=float('nan'),
            avg_reliability=float('nan'),
            avg_resolution=float('nan'),
            avg_uncertainty=float('nan')
        )
    
    # Run expanding window validation
    print(f"\n[2] RUNNING EXPANDING WINDOW VALIDATION")
    print(f"    Strategy: Start small, grow training window")
    print(f"    Gap: 0 days (no embargo)")
    print(f"    Test window: 7 days")
    
    validator = WalkForwardValidator(
        min_train_samples=30,
        test_window_days=7,
        gap_days=0,
        strategy='expanding'
    )
    
    result = validator.validate(picks)
    
    # Output results
    print(f"\n[3] RESULTS")
    print("-" * 50)
    print(f"    Folds completed: {result.n_folds}")
    print(f"    Total test samples: {result.total_test_samples}")
    print()
    print(f"    OUT-OF-SAMPLE BRIER SCORE: {result.oos_brier_score:.4f}")
    print(f"    (std across folds: ±{result.oos_brier_std:.4f})")
    print()
    
    # Interpret Brier score
    if not np.isnan(result.oos_brier_score):
        if result.oos_brier_score < 0.20:
            quality = "EXCELLENT"
        elif result.oos_brier_score < 0.22:
            quality = "GOOD"
        elif result.oos_brier_score < 0.25:
            quality = "FAIR"
        else:
            quality = "NEEDS IMPROVEMENT"
        print(f"    Interpretation: {quality}")
        print(f"    (Reference: 0.25 = random, <0.22 = good, <0.20 = excellent)")
    
    print(f"\n[4] BRIER DECOMPOSITION")
    print("-" * 50)
    print(f"    Reliability (calibration error): {result.avg_reliability:.4f}")
    print(f"    Resolution (discriminative power): {result.avg_resolution:.4f}")
    print(f"    Uncertainty (base rate variance): {result.avg_uncertainty:.4f}")
    print()
    print(f"    → Lower reliability = better calibrated")
    print(f"    → Higher resolution = better at distinguishing outcomes")
    
    if result.by_tier:
        print(f"\n[5] BRIER BY TIER")
        print("-" * 50)
        for tier, brier in sorted(result.by_tier.items(), key=lambda x: x[1]):
            print(f"    {tier}: {brier:.4f}")
            
    if result.by_stat:
        print(f"\n[6] BRIER BY STAT TYPE")
        print("-" * 50)
        for stat, brier in sorted(result.by_stat.items(), key=lambda x: x[1])[:10]:
            print(f"    {stat}: {brier:.4f}")
    
    print(f"\n[7] ACCURACY")
    print("-" * 50)
    print(f"    Overall OOS Accuracy: {result.oos_accuracy:.1%}")
    
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        print(f"\n[+] Results saved to: {output_path}")
    
    print("=" * 70)
    
    return result


def validate_penalty_coefficients(
    calibration_path: str = 'calibration_history.csv'
) -> Dict[str, dict]:
    """
    Run bootstrap validation on penalty coefficients.
    
    For quant interview: "Prove these penalty coefficients aren't overfitted"
    """
    print("=" * 70)
    print("  PENALTY COEFFICIENT VALIDATION")
    print("=" * 70)
    
    picks = load_calibration_data(calibration_path)
    
    if len(picks) < 50:
        print(f"\n[!] Insufficient data for penalty validation")
        print(f"    Have: {len(picks)}, Need: 50+")
        return {}
    
    # Define penalty fields (these would need to be in your calibration history)
    penalty_fields = {
        'SDG Penalty': 'sdg_multiplier',
        'Market Efficiency': 'market_multiplier',
        'Opponent Adjustment': 'opponent_multiplier'
    }
    
    validator = PenaltyCoefficientValidator(n_bootstrap=1000)
    
    results = validator.bootstrap_penalty_validation(
        picks=picks,
        penalty_coefficients={},  # Not needed for this validation
        penalty_fields=penalty_fields
    )
    
    print(f"\n[BOOTSTRAP VALIDATION RESULTS]")
    print("-" * 50)
    
    for penalty_name, stats in results.items():
        print(f"\n{penalty_name}:")
        print(f"  Samples: {stats['n_samples']}")
        if 'mean_improvement' in stats:
            print(f"  Mean Brier improvement: {stats['mean_improvement']:.5f}")
            print(f"  95% CI: [{stats['ci_95'][0]:.5f}, {stats['ci_95'][1]:.5f}]")
            print(f"  p-value: {stats['p_value']:.4f}")
            print(f"  Verdict: {stats['verdict']}")
        else:
            print(f"  Note: {stats.get('note', 'No data')}")
    
    return results


if __name__ == '__main__':
    import sys
    
    # Run validation
    result = run_full_validation(
        output_path='quant_modules/walk_forward_results.json'
    )
    
    # If we have enough data, also validate penalties
    picks = load_calibration_data()
    if len(picks) >= 50:
        print("\n")
        validate_penalty_coefficients()
