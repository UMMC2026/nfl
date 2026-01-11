#!/usr/bin/env python3
"""
Resolve Yesterday's Picks

Fetches actual game results and resolves pending picks from yesterday.
Updates the results tracker with HIT/MISS/PUSH outcomes.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add ufa to path
sys.path.insert(0, str(Path(__file__).parent))

from ufa.analysis.results_tracker import ResultsTracker, TrackedPick


def resolve_yesterdays_picks():
    """Resolve all pending picks from yesterday."""

    # Initialize trackers
    tracker = ResultsTracker()
    service_tracker = None

    try:
        from ufa.services.results_tracker import ResultsTracker as ServiceTracker
        service_tracker = ServiceTracker()
    except ImportError:
        print("⚠️  Service tracker not available, using manual resolution only")
        service_tracker = None

    # Get yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_str = yesterday.strftime("%Y-%m-%d")

    print(f"🔍 Resolving picks for {date_str}")

    # Load yesterday's picks
    picks = tracker.load_picks(date_str)

    if not picks:
        print(f"ℹ️  No picks found for {date_str}")
        return

    print(f"📋 Found {len(picks)} picks to resolve")

    resolved_count = 0
    results = []

    for pick in picks:
        if pick.result not in ["PENDING", "UNKNOWN"]:
            print(f"⏭️  {pick.player} {pick.stat} already resolved: {pick.result}")
            continue

        # Fetch actual stat
        actual_value = None

        if service_tracker:
            try:
                # Assume NBA for now - could be extended for other leagues
                actual_value = service_tracker.fetch_actual_stat(
                    league="NBA",
                    player=pick.player,
                    stat=pick.stat,
                    game_date=yesterday
                )
            except Exception as e:
                print(f"❌ Error fetching stat for {pick.player}: {e}")

        if actual_value is None:
            print(f"❓ No data available for {pick.player} {pick.stat}")
            continue

        # Determine result
        result = determine_result(pick, actual_value)

        print(f"✅ {pick.player} {pick.stat}: {actual_value:.1f} {result}")

        # Update tracker
        tracker.update_result(
            date=date_str,
            player=pick.player,
            stat=pick.stat,
            result=result,
            actual_value=actual_value
        )

        results.append({
            "player": pick.player,
            "stat": pick.stat,
            "result": result,
            "actual_value": actual_value
        })

        resolved_count += 1

    print(f"\n🎯 Resolved {resolved_count} picks for {date_str}")

    # Show summary
    if results:
        hits = sum(1 for r in results if r["result"] == "HIT")
        misses = sum(1 for r in results if r["result"] == "MISS")
        pushes = sum(1 for r in results if r["result"] == "PUSH")

        win_rate = hits / (hits + misses) if (hits + misses) > 0 else 0

        print(f"📊 Results: {hits}-{misses}-{pushes} ({win_rate:.1%})")


def determine_result(pick: TrackedPick, actual_value: float) -> str:
    """Determine HIT/MISS/PUSH based on pick and actual value."""

    line = pick.line
    direction = pick.direction

    if direction == "higher":
        if actual_value > line:
            return "HIT"
        elif actual_value < line:
            return "MISS"
        else:
            return "PUSH"
    elif direction == "lower":
        if actual_value < line:
            return "HIT"
        elif actual_value > line:
            return "MISS"
        else:
            return "PUSH"
    else:
        return "UNKNOWN"


if __name__ == "__main__":
    resolve_yesterdays_picks()