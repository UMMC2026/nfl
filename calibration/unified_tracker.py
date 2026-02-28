"""
Unified Calibration Tracker — Cross-Sport Accuracy Monitoring
NFL_AUTONOMOUS v1.0 Compatible

GOVERNANCE: Tier thresholds imported from config/thresholds.py (single source of truth).
"""
import json
import csv
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional
import statistics

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.thresholds import TIERS, get_tier_threshold

@dataclass
class CalibrationPick:
    """Enhanced pick for calibration tracking with lambda anchor diagnosis"""
    pick_id: str
    date: str
    sport: str  # nba, tennis, cbb, nfl
    player: str
    stat: str
    line: float
    direction: str  # Higher, Lower
    probability: float
    tier: str  # SLAM, STRONG, LEAN
    actual: Optional[float] = None
    hit: Optional[bool] = None
    brier: Optional[float] = None
    
    # Game context (NEW)
    team: str = "UNK"
    opponent: str = "UNK"
    game_id: str = ""
    
    # Lambda anchor tracking (CRITICAL for diagnosis)
    lambda_player: float = 0.0
    lambda_calculation: Optional[str] = None  # How mu was computed
    gap: float = 0.0                          # (line - lambda) / lambda * 100
    z_score: float = 0.0
    
    # Probability chain (for calibration diagnosis)
    prob_raw: float = 0.0                     # Before caps
    prob_stat_capped: float = 0.0             # After stat cap
    prob_global_capped: float = 0.0           # After global cap
    cap_applied: str = "none"
    
    # Model metadata
    model_version: str = "unknown"
    
    # Edge tracking
    edge: float = 0.0                         # lambda - line
    edge_type: str = "PRIMARY"
    
    def compute_brier(self):
        """Compute Brier score if actual result is known"""
        if self.hit is not None:
            predicted = self.probability / 100.0
            actual_binary = 1.0 if self.hit else 0.0
            self.brier = (predicted - actual_binary) ** 2
            return self.brier
        return None

@dataclass
class CalibrationBucket:
    """Probability bucket for calibration analysis"""
    min_prob: float
    max_prob: float
    picks: List[CalibrationPick]
    
    @property
    def hit_rate(self) -> float:
        """Actual hit rate in this bucket"""
        hits = [p for p in self.picks if p.hit is True]
        return len(hits) / len(self.picks) if self.picks else 0.0
    
    @property
    def avg_prob(self) -> float:
        """Average predicted probability"""
        return statistics.mean([p.probability / 100.0 for p in self.picks]) if self.picks else 0.0
    
    @property
    def brier_score(self) -> float:
        """Average Brier score for bucket"""
        briers = [p.brier for p in self.picks if p.brier is not None]
        return statistics.mean(briers) if briers else 0.0
    
    @property
    def calibration_error(self) -> float:
        """Absolute difference between predicted and actual"""
        return abs(self.avg_prob - self.hit_rate)

