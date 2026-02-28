"""
Calibration + Brier Charts (Dashboard-Native)
=============================================
ENFORCEMENT LAYER D — Separates you from 99% of tools.

NO MATH CHANGES — This is calibration visibility/audit only.

Metrics Stored:
- Bucket assignment (55–60%, etc.)
- Predicted vs actual
- Brier score

UI Hard Rule:
  If calibration_error > 2% → banner: "⚠️ Model recalibration in progress"
"""

from __future__ import annotations

import sys
import json
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# CONFIGURATION
# =============================================================================

CALIBRATION_ERROR_THRESHOLD = 0.02  # 2% — triggers warning banner
BRIER_THRESHOLD = 0.25  # Standard threshold

PROBABILITY_BUCKETS = [
    (50, 55, "50–55%"),
    (55, 60, "55–60%"),
    (60, 65, "60–65%"),
    (65, 70, "65–70%"),
    (70, 75, "70–75%"),
    (75, 80, "75–80%"),
    (80, 85, "80–85%"),
    (85, 90, "85–90%"),
    (90, 100, "90–100%"),
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CalibrationPoint:
    """Single pick with calibration data."""
    edge_id: str
    player: str
    stat: str
    line: float
    direction: str
    predicted: float  # 0.0-1.0
    actual: Optional[bool] = None  # True=hit, False=miss, None=pending
    brier: Optional[float] = None
    bucket: Optional[str] = None
    date: str = ""
    tier: str = ""
    
    def compute_brier(self) -> Optional[float]:
        """Compute Brier score = (predicted - actual)^2"""
        if self.actual is None:
            return None
        actual_val = 1.0 if self.actual else 0.0
        self.brier = (self.predicted - actual_val) ** 2
        return self.brier
    
    def assign_bucket(self) -> str:
        """Assign to probability bucket."""
        prob_pct = self.predicted * 100
        for min_p, max_p, label in PROBABILITY_BUCKETS:
            if min_p <= prob_pct < max_p:
                self.bucket = label
                return label
        self.bucket = "Out of range"
        return self.bucket
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationBucket:
    """Aggregated stats for a probability bucket."""
    bucket_label: str
    min_prob: float
    max_prob: float
    
    total_picks: int = 0
    resolved_picks: int = 0
    hits: int = 0
    
    avg_predicted: float = 0.0
    actual_hit_rate: float = 0.0
    calibration_error: float = 0.0
    brier_score: float = 0.0
    
    picks: List[CalibrationPoint] = field(default_factory=list)
    
    def compute_metrics(self):
        """Compute aggregated metrics."""
        if not self.picks:
            return
        
        self.total_picks = len(self.picks)
        resolved = [p for p in self.picks if p.actual is not None]
        self.resolved_picks = len(resolved)
        
        if not resolved:
            return
        
        self.hits = sum(1 for p in resolved if p.actual)
        self.actual_hit_rate = self.hits / self.resolved_picks
        self.avg_predicted = statistics.mean(p.predicted for p in resolved)
        self.calibration_error = abs(self.avg_predicted - self.actual_hit_rate)
        
        briers = [p.brier for p in resolved if p.brier is not None]
        self.brier_score = statistics.mean(briers) if briers else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bucket_label": self.bucket_label,
            "min_prob": self.min_prob,
            "max_prob": self.max_prob,
            "total_picks": self.total_picks,
            "resolved_picks": self.resolved_picks,
            "hits": self.hits,
            "avg_predicted": round(self.avg_predicted, 4),
            "actual_hit_rate": round(self.actual_hit_rate, 4),
            "calibration_error": round(self.calibration_error, 4),
            "brier_score": round(self.brier_score, 4),
        }


