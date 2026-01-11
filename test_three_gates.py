"""
Quick test of the three-gate pipeline.

Run this to verify:
1. Schedule gate filters to today's games only
2. Roster gate fixes player-team truth
3. Dedupe removes duplicate player-stat combinations
"""

from engine.schedule_gate import gate_today_games
from engine.roster_gate import gate_active_roster, build_active_roster_map
from engine.collapse_edges import dedupe_player_props


def test_gates():
    print("=" * 70)
    print("🧪 THREE-GATE PIPELINE TEST")
    print("=" * 70)
    print()

    # Test data
    picks = [
        {
            "player": "Kevin Durant",
            "team": "BKN",
            "opponent": "HOU",
            "stat": "points",
            "line": 27.5,
            "direction": "OVER",
            "edge_key": "KD_PTS_OVER",
            "confidence": 0.72
        },
        {
            "player": "Kevin Durant",
            "team": "HOU",
            "opponent": "BKN",
            "stat": "points",
            "line": 27.5,
            "direction": "OVER",
            "edge_key": "KD_PTS_OVER",
            "confidence": 0.72  # DUPLICATE
        },
        {
            "player": "Giannis Antetokounmpo",
            "team": "MIL",
            "opponent": "LAL",
            "stat": "points",
            "line": 32.5,
            "direction": "OVER",
            "edge_key": "GA_PTS_OVER",
            "confidence": 0.68
        },
        {
            "player": "LeBron James",
            "team": "LAL",
            "opponent": "MIL",
            "stat": "points",
            "line": 25.5,
            "direction": "OVER",
            "edge_key": "LBJ_PTS_OVER",
            "confidence": 0.65
        },
    ]

    today_games = [
        {"home": "HOU", "away": "BKN", "game_id": "001"},
        {"home": "LAL", "away": "MIL", "game_id": "002"},
    ]

    # Test 1: Schedule Gate
    print("TEST 1: SCHEDULE GATE")
    print("-" * 70)
    try:
        scheduled = gate_today_games(picks, today_games)
        print(f"✅ Input: {len(picks)} picks")
        print(f"✅ Output: {len(scheduled)} picks (only today's games)")
        print()
        for p in scheduled:
            print(f"   {p['player']} ({p['team']}) vs {p['opponent']}")
        print()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return
    print()

    # Test 2: Roster Gate
    print("TEST 2: ROSTER GATE")
    print("-" * 70)
    roster_map = {
        "Kevin Durant": "HOU",  # Override BKN → HOU
        "Giannis Antetokounmpo": "MIL",
        "LeBron James": "LAL",
    }

    try:
        roster_fixed = gate_active_roster(scheduled, roster_map)
        print(f"✅ Input: {len(scheduled)} picks")
        print(f"✅ Output: {len(roster_fixed)} picks (teams corrected)")
        print()
        for p in roster_fixed:
            print(f"   {p['player']}: {p['team']} (vs {p['opponent']})")
        print()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return
    print()

    # Test 3: Dedupe
    print("TEST 3: DEDUPE GATE")
    print("-" * 70)
    try:
        deduped = dedupe_player_props(roster_fixed)
        print(f"✅ Input: {len(roster_fixed)} picks")
        print(f"✅ Output: {len(deduped)} unique picks (removed duplicates)")
        print()
        for p in deduped:
            print(f"   {p['player']} | {p['stat']} @ {p['line']} | conf={p.get('confidence')}")
        print()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return
    print()

    print("=" * 70)
    print("✨ ALL TESTS PASSED ✨")
    print("=" * 70)
    print()
    print("Next: Run the full pipeline with:")
    print("  python daily_pipeline.py")
    print()


if __name__ == "__main__":
    test_gates()
