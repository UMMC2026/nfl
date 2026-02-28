"""
Tennis Stats Data Layer
=======================
Fetches player statistics for Monte Carlo simulations.

Data sources:
- Tennis Abstract (free stats API)
- Ultimate Tennis Statistics (if available)
- Manual CSV fallback

Stats needed for props:
- Aces per match
- Break Points Won per match
- Games Won per match
- Fantasy Score components
- Surface splits (Hard/Clay/Grass)
"""

import requests
from dataclasses import dataclass
from typing import Optional, Dict, List
import json
from pathlib import Path
from datetime import datetime, timedelta


@dataclass
class TennisPlayerStats:
    """Player statistics for Monte Carlo modeling"""
    player: str
    
    # Recent averages (L5, L10, season)
    aces_l5: float = 0.0
    aces_l10: float = 0.0
    aces_season: float = 0.0
    aces_std: float = 0.0  # Standard deviation
    
    breakpoints_won_l5: float = 0.0
    breakpoints_won_l10: float = 0.0
    breakpoints_won_season: float = 0.0
    breakpoints_won_std: float = 0.0
    
    games_won_l5: float = 0.0
    games_won_l10: float = 0.0
    games_won_season: float = 0.0
    games_won_std: float = 0.0
    
    fantasy_score_l5: float = 0.0
    fantasy_score_l10: float = 0.0
    fantasy_score_season: float = 0.0
    fantasy_score_std: float = 0.0
    
    # Total games (both players combined)
    total_games_l5: float = 0.0
    total_games_l10: float = 0.0
    total_games_season: float = 0.0
    total_games_std: float = 0.0
    
    # Double faults
    double_faults_l5: float = 0.0
    double_faults_l10: float = 0.0
    double_faults_season: float = 0.0
    double_faults_std: float = 0.0
    
    # Tiebreakers
    tiebreakers_l5: float = 0.0
    tiebreakers_l10: float = 0.0
    tiebreakers_season: float = 0.0
    tiebreakers_std: float = 0.0
    
    # Sets won
    sets_won_l5: float = 0.0
    sets_won_l10: float = 0.0
    sets_won_season: float = 0.0
    sets_won_std: float = 0.0
    
    # Sets played
    sets_played_l5: float = 0.0
    sets_played_l10: float = 0.0
    sets_played_season: float = 0.0
    sets_played_std: float = 0.0
    
    # Surface splits
    surface: str = "Hard"  # Hard/Clay/Grass
    surface_adjustment: float = 1.0
    
    # Opponent adjustment
    opponent_strength: float = 1.0
    
    # Metadata
    matches_played: int = 0
    last_updated: str = ""


