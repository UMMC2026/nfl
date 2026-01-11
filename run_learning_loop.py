"""
Run UFA Learning Loop Analysis

Analyzes historical pick results to identify patterns and generate
recommendations for model improvement.

Usage:
    python run_learning_loop.py                    # Analyze yesterday
    python run_learning_loop.py --date 2024-01-15  # Analyze specific date
    python run_learning_loop.py --days 14          # Analyze last N days
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from ufa.analysis.results_learning_loop import UFALearningLoop


def main():
    parser = argparse.ArgumentParser(description="Run UFA Learning Loop Analysis")
    parser.add_argument(
        "--date",
        type=str,
        help="Date to analyze (YYYY-MM-DD). Defaults to yesterday."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of historical data to analyze. Default: 30"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for detailed report. Default: auto-generated"
    )

    args = parser.parse_args()

    # Determine target date
    if args.date:
        target_date = args.date
    else:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"🎯 UFA Learning Loop Analysis")
    print(f"Target Date: {target_date}")
    print(f"Analysis Window: {args.days} days")
    print("-" * 50)

    # Initialize learning loop
    loop = UFALearningLoop()

    # Run analysis
    try:
        report = asyncio.run(loop.run_nightly_learning(target_date))

        # Print summary to console
        print(f"\n📊 ANALYSIS RESULTS")
        print(f"Analysis Date: {report.analysis_date}")
        print(f"Days Analyzed: {report.days_analyzed}")
        print(f"Total Picks: {report.total_picks}")
        print(f"Overall Win Rate: {report.overall_win_rate:.1%}")

        print(f"\n🔍 PATTERNS IDENTIFIED ({len(report.patterns)})")
        if report.patterns:
            # Group by type
            by_type = {}
            for pattern in report.patterns:
                if pattern.pattern_type not in by_type:
                    by_type[pattern.pattern_type] = []
                by_type[pattern.pattern_type].append(pattern)

            for pattern_type, patterns in by_type.items():
                print(f"\n{pattern_type.upper()} PATTERNS:")
                # Sort by win rate
                patterns.sort(key=lambda x: x.win_rate, reverse=True)
                for pattern in patterns[:3]:  # Top 3 per type
                    print(f"  {pattern.pattern_value}: {pattern.win_rate:.1%} "
                          f"({pattern.hits}-{pattern.misses}, {pattern.total_picks} picks)")
                    print(f"    💡 {pattern.suggestion}")
        else:
            print("  No significant patterns found (need more data)")

        print(f"\n⚠️ ANOMALIES TO INVESTIGATE ({len(report.anomalies)})")
        if report.anomalies:
            for anomaly in report.anomalies[:5]:  # Top 5
                print(f"  {anomaly['player']} {anomaly['stat']}: "
                      f"Expected {anomaly['expected']:.1f}, Got {anomaly['actual']:.1f} "
                      f"(off by {anomaly['deviation']:.1f})")
        else:
            print("  No major anomalies detected")

        print(f"\n💡 RECOMMENDATIONS")
        if report.recommendations:
            for rec in report.recommendations:
                print(f"  • {rec}")
        else:
            print("  No specific recommendations at this time")

        # Save detailed report if requested
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = Path(f"learning_report_{target_date}.txt")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"UFA Learning Loop Report - {report.analysis_date}\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Analysis Summary:\n")
            f.write(f"- Target Date: {target_date}\n")
            f.write(f"- Days Analyzed: {report.days_analyzed}\n")
            f.write(f"- Total Picks: {report.total_picks}\n")
            f.write(f"- Overall Win Rate: {report.overall_win_rate:.1%}\n\n")

            f.write(f"Detailed Patterns:\n")
            for pattern in report.patterns:
                f.write(f"- {pattern.pattern_type}:{pattern.pattern_value}\n")
                f.write(f"  Win Rate: {pattern.win_rate:.1%} ({pattern.hits}-{pattern.misses})\n")
                f.write(f"  Sample Size: {pattern.total_picks} picks\n")
                f.write(f"  Avg Confidence: {pattern.avg_confidence:.2f}\n")
                f.write(f"  Suggestion: {pattern.suggestion}\n\n")

            f.write(f"Anomalies:\n")
            for anomaly in report.anomalies:
                f.write(f"- {anomaly['player']} {anomaly['stat']}: "
                       f"Expected {anomaly['expected']:.1f}, Got {anomaly['actual']:.1f} "
                       f"(deviation: {anomaly['deviation']:.1f})\n")

            f.write(f"\nRecommendations:\n")
            for rec in report.recommendations:
                f.write(f"- {rec}\n")

        print(f"\n📄 Detailed report saved to: {output_path}")

    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()