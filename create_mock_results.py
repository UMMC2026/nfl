"""
Create mock resolved results for testing the learning loop.
"""

from ufa.analysis.results_tracker import ResultsTracker, TrackedPick

def create_mock_resolved_data():
    """Create some mock resolved picks for testing."""

    tracker = ResultsTracker()

    # Create mock resolved picks for 2026-01-04
    mock_picks = [
        TrackedPick(
            date="2026-01-04",
            player="OG Anunoby",
            team="NYK",
            stat="points",
            line=16.5,
            direction="higher",
            tier="SLAM",
            confidence=0.75,
            result="HIT",
            actual_value=22.0
        ),
        TrackedPick(
            date="2026-01-04",
            player="OG Anunoby",
            team="NYK",
            stat="pts+reb+ast",
            line=25.5,
            direction="higher",
            tier="STRONG",
            confidence=0.75,
            result="MISS",
            actual_value=18.0
        ),
        TrackedPick(
            date="2026-01-04",
            player="Jamal Shead",
            team="TOR",
            stat="points",
            line=7.5,
            direction="higher",
            tier="SLAM",
            confidence=0.75,
            result="HIT",
            actual_value=12.0
        ),
        TrackedPick(
            date="2026-01-04",
            player="Giannis Antetokounmpo",
            team="MIL",
            stat="points",
            line=27.5,
            direction="higher",
            tier="SLAM",
            confidence=0.75,
            result="MISS",
            actual_value=22.0  # Large miss for anomaly detection
        ),
        TrackedPick(
            date="2026-01-04",
            player="LeBron James",
            team="LAL",
            stat="assists",
            line=8.5,
            direction="lower",
            tier="LEAN",
            confidence=0.58,
            result="HIT",
            actual_value=6.0
        ),
        TrackedPick(
            date="2026-01-04",
            player="Tyrese Maxey",
            team="PHI",
            stat="points",
            line=25.5,
            direction="higher",
            tier="LEAN",
            confidence=0.58,
            result="MISS",
            actual_value=19.0
        ),
        TrackedPick(
            date="2026-01-03",
            player="Luka Doncic",
            team="DAL",
            stat="points",
            line=28.5,
            direction="higher",
            tier="SLAM",
            confidence=0.80,
            result="HIT",
            actual_value=35.0
        ),
        TrackedPick(
            date="2026-01-03",
            player="Luka Doncic",
            team="DAL",
            stat="assists",
            line=9.5,
            direction="higher",
            tier="STRONG",
            confidence=0.70,
            result="HIT",
            actual_value=12.0
        ),
        TrackedPick(
            date="2026-01-03",
            player="Stephen Curry",
            team="GSW",
            stat="3pm",
            line=4.5,
            direction="higher",
            tier="LEAN",
            confidence=0.55,
            result="MISS",
            actual_value=2.0
        )
    ]

    # Save the mock data
    tracker.save_picks(mock_picks[:6], "2026-01-04")  # First 6 for Jan 4
    tracker.save_picks(mock_picks[6:], "2026-01-03")  # Last 3 for Jan 3

    print("✅ Created mock resolved data for testing")
    print("📊 2026-01-04: 6 picks (mix of HIT/MISS)")
    print("📊 2026-01-03: 3 picks (mostly HIT)")

if __name__ == "__main__":
    create_mock_resolved_data()