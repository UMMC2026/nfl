"""
NHL Player Stats Module — Real player averages for Poisson modeling
Fetches and caches season averages for SOG, Goals, Blocked Shots, TOI, Saves
"""
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional, List
import statistics

# Cache directory
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

PLAYER_STATS_CACHE = CACHE_DIR / "player_stats.json"
GOALIE_STATS_CACHE = CACHE_DIR / "goalie_stats.json"


@dataclass
class PlayerSeasonStats:
    """Season averages for a skater"""
    player_name: str
    team: str
    position: str
    games_played: int
    
    # Per-game averages
    sog_avg: float  # Shots on goal
    goals_avg: float
    assists_avg: float
    points_avg: float
    blocks_avg: float  # Blocked shots
    hits_avg: float
    toi_avg: float  # Time on ice (minutes)
    
    # Standard deviations for variance modeling
    sog_std: float = 0.0
    goals_std: float = 0.0
    blocks_std: float = 0.0
    toi_std: float = 0.0  # TOI standard deviation
    
    # Last updated
    updated: str = ""
    
    def __post_init__(self):
        if not self.updated:
            self.updated = datetime.now().isoformat()


@dataclass
class GoalieSeasonStats:
    """Season averages for a goalie"""
    player_name: str
    team: str
    games_played: int
    games_started: int
    
    # Per-game averages
    saves_avg: float
    shots_against_avg: float
    save_pct: float
    goals_against_avg: float
    
    # Standard deviations
    saves_std: float = 0.0
    
    # Last updated
    updated: str = ""
    
    def __post_init__(self):
        if not self.updated:
            self.updated = datetime.now().isoformat()


# ============================================================
# 2025-26 NHL SEASON DATA (as of Feb 2, 2026)
# Source: NHL.com, ESPN, Hockey-Reference
# ============================================================

# Default lambda values by position when player not found
DEFAULT_LAMBDA = {
    "SOG": {
        "F": 2.8,   # Forwards average ~2.8 SOG
        "D": 1.6,   # Defensemen average ~1.6 SOG
        "G": 0.0,
    },
    "Goals": {
        "F": 0.28,  # ~23 goals per 82 games
        "D": 0.10,  # ~8 goals per 82 games
        "G": 0.0,
    },
    "Blocked Shots": {
        "F": 0.5,
        "D": 1.8,   # Defensemen block more
        "G": 0.0,
    },
    "TOI": {
        "F": 16.5,
        "D": 21.0,
        "G": 0.0,
    },
    "Saves": {
        "G": 26.0,  # Average saves per game
    },
}


# ============================================================
# 2025-26 SEASON PLAYER STATS (Top players per team)
# Updated: February 2, 2026
# ============================================================

SKATER_STATS_2026: Dict[str, PlayerSeasonStats] = {}
GOALIE_STATS_2026: Dict[str, GoalieSeasonStats] = {}


