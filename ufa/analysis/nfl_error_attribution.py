"""
NFL Error Attribution & Feedback Loop - Phase 3 Implementation
===============================================================
Tracks prediction outcomes, identifies systematic biases, and adjusts priors.

Key components:
1. Outcome Resolution: Match predictions to actual results
2. Calibration Analysis: Compare predicted vs actual hit rates by bucket
3. Bias Detection: Identify systematic over/under-confidence by player/position/stat
4. Prior Adjustment: Feedback loop to tune Bayesian priors based on historical accuracy
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from pathlib import Path
import json
import math
import csv


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ResolvedPick:
    """A pick with its actual outcome."""
    # Identification
    pick_id: str
    date: str
    player: str
    team: str
    position: str
    opponent: str
    
    # Prop details
    stat: str
    line: float
    direction: str  # "higher" or "lower"
    
    # Prediction
    p_predicted: float      # Our probability estimate
    posterior_mu: float     # Bayesian posterior mean
    posterior_sigma: float  # Bayesian posterior std
    confidence: str         # "low"/"medium"/"high"
    
    # Actual outcome
    actual_value: float     # What actually happened
    hit: bool              # Did we hit?
    
    # Attribution metadata
    elite_adj: float = 1.0
    matchup_adj: float = 1.0
    shrinkage: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "pick_id": self.pick_id,
            "date": self.date,
            "player": self.player,
            "team": self.team,
            "position": self.position,
            "opponent": self.opponent,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "p_predicted": self.p_predicted,
            "posterior_mu": self.posterior_mu,
            "posterior_sigma": self.posterior_sigma,
            "confidence": self.confidence,
            "actual_value": self.actual_value,
            "hit": self.hit,
            "elite_adj": self.elite_adj,
            "matchup_adj": self.matchup_adj,
            "shrinkage": self.shrinkage,
        }


@dataclass
class CalibrationBucket:
    """Calibration metrics for a probability bucket."""
    p_low: float
    p_high: float
    n_picks: int
    n_hits: int
    avg_predicted: float
    actual_hit_rate: float
    calibration_error: float  # |predicted - actual|
    
    @property
    def is_overconfident(self) -> bool:
        """Are we predicting higher than reality?"""
        return self.avg_predicted > self.actual_hit_rate + 0.02
    
    @property
    def is_underconfident(self) -> bool:
        """Are we predicting lower than reality?"""
        return self.avg_predicted < self.actual_hit_rate - 0.02


@dataclass
class BiasReport:
    """Detected bias in predictions."""
    dimension: str       # "player", "position", "stat", "opponent", "matchup"
    value: str           # e.g., "Josh Allen", "QB", "pass_yds", "vs KC"
    n_picks: int
    avg_predicted: float
    actual_hit_rate: float
    bias: float          # positive = overconfident, negative = underconfident
    significance: str    # "high" (n≥20), "medium" (n≥10), "low" (n<10)
    
    @property
    def adjustment_factor(self) -> float:
        """Suggested multiplier to apply to future predictions."""
        if abs(self.bias) < 0.03:
            return 1.0  # Within acceptable range
        # Shrink toward reality: if overconfident, reduce; if underconfident, increase
        return self.actual_hit_rate / max(self.avg_predicted, 0.01)


@dataclass 
class PriorAdjustment:
    """Recommended adjustment to Bayesian priors."""
    position: str
    stat: str
    current_mu: float
    current_sigma: float
    recommended_mu: float
    recommended_sigma: float
    mu_adjustment: float      # Additive adjustment to apply
    sigma_adjustment: float   # Multiplicative adjustment
    reason: str
    confidence: str           # "high"/"medium"/"low"


# ==============================================================================
# OUTCOME RESOLUTION
# ==============================================================================

class OutcomeResolver:
    """
    Resolves predictions against actual game results.
    """
    
    def __init__(self, boxscores_path: Optional[str] = None):
        self._boxscores = {}
        if boxscores_path:
            self._load_boxscores(boxscores_path)
    
    def _load_boxscores(self, path: str):
        """Load NFL boxscore data."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                # Support multiple formats
                if isinstance(data, dict):
                    self._boxscores = data.get("players", data)
                else:
                    for game in data:
                        for player in game.get("players", []):
                            key = f"{player['name']}_{game['date']}"
                            self._boxscores[key] = player
        except Exception:
            pass
    
    def resolve(
        self,
        player: str,
        stat: str,
        line: float,
        direction: str,
        actual_value: float
    ) -> bool:
        """
        Determine if a pick hit.
        
        Args:
            player: Player name
            stat: Stat type
            line: Prop line
            direction: "higher" or "lower"
            actual_value: Actual stat value
            
        Returns:
            True if pick hit, False otherwise
        """
        if direction.lower() == "higher":
            return actual_value > line
        elif direction.lower() == "lower":
            return actual_value < line
        else:
            raise ValueError("direction must be 'higher' or 'lower'")
    
    def resolve_pick(
        self,
        pick: dict,
        actual_value: float,
        pick_date: str = None
    ) -> ResolvedPick:
        """
        Create a ResolvedPick from a prediction dict and actual value.
        """
        hit = self.resolve(
            pick["player"],
            pick["stat"],
            pick["line"],
            pick["direction"],
            actual_value
        )
        
        pick_id = f"{pick['player']}_{pick['stat']}_{pick['line']}_{pick_date or 'unknown'}"
        
        return ResolvedPick(
            pick_id=pick_id,
            date=pick_date or datetime.now().strftime("%Y-%m-%d"),
            player=pick["player"],
            team=pick.get("team", "UNK"),
            position=pick.get("position", "UNK"),
            opponent=pick.get("opponent", "UNK"),
            stat=pick["stat"],
            line=pick["line"],
            direction=pick["direction"],
            p_predicted=pick.get("p_hit", pick.get("p_predicted", 0.5)),
            posterior_mu=pick.get("posterior_mu", 0),
            posterior_sigma=pick.get("posterior_sigma", 0),
            confidence=pick.get("confidence", "medium"),
            actual_value=actual_value,
            hit=hit,
            elite_adj=pick.get("elite_adj", 1.0),
            matchup_adj=pick.get("matchup_adj", 1.0),
            shrinkage=pick.get("shrinkage", 0.0),
        )


