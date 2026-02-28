"""
SEGMENTED CALIBRATION TRACKER — Priority 2 Implementation
==========================================================

Tracks calibration by multiple segments instead of aggregate.

Segments:
- By tier (SLAM, STRONG, LEAN, SPEC)
- By stat type (points, assists, rebounds, etc.)
- By sport (NBA, NHL, Golf, etc.)
- By book (Underdog, PrizePicks, DraftKings)
- By direction (higher/lower)
- By archetype (if applicable)
- By season period (early, mid, late)

Phase: 5B
Created: 2026-02-05
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import csv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PickOutcome:
    """Record of a single pick outcome."""
    pick_id: str
    sport: str
    player: str
    stat: str
    line: float
    direction: str
    tier: str
    probability: float
    edge: float
    book: str
    
    # Outcome
    result: str  # "win", "loss", "push", "void"
    actual_value: Optional[float] = None
    
    # Metadata
    date: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    archetype: str = ""
    season_period: str = ""  # "early", "mid", "late", "playoffs"
    
    # Optional context
    game_id: str = ""
    opponent: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "pick_id": self.pick_id,
            "sport": self.sport,
            "player": self.player,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "tier": self.tier,
            "probability": self.probability,
            "edge": self.edge,
            "book": self.book,
            "result": self.result,
            "actual_value": self.actual_value,
            "date": self.date,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "archetype": self.archetype,
            "season_period": self.season_period,
            "game_id": self.game_id,
            "opponent": self.opponent,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PickOutcome":
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()
        
        return cls(
            pick_id=data.get("pick_id", ""),
            sport=data.get("sport", ""),
            player=data.get("player", ""),
            stat=data.get("stat", ""),
            line=data.get("line", 0.0),
            direction=data.get("direction", ""),
            tier=data.get("tier", ""),
            probability=data.get("probability", 0.0),
            edge=data.get("edge", 0.0),
            book=data.get("book", ""),
            result=data.get("result", ""),
            actual_value=data.get("actual_value"),
            date=data.get("date", ""),
            timestamp=timestamp,
            archetype=data.get("archetype", ""),
            season_period=data.get("season_period", ""),
            game_id=data.get("game_id", ""),
            opponent=data.get("opponent", ""),
        )


@dataclass
class SegmentStats:
    """Statistics for a calibration segment."""
    segment_key: str
    segment_value: str
    
    total_picks: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    voids: int = 0
    
    # Rate metrics
    win_rate: float = 0.0
    expected_win_rate: float = 0.0  # Based on probabilities
    
    # Edge metrics
    total_edge: float = 0.0
    avg_edge: float = 0.0
    realized_edge: float = 0.0  # Actual vs expected
    
    # Calibration metrics
    calibration_error: float = 0.0  # |expected - actual|
    overconfidence: float = 0.0     # expected - actual (positive = overconfident)
    
    # Trend
    recent_win_rate: float = 0.0    # Last 10 picks
    trend: str = ""                  # "improving", "declining", "stable"
    
    def to_dict(self) -> Dict:
        return {
            "segment_key": self.segment_key,
            "segment_value": self.segment_value,
            "total_picks": self.total_picks,
            "wins": self.wins,
            "losses": self.losses,
            "pushes": self.pushes,
            "voids": self.voids,
            "win_rate": round(self.win_rate, 4),
            "expected_win_rate": round(self.expected_win_rate, 4),
            "total_edge": round(self.total_edge, 2),
            "avg_edge": round(self.avg_edge, 2),
            "realized_edge": round(self.realized_edge, 2),
            "calibration_error": round(self.calibration_error, 4),
            "overconfidence": round(self.overconfidence, 4),
            "recent_win_rate": round(self.recent_win_rate, 4),
            "trend": self.trend,
        }


# =============================================================================
# SEGMENTED CALIBRATION TRACKER
# =============================================================================

class SegmentedCalibrationTracker:
    """
    Track calibration performance by multiple segments.
    
    Segments analyzed:
    - tier: SLAM, STRONG, LEAN, SPEC
    - stat: points, assists, rebounds, 3pm, etc.
    - sport: NBA, NHL, Golf, CBB, etc.
    - book: underdog, prizepicks, draftkings
    - direction: higher, lower
    - archetype: player archetypes
    - season_period: early, mid, late, playoffs
    """
    
    def __init__(self, data_file: Path = None):
        self.data_file = data_file or PROJECT_ROOT / "calibration" / "segmented_outcomes.json"
        self.outcomes: List[PickOutcome] = []
        self._load_data()
    
    def _load_data(self):
        """Load historical outcomes."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    self.outcomes = [PickOutcome.from_dict(o) for o in data.get("outcomes", [])]
                logger.info(f"Loaded {len(self.outcomes)} outcomes from {self.data_file}")
            except Exception as e:
                logger.error(f"Failed to load calibration data: {e}")
                self.outcomes = []
        else:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _save_data(self):
        """Save outcomes to file."""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "total_outcomes": len(self.outcomes),
                "outcomes": [o.to_dict() for o in self.outcomes],
            }
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save calibration data: {e}")
    
    def add_outcome(self, outcome: PickOutcome):
        """Add a new outcome."""
        self.outcomes.append(outcome)
        self._save_data()
    
    def add_outcomes_batch(self, outcomes: List[PickOutcome]):
        """Add multiple outcomes."""
        self.outcomes.extend(outcomes)
        self._save_data()
    
    def _calculate_segment_stats(
        self,
        outcomes: List[PickOutcome],
        segment_key: str,
        segment_value: str,
    ) -> SegmentStats:
        """Calculate statistics for a segment."""
        stats = SegmentStats(
            segment_key=segment_key,
            segment_value=segment_value,
        )
        
        if not outcomes:
            return stats
        
        # Count outcomes
        stats.total_picks = len(outcomes)
        stats.wins = sum(1 for o in outcomes if o.result == "win")
        stats.losses = sum(1 for o in outcomes if o.result == "loss")
        stats.pushes = sum(1 for o in outcomes if o.result == "push")
        stats.voids = sum(1 for o in outcomes if o.result == "void")
        
        # Win rate (exclude pushes and voids)
        decided = stats.wins + stats.losses
        if decided > 0:
            stats.win_rate = stats.wins / decided
        
        # Expected win rate (average probability)
        probs = [o.probability for o in outcomes if o.probability > 0]
        if probs:
            stats.expected_win_rate = sum(probs) / len(probs)
        
        # Edge metrics
        edges = [o.edge for o in outcomes if o.edge > 0]
        if edges:
            stats.total_edge = sum(edges)
            stats.avg_edge = stats.total_edge / len(edges)
        
        # Realized edge (actual ROI)
        if decided > 0:
            # Simple ROI: wins pay 1:1, losses lose 1 unit
            stats.realized_edge = (stats.wins - stats.losses) / decided * 100
        
        # Calibration metrics
        stats.calibration_error = abs(stats.expected_win_rate - stats.win_rate)
        stats.overconfidence = stats.expected_win_rate - stats.win_rate
        
        # Recent trend (last 10 picks)
        recent = sorted(outcomes, key=lambda o: o.timestamp, reverse=True)[:10]
        recent_decided = [o for o in recent if o.result in ("win", "loss")]
        if recent_decided:
            recent_wins = sum(1 for o in recent_decided if o.result == "win")
            stats.recent_win_rate = recent_wins / len(recent_decided)
            
            # Determine trend
            if len(outcomes) >= 20:
                older = sorted(outcomes, key=lambda o: o.timestamp, reverse=True)[10:20]
                older_decided = [o for o in older if o.result in ("win", "loss")]
                if older_decided:
                    older_wins = sum(1 for o in older_decided if o.result == "win")
                    older_win_rate = older_wins / len(older_decided)
                    
                    diff = stats.recent_win_rate - older_win_rate
                    if diff > 0.05:
                        stats.trend = "improving"
                    elif diff < -0.05:
                        stats.trend = "declining"
                    else:
                        stats.trend = "stable"
        
        return stats
    
    def get_segment_breakdown(
        self,
        segment_key: str,
        sport: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, SegmentStats]:
        """
        Get breakdown by a specific segment.
        
        Args:
            segment_key: One of: tier, stat, sport, book, direction, archetype, season_period
            sport: Optional filter by sport
            date_from: Optional filter start date
            date_to: Optional filter end date
        
        Returns:
            Dict mapping segment values to their stats
        """
        # Filter outcomes
        filtered = self.outcomes
        
        if sport:
            filtered = [o for o in filtered if o.sport.upper() == sport.upper()]
        
        if date_from:
            filtered = [o for o in filtered if o.date >= date_from]
        
        if date_to:
            filtered = [o for o in filtered if o.date <= date_to]
        
        # Group by segment
        groups: Dict[str, List[PickOutcome]] = defaultdict(list)
        
        for outcome in filtered:
            segment_value = getattr(outcome, segment_key, "unknown")
            if segment_value:
                groups[segment_value].append(outcome)
        
        # Calculate stats for each group
        result = {}
        for segment_value, outcomes in groups.items():
            result[segment_value] = self._calculate_segment_stats(
                outcomes, segment_key, segment_value
            )
        
        return result
    
    def get_full_report(
        self,
        sport: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict:
        """
        Generate full calibration report with all segments.
        
        Returns nested structure with all segment breakdowns.
        """
        segments = ["tier", "stat", "sport", "book", "direction"]
        
        # Optional segments
        if any(o.archetype for o in self.outcomes):
            segments.append("archetype")
        if any(o.season_period for o in self.outcomes):
            segments.append("season_period")
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "filters": {
                "sport": sport,
                "date_from": date_from,
                "date_to": date_to,
            },
            "overall": self._get_overall_stats(sport, date_from, date_to),
            "segments": {},
        }
        
        for segment in segments:
            breakdown = self.get_segment_breakdown(segment, sport, date_from, date_to)
            report["segments"][segment] = {
                k: v.to_dict() for k, v in breakdown.items()
            }
        
        return report
    
    def _get_overall_stats(
        self,
        sport: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict:
        """Get overall statistics (not segmented)."""
        filtered = self.outcomes
        
        if sport:
            filtered = [o for o in filtered if o.sport.upper() == sport.upper()]
        if date_from:
            filtered = [o for o in filtered if o.date >= date_from]
        if date_to:
            filtered = [o for o in filtered if o.date <= date_to]
        
        stats = self._calculate_segment_stats(filtered, "overall", "all")
        return stats.to_dict()
    
    def get_problem_segments(
        self,
        min_picks: int = 10,
        max_calibration_error: float = 0.10,
        sport: Optional[str] = None,
    ) -> List[Dict]:
        """
        Identify segments with poor calibration.
        
        Returns segments where:
        - Calibration error > threshold
        - Or overconfidence > 0.05 (predicting too high)
        - Or declining trend
        """
        problems = []
        
        for segment_key in ["tier", "stat", "book", "direction"]:
            breakdown = self.get_segment_breakdown(segment_key, sport)
            
            for segment_value, stats in breakdown.items():
                if stats.total_picks < min_picks:
                    continue
                
                issues = []
                
                if stats.calibration_error > max_calibration_error:
                    issues.append(f"High calibration error: {stats.calibration_error:.1%}")
                
                if stats.overconfidence > 0.05:
                    issues.append(f"Overconfident by {stats.overconfidence:.1%}")
                
                if stats.trend == "declining":
                    issues.append("Declining trend")
                
                if issues:
                    problems.append({
                        "segment_key": segment_key,
                        "segment_value": segment_value,
                        "issues": issues,
                        "stats": stats.to_dict(),
                        "priority": len(issues),
                    })
        
        # Sort by priority (most issues first)
        problems.sort(key=lambda x: x["priority"], reverse=True)
        
        return problems
    
    def export_csv(self, output_file: Path = None) -> Path:
        """Export outcomes to CSV for external analysis."""
        output_file = output_file or PROJECT_ROOT / "outputs" / "calibration_export.csv"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.outcomes:
            logger.warning("No outcomes to export")
            return output_file
        
        fieldnames = [
            "pick_id", "date", "sport", "player", "stat", "line", 
            "direction", "tier", "probability", "edge", "book",
            "result", "actual_value", "archetype", "season_period"
        ]
        
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for outcome in self.outcomes:
                row = {k: getattr(outcome, k, "") for k in fieldnames}
                writer.writerow(row)
        
        logger.info(f"Exported {len(self.outcomes)} outcomes to {output_file}")
        return output_file
    
    def print_dashboard(self, sport: Optional[str] = None):
        """Print calibration dashboard to console."""
        print("\n" + "=" * 70)
        print("SEGMENTED CALIBRATION DASHBOARD")
        if sport:
            print(f"Sport: {sport.upper()}")
        print("=" * 70)
        
        # Overall stats
        overall = self._get_overall_stats(sport)
        print(f"\n📊 OVERALL ({overall['total_picks']} picks)")
        print(f"   Win Rate: {overall['win_rate']:.1%} (expected: {overall['expected_win_rate']:.1%})")
        print(f"   Calibration Error: {overall['calibration_error']:.1%}")
        if overall['overconfidence'] > 0:
            print(f"   ⚠️ Overconfident by {overall['overconfidence']:.1%}")
        
        # By tier
        print("\n📈 BY TIER:")
        tier_breakdown = self.get_segment_breakdown("tier", sport)
        for tier, stats in sorted(tier_breakdown.items()):
            if stats.total_picks >= 5:
                status = "✅" if stats.calibration_error < 0.10 else "⚠️"
                print(f"   {status} {tier}: {stats.win_rate:.1%} ({stats.total_picks} picks) "
                      f"— expected {stats.expected_win_rate:.1%}")
        
        # By stat
        print("\n📈 BY STAT:")
        stat_breakdown = self.get_segment_breakdown("stat", sport)
        for stat, stats in sorted(stat_breakdown.items(), key=lambda x: x[1].total_picks, reverse=True)[:8]:
            if stats.total_picks >= 5:
                status = "✅" if stats.win_rate >= stats.expected_win_rate * 0.9 else "⚠️"
                print(f"   {status} {stat}: {stats.win_rate:.1%} ({stats.total_picks} picks)")
        
        # Problem segments
        print("\n⚠️ PROBLEM SEGMENTS:")
        problems = self.get_problem_segments(min_picks=10, sport=sport)
        if problems:
            for problem in problems[:5]:
                print(f"   [{problem['segment_key']}={problem['segment_value']}]: {', '.join(problem['issues'])}")
        else:
            print("   ✅ No major issues detected")
        
        print("\n" + "=" * 70)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_tracker: Optional[SegmentedCalibrationTracker] = None


def get_tracker() -> SegmentedCalibrationTracker:
    """Get or create global tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = SegmentedCalibrationTracker()
    return _tracker


def add_pick_outcome(
    pick_id: str,
    sport: str,
    player: str,
    stat: str,
    line: float,
    direction: str,
    tier: str,
    probability: float,
    edge: float,
    book: str,
    result: str,
    actual_value: float = None,
    **kwargs,
):
    """Add a single pick outcome."""
    outcome = PickOutcome(
        pick_id=pick_id,
        sport=sport,
        player=player,
        stat=stat,
        line=line,
        direction=direction,
        tier=tier,
        probability=probability,
        edge=edge,
        book=book,
        result=result,
        actual_value=actual_value,
        date=kwargs.get("date", datetime.now().strftime("%Y-%m-%d")),
        archetype=kwargs.get("archetype", ""),
        season_period=kwargs.get("season_period", ""),
    )
    get_tracker().add_outcome(outcome)


def get_calibration_report(sport: Optional[str] = None) -> Dict:
    """Get full calibration report."""
    return get_tracker().get_full_report(sport)


def print_calibration_dashboard(sport: Optional[str] = None):
    """Print calibration dashboard."""
    get_tracker().print_dashboard(sport)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI for calibration tracker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Segmented Calibration Tracker")
    parser.add_argument("--sport", help="Filter by sport")
    parser.add_argument("--export", action="store_true", help="Export to CSV")
    parser.add_argument("--problems", action="store_true", help="Show problem segments")
    parser.add_argument("--add-test-data", action="store_true", help="Add test data")
    
    args = parser.parse_args()
    
    tracker = get_tracker()
    
    if args.add_test_data:
        # Add sample outcomes for testing
        import random
        
        sports = ["NBA", "NHL", "Golf", "CBB"]
        stats = ["points", "assists", "rebounds", "3pm", "sog", "round_strokes"]
        tiers = ["SLAM", "STRONG", "LEAN"]
        books = ["underdog", "prizepicks"]
        directions = ["higher", "lower"]
        
        for i in range(50):
            sport = random.choice(sports)
            tier = random.choice(tiers)
            prob = {"SLAM": 0.80, "STRONG": 0.68, "LEAN": 0.58}[tier]
            prob += random.uniform(-0.05, 0.05)
            
            # Simulate outcomes (slightly underperforming predictions)
            win = random.random() < (prob - 0.03)
            
            outcome = PickOutcome(
                pick_id=f"test_{i}",
                sport=sport,
                player=f"Player_{i % 10}",
                stat=random.choice(stats),
                line=random.uniform(10, 30),
                direction=random.choice(directions),
                tier=tier,
                probability=prob,
                edge=prob * 100 - 50,
                book=random.choice(books),
                result="win" if win else "loss",
                date=(datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
            )
            tracker.outcomes.append(outcome)
        
        tracker._save_data()
        print(f"Added 50 test outcomes. Total: {len(tracker.outcomes)}")
    
    if args.export:
        output = tracker.export_csv()
        print(f"Exported to {output}")
    
    if args.problems:
        problems = tracker.get_problem_segments(sport=args.sport)
        print("\n⚠️ PROBLEM SEGMENTS:")
        for p in problems[:10]:
            print(f"\n{p['segment_key']}={p['segment_value']}:")
            for issue in p['issues']:
                print(f"   - {issue}")
            print(f"   Stats: {p['stats']['total_picks']} picks, "
                  f"{p['stats']['win_rate']:.1%} win rate")
    else:
        tracker.print_dashboard(args.sport)


if __name__ == "__main__":
    main()