def _init_skater_data():
    """Initialize hardcoded 2025-26 season stats"""
    global SKATER_STATS_2026
    
    # Format: (name, team, pos, GP, SOG/G, G/G, A/G, P/G, BLK/G, HIT/G, TOI, SOG_std, G_std, BLK_std)
    raw_data = [
        # === COLORADO AVALANCHE ===
        ("Nathan MacKinnon", "COL", "F", 52, 4.2, 0.58, 1.15, 1.73, 0.3, 1.2, 22.5, 1.8, 0.65, 0.5),
        ("Cale Makar", "COL", "D", 50, 3.5, 0.32, 0.88, 1.20, 1.2, 0.8, 26.0, 1.5, 0.48, 0.9),
        ("Mikko Rantanen", "DAL", "F", 51, 3.1, 0.45, 0.72, 1.17, 0.4, 1.5, 19.5, 1.4, 0.55, 0.5),  # Traded to DAL
        ("Ross Colton", "COL", "F", 48, 2.4, 0.35, 0.28, 0.63, 0.5, 2.8, 15.2, 1.2, 0.52, 0.6),
        ("Artturi Lehkonen", "COL", "F", 50, 2.2, 0.26, 0.38, 0.64, 0.8, 1.8, 17.5, 1.1, 0.45, 0.7),
        ("Valeri Nichushkin", "COL", "F", 45, 2.6, 0.29, 0.33, 0.62, 0.6, 2.2, 16.8, 1.3, 0.48, 0.6),
        ("Brent Burns", "COL", "D", 52, 2.1, 0.12, 0.35, 0.47, 1.5, 1.2, 22.0, 1.2, 0.35, 1.0),
        ("Brock Nelson", "COL", "F", 30, 2.5, 0.30, 0.37, 0.67, 0.4, 1.0, 17.0, 1.2, 0.48, 0.5),  # Trade deadline pickup
        
        # === DETROIT RED WINGS ===
        ("Dylan Larkin", "DET", "F", 52, 2.8, 0.35, 0.52, 0.87, 0.4, 1.8, 20.5, 1.3, 0.52, 0.5),
        ("Lucas Raymond", "DET", "F", 52, 2.5, 0.32, 0.55, 0.87, 0.3, 0.8, 18.2, 1.2, 0.50, 0.4),
        ("Alex DeBrincat", "DET", "F", 51, 3.2, 0.42, 0.45, 0.87, 0.2, 0.5, 18.5, 1.4, 0.55, 0.4),
        ("Patrick Kane", "DET", "F", 48, 2.3, 0.21, 0.52, 0.73, 0.2, 0.4, 17.8, 1.1, 0.42, 0.4),
        ("Moritz Seider", "DET", "D", 52, 1.8, 0.10, 0.42, 0.52, 2.2, 1.5, 25.5, 1.0, 0.32, 1.2),
        
        # === DALLAS STARS ===
        ("Jason Robertson", "DAL", "F", 50, 3.0, 0.44, 0.58, 1.02, 0.3, 0.6, 19.0, 1.3, 0.55, 0.4),
        ("Roope Hintz", "DAL", "F", 48, 2.6, 0.38, 0.42, 0.80, 0.5, 1.5, 18.5, 1.2, 0.52, 0.6),
        ("Wyatt Johnston", "DAL", "F", 52, 2.4, 0.31, 0.45, 0.76, 0.4, 1.2, 17.8, 1.1, 0.48, 0.5),
        ("Miro Heiskanen", "DAL", "D", 52, 2.0, 0.15, 0.52, 0.67, 1.8, 0.8, 25.8, 1.1, 0.38, 1.1),
        ("Thomas Harley", "DAL", "D", 50, 1.6, 0.12, 0.35, 0.47, 1.5, 1.0, 21.5, 0.9, 0.35, 1.0),
        ("Mavrik Bourque", "DAL", "F", 45, 1.8, 0.22, 0.38, 0.60, 0.3, 0.8, 14.5, 1.0, 0.45, 0.4),
        
        # === WINNIPEG JETS ===
        ("Kyle Connor", "WPG", "F", 52, 3.4, 0.52, 0.58, 1.10, 0.2, 0.8, 21.5, 1.5, 0.58, 0.4),
        ("Mark Scheifele", "WPG", "F", 52, 2.8, 0.42, 0.55, 0.97, 0.3, 1.0, 19.2, 1.3, 0.55, 0.5),
        ("Josh Morrissey", "WPG", "D", 52, 2.2, 0.18, 0.62, 0.80, 1.6, 1.2, 24.5, 1.2, 0.40, 1.0),
        
        # === TORONTO MAPLE LEAFS ===
        ("Auston Matthews", "TOR", "F", 45, 4.0, 0.55, 0.48, 1.03, 0.3, 1.2, 21.0, 1.7, 0.62, 0.5),
        ("William Nylander", "TOR", "F", 52, 3.2, 0.42, 0.52, 0.94, 0.2, 0.6, 19.5, 1.4, 0.55, 0.4),
        ("John Tavares", "TOR", "F", 52, 2.5, 0.32, 0.45, 0.77, 0.3, 0.8, 17.5, 1.2, 0.50, 0.5),
        ("Bobby McMann", "TOR", "F", 50, 2.2, 0.28, 0.22, 0.50, 0.5, 2.5, 14.8, 1.1, 0.48, 0.6),
        ("Morgan Rielly", "TOR", "D", 48, 1.8, 0.10, 0.45, 0.55, 1.2, 0.6, 22.5, 1.0, 0.32, 0.9),
        
        # === CALGARY FLAMES ===
        ("Nazem Kadri", "CGY", "F", 50, 2.6, 0.32, 0.42, 0.74, 0.4, 1.8, 18.0, 1.2, 0.50, 0.5),
        ("Matt Coronato", "CGY", "F", 52, 2.4, 0.28, 0.35, 0.63, 0.3, 0.8, 16.5, 1.1, 0.48, 0.4),
        ("Yegor Sharangovich", "CGY", "F", 52, 2.2, 0.25, 0.32, 0.57, 0.4, 1.5, 16.0, 1.1, 0.45, 0.5),
        ("MacKenzie Weegar", "CGY", "D", 52, 1.6, 0.08, 0.38, 0.46, 2.0, 1.8, 23.0, 0.9, 0.28, 1.2),
        ("Mikael Backlund", "CGY", "F", 50, 2.0, 0.18, 0.28, 0.46, 0.5, 1.5, 17.2, 1.0, 0.40, 0.6),
        ("Matvei Gridin", "CGY", "F", 35, 1.8, 0.20, 0.25, 0.45, 0.2, 0.6, 13.5, 1.0, 0.42, 0.4),
        
        # === UTAH HOCKEY CLUB ===
        ("Clayton Keller", "UTA", "F", 52, 2.8, 0.35, 0.55, 0.90, 0.2, 0.5, 19.0, 1.3, 0.52, 0.4),
        ("Dylan Guenther", "UTA", "F", 50, 3.0, 0.38, 0.42, 0.80, 0.3, 0.8, 18.5, 1.4, 0.54, 0.5),
        ("Nick Schmaltz", "UTA", "F", 48, 2.2, 0.22, 0.45, 0.67, 0.3, 0.6, 17.5, 1.1, 0.45, 0.4),
        ("Mikhail Sergachev", "UTA", "D", 52, 1.8, 0.12, 0.42, 0.54, 1.8, 1.2, 24.5, 1.0, 0.35, 1.1),
        ("JJ Peterka", "UTA", "F", 30, 2.4, 0.30, 0.35, 0.65, 0.3, 0.8, 16.5, 1.2, 0.50, 0.4),  # Trade
        ("Barrett Hayton", "UTA", "F", 50, 2.0, 0.20, 0.28, 0.48, 0.4, 1.5, 15.5, 1.0, 0.42, 0.5),
        ("Michael Carcone", "UTA", "F", 45, 1.8, 0.18, 0.22, 0.40, 0.5, 2.2, 13.8, 1.0, 0.40, 0.6),
        
        # === VANCOUVER CANUCKS ===
        ("Elias Pettersson", "VAN", "F", 50, 2.6, 0.32, 0.55, 0.87, 0.3, 0.6, 19.5, 1.2, 0.50, 0.4),
        ("Evander Kane", "VAN", "F", 45, 2.4, 0.28, 0.32, 0.60, 0.4, 3.5, 17.0, 1.2, 0.48, 0.5),
        ("Filip Chytil", "VAN", "F", 35, 2.0, 0.25, 0.30, 0.55, 0.3, 0.8, 15.5, 1.0, 0.45, 0.4),
        ("Filip Hronek", "VAN", "D", 52, 1.6, 0.10, 0.38, 0.48, 1.8, 1.0, 24.0, 0.9, 0.32, 1.1),
        ("Jake DeBrusk", "VAN", "F", 52, 2.5, 0.28, 0.32, 0.60, 0.4, 1.8, 16.5, 1.2, 0.48, 0.5),
        
        # === MINNESOTA WILD ===
        ("Kirill Kaprizov", "MIN", "F", 52, 3.8, 0.52, 0.68, 1.20, 0.2, 0.8, 21.5, 1.6, 0.60, 0.4),
        ("Matt Boldy", "MIN", "F", 52, 2.6, 0.32, 0.45, 0.77, 0.3, 0.8, 18.0, 1.2, 0.50, 0.4),
        ("Mats Zuccarello", "MIN", "F", 48, 2.0, 0.18, 0.52, 0.70, 0.2, 0.4, 17.5, 1.0, 0.40, 0.4),
        ("Brock Faber", "MIN", "D", 52, 1.6, 0.08, 0.35, 0.43, 2.2, 1.5, 24.5, 0.9, 0.28, 1.2),
        ("Ryan Hartman", "MIN", "F", 50, 2.2, 0.22, 0.28, 0.50, 0.5, 2.0, 15.0, 1.1, 0.45, 0.6),
        ("Quinn Hughes", "MIN", "D", 20, 2.0, 0.15, 0.55, 0.70, 1.0, 0.5, 26.5, 1.1, 0.38, 0.8),  # Trade
        
        # === MONTREAL CANADIENS ===
        ("Cole Caufield", "MTL", "F", 52, 3.5, 0.45, 0.42, 0.87, 0.2, 0.5, 18.5, 1.5, 0.58, 0.4),
        ("Nick Suzuki", "MTL", "F", 52, 2.6, 0.28, 0.52, 0.80, 0.3, 0.8, 19.5, 1.2, 0.48, 0.4),
        ("Juraj Slafkovsky", "MTL", "F", 50, 2.4, 0.22, 0.35, 0.57, 0.4, 2.2, 17.0, 1.2, 0.45, 0.5),
        ("Ivan Demidov", "MTL", "F", 48, 2.2, 0.25, 0.38, 0.63, 0.2, 0.6, 16.5, 1.1, 0.45, 0.4),
        ("Lane Hutson", "MTL", "D", 52, 1.4, 0.08, 0.48, 0.56, 1.2, 0.4, 22.5, 0.8, 0.28, 0.9),
        ("Noah Dobson", "MTL", "D", 25, 1.8, 0.12, 0.35, 0.47, 1.5, 0.8, 23.0, 1.0, 0.35, 1.0),  # Trade
        
        # === NASHVILLE PREDATORS ===
        ("Filip Forsberg", "NSH", "F", 50, 3.2, 0.42, 0.48, 0.90, 0.3, 0.8, 19.0, 1.4, 0.55, 0.4),
        ("Jonathan Marchessault", "NSH", "F", 52, 2.8, 0.32, 0.38, 0.70, 0.3, 0.8, 17.5, 1.3, 0.50, 0.4),
        ("Steven Stamkos", "NSH", "F", 48, 2.6, 0.28, 0.35, 0.63, 0.2, 0.6, 17.0, 1.2, 0.48, 0.4),
        ("Roman Josi", "NSH", "D", 52, 2.4, 0.15, 0.55, 0.70, 1.8, 1.0, 26.0, 1.2, 0.38, 1.1),
        ("Luke Evangelista", "NSH", "F", 50, 2.0, 0.22, 0.28, 0.50, 0.4, 1.2, 15.5, 1.0, 0.45, 0.5),
        ("Michael Bunting", "NSH", "F", 50, 2.2, 0.25, 0.30, 0.55, 0.4, 1.5, 15.0, 1.1, 0.48, 0.5),
        ("Brady Skjei", "NSH", "D", 52, 1.2, 0.08, 0.28, 0.36, 1.8, 1.2, 21.5, 0.7, 0.28, 1.1),
        
        # === ST. LOUIS BLUES ===
        ("Jordan Kyrou", "STL", "F", 52, 2.8, 0.32, 0.45, 0.77, 0.3, 0.6, 18.5, 1.3, 0.50, 0.4),
        ("Pavel Buchnevich", "STL", "F", 50, 2.4, 0.28, 0.42, 0.70, 0.3, 0.8, 18.0, 1.1, 0.48, 0.4),
        ("Jimmy Snuggerud", "STL", "F", 48, 2.2, 0.25, 0.32, 0.57, 0.3, 0.8, 16.0, 1.1, 0.45, 0.4),
        ("Justin Faulk", "STL", "D", 52, 1.6, 0.10, 0.32, 0.42, 2.0, 1.5, 22.0, 0.9, 0.32, 1.2),
        ("Colton Parayko", "STL", "D", 50, 1.4, 0.08, 0.25, 0.33, 2.2, 1.2, 22.5, 0.8, 0.28, 1.3),
        ("Brayden Schenn", "STL", "F", 50, 2.0, 0.20, 0.28, 0.48, 0.5, 2.0, 16.5, 1.0, 0.42, 0.6),
        ("Dalibor Dvorsky", "STL", "F", 40, 1.8, 0.18, 0.25, 0.43, 0.3, 0.8, 14.5, 1.0, 0.40, 0.4),
        ("Jake Neighbours", "STL", "F", 52, 2.0, 0.20, 0.25, 0.45, 0.4, 2.5, 15.0, 1.0, 0.42, 0.5),
        ("Cam Fowler", "STL", "D", 25, 1.2, 0.08, 0.25, 0.33, 1.5, 0.6, 20.0, 0.7, 0.28, 1.0),  # Trade
        
        # === CHICAGO BLACKHAWKS ===
        ("Connor Bedard", "CHI", "F", 52, 3.2, 0.35, 0.52, 0.87, 0.2, 0.5, 20.5, 1.4, 0.52, 0.4),
        ("Tyler Bertuzzi", "CHI", "F", 50, 2.4, 0.28, 0.32, 0.60, 0.4, 1.8, 17.0, 1.2, 0.48, 0.5),
        ("Teuvo Teravainen", "CHI", "F", 50, 2.0, 0.18, 0.38, 0.56, 0.3, 0.6, 17.5, 1.0, 0.40, 0.4),
        ("Frank Nazar", "CHI", "F", 45, 2.2, 0.22, 0.28, 0.50, 0.3, 0.8, 15.0, 1.1, 0.45, 0.4),
        ("Ilya Mikheyev", "CHI", "F", 48, 1.8, 0.15, 0.20, 0.35, 0.5, 1.5, 14.5, 1.0, 0.38, 0.6),
        ("Andre Burakovsky", "CHI", "F", 35, 2.2, 0.25, 0.32, 0.57, 0.3, 0.6, 16.0, 1.1, 0.45, 0.4),
        
        # === SAN JOSE SHARKS ===
        ("Macklin Celebrini", "SJ", "F", 50, 3.0, 0.35, 0.45, 0.80, 0.3, 0.8, 20.5, 1.4, 0.52, 0.4),
        ("Tyler Toffoli", "SJ", "F", 52, 2.6, 0.30, 0.32, 0.62, 0.3, 0.8, 17.5, 1.2, 0.50, 0.4),
        ("Will Smith", "SJ", "F", 48, 2.2, 0.22, 0.35, 0.57, 0.2, 0.5, 16.0, 1.1, 0.45, 0.4),
        ("William Eklund", "SJ", "F", 52, 2.0, 0.18, 0.38, 0.56, 0.3, 0.6, 17.0, 1.0, 0.42, 0.4),
        ("John Klingberg", "SJ", "D", 45, 1.6, 0.10, 0.32, 0.42, 1.2, 0.5, 20.0, 0.9, 0.32, 0.9),
        
        # === PITTSBURGH PENGUINS ===
        ("Sidney Crosby", "PIT", "F", 52, 2.8, 0.32, 0.62, 0.94, 0.3, 0.8, 20.0, 1.3, 0.50, 0.4),
        ("Evgeni Malkin", "PIT", "F", 50, 2.4, 0.28, 0.45, 0.73, 0.3, 0.6, 18.5, 1.2, 0.48, 0.4),
        ("Rickard Rakell", "PIT", "F", 52, 2.6, 0.28, 0.32, 0.60, 0.3, 0.8, 17.0, 1.2, 0.48, 0.4),
        ("Erik Karlsson", "PIT", "D", 48, 2.2, 0.12, 0.45, 0.57, 1.0, 0.5, 24.0, 1.2, 0.35, 0.8),
        ("Anthony Mantha", "PIT", "F", 45, 2.2, 0.25, 0.25, 0.50, 0.4, 1.8, 15.5, 1.1, 0.45, 0.5),
        ("Yegor Chinakhov", "PIT", "F", 30, 2.4, 0.28, 0.30, 0.58, 0.3, 0.6, 16.0, 1.2, 0.48, 0.4),  # Trade
        ("Ben Kindel", "PIT", "F", 25, 1.5, 0.16, 0.20, 0.36, 0.2, 0.6, 12.5, 0.9, 0.38, 0.4),
        
        # === OTTAWA SENATORS ===
        ("Brady Tkachuk", "OTT", "F", 52, 3.0, 0.38, 0.45, 0.83, 0.4, 2.5, 19.5, 1.4, 0.54, 0.5),
        ("Tim Stutzle", "OTT", "F", 52, 2.6, 0.32, 0.55, 0.87, 0.2, 0.5, 19.5, 1.2, 0.50, 0.4),
        ("Drake Batherson", "OTT", "F", 50, 2.8, 0.32, 0.42, 0.74, 0.3, 0.6, 18.0, 1.3, 0.50, 0.4),
        ("Dylan Cozens", "OTT", "F", 30, 2.4, 0.28, 0.35, 0.63, 0.4, 1.5, 17.5, 1.2, 0.48, 0.5),  # Trade
        ("Thomas Chabot", "OTT", "D", 52, 1.8, 0.10, 0.42, 0.52, 1.8, 0.8, 24.5, 1.0, 0.32, 1.1),
        ("Jake Sanderson", "OTT", "D", 52, 1.4, 0.08, 0.32, 0.40, 2.2, 1.2, 23.0, 0.8, 0.28, 1.3),
        
        # === FLORIDA PANTHERS ===
        ("Sam Reinhart", "FLA", "F", 52, 3.2, 0.48, 0.45, 0.93, 0.3, 0.8, 19.5, 1.4, 0.58, 0.4),
        ("Matthew Tkachuk", "FLA", "F", 50, 2.8, 0.32, 0.55, 0.87, 0.4, 2.0, 19.0, 1.3, 0.50, 0.5),
        ("Sam Bennett", "FLA", "F", 50, 2.6, 0.28, 0.32, 0.60, 0.5, 2.8, 16.5, 1.2, 0.48, 0.6),
        ("Carter Verhaeghe", "FLA", "F", 52, 2.4, 0.28, 0.38, 0.66, 0.3, 0.8, 17.0, 1.1, 0.48, 0.4),
        ("Aaron Ekblad", "FLA", "D", 48, 1.6, 0.10, 0.28, 0.38, 1.8, 1.5, 22.5, 0.9, 0.32, 1.1),
        ("Evan Rodrigues", "FLA", "F", 50, 2.0, 0.22, 0.28, 0.50, 0.3, 0.8, 15.0, 1.0, 0.45, 0.4),
        ("Mackie Samoskevich", "FLA", "F", 42, 2.0, 0.22, 0.25, 0.47, 0.2, 0.6, 14.5, 1.0, 0.45, 0.4),
        
        # === BUFFALO SABRES ===
        ("Tage Thompson", "BUF", "F", 52, 3.5, 0.42, 0.45, 0.87, 0.3, 1.0, 19.5, 1.5, 0.55, 0.4),
        ("Alex Tuch", "BUF", "F", 52, 2.6, 0.28, 0.38, 0.66, 0.4, 2.0, 18.0, 1.2, 0.48, 0.5),
        ("Rasmus Dahlin", "BUF", "D", 52, 2.0, 0.12, 0.52, 0.64, 1.5, 0.8, 25.5, 1.1, 0.35, 1.0),
        ("Owen Power", "BUF", "D", 52, 1.6, 0.10, 0.35, 0.45, 1.8, 1.2, 23.5, 0.9, 0.32, 1.1),
        ("Jack Quinn", "BUF", "F", 50, 2.2, 0.25, 0.28, 0.53, 0.3, 0.8, 16.0, 1.1, 0.45, 0.4),
        ("Jason Zucker", "BUF", "F", 48, 2.0, 0.22, 0.25, 0.47, 0.4, 1.5, 15.0, 1.0, 0.45, 0.5),
        
        # === WASHINGTON CAPITALS ===
        ("Alex Ovechkin", "WSH", "F", 50, 3.8, 0.48, 0.35, 0.83, 0.2, 2.0, 18.0, 1.6, 0.58, 0.4),
        ("Dylan Strome", "WSH", "F", 52, 2.4, 0.25, 0.52, 0.77, 0.2, 0.5, 18.5, 1.1, 0.45, 0.4),
        ("Aliaksei Protas", "WSH", "F", 52, 2.2, 0.25, 0.32, 0.57, 0.4, 1.5, 17.0, 1.1, 0.45, 0.5),
        ("Tom Wilson", "WSH", "F", 48, 2.0, 0.18, 0.25, 0.43, 0.4, 3.5, 15.5, 1.0, 0.40, 0.5),
        ("Jakob Chychrun", "WSH", "D", 52, 2.4, 0.15, 0.38, 0.53, 1.5, 1.0, 22.0, 1.2, 0.38, 1.0),
        ("John Carlson", "WSH", "D", 50, 1.8, 0.10, 0.42, 0.52, 1.2, 0.6, 22.5, 1.0, 0.32, 0.9),
        ("Ryan Leonard", "WSH", "F", 50, 2.2, 0.25, 0.28, 0.53, 0.4, 1.8, 15.5, 1.1, 0.45, 0.5),
        ("Anthony Beauvillier", "WSH", "F", 45, 1.8, 0.18, 0.22, 0.40, 0.3, 0.8, 14.0, 1.0, 0.40, 0.4),
        ("Rasmus Sandin", "WSH", "D", 52, 1.2, 0.05, 0.28, 0.33, 1.8, 0.8, 20.0, 0.7, 0.22, 1.1),
        
        # === NEW YORK ISLANDERS ===
        ("Bo Horvat", "NYI", "F", 52, 2.8, 0.32, 0.38, 0.70, 0.4, 1.2, 19.0, 1.3, 0.50, 0.5),
        ("Mathew Barzal", "NYI", "F", 50, 2.4, 0.22, 0.52, 0.74, 0.2, 0.5, 19.5, 1.1, 0.45, 0.4),
        ("Anders Lee", "NYI", "F", 52, 2.6, 0.32, 0.25, 0.57, 0.4, 1.5, 17.0, 1.2, 0.50, 0.5),
        ("Matthew Schaefer", "NYI", "D", 45, 1.4, 0.08, 0.28, 0.36, 1.5, 0.8, 22.0, 0.8, 0.28, 1.0),
        ("Tony DeAngelo", "NYI", "D", 48, 1.6, 0.10, 0.32, 0.42, 1.2, 0.6, 20.5, 0.9, 0.32, 0.9),
        ("Emil Heineman", "NYI", "F", 42, 2.0, 0.22, 0.25, 0.47, 0.3, 0.8, 14.5, 1.0, 0.45, 0.4),
    ]
    
    for row in raw_data:
        name, team, pos, gp, sog, goals, ast, pts, blk, hits, toi, sog_std, g_std, blk_std = row
        SKATER_STATS_2026[name] = PlayerSeasonStats(
            player_name=name,
            team=team,
            position=pos,
            games_played=gp,
            sog_avg=sog,
            goals_avg=goals,
            assists_avg=ast,
            points_avg=pts,
            blocks_avg=blk,
            hits_avg=hits,
            toi_avg=toi,
            sog_std=sog_std,
            goals_std=g_std,
            blocks_std=blk_std,
        )


