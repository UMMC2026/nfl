"""Check ESPN API response for Solomon Washington."""
import requests, json

core_base = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"

# First find Solomon Washington's ESPN ID from the cache
import sys
sys.path.insert(0, ".")
from sports.cbb.ingest.cbb_data_provider import CBBDataProvider

provider = CBBDataProvider()

# Check the current cache entry
from sports.cbb.ingest.cbb_data_provider import CBBStatsCache
cache = CBBStatsCache()
cached = cache.get_player_stats("Solomon Washington", "MD")
print("=== CACHED DATA ===")
print(json.dumps(cached, indent=2, default=str))

# Now let's try the ESPN API with season parameter
# Try to get Maryland's roster first to find player ID
print("\n=== FINDING PLAYER ID ===")
# Maryland team ID in ESPN = 120
roster_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/120/roster"
r = requests.get(roster_url, timeout=10)
if r.ok:
    data = r.json()
    for ath in data.get("athletes", []):
        name = ath.get("fullName", "")
        if "washington" in name.lower() and "solomon" in name.lower():
            pid = ath.get("id", "")
            print(f"Found: {name} (ID: {pid})")
            
            # Now try default stats endpoint
            stats_url = f"{core_base}/athletes/{pid}/statistics?lang=en&region=us"
            print(f"\n=== DEFAULT STATS ({stats_url}) ===")
            r2 = requests.get(stats_url, timeout=10)
            if r2.ok:
                sdata = r2.json()
                splits = sdata.get("splits", {})
                for cat in splits.get("categories", []):
                    cat_name = cat.get("displayName", "")
                    for s in cat.get("stats", []):
                        abbr = s.get("abbreviation", "")
                        dn = s.get("displayName", "")
                        val = s.get("value")
                        if abbr in ("PTS", "REB", "AST", "GP", "MIN", "GS"):
                            print(f"  {abbr} ({dn}): {val}")
            
            # Try with season=2026 (current season)
            stats_url_season = f"{core_base}/seasons/2026/athletes/{pid}/statistics?lang=en&region=us"
            print(f"\n=== SEASON 2026 STATS ({stats_url_season}) ===")
            r3 = requests.get(stats_url_season, timeout=10)
            if r3.ok:
                sdata3 = r3.json()
                splits3 = sdata3.get("splits", {})
                for cat in splits3.get("categories", []):
                    for s in cat.get("stats", []):
                        abbr = s.get("abbreviation", "")
                        dn = s.get("displayName", "")
                        val = s.get("value")
                        if abbr in ("PTS", "REB", "AST", "GP", "MIN", "GS"):
                            print(f"  {abbr} ({dn}): {val}")
            else:
                print(f"  Season endpoint failed: {r3.status_code}")
                
            # Try alternate: /seasons/2026/types/2/ (regular season)
            stats_url_type = f"{core_base}/seasons/2026/types/2/athletes/{pid}/statistics?lang=en&region=us"
            print(f"\n=== SEASON 2026 TYPE 2 STATS ===")
            r4 = requests.get(stats_url_type, timeout=10)
            if r4.ok:
                sdata4 = r4.json()
                splits4 = sdata4.get("splits", {})
                for cat in splits4.get("categories", []):
                    for s in cat.get("stats", []):
                        abbr = s.get("abbreviation", "")
                        dn = s.get("displayName", "")
                        val = s.get("value")
                        if abbr in ("PTS", "REB", "AST", "GP", "MIN", "GS"):
                            print(f"  {abbr} ({dn}): {val}")
            else:
                print(f"  Season/type endpoint failed: {r4.status_code}")
            break
else:
    print(f"Roster fetch failed: {r.status_code}")