# ==============================================================================
# CALIBRATION ANALYSIS
# ==============================================================================

class CalibrationAnalyzer:
    """
    Analyzes calibration of probability predictions.
    """
    
    def __init__(self, bucket_width: float = 0.05):
        self.bucket_width = bucket_width
    
    def analyze(self, resolved: List[ResolvedPick]) -> List[CalibrationBucket]:
        """
        Compute calibration by probability bucket.
        
        Returns buckets from 0.40-0.45 to 0.75-0.80 (capped at governance limit).
        """
        # Create buckets
        bucket_edges = [round(p, 2) for p in 
                       [0.40 + i * self.bucket_width for i in range(8)]]  # 40-80%
        
        buckets = []
        for i, p_low in enumerate(bucket_edges[:-1]):
            p_high = bucket_edges[i + 1]
            
            # Filter picks in this bucket
            in_bucket = [r for r in resolved 
                        if p_low <= r.p_predicted < p_high]
            
            if not in_bucket:
                continue
            
            n_picks = len(in_bucket)
            n_hits = sum(1 for r in in_bucket if r.hit)
            avg_pred = sum(r.p_predicted for r in in_bucket) / n_picks
            actual_rate = n_hits / n_picks
            cal_error = abs(avg_pred - actual_rate)
            
            buckets.append(CalibrationBucket(
                p_low=p_low,
                p_high=p_high,
                n_picks=n_picks,
                n_hits=n_hits,
                avg_predicted=avg_pred,
                actual_hit_rate=actual_rate,
                calibration_error=cal_error,
            ))
        
        return buckets
    
    def compute_brier_score(self, resolved: List[ResolvedPick]) -> float:
        """
        Compute Brier score (lower is better, 0 = perfect, 0.25 = random).
        """
        if not resolved:
            return 0.25
        
        return sum((r.p_predicted - (1 if r.hit else 0)) ** 2 
                  for r in resolved) / len(resolved)
    
    def compute_log_loss(self, resolved: List[ResolvedPick]) -> float:
        """
        Compute log loss (lower is better).
        """
        if not resolved:
            return 0.693  # -ln(0.5)
        
        eps = 1e-15
        total = 0.0
        for r in resolved:
            p = max(eps, min(1 - eps, r.p_predicted))
            if r.hit:
                total -= math.log(p)
            else:
                total -= math.log(1 - p)
        
        return total / len(resolved)
    
    def format_calibration_report(
        self,
        resolved: List[ResolvedPick],
        buckets: List[CalibrationBucket]
    ) -> str:
        """Generate human-readable calibration report."""
        brier = self.compute_brier_score(resolved)
        log_loss = self.compute_log_loss(resolved)
        
        lines = [
            "=" * 70,
            "CALIBRATION REPORT",
            "=" * 70,
            f"Total Picks: {len(resolved)}",
            f"Overall Hit Rate: {sum(1 for r in resolved if r.hit)/len(resolved):.1%}",
            f"Brier Score: {brier:.4f} (lower is better, 0.25 = random)",
            f"Log Loss: {log_loss:.4f} (lower is better)",
            "",
            f"{'Bucket':<12} {'N':<6} {'Pred':<8} {'Actual':<8} {'Error':<8} {'Status':<12}",
            "-" * 70,
        ]
        
        for b in buckets:
            status = "✓ Calibrated"
            if b.is_overconfident:
                status = "⚠ Overconfident"
            elif b.is_underconfident:
                status = "↑ Underconfident"
            
            lines.append(
                f"{b.p_low:.0%}-{b.p_high:.0%}    "
                f"{b.n_picks:<6} {b.avg_predicted:<8.1%} {b.actual_hit_rate:<8.1%} "
                f"{b.calibration_error:<8.1%} {status:<12}"
            )
        
        lines.append("=" * 70)
        return "\n".join(lines)