@dataclass
class TierAccuracy:
    """Accuracy metrics for a tier."""
    tier: str
    total_picks: int = 0
    resolved_picks: int = 0
    hits: int = 0
    hit_rate: float = 0.0
    avg_brier: float = 0.0
    
    # Expected hit rate from tier
    expected_min: float = 0.0
    expected_max: float = 0.0
    meets_expectation: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationReport:
    """Complete calibration report."""
    generated_at: str
    date_range: Tuple[str, str]
    
    # Overall metrics
    total_picks: int = 0
    resolved_picks: int = 0
    overall_hit_rate: float = 0.0
    overall_brier: float = 0.0
    overall_calibration_error: float = 0.0
    
    # Flags
    needs_recalibration: bool = False
    recalibration_reason: Optional[str] = None
    
    # Breakdown
    buckets: List[CalibrationBucket] = field(default_factory=list)
    tiers: List[TierAccuracy] = field(default_factory=list)
    
    # Trend data (for charts)
    brier_trend_7d: List[float] = field(default_factory=list)
    brier_trend_30d: List[float] = field(default_factory=list)
    brier_trend_90d: List[float] = field(default_factory=list)
    
    reliability_curve: List[Tuple[float, float]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "date_range": self.date_range,
            "total_picks": self.total_picks,
            "resolved_picks": self.resolved_picks,
            "overall_hit_rate": round(self.overall_hit_rate, 4),
            "overall_brier": round(self.overall_brier, 4),
            "overall_calibration_error": round(self.overall_calibration_error, 4),
            "needs_recalibration": self.needs_recalibration,
            "recalibration_reason": self.recalibration_reason,
            "buckets": [b.to_dict() for b in self.buckets],
            "tiers": [t.to_dict() for t in self.tiers],
            "brier_trend_7d": self.brier_trend_7d,
            "brier_trend_30d": self.brier_trend_30d,
            "brier_trend_90d": self.brier_trend_90d,
            "reliability_curve": self.reliability_curve,
        }


# =============================================================================
# CALIBRATION ENGINE
# =============================================================================