class TennisStatsAPI:
    """Fetches tennis player statistics.

    Phase 1 uses mock data + a lightweight L10 patch lane that allows
    external scrapers to inject real-time form without changing the
    Monte Carlo interface.
    """
    
    def __init__(self):
        self.cache_dir = Path(__file__).parent / "stats_cache"
        self.cache_dir.mkdir(exist_ok=True)
        # Optional directory for L10 patches written by scrapers.
        # Each file should be ``{player_name}.json`` with a schema
        # compatible with ``apply_l10_patch_from_dict`` in l10_form_engine.
        self.l10_patch_dir = self.cache_dir / "l10_patches"
        self.l10_patch_dir.mkdir(exist_ok=True)

        self.session = requests.Session()
        
    def get_player_stats(self, player_name: str, surface: str = "Hard") -> Optional[TennisPlayerStats]:
        """
        Get player statistics for Monte Carlo modeling.
        
        For PHASE 1: Returns mock data structure
        TODO: Integrate real ATP/WTA stats API
        """
        # Check cache first
        cached = self._load_from_cache(player_name)
        if cached:
            # Patch: If cached stats have JSON history, ensure it's present
            if hasattr(cached, 'json_stats') and cached.json_stats:
                self._inject_json_history(cached)
            return cached
        
        # PHASE 1: Mock data for testing
        # TODO: Replace with real API calls
        stats = self._generate_mock_stats(player_name, surface)

        # Apply optional L10 patch from local scraper (if present).
        try:
            stats = self._apply_l10_patches(stats)
        except Exception:
            # Patch lane must never break baseline stats.
            pass
        
        # Cache results (post-patch so Monte Carlo sees the blended values).
        self._save_to_cache(player_name, stats)
        
        # Patch: If stats have JSON history, inject
        if hasattr(stats, 'json_stats') and stats.json_stats:
            self._inject_json_history(stats)
        return stats

    def _inject_json_history(self, stats):
        """
        If stats.json_stats is present (parsed from ITF/Qualifier JSON),
        populate games_history and aces_history for Kalman/Bayesian filtering.
        """
        json_stats = getattr(stats, 'json_stats', None)
        if not json_stats:
            return
        # Example schema: {'games': [12, 14, 15, ...], 'aces': [7, 9, 8, ...]}
        games = json_stats.get('games')
        aces = json_stats.get('aces')
        if games:
            stats.games_history = games
        if aces:
            stats.aces_history = aces

    def _apply_l10_patches(self, stats: TennisPlayerStats) -> TennisPlayerStats:
        """Apply L10 form patches from ``stats_cache/l10_patches`` if available.

        This allows an external scraper to write per-player JSON files that
        contain L10 samples for various metrics. We then blend season baselines
        with those samples using the L10 Form Engine and update the *_l10 and
        *_std fields accordingly.
        """

        from .l10_form_engine import apply_l10_patch_from_dict

        player_key = stats.player.replace(" ", "_")
        patch_file = self.l10_patch_dir / f"{player_key}.json"

        if not patch_file.exists():
            return stats

        try:
            patch_dict = json.loads(patch_file.read_text())
        except Exception:
            return stats

        meta_summary: dict = {}

        # Aces
        if stats.aces_season > 0 or stats.aces_l10 > 0:
            base_mu = stats.aces_season or stats.aces_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.aces_std or 2.5,
                patch=patch_dict,
                key="aces",
            )
            stats.aces_l10 = updated_mu
            stats.aces_std = updated_sigma
            meta_summary["aces"] = meta.__dict__

        # Breakpoints won
        if stats.breakpoints_won_season > 0 or stats.breakpoints_won_l10 > 0:
            base_mu = stats.breakpoints_won_season or stats.breakpoints_won_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.breakpoints_won_std or 1.5,
                patch=patch_dict,
                key="breakpoints_won",
            )
            stats.breakpoints_won_l10 = updated_mu
            stats.breakpoints_won_std = updated_sigma
            meta_summary["breakpoints_won"] = meta.__dict__

        # Games won
        if stats.games_won_season > 0 or stats.games_won_l10 > 0:
            base_mu = stats.games_won_season or stats.games_won_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.games_won_std or 3.0,
                patch=patch_dict,
                key="games_won",
            )
            stats.games_won_l10 = updated_mu
            stats.games_won_std = updated_sigma
            meta_summary["games_won"] = meta.__dict__

        # Total games (both players)
        if stats.total_games_season > 0 or stats.total_games_l10 > 0:
            base_mu = stats.total_games_season or stats.total_games_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.total_games_std or 4.0,
                patch=patch_dict,
                key="total_games",
            )
            stats.total_games_l10 = updated_mu
            stats.total_games_std = updated_sigma
            meta_summary["total_games"] = meta.__dict__

        # Fantasy score (PrizePicks-style scoring)
        if stats.fantasy_score_season > 0 or stats.fantasy_score_l10 > 0:
            base_mu = stats.fantasy_score_season or stats.fantasy_score_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.fantasy_score_std or 8.0,
                patch=patch_dict,
                key="fantasy_score",
            )
            stats.fantasy_score_l10 = updated_mu
            stats.fantasy_score_std = updated_sigma
            meta_summary["fantasy_score"] = meta.__dict__

        # Double faults
        if stats.double_faults_season > 0 or stats.double_faults_l10 > 0:
            base_mu = stats.double_faults_season or stats.double_faults_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.double_faults_std or 1.5,
                patch=patch_dict,
                key="double_faults",
            )
            stats.double_faults_l10 = updated_mu
            stats.double_faults_std = updated_sigma
            meta_summary["double_faults"] = meta.__dict__

        # Tiebreakers played
        if stats.tiebreakers_season > 0 or stats.tiebreakers_l10 > 0:
            base_mu = stats.tiebreakers_season or stats.tiebreakers_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.tiebreakers_std or 0.6,
                patch=patch_dict,
                key="tiebreakers",
            )
            stats.tiebreakers_l10 = updated_mu
            stats.tiebreakers_std = updated_sigma
            meta_summary["tiebreakers"] = meta.__dict__

        # Sets won
        if stats.sets_won_season > 0 or stats.sets_won_l10 > 0:
            base_mu = stats.sets_won_season or stats.sets_won_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.sets_won_std or 0.8,
                patch=patch_dict,
                key="sets_won",
            )
            stats.sets_won_l10 = updated_mu
            stats.sets_won_std = updated_sigma
            meta_summary["sets_won"] = meta.__dict__

        # Sets played
        if stats.sets_played_season > 0 or stats.sets_played_l10 > 0:
            base_mu = stats.sets_played_season or stats.sets_played_l10
            updated_mu, updated_sigma, meta = apply_l10_patch_from_dict(
                old_mu=base_mu,
                old_sigma=stats.sets_played_std or 0.5,
                patch=patch_dict,
                key="sets_played",
            )
            stats.sets_played_l10 = updated_mu
            stats.sets_played_std = updated_sigma
            meta_summary["sets_played"] = meta.__dict__

        # Optional diagnostics: write meta summary alongside the patch so
        # calibration / render layers can inspect how aggressively L10
        # influenced each metric. This is purely informational.
        if meta_summary:
            try:
                meta_file = self.l10_patch_dir / f"{player_key}_meta.json"
                payload = {
                    "player": stats.player,
                    "surface": patch_dict.get("surface", "ALL"),
                    "metrics": meta_summary,
                }
                meta_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            except Exception:
                pass

        return stats
    
    def _generate_mock_stats(self, player: str, surface: str) -> TennisPlayerStats:
        """
        Generate mock stats for testing.
        TODO: Remove when real API integrated
        """
        # Base stats (realistic ranges)
        base_aces = 5.0
        base_bp_won = 3.5
        base_games_won = 12.0
        base_fantasy = 25.0
        base_total_games = 22.0  # Combined both players
        base_double_faults = 2.5
        base_tiebreakers = 0.8
        base_sets_won = 1.5
        base_sets_played = 2.5
        
        # Add some player-specific variation
        import hashlib
        player_hash = int(hashlib.md5(player.encode()).hexdigest(), 16)
        variation = (player_hash % 10) / 10.0  # 0.0 to 0.9
        
        return TennisPlayerStats(
            player=player,
            aces_l5=base_aces + variation,
            aces_l10=base_aces + variation * 0.8,
            aces_season=base_aces,
            aces_std=2.5,
            
            breakpoints_won_l5=base_bp_won + variation,
            breakpoints_won_l10=base_bp_won + variation * 0.8,
            breakpoints_won_season=base_bp_won,
            breakpoints_won_std=1.5,
            
            games_won_l5=base_games_won + variation * 2,
            games_won_l10=base_games_won + variation * 1.5,
            games_won_season=base_games_won,
            games_won_std=3.0,
            
            fantasy_score_l5=base_fantasy + variation * 5,
            fantasy_score_l10=base_fantasy + variation * 4,
            fantasy_score_season=base_fantasy,
            fantasy_score_std=8.0,
            
            total_games_l5=base_total_games + variation * 3,
            total_games_l10=base_total_games + variation * 2,
            total_games_season=base_total_games,
            total_games_std=4.0,
            
            double_faults_l5=base_double_faults + variation * 0.5,
            double_faults_l10=base_double_faults + variation * 0.4,
            double_faults_season=base_double_faults,
            double_faults_std=1.5,
            
            tiebreakers_l5=base_tiebreakers + variation * 0.2,
            tiebreakers_l10=base_tiebreakers + variation * 0.15,
            tiebreakers_season=base_tiebreakers,
            tiebreakers_std=0.6,
            
            sets_won_l5=base_sets_won + variation * 0.3,
            sets_won_l10=base_sets_won + variation * 0.2,
            sets_won_season=base_sets_won,
            sets_won_std=0.8,
            
            sets_played_l5=base_sets_played + variation * 0.2,
            sets_played_l10=base_sets_played + variation * 0.15,
            sets_played_season=base_sets_played,
            sets_played_std=0.5,
            
            surface=surface,
            surface_adjustment=1.0,
            opponent_strength=1.0,
            matches_played=10,
            last_updated=datetime.now().isoformat()
        )
    
    def _load_from_cache(self, player: str) -> Optional[TennisPlayerStats]:
        """Load stats from cache if recent"""
        cache_file = self.cache_dir / f"{player.replace(' ', '_')}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            data = json.loads(cache_file.read_text())
            
            # Check if cache is recent (< 24 hours)
            cached_time = datetime.fromisoformat(data['last_updated'])
            if datetime.now() - cached_time > timedelta(hours=24):
                return None
            
            return TennisPlayerStats(**data)
        except Exception:
            return None
    
    def _save_to_cache(self, player: str, stats: TennisPlayerStats):
        """Save stats to cache"""
        cache_file = self.cache_dir / f"{player.replace(' ', '_')}.json"
        
        data = {
            'player': stats.player,
            'aces_l5': stats.aces_l5,
            'aces_l10': stats.aces_l10,
            'aces_season': stats.aces_season,
            'aces_std': stats.aces_std,
            'breakpoints_won_l5': stats.breakpoints_won_l5,
            'breakpoints_won_l10': stats.breakpoints_won_l10,
            'breakpoints_won_season': stats.breakpoints_won_season,
            'breakpoints_won_std': stats.breakpoints_won_std,
            'games_won_l5': stats.games_won_l5,
            'games_won_l10': stats.games_won_l10,
            'games_won_season': stats.games_won_season,
            'games_won_std': stats.games_won_std,
            'fantasy_score_l5': stats.fantasy_score_l5,
            'fantasy_score_l10': stats.fantasy_score_l10,
            'fantasy_score_season': stats.fantasy_score_season,
            'fantasy_score_std': stats.fantasy_score_std,
            'total_games_l5': stats.total_games_l5,
            'total_games_l10': stats.total_games_l10,
            'total_games_season': stats.total_games_season,
            'total_games_std': stats.total_games_std,
            'double_faults_l5': stats.double_faults_l5,
            'double_faults_l10': stats.double_faults_l10,
            'double_faults_season': stats.double_faults_season,
            'double_faults_std': stats.double_faults_std,
            'tiebreakers_l5': stats.tiebreakers_l5,
            'tiebreakers_l10': stats.tiebreakers_l10,
            'tiebreakers_season': stats.tiebreakers_season,
            'tiebreakers_std': stats.tiebreakers_std,
            'sets_won_l5': stats.sets_won_l5,
            'sets_won_l10': stats.sets_won_l10,
            'sets_won_season': stats.sets_won_season,
            'sets_won_std': stats.sets_won_std,
            'sets_played_l5': stats.sets_played_l5,
            'sets_played_l10': stats.sets_played_l10,
            'sets_played_season': stats.sets_played_season,
            'sets_played_std': stats.sets_played_std,
            'surface': stats.surface,
            'surface_adjustment': stats.surface_adjustment,
            'opponent_strength': stats.opponent_strength,
            'matches_played': stats.matches_played,
            'last_updated': stats.last_updated
        }
        
        cache_file.write_text(json.dumps(data, indent=2))