# ==============================================================================
# BIAS DETECTION
# ==============================================================================

class BiasDetector:
    """
    Identifies systematic biases in predictions.
    """
    
    def detect_all_biases(self, resolved: List[ResolvedPick]) -> Dict[str, List[BiasReport]]:
        """
        Detect biases across all dimensions.
        
        Returns:
            Dictionary mapping dimension name to list of BiasReports
        """
        return {
            "player": self._detect_by_dimension(resolved, "player"),
            "position": self._detect_by_dimension(resolved, "position"),
            "stat": self._detect_by_dimension(resolved, "stat"),
            "opponent": self._detect_by_dimension(resolved, "opponent"),
            "confidence": self._detect_by_dimension(resolved, "confidence"),
        }
    
    def _detect_by_dimension(
        self,
        resolved: List[ResolvedPick],
        dimension: str
    ) -> List[BiasReport]:
        """Detect bias along a single dimension."""
        # Group by dimension value
        groups: Dict[str, List[ResolvedPick]] = {}
        for r in resolved:
            value = getattr(r, dimension, "unknown")
            if value not in groups:
                groups[value] = []
            groups[value].append(r)
        
        # Calculate bias for each group
        biases = []
        for value, picks in groups.items():
            if len(picks) < 3:  # Need minimum sample
                continue
            
            avg_pred = sum(p.p_predicted for p in picks) / len(picks)
            actual_rate = sum(1 for p in picks if p.hit) / len(picks)
            bias = avg_pred - actual_rate
            
            # Significance based on sample size
            if len(picks) >= 20:
                sig = "high"
            elif len(picks) >= 10:
                sig = "medium"
            else:
                sig = "low"
            
            # Only report significant biases
            if abs(bias) >= 0.03 or len(picks) >= 10:
                biases.append(BiasReport(
                    dimension=dimension,
                    value=value,
                    n_picks=len(picks),
                    avg_predicted=avg_pred,
                    actual_hit_rate=actual_rate,
                    bias=bias,
                    significance=sig,
                ))
        
        # Sort by absolute bias (biggest problems first)
        return sorted(biases, key=lambda b: abs(b.bias), reverse=True)
    
    def get_worst_biases(
        self,
        all_biases: Dict[str, List[BiasReport]],
        n: int = 10
    ) -> List[BiasReport]:
        """Get the N worst biases across all dimensions."""
        all_reports = []
        for reports in all_biases.values():
            all_reports.extend(reports)
        
        # Filter to significant biases only
        significant = [b for b in all_reports 
                      if b.significance in ("high", "medium") and abs(b.bias) >= 0.05]
        
        return sorted(significant, key=lambda b: abs(b.bias), reverse=True)[:n]
    
    def format_bias_report(
        self,
        all_biases: Dict[str, List[BiasReport]]
    ) -> str:
        """Generate human-readable bias report."""
        lines = [
            "=" * 70,
            "BIAS DETECTION REPORT",
            "=" * 70,
        ]
        
        worst = self.get_worst_biases(all_biases)
        
        if not worst:
            lines.append("No significant biases detected.")
        else:
            lines.append(f"\nTop {len(worst)} Biases Detected:\n")
            lines.append(f"{'Dimension':<12} {'Value':<20} {'N':<6} {'Pred':<8} {'Actual':<8} {'Bias':<8}")
            lines.append("-" * 70)
            
            for b in worst:
                bias_str = f"{b.bias:+.1%}"
                direction = "OVER" if b.bias > 0 else "UNDER"
                lines.append(
                    f"{b.dimension:<12} {b.value:<20} {b.n_picks:<6} "
                    f"{b.avg_predicted:<8.1%} {b.actual_hit_rate:<8.1%} {bias_str:<8} [{direction}]"
                )
        
        lines.append("=" * 70)
        return "\n".join(lines)


