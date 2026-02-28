"""
Tennis Elo Rating System
========================
Surface-weighted Elo for match probability estimation.

This is the foundation probability engine.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

TENNIS_DIR = Path(__file__).parent
ELO_FILE = TENNIS_DIR / "player_elo.json"

# Default Elo for new players
DEFAULT_ELO = 1500
K_FACTOR = 32

# Surface-specific Elo adjustments
SURFACE_K_WEIGHT = {
    "HARD": 1.0,
    "CLAY": 1.2,    # Clay specialists diverge more
    "GRASS": 1.3,   # Grass is most specialized
    "INDOOR": 0.9,  # Similar to hard
}


def load_elo_ratings() -> Dict:
    """Load player Elo ratings from file."""
    if ELO_FILE.exists():
        return json.loads(ELO_FILE.read_text())
    return {"players": {}, "last_updated": None}


def save_elo_ratings(data: Dict):
    """Save player Elo ratings to file."""
    data["last_updated"] = datetime.now().isoformat()
    ELO_FILE.write_text(json.dumps(data, indent=2))


def get_player_elo(player: str, surface: str = "HARD", data: Dict = None) -> float:
    """Get player's Elo rating for a specific surface."""
    if data is None:
        data = load_elo_ratings()
    
    players = data.get("players", {})
    player_data = players.get(player, {})
    
    # Try surface-specific first, then overall
    surface_elo = player_data.get(f"elo_{surface.lower()}", None)
    overall_elo = player_data.get("elo_overall", DEFAULT_ELO)
    
    if surface_elo is not None:
        # Blend surface-specific with overall (70% surface, 30% overall)
        return 0.7 * surface_elo + 0.3 * overall_elo
    
    return overall_elo


def expected_score(elo_a: float, elo_b: float) -> float:
    """Calculate expected score (win probability) for player A."""
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400))


def elo_probability(player_a: str, player_b: str, surface: str = "HARD") -> Tuple[float, float]:
    """
    Calculate match win probabilities based on Elo.
    
    Returns: (prob_a_wins, prob_b_wins)
    """
    data = load_elo_ratings()
    
    elo_a = get_player_elo(player_a, surface, data)
    elo_b = get_player_elo(player_b, surface, data)
    
    prob_a = expected_score(elo_a, elo_b)
    prob_b = 1.0 - prob_a
    
    return prob_a, prob_b


def update_elo(player_a: str, player_b: str, winner: str, surface: str = "HARD"):
    """
    Update Elo ratings after a match.
    
    Called during FINAL resolution only.
    """
    data = load_elo_ratings()
    players = data.setdefault("players", {})
    
    # Initialize players if needed
    for player in [player_a, player_b]:
        if player not in players:
            players[player] = {
                "elo_overall": DEFAULT_ELO,
                "matches_played": 0,
            }
    
    # Get current ratings
    elo_a = get_player_elo(player_a, surface, data)
    elo_b = get_player_elo(player_b, surface, data)
    
    # Calculate expected scores
    exp_a = expected_score(elo_a, elo_b)
    exp_b = 1.0 - exp_a
    
    # Actual scores
    score_a = 1.0 if winner == player_a else 0.0
    score_b = 1.0 - score_a
    
    # Surface-weighted K factor
    k = K_FACTOR * SURFACE_K_WEIGHT.get(surface.upper(), 1.0)
    
    # Update Elo
    new_elo_a = elo_a + k * (score_a - exp_a)
    new_elo_b = elo_b + k * (score_b - exp_b)
    
    # Store updates
    surface_key = f"elo_{surface.lower()}"
    players[player_a][surface_key] = new_elo_a
    players[player_b][surface_key] = new_elo_b
    
    # Update overall (weighted average of surface ratings)
    for player in [player_a, player_b]:
        surface_ratings = [
            players[player].get(f"elo_{s.lower()}", DEFAULT_ELO)
            for s in ["HARD", "CLAY", "GRASS"]
            if f"elo_{s.lower()}" in players[player]
        ]
        if surface_ratings:
            players[player]["elo_overall"] = sum(surface_ratings) / len(surface_ratings)
        players[player]["matches_played"] = players[player].get("matches_played", 0) + 1
    
    save_elo_ratings(data)
    
    return new_elo_a, new_elo_b


def get_elo_summary(player: str) -> Dict:
    """Get a player's Elo summary across surfaces."""
    data = load_elo_ratings()
    player_data = data.get("players", {}).get(player, {})
    
    return {
        "player": player,
        "overall": player_data.get("elo_overall", DEFAULT_ELO),
        "hard": player_data.get("elo_hard", None),
        "clay": player_data.get("elo_clay", None),
        "grass": player_data.get("elo_grass", None),
        "matches": player_data.get("matches_played", 0),
    }


# Seed some initial Elo ratings for top players
SEED_RATINGS = {
    # ATP Top 10 (approximate)
    "Jannik Sinner": {"elo_overall": 2100, "elo_hard": 2150, "elo_clay": 2000},
    "Carlos Alcaraz": {"elo_overall": 2080, "elo_hard": 2050, "elo_clay": 2100, "elo_grass": 2100},
    "Novak Djokovic": {"elo_overall": 2050, "elo_hard": 2100, "elo_clay": 2000, "elo_grass": 2050},
    "Alexander Zverev": {"elo_overall": 1950, "elo_hard": 1950, "elo_clay": 1980},
    "Daniil Medvedev": {"elo_overall": 1920, "elo_hard": 2000, "elo_clay": 1750},
    "Andrey Rublev": {"elo_overall": 1850, "elo_hard": 1870, "elo_clay": 1850},
    "Casper Ruud": {"elo_overall": 1830, "elo_hard": 1780, "elo_clay": 1950},
    "Hubert Hurkacz": {"elo_overall": 1800, "elo_hard": 1820, "elo_grass": 1850},
    "Taylor Fritz": {"elo_overall": 1780, "elo_hard": 1820},
    "Alex de Minaur": {"elo_overall": 1760, "elo_hard": 1800},
    
    # WTA Top 10 (approximate)
    "Iga Swiatek": {"elo_overall": 2100, "elo_hard": 2000, "elo_clay": 2200},
    "Aryna Sabalenka": {"elo_overall": 2050, "elo_hard": 2100, "elo_clay": 1900},
    "Coco Gauff": {"elo_overall": 1950, "elo_hard": 1980, "elo_clay": 1920},
    "Elena Rybakina": {"elo_overall": 1920, "elo_hard": 1950, "elo_grass": 2000},
    "Jessica Pegula": {"elo_overall": 1880, "elo_hard": 1920},
    "Qinwen Zheng": {"elo_overall": 1850, "elo_hard": 1900},
    "Jasmine Paolini": {"elo_overall": 1830, "elo_clay": 1900},
}


def seed_initial_ratings():
    """Seed initial Elo ratings for known players."""
    data = load_elo_ratings()
    players = data.setdefault("players", {})
    
    for player, ratings in SEED_RATINGS.items():
        if player not in players:
            players[player] = ratings
            players[player]["matches_played"] = 50  # Assume established
    
    save_elo_ratings(data)
    print(f"✓ Seeded {len(SEED_RATINGS)} player Elo ratings")


if __name__ == "__main__":
    seed_initial_ratings()
