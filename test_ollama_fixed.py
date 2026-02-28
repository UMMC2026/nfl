import sys
import time
sys.path.insert(0, 'c:/Users/hiday/UNDERDOG ANANLYSIS')

from engine.nfl_ai_integration import NFL_AIAnalyzer

print("Testing Ollama with FIXED streaming configuration...")
print("-" * 60)

analyzer = NFL_AIAnalyzer()

test_game = {
    "away": "Kansas City Chiefs",
    "home": "Buffalo Bills",
    "datetime": "2026-01-13 20:00:00",
    "away_stats": {"offense_rank": 3, "defense_rank": 12},
    "home_stats": {"offense_rank": 5, "defense_rank": 8}
}

test_props = [
    {"player": "Patrick Mahomes", "stat": "pass_yds", "line": 275.5}
]

start_time = time.time()
result = analyzer.get_ollama_commentary(test_game, test_props)
elapsed = time.time() - start_time

print(f"\n✅ Response received in {elapsed:.1f} seconds")
print(f"\nResponse length: {len(result)} chars")
print(f"\nFull response:\n{'-'*60}\n{result}\n{'-'*60}")
