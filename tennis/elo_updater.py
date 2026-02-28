"""
Tennis Elo Rating System — Dynamic Updates
==========================================
Updates player Elo ratings after each match result.
Prevents Elo drift and maintains accuracy.

Usage:
    from tennis.elo_updater import TennisEloSystem
    
    elo_sys = TennisEloSystem()
    elo_sys.update_match_result("Jannik Sinner", "Carlos Alcaraz", "HARD", "ATP_1000")
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

TENNIS_DIR = Path(__file__).parent
DATA_DIR = TENNIS_DIR / "data"
PLAYER_STATS_FILE = DATA_DIR / "player_stats.json"

# Standard tennis K-factors by tournament tier
K_FACTORS = {
    "GRAND_SLAM": 32,
    "ATP_1000": 24,
    "ATP_500": 20,
    "ATP_250": 16,
    "CHALLENGER": 12,
    "ITF": 8,
    "EXHIBITION": 4,
}

DEFAULT_ELO = 1500.0


class TennisEloSystem:
    """
    Manages Elo ratings for tennis players.
    Uses surface-specific Elo (HARD, CLAY, GRASS, INDOOR).
    """
    
    def __init__(self, stats_file: Optional[Path] = None):
        self.stats_file = stats_file or PLAYER_STATS_FILE
        self.players = self._load_stats()
    
    def _load_stats(self) -> Dict:
        """Load player_stats.json."""
        if not self.stats_file.exists():
            return {}
        
        try:
            return json.loads(self.stats_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    
    def _save_stats(self):
        """Save updated stats back to file."""
        try:
            self.stats_file.write_text(
                json.dumps(self.players, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[ELO] Error saving stats: {e}")
    
    def get_elo(self, player: str, surface: str) -> float:
        """Get current Elo for player on surface."""
        player_key = player.lower()
        
        if player_key not in self.players:
            return DEFAULT_ELO
        
        elo_field = f"elo_{surface.lower()}"
        
        # Check nested elo dict first
        elo_dict = self.players[player_key].get("elo", {})
        if isinstance(elo_dict, dict) and surface.upper() in elo_dict:
            return float(elo_dict[surface.upper()])
        
        # Fallback to flat field
        return float(self.players[player_key].get(elo_field, DEFAULT_ELO))
    
    def set_elo(self, player: str, surface: str, new_elo: float):
        """Update Elo for player on surface."""
        player_key = player.lower()
        
        # Initialize player if not exists
        if player_key not in self.players:
            self.players[player_key] = {
                "name": player,
                "tour": "ATP",  # Default
                "elo": {}
            }
        
        # Use nested elo dict (preferred format)
        if "elo" not in self.players[player_key]:
            self.players[player_key]["elo"] = {}
        
        self.players[player_key]["elo"][surface.upper()] = round(new_elo, 2)
        self.players[player_key]["elo_updated"] = datetime.now().isoformat()
    
    def get_k_factor(self, tournament_tier: str) -> int:
        """Get K-factor for tournament tier."""
        return K_FACTORS.get(tournament_tier.upper(), 20)
    
    def expected_score(self, elo_a: float, elo_b: float) -> float:
        """
        Calculate expected score for player A.
        Returns probability between 0.0 and 1.0.
        """
        return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400))
    
    def update_match_result(
        self,
        winner: str,
        loser: str,
        surface: str,
        tournament_tier: str = "ATP_500",
        save: bool = True
    ) -> Dict[str, float]:
        """
        Update Elo ratings after a match result.
        
        Args:
            winner: Winner's name
            loser: Loser's name
            surface: HARD, CLAY, GRASS, or INDOOR
            tournament_tier: Tournament importance (affects K-factor)
            save: Whether to save changes to file
        
        Returns:
            Dict with old and new Elos for both players
        """
        k = self.get_k_factor(tournament_tier)
        
        # Get current Elos
        elo_w_old = self.get_elo(winner, surface)
        elo_l_old = self.get_elo(loser, surface)
        
        # Calculate expected scores
        expected_w = self.expected_score(elo_w_old, elo_l_old)
        expected_l = 1.0 - expected_w
        
        # Update Elos
        elo_w_new = elo_w_old + k * (1.0 - expected_w)
        elo_l_new = elo_l_old + k * (0.0 - expected_l)
        
        # Save
        self.set_elo(winner, surface, elo_w_new)
        self.set_elo(loser, surface, elo_l_new)
        
        if save:
            self._save_stats()
        
        return {
            "winner": winner,
            "loser": loser,
            "surface": surface,
            "k_factor": k,
            "winner_elo_old": round(elo_w_old, 2),
            "winner_elo_new": round(elo_w_new, 2),
            "winner_change": round(elo_w_new - elo_w_old, 2),
            "loser_elo_old": round(elo_l_old, 2),
            "loser_elo_new": round(elo_l_new, 2),
            "loser_change": round(elo_l_new - elo_l_old, 2),
        }


def update_from_match_string(match_result: str, surface: str = "HARD", tier: str = "ATP_500"):
    """
    Convenience function to update Elo from match result string.
    
    Example:
        update_from_match_string("Sinner def. Alcaraz", "HARD", "GRAND_SLAM")
    """
    elo_sys = TennisEloSystem()
    
    # Parse winner/loser
    parts = match_result.lower().replace("def.", "|").replace("defeated", "|").split("|")
    if len(parts) != 2:
        print("[ELO] Invalid match string format. Use: 'Winner def. Loser'")
        return
    
    winner = parts[0].strip().title()
    loser = parts[1].strip().title()
    
    result = elo_sys.update_match_result(winner, loser, surface, tier)
    
    print(f"\n[ELO UPDATE] {winner} def. {loser} ({surface}, {tier})")
    print(f"  {winner}: {result['winner_elo_old']} → {result['winner_elo_new']} ({result['winner_change']:+.2f})")
    print(f"  {loser}: {result['loser_elo_old']} → {result['loser_elo_new']} ({result['loser_change']:+.2f})")


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        match_str = " ".join(sys.argv[1:])
        update_from_match_string(match_str)
    else:
        print("Usage: python elo_updater.py 'Sinner def. Alcaraz'")