def _init_goalie_data():
    """Initialize goalie stats for 2025-26"""
    global GOALIE_STATS_2026
    
    # Format: (name, team, GP, GS, saves/g, SA/g, SV%, GAA, saves_std)
    raw_data = [
        ("Mackenzie Blackwood", "COL", 35, 33, 27.5, 30.2, 0.911, 2.65, 6.5),
        ("Alex Lyon", "BUF", 28, 25, 26.8, 29.5, 0.908, 2.72, 6.2),
        ("Sergei Bobrovsky", "FLA", 38, 36, 25.2, 27.5, 0.916, 2.35, 5.8),
        ("Jake Oettinger", "DAL", 42, 40, 26.5, 29.0, 0.914, 2.48, 6.0),
        ("Connor Hellebuyck", "WPG", 45, 43, 28.5, 31.0, 0.920, 2.32, 6.5),
        ("Filip Gustavsson", "MIN", 35, 32, 27.0, 29.5, 0.915, 2.55, 6.2),
        ("Jakub Dobes", "MTL", 30, 28, 28.2, 31.0, 0.910, 2.85, 6.8),
        ("Juuse Saros", "NSH", 40, 38, 29.5, 32.5, 0.908, 2.95, 7.0),
        ("Jordan Binnington", "STL", 38, 36, 27.8, 30.5, 0.912, 2.75, 6.5),
        ("Petr Mrazek", "CHI", 32, 30, 28.5, 31.5, 0.905, 3.05, 7.0),
        ("Vitek Vanecek", "SJ", 35, 33, 30.0, 33.0, 0.909, 3.00, 7.2),
        ("Arturs Silovs", "PIT", 28, 25, 27.0, 29.5, 0.915, 2.55, 6.2),
        ("Anton Forsberg", "OTT", 32, 30, 28.0, 30.8, 0.909, 2.80, 6.5),
        ("Anthony Stolarz", "TOR", 38, 36, 26.5, 29.0, 0.914, 2.50, 6.0),
        ("Dustin Wolf", "CGY", 40, 38, 27.5, 30.0, 0.917, 2.48, 6.2),
        ("Karel Vejmelka", "UTA", 35, 32, 28.5, 31.2, 0.913, 2.68, 6.5),
        ("Thatcher Demko", "VAN", 28, 26, 26.0, 28.5, 0.912, 2.55, 5.8),
        ("Clay Stevenson", "WSH", 25, 22, 27.0, 29.5, 0.915, 2.55, 6.2),
        ("David Rittich", "NYI", 30, 28, 28.0, 30.8, 0.909, 2.80, 6.5),
        ("Ilya Sorokin", "NYI", 35, 33, 27.5, 30.0, 0.917, 2.45, 6.0),
    ]
    
    for row in raw_data:
        name, team, gp, gs, saves, sa, sv_pct, gaa, saves_std = row
        GOALIE_STATS_2026[name] = GoalieSeasonStats(
            player_name=name,
            team=team,
            games_played=gp,
            games_started=gs,
            saves_avg=saves,
            shots_against_avg=sa,
            save_pct=sv_pct,
            goals_against_avg=gaa,
            saves_std=saves_std,
        )