class CalibrationEngine:
    """
    Compute calibration metrics from pick history.
    
    This is the dashboard-native layer for reliability curves,
    Brier trends, and tier accuracy tables.
    """
    
    # Tier expected hit rates
    TIER_EXPECTATIONS = {
        "SLAM": (0.75, 0.90),
        "STRONG": (0.60, 0.75),
        "LEAN": (0.50, 0.65),
        "WATCH": (0.45, 0.55),
        "NO_PLAY": (0.0, 0.50),
        "NO PLAY": (0.0, 0.50),
        "AVOID": (0.0, 0.45),
    }
    
    def __init__(self, picks: List[CalibrationPoint] = None):
        self.picks: List[CalibrationPoint] = picks or []
    
    def add_pick(self, pick: CalibrationPoint):
        """Add pick and compute derived fields."""
        pick.assign_bucket()
        pick.compute_brier()
        self.picks.append(pick)
    
    def generate_report(
        self,
        start_date: str = None,
        end_date: str = None
    ) -> CalibrationReport:
        """Generate full calibration report."""
        
        # Filter by date if provided
        picks = self.picks
        if start_date:
            picks = [p for p in picks if p.date >= start_date]
        if end_date:
            picks = [p for p in picks if p.date <= end_date]
        
        report = CalibrationReport(
            generated_at=datetime.now().isoformat(),
            date_range=(start_date or "all", end_date or "all"),
        )
        
        if not picks:
            return report
        
        report.total_picks = len(picks)
        
        # Compute buckets
        report.buckets = self._compute_buckets(picks)
        
        # Compute tier accuracy
        report.tiers = self._compute_tier_accuracy(picks)
        
        # Compute overall metrics
        resolved = [p for p in picks if p.actual is not None]
        report.resolved_picks = len(resolved)
        
        if resolved:
            report.overall_hit_rate = sum(1 for p in resolved if p.actual) / len(resolved)
            briers = [p.brier for p in resolved if p.brier is not None]
            report.overall_brier = statistics.mean(briers) if briers else 0.0
            
            # Overall calibration error
            if report.buckets:
                errors = [b.calibration_error for b in report.buckets if b.resolved_picks > 0]
                report.overall_calibration_error = statistics.mean(errors) if errors else 0.0
        
        # Check recalibration needs
        if report.overall_calibration_error > CALIBRATION_ERROR_THRESHOLD:
            report.needs_recalibration = True
            report.recalibration_reason = f"Calibration error {report.overall_calibration_error*100:.1f}% > {CALIBRATION_ERROR_THRESHOLD*100:.0f}% threshold"
        
        if report.overall_brier > BRIER_THRESHOLD:
            report.needs_recalibration = True
            report.recalibration_reason = f"Brier score {report.overall_brier:.3f} > {BRIER_THRESHOLD} threshold"
        
        # Check tier failures
        tier_failures = [t for t in report.tiers if not t.meets_expectation and t.resolved_picks >= 10]
        if len(tier_failures) >= 2:
            report.needs_recalibration = True
            report.recalibration_reason = f"{len(tier_failures)} tiers below expected hit rate"
        
        # Reliability curve
        report.reliability_curve = self._compute_reliability_curve(report.buckets)
        
        # Brier trends (placeholder - would need time-series data)
        report.brier_trend_7d = self._compute_brier_trend(picks, days=7)
        report.brier_trend_30d = self._compute_brier_trend(picks, days=30)
        report.brier_trend_90d = self._compute_brier_trend(picks, days=90)
        
        return report
    
    def _compute_buckets(self, picks: List[CalibrationPoint]) -> List[CalibrationBucket]:
        """Compute metrics for each probability bucket."""
        bucket_map = {}
        
        for min_p, max_p, label in PROBABILITY_BUCKETS:
            bucket_map[label] = CalibrationBucket(
                bucket_label=label,
                min_prob=min_p / 100,
                max_prob=max_p / 100,
            )
        
        for pick in picks:
            bucket_label = pick.bucket or pick.assign_bucket()
            if bucket_label in bucket_map:
                bucket_map[bucket_label].picks.append(pick)
        
        buckets = list(bucket_map.values())
        for bucket in buckets:
            bucket.compute_metrics()
        
        return buckets
    
    def _compute_tier_accuracy(self, picks: List[CalibrationPoint]) -> List[TierAccuracy]:
        """Compute accuracy by tier."""
        tier_picks = defaultdict(list)
        for pick in picks:
            tier = pick.tier.upper() if pick.tier else "UNKNOWN"
            tier_picks[tier].append(pick)
        
        results = []
        for tier, t_picks in tier_picks.items():
            resolved = [p for p in t_picks if p.actual is not None]
            
            ta = TierAccuracy(tier=tier)
            ta.total_picks = len(t_picks)
            ta.resolved_picks = len(resolved)
            
            if resolved:
                ta.hits = sum(1 for p in resolved if p.actual)
                ta.hit_rate = ta.hits / ta.resolved_picks
                briers = [p.brier for p in resolved if p.brier is not None]
                ta.avg_brier = statistics.mean(briers) if briers else 0.0
            
            # Check expectation
            exp = self.TIER_EXPECTATIONS.get(tier, (0.0, 1.0))
            ta.expected_min, ta.expected_max = exp
            
            if ta.resolved_picks >= 5:  # Minimum sample
                ta.meets_expectation = ta.expected_min <= ta.hit_rate <= ta.expected_max + 0.05
            
            results.append(ta)
        
        # Sort by tier importance
        tier_order = ["SLAM", "STRONG", "LEAN", "WATCH", "NO_PLAY", "NO PLAY", "AVOID"]
        results.sort(key=lambda x: tier_order.index(x.tier) if x.tier in tier_order else 99)
        
        return results
    
    def _compute_reliability_curve(
        self,
        buckets: List[CalibrationBucket]
    ) -> List[Tuple[float, float]]:
        """
        Compute reliability curve points (predicted, actual).
        Perfect calibration = diagonal line.
        """
        points = []
        for bucket in buckets:
            if bucket.resolved_picks >= 3:  # Minimum for meaningful point
                points.append((bucket.avg_predicted, bucket.actual_hit_rate))
        
        return sorted(points, key=lambda x: x[0])
    
    def _compute_brier_trend(
        self,
        picks: List[CalibrationPoint],
        days: int
    ) -> List[float]:
        """Compute daily Brier scores for trend chart."""
        if not picks:
            return []
        
        # Group by date
        by_date = defaultdict(list)
        for pick in picks:
            if pick.date and pick.brier is not None:
                by_date[pick.date].append(pick.brier)
        
        # Get last N days
        dates = sorted(by_date.keys())[-days:]
        
        return [statistics.mean(by_date[d]) for d in dates if by_date[d]]


