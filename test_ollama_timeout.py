import requests
import time

# Test Ollama with a realistic long prompt
prompt = """
As an NFL analyst, provide detailed commentary for this matchup:
GAME: Kansas City Chiefs @ Buffalo Bills
TIME: 2026-01-13 20:00:00
TEAM STATS:
- Kansas City Chiefs: {"offense_rank": 3, "defense_rank": 12}
- Buffalo Bills: {"offense_rank": 5, "defense_rank": 8}
KEY PROPS TO ANALYZE:
[{"player": "Patrick Mahomes", "stat": "pass_yds", "line": 275.5}]
Provide 3-4 paragraphs covering:
1. Coaching matchup and scheme implications
2. Key player matchups to watch
3. Weather/field conditions impact
4. Betting angles and edges
Format with clear sections and bullet points where appropriate.
"""

print("Testing Ollama with realistic prompt...")
start_time = time.time()

try:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama2",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 1500
            }
        },
        timeout=60  # Increased to 60 seconds
    )
    elapsed = time.time() - start_time
    print(f"\n✅ SUCCESS in {elapsed:.1f} seconds")
    print(f"\nResponse length: {len(response.json().get('response', ''))} chars")
    print(f"\nFirst 200 chars:\n{response.json().get('response', '')[:200]}")
except requests.exceptions.Timeout:
    elapsed = time.time() - start_time
    print(f"\n❌ TIMEOUT after {elapsed:.1f} seconds")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\n❌ ERROR after {elapsed:.1f} seconds: {str(e)}")
