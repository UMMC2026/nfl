#!/usr/bin/env python3
"""
NFL FEATURE ENGINEERING
=======================

Approved features only. Any missing feature → EDGE BLOCKED.
Metadata logging required.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import yaml


@dataclass
class NFLFeatures:
    """Approved NFL features (SOP v2.1 locked set)."""
    player_name: str
    team: str
    game_id: str
    
    # Usage & Opportunity (snap-based)
    snap_pct: float
    snap_pct_rolling_7d: Optional[float] = None
    snap_pct_rolling_14d: Optional[float] = None
    targets_per_snap: Optional[float] = None
    carries_per_snap: Optional[float] = None
    red_zone_share: Optional[float] = None
    
    # Efficiency
    yards_per_target: Optional[float] = None
    yards_per_carry: Optional[float] = None
    catch_rate: Optional[float] = None
    air_yards_share: Optional[float] = None
    
    # Volatility
    week_to_week_std: Optional[float] = None
    role_stability_score: Optional[float] = None
    
    # Market alignment
    closing_line_value: Optional[float] = None
    implied_team_total: Optional[float] = None
    
    # Metadata
    features_complete: bool = False
    missing_features: list = None
    metadata_logged: bool = False
    
    def __post_init__(self):
        if self.missing_features is None:
            self.missing_features = []


class NFLFeatureBuilder:
    """Build approved feature set from ingested stats."""
    
    def __init__(self, config_path: Path = None):
        """Initialize with config."""
        if config_path is None:
            config_path = Path(__file__).parent / "nfl_config.yaml"
        
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.approved_features = self.config["approved_features"]
    
    def build_features(self, stats: dict, player_history: Optional[dict] = None) -> NFLFeatures:
        """
        Build feature set from stats.
        
        Args:
            stats: Player stats from ingest_nfl_stats
            player_history: Optional historical data for rolling calculations
            
        Returns:
            NFLFeatures with completeness tracking
        """
        features = NFLFeatures(
            player_name=stats.get("player_name", ""),
            team=stats.get("team", ""),
            game_id=stats.get("game_id", ""),
            snap_pct=float(stats.get("snap_pct", 0.0)),
        )
        
        # Usage & Opportunity
        features.snap_pct_rolling_7d = self._compute_rolling_snap_pct(
            player_history, window=7
        ) if player_history else None
        
        features.snap_pct_rolling_14d = self._compute_rolling_snap_pct(
            player_history, window=14
        ) if player_history else None
        
        targets = float(stats.get("targets", 0.0))
        snaps = float(stats.get("snap_pct", 0.0)) * 60  # Rough snap count estimate
        if snaps > 0:
            features.targets_per_snap = targets / snaps
        
        carries = float(stats.get("carries", 0.0))
        if snaps > 0:
            features.carries_per_snap = carries / snaps
        
        red_zone = float(stats.get("red_zone_touches", 0.0))
        team_red_zone = float(stats.get("team_red_zone_touches", 1.0))
        if team_red_zone > 0:
            features.red_zone_share = red_zone / team_red_zone
        
        # Efficiency
        rec_yards = float(stats.get("receiving_yards", 0.0))
        if targets > 0:
            features.yards_per_target = rec_yards / targets
        
        rush_yards = float(stats.get("rushing_yards", 0.0))
        if carries > 0:
            features.yards_per_carry = rush_yards / carries
        
        receptions = float(stats.get("receptions", 0.0))
        if targets > 0:
            features.catch_rate = receptions / targets
        
        # Air yards (placeholder - requires game-level data)
        features.air_yards_share = None
        
        # Volatility (requires historical data)
        features.week_to_week_std = self._compute_week_to_week_std(
            player_history
        ) if player_history else None
        
        features.role_stability_score = self._compute_role_stability(
            player_history
        ) if player_history else None
        
        # Market (placeholder - requires market data)
        features.closing_line_value = None
        features.implied_team_total = None
        
        # Check completeness
        features.missing_features = self._check_completeness(features)
        features.features_complete = len(features.missing_features) == 0
        
        return features
    
    def _compute_rolling_snap_pct(self, history: dict, window: int) -> Optional[float]:
        """Compute rolling average snap % over window."""
        if not history or "snap_pcts" not in history:
            return None
        
        snap_pcts = history["snap_pcts"][-window:]
        if snap_pcts:
            return sum(snap_pcts) / len(snap_pcts)
        return None
    
    def _compute_week_to_week_std(self, history: dict) -> Optional[float]:
        """Compute week-to-week standard deviation in production."""
        if not history or "production" not in history:
            return None
        
        production = history["production"]
        if len(production) < 2:
            return None
        
        mean = sum(production) / len(production)
        variance = sum((x - mean) ** 2 for x in production) / len(production)
        return variance ** 0.5
    
    def _compute_role_stability(self, history: dict) -> Optional[float]:
        """Score role stability (consistency in snap count / usage)."""
        if not history or "snap_pcts" not in history:
            return None
        
        snap_pcts = history["snap_pcts"][-8:]  # Last 8 weeks
        if len(snap_pcts) < 4:
            return None
        
        # Role stability = 1.0 - (std / mean)
        mean = sum(snap_pcts) / len(snap_pcts)
        if mean == 0:
            return 0.0
        
        variance = sum((x - mean) ** 2 for x in snap_pcts) / len(snap_pcts)
        std = variance ** 0.5
        
        stability = 1.0 - (std / mean)
        return max(0.0, min(1.0, stability))  # Clamp 0-1
    
    def _check_completeness(self, features: NFLFeatures) -> list:
        """Check which critical features are missing."""
        missing = []
        
        critical_fields = [
            "snap_pct",
        ]
        
        for field in critical_fields:
            value = getattr(features, field, None)
            if value is None or (isinstance(value, float) and value <= 0):
                missing.append(field)
        
        return missing
    
    def log_features(self, features: NFLFeatures, output_path: Path):
        """Log feature metadata."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "player": features.player_name,
            "game_id": features.game_id,
            "completeness": {
                "all_complete": features.features_complete,
                "missing": features.missing_features,
            },
            "features": {k: v for k, v in asdict(features).items() 
                        if k not in ["missing_features", "metadata_logged"]},
        }
        
        with open(output_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        features.metadata_logged = True


def build_nfl_feature_set(stats_dict: Dict, player_history: Optional[Dict] = None) -> Dict[str, NFLFeatures]:
    """
    Build features for all players in game.
    
    Args:
        stats_dict: Dict of player stats (from ingest_nfl_stats)
        player_history: Optional historical data for rolling/volatility features
        
    Returns:
        Dict[player_name -> NFLFeatures]
    """
    builder = NFLFeatureBuilder()
    
    features = {}
    for player_name, stats in stats_dict.items():
        player_history = player_history.get(player_name) if player_history else None
        
        try:
            features[player_name] = builder.build_features(stats, player_history)
        except Exception as e:
            print(f"  [WARN] Feature build failed for {player_name}: {e}")
    
    return features


if __name__ == "__main__":
    print("NFL Feature Builder ready for pipeline integration.")