# ==============================================================================
# PRIOR ADJUSTMENT (FEEDBACK LOOP)
# ==============================================================================

class PriorAdjuster:
    """
    Recommends adjustments to Bayesian priors based on historical performance.
    """
    
    def __init__(self, learning_rate: float = 0.2):
        """
        Args:
            learning_rate: How aggressively to adjust priors (0-1).
                           0 = no adjustment, 1 = full adjustment to empirical values
        """
        self.learning_rate = learning_rate
    
    def compute_adjustments(
        self,
        resolved: List[ResolvedPick],
        current_priors: Dict[str, Dict[str, dict]]
    ) -> List[PriorAdjustment]:
        """
        Compute recommended prior adjustments based on resolved picks.
        
        Args:
            resolved: List of resolved picks with outcomes
            current_priors: Current NFL_PRIORS structure
            
        Returns:
            List of PriorAdjustment recommendations
        """
        adjustments = []
        
        # Group by position + stat
        groups: Dict[Tuple[str, str], List[ResolvedPick]] = {}
        for r in resolved:
            key = (r.position, r.stat)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)
        
        for (position, stat), picks in groups.items():
            if len(picks) < 5:  # Need minimum sample
                continue
            
            # Get current prior
            pos_priors = current_priors.get(position, {})
            stat_prior = pos_priors.get(stat)
            if not stat_prior:
                continue
            
            current_mu = stat_prior.mu if hasattr(stat_prior, 'mu') else stat_prior.get('mu', 0)
            current_sigma = stat_prior.sigma if hasattr(stat_prior, 'sigma') else stat_prior.get('sigma', 1)
            
            # Calculate empirical statistics from actuals
            actuals = [p.actual_value for p in picks]
            emp_mu = sum(actuals) / len(actuals)
            emp_var = sum((v - emp_mu) ** 2 for v in actuals) / max(len(actuals) - 1, 1)
            emp_sigma = math.sqrt(max(emp_var, 1e-6))
            
            # Calculate calibration error for this position/stat
            avg_pred = sum(p.p_predicted for p in picks) / len(picks)
            actual_rate = sum(1 for p in picks if p.hit) / len(picks)
            bias = avg_pred - actual_rate
            
            # Only adjust if significant bias detected
            if abs(bias) < 0.03 and len(picks) < 15:
                continue
            
            # Compute recommended adjustments
            # For mean: blend toward empirical mean
            mu_adj = self.learning_rate * (emp_mu - current_mu)
            rec_mu = current_mu + mu_adj
            
            # For sigma: adjust if we're systematically wrong
            # If overconfident, increase sigma (more uncertainty)
            # If underconfident, decrease sigma
            sigma_mult = 1.0
            if bias > 0.05:  # Overconfident
                sigma_mult = 1.0 + self.learning_rate * 0.15  # Increase by up to 15%
            elif bias < -0.05:  # Underconfident
                sigma_mult = 1.0 - self.learning_rate * 0.10  # Decrease by up to 10%
            
            rec_sigma = current_sigma * sigma_mult
            
            # Determine confidence
            if len(picks) >= 20:
                conf = "high"
            elif len(picks) >= 10:
                conf = "medium"
            else:
                conf = "low"
            
            # Build reason
            reason_parts = []
            if abs(bias) >= 0.05:
                direction = "overconfident" if bias > 0 else "underconfident"
                reason_parts.append(f"{direction} by {abs(bias):.1%}")
            if abs(emp_mu - current_mu) > current_sigma * 0.5:
                reason_parts.append(f"empirical μ={emp_mu:.1f} vs prior μ={current_mu:.1f}")
            
            if reason_parts:
                adjustments.append(PriorAdjustment(
                    position=position,
                    stat=stat,
                    current_mu=current_mu,
                    current_sigma=current_sigma,
                    recommended_mu=rec_mu,
                    recommended_sigma=rec_sigma,
                    mu_adjustment=mu_adj,
                    sigma_adjustment=sigma_mult,
                    reason="; ".join(reason_parts),
                    confidence=conf,
                ))
        
        # Sort by confidence and impact
        return sorted(adjustments, 
                     key=lambda a: (a.confidence == "high", abs(a.mu_adjustment)), 
                     reverse=True)
    
    def format_adjustment_report(
        self,
        adjustments: List[PriorAdjustment]
    ) -> str:
        """Generate human-readable adjustment report."""
        lines = [
            "=" * 70,
            "PRIOR ADJUSTMENT RECOMMENDATIONS",
            "=" * 70,
        ]
        
        if not adjustments:
            lines.append("No adjustments recommended (system is well-calibrated).")
        else:
            lines.append(f"\n{len(adjustments)} Adjustments Recommended:\n")
            
            for adj in adjustments:
                lines.append(f"[{adj.confidence.upper()}] {adj.position} - {adj.stat}")
                lines.append(f"  Current:     μ={adj.current_mu:.1f}, σ={adj.current_sigma:.1f}")
                lines.append(f"  Recommended: μ={adj.recommended_mu:.1f}, σ={adj.recommended_sigma:.1f}")
                lines.append(f"  Adjustment:  μ{adj.mu_adjustment:+.1f}, σ×{adj.sigma_adjustment:.2f}")
                lines.append(f"  Reason: {adj.reason}")
                lines.append("")
        
        lines.append("=" * 70)
        return "\n".join(lines)