# =============================================================================
# EDGE ENRICHMENT
# =============================================================================

def enrich_edge_with_calibration(edge: Dict, engine: CalibrationEngine) -> Dict:
    """
    Add calibration metadata to edge for dashboard consumption.
    
    Adds:
    - edge["calibration"]["bucket"]: "55–60%"
    - edge["calibration"]["predicted"]: 0.58
    - edge["calibration"]["bucket_hit_rate"]: 0.56
    - edge["calibration"]["bucket_brier"]: 0.19
    """
    prob = edge.get("probability", 0)
    if isinstance(prob, float) and prob <= 1.0:
        prob_pct = prob * 100
    else:
        prob_pct = float(prob)
        prob = prob_pct / 100
    
    # Find bucket
    bucket_label = None
    for min_p, max_p, label in PROBABILITY_BUCKETS:
        if min_p <= prob_pct < max_p:
            bucket_label = label
            break
    
    # Get bucket stats from engine
    bucket_stats = None
    if bucket_label and hasattr(engine, 'picks') and engine.picks:
        report = engine.generate_report()
        for b in report.buckets:
            if b.bucket_label == bucket_label:
                bucket_stats = b
                break
    
    edge_copy = edge.copy()
    edge_copy["calibration"] = {
        "bucket": bucket_label,
        "predicted": round(prob, 4),
        "bucket_hit_rate": round(bucket_stats.actual_hit_rate, 4) if bucket_stats else None,
        "bucket_brier": round(bucket_stats.brier_score, 4) if bucket_stats else None,
        "bucket_sample_size": bucket_stats.resolved_picks if bucket_stats else 0,
    }
    
    return edge_copy


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================

def render_calibration_table(report: CalibrationReport) -> str:
    """Render calibration table for terminal/text."""
    lines = [
        "=" * 70,
        "📊 CALIBRATION REPORT",
        "=" * 70,
    ]
    
    # Warning banner
    if report.needs_recalibration:
        lines.append("")
        lines.append("⚠️  MODEL RECALIBRATION IN PROGRESS")
        lines.append(f"   Reason: {report.recalibration_reason}")
        lines.append("")
    
    # Overall stats
    lines.append(f"\n📈 OVERALL METRICS")
    lines.append("-" * 40)
    lines.append(f"Total picks: {report.total_picks}")
    lines.append(f"Resolved: {report.resolved_picks}")
    lines.append(f"Hit rate: {report.overall_hit_rate*100:.1f}%")
    lines.append(f"Brier score: {report.overall_brier:.4f} (threshold: {BRIER_THRESHOLD})")
    lines.append(f"Calibration error: {report.overall_calibration_error*100:.2f}%")
    
    # Bucket table
    lines.append(f"\n📊 RELIABILITY BY BUCKET")
    lines.append("-" * 70)
    lines.append(f"{'Bucket':<12} {'Picks':>6} {'Predicted':>10} {'Actual':>10} {'Error':>8} {'Brier':>8}")
    lines.append("-" * 70)
    
    for bucket in report.buckets:
        if bucket.resolved_picks > 0:
            error_flag = "⚠️" if bucket.calibration_error > CALIBRATION_ERROR_THRESHOLD else "  "
            lines.append(
                f"{bucket.bucket_label:<12} {bucket.resolved_picks:>6} "
                f"{bucket.avg_predicted*100:>9.1f}% {bucket.actual_hit_rate*100:>9.1f}% "
                f"{bucket.calibration_error*100:>6.1f}% {bucket.brier_score:>7.4f} {error_flag}"
            )
    
    # Tier accuracy
    lines.append(f"\n🏆 TIER ACCURACY")
    lines.append("-" * 70)
    lines.append(f"{'Tier':<12} {'Picks':>6} {'Hits':>6} {'Rate':>8} {'Expected':>15} {'Status':>8}")
    lines.append("-" * 70)
    
    for tier in report.tiers:
        if tier.resolved_picks > 0:
            exp_str = f"{tier.expected_min*100:.0f}–{tier.expected_max*100:.0f}%"
            status = "✅" if tier.meets_expectation else "❌"
            lines.append(
                f"{tier.tier:<12} {tier.resolved_picks:>6} {tier.hits:>6} "
                f"{tier.hit_rate*100:>7.1f}% {exp_str:>15} {status:>8}"
            )
    
    return "\n".join(lines)