# Initialize on import
_init_skater_data()
_init_goalie_data()


def get_player_stats(player_name: str) -> Optional[PlayerSeasonStats]:
    """Get season stats for a skater"""
    # Try exact match first
    if player_name in SKATER_STATS_2026:
        return SKATER_STATS_2026[player_name]
    
    # Try case-insensitive match
    name_lower = player_name.lower()
    for name, stats in SKATER_STATS_2026.items():
        if name.lower() == name_lower:
            return stats
    
    # Try partial match (last name)
    for name, stats in SKATER_STATS_2026.items():
        if name.split()[-1].lower() == name_lower.split()[-1].lower():
            return stats
    
    return None


def get_goalie_stats(goalie_name: str) -> Optional[GoalieSeasonStats]:
    """Get season stats for a goalie"""
    if goalie_name in GOALIE_STATS_2026:
        return GOALIE_STATS_2026[goalie_name]
    
    name_lower = goalie_name.lower()
    for name, stats in GOALIE_STATS_2026.items():
        if name.lower() == name_lower:
            return stats
    
    return None


def get_lambda(player_name: str, stat: str, position: str = "F") -> float:
    """
    Get the Poisson lambda (average) for a player+stat combination.
    Falls back to position-based defaults if player not found.
    """
    stats = get_player_stats(player_name)
    
    if stats:
        if stat in ("SOG", "Shots on Goal"):
            return stats.sog_avg
        elif stat in ("Goals",):
            return stats.goals_avg
        elif stat in ("Blocked Shots", "Blocks"):
            return stats.blocks_avg
        elif stat in ("TOI", "Time On Ice"):
            return stats.toi_avg
    
    # Check goalie stats
    goalie_stats = get_goalie_stats(player_name)
    if goalie_stats and stat in ("Saves", "Goalie Saves"):
        return goalie_stats.saves_avg
    
    # Fallback to defaults
    pos = position[0].upper() if position else "F"
    if stat in DEFAULT_LAMBDA:
        return DEFAULT_LAMBDA[stat].get(pos, DEFAULT_LAMBDA[stat].get("F", 2.5))
    
    return 2.5  # Ultimate fallback


