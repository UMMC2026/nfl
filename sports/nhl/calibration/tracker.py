"""
NHL CALIBRATION TRACKER — v3.0 Module
======================================

Track and analyze prediction accuracy by stat type, tier, and confidence.

Features:
    - Result recording (hit/miss/push)
    - Hit rate by stat type
    - Hit rate by tier
    - Calibration curves
    - Exportable reports

Storage:
    - JSON file (simple, portable)
    - CSV export for analysis
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================
# PATHS
# ============================================================

NHL_DIR = Path(__file__).parent.parent
CALIBRATION_DIR = NHL_DIR / "calibration"
CALIBRATION_FILE = CALIBRATION_DIR / "nhl_calibration_history.json"
CALIBRATION_CSV = CALIBRATION_DIR / "nhl_calibration_export.csv"


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class PickResult:
    """Single pick result"""
    pick_id: str              # Unique identifier
    date: str                 # YYYY-MM-DD
    player: str
    team: str
    opponent: str
    stat: str                 # goals, assists, points, sog, saves
    line: float
    direction: str            # OVER or UNDER
    actual_value: float       # Actual result
    
    # Model predictions
    probability: float        # Model probability (0-1)
    tier: str                 # STRONG, LEAN, NO_PLAY
    
    # Outcome
    result: str               # HIT, MISS, PUSH
    
    # Metadata
    source: str = "underdog"  # Platform
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    @property
    def hit(self) -> bool:
        return self.result == "HIT"
    
    @property
    def miss(self) -> bool:
        return self.result == "MISS"


@dataclass
class CalibrationStats:
    """Aggregated calibration statistics"""
    total_picks: int
    hits: int
    misses: int
    pushes: int
    
    @property
    def hit_rate(self) -> float:
        decided = self.hits + self.misses
        return self.hits / decided if decided > 0 else 0.0
    
    @property
    def decided_picks(self) -> int:
        return self.hits + self.misses


@dataclass
class CalibrationReport:
    """Full calibration report"""
    generated_at: str
    date_range: Tuple[str, str]
    
    # Overall stats
    overall: CalibrationStats
    
    # By stat type
    by_stat: Dict[str, CalibrationStats]
    
    # By tier
    by_tier: Dict[str, CalibrationStats]
    
    # By probability bucket
    by_probability_bucket: Dict[str, CalibrationStats]
    
    # Recent performance (last 7 days)
    last_7_days: Optional[CalibrationStats] = None


# ============================================================
# CALIBRATION TRACKER
# ============================================================

class NHLCalibrationTracker:
    """
    Track and analyze NHL prediction accuracy.
    
    Usage:
        tracker = NHLCalibrationTracker()
        tracker.record_result(...)
        report = tracker.generate_report()
    """
    
    def __init__(self, calibration_file: Path = CALIBRATION_FILE):
        self.calibration_file = calibration_file
        self.results: List[PickResult] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Ensure directory exists
        self.calibration_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing data
        self._load()
    
    def _load(self):
        """Load calibration history from file"""
        if self.calibration_file.exists():
            try:
                with open(self.calibration_file, "r") as f:
                    data = json.load(f)
                    self.results = [PickResult(**r) for r in data.get("results", [])]
                self.logger.info(f"Loaded {len(self.results)} picks from history")
            except Exception as e:
                self.logger.error(f"Failed to load calibration file: {e}")
                self.results = []
        else:
            self.results = []
    
    def _save(self):
        """Save calibration history to file"""
        try:
            data = {
                "updated_at": datetime.now().isoformat(),
                "total_picks": len(self.results),
                "results": [asdict(r) for r in self.results],
            }
            with open(self.calibration_file, "w") as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Saved {len(self.results)} picks to {self.calibration_file}")
        except Exception as e:
            self.logger.error(f"Failed to save calibration file: {e}")
    
    def record_result(
        self,
        player: str,
        team: str,
        opponent: str,
        stat: str,
        line: float,
        direction: str,
        actual_value: float,
        probability: float,
        tier: str,
        pick_date: Optional[str] = None,
        source: str = "underdog",
    ) -> PickResult:
        """
        Record a single pick result.
        
        Args:
            player: Player name
            team: Player's team
            opponent: Opposing team
            stat: Stat type (goals, assists, sog, etc.)
            line: Line value
            direction: OVER or UNDER
            actual_value: Actual stat value
            probability: Model probability (0-1)
            tier: STRONG, LEAN, NO_PLAY
            pick_date: Date (YYYY-MM-DD), defaults to today
            source: Platform source
        
        Returns:
            PickResult object
        """
        if pick_date is None:
            pick_date = date.today().isoformat()
        
        # Determine outcome
        if direction.upper() == "OVER":
            if actual_value > line:
                result = "HIT"
            elif actual_value < line:
                result = "MISS"
            else:
                result = "PUSH"
        else:  # UNDER
            if actual_value < line:
                result = "HIT"
            elif actual_value > line:
                result = "MISS"
            else:
                result = "PUSH"
        
        # Create pick ID
        pick_id = f"{pick_date}_{player}_{stat}_{line}_{direction}".replace(" ", "_").lower()
        
        # Check for duplicate
        if any(r.pick_id == pick_id for r in self.results):
            self.logger.warning(f"Duplicate pick ID: {pick_id}, skipping")
            return None
        
        pick_result = PickResult(
            pick_id=pick_id,
            date=pick_date,
            player=player,
            team=team,
            opponent=opponent,
            stat=stat.lower(),
            line=line,
            direction=direction.upper(),
            actual_value=actual_value,
            probability=probability,
            tier=tier.upper(),
            result=result,
            source=source,
        )
        
        self.results.append(pick_result)
        self._save()
        
        self.logger.info(f"Recorded: {player} {stat} {direction} {line} → {result} ({actual_value})")
        return pick_result
    
    def record_batch(self, picks: List[Dict]) -> int:
        """
        Record multiple results at once.
        
        Args:
            picks: List of pick dictionaries with required fields
        
        Returns:
            Number of successfully recorded picks
        """
        recorded = 0
        for pick in picks:
            try:
                result = self.record_result(**pick)
                if result:
                    recorded += 1
            except Exception as e:
                self.logger.error(f"Failed to record pick: {e}")
        
        return recorded
    
    def _calculate_stats(self, picks: List[PickResult]) -> CalibrationStats:
        """Calculate stats for a list of picks"""
        hits = sum(1 for p in picks if p.result == "HIT")
        misses = sum(1 for p in picks if p.result == "MISS")
        pushes = sum(1 for p in picks if p.result == "PUSH")
        
        return CalibrationStats(
            total_picks=len(picks),
            hits=hits,
            misses=misses,
            pushes=pushes,
        )
    
    def _get_probability_bucket(self, prob: float) -> str:
        """Get probability bucket label"""
        if prob < 0.55:
            return "50-54%"
        elif prob < 0.60:
            return "55-59%"
        elif prob < 0.65:
            return "60-64%"
        elif prob < 0.70:
            return "65-69%"
        elif prob < 0.75:
            return "70-74%"
        else:
            return "75%+"
    
    def generate_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> CalibrationReport:
        """
        Generate calibration report.
        
        Args:
            start_date: Filter from date (YYYY-MM-DD)
            end_date: Filter to date (YYYY-MM-DD)
        
        Returns:
            CalibrationReport
        """
        # Filter by date range
        filtered = self.results
        
        if start_date:
            filtered = [p for p in filtered if p.date >= start_date]
        if end_date:
            filtered = [p for p in filtered if p.date <= end_date]
        
        if not filtered:
            return CalibrationReport(
                generated_at=datetime.now().isoformat(),
                date_range=(start_date or "N/A", end_date or "N/A"),
                overall=CalibrationStats(0, 0, 0, 0),
                by_stat={},
                by_tier={},
                by_probability_bucket={},
            )
        
        # Calculate overall
        overall = self._calculate_stats(filtered)
        
        # By stat type
        by_stat = {}
        stat_groups = defaultdict(list)
        for p in filtered:
            stat_groups[p.stat].append(p)
        for stat, picks in stat_groups.items():
            by_stat[stat] = self._calculate_stats(picks)
        
        # By tier
        by_tier = {}
        tier_groups = defaultdict(list)
        for p in filtered:
            tier_groups[p.tier].append(p)
        for tier, picks in tier_groups.items():
            by_tier[tier] = self._calculate_stats(picks)
        
        # By probability bucket
        by_prob = {}
        prob_groups = defaultdict(list)
        for p in filtered:
            bucket = self._get_probability_bucket(p.probability)
            prob_groups[bucket].append(p)
        for bucket, picks in prob_groups.items():
            by_prob[bucket] = self._calculate_stats(picks)
        
        # Last 7 days
        from datetime import timedelta
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        recent = [p for p in filtered if p.date >= seven_days_ago]
        last_7_days = self._calculate_stats(recent) if recent else None
        
        # Date range
        dates = [p.date for p in filtered]
        date_range = (min(dates), max(dates))
        
        return CalibrationReport(
            generated_at=datetime.now().isoformat(),
            date_range=date_range,
            overall=overall,
            by_stat=by_stat,
            by_tier=by_tier,
            by_probability_bucket=by_prob,
            last_7_days=last_7_days,
        )
    
    def print_report(self, report: Optional[CalibrationReport] = None):
        """Print calibration report to console"""
        if report is None:
            report = self.generate_report()
        
        print("\n" + "=" * 60)
        print("  NHL CALIBRATION REPORT")
        print("=" * 60)
        print(f"  Generated: {report.generated_at[:10]}")
        print(f"  Date Range: {report.date_range[0]} to {report.date_range[1]}")
        
        # Overall
        print("\n  📊 OVERALL PERFORMANCE")
        print("-" * 40)
        o = report.overall
        print(f"    Total Picks: {o.total_picks}")
        print(f"    Hits: {o.hits} | Misses: {o.misses} | Pushes: {o.pushes}")
        print(f"    Hit Rate: {o.hit_rate*100:.1f}%")
        
        # By Tier
        if report.by_tier:
            print("\n  🎯 BY TIER")
            print("-" * 40)
            for tier in ["STRONG", "LEAN", "NO_PLAY"]:
                if tier in report.by_tier:
                    stats = report.by_tier[tier]
                    icon = "🟢" if tier == "STRONG" else ("🟡" if tier == "LEAN" else "🔴")
                    print(f"    {icon} {tier}: {stats.hit_rate*100:.1f}% ({stats.hits}/{stats.decided_picks})")
        
        # By Stat
        if report.by_stat:
            print("\n  📈 BY STAT TYPE")
            print("-" * 40)
            for stat, stats in sorted(report.by_stat.items()):
                print(f"    {stat.upper():10s} {stats.hit_rate*100:.1f}% ({stats.hits}/{stats.decided_picks})")
        
        # By Probability
        if report.by_probability_bucket:
            print("\n  📉 BY PROBABILITY BUCKET")
            print("-" * 40)
            for bucket in ["50-54%", "55-59%", "60-64%", "65-69%", "70-74%", "75%+"]:
                if bucket in report.by_probability_bucket:
                    stats = report.by_probability_bucket[bucket]
                    print(f"    {bucket}: {stats.hit_rate*100:.1f}% ({stats.hits}/{stats.decided_picks})")
        
        # Last 7 days
        if report.last_7_days:
            print("\n  📅 LAST 7 DAYS")
            print("-" * 40)
            l7 = report.last_7_days
            print(f"    Picks: {l7.total_picks} | Hit Rate: {l7.hit_rate*100:.1f}%")
        
        print("\n" + "=" * 60)
    
    def export_csv(self, filepath: Optional[Path] = None) -> Path:
        """Export calibration history to CSV"""
        if filepath is None:
            filepath = CALIBRATION_CSV
        
        import csv
        
        fieldnames = [
            "date", "player", "team", "opponent", "stat", "line",
            "direction", "probability", "tier", "actual_value", "result",
        ]
        
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for r in self.results:
                writer.writerow({
                    "date": r.date,
                    "player": r.player,
                    "team": r.team,
                    "opponent": r.opponent,
                    "stat": r.stat,
                    "line": r.line,
                    "direction": r.direction,
                    "probability": r.probability,
                    "tier": r.tier,
                    "actual_value": r.actual_value,
                    "result": r.result,
                })
        
        self.logger.info(f"Exported {len(self.results)} picks to {filepath}")
        return filepath
    
    def get_stat_accuracy(self, stat: str) -> float:
        """Get hit rate for a specific stat type"""
        stat_picks = [p for p in self.results if p.stat.lower() == stat.lower()]
        if not stat_picks:
            return 0.0
        
        stats = self._calculate_stats(stat_picks)
        return stats.hit_rate
    
    def get_tier_accuracy(self, tier: str) -> float:
        """Get hit rate for a specific tier"""
        tier_picks = [p for p in self.results if p.tier.upper() == tier.upper()]
        if not tier_picks:
            return 0.0
        
        stats = self._calculate_stats(tier_picks)
        return stats.hit_rate


# ============================================================
# CLI TESTING
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  NHL CALIBRATION TRACKER — TEST")
    print("=" * 60)
    
    tracker = NHLCalibrationTracker()
    
    # Add some test data
    test_picks = [
        {
            "player": "Connor McDavid", "team": "EDM", "opponent": "CGY",
            "stat": "points", "line": 1.5, "direction": "OVER",
            "actual_value": 3, "probability": 0.68, "tier": "STRONG",
            "pick_date": "2025-02-01",
        },
        {
            "player": "Leon Draisaitl", "team": "EDM", "opponent": "CGY",
            "stat": "goals", "line": 0.5, "direction": "OVER",
            "actual_value": 1, "probability": 0.62, "tier": "STRONG",
            "pick_date": "2025-02-01",
        },
        {
            "player": "Auston Matthews", "team": "TOR", "opponent": "BOS",
            "stat": "sog", "line": 4.5, "direction": "OVER",
            "actual_value": 3, "probability": 0.60, "tier": "LEAN",
            "pick_date": "2025-02-01",
        },
        {
            "player": "William Nylander", "team": "TOR", "opponent": "BOS",
            "stat": "sog", "line": 3.5, "direction": "OVER",
            "actual_value": 5, "probability": 0.64, "tier": "STRONG",
            "pick_date": "2025-02-02",
        },
    ]
    
    print(f"\n  Recording {len(test_picks)} test picks...")
    recorded = tracker.record_batch(test_picks)
    print(f"  Recorded: {recorded}")
    
    # Generate and print report
    report = tracker.generate_report()
    tracker.print_report(report)
    
    # Export CSV
    csv_path = tracker.export_csv()
    print(f"\n  Exported to: {csv_path}")
    
    print("\n" + "=" * 60)
