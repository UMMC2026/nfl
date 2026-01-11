"""
UFA Learning Loop - Results Analysis & Model Refinement

Analyzes historical pick results to identify patterns, biases, and opportunities
for model improvement. Integrates with Sportsdata.io for bulk historical stats
and SerpApi for contextual analysis of anomalies.

This creates a self-improving feedback loop that transforms UFA from a static
prediction engine into a learning system.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict, Counter

from ufa.analysis.results_tracker import ResultsTracker, TrackedPick, DailyPerformance


@dataclass
class PatternAnalysis:
    """Analysis of a specific pattern in the data."""
    pattern_type: str  # e.g., "stat_type", "player", "tier"
    pattern_value: str  # e.g., "points", "LeBron James", "SLAM"
    total_picks: int
    hits: int
    misses: int
    pushes: int
    win_rate: float
    avg_confidence: float
    avg_line: float
    suggestion: str  # What to adjust


@dataclass
class LearningReport:
    """Complete learning analysis report."""
    analysis_date: str
    days_analyzed: int
    total_picks: int
    overall_win_rate: float
    patterns: List[PatternAnalysis]
    anomalies: List[Dict]  # Large misses that need investigation
    recommendations: List[str]


class UFALearningLoop:
    """
    Self-improving learning system for UFA predictions.

    Analyzes historical results to find systematic biases and suggest
    model refinements. Integrates with external APIs for context.
    """

    def __init__(self, data_dir: str = "data_center/results"):
        self.tracker = ResultsTracker(data_dir)
        self.sportsdata_api_key = None  # Will be loaded from config
        self.serpapi_api_key = None     # Will be loaded from config

    async def run_nightly_learning(self, date: str = None) -> LearningReport:
        """
        Main nightly learning method.

        Args:
            date: Date to analyze (YYYY-MM-DD), defaults to yesterday

        Returns:
            Complete learning report with patterns and recommendations
        """
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        print(f"🔍 Starting learning analysis for {date}")

        # 1. Gather historical results (last 30 days for pattern analysis)
        historical_picks = self._gather_historical_picks(date, days_back=30)

        if not historical_picks:
            print("❌ No historical data available for learning")
            return self._create_empty_report(date)

        # 2. Analyze patterns
        patterns = self._analyze_patterns(historical_picks)

        # 3. Identify anomalies (large misses)
        anomalies = self._identify_anomalies(historical_picks)

        # 4. Generate recommendations
        recommendations = self._generate_recommendations(patterns, anomalies)

        # 5. Create comprehensive report
        report = LearningReport(
            analysis_date=datetime.now().strftime("%Y-%m-%d"),
            days_analyzed=len(set(p.date for p in historical_picks)),
            total_picks=len(historical_picks),
            overall_win_rate=self._calculate_overall_win_rate(historical_picks),
            patterns=patterns,
            anomalies=anomalies,
            recommendations=recommendations
        )

        # 6. Save report
        self._save_learning_report(report)

        print(f"✅ Learning analysis complete. Found {len(patterns)} patterns, {len(anomalies)} anomalies")
        return report

    def _gather_historical_picks(self, target_date: str, days_back: int = 30) -> List[TrackedPick]:
        """Gather resolved picks from recent history."""
        all_picks = []

        for i in range(days_back):
            date = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_picks = self.tracker.load_picks(date)

            # Only include resolved picks
            resolved_picks = [p for p in daily_picks if p.result in ["HIT", "MISS", "PUSH"]]
            all_picks.extend(resolved_picks)

        return all_picks

    def _analyze_patterns(self, picks: List[TrackedPick]) -> List[PatternAnalysis]:
        """Analyze picks for systematic patterns and biases."""
        patterns = []

        # Analyze by stat type
        stat_patterns = self._analyze_by_dimension(picks, "stat")
        patterns.extend(stat_patterns)

        # Analyze by tier
        tier_patterns = self._analyze_by_dimension(picks, "tier")
        patterns.extend(tier_patterns)

        # Analyze by direction (over/under)
        direction_patterns = self._analyze_by_dimension(picks, "direction")
        patterns.extend(direction_patterns)

        # Analyze by line range (buckets)
        line_patterns = self._analyze_by_line_range(picks)
        patterns.extend(line_patterns)

        return patterns

    def _analyze_by_dimension(self, picks: List[TrackedPick], dimension: str) -> List[PatternAnalysis]:
        """Analyze picks grouped by a specific dimension."""
        groups = defaultdict(list)

        for pick in picks:
            key = getattr(pick, dimension)
            groups[key].append(pick)

        patterns = []
        for value, group_picks in groups.items():
            if len(group_picks) < 3:  # Need minimum sample size (reduced for testing)
                continue

            hits = sum(1 for p in group_picks if p.result == "HIT")
            misses = sum(1 for p in group_picks if p.result == "MISS")
            pushes = sum(1 for p in group_picks if p.result == "PUSH")

            total_decided = hits + misses
            win_rate = hits / total_decided if total_decided > 0 else 0

            avg_confidence = sum(p.confidence for p in group_picks) / len(group_picks)
            avg_line = sum(p.line for p in group_picks) / len(group_picks)

            # Generate suggestion based on performance
            suggestion = self._generate_pattern_suggestion(
                dimension, value, win_rate, avg_confidence, len(group_picks)
            )

            patterns.append(PatternAnalysis(
                pattern_type=dimension,
                pattern_value=str(value),
                total_picks=len(group_picks),
                hits=hits,
                misses=misses,
                pushes=pushes,
                win_rate=win_rate,
                avg_confidence=avg_confidence,
                avg_line=avg_line,
                suggestion=suggestion
            ))

        return patterns

    def _analyze_by_line_range(self, picks: List[TrackedPick]) -> List[PatternAnalysis]:
        """Analyze performance by line value ranges."""
        # Bucket lines into ranges
        buckets = {
            "0-5": (0, 5),
            "5-10": (5, 10),
            "10-15": (10, 15),
            "15-20": (15, 20),
            "20-25": (20, 25),
            "25+": (25, float('inf'))
        }

        patterns = []
        for bucket_name, (min_val, max_val) in buckets.items():
            bucket_picks = [p for p in picks if min_val <= p.line < max_val]

            if len(bucket_picks) < 2:  # Reduced for testing
                continue

            hits = sum(1 for p in bucket_picks if p.result == "HIT")
            misses = sum(1 for p in bucket_picks if p.result == "MISS")
            pushes = sum(1 for p in bucket_picks if p.result == "PUSH")

            total_decided = hits + misses
            win_rate = hits / total_decided if total_decided > 0 else 0

            avg_confidence = sum(p.confidence for p in bucket_picks) / len(bucket_picks)

            suggestion = self._generate_line_range_suggestion(bucket_name, win_rate, len(bucket_picks))

            patterns.append(PatternAnalysis(
                pattern_type="line_range",
                pattern_value=bucket_name,
                total_picks=len(bucket_picks),
                hits=hits,
                misses=misses,
                pushes=pushes,
                win_rate=win_rate,
                avg_confidence=avg_confidence,
                avg_line=sum(p.line for p in bucket_picks) / len(bucket_picks),
                suggestion=suggestion
            ))

        return patterns

    def _generate_pattern_suggestion(self, dimension: str, value: str,
                                   win_rate: float, avg_confidence: float,
                                   sample_size: int) -> str:
        """Generate actionable suggestions based on pattern analysis."""

        # Expected win rate baseline (should be > 50% for profitable system)
        baseline = 0.52

        if win_rate > baseline + 0.05:
            return f"✅ Strong performer ({win_rate:.1%} win rate). Consider increasing confidence allocation."
        elif win_rate < baseline - 0.05:
            return f"⚠️ Underperforming ({win_rate:.1%} win rate). Consider reducing confidence or adjusting model."
        else:
            return f"📊 Neutral performance ({win_rate:.1%} win rate). Monitor for changes."

    def _generate_line_range_suggestion(self, bucket: str, win_rate: float, sample_size: int) -> str:
        """Generate suggestions for line range performance."""
        baseline = 0.52

        if win_rate > baseline + 0.03:
            return f"🎯 Sweet spot for {bucket} lines. Higher success rate suggests good model fit."
        elif win_rate < baseline - 0.03:
            return f"⚠️ Challenging range for {bucket} lines. May need line-specific adjustments."
        else:
            return f"📊 Standard performance for {bucket} lines."

    def _identify_anomalies(self, picks: List[TrackedPick]) -> List[Dict]:
        """Identify anomalous results that need investigation."""
        anomalies = []

        for pick in picks:
            if pick.result != "MISS":
                continue

            # Calculate how far off the miss was
            if pick.direction == "higher":
                deviation = pick.line - pick.actual_value
            else:  # lower
                deviation = pick.actual_value - pick.line

            # Flag large deviations (more than 5 units off)
            if deviation > 5:
                anomalies.append({
                    "player": pick.player,
                    "stat": pick.stat,
                    "line": pick.line,
                    "direction": pick.direction,
                    "expected": pick.line,
                    "actual": pick.actual_value,
                    "deviation": deviation,
                    "confidence": pick.confidence,
                    "date": pick.date,
                    "needs_investigation": True
                })

        # Sort by deviation (largest misses first)
        anomalies.sort(key=lambda x: x["deviation"], reverse=True)

        return anomalies[:10]  # Top 10 anomalies

    def _generate_recommendations(self, patterns: List[PatternAnalysis],
                                anomalies: List[Dict]) -> List[str]:
        """Generate actionable recommendations for model improvement."""
        recommendations = []

        # Pattern-based recommendations
        underperformers = [p for p in patterns if p.win_rate < 0.47 and p.total_picks >= 10]

        for pattern in underperformers:
            if pattern.pattern_type == "stat":
                recommendations.append(
                    f"Review {pattern.pattern_value} modeling - {pattern.win_rate:.1%} win rate "
                    f"({pattern.total_picks} picks). Consider stat-specific adjustments."
                )
            elif pattern.pattern_type == "tier":
                recommendations.append(
                    f"Re-evaluate {pattern.pattern_value} tier criteria - {pattern.win_rate:.1%} win rate. "
                    f"May need confidence threshold adjustments."
                )

        # Anomaly-based recommendations
        if anomalies:
            recommendations.append(
                f"Investigate {len(anomalies)} large misses using contextual analysis. "
                f"Check for injuries, matchups, or model blind spots."
            )

        # Overall system health - use actual picks from the analysis
        all_analyzed_picks = []
        for pattern in patterns:
            # This is approximate - we'd need to pass actual picks
            pass
        overall_win_rate = sum(p.win_rate * p.total_picks for p in patterns) / sum(p.total_picks for p in patterns) if patterns else 0.5

        if overall_win_rate > 0.55:
            recommendations.append("✅ System performing well above baseline. Focus on scaling and refinement.")
        elif overall_win_rate < 0.50:
            recommendations.append("⚠️ System below baseline. Prioritize core model improvements.")

        return recommendations

    def _calculate_overall_win_rate(self, picks: List[TrackedPick]) -> float:
        """Calculate overall win rate from picks."""
        decided_picks = [p for p in picks if p.result in ["HIT", "MISS"]]
        if not decided_picks:
            return 0.0

        hits = sum(1 for p in decided_picks if p.result == "HIT")
        return hits / len(decided_picks)

    def _create_empty_report(self, date: str) -> LearningReport:
        """Create empty report when no data available."""
        return LearningReport(
            analysis_date=date,
            days_analyzed=0,
            total_picks=0,
            overall_win_rate=0.0,
            patterns=[],
            anomalies=[],
            recommendations=["No historical data available for analysis"]
        )

    def _save_learning_report(self, report: LearningReport):
        """Save learning report to file."""
        reports_dir = Path("data_center/learning_reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        filename = f"learning_report_{report.analysis_date}.json"
        filepath = reports_dir / filename

        # Convert to dict for JSON serialization
        report_dict = {
            "analysis_date": report.analysis_date,
            "days_analyzed": report.days_analyzed,
            "total_picks": report.total_picks,
            "overall_win_rate": report.overall_win_rate,
            "patterns": [vars(p) for p in report.patterns],
            "anomalies": report.anomalies,
            "recommendations": report.recommendations
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, default=str)

        print(f"Saved learning report to {filepath}")

    async def investigate_anomaly(self, anomaly: Dict) -> Dict:
        """
        Deep investigation of a specific anomaly using external APIs.

        Uses SerpApi to search for contextual information about why
        a pick missed badly.
        """
        if not self.serpapi_api_key:
            return {"error": "SerpApi key not configured"}

        try:
            # This would integrate with SerpApi for contextual search
            # For now, return placeholder
            return {
                "player": anomaly["player"],
                "investigation": "Contextual analysis not yet implemented",
                "recommendations": ["Integrate SerpApi for game recap analysis"]
            }
        except Exception as e:
            return {"error": f"Investigation failed: {str(e)}"}


# CLI interface
async def main():
    """Run learning analysis for yesterday."""
    loop = UFALearningLoop()
    report = await loop.run_nightly_learning()

    # Print summary
    print(f"\n📊 LEARNING REPORT SUMMARY")
    print(f"Date: {report.analysis_date}")
    print(f"Days Analyzed: {report.days_analyzed}")
    print(f"Total Picks: {report.total_picks}")
    print(f"Overall Win Rate: {report.overall_win_rate:.1%}")

    print(f"\n🔍 Key Patterns Found: {len(report.patterns)}")
    for pattern in report.patterns[:5]:  # Show top 5
        print(f"  {pattern.pattern_type}:{pattern.pattern_value} - {pattern.win_rate:.1%} win rate")

    print(f"\n⚠️ Anomalies to Investigate: {len(report.anomalies)}")

    print(f"\n💡 Recommendations:")
    for rec in report.recommendations:
        print(f"  • {rec}")


if __name__ == "__main__":
    asyncio.run(main())