"""
NFL Stats Cache — Live stats fetcher + daily cache system.

Mirrors NBA's stats_last10_cache.py:
- Fetches player stats from ESPN
- Caches mu/sigma per player/stat
- Validates freshness before analysis
- Saves to outputs/stats_cache/nfl_stats_{date}.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Optional
import statistics

sys.path.insert(0, str(Path(__file__).parent))

OUTPUTS_DIR = Path("outputs")
STATS_CACHE_DIR = OUTPUTS_DIR / "stats_cache"


def _get_cache_path() -> Path:
    """Get today's cache file path."""
    today = date.today().strftime("%Y%m%d")
    return STATS_CACHE_DIR / f"nfl_stats_{today}.json"


def load_stats_cache() -> dict:
    """Load today's stats cache if it exists."""
    cache_path = _get_cache_path()
    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)
    return {}


def save_stats_cache(cache: dict) -> Path:
    """Save stats cache to disk."""
    STATS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path()
    
    cache["_metadata"] = {
        "updated": datetime.now().isoformat(),
        "date": date.today().isoformat(),
        "player_count": len([k for k in cache if not k.startswith("_")])
    }
    
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)
    
    return cache_path


def fetch_player_stats_espn(player_name: str, stat_type: str, last_n: int = 10) -> dict:
    """
    Fetch live stats from ESPN for a player.
    
    Returns:
        dict with: values, mean, std_dev, samples, source
    """
    try:
        from ufa.ingest.espn_nfl import ESPNFetcher
        fetcher = ESPNFetcher()
        
        values = fetcher.get_player_stats(player_name, stat_type, last_n=last_n)
        
        if not values:
            return {"values": [], "mean": 0.0, "std_dev": 0.0, "samples": 0, "source": "espn_empty"}
        
        mu = statistics.mean(values)
        sigma = statistics.stdev(values) if len(values) > 1 else 0.0
        
        return {
            "values": values,
            "mean": round(mu, 2),
            "std_dev": round(sigma, 2),
            "samples": len(values),
            "source": "espn_live"
        }
    except Exception as e:
        return {"values": [], "mean": 0.0, "std_dev": 0.0, "samples": 0, "source": f"error: {e}"}


def hydrate_stats_for_picks(picks: list[dict], use_cache: bool = True, verbose: bool = True) -> list[dict]:
    """
    Hydrate all picks with live ESPN stats.
    Falls back to nflverse hydrator if ESPN fails.
    
    Args:
        picks: List of pick dicts from slate
        use_cache: Check cache first before fetching
        verbose: Print progress
    
    Returns:
        Modified picks with stats populated
    """
    cache = load_stats_cache() if use_cache else {}
    updated = 0
    cached = 0
    failed = 0
    
    for i, pick in enumerate(picks):
        player = pick.get("player", "")
        stat = pick.get("stat", "")
        
        if not player or not stat:
            continue
        
        cache_key = f"{player}|{stat}"
        
        # Check cache first
        if cache_key in cache:
            cached_data = cache[cache_key]
            pick["recent_avg"] = cached_data.get("mean", 0.0)
            pick["sigma"] = cached_data.get("std_dev", 0.0)
            pick["sample_size"] = cached_data.get("samples", 0)
            pick["stats_source"] = "cache"
            cached += 1
            continue
        
        # Fetch from ESPN
        if verbose:
            print(f"  Fetching: {player} / {stat}...", end=" ", flush=True)
        
        stats = fetch_player_stats_espn(player, stat)
        
        if stats["samples"] > 0:
            pick["recent_avg"] = stats["mean"]
            pick["sigma"] = stats["std_dev"]
            pick["sample_size"] = stats["samples"]
            pick["stats_source"] = "espn"
            
            # Save to cache
            cache[cache_key] = stats
            updated += 1
            
            if verbose:
                print(f"OK (avg={stats['mean']}, n={stats['samples']})")
        else:
            # Fallback to existing hydrator
            try:
                from hydrators.nfl_stat_hydrator import hydrate_nfl_stat
                stat_data = hydrate_nfl_stat(
                    player=player,
                    stat=stat,
                    team=pick.get("team", ""),
                    season=2025,
                    games=10,
                    position=pick.get("position")
                )
                pick["recent_avg"] = stat_data.get("mean", 0.0)
                pick["sigma"] = stat_data.get("std_dev", 0.0)
                pick["sample_size"] = stat_data.get("samples", 0)
                pick["stats_source"] = "nflverse"
                
                # Cache this too
                cache[cache_key] = {
                    "values": [],
                    "mean": pick["recent_avg"],
                    "std_dev": pick["sigma"],
                    "samples": pick["sample_size"],
                    "source": "nflverse"
                }
                updated += 1
                
                if verbose:
                    print(f"OK via nflverse (avg={pick['recent_avg']})")
            except Exception as e:
                pick["recent_avg"] = 0.0
                pick["sigma"] = 0.0
                pick["sample_size"] = 0
                pick["stats_source"] = "failed"
                failed += 1
                
                if verbose:
                    print(f"FAILED ({e})")
    
    # Save updated cache
    if updated > 0:
        cache_path = save_stats_cache(cache)
        if verbose:
            print(f"\n  Stats: {updated} fetched, {cached} cached, {failed} failed")
            print(f"  Saved: {cache_path.name}")
    
    return picks


def preflight_stats_check(picks: list[dict]) -> tuple[bool, list[str]]:
    """
    Validate stats are populated before analysis.
    
    Returns:
        (passed, list of warning messages)
    """
    warnings = []
    no_stats = 0
    low_sample = 0
    
    for pick in picks:
        if pick.get("action") == "EXCLUDE":
            continue
        
        avg = pick.get("recent_avg", 0.0)
        samples = pick.get("sample_size", 0)
        
        if avg == 0.0 and samples == 0:
            no_stats += 1
            warnings.append(f"  [!] {pick.get('player')}/{pick.get('stat')}: No stats found")
        elif samples < 3:
            low_sample += 1
            warnings.append(f"  [?] {pick.get('player')}/{pick.get('stat')}: Low sample (n={samples})")
    
    total = len([p for p in picks if p.get("action") != "EXCLUDE"])
    
    if no_stats > total * 0.5:
        warnings.insert(0, f"  [!!] {no_stats}/{total} picks have NO STATS — results unreliable!")
        return False, warnings
    
    return True, warnings


if __name__ == "__main__":
    """Quick test — show cache status."""
    cache = load_stats_cache()
    if cache:
        meta = cache.get("_metadata", {})
        print(f"NFL Stats Cache:")
        print(f"  Date: {meta.get('date', 'unknown')}")
        print(f"  Updated: {meta.get('updated', 'unknown')}")
        print(f"  Players: {meta.get('player_count', 0)}")
    else:
        print("No NFL stats cache for today.")
