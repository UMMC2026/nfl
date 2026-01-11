"""
Yesterday's Results Tracker

Tracks historical performance of picks to show users how previous recommendations hit.
Stores results in JSON format and generates performance reports.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from enum import Enum


class PickResult(Enum):
    """Result of a pick."""
    HIT = "✅"
    MISS = "❌"
    PUSH = "🔄"
    PENDING = "⏳"
    UNKNOWN = "❓"


@dataclass
class TrackedPick:
    """A pick with its result."""
    date: str
    player: str
    team: str
    stat: str
    line: float
    direction: str
    tier: str  # SLAM, STRONG, LEAN, etc.
    confidence: float  # Calibrated confidence
    result: str = "PENDING"  # HIT, MISS, PUSH, PENDING
    actual_value: Optional[float] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "TrackedPick":
        return cls(**d)


@dataclass
class DailyPerformance:
    """Performance summary for a single day."""
    date: str
    total_picks: int
    hits: int
    misses: int
    pushes: int
    pending: int
    slam_record: tuple[int, int]  # (hits, total)
    strong_record: tuple[int, int]
    lean_record: tuple[int, int]
    roi_units: float
    resolved_count: int = 0  # Total resolved picks (HIT + MISS + PUSH)
    
    @property
    def win_rate(self) -> float:
        decided = self.hits + self.misses
        return self.hits / decided if decided > 0 else 0.0
    
    @property
    def slam_rate(self) -> float:
        total = self.slam_record[1]
        return self.slam_record[0] / total if total > 0 else 0.0


class ResultsTracker:
    """
    Tracks pick results over time.
    
    Stores results in JSON files in data_center/results/
    """
    
    def __init__(self, data_dir: str = "data_center/results"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, date: str) -> Path:
        """Get file path for a specific date's results."""
        return self.data_dir / f"results_{date}.json"
    
    def save_picks(self, picks: list[TrackedPick], date: str = None):
        """
        Save picks for tracking.
        
        Args:
            picks: List of TrackedPick objects
            date: Date string (YYYY-MM-DD), defaults to today
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        file_path = self._get_file_path(date)
        
        data = {
            "date": date,
            "saved_at": datetime.now().isoformat(),
            "picks": [p.to_dict() for p in picks]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved {len(picks)} picks for {date}")
    
    def load_picks(self, date: str) -> list[TrackedPick]:
        """Load picks for a specific date."""
        file_path = self._get_file_path(date)
        
        if not file_path.exists():
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return [TrackedPick.from_dict(p) for p in data.get("picks", [])]
    
    def update_result(self, date: str, player: str, stat: str, 
                      result: str, actual_value: float = None):
        """
        Update the result for a specific pick.
        
        Args:
            date: Date of the pick
            player: Player name
            stat: Stat type
            result: "HIT", "MISS", "PUSH"
            actual_value: Actual stat value achieved
        """
        picks = self.load_picks(date)
        
        for pick in picks:
            if pick.player == player and pick.stat == stat:
                pick.result = result
                pick.actual_value = actual_value
                break
        
        # Re-save
        file_path = self._get_file_path(date)
        data = {
            "date": date,
            "updated_at": datetime.now().isoformat(),
            "picks": [p.to_dict() for p in picks]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def bulk_update_results(self, date: str, results: list[dict]):
        """
        Update multiple results at once.
        
        Args:
            date: Date of picks
            results: List of dicts with player, stat, result, actual_value
        """
        for r in results:
            self.update_result(
                date=date,
                player=r["player"],
                stat=r["stat"],
                result=r["result"],
                actual_value=r.get("actual_value")
            )
    
    def get_daily_performance(self, date: str) -> Optional[DailyPerformance]:
        """Calculate performance for a specific date."""
        picks = self.load_picks(date)
        
        if not picks:
            return None
        
        hits = sum(1 for p in picks if p.result == "HIT")
        misses = sum(1 for p in picks if p.result == "MISS")
        pushes = sum(1 for p in picks if p.result == "PUSH")
        pending = sum(1 for p in picks if p.result in ["PENDING", "UNKNOWN"])
        resolved = hits + misses + pushes  # Total decided picks
        
        slam_hits = sum(1 for p in picks if p.tier == "SLAM" and p.result == "HIT")
        slam_total = sum(1 for p in picks if p.tier == "SLAM" and p.result in ["HIT", "MISS"])
        
        strong_hits = sum(1 for p in picks if p.tier == "STRONG" and p.result == "HIT")
        strong_total = sum(1 for p in picks if p.tier == "STRONG" and p.result in ["HIT", "MISS"])
        
        lean_hits = sum(1 for p in picks if p.tier == "LEAN" and p.result == "HIT")
        lean_total = sum(1 for p in picks if p.tier == "LEAN" and p.result in ["HIT", "MISS"])
        
        # Simple ROI: +1 unit per hit, -1 per miss
        roi = hits - misses
        
        return DailyPerformance(
            date=date,
            total_picks=len(picks),
            hits=hits,
            misses=misses,
            pushes=pushes,
            pending=pending,
            slam_record=(slam_hits, slam_total),
            strong_record=(strong_hits, strong_total),
            lean_record=(lean_hits, lean_total),
            roi_units=roi,
            resolved_count=resolved
        )
    
    def get_yesterday_performance(self) -> Optional[DailyPerformance]:
        """Get performance for yesterday."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return self.get_daily_performance(yesterday)
    
    def get_rolling_performance(self, days: int = 7) -> dict:
        """Get rolling performance over last N days."""
        total_hits = 0
        total_misses = 0
        total_pushes = 0
        slam_hits = 0
        slam_total = 0
        strong_hits = 0
        strong_total = 0
        days_with_data = 0
        
        for i in range(1, days + 1):  # Start from yesterday
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            perf = self.get_daily_performance(date)
            
            if perf:
                days_with_data += 1
                total_hits += perf.hits
                total_misses += perf.misses
                total_pushes += perf.pushes
                slam_hits += perf.slam_record[0]
                slam_total += perf.slam_record[1]
                strong_hits += perf.strong_record[0]
                strong_total += perf.strong_record[1]
        
        decided = total_hits + total_misses
        
        return {
            "days": days_with_data,
            "total_picks": total_hits + total_misses + total_pushes,
            "hits": total_hits,
            "misses": total_misses,
            "win_rate": total_hits / decided if decided > 0 else 0,
            "slam_rate": slam_hits / slam_total if slam_total > 0 else 0,
            "strong_rate": strong_hits / strong_total if strong_total > 0 else 0,
            "roi_units": total_hits - total_misses
        }
    
    def format_yesterday_block(self) -> str:
        """Generate formatted yesterday's performance block for cheat sheet."""
        perf = self.get_yesterday_performance()
        
        if not perf:
            return "📈 YESTERDAY'S PERFORMANCE\n   No picks tracked yet\n"
        
        lines = [
            f"📈 YESTERDAY'S PERFORMANCE ({perf.date})",
            "=" * 50
        ]
        
        # Show resolved vs pending (truth indicator)
        lines.append(f"  Status: {perf.resolved_count} resolved | {perf.pending} pending")
        
        # Only show record if we have resolved picks
        if perf.resolved_count > 0:
            win_pct = perf.win_rate * 100
            lines.append(f"  Resolved Record: {perf.hits}-{perf.misses} ({win_pct:.0f}%)")
            
            # By tier (only if picks in that tier are resolved)
            if perf.slam_record[1] > 0:
                slam_pct = perf.slam_rate * 100
                lines.append(f"  SLAM Plays: {perf.slam_record[0]}/{perf.slam_record[1]} ({slam_pct:.0f}%)")
            
            if perf.strong_record[1] > 0:
                strong_pct = perf.strong_record[0] / perf.strong_record[1] * 100
                lines.append(f"  STRONG Plays: {perf.strong_record[0]}/{perf.strong_record[1]} ({strong_pct:.0f}%)")
            
            if perf.lean_record[1] > 0:
                lean_pct = perf.lean_record[0] / perf.lean_record[1] * 100
                lines.append(f"  LEAN Plays: {perf.lean_record[0]}/{perf.lean_record[1]} ({lean_pct:.0f}%)")
            
            # ROI
            roi_sign = "+" if perf.roi_units >= 0 else ""
            lines.append(f"  ROI (resolved): {roi_sign}{perf.roi_units:.1f} units")
        else:
            lines.append(f"  ⏳ Waiting for game results...")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def format_rolling_block(self, days: int = 7) -> str:
        """Generate rolling performance block."""
        stats = self.get_rolling_performance(days)
        
        if stats["days"] == 0:
            return f"📊 LAST {days} DAYS\n   No data available\n"
        
        lines = [
            f"📊 LAST {days} DAYS ({stats['days']} days with data)",
            "=" * 50
        ]
        
        win_pct = stats["win_rate"] * 100
        lines.append(f"  Overall: {stats['hits']}-{stats['misses']} ({win_pct:.0f}%)")
        
        if stats["slam_rate"] > 0:
            slam_pct = stats["slam_rate"] * 100
            lines.append(f"  SLAM Hit Rate: {slam_pct:.0f}%")
        
        roi_sign = "+" if stats["roi_units"] >= 0 else ""
        lines.append(f"  Total ROI: {roi_sign}{stats['roi_units']:.1f} units")
        
        lines.append("")
        
        return "\n".join(lines)


# Test
if __name__ == "__main__":
    tracker = ResultsTracker()
    
    # Create sample picks for yesterday
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    sample_picks = [
        TrackedPick(
            date=yesterday,
            player="OG Anunoby",
            team="NYK",
            stat="points",
            line=16.5,
            direction="higher",
            tier="STRONG",
            confidence=0.66,
            result="HIT",
            actual_value=22
        ),
        TrackedPick(
            date=yesterday,
            player="LeBron James",
            team="LAL",
            stat="assists",
            line=8.5,
            direction="lower",
            tier="SLAM",
            confidence=0.70,
            result="HIT",
            actual_value=6
        ),
        TrackedPick(
            date=yesterday,
            player="Tyrese Maxey",
            team="PHI",
            stat="points",
            line=25.5,
            direction="higher",
            tier="LEAN",
            confidence=0.58,
            result="MISS",
            actual_value=22
        ),
    ]
    
    # Save
    tracker.save_picks(sample_picks, yesterday)
    
    # Get performance
    print(tracker.format_yesterday_block())
    print(tracker.format_rolling_block(7))
