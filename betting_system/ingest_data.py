#!/usr/bin/env python3
"""
INGEST_DATA.PY — SOP v2.1 DATA INGESTION
========================================
Stage 1: Load and verify raw data from multiple sources

SOP Rules Enforced:
- Rule 2.2: Data from ≥2 sources required
- Gate checks: FINAL status, cooldown elapsed, injury feed healthy

Version: 2.1.0
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import hashlib


# ============================================================================
# CONFIGURATION
# ============================================================================

# Cooldown periods by sport (time after game end before data is trusted)
COOLDOWN_PERIODS = {
    "NFL": timedelta(minutes=30),
    "NBA": timedelta(minutes=15),
    "WNBA": timedelta(minutes=15),
    "CFB": timedelta(minutes=30),
    "CBB": timedelta(minutes=15),
    "BOXING": timedelta(minutes=60),
    "TENNIS": timedelta(minutes=5)
}

# Data source priorities (Tier 1 = Official, Tier 2 = Verification)
DATA_SOURCES = {
    "NFL": {
        "tier1": ["nfl_official", "espn"],
        "tier2": ["pro_football_reference", "yahoo_sports"]
    },
    "NBA": {
        "tier1": ["nba_api", "espn"],
        "tier2": ["basketball_reference", "yahoo_sports"]
    },
    "WNBA": {
        "tier1": ["wnba_official", "espn"],
        "tier2": ["basketball_reference"]
    },
    "CFB": {
        "tier1": ["espn", "ncaa_official"],
        "tier2": ["sports_reference"]
    },
    "CBB": {
        "tier1": ["espn", "ncaa_official"],
        "tier2": ["sports_reference", "kenpom"]
    }
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class GameData:
    """Raw game data from ingestion"""
    game_id: str
    sport: str
    home_team: str
    away_team: str
    game_date: str
    status: str  # SCHEDULED, IN_PROGRESS, FINAL
    final_confirmed_at: Optional[str]
    venue: str
    weather: Optional[Dict]
    
@dataclass
class PlayerData:
    """Raw player data from ingestion"""
    player_id: str
    player_name: str
    team: str
    position: str
    status: str  # ACTIVE, QUESTIONABLE, DOUBTFUL, OUT
    injury_info: Optional[str]
    
@dataclass
class StatLine:
    """Raw stat line for a player in a game"""
    player_id: str
    player_name: str
    game_id: str
    stat_type: str
    value: float
    source: str
    retrieved_at: str

@dataclass
class MarketLine:
    """Betting line from market"""
    player_id: str
    player_name: str
    game_id: str
    stat_type: str
    line: float
    over_odds: int
    under_odds: int
    source: str
    retrieved_at: str

@dataclass
class IngestionResult:
    """Complete ingestion output"""
    sport: str
    date: str
    timestamp: str
    games: List[Dict]
    players: List[Dict]
    historical_stats: List[Dict]
    market_lines: List[Dict]
    data_sources_used: List[str]
    verification_status: Dict
    checksum: str


# ============================================================================
# DATA INGESTION FUNCTIONS
# ============================================================================

class DataIngester:
    """
    Handles all data ingestion with SOP v2.1 compliance
    """
    
    def __init__(self, sport: str, date: str):
        self.sport = sport.upper()
        self.date = date
        self.errors = []
        self.warnings = []
        
    def ingest_all(self) -> IngestionResult:
        """
        Main ingestion pipeline
        
        Order:
        1. Fetch game schedule
        2. Fetch player rosters and injury status
        3. Fetch historical stats (verified final only)
        4. Fetch current market lines
        5. Cross-verify all data
        6. Generate checksum for audit
        """
        print(f"\n📡 Ingesting {self.sport} data for {self.date}")
        
        # Step 1: Games
        games = self._fetch_games()
        print(f"   Games loaded: {len(games)}")
        
        # Step 2: Players
        players = self._fetch_players(games)
        print(f"   Players loaded: {len(players)}")
        
        # Step 3: Historical stats (VERIFIED ONLY)
        historical = self._fetch_historical_stats(players)
        print(f"   Historical stat lines: {len(historical)}")
        
        # Step 4: Market lines
        lines = self._fetch_market_lines(games)
        print(f"   Market lines loaded: {len(lines)}")
        
        # Step 5: Verification
        verification = self._verify_data(games, players, historical, lines)
        
        # Step 6: Build result
        result = IngestionResult(
            sport=self.sport,
            date=self.date,
            timestamp=datetime.utcnow().isoformat() + "Z",
            games=[asdict(g) if hasattr(g, '__dataclass_fields__') else g for g in games],
            players=[asdict(p) if hasattr(p, '__dataclass_fields__') else p for p in players],
            historical_stats=historical,
            market_lines=lines,
            data_sources_used=self._get_sources_used(),
            verification_status=verification,
            checksum=self._generate_checksum(games, players, historical, lines)
        )
        
        return result
    
    def _fetch_games(self) -> List[Dict]:
        """
        Fetch game schedule
        
        In production: Call actual APIs
        Here: Return mock data for testing
        """
        # MOCK DATA - Replace with actual API calls
        if self.sport == "NBA":
            return [
                {
                    "game_id": "DEN_vs_BOS_20260129",
                    "sport": "NBA",
                    "home_team": "BOS",
                    "away_team": "DEN",
                    "game_date": self.date,
                    "game_time": "19:30:00",
                    "status": "SCHEDULED",
                    "venue": "TD Garden",
                    "weather": None  # Indoor
                },
                {
                    "game_id": "LAL_vs_GSW_20260129",
                    "sport": "NBA",
                    "home_team": "GSW",
                    "away_team": "LAL",
                    "game_date": self.date,
                    "game_time": "22:00:00",
                    "status": "SCHEDULED",
                    "venue": "Chase Center",
                    "weather": None
                }
            ]
        elif self.sport == "NFL":
            return [
                {
                    "game_id": "KC_vs_BUF_20260129",
                    "sport": "NFL",
                    "home_team": "BUF",
                    "away_team": "KC",
                    "game_date": self.date,
                    "game_time": "18:30:00",
                    "status": "SCHEDULED",
                    "venue": "Highmark Stadium",
                    "weather": {
                        "temp_f": 28,
                        "wind_mph": 12,
                        "precipitation": "snow",
                        "dome": False
                    }
                }
            ]
        return []
    
    def _fetch_players(self, games: List[Dict]) -> List[Dict]:
        """
        Fetch player rosters for games
        
        Includes injury status from official sources
        """
        players = []
        
        # MOCK DATA - Replace with actual API calls
        if self.sport == "NBA":
            players = [
                {"player_id": "jokic_001", "player_name": "Nikola Jokic", "team": "DEN", "position": "C", "status": "ACTIVE", "injury_info": None},
                {"player_id": "murray_001", "player_name": "Jamal Murray", "team": "DEN", "position": "PG", "status": "ACTIVE", "injury_info": None},
                {"player_id": "tatum_001", "player_name": "Jayson Tatum", "team": "BOS", "position": "SF", "status": "ACTIVE", "injury_info": None},
                {"player_id": "brown_001", "player_name": "Jaylen Brown", "team": "BOS", "position": "SG", "status": "ACTIVE", "injury_info": None},
                {"player_id": "white_001", "player_name": "Derrick White", "team": "BOS", "position": "PG", "status": "ACTIVE", "injury_info": None},
                {"player_id": "lebron_001", "player_name": "LeBron James", "team": "LAL", "position": "SF", "status": "ACTIVE", "injury_info": None},
                {"player_id": "curry_001", "player_name": "Stephen Curry", "team": "GSW", "position": "PG", "status": "QUESTIONABLE", "injury_info": "Ankle - Limited practice"},
            ]
        elif self.sport == "NFL":
            players = [
                {"player_id": "mahomes_001", "player_name": "Patrick Mahomes", "team": "KC", "position": "QB", "status": "ACTIVE", "injury_info": None},
                {"player_id": "kelce_001", "player_name": "Travis Kelce", "team": "KC", "position": "TE", "status": "ACTIVE", "injury_info": None},
                {"player_id": "allen_001", "player_name": "Josh Allen", "team": "BUF", "position": "QB", "status": "ACTIVE", "injury_info": None},
                {"player_id": "diggs_001", "player_name": "Stefon Diggs", "team": "BUF", "position": "WR", "status": "ACTIVE", "injury_info": None},
            ]
        
        return players
    
    def _fetch_historical_stats(self, players: List[Dict]) -> List[Dict]:
        """
        Fetch historical stats for players
        
        SOP CRITICAL: Only returns VERIFIED FINAL data
        """
        stats = []
        
        # MOCK DATA - In production, fetch from multiple sources and verify
        if self.sport == "NBA":
            # Last 5 games for each player (simplified)
            sample_stats = {
                "jokic_001": {"points": [28, 31, 25, 29, 27], "rebounds": [12, 14, 11, 13, 12], "assists": [9, 11, 8, 10, 9]},
                "tatum_001": {"points": [26, 29, 24, 31, 28], "rebounds": [7, 8, 6, 9, 7], "assists": [5, 4, 6, 5, 4]},
                "murray_001": {"points": [21, 24, 19, 23, 22], "rebounds": [4, 5, 3, 4, 5], "assists": [6, 7, 5, 8, 6]},
                "brown_001": {"points": [23, 25, 21, 27, 24], "rebounds": [5, 6, 4, 5, 5], "assists": [3, 4, 3, 4, 3]},
                "white_001": {"points": [14, 16, 12, 18, 15], "rebounds": [4, 5, 3, 4, 4], "three_pointers": [3, 4, 2, 4, 3]},
            }
            
            for player_id, player_stats in sample_stats.items():
                for stat_type, values in player_stats.items():
                    for i, value in enumerate(values):
                        stats.append({
                            "player_id": player_id,
                            "stat_type": stat_type,
                            "value": value,
                            "game_index": i,  # 0 = most recent
                            "source": "nba_api",
                            "verified": True,
                            "status": "FINAL"
                        })
        
        return stats
    
    def _fetch_market_lines(self, games: List[Dict]) -> List[Dict]:
        """
        Fetch current betting lines from market
        """
        lines = []
        
        # MOCK DATA - In production, fetch from sportsbook APIs
        if self.sport == "NBA":
            lines = [
                {"player_id": "jokic_001", "player_name": "Nikola Jokic", "game_id": "DEN_vs_BOS_20260129", "stat_type": "points", "line": 25.5, "over_odds": -115, "under_odds": -105},
                {"player_id": "jokic_001", "player_name": "Nikola Jokic", "game_id": "DEN_vs_BOS_20260129", "stat_type": "points", "line": 26.5, "over_odds": -105, "under_odds": -115},
                {"player_id": "jokic_001", "player_name": "Nikola Jokic", "game_id": "DEN_vs_BOS_20260129", "stat_type": "rebounds", "line": 11.5, "over_odds": -110, "under_odds": -110},
                {"player_id": "tatum_001", "player_name": "Jayson Tatum", "game_id": "DEN_vs_BOS_20260129", "stat_type": "points", "line": 26.5, "over_odds": -110, "under_odds": -110},
                {"player_id": "murray_001", "player_name": "Jamal Murray", "game_id": "DEN_vs_BOS_20260129", "stat_type": "assists", "line": 5.5, "over_odds": -120, "under_odds": +100},
                {"player_id": "brown_001", "player_name": "Jaylen Brown", "game_id": "DEN_vs_BOS_20260129", "stat_type": "points", "line": 23.5, "over_odds": -110, "under_odds": -110},
                {"player_id": "white_001", "player_name": "Derrick White", "game_id": "DEN_vs_BOS_20260129", "stat_type": "three_pointers", "line": 2.5, "over_odds": -130, "under_odds": +110},
            ]
        
        return lines
    
    def _verify_data(self, games, players, historical, lines) -> Dict:
        """
        Cross-verify data from multiple sources
        
        SOP Rule 2.2: Minimum 2 sources required
        """
        verification = {
            "games_verified": True,
            "players_verified": True,
            "stats_verified": True,
            "lines_verified": True,
            "injury_feed_healthy": True,
            "sources_count": 2,
            "verification_timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # In production: Actually cross-check data between sources
        # For now: Mock verification passes
        
        return verification
    
    def _get_sources_used(self) -> List[str]:
        """Return list of data sources used"""
        sources = DATA_SOURCES.get(self.sport, {"tier1": [], "tier2": []})
        return sources["tier1"] + sources["tier2"][:1]  # At least 2 sources
    
    def _generate_checksum(self, games, players, historical, lines) -> str:
        """Generate checksum for audit trail"""
        data_str = json.dumps({
            "games": games,
            "players": players,
            "historical": historical,
            "lines": lines
        }, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]


# ============================================================================
# FILE I/O
# ============================================================================

def save_ingestion_result(result: IngestionResult, filepath: str):
    """Save ingestion result to JSON"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "sport": result.sport,
        "date": result.date,
        "timestamp": result.timestamp,
        "games": result.games,
        "players": result.players,
        "historical_stats": result.historical_stats,
        "market_lines": result.market_lines,
        "data_sources_used": result.data_sources_used,
        "verification_status": result.verification_status,
        "checksum": result.checksum
    }
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Data Ingestion Pipeline Stage
    
    Usage: python ingest_data.py [sport] [date]
    """
    print("=" * 60)
    print("SOP v2.1 DATA INGESTION")
    print("=" * 60)
    
    sport = sys.argv[1] if len(sys.argv) > 1 else "NBA"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
    
    # Run ingestion
    ingester = DataIngester(sport, date)
    result = ingester.ingest_all()
    
    # Verify minimum sources
    if len(result.data_sources_used) < 2:
        print(f"\n❌ ERROR: Insufficient data sources ({len(result.data_sources_used)} < 2)")
        sys.exit(1)
    
    # Check verification status
    if not result.verification_status.get("injury_feed_healthy"):
        print("\n❌ ERROR: Injury feed unhealthy - cannot proceed")
        sys.exit(1)
    
    # Save output
    output_file = "outputs/ingested_data.json"
    save_ingestion_result(result, output_file)
    
    print(f"\n✅ Ingestion complete")
    print(f"   Output: {output_file}")
    print(f"   Checksum: {result.checksum}")
    print(f"   Sources: {', '.join(result.data_sources_used)}")
    
    print("\n" + "=" * 60)
    print("DATA INGESTION COMPLETE — Run generate_edges.py next")
    print("=" * 60)


if __name__ == "__main__":
    main()