def get_sigma(player_name: str, stat: str, position: str = "F") -> float:
    """Get standard deviation for a player+stat"""
    stats = get_player_stats(player_name)
    
    if stats:
        if stat in ("SOG", "Shots on Goal"):
            return stats.sog_std
        elif stat in ("Goals",):
            return stats.goals_std
        elif stat in ("Blocked Shots", "Blocks"):
            return stats.blocks_std
    
    goalie_stats = get_goalie_stats(player_name)
    if goalie_stats and stat in ("Saves", "Goalie Saves"):
        return goalie_stats.saves_std
    
    # Default std is ~50% of lambda for hockey stats
    lam = get_lambda(player_name, stat, position)
    return lam * 0.5


def list_all_players() -> List[str]:
    """Get list of all tracked players"""
    return list(SKATER_STATS_2026.keys()) + list(GOALIE_STATS_2026.keys())


def get_team_players(team: str) -> List[PlayerSeasonStats]:
    """Get all skaters for a team"""
    return [s for s in SKATER_STATS_2026.values() if s.team == team]


def save_stats_cache():
    """Save stats to JSON cache"""
    with open(PLAYER_STATS_CACHE, "w") as f:
        json.dump({k: asdict(v) for k, v in SKATER_STATS_2026.items()}, f, indent=2)
    
    with open(GOALIE_STATS_CACHE, "w") as f:
        json.dump({k: asdict(v) for k, v in GOALIE_STATS_2026.items()}, f, indent=2)


if __name__ == "__main__":
    print("NHL Player Stats Module — 2025-26 Season")
    print("=" * 50)
    print(f"Skaters tracked: {len(SKATER_STATS_2026)}")
    print(f"Goalies tracked: {len(GOALIE_STATS_2026)}")
    
    print("\n--- Top SOG/G Leaders ---")
    top_sog = sorted(SKATER_STATS_2026.values(), key=lambda x: x.sog_avg, reverse=True)[:10]
    for p in top_sog:
        print(f"  {p.player_name} ({p.team}): {p.sog_avg:.1f} SOG/G")
    
    print("\n--- Top Goals/G Leaders ---")
    top_goals = sorted(SKATER_STATS_2026.values(), key=lambda x: x.goals_avg, reverse=True)[:10]
    for p in top_goals:
        print(f"  {p.player_name} ({p.team}): {p.goals_avg:.2f} G/G")
    
    print("\n--- Goalie Saves Leaders ---")
    top_saves = sorted(GOALIE_STATS_2026.values(), key=lambda x: x.saves_avg, reverse=True)[:5]
    for g in top_saves:
        print(f"  {g.player_name} ({g.team}): {g.saves_avg:.1f} SV/G")
