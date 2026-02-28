from pathlib import Path
import json

# Check stats cache
pattern = "outputs/stats_cache/nba_mu_sigma_L10_L5_blend*_auto_*.json"
cache_files = sorted(Path(".").glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
print(f"Found {len(cache_files)} cache files")
if cache_files:
    print(f"Latest: {cache_files[0]}")
    cache = json.loads(cache_files[0].read_text())
    print(f"Players in cache: {len(cache)}")
    # Check if Pascal Siakam has usage data
    if "Pascal Siakam" in cache:
        ps = cache["Pascal Siakam"]
        print(f"Pascal Siakam data:")
        for key, value in ps.items():
            print(f"  {key}: {value}")
    else:
        print("Pascal Siakam not in cache")
        print("First 5 players:", list(cache.keys())[:5])
