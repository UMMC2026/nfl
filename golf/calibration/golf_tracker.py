"""
Golf Calibration Tracker
========================
Track golf pick results to validate prediction accuracy.
Answers: "Do 78% picks actually win 78% of the time?"
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

GOLF_DIR = Path(__file__).parent.parent
CALIBRATION_FILE = GOLF_DIR / "data" / "golf_calibration_history.csv"
CALIBRATION_FILE.parent.mkdir(exist_ok=True)


@dataclass
class GolfPick:
    """A golf pick for calibration tracking."""
    pick_id: str
    tournament: str
    round_num: int
    player: str
    market: str  # round_strokes, birdies, finishing_position
    line: float
    direction: str  # higher, lower, better
    probability: float
    tier: str
    
    # Result fields (filled in after event)
    actual_value: Optional[float] = None
    outcome: Optional[str] = None  # HIT, MISS, PUSH, VOID
    result_date: Optional[str] = None
    
    # Metadata
    created_at: str = ""
    notes: str = ""


class GolfCalibrationTracker:
    """Track and analyze golf pick calibration."""
    
    def __init__(self):
        self.picks: List[GolfPick] = []
        self._load_history()
    
    def _load_history(self):
        """Load calibration history from CSV."""
        if CALIBRATION_FILE.exists():
            with open(CALIBRATION_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pick = GolfPick(
                        pick_id=row.get('pick_id', ''),
                        tournament=row.get('tournament', ''),
                        round_num=int(row.get('round_num', 0) or 0),
                        player=row.get('player', ''),
                        market=row.get('market', ''),
                        line=float(row.get('line', 0) or 0),
                        direction=row.get('direction', ''),
                        probability=float(row.get('probability', 0) or 0),
                        tier=row.get('tier', ''),
                        actual_value=float(row['actual_value']) if row.get('actual_value') else None,
                        outcome=row.get('outcome') or None,
                        result_date=row.get('result_date') or None,
                        created_at=row.get('created_at', ''),
                        notes=row.get('notes', ''),
                    )
                    self.picks.append(pick)
    
    def save(self):
        """Save calibration history to CSV."""
        with open(CALIBRATION_FILE, 'w', newline='') as f:
            fieldnames = [
                'pick_id', 'tournament', 'round_num', 'player', 'market',
                'line', 'direction', 'probability', 'tier',
                'actual_value', 'outcome', 'result_date', 'created_at', 'notes'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for pick in self.picks:
                writer.writerow(asdict(pick))
    
    def add_pick(self, pick: GolfPick):
        """Add a new pick for tracking."""
        if not pick.created_at:
            pick.created_at = datetime.now().isoformat()
        self.picks.append(pick)
        self.save()
    
    def add_picks_from_edges(self, edges: List[Dict], tournament: str = ""):
        """Add multiple picks from edge output."""
        for edge in edges:
            if edge.get("pick_state") == "OPTIMIZABLE":
                pick = GolfPick(
                    pick_id=edge.get("edge_id", ""),
                    tournament=tournament or edge.get("tournament", ""),
                    round_num=edge.get("round_num", 0),
                    player=edge.get("player", ""),
                    market=edge.get("market", ""),
                    line=edge.get("line", 0),
                    direction=edge.get("direction", ""),
                    probability=edge.get("probability", 0),
                    tier=edge.get("tier", ""),
                    created_at=datetime.now().isoformat(),
                )
                self.picks.append(pick)
        self.save()
    
    def resolve_pick(
        self,
        pick_id: str,
        actual_value: float,
        outcome: str = None
    ):
        """
        Resolve a pick with actual result.
        
        Args:
            pick_id: The pick ID to resolve
            actual_value: The actual stat value (score, birdies, position)
            outcome: Optional override (HIT, MISS, PUSH, VOID)
        """
        for pick in self.picks:
            if pick.pick_id == pick_id:
                pick.actual_value = actual_value
                pick.result_date = datetime.now().strftime("%Y-%m-%d")
                
                # Determine outcome if not provided
                if outcome is None:
                    outcome = self._determine_outcome(pick, actual_value)
                
                pick.outcome = outcome
                break
        
        self.save()
    
    def _determine_outcome(self, pick: GolfPick, actual: float) -> str:
        """Determine HIT/MISS/PUSH based on actual value."""
        line = pick.line
        direction = pick.direction.lower()
        
        if pick.market == "finishing_position":
            # Better = lower position number
            if direction == "better":
                if actual < line:
                    return "HIT"
                elif actual == line:
                    return "PUSH"
                else:
                    return "MISS"
        else:
            # Standard higher/lower
            if direction == "higher":
                if actual > line:
                    return "HIT"
                elif actual == line:
                    return "PUSH"
                else:
                    return "MISS"
            else:  # lower
                if actual < line:
                    return "HIT"
                elif actual == line:
                    return "PUSH"
                else:
                    return "MISS"
        
        return "MISS"
    
    def get_pending_picks(self) -> List[GolfPick]:
        """Get picks awaiting resolution."""
        return [p for p in self.picks if p.outcome is None]
    
    def get_resolved_picks(self) -> List[GolfPick]:
        """Get resolved picks."""
        return [p for p in self.picks if p.outcome is not None]
    
    def calibration_report(self) -> Dict:
        """
        Generate calibration report.
        
        Shows: predicted probability buckets vs actual hit rates.
        """
        resolved = self.get_resolved_picks()
        
        if not resolved:
            return {"error": "No resolved picks to analyze"}
        
        # Bucket by probability range
        buckets = {
            "50-55%": {"predicted": 0.525, "picks": [], "hits": 0, "total": 0},
            "55-60%": {"predicted": 0.575, "picks": [], "hits": 0, "total": 0},
            "60-65%": {"predicted": 0.625, "picks": [], "hits": 0, "total": 0},
            "65-70%": {"predicted": 0.675, "picks": [], "hits": 0, "total": 0},
            "70-75%": {"predicted": 0.725, "picks": [], "hits": 0, "total": 0},
            "75-80%": {"predicted": 0.775, "picks": [], "hits": 0, "total": 0},
            "80%+": {"predicted": 0.825, "picks": [], "hits": 0, "total": 0},
        }
        
        for pick in resolved:
            prob = pick.probability
            if 0.50 <= prob < 0.55:
                bucket = "50-55%"
            elif 0.55 <= prob < 0.60:
                bucket = "55-60%"
            elif 0.60 <= prob < 0.65:
                bucket = "60-65%"
            elif 0.65 <= prob < 0.70:
                bucket = "65-70%"
            elif 0.70 <= prob < 0.75:
                bucket = "70-75%"
            elif 0.75 <= prob < 0.80:
                bucket = "75-80%"
            else:
                bucket = "80%+"
            
            buckets[bucket]["picks"].append(pick)
            buckets[bucket]["total"] += 1
            if pick.outcome == "HIT":
                buckets[bucket]["hits"] += 1
        
        # Calculate actual rates
        report = {
            "total_picks": len(resolved),
            "total_hits": sum(1 for p in resolved if p.outcome == "HIT"),
            "overall_hit_rate": sum(1 for p in resolved if p.outcome == "HIT") / len(resolved) if resolved else 0,
            "buckets": {},
            "calibration_score": 0,
        }
        
        calibration_errors = []
        for bucket_name, data in buckets.items():
            if data["total"] > 0:
                actual_rate = data["hits"] / data["total"]
                predicted = data["predicted"]
                error = abs(actual_rate - predicted)
                calibration_errors.append(error)
                
                report["buckets"][bucket_name] = {
                    "predicted": f"{predicted*100:.1f}%",
                    "actual": f"{actual_rate*100:.1f}%",
                    "count": data["total"],
                    "hits": data["hits"],
                    "error": f"{error*100:.1f}%",
                }
        
        # Calibration score (lower is better, 0 = perfect)
        if calibration_errors:
            report["calibration_score"] = sum(calibration_errors) / len(calibration_errors)
        
        return report
    
    def tier_performance(self) -> Dict:
        """Analyze performance by tier."""
        resolved = self.get_resolved_picks()
        
        tiers = defaultdict(lambda: {"hits": 0, "total": 0, "avg_prob": 0})
        
        for pick in resolved:
            tier = pick.tier
            tiers[tier]["total"] += 1
            tiers[tier]["avg_prob"] += pick.probability
            if pick.outcome == "HIT":
                tiers[tier]["hits"] += 1
        
        result = {}
        for tier, data in tiers.items():
            if data["total"] > 0:
                result[tier] = {
                    "hit_rate": f"{data['hits']/data['total']*100:.1f}%",
                    "avg_predicted": f"{data['avg_prob']/data['total']*100:.1f}%",
                    "count": data["total"],
                    "hits": data["hits"],
                }
        
        return result
    
    def market_performance(self) -> Dict:
        """Analyze performance by market type."""
        resolved = self.get_resolved_picks()
        
        markets = defaultdict(lambda: {"hits": 0, "total": 0})
        
        for pick in resolved:
            market = pick.market
            markets[market]["total"] += 1
            if pick.outcome == "HIT":
                markets[market]["hits"] += 1
        
        return {
            market: {
                "hit_rate": f"{data['hits']/data['total']*100:.1f}%",
                "count": data["total"],
            }
            for market, data in markets.items()
            if data["total"] > 0
        }
    
    def print_report(self):
        """Print formatted calibration report."""
        report = self.calibration_report()
        
        print("=" * 60)
        print("⛳ GOLF CALIBRATION REPORT")
        print("=" * 60)
        
        if "error" in report:
            print(f"\n{report['error']}")
            return
        
        print(f"\nTotal Resolved: {report['total_picks']}")
        print(f"Overall Hit Rate: {report['overall_hit_rate']*100:.1f}%")
        print(f"Calibration Score: {report['calibration_score']*100:.2f}% (lower = better)")
        
        print("\n📊 CALIBRATION BY PROBABILITY BUCKET:")
        print("-" * 50)
        print(f"{'Bucket':<12} {'Predicted':<12} {'Actual':<12} {'Count':<8} {'Error'}")
        print("-" * 50)
        
        for bucket, data in report["buckets"].items():
            print(f"{bucket:<12} {data['predicted']:<12} {data['actual']:<12} {data['count']:<8} {data['error']}")
        
        print("\n📈 TIER PERFORMANCE:")
        tier_perf = self.tier_performance()
        for tier, data in tier_perf.items():
            print(f"  {tier}: {data['hit_rate']} actual vs {data['avg_predicted']} predicted ({data['count']} picks)")
        
        print("\n🎯 MARKET PERFORMANCE:")
        market_perf = self.market_performance()
        for market, data in market_perf.items():
            print(f"  {market}: {data['hit_rate']} ({data['count']} picks)")


def get_golf_tracker() -> GolfCalibrationTracker:
    """Get the golf calibration tracker singleton."""
    return GolfCalibrationTracker()


if __name__ == "__main__":
    tracker = get_golf_tracker()
    
    print(f"Loaded {len(tracker.picks)} picks")
    print(f"Pending: {len(tracker.get_pending_picks())}")
    print(f"Resolved: {len(tracker.get_resolved_picks())}")
    
    if tracker.get_resolved_picks():
        tracker.print_report()
    else:
        print("\nNo resolved picks yet. Add picks and resolve them to see calibration data.")