def render_reliability_curve_ascii(report: CalibrationReport) -> str:
    """Render ASCII reliability curve."""
    lines = [
        "\n📈 RELIABILITY CURVE (Predicted vs Actual)",
        "   Perfect calibration = diagonal",
        ""
    ]
    
    # Simple ASCII chart
    width = 40
    height = 10
    
    grid = [[' ' for _ in range(width)] for _ in range(height)]
    
    # Draw diagonal (perfect calibration)
    for i in range(min(width, height)):
        y = height - 1 - i
        x = int(i * width / height)
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = '·'
    
    # Plot actual points
    for pred, actual in report.reliability_curve:
        x = int(pred * (width - 1))
        y = int((1 - actual) * (height - 1))
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = '●'
    
    # Render
    lines.append("   1.0 ┤" + "".join(grid[0]))
    for i, row in enumerate(grid[1:-1], 1):
        lines.append("       │" + "".join(row))
    lines.append("   0.0 ┤" + "".join(grid[-1]))
    lines.append("       └" + "─" * width)
    lines.append("        0%                           100%")
    lines.append("                 Predicted")
    
    return "\n".join(lines)


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    # Create sample picks for testing
    import random
    
    engine = CalibrationEngine()
    
    # Generate sample picks with realistic calibration
    tiers = ["SLAM", "STRONG", "LEAN"]
    tier_ranges = {
        "SLAM": (0.75, 0.85),
        "STRONG": (0.60, 0.70),
        "LEAN": (0.55, 0.62),
    }
    
    for i in range(100):
        tier = random.choice(tiers)
        prob_min, prob_max = tier_ranges[tier]
        predicted = random.uniform(prob_min, prob_max)
        
        # Actual result with slight under-calibration
        actual_prob = predicted * 0.95  # Slightly overconfident
        actual = random.random() < actual_prob
        
        pick = CalibrationPoint(
            edge_id=f"test_{i}",
            player=f"Player {i % 10}",
            stat=random.choice(["points", "rebounds", "assists"]),
            line=random.uniform(10, 30),
            direction=random.choice(["higher", "lower"]),
            predicted=predicted,
            actual=actual,
            tier=tier,
            date=f"2026-01-{15 + (i % 15):02d}",
        )
        engine.add_pick(pick)
    
    # Generate report
    report = engine.generate_report()
    
    print(render_calibration_table(report))
    print(render_reliability_curve_ascii(report))
    
    print("\n" + "=" * 60)
    print("JSON EXPORT:")
    print("=" * 60)
    print(json.dumps(report.to_dict(), indent=2)[:2000] + "...")