# Quick test
if __name__ == "__main__":
    api = TennisStatsAPI()
    
    # Test players
    players = ["Jannik Sinner", "Carlos Alcaraz", "Novak Djokovic"]
    
    for player in players:
        stats = api.get_player_stats(player)
        print(f"\n{player}:")
        print(f"  Aces (L10): {stats.aces_l10:.2f} ± {stats.aces_std:.2f}")
        print(f"  BP Won (L10): {stats.breakpoints_won_l10:.2f} ± {stats.breakpoints_won_std:.2f}")
        print(f"  Games Won (L10): {stats.games_won_l10:.2f} ± {stats.games_won_std:.2f}")
        print(f"  Fantasy Score (L10): {stats.fantasy_score_l10:.2f} ± {stats.fantasy_score_std:.2f}")
        print(f"  Total Games (L10): {stats.total_games_l10:.2f} ± {stats.total_games_std:.2f}")
        print(f"  Double Faults (L10): {stats.double_faults_l10:.2f} ± {stats.double_faults_std:.2f}")
        print(f"  Tiebreakers (L10): {stats.tiebreakers_l10:.2f} ± {stats.tiebreakers_std:.2f}")
        print(f"  Sets Won (L10): {stats.sets_won_l10:.2f} ± {stats.sets_won_std:.2f}")
        print(f"  Sets Played (L10): {stats.sets_played_l10:.2f} ± {stats.sets_played_std:.2f}")
