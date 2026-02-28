"""
Golf Player Database
====================
Stores and retrieves player statistics for better Monte Carlo accuracy.
Supports: manual entry, CSV import, and DataGolf API enrichment.

Quant Enhancements:
- Data freshness tracking (days since last update)
- Sample size tracking (rounds in dataset)
- Cold-start detection (EXPERIMENTAL tier for sparse data)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

GOLF_DIR = Path(__file__).parent.parent
DATA_DIR = GOLF_DIR / "data"
DATABASE_FILE = DATA_DIR / "player_database.json"

# Ensure data dir exists
DATA_DIR.mkdir(exist_ok=True)


# =============================================================================
# DATA QUALITY THRESHOLDS (Quant Governance)
# =============================================================================

MIN_SAMPLE_SIZE_FOR_OPTIMIZABLE = 10  # Rounds needed for OPTIMIZABLE
MIN_SAMPLE_SIZE_FOR_VETTED = 5        # Rounds needed for VETTED (else EXPERIMENTAL)
MAX_STALE_DAYS = 60                   # Days before data is considered stale


# =============================================================================
# PRE-LOADED TOUR AVERAGES (2024-2025 Season)
# =============================================================================
# Source: PGA Tour Stats, DataGolf baselines

PGA_TOUR_AVERAGES = {
    "scoring_avg": 70.8,
    "scoring_stddev": 3.0,
    "birdies_per_round": 4.2,
    "eagles_per_round": 0.08,
    "bogeys_per_round": 3.3,
    "sg_total_mean": 0.0,  # By definition
    "sg_ott_mean": 0.0,
    "sg_app_mean": 0.0,
    "sg_arg_mean": 0.0,
    "sg_putt_mean": 0.0,
}

# =============================================================================
# KNOWN PLAYER PROFILES (Manual Entry)
# =============================================================================
# These are approximations based on publicly available stats
# sample_size = estimated rounds in 2024-2025 dataset

KNOWN_PLAYERS = {
    # Elite Tier (SG Total > +2.0)
    "Scottie Scheffler": {
        "scoring_avg": 68.5,
        "scoring_stddev": 2.5,
        "birdies_per_round": 4.8,
        "sg_total": 2.5,
        "sg_ott": 0.7,
        "sg_app": 1.1,
        "sg_arg": 0.3,
        "sg_putt": 0.4,
        "tier": "elite",
        "sample_size": 80,  # High sample - plays every week
    },
    "Xander Schauffele": {
        "scoring_avg": 69.0,
        "scoring_stddev": 2.6,
        "birdies_per_round": 4.6,
        "sg_total": 2.0,
        "sg_ott": 0.5,
        "sg_app": 0.9,
        "sg_arg": 0.2,
        "sg_putt": 0.4,
        "tier": "elite",
        "sample_size": 75,
    },
    "Rory McIlroy": {
        "scoring_avg": 69.2,
        "scoring_stddev": 2.7,
        "birdies_per_round": 4.5,
        "sg_total": 1.9,
        "sg_ott": 0.9,
        "sg_app": 0.7,
        "sg_arg": 0.1,
        "sg_putt": 0.2,
        "tier": "elite",
        "sample_size": 60,  # Limited schedule
    },
    
    # Top Tier (SG Total +1.0 to +2.0)
    "Patrick Cantlay": {
        "scoring_avg": 69.5,
        "scoring_stddev": 2.8,
        "birdies_per_round": 4.3,
        "sg_total": 1.5,
        "sg_ott": 0.2,
        "sg_app": 0.6,
        "sg_arg": 0.3,
        "sg_putt": 0.4,
        "tier": "top",
        "sample_size": 70,
    },
    "Collin Morikawa": {
        "scoring_avg": 69.6,
        "scoring_stddev": 2.7,
        "birdies_per_round": 4.2,
        "sg_total": 1.4,
        "sg_ott": 0.1,
        "sg_app": 0.9,
        "sg_arg": 0.2,
        "sg_putt": 0.2,
        "tier": "top",
        "sample_size": 65,
    },
    "Hideki Matsuyama": {
        "scoring_avg": 69.8,
        "scoring_stddev": 2.9,
        "birdies_per_round": 4.1,
        "sg_total": 1.3,
        "sg_ott": 0.4,
        "sg_app": 0.6,
        "sg_arg": 0.2,
        "sg_putt": 0.1,
        "tier": "top",
    },
    "Cameron Young": {
        "scoring_avg": 69.9,
        "scoring_stddev": 3.2,  # High variance player
        "birdies_per_round": 4.5,
        "sg_total": 1.2,
        "sg_ott": 0.7,
        "sg_app": 0.4,
        "sg_arg": 0.0,
        "sg_putt": 0.1,
        "tier": "top",
    },
    
    # Mid Tier (SG Total +0.5 to +1.0)
    "Justin Rose": {
        "scoring_avg": 70.2,
        "scoring_stddev": 2.9,
        "birdies_per_round": 3.9,
        "sg_total": 0.8,
        "sg_ott": 0.2,
        "sg_app": 0.3,
        "sg_arg": 0.2,
        "sg_putt": 0.1,
        "tier": "mid",
    },
    "Jason Day": {
        "scoring_avg": 70.3,
        "scoring_stddev": 3.0,
        "birdies_per_round": 4.0,
        "sg_total": 0.7,
        "sg_ott": 0.3,
        "sg_app": 0.2,
        "sg_arg": 0.1,
        "sg_putt": 0.1,
        "tier": "mid",
    },
    "Si Woo Kim": {
        "scoring_avg": 70.1,
        "scoring_stddev": 3.3,  # Inconsistent
        "birdies_per_round": 4.2,
        "sg_total": 0.6,
        "sg_ott": 0.2,
        "sg_app": 0.3,
        "sg_arg": 0.0,
        "sg_putt": 0.1,
        "tier": "mid",
    },
    "Seamus Power": {
        "scoring_avg": 70.4,
        "scoring_stddev": 2.9,
        "birdies_per_round": 3.8,
        "sg_total": 0.5,
        "sg_ott": 0.1,
        "sg_app": 0.2,
        "sg_arg": 0.1,
        "sg_putt": 0.1,
        "tier": "mid",
    },
    
    # Below Average (SG Total 0 to +0.5)
    "Chris Gotterup": {
        "scoring_avg": 70.8,
        "scoring_stddev": 3.1,
        "birdies_per_round": 3.6,
        "sg_total": 0.2,
        "tier": "average",
    },
    "Jake Knapp": {
        "scoring_avg": 70.9,
        "scoring_stddev": 3.2,
        "birdies_per_round": 3.5,
        "sg_total": 0.1,
        "tier": "average",
    },
    "Maverick McNealy": {
        "scoring_avg": 70.7,
        "scoring_stddev": 2.8,
        "birdies_per_round": 3.7,
        "sg_total": 0.3,
        "tier": "average",
    },
    "Stephan Jaeger": {
        "scoring_avg": 70.5,
        "scoring_stddev": 2.9,
        "birdies_per_round": 3.8,
        "sg_total": 0.4,
        "sg_ott": 0.1,
        "sg_app": 0.2,
        "sg_arg": 0.05,
        "sg_putt": 0.05,
        "tier": "average",
    },
    
    # Additional Players (Added for Farmers Insurance Open 2026)
    "Brooks Koepka": {
        "scoring_avg": 69.6,
        "scoring_stddev": 3.0,
        "birdies_per_round": 4.3,
        "sg_total": 1.1,
        "sg_ott": 0.6,
        "sg_app": 0.4,
        "sg_arg": 0.0,
        "sg_putt": 0.1,
        "tier": "top",
        "sample_size": 50,
    },
    "Harris English": {
        "scoring_avg": 70.2,
        "scoring_stddev": 2.8,
        "birdies_per_round": 4.0,
        "sg_total": 0.5,
        "sg_ott": 0.2,
        "sg_app": 0.2,
        "sg_arg": 0.0,
        "sg_putt": 0.1,
        "tier": "mid",
        "sample_size": 55,
    },
    "Ryo Hisatsune": {
        "scoring_avg": 70.4,
        "scoring_stddev": 3.1,
        "birdies_per_round": 3.9,
        "sg_total": 0.3,
        "sg_ott": 0.1,
        "sg_app": 0.1,
        "sg_arg": 0.0,
        "sg_putt": 0.1,
        "tier": "average",
        "sample_size": 40,
    },
    "Joel Dahmen": {
        "scoring_avg": 70.6,
        "scoring_stddev": 2.9,
        "birdies_per_round": 3.8,
        "sg_total": 0.2,
        "sg_ott": 0.0,
        "sg_app": 0.1,
        "sg_arg": 0.0,
        "sg_putt": 0.1,
        "tier": "average",
        "sample_size": 60,
    },
}


class PlayerDatabase:
    """Manages player statistics for golf analysis."""
    
    def __init__(self):
        self.players: Dict[str, Dict] = {}
        self._load_known_players()
        self._load_saved_database()
    
    def _load_known_players(self):
        """Load pre-configured player profiles."""
        for name, stats in KNOWN_PLAYERS.items():
            self.players[name.lower()] = {
                "name": name,
                "source": "preset",
                "updated": "2025-01-30",
                **stats
            }
    
    def _load_saved_database(self):
        """Load any saved player data from JSON."""
        if DATABASE_FILE.exists():
            try:
                with open(DATABASE_FILE) as f:
                    saved = json.load(f)
                for name, stats in saved.items():
                    if name.lower() not in self.players:
                        self.players[name.lower()] = stats
                    elif saved[name].get("source") == "datagolf":
                        # DataGolf data overrides presets
                        self.players[name.lower()] = stats
            except Exception as e:
                print(f"Warning: Could not load player database: {e}")
    
    def save(self):
        """Save player database to JSON."""
        with open(DATABASE_FILE, "w") as f:
            json.dump(self.players, f, indent=2)
    
    def get_player(self, name: str) -> Optional[Dict]:
        """
        Get player stats by name.
        
        Args:
            name: Player name (case insensitive)
            
        Returns:
            Player stats dict or None
        """
        # Try exact match
        key = name.lower().strip()
        if key in self.players:
            return self.players[key]
        
        # Try partial match
        for player_key, stats in self.players.items():
            if key in player_key or player_key in key:
                return stats
        
        return None
    
    def add_player(
        self,
        name: str,
        scoring_avg: float,
        scoring_stddev: float = 3.0,
        birdies_per_round: float = 4.0,
        sg_total: Optional[float] = None,
        sg_ott: Optional[float] = None,
        sg_app: Optional[float] = None,
        sg_arg: Optional[float] = None,
        sg_putt: Optional[float] = None,
        source: str = "manual"
    ):
        """Add or update a player in the database."""
        self.players[name.lower()] = {
            "name": name,
            "scoring_avg": scoring_avg,
            "scoring_stddev": scoring_stddev,
            "birdies_per_round": birdies_per_round,
            "sg_total": sg_total,
            "sg_ott": sg_ott,
            "sg_app": sg_app,
            "sg_arg": sg_arg,
            "sg_putt": sg_putt,
            "source": source,
            "sample_size": 20,  # Assume reasonable sample for manual entries
            "updated": datetime.now().strftime("%Y-%m-%d"),
        }
        self.save()
    
    def seed_player(
        self,
        name: str,
        tour: str = "PGA",
        status: str = "UNVERIFIED",
    ):
        """
        Auto-seed a missing player with tour averages.
        Blocks betting but allows pipeline to continue.
        
        COLD START: sample_size=0 forces EXPERIMENTAL tier.
        
        Args:
            name: Player name
            tour: Tour (PGA, LPGA, DP World)
            status: UNVERIFIED (blocks betting) or VERIFIED
        """
        self.players[name.lower()] = {
            "name": name,
            "scoring_avg": PGA_TOUR_AVERAGES["scoring_avg"],
            "scoring_stddev": PGA_TOUR_AVERAGES["scoring_stddev"],
            "birdies_per_round": PGA_TOUR_AVERAGES["birdies_per_round"],
            "sg_total": 0.0,  # Assume average
            "sg_ott": 0.0,
            "sg_app": 0.0,
            "sg_arg": 0.0,
            "sg_putt": 0.0,
            "source": "auto_seeded",
            "tour": tour,
            "status": status,  # UNVERIFIED blocks betting
            "block_betting": True,
            "sample_size": 0,  # COLD START: No real data
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "tier": "unverified",
        }
        print(f"[AUTO-SEED] Created UNVERIFIED profile for {name} (tour averages, sample_size=0, betting blocked)")
        self.save()
    
    def get_data_quality(self, name: str) -> Dict:
        """
        Assess data quality for a player (Quant governance).
        
        Returns:
            {
                "sample_size": int,
                "days_since_update": int,
                "quality_tier": "HIGH" | "MEDIUM" | "LOW" | "EXPERIMENTAL",
                "is_stale": bool,
                "is_cold_start": bool,
            }
        """
        player = self.get_player(name)
        if not player:
            return {
                "sample_size": 0,
                "days_since_update": 999,
                "quality_tier": "EXPERIMENTAL",
                "is_stale": True,
                "is_cold_start": True,
            }
        
        sample_size = player.get("sample_size", 0)
        updated_str = player.get("updated", "2020-01-01")
        
        try:
            updated_date = datetime.strptime(updated_str, "%Y-%m-%d")
            days_since = (datetime.now() - updated_date).days
        except:
            days_since = 999
        
        is_stale = days_since > MAX_STALE_DAYS
        is_cold_start = sample_size < MIN_SAMPLE_SIZE_FOR_VETTED
        
        # Determine quality tier
        if sample_size >= MIN_SAMPLE_SIZE_FOR_OPTIMIZABLE and not is_stale:
            quality_tier = "HIGH"
        elif sample_size >= MIN_SAMPLE_SIZE_FOR_VETTED and not is_stale:
            quality_tier = "MEDIUM"
        elif sample_size > 0:
            quality_tier = "LOW"
        else:
            quality_tier = "EXPERIMENTAL"
        
        return {
            "sample_size": sample_size,
            "days_since_update": days_since,
            "quality_tier": quality_tier,
            "is_stale": is_stale,
            "is_cold_start": is_cold_start,
        }
    
    def is_verified(self, name: str) -> bool:
        """Check if player is verified for betting (not auto-seeded)."""
        player = self.get_player(name)
        if not player:
            return False
        return player.get("status") != "UNVERIFIED" and not player.get("block_betting", False)
    
    def get_stats_for_edge(self, name: str, market: str, line: float) -> Dict:
        """
        Get stats formatted for edge generation.
        Auto-seeds missing players with UNVERIFIED status (blocks betting).
        Args:
            name: Player name
            market: Market type (round_strokes, birdies, etc.)
            line: Prop line
        Returns:
            Stats dict compatible with generate_edges
        Raises:
            ValueError if player stats are missing or invalid
        """
        player = self.get_player(name)
        
        # AUTO-HYDRATION: Seed missing players with tour averages
        if not player:
            self.seed_player(name, tour="PGA", status="UNVERIFIED")
            player = self.get_player(name)
        if player:
            if market == "round_strokes":
                avg = player.get("scoring_avg")
                stddev = player.get("scoring_stddev")
                if avg is None or stddev is None:
                    print(f"[STAT LOADER ERROR] Player {name} missing scoring_avg or scoring_stddev.")
                    raise ValueError(f"Player {name} missing scoring_avg or scoring_stddev.")
                return {
                    "avg": avg,
                    "stddev": stddev,
                    "sg_total": player.get("sg_total"),
                    "sources": [player.get("source", "preset")]
                }
            elif market == "birdies":
                avg_birdies = player.get("birdies_per_round")
                if avg_birdies is None:
                    print(f"[STAT LOADER ERROR] Player {name} missing birdies_per_round.")
                    raise ValueError(f"Player {name} missing birdies_per_round.")
                return {
                    "avg_birdies": avg_birdies,
                    "stddev": 1.5,
                    "sources": [player.get("source", "preset")]
                }
            elif market == "finishing_position":
                sg = player.get("sg_total")
                if sg is None:
                    print(f"[STAT LOADER ERROR] Player {name} missing sg_total for finishing_position.")
                    raise ValueError(f"Player {name} missing sg_total for finishing_position.")
                expected = max(5, 40 - (sg * 12))
                return {
                    "expected_finish": expected,
                    "sources": [player.get("source", "preset")]
                }
            elif market in ["matchup", "head_to_head", "birdies_or_better_matchup"]:
                # For matchups, return SG data for comparison
                sg_total = player.get("sg_total")
                return {
                    "sg_total": sg_total,
                    "sg_ott": player.get("sg_ott"),
                    "sg_app": player.get("sg_app"),
                    "sg_arg": player.get("sg_arg"),
                    "sg_putt": player.get("sg_putt"),
                    "tier": player.get("tier"),
                    "sources": [player.get("source", "preset")],
                    "n": player.get("sample_size", 20),
                }
        # Fallback to line inference for unknown markets
        from golf.engines.generate_edges import get_default_player_stats
        stats = get_default_player_stats(market, line)
        print(f"[STAT LOADER WARNING] Fallback to line inference for {name} {market} {line}.")
        return stats
    
    def list_players(self) -> List[str]:
        """Get list of all player names in database."""
        return [stats["name"] for stats in self.players.values()]
    
    def __len__(self):
        return len(self.players)


# Singleton instance
_db_instance: Optional[PlayerDatabase] = None


def get_player_database() -> PlayerDatabase:
    """Get the player database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = PlayerDatabase()
    return _db_instance


if __name__ == "__main__":
    # Demo
    db = get_player_database()
    print(f"Player Database: {len(db)} players loaded")
    print()
    
    # Show some players
    for name in ["Cameron Young", "Patrick Cantlay", "Hideki Matsuyama"]:
        player = db.get_player(name)
        if player:
            print(f"{player['name']}:")
            print(f"  Scoring Avg: {player.get('scoring_avg', 'N/A')}")
            print(f"  Birdies/Round: {player.get('birdies_per_round', 'N/A')}")
            print(f"  SG Total: {player.get('sg_total', 'N/A')}")
            print()