class UnifiedCalibration:
    """Cross-sport calibration tracker"""
    
    # Sport-specific Brier thresholds
    BRIER_THRESHOLDS = {
        "nfl": 0.25,
        "nba": 0.25,
        "tennis": 0.23,  # Stricter for binary markets
        "cbb": 0.22,     # Stricter per CBB SOP
        "soccer": 0.24,  # Between NBA and tennis
        "nhl": 0.24,     # Between NBA and tennis
    }
    
    # Tier integrity targets (from canonical thresholds)
    TIER_TARGETS = TIERS  # Imported from config/thresholds.py
    
    def __init__(self, db_path: Path = Path("calibration/picks.csv")):
        self.db_path = db_path
        self.picks: List[CalibrationPick] = []
        if db_path.exists():
            self.load()
    
    def load(self):
        """Load picks from CSV (backward compatible with old schema)"""
        self.picks = []
        with open(self.db_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Helper to safely get float with default
                def safe_float(key, default=0.0):
                    val = row.get(key, '')
                    return float(val) if val and val not in ('', 'None') else default
                
                pick = CalibrationPick(
                    pick_id=row.get('pick_id', ''),
                    date=row.get('date', ''),
                    sport=row.get('sport', 'unknown'),
                    player=row.get('player', ''),
                    stat=row.get('stat', ''),
                    line=safe_float('line'),
                    direction=row.get('direction', ''),
                    probability=safe_float('probability'),
                    tier=row.get('tier', 'UNKNOWN'),
                    actual=safe_float('actual') if row.get('actual') else None,
                    hit=row.get('hit') == 'True' if row.get('hit') else None,
                    brier=safe_float('brier') if row.get('brier') else None,
                    # New fields (backward compatible)
                    team=row.get('team', 'UNK'),
                    opponent=row.get('opponent', 'UNK'),
                    game_id=row.get('game_id', ''),
                    lambda_player=safe_float('lambda_player'),
                    lambda_calculation=row.get('lambda_calculation'),
                    gap=safe_float('gap'),
                    z_score=safe_float('z_score'),
                    prob_raw=safe_float('prob_raw'),
                    prob_stat_capped=safe_float('prob_stat_capped'),
                    prob_global_capped=safe_float('prob_global_capped'),
                    cap_applied=row.get('cap_applied', 'none'),
                    model_version=row.get('model_version', 'unknown'),
                    edge=safe_float('edge'),
                    edge_type=row.get('edge_type', 'PRIMARY'),
                )
                self.picks.append(pick)
    
    def save(self):
        """Save picks to CSV with enhanced schema"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = [
                'pick_id', 'date', 'sport', 'player', 'stat', 'line', 
                'direction', 'probability', 'tier', 'actual', 'hit', 'brier',
                # Game context
                'team', 'opponent', 'game_id',
                # Lambda tracking (CRITICAL)
                'lambda_player', 'lambda_calculation', 'gap', 'z_score',
                # Probability chain
                'prob_raw', 'prob_stat_capped', 'prob_global_capped', 'cap_applied',
                # Metadata
                'model_version', 'edge', 'edge_type'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for pick in self.picks:
                writer.writerow(asdict(pick))
    
    def add_pick(self, pick: CalibrationPick):
        """Add new pick to tracking"""
        self.picks.append(pick)
        self.save()
    
    def update_result(self, pick_id: str, actual: float):
        """Update pick with actual result"""
        for pick in self.picks:
            if pick.pick_id == pick_id:
                pick.actual = actual
                
                # Determine hit based on direction
                if pick.direction == "Higher":
                    pick.hit = actual > pick.line
                else:  # Lower
                    pick.hit = actual < pick.line
                
                # Compute Brier score
                pick.compute_brier()
                break
        self.save()
    
    def get_sport_brier(self, sport: str) -> float:
        """Get overall Brier score for sport"""
        sport_picks = [p for p in self.picks if p.sport == sport and p.brier is not None]
        if not sport_picks:
            return 0.0
        return statistics.mean([p.brier for p in sport_picks])
    
    def get_tier_stats(self, sport: str = None) -> Dict[str, Dict]:
        """Get tier integrity stats"""
        picks_to_analyze = self.picks
        if sport:
            picks_to_analyze = [p for p in self.picks if p.sport == sport]
        
        tier_stats = {}
        for tier in ["SLAM", "STRONG", "LEAN"]:
            tier_picks = [p for p in picks_to_analyze if p.tier == tier and p.hit is not None]
            if tier_picks:
                hit_rate = len([p for p in tier_picks if p.hit]) / len(tier_picks)
                target = self.TIER_TARGETS[tier]
                tier_stats[tier] = {
                    "picks": len(tier_picks),
                    "hit_rate": hit_rate,
                    "target": target,
                    "meets_target": hit_rate >= target,
                    "gap": hit_rate - target
                }
        return tier_stats
    
    def get_calibration_buckets(self, sport: str = None, bucket_size: float = 0.05) -> List[CalibrationBucket]:
        """Get calibration analysis by probability buckets"""
        picks_to_analyze = [p for p in self.picks if p.hit is not None]
        if sport:
            picks_to_analyze = [p for p in picks_to_analyze if p.sport == sport]
        
        buckets = []
        for min_prob in [i/100.0 for i in range(50, 100, int(bucket_size * 100))]:
            max_prob = min_prob + bucket_size
            bucket_picks = [
                p for p in picks_to_analyze 
                if min_prob <= (p.probability / 100.0) < max_prob
            ]
            if bucket_picks:
                buckets.append(CalibrationBucket(min_prob, max_prob, bucket_picks))
        return buckets
    
    def generate_report(self, sport: str = None) -> str:
        """Generate calibration report"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"UNIFIED CALIBRATION REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        if sport:
            lines.append(f"Sport: {sport.upper()}")
        lines.append("=" * 80)
        lines.append("")
        
        # Overall Brier Score
        if sport:
            brier = self.get_sport_brier(sport)
            threshold = self.BRIER_THRESHOLDS.get(sport, 0.25)
            lines.append(f"BRIER SCORE: {brier:.4f} (threshold: {threshold})")
            if brier > threshold:
                lines.append("⚠️  DRIFT DETECTED — Probability compression recommended")
            else:
                lines.append("✅ Calibration within acceptable range")
            lines.append("")
        
        # Tier Integrity
        tier_stats = self.get_tier_stats(sport)
        lines.append("TIER INTEGRITY:")
        for tier, stats in tier_stats.items():
            status = "✅" if stats["meets_target"] else "❌"
            lines.append(f"  {tier}: {stats['hit_rate']:.1%} ({stats['picks']} picks) "
                        f"Target: {stats['target']:.0%} {status}")
            lines.append(f"         Gap: {stats['gap']:+.1%}")
        lines.append("")
        
        # Calibration Buckets
        buckets = self.get_calibration_buckets(sport)
        if buckets:
            lines.append("CALIBRATION BY PROBABILITY BUCKET:")
            lines.append(f"{'Bucket':<15} {'Picks':<8} {'Predicted':<12} {'Actual':<12} {'Error':<10} {'Brier':<10}")
            lines.append("-" * 80)
            for bucket in buckets:
                lines.append(
                    f"{bucket.min_prob:.0%}-{bucket.max_prob:.0%}  "
                    f"{len(bucket.picks):<8} "
                    f"{bucket.avg_prob:.1%}          "
                    f"{bucket.hit_rate:.1%}          "
                    f"{bucket.calibration_error:.1%}       "
                    f"{bucket.brier_score:.4f}"
                )
        
        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)
    
    def check_drift_flags(self, sport: str) -> Dict[str, bool]:
        """Check for drift conditions requiring intervention"""
        brier = self.get_sport_brier(sport)
        threshold = self.BRIER_THRESHOLDS.get(sport, 0.25)
        
        tier_stats = self.get_tier_stats(sport)
        tier_failures = sum(1 for stats in tier_stats.values() if not stats["meets_target"])
        
        return {
            "brier_drift": brier > threshold,
            "tier_integrity_failure": tier_failures >= 2,
            "requires_recalibration": brier > threshold or tier_failures >= 2
        }

# CLI Interface
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Unified Calibration Tracker")
    parser.add_argument("--sport", choices=["nba", "tennis", "cbb", "nfl"], help="Filter by sport")
    parser.add_argument("--report", action="store_true", help="Generate calibration report")
    parser.add_argument("--add-test-data", action="store_true", help="Add test data")
    args = parser.parse_args()
    
    tracker = UnifiedCalibration()
    
    if args.add_test_data:
        # Add some test picks
        test_picks = [
            CalibrationPick("TEST_001", "2026-01-23", "nba", "LeBron James", "PTS", 25.5, "Higher", 75.0, "STRONG"),
            CalibrationPick("TEST_002", "2026-01-23", "nba", "Steph Curry", "3PM", 4.5, "Higher", 68.0, "STRONG"),
            CalibrationPick("TEST_003", "2026-01-23", "tennis", "Taylor Fritz", "ACES", 18.5, "Lower", 75.0, "STRONG"),
        ]
        for pick in test_picks:
            tracker.add_pick(pick)
        print("✓ Added 3 test picks")
    
    if args.report:
        print(tracker.generate_report(args.sport))
    else:
        print(f"Loaded {len(tracker.picks)} picks")
        print(f"Use --report to generate calibration analysis")
