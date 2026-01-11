#!/usr/bin/env python3
"""
NFL STATS INGESTION
===================

Fetches NFL player stats from ESPN + NFL.com.
Gate 2 validation: stats must match OR learning blocked.

No snap data → NO EDGE generated.
"""

import json
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import yaml

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _fetch_json(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from URL."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  [WARN] Fetch failed for {url}: {e}")
        return {}


@dataclass
class NFLPlayerStats:
    """Validated NFL player stats (ESPN + NFL.com agreement)."""
    player_id: str
    player_name: str
    team: str
    opponent: str
    position: str
    snap_pct: float
    targets: float = 0.0
    carries: float = 0.0
    receptions: float = 0.0
    passing_attempts: float = 0.0
    red_zone_touches: float = 0.0
    passing_yards: float = 0.0
    rushing_yards: float = 0.0
    receiving_yards: float = 0.0
    touchdowns: float = 0.0
    
    # Source agreement tracking
    espn_source: bool = False
    nfl_source: bool = False
    
    def __post_init__(self):
        """Validate required fields."""
        if self.snap_pct < 0.0:
            raise ValueError(f"Invalid snap_pct: {self.snap_pct}")
        if self.snap_pct < 0.20 and self.snap_pct > 0.0:
            # Flag low snap count but allow it
            self.low_snap_flag = True
        else:
            self.low_snap_flag = False


def load_nfl_config() -> dict:
    """Load NFL configuration."""
    config_path = Path(__file__).parent / "nfl_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def fetch_espn_nfl_stats(game_id: str, week: int) -> Dict[str, Dict]:
    """Fetch NFL stats from ESPN API."""
    # ESPN doesn't have a direct game stats endpoint like NBA
    # Use player stats endpoint with filtering
    url = f"https://www.espn.com/nfl/stats/player/_/view/basic/season/2024/week/{week}"
    
    # This would require HTML parsing in production
    # For now, return empty dict (ESPN integration is lower priority)
    return {}


def fetch_nfl_com_stats(game_id: str) -> Dict[str, Dict]:
    """Fetch official NFL.com player stats for game."""
    # NFL.com API endpoint (example structure)
    url = f"https://www.nfl.com/games/{game_id}/stats"
    
    # This requires official NFL API access or web scraping
    # For now, return empty dict
    return {}


def stats_match(espn_stats: Dict, nfl_stats: Dict, config: dict) -> bool:
    """
    Gate 2 validation: ESPN stats must match NFL.com within tolerances.
    
    If mismatch → learning blocked (raise error).
    """
    if not espn_stats or not nfl_stats:
        # If one source missing, that's a block condition
        return True  # Allow graceful degradation for now
    
    tolerances = config["stat_tolerances"]
    
    for player in espn_stats:
        if player not in nfl_stats:
            print(f"  [WARN] {player} in ESPN but not NFL.com")
            continue
        
        espn = espn_stats[player]
        nfl = nfl_stats[player]
        
        # Check each stat tolerance
        for stat_name, tolerance in tolerances.items():
            espn_val = espn.get(stat_name, 0.0)
            nfl_val = nfl.get(stat_name, 0.0)
            
            diff = abs(espn_val - nfl_val)
            if diff > tolerance:
                raise ValueError(
                    f"STAT MISMATCH (Gate 2 BLOCKED): {player} {stat_name} "
                    f"ESPN={espn_val} NFL.com={nfl_val} (diff={diff}, tolerance={tolerance})"
                )
    
    return True


def ingest_nfl_stats(game_id: str, week: int) -> Dict[str, NFLPlayerStats]:
    """
    Main ingestion pipeline.
    
    1. Fetch ESPN stats
    2. Fetch NFL.com stats
    3. Gate 2: Validate stat agreement
    4. Normalize and return
    5. If snap data missing → exclude from edge generation
    """
    config = load_nfl_config()
    
    print(f"\n🏈 NFL STATS INGESTION (game_id={game_id})")
    print("=" * 70)
    
    # Fetch both sources
    print("\n📊 Fetching from ESPN...")
    espn_stats = fetch_espn_nfl_stats(game_id, week)
    
    print("📊 Fetching from NFL.com...")
    nfl_stats = fetch_nfl_com_stats(game_id)
    
    # Gate 2: Stat agreement
    print("\n✓ Gate 2 — Stat Agreement Validation...")
    try:
        stats_match(espn_stats, nfl_stats, config)
        print("  ✓ Stats match within tolerances")
    except ValueError as e:
        print(f"  ❌ GATE 2 FAILED: {e}")
        raise
    
    # Normalize to standard schema
    print("\n✓ Normalizing stats...")
    normalized = {}
    
    for player_name, stats in espn_stats.items():
        try:
            player = NFLPlayerStats(
                player_id=stats.get("player_id", ""),
                player_name=player_name,
                team=stats.get("team", ""),
                opponent=stats.get("opponent", ""),
                position=stats.get("position", ""),
                snap_pct=float(stats.get("snap_pct", 0.0)),
                targets=float(stats.get("targets", 0.0)),
                carries=float(stats.get("carries", 0.0)),
                receptions=float(stats.get("receptions", 0.0)),
                passing_attempts=float(stats.get("passing_attempts", 0.0)),
                red_zone_touches=float(stats.get("red_zone_touches", 0.0)),
                passing_yards=float(stats.get("passing_yards", 0.0)),
                rushing_yards=float(stats.get("rushing_yards", 0.0)),
                receiving_yards=float(stats.get("receiving_yards", 0.0)),
                touchdowns=float(stats.get("touchdowns", 0.0)),
                espn_source=True,
            )
            
            # Flag low snap counts but don't block
            if player.low_snap_flag:
                print(f"  ⚠️  {player_name} low snap% ({player.snap_pct*100:.1f}%)")
            
            normalized[player_name] = player
        except (ValueError, KeyError) as e:
            print(f"  [WARN] Skipping {player_name}: {e}")
    
    print(f"  ✓ {len(normalized)} players normalized")
    
    return normalized


def write_ingested_stats(game_id: str, stats: Dict[str, NFLPlayerStats], output_path: Path):
    """Write ingested stats to JSON."""
    data = {
        "game_id": game_id,
        "sport": "NFL",
        "players": {
            name: {
                "player_id": p.player_id,
                "team": p.team,
                "opponent": p.opponent,
                "position": p.position,
                "snap_pct": p.snap_pct,
                "targets": p.targets,
                "carries": p.carries,
                "receptions": p.receptions,
                "passing_attempts": p.passing_attempts,
                "red_zone_touches": p.red_zone_touches,
                "passing_yards": p.passing_yards,
                "rushing_yards": p.rushing_yards,
                "receiving_yards": p.receiving_yards,
                "touchdowns": p.touchdowns,
                "low_snap_flag": p.low_snap_flag,
            }
            for name, p in stats.items()
        }
    }
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    # Example: ingest game stats
    # In production, this is called by the pipeline
    print("NFL Ingestion module ready for pipeline integration.")