# ==============================================================================
# MAIN ERROR ATTRIBUTION ENGINE
# ==============================================================================

class NFLErrorAttribution:
    """
    Complete error attribution and feedback system for NFL predictions.
    
    Usage:
        engine = NFLErrorAttribution()
        
        # Add resolved picks
        for pick, actual in zip(predictions, actuals):
            resolved = engine.resolve(pick, actual)
        
        # Analyze
        report = engine.full_analysis()
        print(report)
        
        # Get prior adjustments
        adjustments = engine.get_prior_adjustments()
    """
    
    def __init__(self, history_path: Optional[str] = None):
        self.resolver = OutcomeResolver()
        self.calibrator = CalibrationAnalyzer()
        self.bias_detector = BiasDetector()
        self.prior_adjuster = PriorAdjuster()
        
        self.resolved_picks: List[ResolvedPick] = []
        self.history_path = history_path or "data/nfl_calibration_history.json"
        
        self._load_history()
    
    def _load_history(self):
        """Load historical resolved picks."""
        try:
            path = Path(self.history_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    for d in data:
                        self.resolved_picks.append(ResolvedPick(**d))
        except Exception:
            pass
    
    def save_history(self):
        """Save resolved picks to history file."""
        path = Path(self.history_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump([r.to_dict() for r in self.resolved_picks], f, indent=2)
    
    def resolve(self, pick: dict, actual_value: float, pick_date: str = None) -> ResolvedPick:
        """Resolve a single pick and add to history."""
        resolved = self.resolver.resolve_pick(pick, actual_value, pick_date)
        self.resolved_picks.append(resolved)
        return resolved
    
    def analyze_calibration(self) -> Tuple[List[CalibrationBucket], str]:
        """Analyze calibration and return buckets + report."""
        buckets = self.calibrator.analyze(self.resolved_picks)
        report = self.calibrator.format_calibration_report(self.resolved_picks, buckets)
        return buckets, report
    
    def analyze_biases(self) -> Tuple[Dict[str, List[BiasReport]], str]:
        """Detect biases and return reports."""
        biases = self.bias_detector.detect_all_biases(self.resolved_picks)
        report = self.bias_detector.format_bias_report(biases)
        return biases, report
    
    def get_prior_adjustments(self) -> Tuple[List[PriorAdjustment], str]:
        """Get recommended prior adjustments."""
        # Import current priors
        try:
            from ufa.analysis.nfl_bayesian_prior import NFL_PRIORS
            adjustments = self.prior_adjuster.compute_adjustments(
                self.resolved_picks, NFL_PRIORS
            )
        except ImportError:
            adjustments = []
        
        report = self.prior_adjuster.format_adjustment_report(adjustments)
        return adjustments, report
    
    def full_analysis(self) -> str:
        """Run complete analysis and return full report."""
        if not self.resolved_picks:
            return "No resolved picks to analyze."
        
        _, cal_report = self.analyze_calibration()
        _, bias_report = self.analyze_biases()
        _, adj_report = self.get_prior_adjustments()
        
        return "\n\n".join([cal_report, bias_report, adj_report])
    
    def summary_metrics(self) -> dict:
        """Return summary metrics dictionary."""
        if not self.resolved_picks:
            return {"n_picks": 0, "error": "No data"}
        
        n = len(self.resolved_picks)
        n_hits = sum(1 for r in self.resolved_picks if r.hit)
        
        return {
            "n_picks": n,
            "hit_rate": n_hits / n,
            "brier_score": self.calibrator.compute_brier_score(self.resolved_picks),
            "log_loss": self.calibrator.compute_log_loss(self.resolved_picks),
            "avg_predicted": sum(r.p_predicted for r in self.resolved_picks) / n,
        }


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("NFL Error Attribution - Phase 3 Test")
    print("=" * 70)
    
    # Create test resolved picks
    test_picks = [
        # Josh Allen pass yards - predicted high, hit
        {"player": "Josh Allen", "team": "BUF", "position": "QB", "opponent": "KC",
         "stat": "pass_yds", "line": 265.5, "direction": "higher",
         "p_hit": 0.58, "posterior_mu": 280, "posterior_sigma": 45, "confidence": "medium"},
        
        # Derrick Henry rush yards - predicted medium, hit  
        {"player": "Derrick Henry", "team": "BAL", "position": "RB", "opponent": "BUF",
         "stat": "rush_yds", "line": 85.5, "direction": "higher",
         "p_hit": 0.62, "posterior_mu": 95, "posterior_sigma": 30, "confidence": "medium"},
        
        # Travis Kelce rec yards - predicted high, miss
        {"player": "Travis Kelce", "team": "KC", "position": "TE", "opponent": "BUF",
         "stat": "rec_yds", "line": 65.5, "direction": "higher",
         "p_hit": 0.68, "posterior_mu": 75, "posterior_sigma": 20, "confidence": "high"},
        
        # James Cook rush yards - predicted low, hit
        {"player": "James Cook", "team": "BUF", "position": "RB", "opponent": "KC",
         "stat": "rush_yds", "line": 50.5, "direction": "higher",
         "p_hit": 0.45, "posterior_mu": 48, "posterior_sigma": 25, "confidence": "low"},
        
        # Xavier Worthy rec yards - predicted medium, miss
        {"player": "Xavier Worthy", "team": "KC", "position": "WR", "opponent": "BUF",
         "stat": "rec_yds", "line": 45.5, "direction": "higher",
         "p_hit": 0.55, "posterior_mu": 50, "posterior_sigma": 22, "confidence": "medium"},
    ]
    
    # Simulated actual values
    actuals = [285, 105, 55, 65, 32]
    
    # Create engine and resolve picks
    engine = NFLErrorAttribution()
    
    print("\n[Test] Resolving picks...")
    for pick, actual in zip(test_picks, actuals):
        resolved = engine.resolve(pick, actual, "2025-01-19")
        status = "✓ HIT" if resolved.hit else "✗ MISS"
        print(f"  {resolved.player} {resolved.stat} {resolved.line} {resolved.direction.upper()}: "
              f"Actual={actual}, P={resolved.p_predicted:.1%} → {status}")
    
    # Run full analysis
    print("\n" + engine.full_analysis())
    
    # Summary metrics
    print("\n[Test] Summary Metrics:")
    metrics = engine.summary_metrics()
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")
    
    print("\n✅ Phase 3 Error Attribution: OPERATIONAL")
